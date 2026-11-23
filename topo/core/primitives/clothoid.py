"""
topo/core/primitives/clothoid.py
--------------------------------
`ClothoidSeg`: the Euler spiral, the curve whose curvature grows with arc
length, κ(s) = s / A². It is an integral, not an elementary formula:
P(s) = ∫₀ˢ (cos θ(u), sin θ(u)) du with θ(u) = u² / (2A²), that is
A·√π·(C(w), S(w)) with w = s / (A·√π) and C, S the Fresnel integrals, computed
to machine precision.

The parameter is the arc length: the length of a piece is exact, the
derivative is the unit tangent, the polygon is within tolerance by proof
(|P''| = κ, the grid starts at s = 0).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import List, Tuple

from .conics import _grid
from .mathseg import DEFAULT_TOLERANCE, Algebra, MathSeg, Point, _plain, _real
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point

_EPS = sys.float_info.epsilon   # machine precision: the series stop here
# power series below, continued fraction above: both exact, only the number of terms differs
_SERIES_UP_TO = 1.5
_MAX_TERMS = 200


def fresnel(x: float) -> Tuple[float, float]:
    """(C(x), S(x)) = (∫₀ˣ cos(πt²/2) dt, ∫₀ˣ sin(πt²/2) dt), to machine
    precision: power series for |x| ≤ 1.5, continued fraction (Lentz) beyond."""
    ax = abs(x)
    if ax == 0:
        return 0.0, 0.0
    if ax <= _SERIES_UP_TO:
        # C = Σ (−1)ᵏ (π/2)²ᵏ x⁴ᵏ⁺¹ / ((2k)! (4k+1)),  S = Σ (−1)ᵏ (π/2)²ᵏ⁺¹ x⁴ᵏ⁺³ / ((2k+1)! (4k+3))
        fact = math.pi / 2 * ax * ax
        term, c, s = ax, ax, 0.0
        for n in range(1, _MAX_TERMS):
            term *= fact / n
            k, odd = divmod(n, 2)
            part = term / (2 * n + 1)
            if odd:
                s += (-1) ** k * part
            else:
                c += (-1) ** k * part
            if part < _EPS * max(abs(c), abs(s)):
                break
    else:
        # complex erf by continued fraction: (C + iS) = (1+i)/2 · (1 − e^{iπx²/2}·h·(x − ix))
        pix2 = math.pi * ax * ax
        b = complex(1.0, -pix2)
        cc, d = 1e300, 1 / b
        h = d
        n = -1
        for _ in range(_MAX_TERMS):
            n += 2
            a = -n * (n + 1)
            b += 4
            d = 1 / (a * d + b)
            cc = b + a / cc
            step = cc * d
            h *= step
            if abs(step.real - 1) + abs(step.imag) < _EPS:
                break
        h *= complex(ax, -ax)
        cs = complex(0.5, 0.5) * (1 - complex(math.cos(pix2 / 2), math.sin(pix2 / 2)) * h)
        c, s = cs.real, cs.imag
    return (c, s) if x > 0 else (-c, -s)


@dataclass
class ClothoidSeg(MathSeg):
    """
    A piece of the clothoid (Euler spiral) whose curvature grows with arc
    length, κ(s) = s / a²: zero curvature at `origin`, tangent at `angle`
    (radians) there, turning to the left (counter-clockwise) for s > 0 when
    `left`. `a` > 0 is the clothoid parameter (a² = radius · arc length).
    `s` is the arc length from `origin`, from `start_param` to `end_param`
    (either way round, negative on the other arm); `t` is the arc length
    walked from the start, t in [0, |end_param − start_param|].
    """
    origin: Point
    angle: float
    a: float
    start_param: float
    end_param: float
    left: bool = field(default=True, kw_only=True)

    def __post_init__(self):
        self.origin = _plain(self.origin)
        self.angle, self.a = _real(self.angle), _real(self.a)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not self.a > 0:
            raise ValueError(f"the clothoid parameter must be positive, got {self.a}")

    def _sign(self) -> float:
        return 1.0 if self.end_param >= self.start_param else -1.0

    def _local(self, s: float) -> Point:
        k = self.a * math.sqrt(math.pi)
        c, sn = fresnel(s / k)
        return k * c, k * sn * (1.0 if self.left else -1.0)

    def _place(self, p: Point, translate: bool = True) -> Point:
        ca, sa = math.cos(self.angle), math.sin(self.angle)
        x, y = p
        ox, oy = self.origin if translate else (0.0, 0.0)
        return ox + ca * x - sa * y, oy + sa * x + ca * y

    def _at(self, s: float) -> Point:
        return self._place(self._local(s))

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    @property
    def algebra(self) -> Algebra:
        """Transcendental: the point is a Fresnel integral."""
        return "transcendental"

    def point_at(self, t: float) -> Point:
        return self._at(self.start_param + self._sign() * t)

    def derivative_at(self, t: float) -> Point:
        s = self.start_param + self._sign() * t
        theta = s * s / (2 * self.a * self.a)
        tx, ty = math.cos(theta), math.sin(theta) * (1.0 if self.left else -1.0)
        dx, dy = self._place((tx, ty), translate=False)
        return self._sign() * dx, self._sign() * dy

    def endpoints(self) -> Tuple[Point, Point]:
        return self._at(self.start_param), self._at(self.end_param)

    def curvature_at(self, t: float) -> float:
        """Signed curvature at `t`, positive turning left as walked."""
        s = self.start_param + self._sign() * t
        return self._sign() * (1.0 if self.left else -1.0) * s / (self.a * self.a)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """|P''| = κ = |s|/a² grows with |s|. Over [s, s + h] the chord is at most
        h²·(|s| + h)/(8a²) away: the step is the root of h³ + |s|·h² = 8·tol·a²
        (Newton from above, the cubic is increasing and convex)."""
        bound = 8 * tolerance * self.a * self.a

        def step_at(s: float) -> float:
            r = abs(s)
            h = bound ** (1 / 3) + (bound / r) ** 0.5 if r > 0 else bound ** (1 / 3)
            for _ in range(60):
                f = h * h * (h + r) - bound
                if f <= 0:
                    break
                h -= f / (h * (3 * h + 2 * r))
            return h

        lo, hi = sorted((self.start_param, self.end_param))
        params = _grid(lo, hi, step_at)
        if self.start_param > self.end_param:
            params.reverse()
        return [self._at(s) for s in params]

    def to_bspline(self, *, tolerance: float = DEFAULT_TOLERANCE):
        """A cubic B-spline within `tolerance` of the curve, through its two
        ends: an approximation (a clothoid has no exact spline), for a format
        that cannot hold one."""
        from ..geometry.spline_fit import approximate_bspline   # geometry sits above primitives
        from .spline import BSplineSeg
        control, knots = approximate_bspline(self.discretize(tolerance=tolerance / 2), 3, tolerance / 2)
        return BSplineSeg(degree=3, control_points=[tuple(p) for p in control], knots=list(knots))

    def reversed(self) -> "ClothoidSeg":
        return ClothoidSeg(self.origin, self.angle, self.a, self.end_param, self.start_param, left=self.left)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "ClothoidSeg":
        return ClothoidSeg(_rotate_point(self.origin, angle, origin), self.angle + angle, self.a,
                           self.start_param, self.end_param, left=self.left)

    def translated(self, dx: float, dy: float) -> "ClothoidSeg":
        return ClothoidSeg(_translate_point(self.origin, dx, dy), self.angle, self.a,
                           self.start_param, self.end_param, left=self.left)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "ClothoidSeg":
        """A mirror flips the tangent about the axis and the way it turns."""
        return ClothoidSeg(_mirror_point(self.origin, origin, angle), 2 * angle - self.angle, self.a,
                           self.start_param, self.end_param, left=not self.left)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "ClothoidSeg":
        """Arc length and the parameter a are multiplied by `factor`."""
        k = _check_factor(factor)
        return ClothoidSeg(_scale_point(self.origin, k, origin), self.angle, self.a * k,
                           self.start_param * k, self.end_param * k, left=self.left)
