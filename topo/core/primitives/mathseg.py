"""
topo/core/primitives/mathseg.py
-------------------------------
The parent of every primitive: `MathSeg`, a curve given by its mathematics —
a point and an exact derivative for every `t` of `t_range`. Also what holds
for all: `Point`, `DEFAULT_TOLERANCE`, `Algebra`, the endpoints and the
closure of any segment.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Literal, Tuple

from ...precision import SAME_POINT

Point = Tuple[float, float]


def _real(x) -> float:
    """A number as a finite Python float: a NaN or infinite coordinate has no
    position, so the primitive refuses it like a curve of zero measure."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"not a finite number: {x}")
    return x


def _plain(p) -> Point:
    """A point as a tuple of finite Python floats: whoever passes numpy or another
    library's types does not find them in the public fields."""
    return tuple(_real(c) for c in p)


DEFAULT_TOLERANCE = SAME_POINT  # sagitta of the polygons


Algebra = Literal["polynomial", "rational", "transcendental"]


class MathSeg(ABC):
    """
    A curve given by its mathematics: one point for every parameter `t` in
    `t_range`, walked from `t_range[0]` (the start) to `t_range[1]` (the
    end). Every topo primitive is one; what a file format called it is not
    part of it.
    """

    @property
    @abstractmethod
    def t_range(self) -> Tuple[float, float]:
        """(t0, t1): the parameter at the start and at the end, t0 < t1."""

    @abstractmethod
    def point_at(self, t: float) -> Point:
        """The point of the curve at parameter `t`."""

    @abstractmethod
    def derivative_at(self, t: float) -> Point:
        """dP/dt at parameter `t`: the direction of travel, exact."""

    @property
    @abstractmethod
    def algebra(self) -> Algebra:
        """
        "polynomial" when x(t), y(t) are polynomials, "rational" when they are
        ratios of polynomials, "transcendental" otherwise: what kind of
        mathematics writes this curve exactly, read from the curve itself.
        """

    def endpoints(self) -> Tuple[Point, Point]:
        """(start, end): the points at the two ends of `t_range`."""
        t0, t1 = self.t_range
        return self.point_at(t0), self.point_at(t1)

    @abstractmethod
    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """A polyline from start to end, every point of the curve within `tolerance` of it."""

    @abstractmethod
    def reversed(self) -> "MathSeg":
        """The same curve walked the other way."""

    @abstractmethod
    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "MathSeg":
        """The curve rotated by `angle` radians about `origin`."""

    @abstractmethod
    def translated(self, dx: float, dy: float) -> "MathSeg":
        """The curve moved by (`dx`, `dy`)."""

    @abstractmethod
    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "MathSeg":
        """The curve mirrored on the line through `origin` at `angle` radians."""

    @abstractmethod
    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "MathSeg":
        """The curve scaled by `factor` (> 0) about `origin`."""



def segment_endpoints(segment) -> Tuple[Point, Point]:
    """(start, end) of a primitive segment, unrounded XY coordinates."""
    if isinstance(segment, MathSeg):
        return segment.endpoints()
    return (0.0, 0.0), (0.0, 0.0)


def segment_is_closed(segment, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """True if the segment's endpoints coincide within ``tolerance``."""
    start, end = segment_endpoints(segment)
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance
