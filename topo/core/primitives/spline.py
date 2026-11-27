"""
topo/core/primitives/spline.py
------------------------------
The spline: `BSplineSeg` (NURBS with weights), with de Boor, the derivatives
and the knot-span search. The name is the mathematical term (Schoenberg,
de Boor).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from .minimize import certified_min
from .mathseg import Algebra, DEFAULT_TOLERANCE, MathSeg, Point, _plain, _real
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point
from .line import distance_to_segment


def _bspline_find_span(t: float, degree: int, knots: List[float], n: int) -> int:
    """Index `i` with `knots[i] <= t < knots[i+1]` (binary search, "The NURBS
    Book" A2.1); `n` is the index of the last control point."""
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


def _insert_to_degree(p: int, knots: List[float], cpw: List[Tuple[float, float, float]],
                      t: float):
    """Insert `t` in the knot vector until it appears `p` times: there the curve
    passes through a control point and splits into two independent pieces.
    Also at the ends of the span, where an unclamped spline does not pass
    through a control point; outside the span, nothing."""
    if t < knots[p] or t > knots[-(p + 1)]:
        return knots, cpw
    while sum(1 for k in knots if k == t) < p:
        span = _bspline_find_span(t, p, knots, len(cpw) - 1)
        new = []
        for i in range(len(cpw) + 1):
            if i <= span - p:
                new.append(cpw[i])
            elif i > span:
                new.append(cpw[i - 1])
            else:
                alpha = (t - knots[i]) / (knots[i + p] - knots[i])
                new.append(tuple(alpha * cpw[i][c] + (1 - alpha) * cpw[i - 1][c] for c in range(3)))
        knots = knots[:span + 1] + [t] + knots[span + 1:]
        cpw = new
    return knots, cpw


def _bezier_pieces(p: int, knots: List[float], cpw: List[Tuple[float, float, float]]) -> List[list]:
    """The Bézier pieces of the curve between `knots[p]` and `knots[-(p + 1)]`,
    in homogeneous coordinates: every knot of the span inserted up to
    multiplicity `p`, so the curve passes through a control point at each knot."""
    lo, hi = knots[p], knots[-(p + 1)]
    for t in sorted({k for k in knots if lo <= k <= hi}):
        knots, cpw = _insert_to_degree(p, knots, cpw, t)
    first = max(i for i, k in enumerate(knots) if k == lo) - p
    count = len({k for k in knots if lo <= k <= hi}) - 1
    return [cpw[first + i * p:first + i * p + p + 1] for i in range(count)]


def _halves(c: list) -> Tuple[list, list]:
    """de Casteljau at the middle of the (homogeneous) piece `c`: the two halves, same curve."""
    left, right, cur = [c[0]], [c[-1]], list(c)
    while len(cur) > 1:
        cur = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2) for a, b in zip(cur, cur[1:])]
        left.append(cur[0])
        right.append(cur[-1])
    return left, right[::-1]


def _flat_polygon(piece: list, tolerance: float, out: List[Point]) -> None:
    """Append to `out` the piece's vertices after the first: halved until the
    control points are within `tolerance` of the chord. The curve lies in
    their convex hull (positive weights), so within `tolerance` of the chord:
    proved, not estimated."""
    stack = [piece]
    while stack:
        c = stack.pop()
        pts = [(x / w, y / w) for x, y, w in c]
        a, b = pts[0], pts[-1]
        if all(distance_to_segment(q, a, b) <= tolerance for q in pts[1:-1]):
            out.append(b)
        else:
            left, right = _halves(c)
            stack.append(right)
            stack.append(left)


def _derivative_points(points: List[tuple], knots: List[float], p: int) -> List[tuple]:
    """Control points of the derivative (degree p − 1, knots without the first and last)."""
    out = []
    for i in range(len(points) - 1):
        span = knots[i + p + 1] - knots[i + 1]
        scale = p / span if span > 0 else 0.0
        out.append(tuple(scale * (b - a) for a, b in zip(points[i], points[i + 1])))
    return out


