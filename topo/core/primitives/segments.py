"""
topo/core/primitives/segments.py
----------------------------------
Primitive geometriche pure con discretizzazione centralizzata.

Questa è l'UNICA sede della discretizzazione.
Ogni adapter (DXF, PDF, SVG, ...) deve convertire le sue entità in queste
primitive e poi usare SOLO i metodi qui definiti.

La tolleranza è SEMPRE passata come parametro, mai hardcoded.
"""

from __future__ import annotations

from ...precision import FLOAT_NOISE, SAME_POINT
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

Point = Tuple[float, float]


def _real(x) -> float:
    """Un numero come float Python finito: una coordinata NaN o infinita non ha
    posizione, la primitiva la rifiuta come una curva di misura nulla (D154, D190)."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"not a finite number: {x}")
    return x


def _plain(p) -> Point:
    """Un punto come tupla di float Python finiti: chi passa numpy o ezdxf non
    lo ritrova nei campi pubblici (D169)."""
    return tuple(_real(c) for c in p)


# ---------------------------------------------------------------------------
# COSTANTI DI DISCRETIZZAZIONE — MODIFICARE QUI PER CAMBIARE COMPORTAMENTO
# ---------------------------------------------------------------------------

# Lati minimi della griglia di un cerchio; un arco ne prende la sua parte (D145)
MIN_SEGMENTS_CIRCLE = 64

# Un punto della griglia più vicino di così a un estremo dell'arco coincide
# con l'estremo e si salta: eviterebbe solo un tratto degenere
_GRID_SNAP = FLOAT_NOISE

# Numero massimo di segmenti per tratto di spline (evita esplosione di punti)
MAX_SEGMENTS_SPLINE = 100

# Tolleranza predefinita se non specificata
DEFAULT_TOLERANCE = SAME_POINT  # sagitta dei poligoni, D275


# ---------------------------------------------------------------------------
# Le madri: ogni primitiva è una curva matematica (D285)
# ---------------------------------------------------------------------------

class MathSeg(ABC):
    """
    A curve given by its mathematics: one point for every parameter `t` in
    `t_range`, walked from `t_range[0]` (the start) to `t_range[1]` (the
    end). Every topo primitive is one; what a file format called it is not
    part of it.
    """

    @property
    @abstractmethod
    def t_range(self) -> Tuple[float, float]:
        """(t0, t1): the parameter at the start and at the end, t0 < t1."""

    @abstractmethod
    def point_at(self, t: float) -> Point:
        """The point of the curve at parameter `t`."""

    @abstractmethod
    def derivative_at(self, t: float) -> Point:
        """dP/dt at parameter `t`: the direction of travel, exact."""

    @abstractmethod
    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """A polyline from start to end, every point of the curve within `tolerance` of it."""

    @abstractmethod
    def reversed(self) -> "MathSeg":
        """The same curve walked the other way."""

    @abstractmethod
    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "MathSeg":
        """The curve rotated by `angle` radians about `origin`."""

    @abstractmethod
    def translated(self, dx: float, dy: float) -> "MathSeg":
        """The curve moved by (`dx`, `dy`)."""

    @abstractmethod
    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "MathSeg":
        """The curve mirrored on the line through `origin` at `angle` radians."""

    @abstractmethod
    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "MathSeg":
        """The curve scaled by `factor` (> 0) about `origin`."""


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
# LineSeg
# ---------------------------------------------------------------------------

@dataclass
class LineSeg(MathSeg):
    """The straight piece from `start` to `end`: P(t) = start + t·(end − start), t in [0, 1]."""
    start: Point
    end: Point

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, 1.0)

    def point_at(self, t: float) -> Point:
        return (self.start[0] + t * (self.end[0] - self.start[0]), self.start[1] + t * (self.end[1] - self.start[1]))

    def derivative_at(self, t: float) -> Point:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

    def __post_init__(self):
        self.start, self.end = _plain(self.start), _plain(self.end)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Una linea è già esatta: restituisce solo i due endpoint.
        La tolleranza non serve ma la accettiamo per uniformità di interfaccia.
        """
        return [self.start, self.end]

    def reversed(self) -> "LineSeg":
        """Stessa linea, percorsa al contrario."""
        return LineSeg(start=self.end, end=self.start)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """Stessa linea, ruotata di `angle` radianti attorno a `origin`."""
        return LineSeg(
            start=_rotate_point(self.start, angle, origin),
            end=_rotate_point(self.end, angle, origin),
        )

    def translated(self, dx: float, dy: float) -> "LineSeg":
        """Stessa linea, spostata di (`dx`, `dy`)."""
        return LineSeg(start=_translate_point(self.start, dx, dy), end=_translate_point(self.end, dx, dy))

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "LineSeg":
        """Stessa linea, specchiata sulla retta per `origin` a `angle` radianti
        (default: l'asse x, y → −y)."""
        return LineSeg(start=_mirror_point(self.start, origin, angle),
                       end=_mirror_point(self.end, origin, angle))

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """Stessa linea, scalata di `factor` (> 0) attorno a `origin`."""
        factor = _check_factor(factor)
        return LineSeg(start=_scale_point(self.start, factor, origin),
                       end=_scale_point(self.end, factor, origin))


