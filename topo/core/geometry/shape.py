"""
topo/core/geometry/shape.py
----------------------------
Shape facts of a closed contour: circle, ellipse, stadium, rectangle,
polygon. A closed list: a shape has a name only if centre, length, width and
angle determine it; the rest is `polygon` or `other`. The rules read the
primitives as they are: a circle made of splines stays `other`. Pure
geometry, equally valid on `faces()` and `outlines()`. "circle" does not mean
hole: what that circle is is said by whoever reads the drawing or the
process. Facts between several contours (concentric circles, arcs around a
circle) are in `concentric.py`.
"""

from __future__ import annotations

from ...precision import ANGLE_BRACKET_DEG
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from shapely.geometry import Polygon

from .measure import Reach, chord_angle_deg, segment_length, SAME_POINT
from .numeric import golden_min
from ..primitives.line import LineSeg
from ..primitives.mathseg import segment_endpoints, segment_is_closed
from ..primitives.conics import CircleSeg, EllipseSeg, is_arc

Point = Tuple[float, float]


class ShapeKind(str, Enum):
    """
    The six shapes of `contour_shape`, a closed and stable list.
    Inherits from str: `kind == "circle"` works and the text prints the value.
    """
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    STADIUM = "stadium"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)


CIRCLE = ShapeKind.CIRCLE
ELLIPSE = ShapeKind.ELLIPSE
STADIUM = ShapeKind.STADIUM
RECTANGLE = ShapeKind.RECTANGLE
POLYGON = ShapeKind.POLYGON
OTHER = ShapeKind.OTHER



@dataclass(frozen=True)
class ContourShape:
    """
    kind:   a `ShapeKind` (circle | ellipse | stadium | rectangle | polygon | other)
    center: center (circle, ellipse, stadium, rectangle) or centroid (the rest)
    length: larger dimension — circle: diameter; ellipse: major axis;
            stadium: overall length
    width:  smaller dimension — circle: diameter; ellipse: minor axis;
            stadium: 2 × radius
    angle:  degrees [0, 180) of the long axis; None for the circle
    sides:  contour segments after recomposition
    """
    kind: ShapeKind
    center: Point
    length: float
    width: float
    angle: Optional[float]
    sides: int

    @property
    def diameter(self) -> Optional[float]:
        return self.length if self.kind == CIRCLE else None

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "center": list(self.center),
                "length": round(self.length, 4), "width": round(self.width, 4),
                "angle": None if self.angle is None else round(self.angle, 4),
                "sides": self.sides}


def contour_shape(item) -> Optional[ContourShape]:
    """
    Shape of a closed contour (`Contour`, or any object with `.segments`, or
    the list of segments). None if there are no segments or if, in sequence,
    they do not close into a ring.
    Consecutive segments on the same line or circle are first recomposed, so
    a side split by a node stays one side. Every measure of the shape agrees
    within `SAME_POINT`: a rectangle off by more is a polygon.
    """
    segments = list(getattr(item, "segments", item) or [])
    if not segments or not _closes(segments):
        return None
    segments, _ = merge_runs(segments, [None] * len(segments))
    for rule in (_circle, _ellipse, _stadium, _rectangle):
        shape = rule(segments)
        if shape is not None:
            return shape
    return _generic(segments)


def _closes(segments) -> bool:
    """The segments, in a row, make a ring: each starts where the previous ends
    (one way or the other) and the last returns to the first. An open piece
    has no shape."""
    if len(segments) == 1:
        return segment_is_closed(segments[0])
    ends = [segment_endpoints(s) for s in segments]
    for first, last in (ends[0], ends[0][::-1]):
        here = last
        for a, b in ends[1:]:
            if math.dist(here, a) <= SAME_POINT:
                here = b
            elif math.dist(here, b) <= SAME_POINT:
                here = a
            else:
                break
        else:
            if math.dist(here, first) <= SAME_POINT:
                return True
    return False


def _radius(seg) -> Optional[float]:
    """Radius of a piece of circle; an ellipse with axes equal within SAME_POINT is a circle."""
    if isinstance(seg, CircleSeg):
        return seg.radius
    if isinstance(seg, EllipseSeg) and abs(1.0 - seg.ratio) * math.hypot(*seg.major_axis) <= SAME_POINT:
        return math.hypot(*seg.major_axis)
    return None


