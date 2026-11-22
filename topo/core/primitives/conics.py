"""
topo/core/primitives/conics.py
------------------------------
Le coniche (D285, D288): i pezzi di curva su A·x² + B·xy + C·y² + D·x + E·y + F = 0.
`EllipseSeg` (B² − 4AC < 0), con `CircleSeg` figlia (semiassi uguali, D287);
`ParabolaSeg` (= 0) e `HyperbolaSeg` (> 0, un ramo). Ognuna è un centro (o
vertice), dei vettori e un intervallo del parametro; l'equazione si ricava
da loro. Una conica diventa esatta in spline razionale quadratica
(`to_bspline`) per chi la deve scrivere dove la conica non c'è.

Discretizzazione per dimostrazione: fra due punti a distanza h di parametro
lo scarto dalla corda è al più h²/8 · max|P''| sul tratto. La griglia parte
dal parametro 0, così un pezzo ha i vertici della curva intera (D145, D153).
"""

from __future__ import annotations

import math
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Tuple

from ...precision import FLOAT_NOISE
from .segments import (
    DEFAULT_TOLERANCE, Algebra, BSplineSeg, MathSeg, Point, _angular_sweep, _check_factor, _circle_sides,
    _grid_angles, _mirror_point, _plain, _real, _rotate_point, _scale_point, _translate_point,
    point_on_circle,
)

_Equation = Tuple[float, float, float, float, float, float]


class ConicSeg(MathSeg):
    """
    A piece of a conic: a curve on A·x² + B·xy + C·y² + D·x + E·y + F = 0.
    The sign of B² − 4AC says which: < 0 an ellipse (a circle when A = C and
    B = 0), = 0 a parabola, > 0 a hyperbola.
    """

    @property
    @abstractmethod
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        """(A, B, C, D, E, F) of the conic the piece lies on, up to a common factor."""

    @property
    def algebra(self) -> Algebra:
        return "rational"


def _ellipse_equation(center: Point, axis: Point, a: float, b: float) -> Tuple[float, float, float, float, float, float]:
    """(A..F) dell'ellisse di centro `center`, semiasse `a` lungo il versore
    `axis` e `b` a 90°: x'²/a² + y'²/b² = 1 nel suo riferimento, espansa."""
    ux, uy = axis
    p = ux * ux / (a * a) + uy * uy / (b * b)
    q = 2 * ux * uy * (1 / (a * a) - 1 / (b * b))
    r = uy * uy / (a * a) + ux * ux / (b * b)
    cx, cy = center
    return (p, q, r, -2 * p * cx - q * cy, -q * cx - 2 * r * cy, p * cx * cx + q * cx * cy + r * cy * cy - 1)


# ---------------------------------------------------------------------------
# EllipseSeg
# ---------------------------------------------------------------------------