# ---------------------------------------------------------------------------
# Trasformazioni del piano condivise (ogni primitiva): rotazione, traslazione, specchio, scala
# ---------------------------------------------------------------------------

def _rotate_point(pt: Point, angle: float, origin: Point) -> Point:
    """Ruota `pt` di `angle` radianti (CCW) attorno a `origin`."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return (ox + x * cos_a - y * sin_a, oy + x * sin_a + y * cos_a)


def _translate_point(pt: Point, dx: float, dy: float) -> Point:
    """`pt` spostato di (`dx`, `dy`)."""
    return (pt[0] + dx, pt[1] + dy)


def _mirror_point(pt: Point, origin: Point = (0.0, 0.0), angle: float = 0.0) -> Point:
    """`pt` specchiato sulla retta per `origin` inclinata di `angle` radianti
    sull'asse x (default: l'asse x, y → −y)."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_2a, sin_2a = math.cos(2 * angle), math.sin(2 * angle)
    return (ox + x * cos_2a + y * sin_2a, oy + x * sin_2a - y * cos_2a)


def _scale_point(pt: Point, factor: float, origin: Point) -> Point:
    """`pt` scalato di `factor` attorno a `origin`."""
    ox, oy = origin
    return (ox + (pt[0] - ox) * factor, oy + (pt[1] - oy) * factor)


def _check_factor(factor: float) -> float:
    """Il fattore di una scala: positivo e finito. Uno negativo è una
    rotazione di π più una scala, e va chiesto così."""
    factor = float(factor)
    if not (factor > 0 and math.isfinite(factor)):
        raise ValueError(f"the scale factor must be positive and finite, got {factor}")
    return factor


# ---------------------------------------------------------------------------
# Matematica angolare condivisa (CircleSeg / EllipseSeg)
# ---------------------------------------------------------------------------

def _angular_sweep(start: float, end: float, ccw: bool) -> float:
    """
    Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a
    `end` nel verso indicato — stesso calcolo per un CircleSeg (`start_angle`/
    `end_angle`) e un EllipseSeg (`start_param`/`end_param`): entrambi sono
    "percorri da un angolo/parametro a un altro, in un verso".
    """
    raw = (end - start) if ccw else (start - end)
    sweep = raw % (2 * math.pi)
    if sweep < 1e-12 and abs(raw) > 1e-12:
        sweep = 2 * math.pi
    return sweep


def point_on_circle(center: Point, radius: float, angle: float) -> Point:
    """Punto della circonferenza (`center`, `radius`) all'angolo dato (radianti)."""
    return (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))


def angle_from_start(center: Point, start_angle: float, ccw: bool, pt: Point) -> float:
    """
    Angolo, in [0, 2π), da percorrere partendo da `start_angle` nel verso
    `ccw` per arrivare alla direzione di `pt` vista da `center`.
    """
    phi = math.atan2(pt[1] - center[1], pt[0] - center[0])
    delta = (phi - start_angle) if ccw else (start_angle - phi)
    return delta % (2 * math.pi)


