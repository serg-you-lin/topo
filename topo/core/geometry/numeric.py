"""
topo/core/geometry/numeric.py
-----------------------------
Metodi numerici senza geometria: il minimo di una funzione unimodale su un
intervallo, per sezione aurea. Chi cerca un massimo passa `-f`.
"""

import math
from typing import Optional, Tuple


def golden_min(f, a: float, b: float, iterations: Optional[int] = None) -> Tuple[float, float]:
    """(x, f(x)) del minimo di `f` unimodale su [a, b], per sezione aurea:
    `iterations` passi, o (None) finché i double separano i punti interni.
    A parità tiene la metà sinistra; anche gli estremi sono candidati."""
    r = (math.sqrt(5) - 1) / 2
    c, d = b - r * (b - a), a + r * (b - a)
    fc, fd = f(c), f(d)
    steps = 0
    while a < c < d < b and (iterations is None or steps < iterations):
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - r * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + r * (b - a)
            fd = f(d)
        steps += 1
    value, x = min([(f(a), a), (fc, c), (fd, d), (f(b), b)])
    return x, value
