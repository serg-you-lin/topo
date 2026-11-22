"""
topo/primitives.py
------------------
Le primitive geometriche native, pubbliche (MAP.md D120): le madri `MathSeg` e
`ConicSeg` (D285), la retta, le coniche (cerchio, ellisse, parabola, iperbole,
D286-D288), la spline, la curva da formula (D289) e la clotoide (D290), `sub_segment` (il tratto di una di loro) e
`segment_endpoints` (i suoi due estremi).
Math puro, nessun ruolo: un `Edge` (in `topo.model`) ne avvolge uno con ruolo
e stile.

    import topo

    side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))
    arc = topo.primitives.CircleSeg((50, 0), 50, 0.0, math.pi, True)   # mezzo cerchio

Quello che sta sotto `topo.core` è interno, senza garanzie.
"""
from .core.primitives.mathseg import MathSeg, segment_endpoints
from .core.primitives.line import LineSeg
from .core.primitives.spline import BSplineSeg
from .core.primitives.conics import ConicSeg, CircleSeg, EllipseSeg, HyperbolaSeg, ParabolaSeg
from .core.primitives.clothoid import ClothoidSeg
from .core.primitives.formula import FormulaSeg
from .core.primitives.trim import sub_segment

__all__ = ["MathSeg", "ConicSeg", "LineSeg", "CircleSeg", "BSplineSeg", "EllipseSeg", "ParabolaSeg", "HyperbolaSeg", "FormulaSeg", "ClothoidSeg", "sub_segment",
           "segment_endpoints"]
