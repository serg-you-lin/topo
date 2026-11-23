"""
topo/core/geometry/spline_fit.py
---------------------------------
B-splines for an ordered sequence of points: interpolating (through all of
them) and approximating (the least rich that stays within a tolerance).
"""

import math
from typing import Tuple, List
import numpy as np

from .points import Point


def interpolate_bspline(points: List[Point], degree: int = 3) -> Tuple[List[Point], List[float]]:
    """B-spline of degree `degree` through all the `points` (global interpolation,
    Piegl & Tiller 9.2.1): chord-length parameters, "natural" knots for odd
    degree and averaged for even degree. Returns `(control_points, knots)`,
    knots normalized in [0, 1]."""
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
    """The n+1 basis functions N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2)."""
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
    """Spline of degree `degree` with `count` control points, least squares on the
    points, first and last fixed (Piegl & Tiller 9.4.1, knots by averaging, eq.
    9.68-9.69). Returns `(control, knots, max_error)`: the error is the distance
    of each point from the curve at its parameter, which bounds the true
    distance from the curve from above."""
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
    """The degree-`degree` B-spline with fewer control points that passes through
    the first and last point and stays within `tolerance` of all the others
    (least squares, Piegl & Tiller 9.4.1). On noisy or irregularly spaced points
    it does not oscillate like the one interpolating them all; when no
    approximation is enough it is the interpolation itself (`interpolate_bspline`).
    Returns `(control_points, knots)`, knots in [0, 1]."""
    if len(points) <= degree + 1:
        return interpolate_bspline(points, degree)
    pts = np.array(points, dtype=np.float64)
    t = _chord_params(points)
    lo, hi = degree, len(points)   # `lo` is never enough (fewer than degree+1 controls), `hi` is the interpolation
    best = None
    # double until enough, then bisect between the last that is not enough and the first that is
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
