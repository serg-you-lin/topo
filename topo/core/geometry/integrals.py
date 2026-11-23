"""
topo/core/geometry/integrals.py
-------------------------------
Exact area and centroid of a closed loop, integrated over its primitives
with Green's theorem: no discretization, no tolerance.

For an oriented stretch the contribution is the triple

    area = ½ ∮ (x dy − y dx)     mx = ½ ∮ x² dy     my = −½ ∮ y² dx

and over a closed loop the three sums give the signed area (positive
counter-clockwise) and the moments ∬x dA, ∬y dA. Closed form for line, arc,
circle and ellipse; for a polynomial spline, Gauss quadrature exact on every
knot interval, for a rational one quadrature to machine precision. Pure
functions on primitives, one branch per type.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Sequence, Tuple

import numpy as np

from ..primitives.spline import BSplineSeg, _deboor, _derivative_points
from ..primitives.line import LineSeg
from ..primitives.mathseg import MathSeg
from ..primitives.conics import HyperbolaSeg, ParabolaSeg, EllipseSeg
from .rings import ring_jumps

Point = Tuple[float, float]
Vec = Tuple[float, ...]


@dataclass(frozen=True)
class Moments:
    """Signed area and first moments (∬x dA, ∬y dA) of a stretch or a loop."""
    area: float = 0.0
    mx: float = 0.0
    my: float = 0.0

    def __add__(self, other: "Moments") -> "Moments":
        return Moments(self.area + other.area, self.mx + other.mx, self.my + other.my)

    def __neg__(self) -> "Moments":
        return Moments(-self.area, -self.mx, -self.my)


def segment_moments(segment) -> Moments:
    """Green's contribution of a primitive walked in its direction."""
    if isinstance(segment, LineSeg):
        return _line_moments(segment.start, segment.end)
    if isinstance(segment, EllipseSeg):     # the circle too: axis (r, 0), ratio 1
        mx, my = segment.major_axis
        minor = (-my * segment.ratio, mx * segment.ratio)
        sign = 1.0 if segment.ccw else -1.0
        t0 = segment.start_param
        return _trig_moments(segment.center, (mx, my), minor, t0, t0 + sign * segment._sweep())
    if isinstance(segment, BSplineSeg):
        return _spline_moments(segment)
    if isinstance(segment, HyperbolaSeg):
        # in closed form like the ellipse, with cosh and sinh: its rational spline
        # needed an adaptive Gauss that does not converge far from the origin
        return _trig_moments(segment.center, segment.major_axis, segment._minor(),
                             segment.start_param, segment.end_param, hyperbolic=True)
    if isinstance(segment, ParabolaSeg):
        # the same curve, exact, as a polynomial quadratic spline: exact Gauss
        return _spline_moments(segment.to_bspline())
    if isinstance(segment, MathSeg):
        return _curve_moments(segment)
    raise TypeError(f"unsupported primitive: {type(segment).__name__}")


def ring_moments(segments: Sequence) -> Moments:
    """Sum of the contributions of a closed loop, in the given order and direction.
    A jump between the end of a segment and the start of the next (a gap closed
    within the tolerance, source coefficients intact) counts as its chord:
    without it the area would depend on where the piece sits.
    """
    total = Moments()
    for segment in segments:
        total = total + segment_moments(segment)
    for end, start in ring_jumps(segments):
        total = total + _line_moments(end, start)
    return total


def ring_area(segments: Sequence) -> float:
    """Exact (unsigned) area enclosed by a closed loop of primitives."""
    return abs(ring_moments(segments).area)


def ring_centroid(segments: Sequence) -> Point:
    """Exact centroid of the area enclosed by a closed loop. Raises `ValueError`
    if the loop encloses no area."""
    m = ring_moments(segments)
    if m.area == 0.0:
        raise ValueError("the ring encloses no area: no centroid")
    return (m.mx / m.area, m.my / m.area)


# --- Line ---

def _line_moments(p0: Point, p1: Point) -> Moments:
    (x0, y0), (x1, y1) = p0, p1
    return Moments(
        area=0.5 * (x0 * y1 - x1 * y0),
        mx=(y1 - y0) * (x0 * x0 + x0 * x1 + x1 * x1) / 6.0,
        my=-(x1 - x0) * (y0 * y0 + y0 * y1 + y1 * y1) / 6.0,
    )


# --- Arc, circle, ellipse: P(t) = c + M cos t + N sin t ---

# A polynomial in (cos t, sin t) is {(i, j): coefficient of cosⁱ·sinʲ}.
Trig = dict


