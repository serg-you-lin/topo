"""
topo/core/geometry/regions.py
------------------------------
A closed contour and a region: where a point falls on the contour (mid-side,
on a corner, on a fillet), a stretch cut by a region, a contour minus a
region; the union of two contours, even with a shared edge; which outer
contour wholly contains a trace.

Contour and region are head-to-tail rings of primitives (`contour.segments`,
`topo.geometry.circle`, `topo.geometry.rectangle`, ...): a region is any
closed contour, not a named shape. Cuts fall on the exact points of
`intersections`; the pieces stay primitives of the same type (a cut arc is an
arc). Shapely is used only to say whether the midpoint of a piece is inside
or outside.

Pure: primitives only, no format.
"""

from __future__ import annotations

from ...precision import FLOAT_NOISE, SAME_POINT
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from shapely.geometry import LineString, Point as SPoint, Polygon
from shapely.prepared import prep

from .measure import SAME_POINT, segment_length
from .numeric import golden_min
from .shapely_polygons import build_polygon
from ..primitives.spline import BSplineSeg
from ..primitives.line import LineSeg
from ..primitives.mathseg import DEFAULT_TOLERANCE
from ..primitives.conics import angle_from_start, point_on_circle
from ..primitives.conics import CircleSeg, is_arc, is_full_circle
from ..primitives.trim import sub_segment
from .integrals import ring_moments
from .intersections import CURVE_TOLERANCE, intersections
from .shape import merge_runs

Point = Tuple[float, float]

_JOIN = SAME_POINT               # ends closer than this are the same node
_MIN_PIECE = SAME_POINT          # pieces shorter than this do not exist
_POLYGON_TOLERANCE = SAME_POINT  # sagitta of the discretization for the inside/outside tests
_ON_BORDER = SAME_POINT          # a midpoint closer than this to the border runs along it
_ONTO_STEPS = 8                  # Newton steps at most, in `translation_meeting`


# --- Parameter along a primitive: line 0..1, arc 0..sweep, circle 0..2π, other curves length along their discretization ---

def _polyline(seg) -> List[Point]:
    return [tuple(q[:2]) for q in seg.discretize(tolerance=CURVE_TOLERANCE)]


