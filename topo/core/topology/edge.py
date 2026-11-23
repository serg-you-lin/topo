"""
core/topology/edge.py
---------------------
Topological representation of a linear geometric entity — the unit that
graph.py / loops.py / non_contour_edges.py / gaps.py use to build and walk the
graph. It is not a geometric primitive (those are LineSeg/CircleSeg/
BSplineSeg/EllipseSeg in core/primitives/, pure maths with no semantics):
`Edge` wraps one with role, provenance and style — domain data, no reference
to the source entity of any format.

It lives in core/ because its main consumer is core: every adapter builds
Edges, but core defines their shape, exactly as for the primitives.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Optional, Tuple

from ..primitives.line import LineSeg
from ..primitives.mathseg import MathSeg, segment_endpoints, segment_is_closed
from ...model.style import EdgeStyle

Segment = MathSeg


def node_point(pt) -> Tuple:
    """The node of a point: the true point, as floats; no grid."""
    return (float(pt[0]), float(pt[1]))


@dataclass
class Edge:
    """Intermediate layer between the raw source entity (of any format) and the
    topology engine. Pure data — no reference to the source entity.

    Fields:
        role       : semantic role (string: ContourRole constant or a consumer's
                     slug) — assigned by the adapter before building the Edge,
                     never derived from a layer in here
        start      : endpoint rounded to the tolerance
        end        : endpoint rounded to the tolerance
        segment    : native geometric primitive — never discretized here,
                     discretization happens in the LoopFinder via .discretize()
        style      : raw appearance (linetype/colour) of the source entity —
                     captured by the adapter, never interpreted here

    Deliberately NO field saying "came from a closed LWPOLYLINE" or the like: that
    a path is already closed is a fact the topo graph discovers by itself
    (`Graph.degenerate_loops`, a loop found by the `LoopFinder`) — not information
    the adapter can shorten by handing it over as a flag. Such a flag is
    provenance in the source format dressed as a topological property: a PDF/SVG
    adapter would have no way to fill it, and the core must never need it to."""
    role:    str
    start:   Tuple[float, float]
    end:     Tuple[float, float]
    segment: Segment
    _: KW_ONLY
    style:   EdgeStyle = field(default_factory=EdgeStyle)

    @classmethod
    def of(cls, segment: Segment, role: str, *, style: Optional[EdgeStyle] = None) -> "Edge":
        """The Edge of `segment`: the ends are the true points of the segment, the node
        by distance is decided by heal. A closed curve (circle, spline or ellipse with
        ends within the tolerance) has a single node: it is a degenerate loop, which
        the graph recognizes by itself. A very short line or arc stays two nodes —
        they are sides, not loops.

        It is how an adapter builds an Edge."""
        start, end = segment_endpoints(segment)
        start = node_point(start)
        if not isinstance(segment, LineSeg) and segment_is_closed(segment):
            end = start
        else:
            end = node_point(end)
        return cls(role=role, start=start, end=end, segment=segment, style=style or EdgeStyle())