def _sagitta_step(radius: float, tolerance: float) -> Optional[float]:
    """
    Angolo massimo di una corda che dista al più `tolerance` dall'arco di
    raggio `radius`. None se il raggio non supera la tolleranza: lì la formula
    non ha senso e il chiamante sceglie il suo ripiego.
    """
    if radius <= tolerance:
        return None
    ratio = max(-1.0, min(1.0, 1.0 - tolerance / radius))
    return 2.0 * math.acos(ratio)


def _circle_sides(radius: float, tolerance: float) -> int:
    """
    Lati della griglia del cerchio di raggio `radius`: sagitta <= tolerance,
    almeno MIN_SEGMENTS_CIRCLE, nessun tetto (la freccia è assoluta, i lati
    crescono con il raggio). Multiplo di 4: la griglia è simmetrica rispetto
    ai due assi, quindi i quarti cadono sui vertici e un pezzo specchiato dà
    il poligono specchiato.
    """
    step = _sagitta_step(radius, tolerance)
    if step is None:
        return MIN_SEGMENTS_CIRCLE
    sides = max(MIN_SEGMENTS_CIRCLE, int(math.ceil(2 * math.pi / step)))
    return -(-sides // 4) * 4


def _grid_angles(lo: float, hi: float, radius: float, sides: int) -> List[float]:
    """
    Angoli da `lo` a `hi` (lo < hi): i due estremi esatti e, fra loro, i punti
    della griglia k·2π/sides ancorata all'angolo 0 (D145). Così ogni arco di un
    cerchio è un pezzo del poligono del cerchio intero, comunque sia tagliato.
    """
    step = 2 * math.pi / sides
    snap = _GRID_SNAP / radius
    angles = [lo]
    for k in range(math.floor(lo / step) + 1, math.ceil(hi / step)):
        a = k * step
        if a - lo > snap and hi - a > snap:
            angles.append(a)
    angles.append(hi)
    return angles


# ---------------------------------------------------------------------------
# CircleSeg: arco o cerchio intero
# ---------------------------------------------------------------------------

@dataclass
class CircleSeg(ConicSeg):
    """A piece of the circle (`center`, `radius`) from `start_angle` to
    `end_angle`, counter-clockwise when `ccw`; with no angles the whole
    circle from angle 0. A circle is an arc that goes all the way round
    (`full`): one class, not two (D286). `t` is the angle walked from the
    start: t in [0, sweep]."""
    center: Point
    radius: float
    start_angle: float = 0.0          # radianti
    end_angle: float = 2 * math.pi    # radianti
    ccw: bool = True

    def __post_init__(self):
        self.center, self.radius = _plain(self.center), _real(self.radius)
        self.start_angle, self.end_angle = _real(self.start_angle), _real(self.end_angle)
        # raggio 0 è un punto, non una curva (D154)
        if not self.radius > 0:
            raise ValueError(f"the radius must be positive, got {self.radius}")

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
    def from_chord(cls, start: Point, end: Point, bulge: float) -> "CircleSeg":
        """
        Costruisce un arco da due punti e il parametro bulge DXF.

        bulge = tan(Δθ / 4), positivo = CCW, negativo = CW.
        Questa è l'unica sede della conversione — parser DXF e altri
        adapter passano qui senza conoscere la geometria interna.
        """
        if abs(bulge) < 1e-9:
            raise ValueError("zero bulge: use LineSeg, not CircleSeg")

        ccw = bulge > 0
        half_chord = math.hypot(end[0] - start[0], end[1] - start[1]) / 2.0
        if not half_chord > 0:
            # corda nulla: raggio 0, con numpy un arco NaN invece di un errore (D154)
            raise ValueError("zero chord: a point, not an arc")
        sweep = 4.0 * math.atan(abs(bulge))          # angolo spazzato totale
        radius = half_chord / math.sin(sweep / 2.0)

        # Punto medio della corda
        mx = (start[0] + end[0]) / 2.0
        my = (start[1] + end[1]) / 2.0

        # Versore perpendicolare alla corda (verso il centro)
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        chord_len = 2.0 * half_chord
        nx = -dy / chord_len
        ny =  dx / chord_len

        # Distanza (con segno) dal midpoint al centro lungo la perpendicolare.
        # `radius * cos(sweep/2)` è negativo per sweep > π (arco maggiore,
        # |bulge| > 1): il centro sta dalla parte opposta della corda rispetto
        # all'arco minore. `sqrt(r² - half_chord²)` sarebbe sempre positivo e
        # sceglierebbe l'arco minore anche quando il bulge chiede il maggiore.
        d = radius * math.cos(sweep / 2.0)

        # CCW → centro a sinistra della corda (nx, ny positivo)
        # CW  → centro a destra (nx, ny negativo)
        sign = 1.0 if ccw else -1.0
        cx = mx + sign * d * nx
        cy = my + sign * d * ny

        start_angle = math.atan2(start[1] - cy, start[0] - cx)
        end_angle   = math.atan2(end[1]   - cy, end[0]   - cx)

        return cls(
            center=(cx, cy),
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
            ccw=ccw,
        )

# ---------------------------------------------------------------------------
# BSplineSeg
# ---------------------------------------------------------------------------

def _bspline_find_span(t: float, degree: int, knots: List[float], n: int) -> int:
    """
    Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The
    NURBS Book" Algoritmo A2.1) — `n` è l'indice dell'ultimo control point.
    """
    if t >= knots[n + 1]:
        return n
    lo, hi = degree, n + 1
    mid = (lo + hi) // 2
    while t < knots[mid] or t >= knots[mid + 1]:
        if t < knots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


def _derivative_points(points: List[tuple], knots: List[float], p: int) -> List[tuple]:
    """Punti di controllo della derivata (grado p − 1, nodi senza il primo e l'ultimo)."""
    out = []
    for i in range(len(points) - 1):
        span = knots[i + p + 1] - knots[i + 1]
        scale = p / span if span > 0 else 0.0
        out.append(tuple(scale * (b - a) for a, b in zip(points[i], points[i + 1])))
    return out


def _deboor(t: float, p: int, knots: List[float], points: List[tuple]) -> tuple:
    """Punto al parametro `t` di una B-spline di vettori (de Boor, A5.1)."""
    k = _bspline_find_span(t, p, knots, len(points) - 1)
    d = [list(points[k - p + j]) for j in range(p + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = k - p + j
            denom = knots[i + p - r + 1] - knots[i]
            alpha = 0.0 if denom == 0 else (t - knots[i]) / denom
            d[j] = [(1 - alpha) * u + alpha * v for u, v in zip(d[j - 1], d[j])]
    return tuple(d[p])


def _point_to_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy)


def _refine_segment(
    evaluate, t0: float, t1: float, p0: Point, p1: Point,
    tolerance: float, out: List[Point], depth: int,
    max_depth: int = 8,
) -> None:
    """
    Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`)
    resta entro `tolerance` dalla corda. `max_depth` limita i punti su un
    tratto rumoroso che non converge mai; nessun tetto sul totale, che
    lascerebbe il resto della curva a corde grosse fuori tolleranza.

    `evaluate` è un callable `t -> Point` (De Boor per `BSplineSeg`).
    """
    tm = (t0 + t1) / 2
    pm = evaluate(tm)
    if (
        depth >= max_depth
        or _point_to_segment_distance(pm, p0, p1) <= tolerance
    ):
        out.append(p1)
        return
    _refine_segment(evaluate, t0, tm, p0, pm, tolerance, out, depth + 1, max_depth)
    _refine_segment(evaluate, tm, t1, pm, p1, tolerance, out, depth + 1, max_depth)


def _adaptive_polyline(
    evaluate, t_min: float, t_max: float, n_initial: int, tolerance: float,
) -> List[Point]:
    """
    Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra
    `t_min` e `t_max`: campionamento iniziale uniforme in `n_initial` passi
    (scelto dal chiamante in base alla propria stima di curvatura/lunghezza),
    poi suddivisione adattiva (`_refine_segment`) finché ogni tratto resta
    entro `tolerance` dalla corda.
    """
    n_initial = max(1, n_initial)
    ts = [t_min + (t_max - t_min) * i / n_initial for i in range(n_initial + 1)]
    points = [evaluate(t) for t in ts]

    result: List[Point] = [points[0]]
    for i in range(n_initial):
        _refine_segment(evaluate, ts[i], ts[i + 1], points[i], points[i + 1], tolerance, result, depth=0)
    return result


@dataclass
class BSplineSeg(MathSeg):
    """
    B-spline (NURBS se `weights` è impostato): grado, punti di controllo,
    nodi, pesi — solo la geometria (MAP.md D135). Quello che un formato
    sorgente tiene in più (flag, tolleranze, fit points, tangenti) resta
    nell'adapter; `closed` e `periodic` si ricavano dai campi.
    """
    degree: int
    control_points: List[Point]
    knots: List[float]
    weights: Optional[List[float]] = None

    def __post_init__(self):
        self.degree = int(self.degree)
        self.control_points = [_plain(p) for p in self.control_points]
        self.knots = [_real(k) for k in self.knots]
        if self.weights is not None:
            self.weights = [_real(w) for w in self.weights]
        # punti di discretize() per tolleranza: heal() chiede la stessa spline
        # più volte. Non è un campo (fuori da eq/repr/fields); vale perché una
        # spline non si modifica sul posto — reversed/rotated ne fanno una nuova.
        self._points: dict = {}

    @property
    def clamped(self) -> bool:
        """True se i primi e gli ultimi `degree + 1` nodi coincidono: la curva
        parte dal primo punto di controllo e finisce sull'ultimo."""
        p, k = self.degree, self.knots
        if len(k) < 2 * (p + 1):
            return True
        return k[0] == k[p] and k[-1] == k[-(p + 1)]

    @property
    def closed(self) -> bool:
        """True se la curva torna al punto di partenza (entro DEFAULT_TOLERANCE)."""
        if len(self.control_points) < 2:
            return False
        start, end = self.endpoints()
        return math.hypot(start[0] - end[0], start[1] - end[1]) < DEFAULT_TOLERANCE

    @property
    def periodic(self) -> bool:
        """True se la curva è chiusa e non clamped: si richiude senza un punto
        di controllo sul giunto."""
        return self.closed and not self.clamped

    def endpoints(self) -> Tuple[Point, Point]:
        """(inizio, fine) sulla curva vera — per una spline non clamped non
        sono il primo e l'ultimo punto di controllo."""
        if not self.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        p = self.degree
        if len(self.knots) != len(self.control_points) + p + 1:
            return self.control_points[0], self.control_points[-1]
        return self._evaluate(self.knots[p]), self._evaluate(self.knots[-(p + 1)])

    def reversed(self) -> "BSplineSeg":
        """
        Spline con la parametrizzazione invertita — stesso luogo geometrico
        percorso al contrario.

        Invertire una B-spline NON è solo invertire i punti di controllo:
        va invertito anche il vettore dei nodi e rimappato sul dominio
        originale ``U'[i] = a + b - U[m-i]`` (con ``a = U[0]``, ``b = U[-1]``),
        e vanno invertiti i pesi. Invertire i soli control point lascia la
        curva accoppiata a un vettore nodi sbagliato: la curva emessa in DXF
        risulta deformata all'interno (gli endpoint combaciano lo stesso
        perché una spline clamped interpola il primo e l'ultimo CP).
        """
        if self.knots:
            a, b = self.knots[0], self.knots[-1]
            new_knots = [a + b - k for k in reversed(self.knots)]
        else:
            new_knots = []
        return BSplineSeg(
            degree=self.degree,
            control_points=list(reversed(self.control_points)),
            knots=new_knots,
            weights=list(reversed(self.weights)) if self.weights else None,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """Stessa spline, ruotata di `angle` radianti attorno a `origin`: si
        ruotano i punti di controllo, nodi e pesi non cambiano."""
        return BSplineSeg(
            degree=self.degree,
            control_points=[_rotate_point(p, angle, origin) for p in self.control_points],
            knots=list(self.knots),
            weights=list(self.weights) if self.weights else None,
        )

    def translated(self, dx: float, dy: float) -> "BSplineSeg":
        """Stessa spline, spostata di (`dx`, `dy`): si spostano i punti di controllo."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_translate_point(p, dx, dy) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "BSplineSeg":
        """Stessa spline, specchiata sulla retta per `origin` a `angle` radianti
        (default: l'asse x): una mappa affine porta la curva nella curva dei
        punti di controllo specchiati."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_mirror_point(p, origin, angle) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """Stessa spline, scalata di `factor` (> 0) attorno a `origin`: si
        scalano i punti di controllo, nodi e pesi non cambiano."""
        factor = _check_factor(factor)
        return BSplineSeg(degree=self.degree,
                          control_points=[_scale_point(p, factor, origin) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    @property
    def t_range(self) -> Tuple[float, float]:
        """Il dominio dei nodi: da `knots[degree]` a `knots[-(degree + 1)]`."""
        return (self.knots[self.degree], self.knots[-(self.degree + 1)])

    def point_at(self, t: float) -> Point:
        return self._evaluate(t)

    def derivative_at(self, t: float) -> Point:
        """In coordinate omogenee, anche razionale: C' = (A' − w'·C) / w."""
        p, knots, ctrl = self.degree, self.knots, self.control_points
        if p < 1:
            return (0.0, 0.0)
        t0, t1 = self.t_range
        t = min(max(t, t0), t1)
        weights = self.weights or [1.0] * len(ctrl)
        h = [(c[0] * w, c[1] * w, w) for c, w in zip(ctrl, weights)]
        a = _deboor(t, p, knots, h)
        d = _derivative_points(h, knots, p)
        da = _deboor(t, p - 1, knots[1:-1], d) if p > 1 else d[_bspline_find_span(t, 1, knots, len(ctrl) - 1) - 1]
        x, y = a[0] / a[2], a[1] / a[2]
        return ((da[0] - da[2] * x) / a[2], (da[1] - da[2] * y) / a[2])

    def _evaluate(self, t: float) -> Point:
        """
        Punto della curva vera al parametro `t` (algoritmo di de Boor, "The
        NURBS Book" Algoritmo A5.1 — razionale se `weights` è impostato).
        Sola matematica: nessuna libreria di formato coinvolta.
        """
        degree = self.degree
        knots = self.knots
        ctrl = self.control_points
        n = len(ctrl) - 1

        # Fuori dominio si valuta sul bordo: per una spline clamped è il
        # primo/ultimo punto di controllo (esatto), per una non clamped no.
        t_min, t_max = knots[degree], knots[-(degree + 1)]
        t = min(max(t, t_min), t_max)

        k = _bspline_find_span(t, degree, knots, n)
        first = k - degree
        weights = self.weights
        # coordinate omogenee (x·w, y·w, w); w = 1 se la spline non è razionale
        if weights:
            ws = weights[first:k + 1]
            xs = [ctrl[first + j][0] * ws[j] for j in range(degree + 1)]
            ys = [ctrl[first + j][1] * ws[j] for j in range(degree + 1)]
        else:
            ws = None
            xs = [ctrl[first + j][0] for j in range(degree + 1)]
            ys = [ctrl[first + j][1] for j in range(degree + 1)]

        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = first + j
                denom = knots[i + degree - r + 1] - knots[i]
                alpha = 0.0 if denom == 0 else (t - knots[i]) / denom
                beta = 1 - alpha
                xs[j] = beta * xs[j - 1] + alpha * xs[j]
                ys[j] = beta * ys[j - 1] + alpha * ys[j]
                if ws is not None:
                    ws[j] = beta * ws[j - 1] + alpha * ws[j]

        if ws is None:
            return (xs[degree], ys[degree])
        w = ws[degree]
        return (xs[degree], ys[degree]) if w == 0 else (xs[degree] / w, ys[degree] / w)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza la spline in polilinea valutando la curva vera (non il
        poligono di controllo) via `_evaluate()`, con suddivisione adattiva
        finché la deviazione dalla corda resta entro `tolerance`.
        """
        cached = self._points.get(tolerance)
        if cached is None:
            cached = self._points[tolerance] = self._discretize(tolerance)
        return list(cached)

    def _discretize(self, tolerance: float) -> List[Point]:
        if not self.control_points:
            return []

        if len(self.control_points) == 1:
            return [self.control_points[0]]

        if not self.knots:
            return list(self.control_points)

        t_min, t_max = self.knots[self.degree], self.knots[-(self.degree + 1)]
        if t_max <= t_min:
            return list(self.control_points)

        approx_length = sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.control_points, self.control_points[1:])
        )
        n_initial = max(1, int(math.ceil(approx_length / tolerance))) if tolerance > 0 else MAX_SEGMENTS_SPLINE
        n_initial = min(n_initial, MAX_SEGMENTS_SPLINE)

        return _adaptive_polyline(self._evaluate, t_min, t_max, n_initial, tolerance)


def segment_endpoints(segment) -> Tuple[Point, Point]:
    """
    (start, end) di un segmento primitivo, in coordinate XY non arrotondate.

    Unica sede di questo calcolo — usata dall'adapter per costruire gli Edge e
    dal gap solver per lavorare su geometria pura.
    """
    if isinstance(segment, LineSeg):
        return segment.start, segment.end

    if isinstance(segment, CircleSeg):
        return segment._point_at(segment.start_angle), segment._point_at(segment.end_angle)

    if isinstance(segment, BSplineSeg):
        return segment.endpoints()

    if isinstance(segment, EllipseSeg):
        return segment._point_at(segment.start_param), segment._point_at(segment.end_param)

    return (0.0, 0.0), (0.0, 0.0)


def is_full_circle(segment) -> bool:
    """Un `CircleSeg` che fa tutto il giro."""
    return isinstance(segment, CircleSeg) and segment.full


def is_arc(segment) -> bool:
    """Un `CircleSeg` che non fa tutto il giro: un arco."""
    return isinstance(segment, CircleSeg) and not segment.full


def segment_is_closed(segment, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """
    True se gli endpoint del segmento coincidono entro ``tolerance``.

    Unica sede del test di chiusura di un segmento primitivo — usata
    dall'adapter per riconoscere le spline chiuse (loop degenere).
    """
    start, end = segment_endpoints(segment)
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance


# ---------------------------------------------------------------------------
# EllipseSeg
# ---------------------------------------------------------------------------

@dataclass
class EllipseSeg(ConicSeg):
    """
    Ellisse (o arco ellittico) geometrico puro — stessa parametrizzazione del
    gruppo DXF ELLIPSE (ripresa 1:1, non un'invenzione di topo: è così che
    STEP/IGES/ogni kernel CAD reale modella una conica, non una particolarità
    del formato DXF — vedi MAP.md, la voce sull'ellisse).

    `major_axis` è il VETTORE dal centro all'estremo dell'asse maggiore (non
    un punto): la sua lunghezza è il semiasse maggiore, la sua direzione
    l'orientamento dell'ellisse. `ratio` è semiasse minore / semiasse
    maggiore (0 < ratio <= 1). Un'ellisse piena ha `start_param=0`,
    `end_param=2π` (i default DXF); un arco ellittico usa un sotto-intervallo.
    Come `CircleSeg`: un'unica classe copre il giro intero e il pezzo, perché
    matematicamente sono la stessa curva su un intervallo diverso (D286).

    `ccw` esiste per lo stesso motivo di `CircleSeg.ccw`: un'ELLIPSE DXF reale è
    sempre percorsa CCW da `start_param` a `end_param` (nessun flag di verso
    nel formato) — `ccw=False` è uno stato solo interno a topo, usato per
    percorrere il segmento al contrario quando un loop viene orientato
    (`.reversed()`), mai qualcosa che il parser produce da un file.
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
        """
        Punto sull'ellisse al parametro `t` (radianti): stessa formula di
        `ezdxf.math.ellipse.vertex` — `center + cos(t)*major_axis +
        sin(t)*ratio*rotate90(major_axis)` — verificata contro la sorgente di
        ezdxf invece che assunta, per non ricalcare a caso il formato.
        """
        mx, my = self.major_axis
        nx, ny = -my * self.ratio, mx * self.ratio
        return (
            self.center[0] + math.cos(t) * mx + math.sin(t) * nx,
            self.center[1] + math.cos(t) * my + math.sin(t) * ny,
        )

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

        # ratio > 1 (fuori dal formato, ma possibile): il fattore più grande è ratio
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