def _span(seg) -> float:
    if isinstance(seg, LineSeg):
        return 1.0
    if isinstance(seg, CircleSeg):
        return seg._sweep()
    pts = _polyline(seg)
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _param(seg, pt: Point) -> float:
    if isinstance(seg, LineSeg):
        dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
        l2 = dx * dx + dy * dy
        return 0.0 if l2 == 0 else ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2
    if is_full_circle(seg):
        return angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    if is_arc(seg):
        s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
        return 0.0 if s > seg._sweep() + (2 * math.pi - seg._sweep()) / 2 else s
    pts, run, best = _polyline(seg), 0.0, (float("inf"), 0.0)
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L == 0:
            continue
        t = max(0.0, min(1.0, ((pt[0] - a[0]) * (b[0] - a[0]) + (pt[1] - a[1]) * (b[1] - a[1])) / L ** 2))
        d = math.dist(pt, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if d < best[0]:
            best = (d, run + t * L)
        run += L
    return best[1]


def _at(seg, s: float) -> Point:
    if isinstance(seg, LineSeg):
        return (seg.start[0] + s * (seg.end[0] - seg.start[0]), seg.start[1] + s * (seg.end[1] - seg.start[1]))
    if isinstance(seg, CircleSeg):
        return point_on_circle(seg.center, seg.radius, seg.start_angle + (s if seg.ccw else -s))
    pts, run = _polyline(seg), 0.0
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L > 0 and run + L >= s:
            t = (s - run) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        run += L
    return pts[-1]


def _piece_length(seg, s0: float, s1: float) -> float:
    if isinstance(seg, LineSeg):
        return math.dist(seg.start, seg.end) * (s1 - s0)
    if isinstance(seg, CircleSeg):
        return seg.radius * (s1 - s0)
    return s1 - s0


def _ends(seg) -> Tuple[Point, Point]:
    return _at(seg, 0.0), _at(seg, _span(seg))


def _middle(seg) -> Point:
    return _at(seg, _span(seg) / 2)


def _piece(seg, s0: float, s1: float):
    """The stretch of `seg` between the parameters `s0` < `s1`, same primitive."""
    if isinstance(seg, LineSeg):
        return LineSeg(start=seg.start if s0 == 0.0 else _at(seg, s0),
                       end=seg.end if s1 == 1.0 else _at(seg, s1))
    if isinstance(seg, CircleSeg):
        sign = 1.0 if seg.ccw else -1.0
        return CircleSeg(center=seg.center, radius=seg.radius, start_angle=seg.start_angle + sign * s0,
                         end_angle=seg.start_angle + sign * s1, ccw=seg.ccw)
    piece = sub_segment(seg, _at(seg, s0), _at(seg, s1), _at(seg, (s0 + s1) / 2))
    if piece is None:
        raise ValueError(f"{type(seg).__name__} cannot be cut exactly")
    return piece


def _split(seg, points: Sequence[Point]) -> list:
    """`seg` split at the `points` lying on it, in its direction."""
    span = _span(seg)
    params = []
    for p in points:
        s = max(0.0, min(span, _param(seg, p)))
        if math.dist(_at(seg, s), p) <= _JOIN:      # only the points lying on it
            params.append(s)
    params.sort()
    if is_full_circle(seg):
        cuts = []
        for s in params:
            if not cuts or _piece_length(seg, cuts[-1], s) > _MIN_PIECE:
                cuts.append(s)
        if len(cuts) > 1 and _piece_length(seg, cuts[-1], cuts[0] + span) <= _MIN_PIECE:
            cuts.pop()
        if len(cuts) < 2:
            return [seg]
        return [_piece(seg, a, b) for a, b in zip(cuts, cuts[1:] + [cuts[0] + span])]
    bounds = [0.0]
    for s in params:
        if _piece_length(seg, bounds[-1], s) > _MIN_PIECE and _piece_length(seg, s, span) > _MIN_PIECE:
            bounds.append(s)
    bounds.append(span)
    return [_piece(seg, a, b) for a, b in zip(bounds, bounds[1:])]


def end_tangent(seg, at_end: bool) -> Tuple[float, float]:
    """Direction of travel of `seg` at its start or end: the exact derivative of
    the curve. A spline with doubled control points at the end has a null
    derivative there: then the first chord."""
    t0, t1 = seg.t_range
    dx, dy = seg.derivative_at(t1 if at_end else t0)
    if math.hypot(dx, dy) <= FLOAT_NOISE:
        pts = _polyline(seg)
        (ax, ay), (bx, by) = (pts[-2], pts[-1]) if at_end else (pts[0], pts[1])
        dx, dy = bx - ax, by - ay
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _signed_area(ring: Sequence) -> float:
    """Signed area on the primitives (Green): positive counter-clockwise."""
    return ring_moments(ring).area


def _reversed(ring: Sequence) -> list:
    return [s.reversed() for s in reversed(ring)]


def _polygon(ring: Sequence):
    polygon = build_polygon(list(ring), _POLYGON_TOLERANCE)
    if polygon is None:
        raise ValueError("the segments do not close a valid polygon")
    return polygon


def _side(polygon, pt: Point) -> int:
    """+1 inside, -1 outside, 0 on the border."""
    p = SPoint(pt)
    if polygon.exterior.distance(p) <= _ON_BORDER:
        return 0
    return 1 if polygon.contains(p) else -1


def _piece_side(polygon, piece) -> int:
    """Which side of `polygon` a piece is on (it does not change between two cuts):
    the midpoint, and if that falls on the border (a touch right there) the
    points at a third and two thirds. 0 only if it runs along it."""
    span = _span(piece)
    for f in (0.5, 1 / 3, 2 / 3):
        side = _side(polygon, _at(piece, span * f))
        if side:
            return side
    return 0


# --- A point on the contour ---

@dataclass(frozen=True)
class ContourPoint:
    """
    Where a point falls on a contour.

    kind:      "vertex" (two sides meet at an angle), "smooth" (they meet
               continuing one into the other: a blend), "edge" (in the
               middle of a side)
    segments:  indices into `segments`: two for a vertex (incoming,
               outgoing), one for a point in the middle of a side
    turn_deg:  how much the contour turns at the point, 0 if it does not turn
    concave:   True if the interior occupies more than half a turn around
               the point
    """
    point:    Point
    kind:     str
    segments: Tuple[int, ...]
    turn_deg: float
    concave:  bool


def point_on_contour(segments: Sequence, point: Point, *,
                     tolerance: float = DEFAULT_TOLERANCE) -> Optional[ContourPoint]:
    """
    Where `point` falls on the ring `segments` (head to tail): on a vertex,
    on a blend, in the middle of a side. None if it is farther than
    `tolerance` from the contour. A vertex is a blend if, along the longer of
    its two sides, one side strays less than `SAME_POINT` from the other's
    direction; concave or convex is told by the ring's direction, not
    by an inside/outside test.
    """
    segs = list(segments)
    n = len(segs)
    if n > 1:
        for k in range(n):
            if math.dist(_ends(segs[k])[0], point) <= tolerance:
                t_in, t_out = end_tangent(segs[k - 1], at_end=True), end_tangent(segs[k], at_end=False)
                cross = t_in[0] * t_out[1] - t_in[1] * t_out[0]
                turn = abs(math.atan2(cross, t_in[0] * t_out[0] + t_in[1] * t_out[1]))
                side = max(segment_length(segs[k - 1]), segment_length(segs[k]))
                if turn < math.pi / 2 and side * math.sin(turn) <= SAME_POINT:
                    return ContourPoint(point, "smooth", ((k - 1) % n, k), math.degrees(turn), False)
                concave = cross * _signed_area(segs) < 0
                return ContourPoint(point, "vertex", ((k - 1) % n, k), math.degrees(turn), concave)
    for i, seg in enumerate(segs):
        s = max(0.0, min(_span(seg), _param(seg, point)))
        if math.dist(_at(seg, s), point) <= tolerance:
            return ContourPoint(point, "edge", (i,), 0.0, False)
    return None


def nearest_point(segments: Sequence, point: Point) -> Point:
    """
    The point of the primitives `segments` nearest to `point`: also in the
    middle of a side, not only on a vertex. Exact on lines, arcs and circles;
    on every other curve refined on the true curve, to float precision.
    To know where it falls on the contour (vertex, blend, side) pass it to
    `point_on_contour`.
    """
    best: Optional[Point] = None
    for seg in segments:
        curve = None if isinstance(seg, (LineSeg, CircleSeg)) else _true_curve(seg)
        q = (_at(seg, max(0.0, min(_span(seg), _param(seg, point)))) if curve is None
             else _nearest_on_curve(seg, curve, point))
        if best is None or math.dist(q, point) < math.dist(best, point):
            best = q
    if best is None:
        raise ValueError("nearest_point(): `segments` is empty")
    return best


def _true_curve(seg):
    """(point at the parameter, start, end) of the true curve; None if the spline
    has no complete knot vector (the discretization remains)."""
    if not isinstance(seg, BSplineSeg):
        return (seg.point_at, *seg.t_range)
    if not seg._defined():
        return None
    return (seg._evaluate, *seg.t_range)


def _nearest_on_curve(seg, curve, point: Point) -> Point:
    """The point of the true curve nearest `point`: the parameter sampled as finely
    as the discretization, then golden section around the three nearest samples.
    The polyline alone is wrong by up to `CURVE_TOLERANCE`, and a contact is
    decided at 1e-6."""
    at, t0, t1 = curve
    n = max(len(_polyline(seg)) - 1, 1)
    ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    far = [math.dist(at(t), point) for t in ts]
    best: Optional[Point] = None
    for i in sorted(range(n + 1), key=far.__getitem__)[:3]:
        t, _ = golden_min(lambda s: math.dist(at(s), point), ts[max(i - 1, 0)], ts[min(i + 1, n)])
        q = at(t)
        if best is None or math.dist(q, point) < math.dist(best, point):
            best = q
    return best


def translation_meeting(constraints: Sequence[Tuple[Point, object, int]]) -> Optional[Point]:
    """(dx, dy) satisfying all the constraints `(point, curve, direction)` together,
    the one nearest zero: direction +1, the moved point falls on the fixed curve;
    −1, the fixed point falls on the moved curve. None if the translation is not
    unique (all constraints parallel) or none satisfies them all. Exact on lines,
    arcs and circles; on other curves within `CURVE_TOLERANCE`."""
    t = (0.0, 0.0)
    for _ in range(_ONTO_STEPS):
        rows, worst = [], 0.0
        for point, curve, sign in constraints:
            x = (point[0] + sign * t[0], point[1] + sign * t[1])
            foot = nearest_point([curve], x)
            worst = max(worst, math.dist(x, foot))
            n = _normal(curve, foot)
            rows.append((sign * n[0], sign * n[1], n[0] * (foot[0] - x[0]) + n[1] * (foot[1] - x[1])))
        if worst <= FLOAT_NOISE:
            return t
        mxx = sum(a * a for a, _, _ in rows)
        mxy = sum(a * b for a, b, _ in rows)
        myy = sum(b * b for _, b, _ in rows)
        vx = sum(a * r for a, _, r in rows)
        vy = sum(b * r for _, b, r in rows)
        det = mxx * myy - mxy * mxy
        if det <= (FLOAT_NOISE / SAME_POINT) ** 2:
            return None
        t = (t[0] + (vx * myy - vy * mxy) / det, t[1] + (mxx * vy - mxy * vx) / det)
    return None


def _normal(seg, foot: Point) -> Point:
    """The unit normal of `seg` at `foot`, a point of it."""
    if isinstance(seg, CircleSeg):
        dx, dy = foot[0] - seg.center[0], foot[1] - seg.center[1]
    else:
        s = _param(seg, foot)
        p, q = _at(seg, max(0.0, s - _JOIN)), _at(seg, min(_span(seg), s + _JOIN))
        dx, dy = -(q[1] - p[1]), q[0] - p[0]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


# --- A stretch cut by a region ---

def cut_by(segment, region: Sequence, *, keep: str = "outside") -> list:
    """
    The pieces of `segment` outside (`keep="outside"`) or inside
    (`keep="inside"`) the closed region `region`, in the direction of
    `segment`. A piece running along the region's border → ValueError:
    neither inside nor outside.
    """
    if keep not in ("outside", "inside"):
        raise ValueError(f"keep must be 'outside' or 'inside', got {keep!r}")
    polygon = _polygon(region)
    points = [p for r in region for p in intersections(segment, r)]
    want = -1 if keep == "outside" else 1
    out = []
    for piece in _split(segment, points):
        side = _piece_side(polygon, piece)
        if side == 0:
            raise ValueError("a piece runs along the border of the region")
        if side == want:
            out.append(piece)
    return out


# --- Contour minus region ---

def _chain(pieces: list, inside_left: Optional[bool] = None) -> List[list]:
    """Oriented pieces chained head-to-tail into closed rings. With `inside_left`
    (the region is to the left of the pieces, or to the right if False), at a
    node from which several pieces restart the one that narrows the region most
    is taken: two rings touching at a point stay two rings, not a figure eight."""
    left = list(pieces)
    rings = []
    while left:
        ring = [left.pop(0)]
        start = _ends(ring[0])[0]
        while math.dist(_ends(ring[-1])[1], start) > _JOIN:
            tail = _ends(ring[-1])[1]
            nexts = [i for i, p in enumerate(left) if math.dist(_ends(p)[0], tail) <= _JOIN]
            if not nexts:
                raise ValueError("the pieces do not close into a ring")
            k = nexts[0]
            if inside_left is not None and len(nexts) > 1:
                # angle from the direction of arrival, turned, to the outgoing one: the region
                # lies in that wedge, the narrowest wins
                tx, ty = end_tangent(ring[-1], at_end=True)
                back = math.atan2(-ty, -tx)
                sign = 1.0 if inside_left else -1.0

                def wedge(i):
                    ox, oy = end_tangent(left[i], at_end=False)
                    w = (sign * (back - math.atan2(oy, ox))) % (2 * math.pi)
                    # restarts tangent backwards (two curves touching): its region turns all the
                    # way round, the wedge is the full turn
                    turns_back = w < math.pi / 2 and segment_length(left[i]) * math.sin(w) <= SAME_POINT
                    return 2 * math.pi if turns_back else w
                k = min(nexts, key=wedge)
            ring.append(left.pop(k))
        rings.append(ring)
    return rings


def contour_minus(contour: Sequence, region: Sequence) -> List[list]:
    """
    The ring `contour` minus the closed region `region` (both rings of
    head-to-tail primitives): the rings of the border that remains. Each ring
    has the direction of `contour` if it is an outer contour, the opposite if
    it is a hole (the region entirely inside the contour). Empty list if the
    region covers the whole contour.

    As many rings as come out: a cut that detaches a piece gives two. Which
    to keep is the caller's decision. Borders running on top of each other →
    ValueError: there the result is not a cut point but a shared stretch.
    """
    contour, region = list(contour), list(region)
    # the region's border enters the result reversed relative to the contour:
    # `same` says whether the region, as it is, turns like the contour
    same = _signed_area(region) * _signed_area(contour) > 0
    contour_polygon, region_polygon = _polygon(contour), _polygon(region)
    points = []
    for c in contour:
        for r in region:
            for p in intersections(c, r):
                if all(math.dist(p, q) > _JOIN for q in points):
                    points.append(p)
    if len(points) < 2:
        # no crossing (a single touch does not change the shape)
        if _piece_side(region_polygon, contour[0]) == 1:
            return []
        if _piece_side(contour_polygon, region[0]) == 1:
            return [contour, _reversed(region) if same else list(region)]
        return [contour]
    kept = []
    for c in contour:
        for piece in _split(c, points):
            side = _piece_side(region_polygon, piece)
            if side == 0:
                raise ValueError("the contour runs along the border of the region")
            if side == -1:
                kept.append(piece)
    for r in region:
        for piece in _split(r, points):
            side = _piece_side(contour_polygon, piece)
            if side == 0:
                raise ValueError("the region runs along the border of the contour")
            if side == 1:
                kept.append(piece.reversed() if same else piece)
    return _chain(kept)


# --- Union of two contours ---

def _twin(piece, pieces: list) -> Tuple[Optional[int], bool]:
    """The index of the piece of `pieces` that covers `piece` (same ends, same
    midpoint) and whether it runs the same way; (None, False) if none."""
    a, b = _ends(piece)
    mid = _middle(piece)
    for i, q in enumerate(pieces):
        if math.dist(_middle(q), mid) > _ON_BORDER:
            continue
        qa, qb = _ends(q)
        if math.dist(qa, a) <= _JOIN and math.dist(qb, b) <= _JOIN:
            return i, True
        if math.dist(qa, b) <= _JOIN and math.dist(qb, a) <= _JOIN:
            return i, False
    return None, False


def _same_curve(a, b) -> bool:
    """`a` and `b` are the same spline or ellipse (even reversed): crossed on their
    discretizations they would give a point at every vertex. Overlapping lines
    and arcs give no points on their own."""
    if isinstance(a, (LineSeg, CircleSeg)) or isinstance(b, (LineSeg, CircleSeg)):
        return False
    return _twin(a, [b])[0] is not None


def contour_union(contour: Sequence, other: Sequence) -> List[list]:
    """
    The union of the rings `contour` and `other` (head-to-tail primitives):
    the rings of the resulting border, the largest first. An outer contour
    has the direction of `contour`, a hole (enclosed between the two) the
    opposite; two distant contours stay two rings.

    A shared border is the case that matters: where the two sit side by side
    the common stretch disappears, where they overlap it remains once. The
    common stretch must coincide piece by piece (same line, same circle, same
    curve between the same ends); a border running along the other without
    coinciding → ValueError. Where the border continues on the same line or
    the same circle there is no corner: the pieces become one again.
    """
    contour, other = list(contour), list(other)
    ccw = _signed_area(contour) > 0
    if (_signed_area(other) > 0) != ccw:
        other = _reversed(other)
    contour_polygon, other_polygon = _polygon(contour), _polygon(other)
    # cuts: the crossings, plus the ends of the other ring's sides, because two
    # overlapping stretches do not cross at a point (their own ends do not: the end
    # of a circle is a convention, not a node)
    crossings = [p for c in contour for o in other if not _same_curve(c, o)
                 for p in intersections(c, o)]
    cuts = [crossings + [q for o in other for q in _ends(o)],
            crossings + [q for c in contour for q in _ends(c)]]
    pieces = [(piece, _piece_side(other_polygon, piece))
              for c in contour for piece in _split(c, cuts[0])]
    other_pieces = [(piece, _piece_side(contour_polygon, piece))
                    for o in other for piece in _split(o, cuts[1])]
    on_border = [piece for piece, side in other_pieces if side == 0]
    kept = []
    for piece, side in pieces:
        if side == 0:
            k, same = _twin(piece, on_border)
            if k is None:
                raise ValueError("the contour runs along the other without coinciding")
            on_border.pop(k)
            if same:             # overlapping: the interior is on the same side
                kept.append(piece)
            continue             # side by side: the common stretch disappears
        if side == -1:
            kept.append(piece)
    if on_border:
        raise ValueError("the other contour runs along the first without coinciding")
    kept += [piece for piece, side in other_pieces if side == -1]
    rings = [merge_runs(ring, [None] * len(ring))[0] for ring in _chain(kept, inside_left=ccw)]
    return sorted(rings, key=lambda ring: -abs(_signed_area(ring)))


# --- Which contour contains a trace ---

def enclosing(tracks: Sequence[Sequence[Point]], outers: Sequence, tolerance: float) -> List[Optional[int]]:
    """For each trace (a sequence of points), the index in `outers` of the smallest
    polygon that wholly contains it, `None` if none. Only the outer border
    counts: a trace inside a hole is inside the part (a cross in the middle of a
    hole). The border is inside, within `tolerance`: a line from side to side
    belongs to the piece it crosses."""
    regions = []
    for i, outer in enumerate(outers):
        if outer is None or outer.is_empty:
            continue
        filled = Polygon(outer.exterior).buffer(tolerance)
        regions.append((filled.area, i, filled.bounds, prep(filled)))
    regions.sort(key=lambda r: r[0])
    found: List[Optional[int]] = []
    for pts in tracks:
        pts = list(pts)
        if not pts:
            found.append(None)
            continue
        shape = LineString(pts) if len(pts) > 1 else SPoint(pts[0])
        x0, y0, x1, y1 = shape.bounds
        found.append(next(
            (i for _, i, (a, b, c, d), region in regions
             if a <= x0 and b <= y0 and x1 <= c and y1 <= d and region.covers(shape)),
            None,
        ))
    return found
