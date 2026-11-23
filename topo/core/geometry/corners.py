"""
topo/core/geometry/corners.py
------------------------------
Corners of a sampled sequence: where the turn, measured on a scale, is not
that of a smooth curve.
"""

import math
from typing import Optional, List

from ...precision import FLOAT_NOISE
from .points import Point, douglas_peucker
from .curve_tests import within_smooth_curve


def _turn(back: Point, at: Point, forward: Point) -> float:
    """Di quanto gira (gradi, 0..180) chi va da `back` ad `at` e poi a `forward`."""
    v1 = (at[0] - back[0], at[1] - back[1])
    v2 = (forward[0] - at[0], forward[1] - at[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _point_at(points: List[Point], cum: List[float], s: float) -> Point:
    """Point of the polyline `points` at arc length `s` (clamped at the ends)."""
    if s <= 0:
        return points[0]
    if s >= cum[-1]:
        return points[-1]
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    t = (s - cum[lo]) / (cum[hi] - cum[lo]) if cum[hi] > cum[lo] else 0.0
    a, b = points[lo], points[hi]
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def turn_corners(points: List[Point], closed: bool, turn_deg: Optional[float], scale: float,
                 tolerance: float) -> List[int]:
    """Indices of the corners of a sampled sequence: Douglas-Peucker vertices (at
    `tolerance`) where the curve turns by at least `turn_deg` degrees between the
    point `scale` before and the one `scale` after, along the curve. With
    `turn_deg=None` a corner is where no smooth curve passes within `tolerance`
    of the polyline between those two points: valid for dense points, whose
    chord deviates from the curve by less than `tolerance` (a curve written as
    points by a CAD). Measured on a scale and not between two close samples, a
    sharp angle blunted by sampling counts for its whole turn. Among corners
    closer than `scale` the one that turns most is kept. On an open sequence the
    ends are never corners."""
    n = len(points)
    if n < 3:
        return []
    # closed: three loops in a row, so the window around the middle loop is never truncated
    ring = list(points) * 3 if closed else list(points)
    cum = [0.0]
    for a, b in zip(ring, ring[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    if closed:
        perimeter = cum[n]
        candidates = [n + k for k in douglas_peucker(ring[n: 2 * n + 1], tolerance) if k < n]
    else:
        perimeter = math.inf
        candidates = douglas_peucker(ring, tolerance)[1:-1]

    scored = []
    for k in candidates:
        s = cum[k]
        if not closed and (s < scale or s > cum[-1] - scale):
            continue
        back, forward = _point_at(ring, cum, s - scale), _point_at(ring, cum, s + scale)
        turn = _turn(back, ring[k], forward)
        if turn_deg is None:
            # the polyline between the points, not only the points: a circle always passes through 3 points
            window = [back] + [q for q, c in zip(ring, cum) if s - scale < c < s + scale] + [forward]
            window = [q for a, b in zip(window, window[1:]) for q in (a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))] + [forward]
            corner = not within_smooth_curve(window, tolerance)
        else:
            corner = turn >= turn_deg
        if corner:
            scored.append((turn, k))

    def apart(k: int, a: int) -> float:
        d = abs(cum[k] - cum[a])
        return min(d, perimeter - d)

    def ahead(a: int, b: int) -> float:
        """How far `b` comes after `a` along the curve (around the loop, if closed)."""
        return (cum[b] - cum[a]) % perimeter

    # from the most turned; two turns closer than the noise (the angle FLOAT_NOISE
    # subtends on `scale`) and less than `scale` apart tie: the first along the
    # curve inside their span wins, not the last bit of motion nor the point where
    # the ring starts
    slack = math.degrees(FLOAT_NOISE / scale)
    remaining = sorted(scored, key=lambda t: t[1])
    accepted: List[int] = []
    while remaining:
        top = max(turn for turn, _ in remaining)
        seed = next(c for c in remaining if c[0] >= top - slack)
        group = [c for c in remaining if c[0] >= top - slack and apart(c[1], seed[1]) < scale]
        pick = min(group, key=lambda c: max(ahead(c[1], o[1]) for o in group))
        remaining.remove(pick)
        if all(apart(pick[1], a) >= scale for a in accepted):
            accepted.append(pick[1])
    return sorted(k - n for k in accepted) if closed else sorted(accepted)
