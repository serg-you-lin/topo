"""
topo/primitives.py
------------------
The native geometric primitives, public: the parents `MathSeg` and
`ConicSeg`, the line, the conics (circle, ellipse, parabola, hyperbola), the
spline, the formula curve and the clothoid, `sub_segment` (the stretch of one
of them) and `segment_endpoints` (its two ends).
Pure maths, no role: an `Edge` (in `topo.model`) wraps one with role and style.

    import topo

    side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))
    arc = topo.primitives.CircleSeg((50, 0), 50, 0.0, math.pi, True)   # half circle

What is under `topo.core` is internal, with no guarantees.
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
