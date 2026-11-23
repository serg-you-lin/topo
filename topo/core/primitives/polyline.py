"""
topo/core/primitives/polyline.py
--------------------------------
Distance of a point from a chord: the check on the control polygons of curves
(the spline by proof, the adaptive formula).
"""

from __future__ import annotations

import math

from .mathseg import Point


def _point_to_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distance of `p` from the segment `a`-`b` (point distance if `a == b`)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy)
