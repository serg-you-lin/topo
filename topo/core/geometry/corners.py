"""
topo/core/geometry/corners.py
------------------------------
Spigoli di una sequenza campionata: dove la svolta, misurata su una scala,
non è di una curva liscia (MAP.md D141).
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
    """Punto della polilinea `points` all'ascissa curvilinea `s` (troncata agli estremi)."""
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
    """
    Indici degli spigoli di una sequenza campionata: vertici Douglas-Peucker
    (a `tolerance`) dove la curva svolta di almeno `turn_deg` gradi fra il
    punto a `scale` prima e quello a `scale` dopo, lungo la curva. Con
    `turn_deg=None` è spigolo dove nessuna curva liscia passa entro
    `tolerance` dalla polilinea fra quei due punti (D283):
    vale per punti fitti, la cui corda si scosta dalla curva meno di
    `tolerance` (una curva scritta a punti da un CAD). Misurata su
    una scala e non fra due campioni vicini, un angolo vivo smussato dal
    campionamento conta per tutta la sua svolta. Fra spigoli più vicini di
    `scale` resta quello che svolta di più. Su una sequenza aperta gli
    estremi non sono mai spigoli.
    """
    n = len(points)
    if n < 3:
        return []
    # chiusa: tre giri di fila, la finestra attorno al giro centrale non si tronca mai
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
            # la polilinea fra i punti, non solo i punti: per 3 punti passa sempre un cerchio
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
        """Quanto `b` viene dopo `a` lungo la curva (sul giro, se chiusa)."""
        return (cum[b] - cum[a]) % perimeter

    # dal più svoltato; due svolte più vicine del rumore (l'angolo che
    # FLOAT_NOISE sottende su `scale`) e a meno di `scale` sono pari merito:
    # vince il primo lungo la curva dentro il loro tratto, non l'ultimo bit
    # del moto né il punto dove l'anello comincia (G6e)
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
