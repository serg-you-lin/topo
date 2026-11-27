"""
topo/core/geometry/fitting.py
------------------------------
From an ordered, dense sequence of points (a contour traced from a raster, a
curve written as points by a source) to clean primitives: lines where it is
straight, arcs where the radius is constant, splines only for the rest,
sharp corners where it turns — the inverse of discretization.

    simplify_points — the only entry

Three guarantees, all geometric: every given point is within `tolerance` of
the primitives; the primitives are a head-to-tail chain (an open sequence
starts and ends exactly at its ends, a closed one closes); a primitive is a
line or an arc only if its points are one within `tolerance`. Thresholds are
always the caller's.

The maths on points (Douglas-Peucker, corners by turn, circle through three
points, approximating b-spline) lives in `points.py`, `corners.py`,
`curve_tests.py` and `spline_fit.py` alongside; here is the orchestration:
split on corners, decide line, arc or spline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..primitives.line import LineSeg
from ..primitives.spline import BSplineSeg
from ..primitives.mathseg import MathSeg, Point
from ..primitives.conics import CircleSeg, EllipseSeg, HyperbolaSeg, is_arc
from .measure import FLOAT_NOISE, track_length
from .points import (
    DEFAULT_DUPLICATE_TOLERANCE, circle_through, douglas_peucker, drop_duplicate_points,
    even_spacing, fit_circle_kasa, offset_from_line,
)
from .spline_fit import approximate_bspline
from .curve_tests import within_chord, within_circle_through, within_conic_through, within_smooth_curve
from .corners import turn_corners

Primitive = MathSeg

DEFAULT_SPLINE_DEGREE = 3


@dataclass
class _Part:
    """A piece of the sequence: `kind` "line" or "curve", with the points it covers (ends shared with the neighbours)."""
    kind: str
    points: List[Point]


def _signed_turn(a: Point, b: Point, c: Point) -> float:
    """Signed turn (degrees) at `b` going from `a` to `c`: positive to the left.
    0 if `b` is on the line `a`-`c` within the noise: the sign there is the last bit's."""
    if abs(offset_from_line(b, a, c)) <= FLOAT_NOISE:
        return 0.0
    v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    return math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1]))


def _split_stretch(points: List[Point], tolerance: float, scale: float, corner_turn_deg: Optional[float],
                   arcs: bool) -> List[_Part]:
    """A stretch with no corners: all within `tolerance` of the chord -> a line;
    all within `tolerance` of an arc through its ends (with `arcs`) -> an arc.
    Otherwise the Douglas-Peucker sides at least `scale` long become lines,
    except those INSIDE a curve — small turn and in the same direction at the
    ends that have a neighbour, and not much longer than the neighbours: they
    are facets of a curve, not a straight side (the straight side of a squared O
    is more than twice as long as its neighbours). Small turn: below
    `corner_turn_deg`, or with `None` the side, with `scale` on each side, within
    `tolerance` of a smooth curve."""
    if within_chord(points, tolerance) and _chord_in_order(points, tolerance):
        return [_Part("line", points)]
    if arcs and len(points) >= 4 and (_arc_through_ends(points, tolerance) is not None
                                      or _ellipse_fits(points, tolerance)):
        return [_Part("curve", points)]
    dp = douglas_peucker(points, tolerance)
    sides = list(zip(dp, dp[1:]))
    lengths = [math.dist(points[i], points[j]) for i, j in sides]

    def is_line(e: int) -> bool:
        if lengths[e] < scale:
            return False
        turns, neighbours = [], []
        i, j = sides[e]
        if e > 0:
            turns.append(_signed_turn(points[sides[e - 1][0]], points[i], points[j]))
            neighbours.append(lengths[e - 1])
        if e < len(sides) - 1:
            turns.append(_signed_turn(points[i], points[j], points[sides[e + 1][1]]))
            neighbours.append(lengths[e + 1])
        if not turns:
            return True
        same_way = all(t > 0 for t in turns) or all(t < 0 for t in turns)
        if corner_turn_deg is None:
            # the side plus `scale` on each side: a long straight neighbour does not count
            first, last = i, j
            while first > 0 and math.dist(points[first - 1], points[i]) <= scale:
                first -= 1
            while last < len(points) - 1 and math.dist(points[last + 1], points[j]) <= scale:
                last += 1
            inside_curve = same_way and within_smooth_curve(points[first: last + 1], tolerance)
        else:
            inside_curve = same_way and max(abs(t) for t in turns) < corner_turn_deg
        return not inside_curve or lengths[e] >= 2 * max(neighbours)

    parts: List[_Part] = []
    curve_from = 0
    for e, (i, j) in enumerate(sides):
        if is_line(e):
            if i > curve_from:
                parts.append(_Part("curve", points[curve_from: i + 1]))
            parts.append(_Part("line", points[i: j + 1]))
            curve_from = j
    if curve_from < len(points) - 1:
        parts.append(_Part("curve", points[curve_from:]))
    return parts


