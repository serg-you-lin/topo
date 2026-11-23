"""
topo/core/geometry/concentric.py
--------------------------------
Geometric facts between several contours: concentric circles, arcs around a
circle. What they are and with which thresholds is the consumer's call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from .measure import FLOAT_NOISE, noise_runs
from .shape import CIRCLE, ContourShape, contour_shape
from ..primitives.conics import CircleSeg, is_arc

Point = Tuple[float, float]



@dataclass(frozen=True)
class ConcentricGroup:
    """
    Circular contours with the same center, from smallest to largest radius.

    center: center of the smallest circle (the group's reference)
    items:  the contours, in radius order
    shapes: the `ContourShape` of each, in the same order
    """
    center: Point
    items: tuple
    shapes: Tuple[ContourShape, ...]

    @property
    def diameters(self) -> Tuple[float, ...]:
        return tuple(s.length for s in self.shapes)


def concentric_groups(items, *, tolerance: float) -> list[ConcentricGroup]:
    """Partition of the circular contours of `items` by centre: every circle is in
    exactly one group, even alone. A circle joins, among the groups whose centre
    is at most `tolerance` from its own, the nearest one; non-circular ones do
    not appear. Groups sorted by centre (x, y), ties within noise."""
    circles = sorted(((k, item, shape) for k, item in enumerate(items)
                      if (shape := contour_shape(item)) is not None and shape.kind == CIRCLE),
                     key=lambda c: c[2].length)
    # equal diameter within the noise: the given order decides, which a motion does not change
    circles = [c for run in noise_runs(circles, lambda a, b: b[2].length - a[2].length <= FLOAT_NOISE)
               for c in sorted(run, key=lambda c: c[0])]
    groups: list[list] = []
    for _, item, shape in circles:
        near = [(math.dist(g[0][1].center, shape.center), g) for g in groups]
        near = [(d, g) for d, g in near if d <= tolerance]
        if not near:
            groups.append([(item, shape)])
            continue
        closest = min(d for d, _ in near)
        # equidistant within the noise: the group born first
        next(g for d, g in near if d - closest <= FLOAT_NOISE).append((item, shape))
    out = [ConcentricGroup(tuple(g[0][1].center), tuple(i for i, _ in g), tuple(s for _, s in g))
           for g in groups]
    by_x = sorted(out, key=lambda g: g.center[0])
    return [g for run in noise_runs(by_x, lambda a, b: b.center[0] - a.center[0] <= FLOAT_NOISE)
            for g in sorted(run, key=lambda g: g.center[1])]


@dataclass(frozen=True)
class ArcAround:
    """
    An arc concentric with a circle and larger than it.

    arc:          the `CircleSeg`
    sweep:        swept angle, in degrees
    radius_ratio: arc radius / circle radius (> 1)
    """
    arc: CircleSeg
    sweep: float
    radius_ratio: float


def arcs_around(center: Point, radius: float, arcs,
                *, tolerance: float) -> list[ArcAround]:
    """
    The arcs of `arcs` with center within `tolerance` of `center` and radius
    larger than `radius`, from the nearest to the circle to the farthest.
    """
    out = [ArcAround(a, math.degrees(a._sweep()), a.radius / radius) for a in arcs
           if is_arc(a) and a.radius > radius and math.dist(a.center, center) <= tolerance]
    return sorted(out, key=lambda a: a.radius_ratio)
