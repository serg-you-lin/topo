"""
topo/core/primitives/motion.py
------------------------------
Le mosse rigide e la scala di un punto: rotazione, traslazione, specchio,
scala. Ogni primitiva si muove muovendo i suoi punti con queste.
"""

from __future__ import annotations

import math

from .mathseg import Point

def _rotate_point(pt: Point, angle: float, origin: Point) -> Point:
    """Ruota `pt` di `angle` radianti (CCW) attorno a `origin`."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return (ox + x * cos_a - y * sin_a, oy + x * sin_a + y * cos_a)


def _translate_point(pt: Point, dx: float, dy: float) -> Point:
    """`pt` spostato di (`dx`, `dy`)."""
    return (pt[0] + dx, pt[1] + dy)


def _mirror_point(pt: Point, origin: Point = (0.0, 0.0), angle: float = 0.0) -> Point:
    """`pt` specchiato sulla retta per `origin` inclinata di `angle` radianti
    sull'asse x (default: l'asse x, y → −y)."""
    ox, oy = origin
    x, y = pt[0] - ox, pt[1] - oy
    cos_2a, sin_2a = math.cos(2 * angle), math.sin(2 * angle)
    return (ox + x * cos_2a + y * sin_2a, oy + x * sin_2a - y * cos_2a)


def _scale_point(pt: Point, factor: float, origin: Point) -> Point:
    """`pt` scalato di `factor` attorno a `origin`."""
    ox, oy = origin
    return (ox + (pt[0] - ox) * factor, oy + (pt[1] - oy) * factor)


def _check_factor(factor: float) -> float:
    """Il fattore di una scala: positivo e finito. Uno negativo è una
    rotazione di π più una scala, e va chiesto così."""
    factor = float(factor)
    if not (factor > 0 and math.isfinite(factor)):
        raise ValueError(f"the scale factor must be positive and finite, got {factor}")
    return factor
