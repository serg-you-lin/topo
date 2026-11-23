"""
topo/core/primitives/minimize.py
--------------------------------
Il minimo di una funzione del punto lungo una curva, per certificato: la
curva si divide in pezzi di parametro, ognuno con un minorante della funzione
su tutto il pezzo; un pezzo che non scende sotto il migliore trovato si scarta,
gli altri si dimezzano. Nessun campionamento: un ramo vicino non vince per
sbaglio (D300). Il minorante lo dà la curva (inviluppo dei punti di controllo,
velocità nota, aritmetica degli intervalli); il meccanismo è uno solo.
"""

from __future__ import annotations

import heapq
import itertools
import math
from typing import Any, Callable, Iterable, Tuple

from ...precision import FLOAT_NOISE
from .mathseg import Point

# un pezzo: (t0, t1, punto in t0, punto in t1, dati della curva sul pezzo)
Piece = Tuple[float, float, Point, Point, Any]


def certified_min(pieces: Iterable[Piece],
                  value: Callable[[Point], float],
                  bound: Callable[[Piece], float],
                  split: Callable[[Piece], Tuple[Piece, Piece]]) -> Tuple[float, float, float]:
    """(t, lo, hi): il parametro dove `value(punto)` è minimo sulla curva, entro
    FLOAT_NOISE, e il pezzo [lo, hi] attorno a lui da rifinire. `bound(pezzo)`
    minora `value` su tutto il pezzo; `split(pezzo)` lo dimezza, e il punto di
    mezzo è il capo comune delle due metà."""
    best = (math.inf, 0.0, 0.0, 0.0)
    heap: list = []
    order = itertools.count()   # a pari minorante, nell'ordine di arrivo
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
    """Il dimezzamento di un pezzo di una curva data per punti `at(t)`, senza dati suoi."""
    def halves(piece: Piece) -> Tuple[Piece, Piece]:
        t0, t1, p0, p1, data = piece
        tm = (t0 + t1) / 2
        pm = at(tm)
        return (t0, tm, p0, pm, data), (tm, t1, pm, p1, data)
    return halves