def _arc_through_ends(points: List[Point], tolerance: float) -> Optional[CircleSeg]:
    """The arc passing exactly through the first and last point (and the middle
    one), if all points are within `tolerance` of its circle. It goes through
    the ends rather than by least squares: an arc that moves them leaves a gap
    with the adjacent primitive."""
    a, m, b = points[0], points[len(points) // 2], points[-1]
    circle = within_circle_through(points, tolerance)
    if circle is None:
        return None
    center, radius = circle
    # from a to b through m: counter-clockwise if m is to the right of the chord a->b
    ccw = offset_from_line(m, a, b) < 0
    sign, start = (1.0 if ccw else -1.0), math.atan2(a[1] - center[1], a[0] - center[0])
    walked = [(sign * (math.atan2(p[1] - center[1], p[0] - center[0]) - start)) % (2 * math.pi) for p in points]
    walked[0] = 0.0

    def foot(w: float) -> Point:
        return center[0] + radius * math.cos(start + sign * w), center[1] + radius * math.sin(start + sign * w)

    if not _one_pass(points, walked, foot, walked[-1], tolerance):
        return None
    return CircleSeg(center=center, radius=radius, start_angle=start,
                  end_angle=math.atan2(b[1] - center[1], b[0] - center[0]), ccw=ccw)


def _ellipse_fits(points: List[Point], tolerance: float) -> bool:
    """The whole stretch lies on an ellipse through its ends. Not a hyperbola: its
    branches stay close to their asymptotes, and a narrow one passes within
    `tolerance` of two lines that meet. The straight sides separate first; the
    hyperbola is tried afterwards on the curved piece that remains (`_fit_curve`)."""
    return isinstance(_conic_through_ends(points, tolerance), EllipseSeg)


def _conic_through_ends(points: List[Point], tolerance: float):
    """The ellipse or hyperbola arc through the first and last point, in the
    direction that passes through the others, if all are within `tolerance` of
    it (like `_arc_through_ends`); which of the two is told by the conic."""
    fit = within_conic_through(points, tolerance)
    if fit is None:
        return None
    kind, center, major_axis, ratio, params = fit
    ta, tm, tb = params[0], params[len(params) // 2], params[-1]
    if kind == "hyperbola":
        # on a branch the parameter runs straight from one end to the other: the middle point lies between them
        if not min(ta, tb) < tm < max(ta, tb):
            return None
        seg = HyperbolaSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=ta, end_param=tb)
        sign = 1.0 if tb > ta else -1.0
        walked = [sign * (t - ta) for t in params]
        at = seg._point
    else:
        ccw = (tm - ta) % (2 * math.pi) < (tb - ta) % (2 * math.pi)
        seg = EllipseSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=ta, end_param=tb, ccw=ccw)
        sign = 1.0 if ccw else -1.0
        walked = [(sign * (t - ta)) % (2 * math.pi) for t in params]
        walked[0] = 0.0
        at = seg._point_at
    if not _one_pass(points, walked, lambda w: at(ta + sign * w), walked[-1], tolerance):
        return None
    return seg


