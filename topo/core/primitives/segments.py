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

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# COSTANTI DI DISCRETIZZAZIONE — MODIFICARE QUI PER CAMBIARE COMPORTAMENTO
# ---------------------------------------------------------------------------

# Lati minimi della griglia di un cerchio; un arco ne prende la sua parte (D145)
MIN_SEGMENTS_CIRCLE = 64

# Un punto della griglia più vicino di così a un estremo dell'arco coincide
# con l'estremo e si salta: eviterebbe solo un tratto degenere
_GRID_SNAP = 1e-9

# Numero massimo di segmenti per tratto di spline (evita esplosione di punti)
MAX_SEGMENTS_SPLINE = 100

# Tolleranza predefinita se non specificata
DEFAULT_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# LineSeg
# ---------------------------------------------------------------------------

@dataclass
class LineSeg:
    start: Point
    end: Point

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Una linea è già esatta: restituisce solo i due endpoint.
        La tolleranza non serve ma la accettiamo per uniformità di interfaccia.
        """
        return [self.start, self.end]

    def reversed(self) -> "LineSeg":
        """Stessa linea, percorsa al contrario."""
        return LineSeg(start=self.end, end=self.start)

    def rotated(self, angle: float, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """Stessa linea, ruotata di `angle` radianti attorno a `origin`."""
        return LineSeg(
            start=_rotate_point(self.start, angle, origin),
            end=_rotate_point(self.end, angle, origin),
        )

    def translated(self, dx: float, dy: float) -> "LineSeg":
        """Stessa linea, spostata di (`dx`, `dy`)."""
        return LineSeg(start=_translate_point(self.start, dx, dy), end=_translate_point(self.end, dx, dy))

    def mirrored(self) -> "LineSeg":
        """Stessa linea, specchiata sull'asse x (y → −y)."""
        return LineSeg(start=_mirror_point(self.start), end=_mirror_point(self.end))


# ---------------------------------------------------------------------------
# Matematica di rotazione condivisa (ogni primitiva)
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


def _mirror_point(pt: Point) -> Point:
    """`pt` specchiato sull'asse x."""
    return (pt[0], -pt[1])


# ---------------------------------------------------------------------------
# Matematica angolare condivisa (ArcSeg / EllipseSeg)
# ---------------------------------------------------------------------------

