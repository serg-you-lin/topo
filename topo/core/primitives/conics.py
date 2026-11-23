"""
topo/core/primitives/conics.py
------------------------------
The conics: pieces of curve on A·x² + B·xy + C·y² + D·x + E·y + F = 0.
`EllipseSeg` (B² − 4AC < 0), with `CircleSeg` as its child (equal semi-axes);
`ParabolaSeg` (= 0) and `HyperbolaSeg` (> 0, one branch). Each is a centre (or
vertex), some vectors and a parameter interval; the equation is derived from
them. A conic becomes an exact rational quadratic spline (`to_bspline`) for
whoever must write it where the conic does not exist.

Discretization by proof: between two points h apart in parameter the deviation
from the chord is at most h²/8 · max|P''| over the piece. The grid starts at
parameter 0, so a piece has the vertices of the whole curve.
"""

from __future__ import annotations

import math
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ...precision import FLOAT_NOISE
from .mathseg import DEFAULT_TOLERANCE, Algebra, MathSeg, Point, _plain, _real
from .spline import BSplineSeg
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point

# ---------------------------------------------------------------------------
# Angles and grid of arcs and ellipses
# ---------------------------------------------------------------------------

# a grid point closer than this to an arc end is the end itself and is skipped:
# it would only make a degenerate piece
_GRID_SNAP = FLOAT_NOISE


def _angular_sweep(start: float, end: float, ccw: bool) -> float:
    """Angle swept in radians, always positive, walking from `start` to `end`
    the given way — the same for a CircleSeg and an EllipseSeg."""
    raw = (end - start) if ccw else (start - end)
    sweep = raw % (2 * math.pi)
    # a full turn from any angle: (a + 2π) − a lands one ulp from 2π, above
    # (remainder ~0) or below (~2π); both are the full turn
    if (sweep < 1e-12 or 2 * math.pi - sweep < 1e-12) and abs(raw) > 1e-12:
        sweep = 2 * math.pi
    return sweep


def point_on_circle(center: Point, radius: float, angle: float) -> Point:
    """Point of the circle (`center`, `radius`) at the given angle (radians)."""
    return (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))


def angle_from_start(center: Point, start_angle: float, ccw: bool, pt: Point) -> float:
    """Angle, in [0, 2π), to walk from `start_angle` the `ccw` way to reach the
    direction of `pt` seen from `center`."""
    phi = math.atan2(pt[1] - center[1], pt[0] - center[0])
    delta = (phi - start_angle) if ccw else (start_angle - phi)
    return delta % (2 * math.pi)


def _sagitta_step(radius: float, tolerance: float) -> Optional[float]:
    """Largest angle of a chord at most `tolerance` from the arc of radius
    `radius`. None if the radius does not exceed the tolerance: the formula
    is meaningless there and the caller picks its fallback."""
    if radius <= tolerance:
        return None
    ratio = max(-1.0, min(1.0, 1.0 - tolerance / radius))
    return 2.0 * math.acos(ratio)