def _one_pass(points: List[Point], walked: List[float], foot, total: float, tolerance: float) -> bool:
    """The points walk the piece once, in order, like the sequence that gave it.
    `walked[k]`: the parameter of the foot of point k counted from the first in
    the piece's direction, `total` that of the last, `foot(w)` the point of the
    piece there. A foot outside the piece is a point beyond an end: fine within
    `tolerance` of that end. A step back is noise only if the two feet are
    within `tolerance`; longer, the piece would pass again where it has been, or
    go round the other way. Like `_walked`, but for points known within
    `tolerance` instead of exact."""
    start, end = foot(0.0), foot(total)
    reached = 0.0
    for p, w in zip(points, walked):
        if not 0.0 <= w <= total:
            near_start, near_end = math.dist(p, start), math.dist(p, end)
            if min(near_start, near_end) > tolerance:
                return False
            w = 0.0 if near_start <= near_end else total
        if w < reached and math.dist(foot(w), foot(reached)) > tolerance:
            return False
        reached = max(reached, w)
    return True


def _chord_in_order(points: List[Point], tolerance: float) -> bool:
    """The first-last chord walked once by the points (`_one_pass`)."""
    a, b = points[0], points[-1]
    length = math.dist(a, b)
    if length == 0:
        return True
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    walked = [(p[0] - a[0]) * ux + (p[1] - a[1]) * uy for p in points]
    return _one_pass(points, walked, lambda w: (a[0] + w * ux, a[1] + w * uy), length, tolerance)


def _chords_within(pts: List[Point], feet: List[Point], radius_between, polygon: float, tolerance: float) -> bool:
    """Every point of the curve within `tolerance` of the conic, not only the
    vertices: the curve is within `polygon` of the chords, a chord within the
    deviation of its ends from the chord between their feet on the conic, and
    that within the sagitta of the circle of the smallest curvature radius on
    the arc between the feet (`radius_between(i)`): a less curved curve than a
    circle deviates less from the chord."""
    for i in range(len(pts) - 1):
        rho = radius_between(i)
        half = math.dist(feet[i], feet[i + 1]) / 2
        if half > rho:
            return False
        gap = max(math.dist(pts[i], feet[i]), math.dist(pts[i + 1], feet[i + 1]))
        if gap + rho - math.sqrt(rho * rho - half * half) + polygon > tolerance:
            return False
    return True


def _ellipse_curvature_radius(a: float, b: float, t0: float, t1: float) -> float:
    """Smallest curvature radius of the ellipse between the nearby parameters `t0`
    and `t1`: (a²sin²t + b²cos²t)^(3/2)/(ab) grows with sin²t, which is minimal
    at a multiple of π if the span contains one, otherwise at an end."""
    d = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi
    lo, hi = min(t0, t0 + d), max(t0, t0 + d)
    s2 = 0.0 if math.floor(hi / math.pi) >= math.ceil(lo / math.pi) else min(math.sin(lo) ** 2, math.sin(hi) ** 2)
    return (a * a * s2 + b * b * (1 - s2)) ** 1.5 / (a * b)


def _walked(params: Sequence[float], ccw: bool, closed: bool) -> Optional[List[float]]:
    """The parameter (angle) walked from the first point, the `ccw` way; None if it
    goes back: then the curve does not walk the conic once."""
    sign = 1.0 if ccw else -1.0
    walked = [(sign * (p - params[0])) % (2 * math.pi) for p in params]
    walked[0] = 0.0
    if closed:
        walked[-1] = 2 * math.pi
    if any(b < a - FLOAT_NOISE for a, b in zip(walked, walked[1:])):
        return None
    return walked


def conic_of_spline(spline: BSplineSeg, tolerance: float) -> Optional[EllipseSeg]:
    """The arc (or circle) or ellipse arc (or ellipse) that the spline is: through
    its exact ends, every point of the true curve within `tolerance` of it,
    proved on the chords of its polygon, walked once in the spline's direction.
    The circle first, simpler; never the hyperbola. None if neither. The polygon
    is refined tenfold at a time, down to FLOAT_NOISE, only while the answer can
    still change: vertices within `tolerance` and chords not yet proved, or too
    few points."""
    polygon = tolerance / 10
    while True:
        conic, finer = _conic_on(spline, polygon, tolerance)
        if conic is not None or not finer or polygon <= FLOAT_NOISE:
            return conic
        polygon /= 10


