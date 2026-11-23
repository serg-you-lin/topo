"""
topo/core/primitives/motion.py
------------------------------
Rigid moves and scaling of a point: rotation, translation, mirror, scale.
Every primitive moves by moving its points with these.
"""

from __future__ import annotations

import math

from .mathseg import Point

def _rotate_point(pt: Point, angle: float, origin: Point) -> Point:
    """`pt` rotated by `angle` radians (CCW) about `origin`."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return (ox + x * cos_a - y * sin_a, oy + x * sin_a + y * cos_a)


def _translate_point(pt: Point, dx: float, dy: float) -> Point:
    """`pt` shifted by (`dx`, `dy`)."""
    return (pt[0] + dx, pt[1] + dy)


def _mirror_point(pt: Point, origin: Point = (0.0, 0.0), angle: float = 0.0) -> Point:
    """`pt` mirrored on the line through `origin` at `angle` radians from the
    x axis (default: the x axis, y → −y)."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_2a, sin_2a = math.cos(2 * angle), math.sin(2 * angle)
    return (ox + x * cos_2a + y * sin_2a, oy + x * sin_2a - y * cos_2a)


def _scale_point(pt: Point, factor: float, origin: Point) -> Point:
    """`pt` scaled by `factor` about `origin`."""
    ox, oy = origin
    return (ox + (pt[0] - ox) * factor, oy + (pt[1] - oy) * factor)


def _check_factor(factor: float) -> float:
    """A scale factor: positive and finite. A negative one is a rotation
    by π plus a scale, and must be asked for that way."""
    factor = float(factor)
    if not (factor > 0 and math.isfinite(factor)):
        raise ValueError(f"the scale factor must be positive and finite, got {factor}")
    return factor
