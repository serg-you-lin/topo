"""
topo/core/primitives/polyline.py
--------------------------------
La discretizzazione adattiva di una curva qualunque: si dimezza un tratto
finché la curva vera sta entro `tolerance` dalla corda. La usano le curve
che non hanno una griglia per dimostrazione (spline, formula).
"""

from __future__ import annotations

import math
from typing import List

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


def _refine_segment(
    evaluate, t0: float, t1: float, p0: Point, p1: Point,
    tolerance: float, out: List[Point], depth: int,
    max_depth: int = 8,
) -> None:
    """
    Suddivide `[t0, t1]` finché il punto medio (valutato con `evaluate(t)`)
    resta entro `tolerance` dalla corda. `max_depth` limita i punti su un
    tratto rumoroso che non converge mai; nessun tetto sul totale, che
    lascerebbe il resto della curva a corde grosse fuori tolleranza.

    `evaluate` è un callable `t -> Point` (De Boor per `BSplineSeg`).
    """
    tm = (t0 + t1) / 2
    pm = evaluate(tm)
    if (
        depth >= max_depth
        or _point_to_segment_distance(pm, p0, p1) <= tolerance
    ):
        out.append(p1)
        return
    _refine_segment(evaluate, t0, tm, p0, pm, tolerance, out, depth + 1, max_depth)
    _refine_segment(evaluate, tm, t1, pm, p1, tolerance, out, depth + 1, max_depth)


def _adaptive_polyline(
    evaluate, t_min: float, t_max: float, n_initial: int, tolerance: float,
) -> List[Point]:
    """
    Discretizza una curva parametrica valutata da `evaluate(t) -> Point` fra
    `t_min` e `t_max`: campionamento iniziale uniforme in `n_initial` passi
    (scelto dal chiamante in base alla propria stima di curvatura/lunghezza),
    poi suddivisione adattiva (`_refine_segment`) finché ogni tratto resta
    entro `tolerance` dalla corda.
    """
    n_initial = max(1, n_initial)
    ts = [t_min + (t_max - t_min) * i / n_initial for i in range(n_initial + 1)]
    points = [evaluate(t) for t in ts]

    result: List[Point] = [points[0]]
    for i in range(n_initial):
        _refine_segment(evaluate, ts[i], ts[i + 1], points[i], points[i + 1], tolerance, result, depth=0)
    return result