def _trig_moments(center: Point, m: Point, n: Point, t0: float, t1: float, hyperbolic: bool = False) -> Moments:
    """Contribution of the stretch t0 → t1 of c + M cos t + N sin t (arc: M, N =
    (r, 0), (0, r); ellipse: major and minor axis), or with `hyperbolic` of
    c + M cosh t + N sinh t (one branch of a hyperbola). The integrands are
    polynomials of degree ≤ 3 in the two functions, integrated in closed form."""
    x = {(0, 0): center[0], (1, 0): m[0], (0, 1): n[0]}
    y = {(0, 0): center[1], (1, 0): m[1], (0, 1): n[1]}
    # cos' = −sin, sin' = cos; cosh' = sinh, sinh' = cosh
    turn = 1.0 if hyperbolic else -1.0
    dx = {(0, 1): turn * m[0], (1, 0): n[0]}
    dy = {(0, 1): turn * m[1], (1, 0): n[1]}
    area = _trig_add(_trig_mul(x, dy), _trig_mul(y, dx), -1.0)
    return Moments(
        area=0.5 * _trig_integral(area, t0, t1, hyperbolic),
        mx=0.5 * _trig_integral(_trig_mul(_trig_mul(x, x), dy), t0, t1, hyperbolic),
        my=-0.5 * _trig_integral(_trig_mul(_trig_mul(y, y), dx), t0, t1, hyperbolic),
    )


def _trig_mul(a: Trig, b: Trig) -> Trig:
    out: Trig = {}
    for (i, j), u in a.items():
        for (k, l), v in b.items():
            out[(i + k, j + l)] = out.get((i + k, j + l), 0.0) + u * v
    return out


def _trig_add(a: Trig, b: Trig, scale: float = 1.0) -> Trig:
    out = dict(a)
    for key, v in b.items():
        out[key] = out.get(key, 0.0) + scale * v
    return out


def _trig_integral(poly: Trig, t0: float, t1: float, hyperbolic: bool = False) -> float:
    integral = _cosh_sinh_integral if hyperbolic else _cos_sin_integral
    return sum(coef * integral(i, j, t0, t1) for (i, j), coef in poly.items())


def _cosh_sinh_integral(i: int, j: int, t0: float, t1: float) -> float:
    """∫ coshⁱ t · sinhʲ t dt from t0 to t1, in closed form for i + j ≤ 3."""
    if i + j > 3:
        raise ValueError(f"unexpected degree: cosh^{i} sinh^{j}")

    def primitive(t: float) -> float:
        c, s = math.cosh(t), math.sinh(t)
        return {(0, 0): t, (1, 0): s, (0, 1): c, (2, 0): 0.5 * (t + s * c), (0, 2): 0.5 * (s * c - t),
                (1, 1): 0.5 * s * s, (3, 0): s + s ** 3 / 3.0, (0, 3): c ** 3 / 3.0 - c,
                (2, 1): c ** 3 / 3.0, (1, 2): s ** 3 / 3.0}[(i, j)]

    return primitive(t1) - primitive(t0)


def _cos_sin_integral(i: int, j: int, t0: float, t1: float) -> float:
    """∫ cosⁱ t · sinʲ t dt from t0 to t1, in closed form for i + j ≤ 3."""
    c0, s0, c1, s1 = math.cos(t0), math.sin(t0), math.cos(t1), math.sin(t1)
    if (i, j) == (0, 0):
        return t1 - t0
    if (i, j) == (1, 0):
        return s1 - s0
    if (i, j) == (0, 1):
        return c0 - c1
    if (i, j) == (2, 0):
        return 0.5 * (t1 - t0) + 0.5 * (s1 * c1 - s0 * c0)
    if (i, j) == (0, 2):
        return 0.5 * (t1 - t0) - 0.5 * (s1 * c1 - s0 * c0)
    if (i, j) == (1, 1):
        return 0.5 * (s1 * s1 - s0 * s0)
    if (i, j) == (3, 0):
        return (s1 - s1 ** 3 / 3.0) - (s0 - s0 ** 3 / 3.0)
    if (i, j) == (0, 3):
        return (-c1 + c1 ** 3 / 3.0) - (-c0 + c0 ** 3 / 3.0)
    if (i, j) == (2, 1):
        return (c0 ** 3 - c1 ** 3) / 3.0
    if (i, j) == (1, 2):
        return (s1 ** 3 - s0 ** 3) / 3.0
    raise ValueError(f"unexpected degree: cos^{i} sin^{j}")


# ---------------------------------------------------------------------------
# Spline
# ---------------------------------------------------------------------------

