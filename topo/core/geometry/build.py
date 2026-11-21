"""
topo/core/geometry/build.py
----------------------------
Costruire forme e curve come segmenti di topo. Le forme sono un giro chiuso,
pronto per `topo.load_segments`, con gli argomenti che `contour_shape`
restituisce (centro, lunghezza, larghezza, angolo): costruire e leggere usano
le stesse misure, così `contour_shape(rectangle(...))` ridà i numeri passati
(MAP.md D96). Le curve (D291) sono pezzi aperti: il raccordo fra due capi, il
grafico di un polinomio, l'evolvente, la clotoide. Curve vere, non
poligonali; gli angoli di posizione in gradi, come per le forme.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..primitives.segments import BSplineSeg, LineSeg
from ..primitives.conics import CircleSeg, EllipseSeg
from ..primitives.clothoid import ClothoidSeg
from ..primitives.formula import FormulaSeg

Point = Tuple[float, float]


def _place(points: Sequence[Point], center: Point, angle: float) -> List[Point]:
    """Ruota di `angle` gradi attorno all'origine e trasla in `center`."""
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(center[0] + x * c - y * s, center[1] + x * s + y * c) for x, y in points]


def polygon(points: Sequence[Point]) -> List[LineSeg]:
    """The polygon through the given `points`, closed: the last side returns to the first point. At least 3 points."""
    pts = [tuple(p) for p in points]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        raise ValueError(f"polygon(): needs at least 3 distinct points, got {len(pts)}")
    return [LineSeg(start=pts[i], end=pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def rectangle(length: float, width: float, *, center: Point = (0.0, 0.0), angle: float = 0.0) -> List[LineSeg]:
    """Rectangle of `length` × `width` centered at `center`, with the long side at `angle` degrees."""
    h, w = length / 2, width / 2
    return polygon(_place([(-h, -w), (h, -w), (h, w), (-h, w)], center, angle))


def regular_polygon(sides: int, radius: float, *, center: Point = (0.0, 0.0), angle: float = 0.0) -> List[LineSeg]:
    """Regular polygon with `sides` sides inscribed in the circle of radius `radius`; first vertex at `angle` degrees."""
    if sides < 3:
        raise ValueError(f"regular_polygon(): needs at least 3 sides, got {sides}")
    step = 2 * math.pi / sides
    return polygon(_place([(radius * math.cos(k * step), radius * math.sin(k * step)) for k in range(sides)],
                          center, angle))


def circle(radius: float, *, center: Point = (0.0, 0.0)) -> List[CircleSeg]:
    """The circle of radius `radius` at `center`."""
    return [CircleSeg(center=tuple(center), radius=radius)]


def ellipse(length: float, width: float, *, center: Point = (0.0, 0.0), angle: float = 0.0) -> List[EllipseSeg]:
    """
    The ellipse with axes `length` × `width` centered at `center`, long axis
    at `angle` degrees. `length` >= `width` > 0.
    """
    if not length >= width > 0:
        raise ValueError(f"ellipse(): needs length >= width > 0, got {length} x {width}")
    a = math.radians(angle)
    major = (length / 2 * math.cos(a), length / 2 * math.sin(a))
    return [EllipseSeg(center=tuple(center), major_axis=major, ratio=width / length,
                       start_param=0.0, end_param=2 * math.pi)]


def stadium(length: float, width: float, *, center: Point = (0.0, 0.0), angle: float = 0.0) -> list:
    """
    Stadium of overall `length` × `width` (two semicircles of radius
    `width / 2` joined by two parallel sides), long axis at `angle` degrees.
    `length` > `width`.
    """
    if length <= width:
        raise ValueError(f"stadium(): length ({length}) must exceed width ({width})")
    r, half = width / 2, (length - width) / 2
    a = math.radians(angle)
    (p1, p2, p3, p4) = _place([(-half, -r), (half, -r), (half, r), (-half, r)], center, angle)
    (c1, c2) = _place([(-half, 0.0), (half, 0.0)], center, angle)
    return [
        LineSeg(start=p1, end=p2),
        CircleSeg(center=c2, radius=r, start_angle=a - math.pi / 2, end_angle=a + math.pi / 2, ccw=True),
        LineSeg(start=p3, end=p4),
        CircleSeg(center=c1, radius=r, start_angle=a + math.pi / 2, end_angle=a + 3 * math.pi / 2, ccw=True),
    ]


def triangle(a: float, b: float, c: float, *, start: Point = (0.0, 0.0), angle: float = 0.0) -> List[LineSeg]:
    """
    The triangle with sides `a`, `b`, `c`: side `a` from `start` at `angle`
    degrees, then `b`, then `c` back to `start`, counter-clockwise. Each side
    shorter than the other two together.
    """
    if not (a > 0 and b > 0 and c > 0 and a < b + c and b < a + c and c < a + b):
        raise ValueError(f"triangle(): sides {a}, {b}, {c} do not close a triangle")
    # il terzo vertice dal teorema del coseno, nell'angolo fra `a` e `c`
    x = (a * a + c * c - b * b) / (2 * a)
    y = math.sqrt(max(c * c - x * x, 0.0))
    return polygon([tuple(start)] + _place([(a, 0.0), (x, y)], start, angle))


def right_triangle(leg_a: float, leg_b: float, *, start: Point = (0.0, 0.0), angle: float = 0.0) -> List[LineSeg]:
    """
    The right triangle with legs `leg_a` and `leg_b` and the right angle at
    `start`: `leg_a` leaves at `angle` degrees, `leg_b` at `angle` + 90°,
    counter-clockwise. The hypotenuse is √(leg_a² + leg_b²).
    """
    if not (leg_a > 0 and leg_b > 0):
        raise ValueError(f"right_triangle(): legs must be positive, got {leg_a}, {leg_b}")
    return polygon([tuple(start)] + _place([(leg_a, 0.0), (0.0, leg_b)], start, angle))


def _unit(v: Point, name: str) -> Point:
    n = math.hypot(*v)
    if not n > 0:
        raise ValueError(f"blend(): {name} must be a non-zero vector")
    return v[0] / n, v[1] / n


def blend(start: Point, start_direction: Point, end: Point, end_direction: Point, *,
          continuity: int = 1) -> List[BSplineSeg]:
    """
    The smooth curve from `start`, leaving along `start_direction`, to `end`,
    arriving along `end_direction` (vectors, any length): a polynomial, so an
    exact B-spline. `continuity=1`: a cubic, tangent to both directions (G1).
    `continuity=2`: a quintic that also starts and ends with zero curvature,
    so it joins two straight lines with continuous curvature (G2). The
    handles are a fraction of the chord: a third (cubic), a fifth (quintic).
    """
    (ux, uy), (vx, vy) = _unit(start_direction, "start_direction"), _unit(end_direction, "end_direction")
    p0, p1 = tuple(start), tuple(end)
    chord = math.dist(p0, p1)
    if not chord > 0:
        raise ValueError("blend(): start and end coincide")
    if continuity == 1:
        h = chord / 3
        control = [p0, (p0[0] + h * ux, p0[1] + h * uy), (p1[0] - h * vx, p1[1] - h * vy), p1]
    elif continuity == 2:
        # derivata seconda nulla ai capi: P2 − 2·P1 + P0 = 0, e lo stesso all'altro capo
        h = chord / 5
        control = [p0, (p0[0] + h * ux, p0[1] + h * uy), (p0[0] + 2 * h * ux, p0[1] + 2 * h * uy),
                   (p1[0] - 2 * h * vx, p1[1] - 2 * h * vy), (p1[0] - h * vx, p1[1] - h * vy), p1]
    else:
        raise ValueError(f"blend(): continuity is 1 (tangent) or 2 (curvature), got {continuity}")
    degree = len(control) - 1
    return [BSplineSeg(degree=degree, control_points=control, knots=[0.0] * (degree + 1) + [1.0] * (degree + 1))]


def polynomial(coefficients: Sequence[float], x_from: float, x_to: float) -> list:
    """
    The graph of y = c0 + c1·x + c2·x² + … for x from `x_from` to `x_to`, with
    `coefficients` = (c0, c1, c2, …): exactly a Bézier curve (Bernstein basis),
    a `BSplineSeg` of the polynomial's degree; a straight `LineSeg` up to degree 1.
    """
    c = [float(v) for v in coefficients]
    while len(c) > 1 and c[-1] == 0:
        c.pop()
    if not c or x_from == x_to:
        raise ValueError("polynomial(): needs coefficients and x_from != x_to")
    w = x_to - x_from
    n = len(c) - 1
    # y nel parametro u ∈ [0, 1] con x = x_from + w·u: b_j = Σ_k c_k · C(k, j) · x_from^(k − j) · w^j
    b = [sum(c[k] * math.comb(k, j) * x_from ** (k - j) * w ** j for k in range(j, n + 1)) for j in range(n + 1)]
    if n <= 1:
        slope = b[1] if n == 1 else 0.0
        return [LineSeg(start=(x_from, b[0]), end=(x_to, b[0] + slope))]
    # dalla base delle potenze a quella di Bernstein: y_i = Σ_{j ≤ i} C(i, j) / C(n, j) · b_j
    ys = [sum(math.comb(i, j) / math.comb(n, j) * b[j] for j in range(i + 1)) for i in range(n + 1)]
    control = [(x_from + w * i / n, ys[i]) for i in range(n + 1)]
    return [BSplineSeg(degree=n, control_points=control, knots=[0.0] * (n + 1) + [1.0] * (n + 1))]


def involute(base_radius: float, end: float, *, start: float = 0.0, center: Point = (0.0, 0.0),
             angle: float = 0.0) -> List[FormulaSeg]:
    """
    The involute of the circle of radius `base_radius` at `center`: the path
    of the end of a string unwound from it, from unwinding angle `start` to
    `end` (radians, the formula's own parameter), starting on the circle at
    `angle` degrees. x = r·(cos t + t·sin t), y = r·(sin t − t·cos t).
    """
    if not base_radius > 0:
        raise ValueError(f"involute(): base_radius must be positive, got {base_radius}")
    seg = FormulaSeg("r*(cos(t) + t*sin(t))", "r*(sin(t) - t*cos(t))", start, end, params={"r": base_radius})
    return [seg.rotated(math.radians(angle)).translated(*center)]


def clothoid(a: float, length: float, *, start: Point = (0.0, 0.0), angle: float = 0.0,
             left: bool = True) -> List[ClothoidSeg]:
    """
    The clothoid (Euler spiral) with parameter `a` (a² = radius · arc length),
    from zero curvature at `start`, leaving at `angle` degrees, for `length`
    along the curve, turning left (counter-clockwise) when `left`. At the end
    the radius is a² / `length`.
    """
    if not length > 0:
        raise ValueError(f"clothoid(): length must be positive, got {length}")
    return [ClothoidSeg(origin=tuple(start), angle=math.radians(angle), a=a, start_param=0.0, end_param=length,
                        left=left)]