def _angular_sweep(start: float, end: float, ccw: bool) -> float:
    """
    Angolo spazzato in radianti, sempre positivo, percorrendo da `start` a
    `end` nel verso indicato — stesso calcolo per un ArcSeg (`start_angle`/
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
# ArcSeg
# ---------------------------------------------------------------------------

@dataclass
class ArcSeg:
    center: Point
    radius: float
    start_angle: float  # radianti
    end_angle: float    # radianti
    ccw: bool = True

    def __post_init__(self):
        # raggio 0 è un punto, non una curva: come CircleSeg (D154)
        if not self.radius > 0:
            raise ValueError(f"Raggio deve essere positivo: {self.radius}")

    def _sweep(self) -> float:
        """Angolo spazzato in radianti, sempre positivo."""
        return _angular_sweep(self.start_angle, self.end_angle, self.ccw)

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza l'arco sulla griglia del suo cerchio (D145): gli estremi
        esatti più i vertici di `CircleSeg.discretize` che cadono fra loro, così
        l'arco si sovrappone al cerchio intero. Sagitta <= tolerance: nessun
        tratto supera il passo della griglia, i due di testa sono più corti.
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

    def reversed(self) -> "ArcSeg":
        """Stesso arco fisico, percorso al contrario: scambia gli angoli e nega ccw."""
        return ArcSeg(
            center=self.center,
            radius=self.radius,
            start_angle=self.end_angle,
            end_angle=self.start_angle,
            ccw=not self.ccw,
        )

    def rotated(self, angle: float, origin: Point = (0.0, 0.0)) -> "ArcSeg":
        """
        Stesso arco fisico, ruotato di `angle` radianti attorno a `origin`:
        il centro trasla con la rotazione, `start_angle`/`end_angle` si
        spostano dello stesso `angle` (il raggio e il verso non cambiano).
        """
        return ArcSeg(
            center=_rotate_point(self.center, angle, origin),
            radius=self.radius,
            start_angle=self.start_angle + angle,
            end_angle=self.end_angle + angle,
            ccw=self.ccw,
        )

    def translated(self, dx: float, dy: float) -> "ArcSeg":
        """Stesso arco, spostato di (`dx`, `dy`): si sposta solo il centro."""
        return ArcSeg(center=_translate_point(self.center, dx, dy), radius=self.radius,
                      start_angle=self.start_angle, end_angle=self.end_angle, ccw=self.ccw)

    def mirrored(self) -> "ArcSeg":
        """
        Stesso arco, specchiato sull'asse x: il punto all'angolo `a` va
        all'angolo `−a`, quindi gli angoli cambiano segno e il verso si
        inverte. La griglia del cerchio (D145, ancorata all'angolo 0) è
        simmetrica: l'arco specchiato ha i vertici specchiati.
        """
        return ArcSeg(center=_mirror_point(self.center), radius=self.radius,
                      start_angle=-self.start_angle, end_angle=-self.end_angle, ccw=not self.ccw)

    @classmethod
    def from_chord(cls, start: Point, end: Point, bulge: float) -> "ArcSeg":
        """
        Costruisce un ArcSeg da due punti e il parametro bulge DXF.

        bulge = tan(Δθ / 4), positivo = CCW, negativo = CW.
        Questa è l'unica sede della conversione — parser DXF e altri
        adapter passano qui senza conoscere la geometria interna.
        """
        if abs(bulge) < 1e-9:
            raise ValueError("bulge nullo: usa LineSeg, non ArcSeg")

        ccw = bulge > 0
        half_chord = math.hypot(end[0] - start[0], end[1] - start[1]) / 2.0
        if not half_chord > 0:
            # corda nulla: raggio 0, con numpy un arco NaN invece di un errore (D154)
            raise ValueError("corda nulla: un punto, non un arco")
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
class BSplineSeg:
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

    def rotated(self, angle: float, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
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

    def mirrored(self) -> "BSplineSeg":
        """Stessa spline, specchiata sull'asse x: una mappa lineare porta la
        curva nella curva dei punti di controllo specchiati."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_mirror_point(p) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

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

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
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

    if isinstance(segment, ArcSeg):
        return segment._point_at(segment.start_angle), segment._point_at(segment.end_angle)

    if isinstance(segment, BSplineSeg):
        return segment.endpoints()

    if isinstance(segment, CircleSeg):
        pt = (segment.center[0] + segment.radius, segment.center[1])
        return pt, pt

    if isinstance(segment, EllipseSeg):
        return segment._point_at(segment.start_param), segment._point_at(segment.end_param)

    return (0.0, 0.0), (0.0, 0.0)


def segment_is_closed(segment, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """
    True se gli endpoint del segmento coincidono entro ``tolerance``.

    Unica sede del test di chiusura di un segmento primitivo — usata
    dall'adapter per riconoscere le spline chiuse (loop degenere).
    """
    start, end = segment_endpoints(segment)
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance


@dataclass
class CircleSeg:
    """Cerchio geometrico puro."""
    center: Point
    radius: float
    
    def __post_init__(self):
        if not self.radius > 0:
            raise ValueError(f"Raggio deve essere positivo: {self.radius}")

    def reversed(self) -> "CircleSeg":
        """Un cerchio è simmetrico: invertirlo lo lascia identico."""
        return CircleSeg(center=self.center, radius=self.radius)

    def rotated(self, angle: float, origin: Point = (0.0, 0.0)) -> "CircleSeg":
        """Stesso cerchio, ruotato di `angle` radianti attorno a `origin` (solo il centro si sposta)."""
        return CircleSeg(center=_rotate_point(self.center, angle, origin), radius=self.radius)

    def translated(self, dx: float, dy: float) -> "CircleSeg":
        """Stesso cerchio, spostato di (`dx`, `dy`)."""
        return CircleSeg(center=_translate_point(self.center, dx, dy), radius=self.radius)

    def mirrored(self) -> "CircleSeg":
        """Stesso cerchio, specchiato sull'asse x (la griglia, ancorata
        all'angolo 0, è simmetrica)."""
        return CircleSeg(center=_mirror_point(self.center), radius=self.radius)

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza il cerchio in polilinea chiusa sulla sua griglia
        (`_circle_sides`, ancorata all'angolo 0): sagitta <= tolerance, lati
        che crescono con il raggio (~π·√(r/2·tol)). Ogni `ArcSeg` dello stesso
        cerchio usa gli stessi vertici (D145).
        """
        n_segments = _circle_sides(self.radius, tolerance)

        # Genera i punti (chiuso)
        pts = []
        for i in range(n_segments + 1):
            pts.append(point_on_circle(self.center, self.radius, 2 * math.pi * i / n_segments))

        return pts


# ---------------------------------------------------------------------------
# EllipseSeg
# ---------------------------------------------------------------------------

@dataclass
class EllipseSeg:
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
    Stesso trattamento di ArcSeg: un'unica classe copre sia il caso chiuso sia
    quello aperto, perché è così che l'entità DXF stessa li tratta — non
    serve una "EllipseSeg chiusa" separata come invece serve per CIRCLE (che
    in DXF è sempre e solo chiuso).

    `ccw` esiste per lo stesso motivo di `ArcSeg.ccw`: un'ELLIPSE DXF reale è
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
        # asse nullo o ratio 0 è un punto o un segmento, non un'ellisse (D154)
        if not (math.hypot(*self.major_axis) > 0 and self.ratio > 0):
            raise ValueError(f"Ellisse degenere: asse {self.major_axis}, ratio {self.ratio}")

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

    def discretize(self, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza sulla griglia del parametro (D153): l'ellisse è il cerchio
        del semiasse maggiore `a` visto attraverso una mappa lineare che non
        allunga nessun vettore (fattori 1 e ratio), quindi i vertici k·2π/N di
        `_circle_sides(a, tolerance)` portati sull'ellisse restano entro
        `tolerance` come sul cerchio. Gli estremi esatti più i punti di griglia
        fra loro, come `ArcSeg`: un'ellisse tagliata in pezzi dà il poligono
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

    def rotated(self, angle: float, origin: Point = (0.0, 0.0)) -> "EllipseSeg":
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

    def mirrored(self) -> "EllipseSeg":
        """
        Stessa ellisse, specchiata sull'asse x. Il semiasse minore è
        `ratio`·(asse maggiore ruotato di +90°): specchiando l'asse maggiore
        quello ricavato punta dalla parte opposta all'immagine del minore,
        quindi il punto al parametro `t` va al parametro `−t` — parametri
        col segno cambiato e verso invertito, come `ArcSeg.mirrored`.
        """
        return EllipseSeg(center=_mirror_point(self.center), major_axis=_mirror_point(self.major_axis),
                          ratio=self.ratio, start_param=-self.start_param, end_param=-self.end_param,
                          ccw=not self.ccw)
