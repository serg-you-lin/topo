"""
topo/core/geometry/points.py
-----------------------------
Ordered sequences of points (a sampled contour: from a raster, from a
polyline that writes a curve as points): duplicates, regular spacing,
distance from a line, Douglas-Peucker, circle through three points, circle
fit. Splines are in `spline_fit.py`, the "do the points lie on a curve?"
tests in `curve_tests.py`, corners by turn in `corners.py`.
"""

import math
from typing import Optional, Tuple, List
import numpy as np

from ...precision import FLOAT_NOISE

Point = Tuple[float, float]


# Generic maths on an ordered sequence of points (x, y): it knows nothing of
# topo primitives (LineSeg/CircleSeg/...) or of how the caller will use it.
# `core/geometry/fitting.py` is the orchestrator that decides when and how to
# use it to rebuild lines/arcs/splines.

DEFAULT_DUPLICATE_TOLERANCE = FLOAT_NOISE


def drop_duplicate_points(
    points: List[Point], tolerance: float = DEFAULT_DUPLICATE_TOLERANCE
) -> List[Point]:
    """Remove consecutive points coinciding within `tolerance`."""
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        last = cleaned[-1]
        if math.hypot(p[0] - last[0], p[1] - last[1]) > tolerance:
            cleaned.append(p)
    return cleaned


def fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]:
    """Least-squares algebraic (Kasa) fit of a circle on `points`: minimizes
    `x²+y²+Dx+Ey+F=0`, a circle of centre `(-D/2,-E/2)` and a radius derived from
    `D,E,F`. Returns `(center, radius, max_residual)` — `max_residual` is the
    largest deviation of a point from the fitted circle, to decide whether to
    accept it. `None` if the fit is degenerate (fewer than 3 points, nearly
    collinear points, non-real radius)."""
    if len(points) < 3:
        return None

    pts = np.asarray(points, dtype=float)[:, :2]
    # in the frame of the points: x²+y² on large coordinates cancels digits, and
    # the circle would depend on where the drawing sits
    origin = pts.mean(axis=0)
    x, y = pts[:, 0] - origin[0], pts[:, 1] - origin[1]
    a_matrix = np.column_stack([x, y, np.ones_like(x)])
    b_vector = -(x**2 + y**2)
    try:
        (d, e, f), *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    except np.linalg.LinAlgError:
        return None

    local = (-d / 2.0, -e / 2.0)
    radius_sq = (d**2 + e**2) / 4.0 - f
    if radius_sq <= 0:
        return None
    radius = math.sqrt(radius_sq)
    center = (float(local[0] + origin[0]), float(local[1] + origin[1]))

    residuals = np.hypot(x - local[0], y - local[1]) - radius
    max_residual = float(np.max(np.abs(residuals)))
    return center, radius, max_residual


def circle_through(a: Point, m: Point, b: Point) -> Optional[Tuple[Point, float]]:
    """The circle through three points: `(center, radius)`, None if they are
    aligned. Computed in the frame of `a`: squared coordinates do not lose
    digits far from the origin."""
    ox, oy = a[0], a[1]
    a, m, b = (0.0, 0.0), (m[0] - ox, m[1] - oy), (b[0] - ox, b[1] - oy)
    den = 2 * (m[0] * b[1] - b[0] * m[1])
    if abs(den) < 1e-12:
        return None
    sm, sb = m[0] ** 2 + m[1] ** 2, b[0] ** 2 + b[1] ** 2
    cx = (sm * b[1] - sb * m[1]) / den
    cy = (sb * m[0] - sm * b[0]) / den
    return (cx + ox, cy + oy), math.hypot(cx, cy)


def even_spacing(points: List[Point], closed: bool) -> List[Point]:
    """The points with others added where two neighbours are farther apart than the
    median step. A long side with no points between would pass an arc through 3
    points as good (3 points always lie on a circle) and make a spline at
    irregular spacing oscillate. All given points stay, in the same order."""
    ring = list(points) + [points[0]] if closed else list(points)
    steps = sorted(math.dist(a, b) for a, b in zip(ring, ring[1:]))
    step = steps[len(steps) // 2] if steps else 0.0
    if step <= 0:
        return list(points)
    out: List[Point] = []
    for a, b in zip(ring, ring[1:]):
        out.append(a)
        extra = int(math.dist(a, b) / step)
        for k in range(1, extra):
            t = k / extra
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    if not closed:
        out.append(points[-1])
    return out


def offset_from_line(p: Point, a: Point, b: Point) -> float:
    """Signed distance of `p` from the line a->b (positive to the left)."""
    length = math.dist(a, b)
    if length == 0:
        return math.dist(p, a)
    return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / length


def douglas_peucker(points: List[Point], tolerance: float) -> List[int]:
    """Indices of the vertices Douglas-Peucker keeps on the open polyline
    `points`, ends included: every discarded point is at most `tolerance` from
    the side that replaces it."""
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        dist = {k: abs(offset_from_line(points[k], points[i], points[j])) for k in range(i + 1, j)}
        best = max(dist.values(), default=0.0)
        if best > tolerance:
            # the farthest points tied (within the noise) are all kept: picking one would
            # be decided by the direction or the last bit
            #
            cuts = [i] + [k for k, d in dist.items() if d >= best - FLOAT_NOISE] + [j]
            keep.update(cuts)
            stack.extend(zip(cuts, cuts[1:]))
    return sorted(keep)
