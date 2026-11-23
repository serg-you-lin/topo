"""
topo/core/geometry/measure.py
------------------------------
Measures of primitives and traces: length and angle of a segment, vertices
and type of an open trace.
"""

from ...precision import FLOAT_NOISE, SAME_POINT
import math
from typing import Optional, Tuple, List

from shapely.geometry import LineString, box

from ..primitives.line import LineSeg
from ..primitives.spline import BSplineSeg
from ..primitives.mathseg import MathSeg
from ..primitives.clothoid import ClothoidSeg
from ..primitives.conics import HyperbolaSeg, ParabolaSeg, CircleSeg, EllipseSeg
from .numeric import golden_min

Point = Tuple[float, float]


# FLOAT_NOISE e SAME_POINT vivono in topo/precision.py


def noise_runs(items: list, together) -> list:
    """`items` (already sorted) split where two neighbours are not `together`:
    "equal within the noise" chains along the sorted values, so it does not
    depend on input order."""
    runs = []
    for item in items:
        if runs and together(runs[-1][-1], item):
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


# Open traces — vertices / length / type from native segments.
# An open trace (bending line, engraving, unclosed fragment) in the model is a
# list of native segments (LineSeg / CircleSeg / BSplineSeg / EllipseSeg).
# `pts`, `length`, `shape_type` are values DERIVED from those segments: here,
# not stored on the model.

def track_points(segments, *, tolerance: Optional[float] = None) -> List[Point]:
    """
    Vertices of an open trace as a chain of native segments.

    Concatenates the `seg.discretize()` of each segment, deduplicating the
    vertex shared at the junction between one segment and the next.
    """
    pts: List[Point] = []
    for seg in segments or []:
        seg_pts = seg.discretize() if tolerance is None else seg.discretize(tolerance=tolerance)
        if not seg_pts:
            continue
        if pts and math.dist(pts[-1], seg_pts[0]) < 1e-9:
            pts.extend(seg_pts[1:])
        else:
            pts.extend(seg_pts)
    return pts


def track_length(pts) -> float:
    """Total length of a polyline (sum of the chords)."""
    return sum(
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    )


# --- Length and angle of ONE native primitive — never stored on the model, always derived ---

def segment_length(segment) -> float:
    """
    Real length of a single native primitive. A line and a circle have a
    closed formula, a clothoid its arc-length parameter; every other curve
    the integral of its exact speed |P'(t)|. A spline whose knots do
    not define it falls back to the polyline of `discretize()`.
    """
    if isinstance(segment, LineSeg):
        return math.hypot(segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])
    if isinstance(segment, CircleSeg):
        return segment.radius * segment._sweep()
    if isinstance(segment, ClothoidSeg):
        return abs(segment.end_param - segment.start_param)   # the parameter is the arc length
    if isinstance(segment, BSplineSeg) and not segment._defined():
        return track_length(segment.discretize())
    from .integrals import curve_length   # integrals sits above measure
    return curve_length(segment)


def length_inside(segment, bounds: Tuple[float, float, float, float]) -> float:
    """
    How much of `segment` (any native primitive) lies inside the rectangle
    `bounds` = (xmin, ymin, xmax, ymax), border included. Curves are measured
    on the `discretize()` polyline.
    """
    pts = segment.discretize()
    if len(pts) < 2:
        return 0.0
    return LineString(pts).intersection(box(*bounds)).length


def longest_segment(segments) -> Tuple[Optional[object], float]:
    """`(segment, length)` of the longest segment in `segments` — `(None, 0.0)` if
    the list is empty. Linear comparison via `segment_length`."""
    best_seg, best_len = None, 0.0
    for seg in segments or []:
        length = segment_length(seg)
        if best_seg is None or length > best_len:
            best_seg, best_len = seg, length
    return best_seg, best_len


def chord_angle_deg(a: Point, b: Point) -> float:
    """
    Angle (degrees, 0-180°) of the chord from `a` to `b`. Modulo 180 because
    a line has no direction of its own (`a->b` and `b->a` are the same
    orientation).
    """
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def unit_vector(v: Point) -> Optional[Point]:
    """`v` with length 1; None if it is null or not finite (then it has no
    direction). What to do with None is the caller's call."""
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n) if n > 0 and math.isfinite(n) else None


# Extent of a primitive along a direction — on the curve, not on the polygon.
# The polygon of discretize() is inscribed: its projection is shorter than the
# curve by up to 2·tol. Here (min, max) of p·d on the true curve.

