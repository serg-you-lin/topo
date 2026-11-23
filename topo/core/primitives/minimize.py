"""
topo/core/primitives/minimize.py
--------------------------------
Minimum of a function of the point along a curve, by certificate: the curve is
split into parameter pieces, each with a lower bound of the function over the
whole piece; a piece whose bound is not below the best found is discarded, the
others are halved. No sampling, so a near branch cannot win by mistake. The
curve supplies the bound (control-point hull, known speed, interval
arithmetic); the mechanism is one.
"""

from __future__ import annotations

import heapq
import itertools
import math
from typing import Any, Callable, Iterable, Tuple

from ...precision import FLOAT_NOISE
from .mathseg import Point

# a piece: (t0, t1, point at t0, point at t1, the curve's data on the piece)
Piece = Tuple[float, float, Point, Point, Any]


def certified_min(pieces: Iterable[Piece],
                  value: Callable[[Point], float],
                  bound: Callable[[Piece], float],
                  split: Callable[[Piece], Tuple[Piece, Piece]]) -> Tuple[float, float, float]:
    """(t, lo, hi): the parameter where `value(point)` is minimal on the curve,
    within FLOAT_NOISE, and the piece [lo, hi] around it to refine. `bound(piece)`
    is a lower bound of `value` over the piece; `split(piece)` halves it, the
    midpoint being the shared end of the two halves."""
    best = (math.inf, 0.0, 0.0, 0.0)
    heap: list = []
    order = itertools.count()   # ties on the bound go in arrival order
    for piece in pieces:
        t0, t1, p0, p1, _ = piece
        for t, q in ((t0, p0), (t1, p1)):
            v = value(q)
            if v < best[0]:
                best = (v, t, t0, t1)
        heap.append((bound(piece), next(order), piece))
    heapq.heapify(heap)
    while heap:
        b, _, piece = heapq.heappop(heap)
        if b >= best[0] - FLOAT_NOISE:
            break
        t0, t1 = piece[0], piece[1]
        tm = (t0 + t1) / 2
        if not t0 < tm < t1:
            continue
        left, right = split(piece)
        v = value(left[3])
        if v < best[0]:
            best = (v, tm, t0, t1)
        for half in (left, right):
            heapq.heappush(heap, (bound(half), next(order), half))
    return best[1], best[2], best[3]


def point_split(at: Callable[[float], Point]) -> Callable[[Piece], Tuple[Piece, Piece]]:
    """Halving of a piece of a curve given by points `at(t)`, with no data of its own."""
    def halves(piece: Piece) -> Tuple[Piece, Piece]:
        t0, t1, p0, p1, data = piece
        tm = (t0 + t1) / 2
        pm = at(tm)
        return (t0, tm, p0, pm, data), (tm, t1, pm, p1, data)
    return halves
