"""
topo/core/geometry/intersections.py
------------------------------------
Pure intersections: line/line, circle/line, circle/circle, line/conic
(ellipse, parabola, hyperbola: a second-degree equation in the conic's frame)
and `intersections(a, b)` between any two primitives.
"""

from ...precision import FLOAT_NOISE, SAME_POINT
import math
from typing import Optional, Tuple, List

from ..primitives.line import LineSeg
from ..primitives.conics import angle_from_start
from ..primitives.conics import CircleSeg, ConicSeg, HyperbolaSeg, ParabolaSeg
from .measure import FLOAT_NOISE

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Intersezioni geometriche pure — usate da core/base/gaps.py
# ---------------------------------------------------------------------------

def line_intersection(p1: Point, p2: Point,
                       p3: Point, p4: Point) -> Optional[Point]:
    """Intersection of line (p1,p2) and line (p3,p4). None if parallel."""
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    # parallel: along the longer stretch the two directions differ by less than
    # the double noise (a fixed threshold in mm² would be decided by the motion)
    shorter = min(math.hypot(x1 - x2, y1 - y2), math.hypot(x3 - x4, y3 - y4))
    if abs(denom) <= FLOAT_NOISE * shorter:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def circle_line_intersections(cx: float, cy: float, r: float,
                                p1: Point, p2: Point) -> List[Point]:
    """Intersections of the circle (cx, cy, r) and the infinite line (p1, p2).
    Returns a list of 0, 1 or 2 points."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length <= FLOAT_NOISE:
        return []
    ux, uy = dx / length, dy / length
    # the foot of the perpendicular from the centre, in the centre's frame
    fx, fy = p1[0] - cx, p1[1] - cy
    along = -(fx * ux + fy * uy)
    footx, footy = fx + along * ux, fy + along * uy
    # tangency decided on the distance from the circle (mm), not on the
    # discriminant: the half-chord amplifies the noise by the square root
    h = math.hypot(footx, footy)
    if h > r + FLOAT_NOISE:
        return []
    if h >= r - FLOAT_NOISE:
        return [(cx + footx, cy + footy)]
    half = math.sqrt(r * r - h * h)
    return [(cx + footx - half * ux, cy + footy - half * uy),
            (cx + footx + half * ux, cy + footy + half * uy)]


def circle_circle_intersections(cx1: float, cy1: float, r1: float,
                                  cx2: float, cy2: float, r2: float) -> List[Point]:
    """Intersections of two circles. Returns 0, 1 or 2 points."""
    d = math.dist((cx1, cy1), (cx2, cy2))
    # concentric (no isolated point), far apart or one inside the other
    if d <= FLOAT_NOISE or d > r1 + r2 + FLOAT_NOISE or d < abs(r1 - r2) - FLOAT_NOISE:
        return []
    ux, uy = (cx2 - cx1) / d, (cy2 - cy1) / d
    # tangency on the distance of the centres (mm), as for the line
    outside = d >= r1 + r2 - FLOAT_NOISE
    if outside or d <= abs(r1 - r2) + FLOAT_NOISE:
        side = r1 if outside or r1 >= r2 else -r1
        return [(cx1 + side * ux, cy1 + side * uy)]

    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = cx1 + a * ux, cy1 + a * uy
    px, py = h * uy, h * ux
    return [(mx + px, my - py), (mx - px, my + py)]


def closest_to(candidates: List[Point], ref: Point, other: Point) -> Optional[Point]:
    """The candidate nearest `ref`; on a tie within FLOAT_NOISE the one nearest
    `other`; still a tie, None: two points symmetric with respect to both ends,
    and picking one would be decided by the last bit."""
    def tied(p, q, at):
        return abs(math.dist(p, at) - math.dist(q, at)) <= FLOAT_NOISE

    best = None
    for p in sorted(candidates, key=lambda p: math.dist(p, ref)):
        if best is None:
            best = p
        elif tied(p, best, ref):
            if tied(p, best, other):
                return None
            if math.dist(p, other) < math.dist(best, other):
                best = p
    return best


# ---------------------------------------------------------------------------
# Due primitive qualunque
# ---------------------------------------------------------------------------

_SAME_ROOT = FLOAT_NOISE    # two roots closer than this are the same point computed twice
CURVE_TOLERANCE = SAME_POINT  # curves without a closed form are discretized to cross them


def _exact_parts(seg) -> list:
    """Line, arc, circle stay themselves; the other curves become dense lines
    (`CURVE_TOLERANCE`): they have no closed-form intersection."""
    if isinstance(seg, (LineSeg, CircleSeg)):
        return [seg]
    pts = [tuple(q[:2]) for q in seg.discretize(tolerance=CURVE_TOLERANCE)]
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:]) if a != b]


def _on_line(seg: LineSeg, pt: Point) -> bool:
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return False
    t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    # on the stretch if it overshoots an end by at most the double noise, in mm
    slack = FLOAT_NOISE / math.sqrt(l2)
    return -slack <= t <= 1 + slack


def _on_arc(seg, pt: Point) -> bool:
    s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    slack = FLOAT_NOISE / seg.radius   # the same overshoot in mm, as an angle
    return s <= seg._sweep() + slack or s >= 2 * math.pi - slack


def _meet(a, b) -> List[Point]:
    if isinstance(a, LineSeg) and isinstance(b, LineSeg):
        ix = line_intersection(a.start, a.end, b.start, b.end)
        return [ix] if ix and _on_line(a, ix) and _on_line(b, ix) else []
    if isinstance(a, LineSeg) or isinstance(b, LineSeg):
        line, arc = (a, b) if isinstance(a, LineSeg) else (b, a)
        pts = circle_line_intersections(arc.center[0], arc.center[1], arc.radius, line.start, line.end)
        return [p for p in pts if _on_line(line, p) and _on_arc(arc, p)]
    pts = circle_circle_intersections(a.center[0], a.center[1], a.radius,
                                       b.center[0], b.center[1], b.radius)
    return [p for p in pts if _on_arc(a, p) and _on_arc(b, p)]


def _conic_frame(conic):
    """(origin, unit x, unit y) of the frame in which the conic has its simple
    equation: x²/a² ± y²/b² = 1 (centre and axis), x² = 4f·y (vertex, x along the
    tangent at the vertex, y towards the focus)."""
    if isinstance(conic, ParabolaSeg):
        _, u, n = conic._frame()
        return conic.vertex, n, u
    a = math.hypot(*conic.major_axis)
    u = (conic.major_axis[0] / a, conic.major_axis[1] / a)
    return conic.center, u, (-u[1], u[0])


def _line_conic(line: LineSeg, conic) -> List[Point]:
    """The points where the stretch `line` meets the piece `conic`: the line
    A + λ·(B − A) in the conic's equation gives α·λ² + β·λ + γ = 0."""
    origin, ex, ey = _conic_frame(conic)
    ax, ay = line.start[0] - origin[0], line.start[1] - origin[1]
    dx, dy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    x0, y0 = ax * ex[0] + ay * ex[1], ax * ey[0] + ay * ey[1]
    x1, y1 = dx * ex[0] + dy * ex[1], dx * ey[0] + dy * ey[1]
    if isinstance(conic, ParabolaSeg):
        f = conic._frame()[0]
        alpha, beta, gamma = x1 * x1, 2 * x0 * x1 - 4 * f * y1, x0 * x0 - 4 * f * y0
    else:
        a = math.hypot(*conic.major_axis)
        b = a * conic.ratio
        sign = -1.0 if isinstance(conic, HyperbolaSeg) else 1.0
        alpha = (x1 / a) ** 2 + sign * (y1 / b) ** 2
        beta = 2 * (x0 * x1 / (a * a) + sign * y0 * y1 / (b * b))
        gamma = (x0 / a) ** 2 + sign * (y0 / b) ** 2 - 1
    scale = max(abs(alpha), abs(beta), abs(gamma))
    if scale == 0:
        return []
    if abs(alpha) <= FLOAT_NOISE * scale:
        roots = [-gamma / beta] if abs(beta) > FLOAT_NOISE * scale else []
    else:
        disc = beta * beta - 4 * alpha * gamma
        if disc < -FLOAT_NOISE * beta * beta:
            roots = []
        else:
            # stable root (no subtraction of two close numbers), the other from the product
            q = -0.5 * (beta + math.copysign(math.sqrt(max(disc, 0.0)), beta))
            roots = [q / alpha] + ([gamma / q] if q != 0 else [])
    length = math.hypot(dx, dy)
    out = []
    for lam in roots:
        if not -FLOAT_NOISE / length <= lam <= 1 + FLOAT_NOISE / length:
            continue
        x, y = x0 + lam * x1, y0 + lam * y1
        if _on_conic_piece(conic, x, y):
            out.append((line.start[0] + lam * dx, line.start[1] + lam * dy))
    return out