@dataclass
class EllipseSeg(ConicSeg):
    """
    A piece of the ellipse P(s) = center + cos(s)·major_axis + sin(s)·ratio·
    (major_axis turned +90°): the unit circle seen through a linear map.
    `major_axis` is the vector from the centre to the end of the long axis
    (its length is the semi-major axis a), `ratio` = b / a. `s` runs from
    `start_param` to `end_param`, counter-clockwise when `ccw`; the whole
    ellipse is 0 to 2π. `t` is the parameter walked from the start, t in
    [0, sweep].
    """
    center: Point
    major_axis: Point   # vettore dal centro, non un punto assoluto
    ratio: float         # semiasse minore / semiasse maggiore, 0 < ratio <= 1
    start_param: float   # radianti
    end_param: float     # radianti
    ccw: bool = True

    def __post_init__(self):
        self.center, self.major_axis = _plain(self.center), _plain(self.major_axis)
        self.ratio = _real(self.ratio)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        # asse nullo o ratio 0 è un punto o un segmento, non un'ellisse (D154)
        if not (math.hypot(*self.major_axis) > 0 and self.ratio > 0):
            raise ValueError(f"degenerate ellipse: axis {self.major_axis}, ratio {self.ratio}")

    def _sweep(self) -> float:
        """Angolo (parametro) spazzato in radianti, sempre positivo."""
        return _angular_sweep(self.start_param, self.end_param, self.ccw)

    def _point_at(self, t: float) -> Point:
        """center + cos(t)·major_axis + sin(t)·ratio·(major_axis ruotato di +90°)."""
        mx, my = self.major_axis
        nx, ny = -my * self.ratio, mx * self.ratio
        return (
            self.center[0] + math.cos(t) * mx + math.sin(t) * nx,
            self.center[1] + math.cos(t) * my + math.sin(t) * ny,
        )

    def endpoints(self) -> Tuple[Point, Point]:
        return self._point_at(self.start_param), self._point_at(self.end_param)

    @property
    def t_range(self) -> Tuple[float, float]:
        """`t` è il parametro percorso da `start_param`: t in [0, sweep]."""
        return (0.0, self._sweep())

    def point_at(self, t: float) -> Point:
        return self._point_at(self.start_param + (t if self.ccw else -t))

    def derivative_at(self, t: float) -> Point:
        u = self.start_param + (t if self.ccw else -t)
        sign = 1.0 if self.ccw else -1.0
        (mx, my), r = self.major_axis, self.ratio
        return (sign * (-math.sin(u) * mx - math.cos(u) * my * r), sign * (-math.sin(u) * my + math.cos(u) * mx * r))

    @property
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        a = math.hypot(*self.major_axis)
        return _ellipse_equation(self.center, (self.major_axis[0] / a, self.major_axis[1] / a), a, a * self.ratio)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza sulla griglia del parametro (D153): l'ellisse è il cerchio
        del semiasse maggiore `a` visto attraverso una mappa lineare che non
        allunga nessun vettore (fattori 1 e ratio), quindi i vertici k·2π/N di
        `_circle_sides(a, tolerance)` portati sull'ellisse restano entro
        `tolerance` come sul cerchio. Gli estremi esatti più i punti di griglia
        fra loro, come `CircleSeg`: un'ellisse tagliata in pezzi dà il poligono
        dell'ellisse intera, una percorsa al contrario gli stessi punti.
        """
        total_angle = self._sweep()
        if total_angle < 1e-12:
            pt = self._point_at(self.start_param)
            return [pt, pt]

        # ratio > 1 (l'asse dato è il minore): il fattore più grande è ratio
        radius = math.hypot(*self.major_axis) * max(1.0, self.ratio)
        sides = _circle_sides(radius, tolerance)
        if self.ccw:
            params = _grid_angles(self.start_param, self.start_param + total_angle, radius, sides)
        else:
            params = _grid_angles(self.start_param - total_angle, self.start_param, radius, sides)[::-1]
        return [self._point_at(t) for t in params]

    def reversed(self) -> "EllipseSeg":
        """Stessa ellisse fisica, percorsa al contrario: scambia i parametri e nega ccw."""
        return EllipseSeg(
            center=self.center,
            major_axis=self.major_axis,
            ratio=self.ratio,
            start_param=self.end_param,
            end_param=self.start_param,
            ccw=not self.ccw,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "EllipseSeg":
        """
        Stessa ellisse fisica, ruotata di `angle` radianti attorno a `origin`:
        il centro trasla con la rotazione, `major_axis` (vettore) ruota
        attorno a (0, 0) — mai traslato — che è già come un'ellisse ruota
        nella sua stessa parametrizzazione, senza toccare `start_param`/
        `end_param` (relativi a `major_axis`, non a coordinate assolute).
        """
        return EllipseSeg(
            center=_rotate_point(self.center, angle, origin),
            major_axis=_rotate_point(self.major_axis, angle, (0.0, 0.0)),
            ratio=self.ratio,
            start_param=self.start_param,
            end_param=self.end_param,
            ccw=self.ccw,
        )

    def translated(self, dx: float, dy: float) -> "EllipseSeg":
        """Stessa ellisse, spostata di (`dx`, `dy`): si sposta solo il centro."""
        return EllipseSeg(center=_translate_point(self.center, dx, dy), major_axis=self.major_axis,
                          ratio=self.ratio, start_param=self.start_param, end_param=self.end_param,
                          ccw=self.ccw)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "EllipseSeg":
        """
        Stessa ellisse, specchiata sulla retta per `origin` a `angle` radianti
        (default: l'asse x). Il semiasse minore è `ratio`·(asse maggiore
        ruotato di +90°): uno specchio, su qualunque asse, inverte la
        rotazione di 90°, quindi il minore ricavato dall'asse maggiore
        specchiato punta dalla parte opposta all'immagine del minore. Il punto
        al parametro `t` va al parametro `−t`: parametri col segno cambiato e
        verso invertito. `major_axis` è un vettore: si specchia sulla
        direzione dell'asse, senza traslarlo.
        """
        return EllipseSeg(center=_mirror_point(self.center, origin, angle),
                          major_axis=_mirror_point(self.major_axis, (0.0, 0.0), angle),
                          ratio=self.ratio, start_param=-self.start_param, end_param=-self.end_param,
                          ccw=not self.ccw)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "EllipseSeg":
        """Stessa ellisse, scalata di `factor` (> 0) attorno a `origin`: il
        centro si sposta, il vettore `major_axis` si allunga, `ratio` e
        parametri non cambiano."""
        factor = _check_factor(factor)
        return EllipseSeg(center=_scale_point(self.center, factor, origin),
                          major_axis=(self.major_axis[0] * factor, self.major_axis[1] * factor),
                          ratio=self.ratio, start_param=self.start_param, end_param=self.end_param,
                          ccw=self.ccw)


# ---------------------------------------------------------------------------
# CircleSeg: arco o cerchio intero
# ---------------------------------------------------------------------------

class CircleSeg(EllipseSeg):
    """A piece of the circle (`center`, `radius`) from `start_angle` to
    `end_angle`, counter-clockwise when `ccw`; with no angles the whole
    circle from angle 0. A circle is an arc that goes all the way round
    (`full`, D286), and an ellipse with equal semi-axes (D287): its axis is
    (radius, 0), so the ellipse's parameter is the angle. `t` is the angle
    walked from the start: t in [0, sweep]."""

    def __init__(self, center: Point, radius: float, start_angle: float = 0.0,
                 end_angle: float = 2 * math.pi, ccw: bool = True):
        radius = _real(radius)
        # raggio 0 è un punto, non una curva (D154)
        if not radius > 0:
            raise ValueError(f"the radius must be positive, got {radius}")
        super().__init__(center=center, major_axis=(radius, 0.0), ratio=1.0,
                         start_param=start_angle, end_param=end_angle, ccw=ccw)

    @property
    def radius(self) -> float:
        return self.major_axis[0]

    @property
    def start_angle(self) -> float:
        return self.start_param

    @property
    def end_angle(self) -> float:
        return self.end_param

    def __repr__(self) -> str:
        return (f"CircleSeg(center={self.center!r}, radius={self.radius!r}, start_angle={self.start_angle!r}, "
                f"end_angle={self.end_angle!r}, ccw={self.ccw!r})")

    def _sweep(self) -> float:
        """Angolo spazzato in radianti, sempre positivo."""
        return _angular_sweep(self.start_angle, self.end_angle, self.ccw)

    @property
    def full(self) -> bool:
        """True when the piece goes all the way round: the whole circle."""
        return self._sweep() == 2 * math.pi

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza sulla griglia del cerchio (`_circle_sides`, ancorata
        all'angolo 0, D145): gli estremi esatti più i vertici della griglia
        che cadono fra loro, così ogni arco si sovrappone al cerchio intero.
        Sagitta <= tolerance. Anche il giro intero: un cerchio e i suoi archi
        hanno gli stessi vertici, da qualunque angolo parta.
        """
        total_angle = self._sweep()

        if total_angle < 1e-12:
            # Arco nullo
            start_pt = self._point_at(self.start_angle)
            return [start_pt, start_pt]

        sides = _circle_sides(self.radius, tolerance)
        if self.ccw:
            angles = _grid_angles(self.start_angle, self.start_angle + total_angle, self.radius, sides)
        else:
            angles = _grid_angles(self.start_angle - total_angle, self.start_angle, self.radius, sides)[::-1]
        return [self._point_at(a) for a in angles]

    def _point_at(self, angle: float) -> Point:
        """Punto sull'arco all'angolo dato (radianti)."""
        return point_on_circle(self.center, self.radius, angle)

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, self._sweep())

    def point_at(self, t: float) -> Point:
        return self._point_at(self.start_angle + (t if self.ccw else -t))

    def derivative_at(self, t: float) -> Point:
        a = self.start_angle + (t if self.ccw else -t)
        sign = 1.0 if self.ccw else -1.0
        return (-sign * self.radius * math.sin(a), sign * self.radius * math.cos(a))

    @property
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        return _ellipse_equation(self.center, (1.0, 0.0), self.radius, self.radius)

    def reversed(self) -> "CircleSeg":
        """Stesso arco fisico, percorso al contrario: scambia gli angoli e nega ccw."""
        return CircleSeg(
            center=self.center,
            radius=self.radius,
            start_angle=self.end_angle,
            end_angle=self.start_angle,
            ccw=not self.ccw,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "CircleSeg":
        """
        Stesso arco fisico, ruotato di `angle` radianti attorno a `origin`:
        il centro trasla con la rotazione, `start_angle`/`end_angle` si
        spostano dello stesso `angle` (il raggio e il verso non cambiano).
        """
        return CircleSeg(
            center=_rotate_point(self.center, angle, origin),
            radius=self.radius,
            start_angle=self.start_angle + angle,
            end_angle=self.end_angle + angle,
            ccw=self.ccw,
        )

    def translated(self, dx: float, dy: float) -> "CircleSeg":
        """Stesso arco, spostato di (`dx`, `dy`): si sposta solo il centro."""
        return CircleSeg(center=_translate_point(self.center, dx, dy), radius=self.radius,
                      start_angle=self.start_angle, end_angle=self.end_angle, ccw=self.ccw)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "CircleSeg":
        """
        Stesso arco, specchiato sulla retta per `origin` a `angle` radianti
        (default: l'asse x): il punto all'angolo `a` va all'angolo
        `2·angle − a`, quindi il verso si inverte. Sull'asse x la griglia del
        cerchio (D145, ancorata all'angolo 0) è simmetrica e l'arco specchiato
        ha i vertici specchiati; su un altro asse la curva è esatta e i
        vertici cadono sulla griglia dell'arco nuovo.
        """
        return CircleSeg(center=_mirror_point(self.center, origin, angle), radius=self.radius,
                      start_angle=2 * angle - self.start_angle, end_angle=2 * angle - self.end_angle,
                      ccw=not self.ccw)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "CircleSeg":
        """Stesso arco, scalato di `factor` (> 0) attorno a `origin`: il centro
        si sposta, il raggio si moltiplica, angoli e verso non cambiano."""
        factor = _check_factor(factor)
        return CircleSeg(center=_scale_point(self.center, factor, origin), radius=self.radius * factor,
                      start_angle=self.start_angle, end_angle=self.end_angle, ccw=self.ccw)

    @classmethod
    def from_ends(cls, start: Point, end: Point, sweep: float) -> "CircleSeg":
        """The arc from `start` to `end` that turns through `sweep` radians:
        positive counter-clockwise, negative clockwise, 0 < |sweep| < 2π."""
        if not 0 < abs(sweep) < 2 * math.pi:
            raise ValueError(f"the sweep must be in (0, 2π) either way, got {sweep}")
        half_chord = math.dist(start, end) / 2.0
        if not half_chord > 0:
            # corda nulla: raggio 0, con numpy un arco NaN invece di un errore (D154)
            raise ValueError("zero chord: a point, not an arc")
        ccw = sweep > 0
        turn = abs(sweep)
        radius = half_chord / math.sin(turn / 2.0)
        # dal punto medio della corda il centro sta sulla perpendicolare, a
        # sinistra se l'arco gira antiorario; a r·cos(turn/2) con segno: oltre
        # mezzo giro il centro passa dall'altra parte della corda
        nx, ny = -(end[1] - start[1]) / (2 * half_chord), (end[0] - start[0]) / (2 * half_chord)
        d = (1.0 if ccw else -1.0) * radius * math.cos(turn / 2.0)
        cx, cy = (start[0] + end[0]) / 2.0 + d * nx, (start[1] + end[1]) / 2.0 + d * ny
        return cls(center=(cx, cy), radius=radius,
                   start_angle=math.atan2(start[1] - cy, start[0] - cx),
                   end_angle=math.atan2(end[1] - cy, end[0] - cx), ccw=ccw)


def is_full_circle(segment) -> bool:
    """Un `CircleSeg` che fa tutto il giro."""
    return isinstance(segment, CircleSeg) and segment.full


def is_arc(segment) -> bool:
    """Un `CircleSeg` che non fa tutto il giro: un arco."""
    return isinstance(segment, CircleSeg) and not segment.full



def _walk(start: float, end: float) -> float:
    """+1 se il parametro cresce da `start` a `end`, −1 se cala."""
    return 1.0 if end >= start else -1.0


def _grid(lo: float, hi: float, step_at) -> List[float]:
    """I parametri da `lo` a `hi` (lo < hi): i due estremi esatti e, fra loro,
    i punti della griglia che parte da 0 e avanza di `step_at(|s|)` verso
    ciascun lato. Un pezzo cade sulla griglia della curva intera."""
    snap = (hi - lo) * FLOAT_NOISE
    marks = []
    for sign in (1.0, -1.0):
        t = 0.0 if sign > 0 else step_at(0.0)
        while (sign * t < hi) if sign > 0 else (sign * t > lo):
            if lo + snap < sign * t < hi - snap:
                marks.append(sign * t)
            t += step_at(t)
    return [lo] + sorted(marks) + [hi]


@dataclass
class ParabolaSeg(ConicSeg):
    """
    A piece of the parabola with vertex `vertex` and focus `focus`:
    P(s) = vertex + s·n + s²/(4f)·u, u the unit axis towards the focus, n the
    axis turned +90°, f the vertex–focus distance. `s` runs from
    `start_param` to `end_param` (either way round); `t` is the parameter
    walked from the start, t in [0, |end_param − start_param|].
    """
    vertex: Point
    focus: Point
    start_param: float
    end_param: float

    def __post_init__(self):
        self.vertex, self.focus = _plain(self.vertex), _plain(self.focus)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not math.dist(self.vertex, self.focus) > 0:
            raise ValueError(f"degenerate parabola: vertex and focus coincide at {self.vertex}")

    def _frame(self) -> Tuple[float, Point, Point]:
        """(f, u, n): distanza focale, asse verso il fuoco, asse ruotato di +90°."""
        dx, dy = self.focus[0] - self.vertex[0], self.focus[1] - self.vertex[1]
        f = math.hypot(dx, dy)
        u = (dx / f, dy / f)
        return f, u, (-u[1], u[0])

    def _point(self, s: float) -> Point:
        f, u, n = self._frame()
        q = s * s / (4 * f)
        return (self.vertex[0] + s * n[0] + q * u[0], self.vertex[1] + s * n[1] + q * u[1])

    @property
    def algebra(self) -> Algebra:
        """Polinomiale: s e s² nel suo riferimento (ellisse e iperbole no)."""
        return "polynomial"

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    def point_at(self, t: float) -> Point:
        return self._point(self.start_param + _walk(self.start_param, self.end_param) * t)

    def derivative_at(self, t: float) -> Point:
        sign = _walk(self.start_param, self.end_param)
        s = self.start_param + sign * t
        f, u, n = self._frame()
        q = s / (2 * f)
        return (sign * (n[0] + q * u[0]), sign * (n[1] + q * u[1]))

    @property
    def equation(self) -> _Equation:
        """(n·(p − V))² − 4f·u·(p − V) = 0, espansa."""
        f, (ux, uy), (nx, ny) = self._frame()
        vx, vy = self.vertex
        nv, uv = nx * vx + ny * vy, ux * vx + uy * vy
        return (nx * nx, 2 * nx * ny, ny * ny, -2 * nx * nv - 4 * f * ux, -2 * ny * nv - 4 * f * uy,
                nv * nv + 4 * f * uv)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """|P''| = 1/(2f) costante: il passo h = √(16·f·tol) tiene ogni corda entro `tolerance`."""
        f, _, _ = self._frame()
        step = math.sqrt(16 * f * tolerance)
        lo, hi = sorted((self.start_param, self.end_param))
        snap = (hi - lo) * FLOAT_NOISE
        params = [lo] + [k * step for k in range(math.floor(lo / step) + 1, math.ceil(hi / step))
                         if lo + snap < k * step < hi - snap] + [hi]
        if self.start_param > self.end_param:
            params.reverse()
        return [self._point(s) for s in params]

    def to_bspline(self) -> BSplineSeg:
        """La stessa curva come spline quadratica (peso 1): esatta, non un'approssimazione."""
        a, b = self.start_param, self.end_param
        f, u, n = self._frame()
        q = a * b / (4 * f)
        middle = (self.vertex[0] + (a + b) / 2 * n[0] + q * u[0], self.vertex[1] + (a + b) / 2 * n[1] + q * u[1])
        return BSplineSeg(degree=2, control_points=[self._point(a), middle, self._point(b)], knots=[0, 0, 0, 1, 1, 1])

    def reversed(self) -> "ParabolaSeg":
        return ParabolaSeg(self.vertex, self.focus, self.end_param, self.start_param)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "ParabolaSeg":
        return ParabolaSeg(_rotate_point(self.vertex, angle, origin), _rotate_point(self.focus, angle, origin),
                           self.start_param, self.end_param)

    def translated(self, dx: float, dy: float) -> "ParabolaSeg":
        return ParabolaSeg(_translate_point(self.vertex, dx, dy), _translate_point(self.focus, dx, dy),
                           self.start_param, self.end_param)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "ParabolaSeg":
        """Uno specchio inverte n rispetto a u: il punto a `s` va a `−s`."""
        return ParabolaSeg(_mirror_point(self.vertex, origin, angle), _mirror_point(self.focus, origin, angle),
                           -self.start_param, -self.end_param)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "ParabolaSeg":
        """f diventa factor·f e il punto a `s` va a `factor·s`."""
        factor = _check_factor(factor)
        return ParabolaSeg(_scale_point(self.vertex, factor, origin), _scale_point(self.focus, factor, origin),
                           self.start_param * factor, self.end_param * factor)


@dataclass
class HyperbolaSeg(ConicSeg):
    """
    A piece of one branch of the hyperbola with centre `center`:
    P(s) = center + cosh(s)·major_axis + sinh(s)·ratio·(major_axis turned
    +90°). `major_axis` is the vector from the centre to the branch's vertex
    (length a), `ratio` = b / a > 0. `s` runs from `start_param` to
    `end_param` (either way round); `t` is the parameter walked from the
    start, t in [0, |end_param − start_param|].
    """
    center: Point
    major_axis: Point
    ratio: float
    start_param: float
    end_param: float

    def __post_init__(self):
        self.center, self.major_axis = _plain(self.center), _plain(self.major_axis)
        self.ratio = _real(self.ratio)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not (math.hypot(*self.major_axis) > 0 and self.ratio > 0):
            raise ValueError(f"degenerate hyperbola: axis {self.major_axis}, ratio {self.ratio}")

    def _minor(self) -> Point:
        mx, my = self.major_axis
        return (-my * self.ratio, mx * self.ratio)

    def _point(self, s: float) -> Point:
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        c, h = math.cosh(s), math.sinh(s)
        return (self.center[0] + c * mx + h * nx, self.center[1] + c * my + h * ny)

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    def point_at(self, t: float) -> Point:
        return self._point(self.start_param + _walk(self.start_param, self.end_param) * t)

    def derivative_at(self, t: float) -> Point:
        sign = _walk(self.start_param, self.end_param)
        s = self.start_param + sign * t
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        c, h = math.cosh(s), math.sinh(s)
        return (sign * (h * mx + c * nx), sign * (h * my + c * ny))

    @property
    def equation(self) -> _Equation:
        """x'²/a² − y'²/b² = 1 nel riferimento del centro e dell'asse, espansa."""
        a = math.hypot(*self.major_axis)
        b = a * self.ratio
        ux, uy = self.major_axis[0] / a, self.major_axis[1] / a
        p = ux * ux / (a * a) - uy * uy / (b * b)
        q = 2 * ux * uy * (1 / (a * a) + 1 / (b * b))
        r = uy * uy / (a * a) - ux * ux / (b * b)
        cx, cy = self.center
        return (p, q, r, -2 * p * cx - q * cy, -q * cx - 2 * r * cy, p * cx * cx + q * cx * cy + r * cy * cy - 1)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """|P''(s)|² = a²·cosh²s + b²·sinh²s cresce con |s|: il passo da |s| si
        misura all'estremo più lontano del tratto, così ogni corda sta entro `tolerance`."""
        a = math.hypot(*self.major_axis)
        b = a * self.ratio

        def bend(s: float) -> float:
            return math.sqrt(a * a * math.cosh(s) ** 2 + b * b * math.sinh(s) ** 2)

        def step_at(s: float) -> float:
            first = math.sqrt(8 * tolerance / bend(s))
            return math.sqrt(8 * tolerance / bend(s + first))

        lo, hi = sorted((self.start_param, self.end_param))
        params = _grid(lo, hi, step_at)
        if self.start_param > self.end_param:
            params.reverse()
        return [self._point(s) for s in params]

    def to_bspline(self) -> BSplineSeg:
        """La stessa curva come spline razionale quadratica: il punto di mezzo è
        (cosh m·M + sinh m·N) / cosh d dal centro, peso cosh d (m il parametro
        di mezzo, d la metà dell'ampiezza). Esatta per ogni ampiezza."""
        a, b = self.start_param, self.end_param
        m, d = (a + b) / 2, abs(b - a) / 2
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        k = 1 / math.cosh(d)
        middle = (self.center[0] + k * (math.cosh(m) * mx + math.sinh(m) * nx),
                  self.center[1] + k * (math.cosh(m) * my + math.sinh(m) * ny))
        return BSplineSeg(degree=2, control_points=[self._point(a), middle, self._point(b)],
                          knots=[0, 0, 0, 1, 1, 1], weights=[1.0, math.cosh(d), 1.0])

    def reversed(self) -> "HyperbolaSeg":
        return HyperbolaSeg(self.center, self.major_axis, self.ratio, self.end_param, self.start_param)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "HyperbolaSeg":
        return HyperbolaSeg(_rotate_point(self.center, angle, origin), _rotate_point(self.major_axis, angle, (0.0, 0.0)),
                            self.ratio, self.start_param, self.end_param)

    def translated(self, dx: float, dy: float) -> "HyperbolaSeg":
        return HyperbolaSeg(_translate_point(self.center, dx, dy), self.major_axis, self.ratio,
                            self.start_param, self.end_param)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "HyperbolaSeg":
        """Come l'ellisse: uno specchio inverte il secondo asse, il punto a `s` va a `−s`."""
        return HyperbolaSeg(_mirror_point(self.center, origin, angle), _mirror_point(self.major_axis, (0.0, 0.0), angle),
                            self.ratio, -self.start_param, -self.end_param)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "HyperbolaSeg":
        factor = _check_factor(factor)
        return HyperbolaSeg(_scale_point(self.center, factor, origin),
                            (self.major_axis[0] * factor, self.major_axis[1] * factor),
                            self.ratio, self.start_param, self.end_param)
