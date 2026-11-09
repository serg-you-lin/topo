"""
topo/core/geometry/build.py
----------------------------
Costruire forme regolari come segmenti di topo: un giro chiuso, pronto per
`topo.load_segments`. Gli argomenti sono quelli che `contour_shape` restituisce
(centro, lunghezza, larghezza, angolo): costruire e leggere usano le stesse
misure, così `contour_shape(rectangle(...))` ridà i numeri passati (MAP.md D96).
Archi veri, non poligonali: è la differenza da un poligono di shapely.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..primitives.segments import ArcSeg, CircleSeg, EllipseSeg, LineSeg

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
        ArcSeg(center=c2, radius=r, start_angle=a - math.pi / 2, end_angle=a + math.pi / 2, ccw=True),
        LineSeg(start=p3, end=p4),
        ArcSeg(center=c1, radius=r, start_angle=a + math.pi / 2, end_angle=a + 3 * math.pi / 2, ccw=True),
    ]
