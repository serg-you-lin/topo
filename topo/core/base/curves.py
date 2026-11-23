"""
topo/core/base/curves.py
------------------------
From loops and edges to model curves, for every reading: a loop becomes a
closed contour, or its open curves if it encloses nothing; what no contour
takes goes to `loose` with a single rule, role intact. Nothing is lost: an
edge closed by itself comes out closed.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

from typing import List, Optional

from shapely.geometry import Polygon

from ..geometry.integrals import ring_area
from ..geometry.measure import SAME_POINT, segment_length
from ..geometry.shapely_polygons import with_polygon
from ..geometry.rings import ring_scale
from ..primitives import LineSeg
from ..primitives.mathseg import segment_is_closed
from ..topology.edge import Edge
from ..topology.loops import loop_geometry
from ...model.curve import ClosedCurve, OpenCurve
from ...model.role import ContourRole
from .refit import chain_runs


def loop_to_closed_curve(
    loop,
    role: ContourRole = ContourRole.UNKNOWN,
    polygon=None,
    segments: list = None,
    styles: list = None,
) -> Optional[ClosedCurve]:
    from ..topology.loops import loop_points

    if polygon is not None:
        poly = polygon
    else:
        pts = loop_points(loop)
        if len(pts) < 3:
            return None
        poly = Polygon(pts)

    try:
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None
        # average width below SAME_POINT (2·area/perimeter): the two sides are the same
        # stretch, there is no contour
        if not segments or 2 * ring_area(segments) <= SAME_POINT * ring_scale(segments):
            return None

        return with_polygon(ClosedCurve(role=role, segments=segments, styles=styles or []), poly)
    except Exception:
        return None


def loops_to_curves(loops: List[list]) -> List[ClosedCurve | OpenCurve]:
    """One ClosedCurve per loop, with the role of the first edge. A loop that makes
    no contour (null polygon, narrower than SAME_POINT) comes back as one
    OpenCurve per edge, so it ends in `loose` instead of vanishing."""
    curves = []
    for loop in loops:
        role = loop[0][0].role if loop else ContourRole.UNKNOWN
        geometry = loop_geometry(loop)
        curve = None
        if geometry is not None:
            segments, styles, polygon = geometry
            curve = loop_to_closed_curve(loop, role=role, polygon=polygon, segments=segments,
                                         styles=styles)
        if curve is not None:
            curves.append(curve)
        else:
            curves += _open(edge for edge, _ in loop)
    return curves


def loose_curves(edges: List[Edge]) -> list:
    """The curves of `loose`: a piece that closes by itself — a closed segment, or a
    chain in which every node has degree 2 — is a ClosedCurve, because there is
    nothing to choose; the rest one OpenCurve per edge. The role of each edge
    stays its own."""
    edges = list(edges)
    single = [e for e in edges if e.segment is not None and segment_is_closed(e.segment)]
    rest = [e for e in edges if not (e.segment is not None and segment_is_closed(e.segment))]
    rings = [[(e, False)] for e in single] + [path for path, closed in chain_runs(rest) if closed]
    ringed = {id(e) for ring in rings for e, _ in ring}
    return loops_to_curves(rings) + _open(e for e in rest if id(e) not in ringed)


def _open(edges) -> List[OpenCurve]:
    """One OpenCurve per edge with its native segment, even if closed by itself (a
    discarded circle is not a contour). Only zero-length stretches are excluded."""
    curves = []
    for edge in edges:
        seg = edge.segment or LineSeg(start=edge.start, end=edge.end)
        if segment_length(seg) > 0:
            curves.append(OpenCurve(role=edge.role, segments=[seg], styles=[edge.style]))
    return curves
