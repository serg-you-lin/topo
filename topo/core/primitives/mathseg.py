"""
topo/core/primitives/mathseg.py
-------------------------------
La madre di ogni primitiva (D285): `MathSeg`, una curva data dalla sua
matematica — un punto e una derivata esatta per ogni `t` di `t_range`. Qui
anche quello che vale per tutte: `Point`, `DEFAULT_TOLERANCE`, `Algebra`
(D295), gli estremi e la chiusura di un segmento qualunque.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Literal, Tuple

from ...precision import SAME_POINT

Point = Tuple[float, float]


def _real(x) -> float:
    """Un numero come float Python finito: una coordinata NaN o infinita non ha
    posizione, la primitiva la rifiuta come una curva di misura nulla (D154, D190)."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError(f"not a finite number: {x}")
    return x


def _plain(p) -> Point:
    """Un punto come tupla di float Python finiti: chi passa numpy o i tipi di un'altra libreria non
    lo ritrova nei campi pubblici (D169)."""
    return tuple(_real(c) for c in p)



# Tolleranza predefinita se non specificata
DEFAULT_TOLERANCE = SAME_POINT  # sagitta dei poligoni, D275


# che matematica scrive esatta una curva (MathSeg.algebra)
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
    """
    (start, end) di un segmento primitivo, in coordinate XY non arrotondate.

    Unica sede di questo calcolo — usata dall'adapter per costruire gli Edge e
    dal gap solver per lavorare su geometria pura.
    """
    if isinstance(segment, MathSeg):
        return segment.endpoints()
    return (0.0, 0.0), (0.0, 0.0)


def segment_is_closed(segment, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """
    True se gli endpoint del segmento coincidono entro ``tolerance``.

    Unica sede del test di chiusura di un segmento primitivo — usata
    dall'adapter per riconoscere le spline chiuse (loop degenere).
    """
    start, end = segment_endpoints(segment)
    return math.hypot(start[0] - end[0], start[1] - end[1]) < tolerance