def _conic_on(spline: BSplineSeg, polygon: float, tolerance: float) -> Tuple[Optional[EllipseSeg], bool]:
    """(conic, whether a finer polygon can change the answer) on the spline's
    polygon within `polygon`."""
    pts = spline.discretize(tolerance=polygon)
    start, end = spline.endpoints()
    pts[0], pts[-1] = start, end
    closed = math.dist(start, end) <= FLOAT_NOISE
    if closed:
        pts[-1] = start
        # the direction the curve turns: the signed area of its polygon
        ccw = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:])) > 0
        n = len(pts)
        circle = circle_through(start, pts[n // 3], pts[2 * n // 3])
    else:
        ccw = offset_from_line(pts[len(pts) // 2], start, end) < 0
        circle = circle_through(start, pts[len(pts) // 2], end)
    if circle is not None:
        center, radius = circle
        if all(abs(math.dist(center, p) - radius) <= tolerance for p in pts):
            angles = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in pts]
            if _walked(angles, ccw, closed) is not None:
                feet = [(center[0] + radius * math.cos(a), center[1] + radius * math.sin(a)) for a in angles]
                if not _chords_within(pts, feet, lambda i: radius, polygon, tolerance):
                    # the vertices are on the circle, the chords not yet: finer, not the ellipse
                    return None, True
                a0 = angles[0]
                a1 = a0 + (2 * math.pi if ccw else -2 * math.pi) if closed else angles[-1]
                return CircleSeg(center=center, radius=radius, start_angle=a0, end_angle=a1, ccw=ccw), False
    # a conic is fixed by 5 points: with fewer than 6 the test says nothing
    if len(pts) < 6:
        return None, True
    fit = within_conic_through(pts, tolerance)
    if fit is None or fit[0] != "ellipse":
        return None, False
    _, center, major_axis, ratio, params = fit
    if _walked(params, ccw, closed) is None:
        return None, False
    p0 = params[0]
    p1 = p0 + (2 * math.pi if ccw else -2 * math.pi) if closed else params[-1]
    ellipse = EllipseSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=p0, end_param=p1, ccw=ccw)
    a = math.hypot(*major_axis)
    feet = [ellipse._point_at(t) for t in params]
    if not _chords_within(pts, feet, lambda i: _ellipse_curvature_radius(a, a * ratio, params[i], params[i + 1]),
                          polygon, tolerance):
        return None, True
    return ellipse, False


def _fit_curve(points: List[Point], tolerance: float, arcs: bool, degree: int) -> List[Primitive]:
    """A curved piece: the simplest family within `tolerance` for the ends — arc,
    ellipse or hyperbola arc (with `arcs`), spline."""
    if len(points) <= degree:
        return [LineSeg(start=a, end=b) for a, b in zip(points, points[1:])]
    if arcs and len(points) >= 4:
        arc = _arc_through_ends(points, tolerance)
        if arc is not None:
            return [arc]
        conic = _conic_through_ends(points, tolerance)
        if conic is not None:
            return [conic]
    control, knots = approximate_bspline(points, degree, tolerance)
    if len(control) >= len(points):
        # the spline through all the points has not been tested by anyone: it always
        # passes, even on a corner. The sides remain
        return [LineSeg(start=a, end=b) for a, b in zip(points, points[1:])]
    return [BSplineSeg(degree=degree, control_points=control, knots=knots)]


def _line_fit(points: List[Point]) -> Tuple[Point, Point]:
    """Least-squares line on the points: (point, unit direction)."""
    n = len(points)
    cx, cy = sum(p[0] for p in points) / n, sum(p[1] for p in points) / n
    sxx = sum((p[0] - cx) ** 2 for p in points)
    syy = sum((p[1] - cy) ** 2 for p in points)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in points)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return (cx, cy), (math.cos(angle), math.sin(angle))


def _crossing(l1, l2) -> Optional[Point]:
    (p, d), (q, e) = l1, l2
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + t * d[0], p[1] + t * d[1])




def _line_turn(a: _Part, b: _Part) -> float:
    """By how many degrees one turns going from line `a` to line `b`."""
    (ax, ay), (bx, by) = a.points[0], a.points[-1]
    (cx, cy), (dx, dy) = b.points[0], b.points[-1]
    u, v = (bx - ax, by - ay), (dx - cx, dy - cy)
    return abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))


def _is_rounding(part: _Part, before: _Part, after: _Part, tolerance: float,
                 corner_turn_deg: Optional[float]) -> bool:
    """The curved piece between the lines `before` and `after` is the blunting of a corner."""
    if corner_turn_deg is not None:
        return _line_turn(before, after) >= corner_turn_deg
    lines = [(before.points[0], before.points[-1]), (after.points[0], after.points[-1])]
    return all(min(abs(offset_from_line(q, a, b)) for a, b in lines) <= tolerance for q in part.points)


def _restore_corners(parts: List[_Part], closed: bool, tolerance: float, scale: float,
                     corner_turn_deg: Optional[float]) -> List[_Part]:
    """The sharp corners that sampling blunted. A curved piece shorter than `scale`
    between two lines that turn by at least `corner_turn_deg` (with `None`: whose
    points are within `tolerance` of one line or the other) is the rounding of a
    corner: it disappears. Then between two consecutive lines the common vertex
    goes to the least-squares intersection of the two lines, where the true
    corner is, if it falls within `scale` of the sampled vertex and the points
    of the two lines farther than `scale` from there stay within `tolerance`. An
    end of an open sequence never moves."""
    kept: List[_Part] = []
    n = len(parts)
    for k, part in enumerate(parts):
        before, after = parts[k - 1] if (closed or k > 0) else None, parts[(k + 1) % n] if (closed or k < n - 1) else None
        if (part.kind == "curve" and before is not None and after is not None and n > 2
                and before.kind == "line" and after.kind == "line" and before is not after
                and track_length(part.points) < scale and _is_rounding(part, before, after, tolerance, corner_turn_deg)):
            continue
        kept.append(part)
    parts = kept

    count = len(parts)
    for i in (range(count) if closed else range(count - 1)):
        a, b = parts[i], parts[(i + 1) % count]
        if a.kind != "line" or b.kind != "line" or a is b:
            continue
        joint_a, joint_b = a.points[-1], b.points[0]
        corner = _crossing(_line_fit(a.points), _line_fit(b.points))
        if corner is None or math.dist(corner, joint_a) > scale + math.dist(joint_a, joint_b):
            if joint_a != joint_b:   # a gap is left where the rounding was: the midpoint closes it
                mid = ((joint_a[0] + joint_b[0]) / 2, (joint_a[1] + joint_b[1]) / 2)
                a.points, b.points = a.points[:-1] + [mid], [mid] + b.points[1:]
            continue
        far_a = [q for q in a.points[:-1] if math.dist(q, corner) > scale] + [corner]
        far_b = [corner] + [q for q in b.points[1:] if math.dist(q, corner) > scale]
        if within_chord(far_a, tolerance) and within_chord(far_b, tolerance):
            a.points, b.points = a.points[:-1] + [corner], [corner] + b.points[1:]
        elif joint_a != joint_b:
            mid = ((joint_a[0] + joint_b[0]) / 2, (joint_a[1] + joint_b[1]) / 2)
            a.points, b.points = a.points[:-1] + [mid], [mid] + b.points[1:]
    return parts


def _join_seam(prims: List[Primitive], tolerance: float) -> List[Primitive]:
    """A contour without corners opens at any point: if the first and last piece
    are the same arc or the same line, the seam is not a point of the contour
    and the two become one."""
    if len(prims) < 2:
        return prims
    last, first = prims[-1], prims[0]
    if is_arc(last) and is_arc(first) and last.ccw == first.ccw             and math.dist(last.center, first.center) <= tolerance and abs(last.radius - first.radius) <= tolerance:
        merged = CircleSeg(center=last.center, radius=last.radius, start_angle=last.start_angle,
                        end_angle=first.end_angle, ccw=last.ccw)
        return [merged] + prims[1:-1]
    if isinstance(last, LineSeg) and isinstance(first, LineSeg)             and abs(offset_from_line(last.end, last.start, first.end)) <= tolerance:
        return [LineSeg(start=last.start, end=first.end)] + prims[1:-1]
    return prims