def segment_reach(segment, direction: Point) -> Tuple[float, float]:
    """(min, max) of the projection of the points of `segment` on the unit vector
    `direction`. Exact for line, arc, circle, ellipse (extremes in closed form);
    for the B-spline by certificate on the Bézier pieces, refined to machine
    precision. For many directions on the same segment use `Reach`: the pieces
    are computed once."""
    return Reach(segment)(direction)


class Reach:
    """`segment_reach` of a fixed segment, for many directions."""

    def __init__(self, segment):
        self.segment = segment

    def __call__(self, direction: Point) -> Tuple[float, float]:
        dx, dy = direction
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm

        def dot(p):
            return p[0] * dx + p[1] * dy

        segment = self.segment
        if isinstance(segment, LineSeg):
            a, b = dot(segment.start), dot(segment.end)
            return min(a, b), max(a, b)
        if isinstance(segment, EllipseSeg):
            # the circle too: p·d = c·d + A·cos t + B·sin t, extremes at t = atan2(B, A) and + π
            mx, my = segment.major_axis
            a_coef = mx * dx + my * dy
            b_coef = segment.ratio * (-my * dx + mx * dy)
            t0 = math.atan2(b_coef, a_coef)
            sweep = segment._sweep()
            values = [dot(segment._point_at(segment.start_param)),
                      dot(segment._point_at(segment.end_param))]
            values += [dot(segment._point_at(t)) for t in (t0, t0 + math.pi)
                       if _on_sweep(segment.start_param, segment.ccw, sweep, t)]
            return min(values), max(values)
        if isinstance(segment, BSplineSeg):
            return self._spline(dot)
        if isinstance(segment, (ParabolaSeg, HyperbolaSeg)):
            return self._conic(dot, dx, dy)
        if isinstance(segment, MathSeg):
            # a formula: on the polygon within SAME_POINT
            values = [dot(p) for p in segment.discretize(tolerance=SAME_POINT)]
            return min(values), max(values)
        raise TypeError(f"unsupported primitive: {type(segment).__name__}")

    def _conic(self, dot, dx: float, dy: float) -> Tuple[float, float]:
        """Parabola: p·d = V·d + s·(n·d) + s²/(4f)·(u·d), extreme at s = −2f·(n·d)/(u·d).
        Hyperbola: p·d = C·d + cosh s·A + sinh s·B, extreme where tanh s = −B/A (if |B| < |A|)."""
        seg = self.segment
        lo, hi = sorted((seg.start_param, seg.end_param))
        if isinstance(seg, ParabolaSeg):
            f, u, n = seg._frame()
            ud, nd = u[0] * dx + u[1] * dy, n[0] * dx + n[1] * dy
            inner = [-2 * f * nd / ud] if ud != 0 else []
        else:
            (mx, my), (px, py) = seg.major_axis, seg._minor()
            a_coef, b_coef = mx * dx + my * dy, px * dx + py * dy
            inner = [math.atanh(-b_coef / a_coef)] if abs(b_coef) < abs(a_coef) else []
        values = [dot(seg._point(lo)), dot(seg._point(hi))] + [dot(seg._point(s)) for s in inner if lo < s < hi]
        return min(values), max(values)

    def _spline(self, dot) -> Tuple[float, float]:
        """The extremes by certificate on the Bézier pieces: a linear function on the
        control-point hull has its extreme at one of them, so no piece behind the
        best can win. Then the golden section around the winner, to machine precision."""
        seg = self.segment
        out = []
        for sign in (1.0, -1.0):
            t, lo, hi = seg._minimize(lambda q: -sign * dot(q), lambda ctrl: min(-sign * dot(q) for q in ctrl))
            _t, refined = golden_min(lambda u: -sign * dot(seg._evaluate(u)), lo, hi, iterations=40)
            out.append(sign * max(sign * dot(seg._evaluate(t)), -refined))
        return out[1], out[0]


def _on_sweep(start: float, ccw: bool, sweep: float, t: float) -> bool:
    """True if the angle `t` falls in the interval walked from `start` for `sweep`."""
    offset = ((t - start) if ccw else (start - t)) % (2 * math.pi)
    return offset <= sweep + 1e-12


def within_diameter(points, limit: float) -> bool:
    """True if every pair of `points` is at most `limit` apart: the diameter of the
    set, which does not depend on the frame (the bbox diagonal does). The
    diagonal lies between the diameter and the diameter times √2."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    if diagonal <= limit:
        return True
    if diagonal > 2 * limit:
        return False
    return all(math.dist(a, b) <= limit for i, a in enumerate(points) for b in points[i + 1:])


def reach(limit: float) -> float:
    """How far a topo threshold reaches: `limit` included, up to the double noise.
    Every comparison with a reading's tolerance goes through here."""
    return limit + FLOAT_NOISE

