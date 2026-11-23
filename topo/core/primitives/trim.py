"""
topo/core/primitives/trim.py
-----------------------------
The piece of a primitive between two of its points: the same curve, shortened —
same centre and axes for a circle or an ellipse, the same polynomial pieces
for a B-spline (knot insertion, Piegl & Tiller A5.1), not an approximation.

Pure: primitives only, no format.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Optional, Tuple

from ...precision import FLOAT_NOISE
from .line import LineSeg
from .mathseg import Point
from .spline import BSplineSeg, _insert_to_degree
from .conics import CircleSeg, EllipseSeg, HyperbolaSeg, ParabolaSeg
from .clothoid import ClothoidSeg
from .formula import FormulaSeg
from .minimize import certified_min, point_split

_TWO_PI = 2 * math.pi
_REFINE_STEPS = 60     # ternary-search steps on the parameter


def sub_segment(seg, a: Point, b: Point, via: Point):
    """
    The piece of `seg` from `a` to `b` (points on the curve, or within a
    tolerance of it), walked from `a` towards `b`. `via` is a point inside the
    piece: needed only on a closed curve (circle, full ellipse) to tell which
    way to turn. None if `seg` cannot be cut exactly (periodic spline, or one
    without a knot vector).
    """
    if isinstance(seg, LineSeg):
        return LineSeg(start=_on_line(seg, a), end=_on_line(seg, b))
    if isinstance(seg, (CircleSeg, EllipseSeg)):
        return _sub_angular(seg, a, b, via)
    if isinstance(seg, BSplineSeg):
        return _sub_spline(seg, a, b, via)
    if isinstance(seg, (ParabolaSeg, HyperbolaSeg)):
        return _sub_open_conic(seg, a, b)
    if isinstance(seg, (FormulaSeg, ClothoidSeg)):
        return _sub_interval(seg, a, b)
    return None


def _sub_interval(seg, a: Point, b: Point):
    """The same curve over a shorter interval: from the parameter of `a` to that of `b`."""
    t0, t1 = seg.t_range
    sign = 1.0 if seg.end_param >= seg.start_param else -1.0
    ta, tb = (_curve_param(seg, p, t0, t1) for p in (a, b))
    return replace(seg, start_param=seg.start_param + sign * ta, end_param=seg.start_param + sign * tb)


def _sub_open_conic(seg, a: Point, b: Point):
    """Parabola and hyperbola are open: the piece runs from the parameter of `a`
    to that of `b`, inside the original. Parabola: s = (p − V)·n; hyperbola:
    s = asinh((p − C)·N / |N|²), N the second axis."""
    lo, hi = sorted((seg.start_param, seg.end_param))

    def param(pt: Point) -> float:
        if isinstance(seg, ParabolaSeg):
            _, _, n = seg._frame()
            s = (pt[0] - seg.vertex[0]) * n[0] + (pt[1] - seg.vertex[1]) * n[1]
        else:
            nx, ny = seg._minor()
            b2 = nx * nx + ny * ny
            # (p − C)·N = sinh(s)·|N|², because M ⟂ N
            s = math.asinh(((pt[0] - seg.center[0]) * nx + (pt[1] - seg.center[1]) * ny) / b2)
        return min(max(s, lo), hi)

    return type(seg)(*_fields_before_params(seg), param(a), param(b))


def _fields_before_params(seg) -> tuple:
    """The fields that fix the curve, without the parameter interval."""
    if isinstance(seg, ParabolaSeg):
        return (seg.vertex, seg.focus)
    return (seg.center, seg.major_axis, seg.ratio)


# ---------------------------------------------------------------------------
# Line
# ---------------------------------------------------------------------------

def _on_line(seg: LineSeg, pt: Point) -> Point:
    """Projection of `pt` on the line, between its two ends."""
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return seg.start
    t = max(0.0, min(1.0, ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2))
    return (seg.start[0] + t * dx, seg.start[1] + t * dy)


# ---------------------------------------------------------------------------
# Circle and ellipse (a circle is an ellipse): an angular parameter walked one way
# ---------------------------------------------------------------------------

def _sub_angular(seg, a: Point, b: Point, via: Point):
    start, sweep, ccw = seg.start_param, seg._sweep(), seg.ccw
    sign = 1.0 if ccw else -1.0
    closed = sweep == _TWO_PI   # the full turn, like `.full`

    def offset(pt: Point) -> float:
        """How far one walks from `start`, the curve's way, to `pt`."""
        return (sign * (_angle_of(seg, pt) - start)) % _TWO_PI

    if closed:
        oa = offset(a)
        ob = (offset(b) - oa) % _TWO_PI or _TWO_PI
        forward = (offset(via) - oa) % _TWO_PI <= ob
        lo = start + sign * oa
        hi = lo + sign * ob if forward else lo - sign * (_TWO_PI - ob)
        return _angular(seg, lo, hi, ccw if forward else not ccw)
    oa, ob = _clamp(offset(a), sweep), _clamp(offset(b), sweep)
    return _angular(seg, start + sign * oa, start + sign * ob, ccw if oa <= ob else not ccw)


def _clamp(offset: float, sweep: float) -> float:
    """A point just past an end (within tolerance) is on that end."""
    if offset <= sweep:
        return offset
    return sweep if offset - sweep < _TWO_PI - offset else 0.0


def _angle_of(seg, pt: Point) -> float:
    """Angle (or ellipse parameter) of `pt` seen from the curve's centre."""
    dx, dy = pt[0] - seg.center[0], pt[1] - seg.center[1]
    if isinstance(seg, CircleSeg):
        return math.atan2(dy, dx)
    mx, my = seg.major_axis
    nx, ny = -my * seg.ratio, mx * seg.ratio
    return math.atan2((dx * nx + dy * ny) / (nx * nx + ny * ny),
                      (dx * mx + dy * my) / (mx * mx + my * my))