def _to_primitives(parts: List[_Part], tolerance: float, arcs: bool, degree: int) -> List[Primitive]:
    out: List[Primitive] = []
    for part in parts:
        if part.kind == "line":
            if math.dist(part.points[0], part.points[-1]) > 0:
                out.append(LineSeg(start=part.points[0], end=part.points[-1]))
        else:
            out.extend(_fit_curve(part.points, tolerance, arcs, degree))
    return out


def simplify_points(
    points: Sequence[Point],
    tolerance: float,
    scale: float,
    closed: bool = True,
    *,
    corner_turn_deg: Optional[float],
    arcs: bool = True,
    spline_degree: int = DEFAULT_SPLINE_DEGREE,
) -> List[Primitive]:
    """Primitives (lines, arcs, circles, ellipses, splines) for the sequence of
    points `points`, as a head-to-tail chain, every point within `tolerance` of
    them — except those within `scale` of a corner that sampling had blunted and
    that comes back sharp here.

    Args:
        points:           ordered points; `closed=True` a contour (the last
                          returns to the first), `closed=False` an open stretch
                          whose ends stay exactly where they are
        tolerance:        maximum deviation from the points (units of the points)
        scale:            the length over which the turn of a corner is measured:
                          a shorter straight stretch stays part of a curve, a
                          curve shorter than two sides is a blunted corner
        corner_turn_deg:  minimum turn (degrees) over `scale` for a corner,
                          chosen by the caller: lower, more corners. None:
                          a corner where no line or arc is within `tolerance`
                          over `scale`; only for dense points, like the refit of
                          `heal()`. Temporary: goes away when smoother has its
                          own fitter
        arcs:             False: no arcs, circles or conics, only lines and splines
        spline_degree:    degree of the splines"""
    pts = [(float(p[0]), float(p[1])) for p in drop_duplicate_points(list(points), DEFAULT_DUPLICATE_TOLERANCE)]
    if closed and len(pts) > 1 and math.dist(pts[0], pts[-1]) <= DEFAULT_DUPLICATE_TOLERANCE:
        pts.pop()
    if len(pts) < 2:
        return []
    if len(pts) == 2:
        return [] if closed else [LineSeg(start=pts[0], end=pts[1])]
    pts = even_spacing(pts, closed)
    corners = turn_corners(pts, closed, corner_turn_deg, scale, tolerance)

    if closed and not corners:
        if arcs:
            fit = fit_circle_kasa(pts)
            if fit is not None and fit[2] <= tolerance:
                return [CircleSeg(center=fit[0], radius=fit[1])]
            ring = within_conic_through(pts + [pts[0]], tolerance)
            if ring is not None and ring[0] == "ellipse":      # a closed ring: a hyperbola does not close
                return [EllipseSeg(center=ring[1], major_axis=ring[2], ratio=ring[3],
                                   start_param=0.0, end_param=2 * math.pi)]
        # no corner: the loop opens at the point farthest from the first
        #
        far = max(range(len(pts)), key=lambda k: math.dist(pts[0], pts[k]))
        loop = pts[far:] + pts[:far] + [pts[far]]
        parts = _split_stretch(loop, tolerance, scale, corner_turn_deg, arcs)
        parts = _restore_corners(parts, False, tolerance, scale, corner_turn_deg)
        return _join_seam(_to_primitives(parts, tolerance, arcs, spline_degree), tolerance)

    if closed:
        start = corners[0]
        ordered = pts[start:] + pts[:start] + [pts[start]]
        bounds = [k - start for k in corners] + [len(pts)]
    else:
        ordered = pts
        bounds = [0] + corners + [len(pts) - 1]

    parts: List[_Part] = []
    for i, j in zip(bounds, bounds[1:]):
        parts.extend(_split_stretch(ordered[i: j + 1], tolerance, scale, corner_turn_deg, arcs))
    parts = _restore_corners(parts, closed, tolerance, scale, corner_turn_deg)
    return _to_primitives(parts, tolerance, arcs, spline_degree)
