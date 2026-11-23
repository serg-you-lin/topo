"""
topo/core/geometry/curve_tests.py
----------------------------------
I punti di una sequenza stanno su una curva entro una tolleranza? Corda,
cerchio per tre punti, conica (ellisse o iperbole), curva liscia (MAP.md D141).
"""

import math
from typing import Optional, Tuple, List
import numpy as np

from ...precision import FLOAT_NOISE
from .points import Point, circle_through, offset_from_line
from .spline_fit import _chord_params, _least_squares


def within_chord(points: List[Point], tolerance: float) -> bool:
    """Tutti i punti entro `tolerance` dalla corda primo-ultimo."""
    a, b = points[0], points[-1]
    return all(abs(offset_from_line(p, a, b)) <= tolerance for p in points[1:-1])


def within_circle_through(points: List[Point], tolerance: float) -> Optional[Tuple[Point, float]]:
    """(centro, raggio) del cerchio per il primo, quello a metà e l'ultimo punto, se
    tutti i punti stanno entro `tolerance` da lui; None altrimenti."""
    circle = circle_through(points[0], points[len(points) // 2], points[-1])
    if circle is None:
        return None
    center, radius = circle
    if any(abs(math.dist(center, p) - radius) > tolerance for p in points):
        return None
    return circle


def _ellipse_distance(p: Point, center: Point, axis: Point, a: float, b: float) -> Tuple[float, float]:
    """(distanza, parametro) del punto dell'ellisse più vicino a `p`: Newton sul
    parametro, partendo dall'angolo di `p` nel cerchio unitario dell'ellisse."""
    dx, dy = p[0] - center[0], p[1] - center[1]
    x, y = dx * axis[0] + dy * axis[1], -dx * axis[1] + dy * axis[0]
    t = math.atan2(y * a, x * b)
    for _ in range(30):
        c, s = math.cos(t), math.sin(t)
        # derivata (a meno di 2) della distanza al quadrato, e la sua derivata
        g = (a * a - b * b) * s * c - x * a * s + y * b * c
        h = (a * a - b * b) * (c * c - s * s) - x * a * c - y * b * s
        if h == 0:
            break
        step = g / h
        t -= step
        if abs(step) <= FLOAT_NOISE / a:
            break
    return math.hypot(x - a * math.cos(t), y - b * math.sin(t)), t


def _hyperbola_distance(p: Point, center: Point, axis: Point, a: float, b: float) -> Tuple[float, float]:
    """(distanza, parametro) del punto del ramo x' = a·cosh s, y' = b·sinh s più
    vicino a `p`: Newton sul parametro, partendo da asinh(y'/b)."""
    dx, dy = p[0] - center[0], p[1] - center[1]
    x, y = dx * axis[0] + dy * axis[1], -dx * axis[1] + dy * axis[0]
    s = math.asinh(y / b)
    for _ in range(30):
        ch, sh = math.cosh(s), math.sinh(s)
        # derivata (a meno di 2) della distanza al quadrato, e la sua derivata
        g = (a * a + b * b) * sh * ch - x * a * sh - y * b * ch
        h = (a * a + b * b) * (ch * ch + sh * sh) - x * a * ch - y * b * sh
        if h == 0:
            break
        step = g / h
        s -= step
        if abs(step) * max(a, b) <= FLOAT_NOISE:
            break
    return math.hypot(x - a * math.cosh(s), y - b * math.sinh(s)), s


def within_conic_through(points: List[Point], tolerance: float) -> Optional[Tuple[str, Point, Point, float, List[float]]]:
    """("ellipse" | "hyperbola", centro, vettore del semiasse reale, rapporto b/a,
    parametro di ogni punto) della conica che passa esatta per il primo e
    l'ultimo punto, se tutti i punti stanno entro `tolerance` da lei; None
    altrimenti. La conica ai minimi quadrati algebrici col vincolo dei capi; il
    segno di B² − 4AC dice quale (D284, D294). Più punti dei 5 che fissano una
    conica, se no il test non dice nulla; un'iperbole su un ramo solo."""
    if len(points) < 6:
        return None
    pts = np.asarray(points, dtype=np.float64)
    origin = pts.mean(axis=0)
    size = float(np.ptp(pts, axis=0).max())
    if size <= 0:
        return None
    # nel riferimento dei punti, a misura dei punti: x² su coordinate grandi cancella le cifre
    x, y = (pts[:, 0] - origin[0]) / size, (pts[:, 1] - origin[1]) / size
    rows = np.column_stack([x * x, x * y, y * y, x, y, np.ones_like(x)])
    ends = rows[[0]] if math.dist(points[0], points[-1]) <= FLOAT_NOISE else rows[[0, -1]]
    _, sv, vt = np.linalg.svd(ends)
    free = vt[np.count_nonzero(sv > FLOAT_NOISE * sv[0]):].T
    _, _, wt = np.linalg.svd(rows @ free)
    A, B, C, D, E, F = free @ wt[-1]
    det = 4 * A * C - B * B
    if det == 0:
        return None
    cx, cy = (B * E - 2 * C * D) / det, (B * D - 2 * A * E) / det
    value = A * cx * cx + B * cx * cy + C * cy * cy + D * cx + E * cy + F
    w, v = np.linalg.eigh(np.array([[A, B / 2], [B / 2, C]]))
    center = (float(cx * size + origin[0]), float(cy * size + origin[1]))
    if det > 0:
        if not (-value / w[0] > 0 and -value / w[1] > 0):
            return None
        # il semiasse maggiore va col valore proprio più piccolo in modulo
        real = int(np.argmin(np.abs(w)))
        kind, distance = "ellipse", _ellipse_distance
    else:
        # x'²/a² − y'²/b² = 1: l'asse reale è quello con −value/λ positivo
        real = 0 if -value / w[0] > 0 else 1
        if not (-value / w[real] > 0 and value / w[1 - real] > 0):
            return None
        kind, distance = "hyperbola", _hyperbola_distance
    a = math.sqrt(-value / w[real]) * size
    b = math.sqrt(abs(value / w[1 - real])) * size
    axis = (float(v[0, real]), float(v[1, real]))
    if kind == "hyperbola":
        # il ramo dei punti: x' > 0 lungo l'asse
        mx, my = points[len(points) // 2]
        if (mx - center[0]) * axis[0] + (my - center[1]) * axis[1] < 0:
            axis = (-axis[0], -axis[1])
    params = []
    for p in points:
        gap, t = distance(p, center, axis, a, b)
        if gap > tolerance:
            return None
        params.append(t)
    return kind, center, (axis[0] * a, axis[1] * a), b / a, params


def within_smooth_curve(points: List[Point], tolerance: float) -> bool:
    """Una curva liscia passa entro `tolerance` da tutti i punti: la cubica a un
    tratto ai minimi quadrati coi capi fissi (`_least_squares`, il cui errore
    maggiora la distanza vera). Un arco no: una curva liscia non è per forza un
    arco, la curvatura può cambiare (D283)."""
    if len(points) < 5:
        return within_chord(points, tolerance)
    _, _, error = _least_squares(np.array(points, dtype=np.float64), _chord_params(points), 3, 4)
    return error <= tolerance
