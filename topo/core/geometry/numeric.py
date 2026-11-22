"""
topo/core/geometry/numeric.py
-----------------------------
Metodi numerici senza geometria: l'estremo di una funzione unimodale su un
intervallo, per sezione aurea. Due varianti col loro arresto: `golden_max` a
iterazioni contate, `golden_min` finché i double separano i punti interni.
"""

import math
from typing import Tuple


def golden_max(f, a: float, b: float, iterations: int = 40) -> Tuple[float, float]:
    """(x, f(x)) del massimo di `f` unimodale su [a, b], per sezione aurea."""
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iterations):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return (c, fc) if fc > fd else (d, fd)


def golden_min(f, a: float, b: float) -> float:
    """Il minimo di `f` su [a, b] (sezione aurea), fino a che i double
    separano i punti interni."""
    r = (math.sqrt(5) - 1) / 2
    c, d = b - r * (b - a), a + r * (b - a)
    fc, fd = f(c), f(d)
    while a < c < d < b:
        if fc <= fd:
            b, d, fd = d, c, fc
            c = b - r * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + r * (b - a)
            fd = f(d)
    candidates = [(f(a), a), (fc, c), (fd, d), (f(b), b)]
    return min(candidates)[1]