def _circle_sides(radius: float, tolerance: float) -> int:
    """Sides of the grid of a circle of radius `radius`: sagitta <= tolerance,
    no minimum and no cap (the sagitta is absolute, sides grow with the
    radius). A multiple of 4: the grid is symmetric about both axes, so
    quarters fall on vertices and a mirrored piece gives the mirrored polygon.
    A radius within the tolerance has 4: every inscribed polygon is at most
    the radius from the circle."""
    step = _sagitta_step(radius, tolerance)
    sides = 4 if step is None else math.ceil(2 * math.pi / step)
    return -(-sides // 4) * 4


def _grid_angles(lo: float, hi: float, radius: float, sides: int) -> List[float]:
    """Angles from `lo` to `hi` (lo < hi): the two exact ends and, between them,
    the points of the grid k·2π/sides anchored at angle 0. So every arc of a
    circle is a piece of the whole circle's polygon, however it is cut."""
    step = 2 * math.pi / sides
    snap = _GRID_SNAP / radius
    angles = [lo]
    for k in range(math.floor(lo / step) + 1, math.ceil(hi / step)):
        a = k * step
        if a - lo > snap and hi - a > snap:
            angles.append(a)
    angles.append(hi)
    return angles


_Equation = Tuple[float, float, float, float, float, float]


class ConicSeg(MathSeg):
    """
    A piece of a conic: a curve on A·x² + B·xy + C·y² + D·x + E·y + F = 0.
    The sign of B² − 4AC says which: < 0 an ellipse (a circle when A = C and
    B = 0), = 0 a parabola, > 0 a hyperbola.
    """

    @property
    @abstractmethod
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        """(A, B, C, D, E, F) of the conic the piece lies on, up to a common factor."""

    @property
    def algebra(self) -> Algebra:
        return "rational"


def _ellipse_equation(center: Point, axis: Point, a: float, b: float) -> Tuple[float, float, float, float, float, float]:
    """(A..F) of the ellipse centred `center`, semi-axis `a` along the unit
    vector `axis` and `b` at 90°: x'²/a² + y'²/b² = 1 in its frame, expanded."""
    ux, uy = axis
    p = ux * ux / (a * a) + uy * uy / (b * b)
    q = 2 * ux * uy * (1 / (a * a) - 1 / (b * b))
    r = uy * uy / (a * a) + ux * ux / (b * b)
    cx, cy = center
    return (p, q, r, -2 * p * cx - q * cy, -q * cx - 2 * r * cy, p * cx * cx + q * cx * cy + r * cy * cy - 1)


# ---------------------------------------------------------------------------
# EllipseSeg
# ---------------------------------------------------------------------------

@dataclass
class EllipseSeg(ConicSeg):
    """
    A piece of the ellipse P(s) = center + cos(s)·major_axis + sin(s)·ratio·
    (major_axis turned +90°): the unit circle seen through a linear map.
    `major_axis` is the vector from the centre to the end of the long axis
    (its length is the semi-major axis a), `ratio` = b / a. `s` runs from
    `start_param` to `end_param`, counter-clockwise when `ccw`; the whole
    ellipse is 0 to 2π. `t` is the parameter walked from the start, t in
    [0, sweep].
    """
    center: Point
    major_axis: Point   # vector from the centre, not an absolute point
    ratio: float         # minor / major semi-axis, 0 < ratio <= 1
    start_param: float   # radians
    end_param: float     # radians
    ccw: bool = True

    def __post_init__(self):
        self.center, self.major_axis = _plain(self.center), _plain(self.major_axis)
        self.ratio = _real(self.ratio)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not (math.hypot(*self.major_axis) > 0 and self.ratio > 0):
            raise ValueError(f"degenerate ellipse: axis {self.major_axis}, ratio {self.ratio}")

    def _sweep(self) -> float:
        """Angle (parameter) swept in radians, always positive."""
        return _angular_sweep(self.start_param, self.end_param, self.ccw)

    def _point_at(self, t: float) -> Point:
        """center + cos(t)·major_axis + sin(t)·ratio·(major_axis turned +90°)."""
        mx, my = self.major_axis
        nx, ny = -my * self.ratio, mx * self.ratio
        return (
            self.center[0] + math.cos(t) * mx + math.sin(t) * nx,
            self.center[1] + math.cos(t) * my + math.sin(t) * ny,
        )

    def endpoints(self) -> Tuple[Point, Point]:
        return self._point_at(self.start_param), self._point_at(self.end_param)

    @property
    def t_range(self) -> Tuple[float, float]:
        """`t` is the parameter walked from `start_param`: t in [0, sweep]."""
        return (0.0, self._sweep())

    def point_at(self, t: float) -> Point:
        return self._point_at(self.start_param + (t if self.ccw else -t))

    def derivative_at(self, t: float) -> Point:
        u = self.start_param + (t if self.ccw else -t)
        sign = 1.0 if self.ccw else -1.0
        (mx, my), r = self.major_axis, self.ratio
        return (sign * (-math.sin(u) * mx - math.cos(u) * my * r), sign * (-math.sin(u) * my + math.cos(u) * mx * r))

    @property
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        a = math.hypot(*self.major_axis)
        return _ellipse_equation(self.center, (self.major_axis[0] / a, self.major_axis[1] / a), a, a * self.ratio)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """On the parameter grid: the ellipse is the circle of the major
        semi-axis `a` seen through a linear map that stretches no vector
        (factors 1 and ratio), so the vertices k·2π/N of `_circle_sides(a,
        tolerance)` carried onto the ellipse stay within `tolerance` as on the
        circle. Exact ends plus the grid points between them, like `CircleSeg`:
        a cut ellipse gives the whole ellipse's polygon, a reversed one the
        same points."""
        total_angle = self._sweep()
        if total_angle < 1e-12:
            pt = self._point_at(self.start_param)
            return [pt, pt]

        # ratio > 1 (the given axis is the minor one): the larger factor is ratio
        radius = math.hypot(*self.major_axis) * max(1.0, self.ratio)
        sides = _circle_sides(radius, tolerance)
        if self.ccw:
            params = _grid_angles(self.start_param, self.start_param + total_angle, radius, sides)
        else:
            params = _grid_angles(self.start_param - total_angle, self.start_param, radius, sides)[::-1]
        return [self._point_at(t) for t in params]

    def reversed(self) -> "EllipseSeg":
        """The same ellipse walked the other way: swaps the parameters and negates ccw."""
        return EllipseSeg(
            center=self.center,
            major_axis=self.major_axis,
            ratio=self.ratio,
            start_param=self.end_param,
            end_param=self.start_param,
            ccw=not self.ccw,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "EllipseSeg":
        """The ellipse rotated by `angle` radians about `origin`: the centre
        rotates about `origin`, `major_axis` (a vector) about (0, 0); the
        parameters are relative to `major_axis` and stay."""
        return EllipseSeg(
            center=_rotate_point(self.center, angle, origin),
            major_axis=_rotate_point(self.major_axis, angle, (0.0, 0.0)),
            ratio=self.ratio,
            start_param=self.start_param,
            end_param=self.end_param,
            ccw=self.ccw,
        )

    def translated(self, dx: float, dy: float) -> "EllipseSeg":
        """The ellipse moved by (`dx`, `dy`): only the centre moves."""
        return EllipseSeg(center=_translate_point(self.center, dx, dy), major_axis=self.major_axis,
                          ratio=self.ratio, start_param=self.start_param, end_param=self.end_param,
                          ccw=self.ccw)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "EllipseSeg":
        """The ellipse mirrored on the line through `origin` at `angle` radians
        (default: the x axis). A mirror reverses the 90° turn that gives the
        minor axis, so the point at parameter `t` goes to `−t`: parameters
        change sign and the direction flips. `major_axis` is a vector: it
        mirrors on the axis direction, with no translation."""
        return EllipseSeg(center=_mirror_point(self.center, origin, angle),
                          major_axis=_mirror_point(self.major_axis, (0.0, 0.0), angle),
                          ratio=self.ratio, start_param=-self.start_param, end_param=-self.end_param,
                          ccw=not self.ccw)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "EllipseSeg":
        """The ellipse scaled by `factor` (> 0) about `origin`: the centre moves,
        `major_axis` stretches, `ratio` and parameters are unchanged."""
        factor = _check_factor(factor)
        return EllipseSeg(center=_scale_point(self.center, factor, origin),
                          major_axis=(self.major_axis[0] * factor, self.major_axis[1] * factor),
                          ratio=self.ratio, start_param=self.start_param, end_param=self.end_param,
                          ccw=self.ccw)


# ---------------------------------------------------------------------------
# CircleSeg: an arc or a whole circle
# ---------------------------------------------------------------------------

class CircleSeg(EllipseSeg):
    """A piece of the circle (`center`, `radius`) from `start_angle` to
    `end_angle`, counter-clockwise when `ccw`; with no angles the whole
    circle from angle 0. A circle is an arc that goes all the way round
    (`full`), and an ellipse with equal semi-axes: its axis is
    (radius, 0), so the ellipse's parameter is the angle. `t` is the angle
    walked from the start: t in [0, sweep]."""

    def __init__(self, center: Point, radius: float, start_angle: float = 0.0,
                 end_angle: float = 2 * math.pi, ccw: bool = True):
        radius = _real(radius)
        if not radius > 0:
            raise ValueError(f"the radius must be positive, got {radius}")
        super().__init__(center=center, major_axis=(radius, 0.0), ratio=1.0,
                         start_param=start_angle, end_param=end_angle, ccw=ccw)

    @property
    def radius(self) -> float:
        return self.major_axis[0]

    @property
    def start_angle(self) -> float:
        return self.start_param

    @property
    def end_angle(self) -> float:
        return self.end_param

    def __repr__(self) -> str:
        return (f"CircleSeg(center={self.center!r}, radius={self.radius!r}, start_angle={self.start_angle!r}, "
                f"end_angle={self.end_angle!r}, ccw={self.ccw!r})")

    def _sweep(self) -> float:
        """Angle swept in radians, always positive."""
        return _angular_sweep(self.start_angle, self.end_angle, self.ccw)

    @property
    def full(self) -> bool:
        """True when the piece goes all the way round: the whole circle."""
        return self._sweep() == 2 * math.pi

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """On the circle's grid (`_circle_sides`, anchored at angle 0): the exact
        ends plus the grid vertices between them, so every arc lies on the whole
        circle's polygon. Sagitta <= tolerance. Also the full turn: a circle and
        its arcs have the same vertices, wherever it starts."""
        total_angle = self._sweep()

        if total_angle < 1e-12:
            start_pt = self._point_at(self.start_angle)
            return [start_pt, start_pt]

        sides = _circle_sides(self.radius, tolerance)
        if self.ccw:
            angles = _grid_angles(self.start_angle, self.start_angle + total_angle, self.radius, sides)
        else:
            angles = _grid_angles(self.start_angle - total_angle, self.start_angle, self.radius, sides)[::-1]
        return [self._point_at(a) for a in angles]

    def _point_at(self, angle: float) -> Point:
        """Point on the arc at the given angle (radians)."""
        return point_on_circle(self.center, self.radius, angle)

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, self._sweep())

    def point_at(self, t: float) -> Point:
        return self._point_at(self.start_angle + (t if self.ccw else -t))

    def derivative_at(self, t: float) -> Point:
        a = self.start_angle + (t if self.ccw else -t)
        sign = 1.0 if self.ccw else -1.0
        return (-sign * self.radius * math.sin(a), sign * self.radius * math.cos(a))

    @property
    def equation(self) -> Tuple[float, float, float, float, float, float]:
        return _ellipse_equation(self.center, (1.0, 0.0), self.radius, self.radius)

    def reversed(self) -> "CircleSeg":
        """The same arc walked the other way: swaps the angles and negates ccw."""
        return CircleSeg(
            center=self.center,
            radius=self.radius,
            start_angle=self.end_angle,
            end_angle=self.start_angle,
            ccw=not self.ccw,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "CircleSeg":
        """The arc rotated by `angle` radians about `origin`: the centre rotates,
        the angles shift by `angle`; radius and direction are unchanged."""
        return CircleSeg(
            center=_rotate_point(self.center, angle, origin),
            radius=self.radius,
            start_angle=self.start_angle + angle,
            end_angle=self.end_angle + angle,
            ccw=self.ccw,
        )

    def translated(self, dx: float, dy: float) -> "CircleSeg":
        """The arc moved by (`dx`, `dy`): only the centre moves."""
        return CircleSeg(center=_translate_point(self.center, dx, dy), radius=self.radius,
                      start_angle=self.start_angle, end_angle=self.end_angle, ccw=self.ccw)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "CircleSeg":
        """The arc mirrored on the line through `origin` at `angle` radians
        (default: the x axis): the point at angle `a` goes to `2·angle − a`, so
        the direction flips. On the x axis the circle's grid (anchored at
        angle 0) is symmetric and the mirrored arc has the mirrored vertices;
        on another axis the curve is exact and the vertices fall on the new
        arc's grid."""
        return CircleSeg(center=_mirror_point(self.center, origin, angle), radius=self.radius,
                      start_angle=2 * angle - self.start_angle, end_angle=2 * angle - self.end_angle,
                      ccw=not self.ccw)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "CircleSeg":
        """The arc scaled by `factor` (> 0) about `origin`: the centre moves, the
        radius is multiplied, angles and direction are unchanged."""
        factor = _check_factor(factor)
        return CircleSeg(center=_scale_point(self.center, factor, origin), radius=self.radius * factor,
                      start_angle=self.start_angle, end_angle=self.end_angle, ccw=self.ccw)

    @classmethod
    def from_ends(cls, start: Point, end: Point, sweep: float) -> "CircleSeg":
        """The arc from `start` to `end` that turns through `sweep` radians:
        positive counter-clockwise, negative clockwise, 0 < |sweep| < 2π."""
        if not 0 < abs(sweep) < 2 * math.pi:
            raise ValueError(f"the sweep must be in (0, 2π) either way, got {sweep}")
        half_chord = math.dist(start, end) / 2.0
        if not half_chord > 0:
            raise ValueError("zero chord: a point, not an arc")
        ccw = sweep > 0
        turn = abs(sweep)
        radius = half_chord / math.sin(turn / 2.0)
        # from the chord's midpoint the centre lies on the perpendicular, to the
        # left if the arc turns counter-clockwise, at a signed r·cos(turn/2):
        # past half a turn the centre crosses to the other side of the chord
        nx, ny = -(end[1] - start[1]) / (2 * half_chord), (end[0] - start[0]) / (2 * half_chord)
        d = (1.0 if ccw else -1.0) * radius * math.cos(turn / 2.0)
        cx, cy = (start[0] + end[0]) / 2.0 + d * nx, (start[1] + end[1]) / 2.0 + d * ny
        return cls(center=(cx, cy), radius=radius,
                   start_angle=math.atan2(start[1] - cy, start[0] - cx),
                   end_angle=math.atan2(end[1] - cy, end[0] - cx), ccw=ccw)


def is_full_circle(segment) -> bool:
    """A `CircleSeg` that goes all the way round."""
    return isinstance(segment, CircleSeg) and segment.full


def is_arc(segment) -> bool:
    """A `CircleSeg` that does not go all the way round: an arc."""
    return isinstance(segment, CircleSeg) and not segment.full



def _walk(start: float, end: float) -> float:
    """+1 if the parameter grows from `start` to `end`, −1 if it falls."""
    return 1.0 if end >= start else -1.0


def _grid(lo: float, hi: float, step_at) -> List[float]:
    """The parameters from `lo` to `hi` (lo < hi): the two exact ends and,
    between them, the grid points starting at 0 and advancing by `step_at(|s|)`
    towards each side. A piece falls on the whole curve's grid."""
    snap = (hi - lo) * FLOAT_NOISE
    marks = []
    for sign in (1.0, -1.0):
        t = 0.0 if sign > 0 else step_at(0.0)
        while (sign * t < hi) if sign > 0 else (sign * t > lo):
            if lo + snap < sign * t < hi - snap:
                marks.append(sign * t)
            t += step_at(t)
    return [lo] + sorted(marks) + [hi]


@dataclass
class ParabolaSeg(ConicSeg):
    """
    A piece of the parabola with vertex `vertex` and focus `focus`:
    P(s) = vertex + s·n + s²/(4f)·u, u the unit axis towards the focus, n the
    axis turned +90°, f the vertex–focus distance. `s` runs from
    `start_param` to `end_param` (either way round); `t` is the parameter
    walked from the start, t in [0, |end_param − start_param|].
    """
    vertex: Point
    focus: Point
    start_param: float
    end_param: float

    def __post_init__(self):
        self.vertex, self.focus = _plain(self.vertex), _plain(self.focus)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not math.dist(self.vertex, self.focus) > 0:
            raise ValueError(f"degenerate parabola: vertex and focus coincide at {self.vertex}")

    def _frame(self) -> Tuple[float, Point, Point]:
        """(f, u, n): focal distance, axis towards the focus, axis turned +90°."""
        dx, dy = self.focus[0] - self.vertex[0], self.focus[1] - self.vertex[1]
        f = math.hypot(dx, dy)
        u = (dx / f, dy / f)
        return f, u, (-u[1], u[0])

    def _point(self, s: float) -> Point:
        f, u, n = self._frame()
        q = s * s / (4 * f)
        return (self.vertex[0] + s * n[0] + q * u[0], self.vertex[1] + s * n[1] + q * u[1])

    @property
    def algebra(self) -> Algebra:
        """Polynomial: s and s² in its frame (ellipse and hyperbola are not)."""
        return "polynomial"

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    def point_at(self, t: float) -> Point:
        return self._point(self.start_param + _walk(self.start_param, self.end_param) * t)

    def derivative_at(self, t: float) -> Point:
        sign = _walk(self.start_param, self.end_param)
        s = self.start_param + sign * t
        f, u, n = self._frame()
        q = s / (2 * f)
        return (sign * (n[0] + q * u[0]), sign * (n[1] + q * u[1]))

    @property
    def equation(self) -> _Equation:
        """(n·(p − V))² − 4f·u·(p − V) = 0, expanded."""
        f, (ux, uy), (nx, ny) = self._frame()
        vx, vy = self.vertex
        nv, uv = nx * vx + ny * vy, ux * vx + uy * vy
        return (nx * nx, 2 * nx * ny, ny * ny, -2 * nx * nv - 4 * f * ux, -2 * ny * nv - 4 * f * uy,
                nv * nv + 4 * f * uv)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """|P''| = 1/(2f) is constant: the step h = √(16·f·tol) keeps every chord within `tolerance`."""
        f, _, _ = self._frame()
        step = math.sqrt(16 * f * tolerance)
        lo, hi = sorted((self.start_param, self.end_param))
        snap = (hi - lo) * FLOAT_NOISE
        params = [lo] + [k * step for k in range(math.floor(lo / step) + 1, math.ceil(hi / step))
                         if lo + snap < k * step < hi - snap] + [hi]
        if self.start_param > self.end_param:
            params.reverse()
        return [self._point(s) for s in params]

    def to_bspline(self) -> BSplineSeg:
        """The same curve as a quadratic spline (weight 1): exact, not an approximation."""
        a, b = self.start_param, self.end_param
        f, u, n = self._frame()
        q = a * b / (4 * f)
        middle = (self.vertex[0] + (a + b) / 2 * n[0] + q * u[0], self.vertex[1] + (a + b) / 2 * n[1] + q * u[1])
        return BSplineSeg(degree=2, control_points=[self._point(a), middle, self._point(b)], knots=[0, 0, 0, 1, 1, 1])

    def reversed(self) -> "ParabolaSeg":
        return ParabolaSeg(self.vertex, self.focus, self.end_param, self.start_param)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "ParabolaSeg":
        return ParabolaSeg(_rotate_point(self.vertex, angle, origin), _rotate_point(self.focus, angle, origin),
                           self.start_param, self.end_param)

    def translated(self, dx: float, dy: float) -> "ParabolaSeg":
        return ParabolaSeg(_translate_point(self.vertex, dx, dy), _translate_point(self.focus, dx, dy),
                           self.start_param, self.end_param)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "ParabolaSeg":
        """A mirror flips n relative to u: the point at `s` goes to `−s`."""
        return ParabolaSeg(_mirror_point(self.vertex, origin, angle), _mirror_point(self.focus, origin, angle),
                           -self.start_param, -self.end_param)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "ParabolaSeg":
        """f becomes factor·f and the point at `s` goes to `factor·s`."""
        factor = _check_factor(factor)
        return ParabolaSeg(_scale_point(self.vertex, factor, origin), _scale_point(self.focus, factor, origin),
                           self.start_param * factor, self.end_param * factor)


@dataclass
class HyperbolaSeg(ConicSeg):
    """
    A piece of one branch of the hyperbola with centre `center`:
    P(s) = center + cosh(s)·major_axis + sinh(s)·ratio·(major_axis turned
    +90°). `major_axis` is the vector from the centre to the branch's vertex
    (length a), `ratio` = b / a > 0. `s` runs from `start_param` to
    `end_param` (either way round); `t` is the parameter walked from the
    start, t in [0, |end_param − start_param|].
    """
    center: Point
    major_axis: Point
    ratio: float
    start_param: float
    end_param: float

    def __post_init__(self):
        self.center, self.major_axis = _plain(self.center), _plain(self.major_axis)
        self.ratio = _real(self.ratio)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        if not (math.hypot(*self.major_axis) > 0 and self.ratio > 0):
            raise ValueError(f"degenerate hyperbola: axis {self.major_axis}, ratio {self.ratio}")

    def _minor(self) -> Point:
        mx, my = self.major_axis
        return (-my * self.ratio, mx * self.ratio)

    def _point(self, s: float) -> Point:
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        c, h = math.cosh(s), math.sinh(s)
        return (self.center[0] + c * mx + h * nx, self.center[1] + c * my + h * ny)

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    def point_at(self, t: float) -> Point:
        return self._point(self.start_param + _walk(self.start_param, self.end_param) * t)

    def derivative_at(self, t: float) -> Point:
        sign = _walk(self.start_param, self.end_param)
        s = self.start_param + sign * t
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        c, h = math.cosh(s), math.sinh(s)
        return (sign * (h * mx + c * nx), sign * (h * my + c * ny))

    @property
    def equation(self) -> _Equation:
        """x'²/a² − y'²/b² = 1 in the frame of the centre and the axis, expanded."""
        a = math.hypot(*self.major_axis)
        b = a * self.ratio
        ux, uy = self.major_axis[0] / a, self.major_axis[1] / a
        p = ux * ux / (a * a) - uy * uy / (b * b)
        q = 2 * ux * uy * (1 / (a * a) + 1 / (b * b))
        r = uy * uy / (a * a) - ux * ux / (b * b)
        cx, cy = self.center
        return (p, q, r, -2 * p * cx - q * cy, -q * cx - 2 * r * cy, p * cx * cx + q * cx * cy + r * cy * cy - 1)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """|P''(s)|² = a²·cosh²s + b²·sinh²s grows with |s|: the step from |s| is
        measured at the far end of the piece, so every chord is within `tolerance`."""
        a = math.hypot(*self.major_axis)
        b = a * self.ratio

        def bend(s: float) -> float:
            return math.sqrt(a * a * math.cosh(s) ** 2 + b * b * math.sinh(s) ** 2)

        def step_at(s: float) -> float:
            first = math.sqrt(8 * tolerance / bend(s))
            return math.sqrt(8 * tolerance / bend(s + first))

        lo, hi = sorted((self.start_param, self.end_param))
        params = _grid(lo, hi, step_at)
        if self.start_param > self.end_param:
            params.reverse()
        return [self._point(s) for s in params]

    def to_bspline(self) -> BSplineSeg:
        """The same curve as a rational quadratic spline: the middle point is
        (cosh m·M + sinh m·N) / cosh d from the centre, weight cosh d (m the
        middle parameter, d half the span). Exact for every span."""
        a, b = self.start_param, self.end_param
        m, d = (a + b) / 2, abs(b - a) / 2
        (mx, my), (nx, ny) = self.major_axis, self._minor()
        k = 1 / math.cosh(d)
        middle = (self.center[0] + k * (math.cosh(m) * mx + math.sinh(m) * nx),
                  self.center[1] + k * (math.cosh(m) * my + math.sinh(m) * ny))
        return BSplineSeg(degree=2, control_points=[self._point(a), middle, self._point(b)],
                          knots=[0, 0, 0, 1, 1, 1], weights=[1.0, math.cosh(d), 1.0])

    def reversed(self) -> "HyperbolaSeg":
        return HyperbolaSeg(self.center, self.major_axis, self.ratio, self.end_param, self.start_param)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "HyperbolaSeg":
        return HyperbolaSeg(_rotate_point(self.center, angle, origin), _rotate_point(self.major_axis, angle, (0.0, 0.0)),
                            self.ratio, self.start_param, self.end_param)

    def translated(self, dx: float, dy: float) -> "HyperbolaSeg":
        return HyperbolaSeg(_translate_point(self.center, dx, dy), self.major_axis, self.ratio,
                            self.start_param, self.end_param)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "HyperbolaSeg":
        """Like the ellipse: a mirror flips the second axis, the point at `s` goes to `−s`."""
        return HyperbolaSeg(_mirror_point(self.center, origin, angle), _mirror_point(self.major_axis, (0.0, 0.0), angle),
                            self.ratio, -self.start_param, -self.end_param)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "HyperbolaSeg":
        factor = _check_factor(factor)
        return HyperbolaSeg(_scale_point(self.center, factor, origin),
                            (self.major_axis[0] * factor, self.major_axis[1] * factor),
                            self.ratio, self.start_param, self.end_param)
