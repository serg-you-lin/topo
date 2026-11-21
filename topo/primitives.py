"""
topo/primitives.py
------------------
Le primitive geometriche native, pubbliche (MAP.md D120): le madri `MathSeg` e
`ConicSeg` (D285), i cinque segmenti
che un disegno contiene davvero, `sub_segment` (il tratto di uno di loro) e
`segment_endpoints` (i suoi due estremi, per chi lo riscrive in un formato).
Math puro, nessun ruolo: un `Edge` (in `topo.model`) ne avvolge uno con ruolo
e stile.

    import topo

    side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))
    arc = topo.primitives.ArcSeg((50, 0), 50, 0.0, math.pi, True)

Quello che sta sotto `topo.core` è interno, senza garanzie.
"""
from .core.primitives.segments import (
    MathSeg, ConicSeg, LineSeg, ArcSeg, CircleSeg, BSplineSeg, EllipseSeg, segment_endpoints,
)
from .core.primitives.trim import sub_segment

__all__ = ["MathSeg", "ConicSeg", "LineSeg", "ArcSeg", "CircleSeg", "BSplineSeg", "EllipseSeg", "sub_segment",
           "segment_endpoints"]