def _circle(segments):
    radii = [_radius(s) for s in segments]
    if any(r is None for r in radii):
        return None
    s0, r0 = segments[0], radii[0]
    if any(abs(r - r0) > SAME_POINT or math.dist(s.center, s0.center) > SAME_POINT
           for s, r in zip(segments, radii)):
        return None
    sweep = sum(s._sweep() for s in segments)
    if abs(sweep - 2 * math.pi) * r0 > SAME_POINT:
        return None
    d = 2 * r0
    return ContourShape(CIRCLE, tuple(s0.center), d, d, None, len(segments))


def _ellipse(segments):
    """Pieces of the same ellipse (centre, semi-axes, axis direction) for a full turn."""
    if not all(isinstance(s, EllipseSeg) for s in segments):
        return None
    s0 = segments[0]
    a = math.hypot(*s0.major_axis)
    angle = math.degrees(math.atan2(s0.major_axis[1], s0.major_axis[0])) % 180
    for s in segments:
        if (abs(math.hypot(*s.major_axis) - a) > SAME_POINT or abs(s.ratio - s0.ratio) * a > SAME_POINT
                or math.dist(s.center, s0.center) > SAME_POINT
                or math.radians(_angle_diff(math.degrees(math.atan2(s.major_axis[1], s.major_axis[0])), angle)) * a > SAME_POINT):
            return None
    if abs(sum(s._sweep() for s in segments) - 2 * math.pi) * a > SAME_POINT:
        return None
    return ContourShape(ELLIPSE, tuple(s0.center), 2 * a, 2 * a * s0.ratio, angle, len(segments))


def _stadium(segments):
    if len(segments) != 4:
        return None
    k = 0 if is_arc(segments[0]) else 1
    a1, l1, a2, l2 = segments[k:] + segments[:k]
    if not (is_arc(a1) and is_arc(a2)
            and isinstance(l1, LineSeg) and isinstance(l2, LineSeg)):
        return None
    r = a1.radius
    if abs(a2.radius - r) > SAME_POINT:
        return None
    if any(abs(a._sweep() - math.pi) * r > SAME_POINT for a in (a1, a2)):
        return None
    axis = math.dist(a1.center, a2.center)
    if axis <= SAME_POINT:
        return None
    angle = chord_angle_deg(a1.center, a2.center)
    for line in (l1, l2):
        if abs(segment_length(line) - axis) > SAME_POINT:
            return None
        if math.radians(_angle_diff(chord_angle_deg(line.start, line.end), angle)) * segment_length(line) > SAME_POINT:
            return None
    center = ((a1.center[0] + a2.center[0]) / 2, (a1.center[1] + a2.center[1]) / 2)
    return ContourShape(STADIUM, center, axis + 2 * r, 2 * r, angle, 4)


def _rectangle(segments):
    if len(segments) != 4 or not all(isinstance(s, LineSeg) for s in segments):
        return None
    angles = [chord_angle_deg(s.start, s.end) for s in segments]
    lengths = [segment_length(s) for s in segments]
    # deviation from the right angle along the longer of the two sides
    if any(math.radians(abs(_angle_diff(angles[i], angles[i - 1]) - 90)) * max(lengths[i], lengths[i - 1]) > SAME_POINT
           for i in range(4)):
        return None
    if abs(lengths[0] - lengths[2]) > SAME_POINT or abs(lengths[1] - lengths[3]) > SAME_POINT:
        return None
    i = 0 if lengths[0] >= lengths[1] else 1
    xs = [s.start[0] for s in segments]
    ys = [s.start[1] for s in segments]
    center = (sum(xs) / 4, sum(ys) / 4)
    return ContourShape(RECTANGLE, center, lengths[i], lengths[1 - i], angles[i], 4)


def _generic(segments):
    kind = POLYGON if len(segments) >= 3 and all(isinstance(s, LineSeg) for s in segments) else OTHER
    points = [p for s in segments for p in s.discretize()]
    polygon = Polygon(points) if len(points) >= 3 else Polygon()
    box = polygon.minimum_rotated_rectangle
    if box.geom_type != "Polygon":
        return None
    # the polygon gives the starting orientation of the minimum rectangle; the
    # measures are the extent of the primitives, and for a curve the angle too is
    # refined on them
    corners = list(box.exterior.coords)[:4]
    theta = math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0])
    reaches = [Reach(s) for s in segments]
    if kind == OTHER:
        theta = _min_area_angle(reaches, theta)
    sides = [_extent_along(reaches, _angle_direction(theta)), _extent_along(reaches, _angle_direction(theta + math.pi / 2))]
    i = 0 if sides[0] >= sides[1] else 1
    angle = math.degrees(theta + i * math.pi / 2) % 180
    c = polygon.centroid
    return ContourShape(kind, (c.x, c.y), sides[i], sides[1 - i], angle, len(segments))


