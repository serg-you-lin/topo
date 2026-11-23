"""
core/topology/non_contour_edges.py
----------------------------------
Finds the edges that are NOT part of a contour and must be excluded from the
graph before the loop search.

It is not feature classification: here no edge is decided to "be a bend". It
is decided only, topologically, that an edge does not close a contour —
typically a line crossing the part from side to side (often a bend line, but
also an axis, a centreline, a through trace). The true semantics lives in a
consumer (snapbend `detect_flat`), which picks them back from `result.loose`.

The chain is judged (`Graph.chains`): the edges in a row through nodes of
degree 2. A chain is excluded, whole, if:
  1. Its two ends are distinct branching nodes (degree > 2)
  2. It does not border the outer face of ITS connected component on one
     side only: the border of that face does not walk it, or walks it back and
     forth

Criterion 2 is topological: a true contour side has material on one side and
the outside on the other, a chord has a face closed on both sides. It holds
for a concave part as for a convex one, and per component: a sheet with
several views does not mix the shapes. Where the edge comes from in the source
format is never a criterion.

The outer face is walked on the planar network (`split_at_crossings`, the same
as outlines()): two sides that cross in the file without a node — a notch with
flanks overlapping by a tenth — would fool the walk, which would pass over the
crossing. A chain is on the border if pieces of it are for more than half its
length. The cuts within `tolerance` are a single contact: a chord arriving at
the rounded node at the end of a fillet does not open a face of a few hundredths.

Input:  Graph, list[Edge]
Output: set[int]  — id() of the Edges to exclude from the contour graph
"""

from .graph import Graph, build_node_graph
from .edge import Edge
from .noding import GRAPH_EPSILON, NodedEdges, edge_geometry, split_at_crossings
from .outer_face import outer_face_passes


class NonContourEdgeDetector:

    def __init__(self, tolerance: float):
        self.tolerance = tolerance

    def detect(self, graph: Graph, edges: list[Edge], planar: bool = False) -> set[int]:
        """id(edge) of the chains that are not contours. `planar`: the edges are already
        the planar network of `split_at_crossings` (`outlines()`), not split again."""
        branching = set(graph.branching_nodes())
        if not branching:
            return set()
        given = {id(e) for e in edges}
        # the candidate is the chain, not the edge: its interior nodes have degree 2, so
        # it is wholly in one loop or in none. A chain closed on a single node is already
        # a loop, never a chord between two points
        chains = [run for run, a, b in graph.chains()
                  if a != b and a in branching and b in branching
                  and all(id(e) in given for e in run)]
        candidates = [e for run in chains for e in run]
        if not candidates:
            return set()

        noded = (NodedEdges(pieces=list(edges), parent={id(e): e for e in edges}) if planar
                 else split_at_crossings(edges, self.tolerance))
        plane = build_node_graph(noded.pieces, sliver=GRAPH_EPSILON)
        wanted = {id(e) for e in candidates}
        outside = {}   # id(edge) -> length of its pieces bordering the outside
        # one walk of the outer face for every component that has candidates
        for component in plane.connected_components():
            pieces = {id(p): p for node in component for p, _ in plane[node]}
            if not {id(noded.parent_of(p)) for p in pieces.values()} & wanted:
                continue
            passes = outer_face_passes(plane, component, len(noded.pieces))
            for key, piece in pieces.items():
                if passes.get(key, 0) == 1:
                    parent = id(noded.parent_of(piece))
                    outside[parent] = outside.get(parent, 0.0) + edge_geometry(piece).length
        # border = borders the outside for more than half its length: a true side does
        # so wholly, a chord at most for a grazed stretch (nearly tangent to a fillet,
        # below the thickness tolerance)
        excluded: set[int] = set()
        for run in chains:
            border = sum(outside.get(id(e), 0.0) for e in run)
            if border <= sum(edge_geometry(e).length for e in run) / 2:
                excluded |= {id(e) for e in run}
        return excluded


def non_contour_pieces(noded: NodedEdges, tolerance: float) -> set:
    """id of the pieces of the planar network `noded` that do not close a contour,
    judged on the planar network: the same for every reading."""
    graph = build_node_graph(noded.pieces, sliver=GRAPH_EPSILON)
    return NonContourEdgeDetector(tolerance).detect(graph, noded.pieces, planar=noded.planar)

