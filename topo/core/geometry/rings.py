"""
topo/core/geometry/rings.py
---------------------------
Fatti di un giro chiuso di primitive, calcolati sulle primitive (MAP.md D166,
D167): bbox, perimetro, punti discretizzati, "il punto sta dentro?". Il giro
è quello di `ring_moments`: un salto fra la fine di un segmento e l'inizio del
successivo (gap chiuso entro la tolleranza, D143) conta come la sua corda.
Funzioni pure su primitive, un ramo per tipo.
"""

import math
from typing import Iterator, List, Sequence, Tuple

from ..primitives.segments import (
    ArcSeg, BSplineSeg, CircleSeg, DEFAULT_TOLERANCE, EllipseSeg, LineSeg, segment_endpoints,
)
from .measure import Reach, segment_length

Point = Tuple[float, float]
Bounds = Tuple[float, float, float, float]

ON_BOUNDARY = 1e-6   # mm: un punto più vicino di così al bordo ci sta sopra (griglia dei nodi, D113)


def ring_jumps(segments: Sequence) -> Iterator[Tuple[Point, Point]]:
    """
    (fine, inizio) di ogni salto fra un segmento e il successivo, nell'ordine
    del giro. Un `CircleSeg` è un giro da sé: nessun salto da o verso lui.
    """
    segments = list(segments)
    for segment, following in zip(segments, segments[1:] + segments[:1]):
        if isinstance(segment, CircleSeg) or isinstance(following, CircleSeg):
            continue
        end, start = segment_endpoints(segment)[1], segment_endpoints(following)[0]
        if end != start:
            yield end, start


