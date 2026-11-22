"""
topo/core/primitives/line.py
----------------------------
La retta: `LineSeg`, il tratto da `start` a `end`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .mathseg import Algebra, DEFAULT_TOLERANCE, MathSeg, Point, _plain
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point

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
        """
        Una linea è già esatta: restituisce solo i due endpoint.
        La tolleranza non serve ma la accettiamo per uniformità di interfaccia.
        """
        return [self.start, self.end]

    def reversed(self) -> "LineSeg":
        """Stessa linea, percorsa al contrario."""
        return LineSeg(start=self.end, end=self.start)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """Stessa linea, ruotata di `angle` radianti attorno a `origin`."""
        return LineSeg(
            start=_rotate_point(self.start, angle, origin),
            end=_rotate_point(self.end, angle, origin),
        )

    def translated(self, dx: float, dy: float) -> "LineSeg":
        """Stessa linea, spostata di (`dx`, `dy`)."""
        return LineSeg(start=_translate_point(self.start, dx, dy), end=_translate_point(self.end, dx, dy))

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "LineSeg":
        """Stessa linea, specchiata sulla retta per `origin` a `angle` radianti
        (default: l'asse x, y → −y)."""
        return LineSeg(start=_mirror_point(self.start, origin, angle),
                       end=_mirror_point(self.end, origin, angle))

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "LineSeg":
        """Stessa linea, scalata di `factor` (> 0) attorno a `origin`."""
        factor = _check_factor(factor)
        return LineSeg(start=_scale_point(self.start, factor, origin),
                       end=_scale_point(self.end, factor, origin))