_ANGLE_BRACKET = math.radians(ANGLE_BRACKET_DEG)


def _min_area_angle(reaches, theta: float) -> float:
    """Angle of the minimum-area rectangle around the primitives, searched within
    ±1° of the angle of the inscribed polygon: the two differ only by the
    sagitta of the curved sides. On the refined extents also for splines: on the
    samples alone a nearly symmetric shape (area flat with the angle) picks
    another local minimum. It costs time, on purpose."""
    def area(t):
        return _extent_along(reaches, _angle_direction(t)) * _extent_along(reaches, _angle_direction(t + math.pi / 2))

    best, value = golden_min(area, theta - _ANGLE_BRACKET, theta + _ANGLE_BRACKET, iterations=30)
    return best if value < area(theta) else theta


def _angle_direction(t: float) -> Point:
    return (math.cos(t), math.sin(t))


def _extent_along(reaches, direction) -> float:
    """Extent of the set of segments along `direction`, on the primitives."""
    spans = [r(direction) for r in reaches]
    return max(hi for _lo, hi in spans) - min(lo for lo, _hi in spans)




def _angle_diff(a: float, b: float) -> float:
    """Difference between two directions modulo 180, in [0, 90]."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


# --- Recomposing a loop (used here and by outlines()) ---

def merge_runs(segments: list, styles: list):
    """Consecutive segments of a closed loop on the same circle (or line), in the
    same direction and with the same style, merged into one: the merge of
    `_normalize` removes duplicates before the cut, this recomposes afterwards
    what `split_at_crossings` split. A loop made wholly of arcs of the same
    circle comes back as a CircleSeg."""
    n = len(segments)
    if n < 2 or len(styles) != n:
        return segments, styles
    same = [_continues(segments[i - 1], styles[i - 1], segments[i], styles[i]) for i in range(n)]
    if all(same):
        s0 = segments[0]
        if is_arc(s0):
            return [CircleSeg(center=s0.center, radius=s0.radius)], [styles[0]]
        return segments, styles
    k = same.index(False)          # the loop restarts at the start of a stretch
    segments, styles, same = segments[k:] + segments[:k], styles[k:] + styles[:k], same[k:] + same[:k]
    out_s, out_st = [], []
    for seg, st, cont in zip(segments, styles, same):
        if cont:
            out_s[-1] = _joined(out_s[-1], seg)
        else:
            out_s.append(seg)
            out_st.append(st)
    return out_s, out_st


_MERGE_EPS = SAME_POINT   # mm — the step of the old node grid


def _continues(prev, prev_style, seg, style) -> bool:
    """Does `seg` continue `prev` on the same curve, in the same direction?"""
    if style != prev_style or type(seg) is not type(prev):
        return False
    if is_arc(seg):
        return (seg.ccw == prev.ccw and abs(seg.radius - prev.radius) < _MERGE_EPS
                and math.dist(seg.center, prev.center) < _MERGE_EPS)
    if isinstance(seg, LineSeg):
        (ax, ay), (bx, by) = prev.start, prev.end
        length = math.hypot(bx - ax, by - ay)
        if length < _MERGE_EPS:
            return False
        ex, ey = seg.end
        cross = (bx - ax) * (ey - ay) - (by - ay) * (ex - ax)
        dot = (bx - ax) * (ex - bx) + (by - ay) * (ey - by)
        return abs(cross) / length < _MERGE_EPS and dot > 0
    return False


def _joined(prev, seg):
    if is_arc(prev):
        # the sweeps add up: `seg.end_angle` alone may be the start angle of `prev` up
        # to a turn (an arc through 0)
        sweep = prev._sweep() + seg._sweep()
        return CircleSeg(center=prev.center, radius=prev.radius, start_angle=prev.start_angle,
                      end_angle=prev.start_angle + (sweep if prev.ccw else -sweep), ccw=prev.ccw)
    return LineSeg(start=prev.start, end=seg.end)
