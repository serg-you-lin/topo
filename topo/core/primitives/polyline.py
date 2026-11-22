"""
topo/core/primitives/polyline.py
--------------------------------
La distanza di un punto da una corda: il controllo dei poligoni delle curve
(la spline per dimostrazione, D299; la formula adattiva, D289).
"""

from __future__ import annotations

import math

from .mathseg import Point


def _point_to_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distanza perpendicolare di `p` dal segmento `a`-`b` (0 se `a == b`)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = a[0] + t * dx, a[1] + t * dy
    return math.hypot(p[0] - cx, p[1] - cy)