def _deboor(t: float, p: int, knots: List[float], points: List[tuple]) -> tuple:
    """Point at parameter `t` of a vector-valued B-spline (de Boor, A5.1)."""
    k = _bspline_find_span(t, p, knots, len(points) - 1)
    d = [list(points[k - p + j]) for j in range(p + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = k - p + j
            denom = knots[i + p - r + 1] - knots[i]
            alpha = 0.0 if denom == 0 else (t - knots[i]) / denom
            d[j] = [(1 - alpha) * u + alpha * v for u, v in zip(d[j - 1], d[j])]
    return tuple(d[p])


@dataclass
class BSplineSeg(MathSeg):
    """
    B-spline (NURBS if `weights` is set): degree, control points, knots,
    weights — geometry only. What a source format keeps besides (flags,
    tolerances, fit points, tangents) stays in the adapter; `closed` and
    `periodic` are derived from the fields.
    """
    degree: int
    control_points: List[Point]
    knots: List[float]
    weights: Optional[List[float]] = None

    def __post_init__(self):
        self.degree = int(self.degree)
        self.control_points = [_plain(p) for p in self.control_points]
        self.knots = [_real(k) for k in self.knots]
        if self.weights is not None:
            self.weights = [_real(w) for w in self.weights]
        # discretize() points per tolerance: heal() asks for the same spline
        # many times. Not a field (outside eq/repr/fields); valid because a
        # spline is never modified in place — reversed/rotated make a new one.
        self._points: dict = {}
        self._pieces_cache: Optional[list] = None

    @property
    def algebra(self) -> Algebra:
        """Polynomial with no weights or all equal (the common factor cancels),
        rational otherwise."""
        w = self.weights
        return "polynomial" if not w or all(v == w[0] for v in w) else "rational"

    @property
    def clamped(self) -> bool:
        """True if the first and the last `degree + 1` knots coincide: the curve
        starts at the first control point and ends at the last."""
        p, k = self.degree, self.knots
        if len(k) < 2 * (p + 1):
            return True
        return k[0] == k[p] and k[-1] == k[-(p + 1)]

    @property
    def closed(self) -> bool:
        """True if the curve returns to its start (within DEFAULT_TOLERANCE)."""
        if len(self.control_points) < 2:
            return False
        start, end = self.endpoints()
        return math.hypot(start[0] - end[0], start[1] - end[1]) < DEFAULT_TOLERANCE

    @property
    def periodic(self) -> bool:
        """True if the curve is closed and not clamped: it closes with no
        control point on the joint."""
        return self.closed and not self.clamped

    def endpoints(self) -> Tuple[Point, Point]:
        """(start, end) on the true curve — for an unclamped spline they are
        not the first and last control points."""
        if not self.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        p = self.degree
        if len(self.knots) != len(self.control_points) + p + 1:
            return self.control_points[0], self.control_points[-1]
        return self._evaluate(self.knots[p]), self._evaluate(self.knots[-(p + 1)])

    def reversed(self) -> "BSplineSeg":
        """The same curve walked the other way: control points, weights and the
        knots remapped on the original domain (U'[i] = a + b − U[m−i]) are all
        reversed; reversing the control points alone deforms the curve inside."""
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

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """The spline rotated by `angle` radians about `origin`: control points
        rotate, knots and weights are unchanged."""
        return BSplineSeg(
            degree=self.degree,
            control_points=[_rotate_point(p, angle, origin) for p in self.control_points],
            knots=list(self.knots),
            weights=list(self.weights) if self.weights else None,
        )

    def translated(self, dx: float, dy: float) -> "BSplineSeg":
        """The spline moved by (`dx`, `dy`): the control points move."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_translate_point(p, dx, dy) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "BSplineSeg":
        """The spline mirrored on the line through `origin` at `angle` radians
        (default: the x axis): an affine map takes the curve to the curve of the
        mirrored control points."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_mirror_point(p, origin, angle) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """The spline scaled by `factor` (> 0) about `origin`: control points
        scale, knots and weights are unchanged."""
        factor = _check_factor(factor)
        return BSplineSeg(degree=self.degree,
                          control_points=[_scale_point(p, factor, origin) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def _defined(self) -> bool:
        """The knots define the curve: as many as the control points plus
        degree + 1, and a non-empty domain."""
        p, knots = self.degree, self.knots
        return p >= 1 and len(knots) == len(self.control_points) + p + 1 and knots[-(p + 1)] > knots[p]

    @property
    def t_range(self) -> Tuple[float, float]:
        """The knot domain: from `knots[degree]` to `knots[-(degree + 1)]`."""
        return (self.knots[self.degree], self.knots[-(self.degree + 1)])

    def point_at(self, t: float) -> Point:
        return self._evaluate(t)

    def derivative_at(self, t: float) -> Point:
        """In homogeneous coordinates, rational too: C' = (A' − w'·C) / w."""
        p, knots, ctrl = self.degree, self.knots, self.control_points
        # knots that do not define the curve: no derivative (the caller falls back on the chord)
        if not self._defined():
            return (0.0, 0.0)
        t0, t1 = self.t_range
        t = min(max(t, t0), t1)
        weights = self.weights or [1.0] * len(ctrl)
        h = [(c[0] * w, c[1] * w, w) for c, w in zip(ctrl, weights)]
        a = _deboor(t, p, knots, h)
        d = _derivative_points(h, knots, p)
        da = _deboor(t, p - 1, knots[1:-1], d) if p > 1 else d[_bspline_find_span(t, 1, knots, len(ctrl) - 1) - 1]
        x, y = a[0] / a[2], a[1] / a[2]
        return ((da[0] - da[2] * x) / a[2], (da[1] - da[2] * y) / a[2])

    def _evaluate(self, t: float) -> Point:
        """Point of the true curve at parameter `t` (de Boor, "The NURBS Book"
        A5.1 — rational if `weights` is set)."""
        degree = self.degree
        knots = self.knots
        ctrl = self.control_points
        n = len(ctrl) - 1

        # outside the domain evaluate at the border
        t_min, t_max = knots[degree], knots[-(degree + 1)]
        t = min(max(t, t_min), t_max)

        k = _bspline_find_span(t, degree, knots, n)
        first = k - degree
        weights = self.weights
        # homogeneous coordinates (x·w, y·w, w)
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

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """A polyline within `tolerance` of the true curve, by proof: Bézier
        pieces halved until their control points are within `tolerance` of the
        chord. Exact ends."""
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

        start, end = self.endpoints()
        out: List[Point] = [start]
        for _, _, piece in self._pieces():
            _flat_polygon(piece, tolerance, out)
        out[-1] = end
        return out

    def _pieces(self) -> List[Tuple[float, float, list]]:
        """(t0, t1, homogeneous Bézier piece) from one knot to the next. Weights
        must be positive: only then does the curve lie in the control hull."""
        if self._pieces_cache is None:
            if self.weights and min(self.weights) <= 0:
                raise ValueError("a spline's weights must be positive to be discretized")
            weights = self.weights or [1.0] * len(self.control_points)
            cpw = [(x * w, y * w, w) for (x, y), w in zip(self.control_points, weights)]
            p, knots = self.degree, list(self.knots)
            ks = sorted({k for k in knots if knots[p] <= k <= knots[-(p + 1)]})
            self._pieces_cache = list(zip(ks, ks[1:], _bezier_pieces(p, knots, cpw)))
        return self._pieces_cache

    def _minimize(self, value: Callable[[Point], float],
                  bound: Callable[[List[Point]], float]) -> Tuple[float, float, float]:
        """(t, lo, hi): the parameter where `value(point)` is minimal on the curve,
        within FLOAT_NOISE, and the span [lo, hi] around it to refine.
        `bound(control points)` is a lower bound of `value` over the piece (the
        curve lies in their hull); see `certified_min`."""
        def flat(q) -> Point:
            return q[0] / q[2], q[1] / q[2]

        def halves(piece):
            t0, t1, p0, p1, c = piece
            tm = (t0 + t1) / 2
            left, right = _halves(c)
            pm = flat(left[-1])
            return (t0, tm, p0, pm, left), (tm, t1, pm, p1, right)

        pieces = [(t0, t1, flat(c[0]), flat(c[-1]), c) for t0, t1, c in self._pieces()]
        return certified_min(pieces, value, lambda piece: bound([flat(q) for q in piece[4]]), halves)