def _on_conic_piece(conic, x: float, y: float) -> bool:
    """The point (x, y), on the conic in its frame, falls on the piece."""
    if isinstance(conic, ParabolaSeg):
        lo, hi = sorted((conic.start_param, conic.end_param))
        return lo - FLOAT_NOISE <= x <= hi + FLOAT_NOISE
    a = math.hypot(*conic.major_axis)
    b = a * conic.ratio
    if isinstance(conic, HyperbolaSeg):
        lo, hi = sorted((conic.start_param, conic.end_param))
        s = math.asinh(y / b)
        return x > 0 and lo - FLOAT_NOISE / b <= s <= hi + FLOAT_NOISE / b
    s = math.atan2(y / b, x / a)
    off = ((s - conic.start_param) if conic.ccw else (conic.start_param - s)) % (2 * math.pi)
    slack = FLOAT_NOISE / b
    return off <= conic._sweep() + slack or off >= 2 * math.pi - slack


def _exact_conic(seg) -> bool:
    """A conic that is not a circle: it meets a line in closed form."""
    return isinstance(seg, ConicSeg) and not isinstance(seg, CircleSeg)


def intersections(a, b) -> List[Point]:
    """
    The points where two primitives meet: crossings and touches, ends
    included. Exact between lines, arcs and circles, and between a line and
    any conic (closed form); elsewhere (two non-circular conics, splines)
    within `CURVE_TOLERANCE`.
    Two overlapping stretches (same line, same circle) give no points: their
    meeting is a stretch, not a point.
    """
    out: List[Point] = []
    if isinstance(a, LineSeg) and _exact_conic(b) or isinstance(b, LineSeg) and _exact_conic(a):
        line, conic = (a, b) if isinstance(a, LineSeg) else (b, a)
        for p in _line_conic(line, conic):
            if all(math.dist(p, q) > _SAME_ROOT for q in out):
                out.append(p)
        return out
    for pa in _exact_parts(a):
        for pb in _exact_parts(b):
            for p in _meet(pa, pb):
                if all(math.dist(p, q) > _SAME_ROOT for q in out):
                    out.append(p)
    return out
