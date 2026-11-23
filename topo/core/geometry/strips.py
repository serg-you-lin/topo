"""
topo/core/geometry/strips.py
-----------------------------
A strip of given width between two closed contours, and the open contours
where the strip touches them. Pure geometry: head-to-tail rings of
primitives (`contour.segments`), no hierarchy. Which contours face each
other and which regions stay detached is said by `topo.tools.strips`, which
reads a cluster's hierarchy.

Cuts fall on the exact points of `intersections`, the pieces stay primitives
of the same type (a cut arc is an arc).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points

from ..primitives.line import LineSeg
from ..primitives.conics import CircleSeg
from .intersections import CURVE_TOLERANCE, intersections
from .measure import unit_vector
from .regions import (
    _JOIN, _at, _ends, _param, _polygon, _polyline, _side, _signed_area, _span, _split,
    nearest_point,
)

Point = Tuple[float, float]

_TOUCH = 10 * CURVE_TOLERANCE   # a meeting closer than this to an end of the side is its attachment


# --- Distance between two contours ---

@dataclass(frozen=True)
class Gap:
    """The minimum distance between two boundaries and the closest pair of
    points, one on each (`on_a` on the first, `on_b` on the second)."""
    distance: float
    on_a:     Point
    on_b:     Point


def _ring_points(ring: Sequence) -> List[Point]:
    pts = [q for seg in ring for q in _polyline(seg)]
    return pts + pts[:1]


def gap(a, b) -> Gap:
    """
    The minimum distance between the boundaries `a` and `b` and the closest
    pair of points. Each is a `Contour`, any object with `.segments`, or a
    list of primitives (a ring, or open pieces). Boundaries that touch or
    cross give 0 within float noise (compare with a small threshold,
    1e-6 mm, never with `== 0`); one inside the other gives the distance between the two
    boundaries, not 0. Exact on lines, arcs and circles; on splines and
    ellipses within `CURVE_TOLERANCE`.
    """
    a = list(getattr(a, "segments", a))
    b = list(getattr(b, "segments", b))
    if not a or not b:
        raise ValueError("gap(): empty boundary")
    pa, pb = nearest_points(LineString(_ring_points(a)), LineString(_ring_points(b)))
    return refine_gap(a, b, (pa.x, pa.y), (pb.x, pb.y))


def refine_gap(a: Sequence, b: Sequence, on_a: Point, on_b: Point) -> Gap:
    """The nearest pair between the primitives `a` and `b` (rings or open pieces),
    starting from `on_a`, `on_b` taken on the discretizations: alternating
    projections with `nearest_point` until they stop."""
    for _ in range(20):
        new_a = nearest_point(a, on_b)
        new_b = nearest_point(b, new_a)
        moved = math.dist(new_a, on_a) + math.dist(new_b, on_b)
        on_a, on_b = new_a, new_b
        if moved < 1e-12:
            break
    return Gap(math.dist(on_a, on_b), on_a, on_b)


# ---------------------------------------------------------------------------
# La striscia
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Strip:
    """A strip between the contours `a` and `b`. `a_at`/`b_at`: where its midline
    touches the two contours. `a_cuts`/`b_cuts`: where the two sides touch them,
    in the same order as `sides` (side `i` runs from `a_cuts[i]` to `b_cuts[i]`).
    The stretch of `a` between the two `a_cuts` that passes through `a_at` is the
    one covered by the strip, the same for `b`."""
    a_at:   Point
    b_at:   Point
    a_cuts: Tuple[Point, Point]
    b_cuts: Tuple[Point, Point]
    sides:  Tuple[LineSeg, LineSeg]

    @property
    def outline(self) -> List[LineSeg]:
        """The quadrilateral of the four cuts, as a ring of sides."""
        (a0, a1), (b0, b1) = self.a_cuts, self.b_cuts
        return [LineSeg(start=a0, end=b0), LineSeg(start=b0, end=b1),
                LineSeg(start=b1, end=a1), LineSeg(start=a1, end=a0)]


def _unit(v: Point) -> Point:
    u = unit_vector(v)
    if u is None:
        raise ValueError("zero direction")
    return u


def _tangent_at(ring: Sequence, point: Point) -> Point:
    """Direction of travel of the ring at its point nearest `point`."""
    seg = min(ring, key=lambda s: math.dist(nearest_point([s], point), point))
    if isinstance(seg, LineSeg):
        return _unit((seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]))
    if isinstance(seg, CircleSeg):
        r = _unit((point[0] - seg.center[0], point[1] - seg.center[1]))
        return (-r[1], r[0]) if seg.ccw else (r[1], -r[0])
    span = _span(seg)
    s = max(0.0, min(span, _param(seg, point)))
    h = span * 1e-4
    p0, p1 = _at(seg, max(0.0, s - h)), _at(seg, min(span, s + h))
    return _unit((p1[0] - p0[0], p1[1] - p0[1]))


def _normal_toward(ring: Sequence, point: Point, other: Sequence) -> Point:
    """Normal to the ring `ring` at its point `point`, from the side where the ring
    `other` is: inwards if `ring` contains it, outwards otherwise. The side is
    read from the direction of travel (signed area), exact even where the contour
    is thin or concave."""
    t = _tangent_at(ring, point)
    right = (t[1], -t[0])
    outward = right if _signed_area(ring) > 0 else (-right[0], -right[1])
    inside = _side(_polygon(ring), _ends(other[0])[0]) > 0
    return (-outward[0], -outward[1]) if inside else outward


def _hits(ring: Sequence, line: LineSeg) -> List[Point]:
    return [p for seg in ring for p in intersections(line, seg)]


def _ray_hits(ring: Sequence, start: Point, direction: Point, length: float) -> List[Point]:
    """Where the ray from `start` towards `direction` meets `ring`, nearest first."""
    line = LineSeg(start=start, end=(start[0] + direction[0] * length, start[1] + direction[1] * length))
    hits = [p for p in _hits(ring, line) if math.dist(p, start) > _TOUCH]
    return sorted(hits, key=lambda p: math.dist(p, start))


def _size(*rings: Sequence) -> float:
    pts = [q for ring in rings for q in _ring_points(ring)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def strip_between(a: Sequence, b: Sequence, at: Point, width: float,
                  obstacles: Sequence[Sequence] = (), placed: Sequence[Strip] = ()) -> Strip:
    """The strip of width `width` between the rings `a` and `b`, at the point `at`
    chosen by the caller. `at` is projected on the nearer of the two rings and the
    midline starts there perpendicular to the ring, from the side where the other
    is; if in that direction the other is not there, it goes towards its nearest
    point. Never just the nearest point: from a straight side it can be to one
    side, and the strip would run along the side instead of leaving it. The two
    sides are the parallels at `±width/2`, cut where they meet `a` and `b` near
    the midline.

    Rejected (`ValueError`, with the reason) if a side does not meet `a` or `b`,
    if a side crosses a ring of `obstacles` or `a` or `b` again, if a ring of
    `obstacles` is inside the strip, if it touches a strip of `placed`. The
    obstacles are the other facing contours (`topo.tools.strips.facing_boundaries`)."""
    if width <= 0:
        raise ValueError(f"width must be > 0, got {width}")
    a, b = list(a), list(b)
    length = 4 * _size(a, b) + 4 * width
    on_a, on_b = nearest_point(a, at), nearest_point(b, at)
    flip = math.dist(at, on_b) < math.dist(at, on_a)
    start_ring, end_ring, start = (b, a, on_b) if flip else (a, b, on_a)

    hits = _ray_hits(end_ring, start, _normal_toward(start_ring, start, end_ring), length)
    end = hits[0] if hits else nearest_point(end_ring, start)
    direction = _unit((end[0] - start[0], end[1] - start[1]))
    across = (-direction[1] * width / 2, direction[0] * width / 2)

    def cut(ring: Sequence, near: Point, sign: float, which: str) -> Point:
        o = (sign * across[0], sign * across[1])
        line = LineSeg(start=(near[0] + o[0] - direction[0] * length, near[1] + o[1] - direction[1] * length),
                       end=(near[0] + o[0] + direction[0] * length, near[1] + o[1] + direction[1] * length))
        found = _hits(ring, line)
        if not found:
            raise ValueError(f"a side of the strip {width} wide does not meet {which}")
        return nearest_point(ring, min(found, key=lambda p: math.dist(p, near)))

    start_cuts = (cut(start_ring, start, 1.0, "il contorno di partenza"),
                  cut(start_ring, start, -1.0, "il contorno di partenza"))
    end_cuts = (cut(end_ring, end, 1.0, "il contorno d'arrivo"), cut(end_ring, end, -1.0, "il contorno d'arrivo"))
    if flip:
        found = Strip(a_at=end, b_at=start, a_cuts=end_cuts, b_cuts=start_cuts,
                      sides=(LineSeg(start=end_cuts[0], end=start_cuts[0]),
                             LineSeg(start=end_cuts[1], end=start_cuts[1])))
    else:
        found = Strip(a_at=start, b_at=end, a_cuts=start_cuts, b_cuts=end_cuts,
                      sides=(LineSeg(start=start_cuts[0], end=end_cuts[0]),
                             LineSeg(start=start_cuts[1], end=end_cuts[1])))
    _refuse_crossings(found, a, b, obstacles, placed)
    return found


def _refuse_crossings(strip: Strip, a: Sequence, b: Sequence, obstacles: Sequence[Sequence],
                      placed: Sequence[Strip]) -> None:
    for side in strip.sides:
        if math.dist(side.start, side.end) <= _TOUCH:
            raise ValueError("a side of the strip has zero length: the two contours touch there")
        ends = (side.start, side.end)
        for name, ring in [("di nuovo un suo contorno", a), ("di nuovo un suo contorno", b),
                           *(("un altro contorno", r) for r in obstacles),
                           *(("un'altra striscia", s.outline) for s in placed)]:
            if any(min(math.dist(p, e) for e in ends) > _TOUCH for p in _hits(ring, side)):
                raise ValueError(f"the strip crosses {name}")
    quad = Polygon([s.start for s in strip.outline])
    for ring in obstacles:
        if quad.contains(LineString(_ring_points(ring)).interpolate(0)):
            raise ValueError("another contour lies inside the strip")
    for other in placed:
        if quad.intersects(Polygon([s.start for s in other.outline])):
            raise ValueError("the strip overlaps another strip")


# --- An open contour where the strips touch it ---

def open_ring(ring: Sequence, covered: Sequence[Tuple[Point, Point, Point]]) -> List[list]:
    """The ring `ring` without the covered stretches: each is `(end, end, point)`,
    the two ends on the ring and a point of the stretch between them (for a strip:
    `a_cuts` and `a_at`). Returns the open chains of primitives that remain, in
    the ring's direction. `ValueError` if two stretches overlap or an end is not
    on the ring.
    """
    ring = list(ring)
    if not covered:
        return [ring]
    cuts = [nearest_point(ring, p) for c in covered for p in c[:2]]
    for c, p in zip([p for c in covered for p in c[:2]], cuts):
        if math.dist(c, p) > _TOUCH:
            raise ValueError("an end of a covered stretch is not on the ring")
    pieces = [piece for seg in ring for piece in _split(seg, cuts)]

    def at_cut(p: Point) -> bool:
        return any(math.dist(p, c) <= _JOIN for c in cuts)

    first = next((k for k, piece in enumerate(pieces) if at_cut(_ends(piece)[0])), None)
    if first is None:
        raise ValueError("the covered stretches do not cut the ring")
    pieces = pieces[first:] + pieces[:first]
    chains: List[list] = []
    for piece in pieces:
        if not chains or at_cut(_ends(piece)[0]):
            chains.append([piece])
        else:
            chains[-1].append(piece)

    dropped = [0] * len(covered)
    kept = []
    for chain in chains:
        ends = (_ends(chain[0])[0], _ends(chain[-1])[1])
        under = None
        for k, (c0, c1, inside) in enumerate(covered):
            same = ({_snap(ends[0], cuts), _snap(ends[1], cuts)} == {_snap(c0, cuts), _snap(c1, cuts)})
            if same and math.dist(nearest_point(chain, inside), inside) <= _TOUCH:
                under = k
        if under is None:
            kept.append(chain)
        else:
            dropped[under] += 1
    if any(n != 1 for n in dropped):
        raise ValueError("two covered stretches overlap on the ring")
    return kept


def _snap(p: Point, cuts: Sequence[Point]) -> int:
    """Index of the first cut that coincides with `p` (two coinciding cuts count as one).
    """
    k = min(range(len(cuts)), key=lambda i: math.dist(p, cuts[i]))
    return next(i for i in range(len(cuts)) if math.dist(cuts[i], cuts[k]) <= _JOIN)
