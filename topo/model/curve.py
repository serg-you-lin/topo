"""
model/curve.py

Base hierarchy of the topo domain: a curve is a sequence of segments, closed
or open. A geometric name, not a process one.

Curve
├── ClosedCurve   — closed contour (loop): the segments close a loop
└── OpenCurve     — open trace

All model entities inherit from here:
    Hole(ClosedCurve), Contour(ClosedCurve)
    BendingLine(OpenCurve), Engraving(OpenCurve)

Notes:
    - segments is List[MathSeg] — pure primitives
    - styles is List[EdgeStyle], aligned 1:1 with segments — raw appearance
      (linetype/colour) of the source entity of each segment. It may be
      shorter than segments or empty (synthesized geometry, e.g. gap-closing
      bridges or the polygonize fallback): whoever consumes it in write()
      treats a missing index as "no known style".
    - no shapely type in the model: the polygon for questions between several
      curves is a private cache, `core.geometry.shapely_polygons.curve_polygon`
    - role is the only internal semantic channel — never read a layer in core
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Any, List, Optional, Tuple

from topo.core.geometry.integrals import ring_area, ring_centroid
from topo.core.geometry.rings import ON_BOUNDARY, ring_bbox, ring_contains, ring_points
from topo.core.primitives.mathseg import MathSeg, DEFAULT_TOLERANCE
from topo.model.style import EdgeStyle


@dataclass
class Curve:
    """Root of the hierarchy. It carries only semantic identity and traceability.

    Do not instantiate directly — use ClosedCurve or OpenCurve."""
    role:       str          # ContourRole constant, or a consumer's slug


@dataclass
class ClosedCurve(Curve):
    """Closed curve: a list of segments that closes a loop. Its facts (area, bbox,
    centroid, contains) are computed on the segments.

    It carries no `diameter` / `center`: shape and measures of a contour are read
    from `topo.geometry.contour_shape`."""
    segments: List[MathSeg] = field(default_factory=list)
    _: KW_ONLY
    styles:   List[EdgeStyle]                  = field(default_factory=list)
    cluster_ref: Optional[int]                 = None   # in result.loose: index of the cluster that contains it
    # the reading's polygon, only for questions between several curves (curve_polygon)
    _polygon:    Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def area(self) -> float:
        """Exact area, integrated on the `segments` (Green): it does not depend on the
        discretization tolerance."""
        return ring_area(self.segments) if self.segments else 0.0

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Exact (xmin, ymin, xmax, ymax) of the `segments`: arcs and ellipses
        reach their true extremes, not their chords."""
        return ring_bbox(self.segments) if self.segments else (0.0, 0.0, 0.0, 0.0)

    @property
    def centroid(self) -> Tuple[float, float]:
        """Exact centroid of the enclosed area, integrated on the `segments`
        (Green). `ValueError` if the ring encloses no area."""
        return ring_centroid(self.segments)

    def contains(self, point: Tuple[float, float], *, tolerance: float = ON_BOUNDARY) -> bool:
        """True if `point` lies in the closed region: inside, or on the
        boundary within `tolerance`. Computed on the `segments`."""
        return ring_contains(self.segments, point, tolerance)

    def points(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Tuple[float, float]]:
        """The ring discretized within `tolerance`, as plain (x, y) tuples in
        order; the first point is not repeated at the end."""
        return ring_points(self.segments, tolerance)


@dataclass
class OpenCurve(Curve):
    """Open curve: segments that do not close a loop."""
    segments:    List[MathSeg] = field(default_factory=list)
    _: KW_ONLY
    styles:      List[EdgeStyle]                  = field(default_factory=list)
    cluster_ref: Optional[int]                    = None   # in result.loose: index of the cluster that contains it