def ring_closes(segments: Sequence, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """I segmenti chiudono un giro testa-coda: ognuno parte entro `tolerance`
    da dove finisce il precedente, l'ultimo torna al primo."""
    segments = list(segments)
    if not segments:
        return False
    ends = [segment_endpoints(s) for s in segments]
    return all(math.dist(ends[k][1], ends[(k + 1) % len(ends)][0]) <= tolerance
               for k in range(len(ends)))


def ring_bbox(segments: Sequence) -> Bounds:
    """(xmin, ymin, xmax, ymax) esatto delle primitive: gli estremi di archi
    ed ellissi dove la curva li tocca, non sulle corde. I salti stanno fra
    estremi di segmenti, già dentro."""
    if not segments:
        raise ValueError("ring_bbox(): giro vuoto")
    xs, ys = [], []
    for segment in segments:
        reach = Reach(segment)
        xs.extend(reach((1.0, 0.0)))
        ys.extend(reach((0.0, 1.0)))
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


def ring_perimeter(segments: Sequence) -> float:
    """Lunghezza del giro: le primitive più le corde dei salti."""
    return (sum(segment_length(s) for s in segments)
            + sum(math.dist(a, b) for a, b in ring_jumps(segments)))


def ring_points(segments: Sequence, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
    """
    I vertici del giro discretizzato entro `tolerance` (la griglia di ogni
    primitiva, D145), in ordine, senza ripetere il primo in fondo: l'ultimo
    lato torna al primo punto. Un salto resta, come lato fra i due capi.
    """
    pts: List[Point] = []
    for segment in segments:
        seg_pts = [tuple(p) for p in segment.discretize(tolerance)]
        if pts and seg_pts and pts[-1] == seg_pts[0]:
            seg_pts = seg_pts[1:]
        pts.extend(seg_pts)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def ring_contains(segments: Sequence, point: Point, tolerance: float = ON_BOUNDARY) -> bool:
    """
    `point` sta nella regione chiusa del giro: dentro, o sul bordo entro
    `tolerance`. Numero di avvolgimento sulle primitive: retta, arco, cerchio
    ed ellisse in forma chiusa; la spline sulla sua polilinea entro
    `tolerance` / 2, che lontano dal bordo dà lo stesso numero.
    """
    if not segments:
        raise ValueError("ring_contains(): giro vuoto")
    turn = 0.0
    for segment in segments:
        swept = _swept(segment, point, tolerance)
        if swept is None:
            return True
        turn += swept
    for a, b in ring_jumps(segments):
        if _line_distance(point, a, b) <= tolerance:
            return True
        turn += _chord_angle(point, a, b)
    return round(turn / (2 * math.pi)) != 0


# ---------------------------------------------------------------------------
# Angolo spazzato da una primitiva vista da `point`; None se ci passa sopra
# ---------------------------------------------------------------------------

def _swept(segment, point: Point, tolerance: float):
    if isinstance(segment, LineSeg):
        if _line_distance(point, segment.start, segment.end) <= tolerance:
            return None
        return _chord_angle(point, segment.start, segment.end)
    if isinstance(segment, (ArcSeg, CircleSeg)):
        r = segment.radius
        if isinstance(segment, CircleSeg):
            t0, t1 = 0.0, 2 * math.pi
        else:
            sign = 1.0 if segment.ccw else -1.0
            t0 = segment.start_angle
            t1 = t0 + sign * segment._sweep()
        if _arc_distance(point, segment.center, r, t0, t1) <= tolerance:
            return None
        return _conic_swept(point, segment.center, (r, 0.0), (0.0, r), t0, t1)
    if isinstance(segment, EllipseSeg):
        if _clear_polyline(segment, point, tolerance) is None:
            return None
        mx, my = segment.major_axis
        minor = (-my * segment.ratio, mx * segment.ratio)
        sign = 1.0 if segment.ccw else -1.0
        t0 = segment.start_param
        return _conic_swept(point, segment.center, (mx, my), minor, t0, t0 + sign * segment._sweep())
    if isinstance(segment, BSplineSeg):
        pts = _clear_polyline(segment, point, tolerance)
        if pts is None:
            return None
        return sum(_chord_angle(point, a, b) for a, b in zip(pts, pts[1:]))
    raise TypeError(f"primitiva non supportata: {type(segment).__name__}")


def _chord_angle(point: Point, a: Point, b: Point) -> float:
    """Angolo con segno, in (−π, π], da a a b visti da `point`."""
    ax, ay = a[0] - point[0], a[1] - point[1]
    bx, by = b[0] - point[0], b[1] - point[1]
    return math.atan2(ax * by - ay * bx, ax * bx + ay * by)


def _conic_swept(point: Point, center: Point, m: Point, n: Point, t0: float, t1: float) -> float:
    """
    Angolo spazzato da c + M cos t + N sin t, t0 → t1, visto da `point`
    (fuori dalla curva). L'arco più la corda di ritorno è un giro che avvolge
    `point` solo se sta nel segmento di conica fra i due: allora l'arco spazza
    la corda più un giro intero nel suo verso. Nelle coordinate (cos, sin)
    della conica il segmento è il disco unitario dalla parte del punto medio
    dell'arco rispetto alla corda (tutto il disco per un giro intero).
    """
    det = m[0] * n[1] - m[1] * n[0]
    dx, dy = point[0] - center[0], point[1] - center[1]
    u = (dx * n[1] - dy * n[0]) / det
    v = (m[0] * dy - m[1] * dx) / det
    full = abs(t1 - t0) >= 2 * math.pi
    turn = math.copysign(2 * math.pi, (t1 - t0) * det)
    inside = u * u + v * v < 1.0
    if full:
        return turn if inside else 0.0
    a = (math.cos(t0), math.sin(t0))
    b = (math.cos(t1), math.sin(t1))
    start = (center[0] + m[0] * a[0] + n[0] * a[1], center[1] + m[1] * a[0] + n[1] * a[1])
    end = (center[0] + m[0] * b[0] + n[0] * b[1], center[1] + m[1] * b[0] + n[1] * b[1])
    chord = _chord_angle(point, start, end)
    if inside and abs(abs(chord) - math.pi) > 1e-9:   # sulla corda è dentro, chiuso
        mid = (t0 + t1) / 2
        c = (math.cos(mid), math.sin(mid))
        cross_mid = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        cross_pt = (b[0] - a[0]) * (v - a[1]) - (b[1] - a[1]) * (u - a[0])
        inside = cross_pt * cross_mid > 0.0
    if not inside:
        return chord
    # corda e arco girano in versi opposti: |arco| = 2π − |corda|, nel verso
    # dell'arco (anche sulla corda, dove il segno della corda è rumore)
    return math.copysign(2 * math.pi - abs(chord), turn)


# ---------------------------------------------------------------------------
# Distanze dal bordo
# ---------------------------------------------------------------------------

def _line_distance(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / l2))
    return math.dist(point, (a[0] + t * dx, a[1] + t * dy))


def _arc_distance(point: Point, center: Point, r: float, t0: float, t1: float) -> float:
    """Distanza esatta dall'arco t0 → t1 del cerchio (centro, r)."""
    phi = math.atan2(point[1] - center[1], point[0] - center[0])
    lo, hi = min(t0, t1), max(t0, t1)
    if hi - lo >= 2 * math.pi or (phi - lo) % (2 * math.pi) <= hi - lo:
        return abs(math.dist(point, center) - r)
    ends = [(center[0] + r * math.cos(t), center[1] + r * math.sin(t)) for t in (t0, t1)]
    return min(math.dist(point, q) for q in ends)


def _clear_polyline(segment, point: Point, tolerance: float):
    """
    Una polilinea di `segment` entro δ che non passa su `point`, o None se
    `point` sta sul bordo (entro `tolerance`). Se la polilinea dista d > 2δ
    da `point`, anche la curva ne dista più di δ: fra le due nessun giro può
    avvolgerlo, quindi spazzano lo stesso angolo. δ scende solo vicino al bordo.
    """
    delta = max(DEFAULT_TOLERANCE, tolerance)
    while True:
        pts = segment.discretize(delta)
        d = _polyline_distance(point, pts)
        if d > max(2 * delta, tolerance + delta):
            return pts
        if delta <= tolerance / 2:
            return None if d <= tolerance else pts
        delta = max(tolerance / 2, min(delta, d) / 4)


def _polyline_distance(point: Point, pts: Sequence[Point]) -> float:
    if len(pts) == 1:
        return math.dist(point, pts[0])
    return min(_line_distance(point, a, b) for a, b in zip(pts, pts[1:]))
