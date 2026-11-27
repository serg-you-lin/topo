"""
topo/core/primitives/line.py
----------------------------
`LineSeg`: the straight piece from `start` to `end`, and the distance of a point from such a piece.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from .mathseg import Algebra, DEFAULT_TOLERANCE, MathSeg, Point, _plain
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point


def distance_to_segment(p: Point, a: Point, b: Point) -> float:
    """Distance of `p` from the segment `a`-`b` (point distance if `a == b`)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy)


@dataclass
class LineSeg(MathSeg):
    """The straight piece from `start` to `end`: P(t) = start + t·(end − start), t in [0, 1]."""
    start: Point
    end: Point

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, 1.0)

    @property
    def algebra(self) -> Algebra:
        return "polynomial"

    def point_at(self, t: float) -> Point:
        return (self.start[0] + t * (self.end[0] - self.start[0]), self.start[1] + t * (self.end[1] - self.start[1]))

    def derivative_at(self, t: float) -> Point:
        return (self.end[0] - self.start[0], self.end[1] - self.start[1])

    def endpoints(self) -> Tuple[Point, Point]:
        return self.start, self.end

    def __post_init__(self):
        self.start, self.end = _plain(self.start), _plain(self.end)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """The two endpoints: a line is already exact (`tolerance` is unused)."""
        return [self.start, self.end]

    def reversed(self) -> "LineSeg":
        """The same line walked the other way."""
        return LineSeg(start=self.end, end=self.start)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """The line rotated by `angle` radians about `origin`."""
        return LineSeg(
            start=_rotate_point(self.start, angle, origin),
            end=_rotate_point(self.end, angle, origin),
        )

    def translated(self, dx: float, dy: float) -> "LineSeg":
        """The line moved by (`dx`, `dy`)."""
        return LineSeg(start=_translate_point(self.start, dx, dy), end=_translate_point(self.end, dx, dy))

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "LineSeg":
        """The line mirrored on the line through `origin` at `angle` radians
        (default: the x axis, y → −y)."""
        return LineSeg(start=_mirror_point(self.start, origin, angle),
                       end=_mirror_point(self.end, origin, angle))

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """The line scaled by `factor` (> 0) about `origin`."""
        factor = _check_factor(factor)
        return LineSeg(start=_scale_point(self.start, factor, origin),
                       end=_scale_point(self.end, factor, origin))