def _angular(seg, lo: float, hi: float, ccw: bool):
    if isinstance(seg, CircleSeg):
        return CircleSeg(center=seg.center, radius=seg.radius, start_angle=lo, end_angle=hi, ccw=ccw)
    return EllipseSeg(center=seg.center, major_axis=seg.major_axis, ratio=seg.ratio,
                      start_param=lo, end_param=hi, ccw=ccw)


# ---------------------------------------------------------------------------
# B-spline
# ---------------------------------------------------------------------------

def _sub_spline(seg: BSplineSeg, a: Point, b: Point, via: Point) -> Optional[BSplineSeg]:
    if seg.periodic or not seg.knots or len(seg.control_points) < 2:
        return None
    p = seg.degree
    lo, hi = seg.knots[p], seg.knots[-(p + 1)]
    ta, tb = _spline_param(seg, a, lo, hi), _spline_param(seg, b, lo, hi)
    # an end on the seam of a closed spline has two parameters, lo and hi,
    # equally good: the one that puts `via` inside the piece wins, as on the circle
    seam_a, seam_b = _on_seam(seg, a, lo, hi), _on_seam(seg, b, lo, hi)
    if seam_a and seam_b:
        ta, tb = lo, hi
    elif seam_a or seam_b:
        tv = _spline_param(seg, via, lo, hi)
        if seam_a:
            ta = lo if tv < tb else hi
        else:
            tb = lo if tv < ta else hi
    if ta == tb:
        return None
    reverse = ta > tb
    if reverse:
        ta, tb = tb, ta
    weights = seg.weights or [1.0] * len(seg.control_points)
    cpw = [(x * w, y * w, w) for (x, y), w in zip(seg.control_points, weights)]
    knots = list(seg.knots)
    for t in (ta, tb):
        knots, cpw = _insert_to_degree(p, knots, cpw, t)
    last_a = max(i for i, k in enumerate(knots) if k == ta)
    inner = [k for k in knots if ta < k < tb]
    sub_knots = [ta] * (p + 1) + inner + [tb] * (p + 1)
    first = last_a - p
    sub_cpw = cpw[first:first + len(sub_knots) - p - 1]
    out = BSplineSeg(
        degree=p,
        control_points=[(x / w, y / w) for x, y, w in sub_cpw],
        knots=sub_knots,
        weights=[w for _, _, w in sub_cpw] if seg.weights else None,
    )
    return out.reversed() if reverse else out


def _on_seam(seg: BSplineSeg, pt: Point, lo: float, hi: float) -> bool:
    """`pt` is on both ends of the spline at once: at the same distance from both
    within FLOAT_NOISE, and on them."""
    d_lo, d_hi = math.dist(seg._evaluate(lo), pt), math.dist(seg._evaluate(hi), pt)
    return abs(d_lo - d_hi) <= FLOAT_NOISE and max(d_lo, d_hi) <= FLOAT_NOISE


def _spline_param(seg: BSplineSeg, pt: Point, lo: float, hi: float) -> float:
    """Parameter of the spline point nearest `pt`: the right branch by
    certificate on the Bézier pieces, then refined."""
    t, left, right = seg._minimize(lambda q: math.dist(q, pt), lambda ctrl: _to_box(ctrl, pt))
    return _refine(seg._evaluate, pt, t, left, right, lo, hi)


def _to_box(corners: List[Point], pt: Point) -> float:
    """Distance from `pt` to the box of the points: a lower bound of the distance
    to every point of their hull. No points, no bound: 0."""
    if not corners:
        return 0.0
    xs, ys = [q[0] for q in corners], [q[1] for q in corners]
    return math.hypot(max(min(xs) - pt[0], 0.0, pt[0] - max(xs)),
                      max(min(ys) - pt[1], 0.0, pt[1] - max(ys)))


def _curve_param(seg, pt: Point, lo: float, hi: float) -> float:
    """Parameter in [lo, hi] of the point of a clothoid or a formula nearest
    `pt`, by certificate (`certified_min`), then refined. Clothoid: t is the arc
    length, so over [t0, t1] the distance is at least (d0 + d1 − (t1 − t0)) / 2.
    Formula: the box of the intervals (`_box`)."""
    def gap(q: Point) -> float:
        return math.dist(q, pt)

    if isinstance(seg, ClothoidSeg):
        def bound(piece) -> float:
            t0, t1, p0, p1, _ = piece
            return (gap(p0) + gap(p1) - (t1 - t0)) / 2
    else:
        def bound(piece) -> float:
            return _to_box(seg._box(piece[0], piece[1]), pt)

    piece = (lo, hi, seg.point_at(lo), seg.point_at(hi), None)
    t, left, right = certified_min([piece], gap, bound, point_split(seg.point_at))
    return _refine(seg.point_at, pt, t, left, right, lo, hi)


def _refine(at, pt: Point, t: float, left: float, right: float, lo: float, hi: float) -> float:
    """Ternary search on [left, right], around the best `t`: never worse than
    it, nor than the two ends of the curve."""
    for _ in range(_REFINE_STEPS):
        m1, m2 = left + (right - left) / 3, right - (right - left) / 3
        if math.dist(at(m1), pt) <= math.dist(at(m2), pt):
            right = m2
        else:
            left = m1
    for cand in ((left + right) / 2, lo, hi):
        if math.dist(at(cand), pt) <= math.dist(at(t), pt):
            t = cand
    return t
