"""
topo/core/geometry/intersections.py
------------------------------------
Intersezioni pure: retta/retta, cerchio/retta, cerchio/cerchio
e `intersections(a, b)` fra due primitive qualunque.
"""

import math
from typing import Optional, Tuple, List

from ..primitives.segments import (
    ArcSeg, CircleSeg, LineSeg, angle_from_start,
)
from .measure import FLOAT_NOISE

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Intersezioni geometriche pure — usate da core/base/gap_solver.py
# ---------------------------------------------------------------------------

def _line_intersection(p1: Point, p2: Point,
                       p3: Point, p4: Point) -> Optional[Point]:
    """Intersezione tra retta (p1,p2) e retta (p3,p4). None se parallele."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    # parallele: lungo il tratto più lungo le due direzioni si scostano meno
    # del rumore dei double (G6e: una soglia fissa in mm² la decide il moto)
    shorter = min(math.hypot(x1 - x2, y1 - y2), math.hypot(x3 - x4, y3 - y4))
    if abs(denom) <= FLOAT_NOISE * shorter:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _distance(p1: Point, p2: Point) -> float:
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)


def _circle_line_intersections(cx: float, cy: float, r: float,
                                p1: Point, p2: Point) -> List[Point]:
    """
    Intersezioni tra la circonferenza (cx, cy, r) e la retta infinita (p1, p2).
    Restituisce lista di 0, 1 o 2 punti.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length <= FLOAT_NOISE:
        return []
    ux, uy = dx / length, dy / length
    # il piede della perpendicolare dal centro, nel riferimento del centro
    fx, fy = p1[0] - cx, p1[1] - cy
    along = -(fx * ux + fy * uy)
    footx, footy = fx + along * ux, fy + along * uy
    # tangenza decisa sulla distanza dalla circonferenza (mm), non sul
    # discriminante: la semicorda amplifica il rumore con la radice (G6e)
    h = math.hypot(footx, footy)
    if h > r + FLOAT_NOISE:
        return []
    if h >= r - FLOAT_NOISE:
        return [(cx + footx, cy + footy)]
    half = math.sqrt(r * r - h * h)
    return [(cx + footx - half * ux, cy + footy - half * uy),
            (cx + footx + half * ux, cy + footy + half * uy)]


def _circle_circle_intersections(cx1: float, cy1: float, r1: float,
                                  cx2: float, cy2: float, r2: float) -> List[Point]:
    """Intersezioni tra due circonferenze. Restituisce 0, 1 o 2 punti."""
    d = _distance((cx1, cy1), (cx2, cy2))
    # concentriche (nessun punto isolato), lontane o una dentro l'altra
    if d <= FLOAT_NOISE or d > r1 + r2 + FLOAT_NOISE or d < abs(r1 - r2) - FLOAT_NOISE:
        return []
    ux, uy = (cx2 - cx1) / d, (cy2 - cy1) / d
    # tangenza sulla distanza dei centri (mm), come per la retta (G6e)
    outside = d >= r1 + r2 - FLOAT_NOISE
    if outside or d <= abs(r1 - r2) + FLOAT_NOISE:
        side = r1 if outside or r1 >= r2 else -r1
        return [(cx1 + side * ux, cy1 + side * uy)]

    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = cx1 + a * ux, cy1 + a * uy
    px, py = h * uy, h * ux
    return [(mx + px, my - py), (mx - px, my + py)]


def _closest_to(candidates: List[Point], ref: Point, other: Point) -> Optional[Point]:
    """Il candidato più vicino a `ref`; a pari merito entro FLOAT_NOISE quello più
    vicino a `other`; ancora pari, None: due punti simmetrici rispetto a tutti e
    due i capi, e sceglierne uno lo deciderebbe l'ultimo bit (G6e)."""
    def tied(p, q, at):
        return abs(_distance(p, at) - _distance(q, at)) <= FLOAT_NOISE

    best = None
    for p in sorted(candidates, key=lambda p: _distance(p, ref)):
        if best is None:
            best = p
        elif tied(p, best, ref):
            if tied(p, best, other):
                return None
            if _distance(p, other) < _distance(best, other):
                best = p
    return best


# ---------------------------------------------------------------------------
# Due primitive qualunque
# ---------------------------------------------------------------------------

_SAME_POINT = 1e-7    # due radici più vicine di così sono lo stesso punto
CURVE_TOLERANCE = 1e-4  # discretizzazione di spline ed ellissi per incrociarle


def _exact_parts(seg) -> list:
    """Retta, arco, cerchio restano se stessi; spline ed ellisse diventano
    rette fitte (`CURVE_TOLERANCE`): non hanno un'intersezione in forma chiusa."""
    if isinstance(seg, (LineSeg, ArcSeg, CircleSeg)):
        return [seg]
    pts = [tuple(q[:2]) for q in seg.discretize(tolerance=CURVE_TOLERANCE)]
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:]) if a != b]


def _on_line(seg: LineSeg, pt: Point) -> bool:
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return False
    t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    # sul tratto se sfora un capo al più del rumore dei double, in mm (G6e)
    slack = FLOAT_NOISE / math.sqrt(l2)
    return -slack <= t <= 1 + slack


def _on_arc(seg, pt: Point) -> bool:
    if isinstance(seg, CircleSeg):
        return True
    s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    slack = FLOAT_NOISE / seg.radius   # lo stesso sforamento in mm, come angolo
    return s <= seg._sweep() + slack or s >= 2 * math.pi - slack


def _meet(a, b) -> List[Point]:
    if isinstance(a, LineSeg) and isinstance(b, LineSeg):
        ix = _line_intersection(a.start, a.end, b.start, b.end)
        return [ix] if ix and _on_line(a, ix) and _on_line(b, ix) else []
    if isinstance(a, LineSeg) or isinstance(b, LineSeg):
        line, arc = (a, b) if isinstance(a, LineSeg) else (b, a)
        pts = _circle_line_intersections(arc.center[0], arc.center[1], arc.radius, line.start, line.end)
        return [p for p in pts if _on_line(line, p) and _on_arc(arc, p)]
    pts = _circle_circle_intersections(a.center[0], a.center[1], a.radius,
                                       b.center[0], b.center[1], b.radius)
    return [p for p in pts if _on_arc(a, p) and _on_arc(b, p)]


def intersections(a, b) -> List[Point]:
    """
    The points where two primitives meet: crossings and touches, ends
    included. Exact between lines, arcs and circles (closed form); on splines
    and ellipses within `CURVE_TOLERANCE`, because there is no closed form.
    Two overlapping stretches (same line, same circle) give no points: their
    meeting is a stretch, not a point.
    """
    out: List[Point] = []
    for pa in _exact_parts(a):
        for pb in _exact_parts(b):
            for p in _meet(pa, pb):
                if all(_distance(p, q) > _SAME_POINT for q in out):
                    out.append(p)
    return out