def _spline_moments(seg: BSplineSeg) -> Moments:
    """On every non-empty knot interval of the domain. Polynomial: x, y of degree
    p, the highest integrand (x²·y') of degree 3p − 1, exact with 2p-point
    Gauss. Rational: (2p + 8)-point Gauss, the interval halved until two levels
    agree to machine precision."""
    p = seg.degree
    knots = seg.knots
    if p < 1 or len(knots) != len(seg.control_points) + p + 1:
        raise ValueError("malformed spline: knots and control points do not agree")
    weights = seg.weights or [1.0] * len(seg.control_points)
    hom = [(x * w, y * w, w) for (x, y), w in zip(seg.control_points, weights)]
    der = _derivative_points(hom, knots, p)
    rational = seg.weights is not None and len(set(weights)) > 1

    def integrand(t: float) -> Vec:
        xw, yw, w = _deboor(t, p, knots, hom)
        dxw, dyw, dw = _deboor(t, p - 1, knots[1:-1], der)
        x, y = xw / w, yw / w
        dx, dy = (dxw - x * dw) / w, (dyw - y * dw) / w
        return (0.5 * (x * dy - y * dx), 0.5 * x * x * dy, -0.5 * y * y * dx)

    total = (0.0, 0.0, 0.0)
    for a, b in zip(knots[p:len(knots) - p - 1], knots[p + 1:len(knots) - p]):
        if b <= a:
            continue
        if rational:
            part = _adaptive_gauss(integrand, a, b, 2 * p + 8)
        else:
            part = _gauss(integrand, a, b, 2 * p)
        total = tuple(u + v for u, v in zip(total, part))
    return Moments(*total)


def _curve_moments(seg) -> Moments:
    """Any curve: exact `point_at` and `derivative_at`, 16-point Gauss on 16
    pieces, each halved until two levels agree to machine precision."""
    def integrand(t: float) -> Vec:
        x, y = seg.point_at(t)
        dx, dy = seg.derivative_at(t)
        return (0.5 * (x * dy - y * dx), 0.5 * x * x * dy, -0.5 * y * y * dx)

    t0, t1 = seg.t_range
    total = (0.0, 0.0, 0.0)
    for k in range(16):
        part = _adaptive_gauss(integrand, t0 + (t1 - t0) * k / 16, t0 + (t1 - t0) * (k + 1) / 16, 16)
        total = tuple(u + v for u, v in zip(total, part))
    return Moments(*total)


def curve_length(seg) -> float:
    """∫|P'(t)| dt on the exact derivative: 16-point Gauss, every piece halved
    until two levels agree to machine precision. The pieces: on a spline the
    intervals between two knots (at a knot the derivative may have a kink, which
    Gauss must not cross), on other curves four equal parts."""
    def speed(t: float) -> Vec:
        return (math.hypot(*seg.derivative_at(t)),)

    t0, t1 = seg.t_range
    if isinstance(seg, BSplineSeg):
        bounds = [t0] + sorted({k for k in seg.knots if t0 < k < t1}) + [t1]
    else:
        bounds = [t0 + (t1 - t0) * k / 4 for k in range(5)]
    return sum(_adaptive_gauss(speed, a, b, 16)[0] for a, b in zip(bounds, bounds[1:]))


@lru_cache(maxsize=None)
def _gauss_rule(n: int) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    nodes, weights = np.polynomial.legendre.leggauss(n)
    return tuple(float(x) for x in nodes), tuple(float(w) for w in weights)


def _gauss(f: Callable[[float], Vec], a: float, b: float, n: int) -> Vec:
    nodes, weights = _gauss_rule(n)
    half, mid = 0.5 * (b - a), 0.5 * (a + b)
    total = None
    for x, w in zip(nodes, weights):
        value = f(mid + half * x)
        total = [w * v for v in value] if total is None else [s + w * v for s, v in zip(total, value)]
    return tuple(half * s for s in total)


def _adaptive_gauss(f: Callable[[float], Vec], a: float, b: float, n: int, depth: int = 0) -> Vec:
    whole = _gauss(f, a, b, n)
    mid = 0.5 * (a + b)
    left, right = _gauss(f, a, mid, n), _gauss(f, mid, b, n)
    halves = tuple(u + v for u, v in zip(left, right))
    scale = max(1.0, *(abs(v) for v in halves))
    if depth >= 12 or all(abs(u - v) <= 1e-14 * scale for u, v in zip(whole, halves)):
        return halves
    l = _adaptive_gauss(f, a, mid, n, depth + 1)
    r = _adaptive_gauss(f, mid, b, n, depth + 1)
    return tuple(u + v for u, v in zip(l, r))
