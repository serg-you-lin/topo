"""
topo/core/readings/outline.py
-----------------------------
The reading from the outside of a repaired network: `Network.outlines()`.

`faces()` rebuilds the topology from the inside and finds the part by
containment. `outlines()` reads the drawing from the outside: the groups are
the edges touching within `max_gap`, the outer contour of each is the outer
face of its planar network with the crossings cut, and every outer contour
that is not inside another is a Cluster. What lies inside, closed or open,
is its own by containment. It is the right reading for a drawing of views
(projected 3D, several views on a sheet), where the graph of faces() is
ambiguous. What a contour is — view, part, frame — is the caller's call.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional


from ...model.cluster import Cluster
from ...model.contour import Contour
from ...model.diagnostic import Diagnostic
from ...model.result import Result
from ...model.role import ContourRole
from ..geometry.shapely_polygons import curve_polygon, with_polygon
from ..primitives.mathseg import segment_endpoints
from ..topology.edge import Edge
from ..geometry.integrals import ring_area
from ..geometry.rings import ring_bbox, ring_contains
from ..geometry.shape import merge_runs
from ...precision import SAME_POINT
from ..topology.noding import GRAPH_EPSILON, edge_geometry, split_at_crossings
from ..topology.outer_face import OuterFace, outer_face
from ..base.hierarchy import assign_cluster_refs, sort_clusters
from ..base.curves import loose_curves
from ..topology.non_contour_edges import non_contour_pieces
from ..topology.touching import touching_groups
from .network import repair_edges
from .heal_steps import close_contour_jumps

if TYPE_CHECKING:
    from .network import Network


@dataclass
class OutlineReading:
    """What outlines() decided about a group, piece by piece."""
    edges:          List[Edge]                               # of the group, as they arrive
    outer:          Optional[OuterFace]    = None            # None: no closed loop
    spurs:          List[Edge]             = field(default_factory=list)   # back-and-forth walks
    outside:        List[Edge]             = field(default_factory=list)   # outside the contour
    non_contour:    List[Edge]             = field(default_factory=list)   # non-contour criterion
    unclassified:   List[Edge]             = field(default_factory=list)
    nested_in:     Optional[int]          = None            # index of the group that contains it (even without an outer)


# --- Public API ---

def read_network_outlines(net: Network) -> Result:
    """A Cluster for every outer contour not inside another, with the `outer` only:
    no inners. Everything else — closed or open, inside or outside the contour, a
    whole group inside another — goes to `loose`, from the repaired network,
    with `cluster_ref` = the Cluster it touches or that contains it; `None` if it
    is outside every one. With the frame in the drawing the only outer contour is
    the frame: removing it is the caller's job."""
    tol = SAME_POINT
    result = Result(source_file=net.source_file, source_format=net.source_format, reading="outlines",
                    max_gap=net.max_gap, texts=list(net._texts))
    result.warnings += net.warnings
    result.notes += net.notes
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    readings = _read_groups(net.edges, tol, net.max_gap)
    result.loose += loose_curves(net.set_aside)
    clusters = {}
    for i, r in enumerate(readings):
        if r.outer is not None and r.nested_in is None:
            clusters[i] = _cluster(r, net.source_file, net.label)
    owned = []   # (curve, cluster that contains it)
    for i, r in enumerate(readings):
        host = clusters.get(r.nested_in) if r.nested_in is not None else clusters.get(i)
        if host is None or r.outer is None:
            owned += [(f, host) for f in loose_curves(r.edges)]
            continue
        if r.nested_in is not None:
            # a group inside another is not its inner, it goes to `loose`
            owned += [(f, host) for f in loose_curves(r.edges)]
            continue
        owned += [(f, host) for f in loose_curves(r.spurs + r.outside + r.non_contour + r.unclassified)]
    result.clusters = sort_clusters(list(clusters.values()))
    index = {id(c): k for k, c in enumerate(result.clusters)}
    for curve, host in owned:
        curve.cluster_ref = None if host is None else index[id(host)]
    result.loose += [f for f, _ in owned]
    # whoever touches no contour has the Cluster that contains it, if any (a
    # detached axis inside the view, the frame marked by the caller)
    free = [c for c in result.loose if c.cluster_ref is None]
    assign_cluster_refs(free, result.clusters, tol)
    if not result.clusters:
        result.is_valid = False
        result.errors.append(Diagnostic("no-closed-outer", "no group of edges has a closed outer contour",
                                        level="error"))
        return result
    close_contour_jumps(result, tol)
    from ...rules.validator import validate_result
    validate_result(result)
    return result


