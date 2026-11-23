"""
topo/core/geometry/spline_fit.py
---------------------------------
B-spline per una sequenza ordinata di punti: interpolante (passa per tutti)
e approssimante (la meno ricca che resta entro una tolleranza) (MAP.md D141).
"""

import math
from typing import Tuple, List
import numpy as np

from .points import Point


def interpolate_bspline(points: List[Point], degree: int = 3) -> Tuple[List[Point], List[float]]:
    """
    B-spline di grado `degree` che passa per tutti i `points` (interpolazione
    globale, Piegl & Tiller cap. 9.2.1): parametri per lunghezza di corda,
    nodi "natural" per grado dispari e mediati per grado pari. Ritorna
    `(control_points, knots)`, nodi normalizzati in [0, 1].
    """
    n = len(points) - 1
    p = degree
    if n < p:
        raise ValueError(f"a spline of degree {p} needs at least {p + 1} points")

    dists = [math.dist(points[i], points[i + 1]) for i in range(n)]
    total = sum(dists)
    if total > 0:
        t, acc = [0.0], 0.0
        for d in dists:
            acc += d
            t.append(acc / total)
        t[-1] = 1.0
    else:
        t = [i / n for i in range(n + 1)]

    if p % 2:
        inner = t[2:n - p + 2]
    else:
        inner = [sum(t[j:j + p]) / p for j in range(1, n - p + 1)]
    knots = [0.0] * (p + 1) + list(inner) + [1.0] * (p + 1)

    basis = np.array([_bspline_basis_row(u, p, knots, n) for u in t])
    control = np.linalg.solve(basis, np.array(points, dtype=np.float64))
    return [(float(x), float(y)) for x, y in control], knots


def _bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]:
    """Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2)."""
    row = [0.0] * (n + 1)
    if u >= knots[n + 1]:
        row[n] = 1.0
        return row
    span = p
    while span < n and knots[span + 1] <= u:
        span += 1
    funcs = [1.0] + [0.0] * p
    left, right = [0.0] * (p + 1), [0.0] * (p + 1)
    for j in range(1, p + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            temp = funcs[r] / (right[r + 1] + left[j - r])
            funcs[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        funcs[j] = saved
    for j in range(p + 1):
        row[span - p + j] = funcs[j]
    return row


def _chord_params(points: List[Point]) -> List[float]:
    dists = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(dists)
    if total == 0:
        return [i / (len(points) - 1) for i in range(len(points))]
    t, acc = [0.0], 0.0
    for d in dists:
        acc += d
        t.append(acc / total)
    t[-1] = 1.0
    return t


def _least_squares(points: np.ndarray, t: List[float], degree: int, count: int):
    """
    Spline di grado `degree` con `count` punti di controllo ai minimi quadrati
    sui punti, primo e ultimo fissati (Piegl & Tiller 9.4.1, nodi per media,
    eq. 9.68-9.69). Ritorna `(control, knots, max_error)`: l'errore è la
    distanza di ogni punto dalla curva al suo parametro, che maggiora la
    distanza vera dalla curva.
    """
    m, n, p = len(points) - 1, count - 1, degree
    d = (m + 1) / (n - p + 1)
    inner = []
    for j in range(1, n - p + 1):
        i = int(j * d)
        alpha = j * d - i
        inner.append((1 - alpha) * t[i - 1] + alpha * t[i])
    knots = [0.0] * (p + 1) + inner + [1.0] * (p + 1)
    basis = np.array([_bspline_basis_row(u, p, knots, n) for u in t])
    q0, qm = points[0], points[-1]
    rhs = points[1:-1] - np.outer(basis[1:-1, 0], q0) - np.outer(basis[1:-1, n], qm)
    inner_ctrl, *_ = np.linalg.lstsq(basis[1:-1, 1:n], rhs, rcond=None)
    control = np.vstack([q0, inner_ctrl, qm])
    error = float(np.max(np.hypot(*(basis @ control - points).T)))
    return control, knots, error


def approximate_bspline(points: List[Point], degree: int, tolerance: float) -> Tuple[List[Point], List[float]]:
    """
    La B-spline di grado `degree` con meno punti di controllo che passa per il
    primo e l'ultimo punto e resta entro `tolerance` da tutti gli altri
    (minimi quadrati, Piegl & Tiller 9.4.1). Su punti rumorosi o a passo
    irregolare non oscilla come quella che li interpola tutti; quando nessuna
    approssimazione basta è l'interpolazione stessa (`interpolate_bspline`).
    Ritorna `(control_points, knots)`, nodi in [0, 1].
    """
    if len(points) <= degree + 1:
        return interpolate_bspline(points, degree)
    pts = np.array(points, dtype=np.float64)
    t = _chord_params(points)
    lo, hi = degree, len(points)   # `lo` non basta mai (meno di degree+1 controlli), `hi` è l'interpolazione
    best = None
    # raddoppia finché basta, poi bisezione fra l'ultimo che non basta e il primo che basta
    count = degree + 1
    while count < hi:
        control, knots, error = _least_squares(pts, t, degree, count)
        if error <= tolerance:
            best = (control, knots)
            break
        lo, count = count, min(hi, count * 2)
    if best is None:
        return interpolate_bspline(points, degree)
    hi = count
    while hi - lo > 1:
        mid = (lo + hi) // 2
        control, knots, error = _least_squares(pts, t, degree, mid)
        if error <= tolerance:
            hi, best = mid, (control, knots)
        else:
            lo = mid
    control, knots = best
    return [(float(x), float(y)) for x, y in control], [float(k) for k in knots]