def read_outlines(edges: List[Edge], tolerance: float, max_gap: float) -> List[OutlineReading]:
    """The edges repaired like heal() (`network.repair_edges`), then the touching
    pieces (`touching_groups` at `max_gap`) read one by one, and the nesting: a
    piece lying inside another's contour — with its contour, or with no contour
    with all its edges — carries in `nested_in` the index of the outermost that
    contains it."""
    return _read_groups(repair_edges(edges, tolerance, max_gap), tolerance, max(tolerance, max_gap))


def read_outline(edges: List[Edge], tolerance: float, max_gap: float) -> OutlineReading:
    """A group: the edges repaired like heal() (`network.repair_edges`), the planar
    network, its outer face, then the rest, which all goes to `loose`: outside
    the contour, non-contour, unclassified."""
    return _read_group(repair_edges(edges, tolerance, max_gap), tolerance)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _read_groups(edges: List[Edge], tolerance: float, gap: float) -> List[OutlineReading]:
    """Already repaired edges: the groups touching within `gap`, read, and nested."""
    readings = [_read_group(g.edges, tolerance) for g in touching_groups(edges, gap)]
    # the exact box of every host, widened by GRAPH_EPSILON (well beyond the
    # ring_contains border and the spline error): a point outside is neither inside
    # nor on the border, and the winding on the true curves is skipped
    outers = [(j, r.outer.segments, ring_area(r.outer.segments), ring_bbox(r.outer.segments))
              for j, r in enumerate(readings) if r.outer is not None]
    e = GRAPH_EPSILON
    for i, r in enumerate(readings):
        # two groups are farther apart than the threshold on the true curves: a point
        # of the piece lies inside a host only if the whole piece does
        if r.outer is not None:
            point, area = segment_endpoints(r.outer.segments[0])[0], ring_area(r.outer.segments)
        else:
            point, area = r.edges[0].start, 0.0
        hosts = [(j, big_area) for j, ring, big_area, (x0, y0, x1, y1) in outers
                 if j != i and big_area > area and x0 - e <= point[0] <= x1 + e and y0 - e <= point[1] <= y1 + e
                 and ring_contains(ring, point)]
        if hosts:
            r.nested_in = max(hosts, key=lambda h: h[1])[0]
    return readings


def _read_group(edges: List[Edge], tolerance: float) -> OutlineReading:
    """A group of already repaired edges: the planar network with the crossings cut,
    the outer face, the rest classified."""
    noded = split_at_crossings(edges, tolerance)
    pieces = noded.pieces
    face = outer_face(pieces, epsilon=GRAPH_EPSILON)

    reading = OutlineReading(edges=list(edges), outer=face)
    taken = set()
    if face is not None:
        taken = {id(e) for e in face.edges} | {id(e) for e in face.spurs}
        reading.spurs = list(face.spurs)
    rest = [e for e in pieces if id(e) not in taken] + (face.rest if face is not None else [])
    if face is not None:
        probe = curve_polygon(face).buffer(tolerance)
        reading.outside = [e for e in rest if not probe.contains(edge_geometry(e))]
        outside_ids = {id(e) for e in reading.outside}
        rest = [e for e in rest if id(e) not in outside_ids]
    # inside the contour no inner, everything else goes to `loose`
    non_contour_ids = non_contour_pieces(noded, tolerance)
    reading.non_contour = [e for e in rest if id(e) in non_contour_ids]
    reading.unclassified = [e for e in rest if id(e) not in non_contour_ids]
    return reading


def _cluster(reading: OutlineReading, source_file: str, label: str) -> Cluster:
    face = reading.outer
    outer = _contour(face.segments, face.styles, curve_polygon(face), ContourRole.OUTER, None)
    return Cluster(outer=outer, source_file=source_file, label=label)


def _contour(segments, styles, polygon, role, parent) -> Contour:
    """The polygon stays that of the planar network's pieces; the segments are
    recomposed where the cut had split them (`geometry.shape.merge_runs`)."""
    segments, styles = merge_runs(list(segments), list(styles))
    return with_polygon(Contour(role=role, segments=segments, styles=styles,
                                depth=0 if parent is None else 1, parent=parent), polygon)


