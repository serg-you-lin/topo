"""
topo/core/readings/heal_steps.py
--------------------------------
The steps proper to heal(), one per function: the ladder that closes the
loops, the polygonize fallback, the non-contours, the hierarchy. The common
foundations are in `core/base`.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Set, Tuple

from shapely import STRtree
from shapely.geometry import Point

from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ..topology.non_contour_edges import non_contour_pieces
from ..topology.noding import split_at_crossings
from ...model.cluster import Cluster
from ...model.diagnostic import Diagnostic
from ...model.role import ContourRole, is_structural_role
from ..base.hierarchy import HierarchyBuilder
from ..geometry.measure import FLOAT_NOISE, reach
from ..geometry.rings import ring_bridges


def find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]:
    """id(edge) of the Edges that do not close a contour (chains between two
    branching nodes, and not on the border of the component's outer face): those
    whose pieces of the planar network are all non-contour, the same judgment the
    readings make (`non_contour_pieces`). `tolerance`: two cuts closer than this
    are one contact."""
    noded = split_at_crossings(edges, tolerance, cut_crossings=False)
    excluded = non_contour_pieces(noded, tolerance)
    verdict: dict = {}
    for piece in noded.pieces:
        key = id(noded.parent_of(piece))
        verdict[key] = verdict.get(key, True) and id(piece) in excluded
    return {key for key, out in verdict.items() if out}


def find_joining_edges(edges: List[Edge], candidate_ids: Set[int]) -> List[Edge]:
    """The Edges among `candidate_ids` (usually the non-contours) that join two
    otherwise detached shapes: removed, their two ends are no longer connected.
    Between two closed shapes it is the ambiguous node par excellence — a part
    with a line attached, or two parts? heal() reads them as two and says so in
    a warning."""
    graph = build_node_graph(edges)
    joining = []
    for edge in edges:
        if id(edge) not in candidate_ids:
            continue
        start, goal = graph.canonical(edge.start), graph.canonical(edge.end)
        if start == goal:
            continue
        seen, todo = {start}, [start]
        while todo and goal not in seen:
            node = todo.pop()
            for other_edge, other in graph[node]:
                if other_edge is not edge and other not in seen:
                    seen.add(other)
                    todo.append(other)
        if goal not in seen:
            joining.append(edge)
    return joining


def free_ends(edges: List[Edge], epsilon: float = 0.0) -> List[Tuple[Tuple, float]]:
    """(end, distance from the nearest node) for every end no other edge touches,
    nearest to a node first: an end a few mm from a vertex is a gap the tolerance
    did not close. `epsilon`: that of the graph on which the loops were closed,
    because an end merged there is not free."""
    graph = build_node_graph(edges, epsilon=epsilon)
    open_nodes = graph.open_nodes()
    if not open_nodes:
        return []
    nodes = list(graph.nodes)
    tree = STRtree([Point(q) for q in nodes])
    ends = []
    for node in open_nodes:
        hit = tree.query_nearest(Point(node), exclusive=True, return_distance=True)
        ends.append((node, float(hit[1][0]) if len(hit[1]) else math.inf))
    return sorted(ends, key=lambda item: item[1])


def structural_loops(loops: List[list],
                     is_structural: Optional[Callable[[str], bool]] = None) -> List[list]:
    """The loops in which every edge with a decided role is structural: a single
    non-structural edge (engrave, frame, ...) demotes the whole loop."""
    return [loop for loop in loops if all(may_be_contour(e, is_structural) for e, _ in loop)]


def may_be_contour(edge: Edge, is_structural: Optional[Callable[[str], bool]] = None) -> bool:
    """The edge may be a contour: undecided role, or structural."""
    return edge.role == ContourRole.UNKNOWN or (is_structural or is_structural_role)(edge.role)


def build_hierarchy(curves: list, label: str = "",
                    is_structural: Optional[Callable[[str], bool]] = None
                    ) -> Tuple[List[Cluster], list]:
    """Containment tree on the ClosedCurves: every root is a Cluster (outer), the
    descendants its inners with `depth`/`parent`. Returns (cluster, loose):
    loose is what did not end up in a cluster and is not structural."""
    builder = HierarchyBuilder(label=label, is_structural=is_structural)
    return builder.build(curves)


def close_contour_jumps(result, tolerance: float) -> None:
    """Every delivered contour closes exactly: a jump within `tolerance` between a
    segment and the next becomes a new line between the two ends, with the style
    of the previous segment. No curve moves; the polygon already counted the jump
    as its chord. **Mutates** `result` and says so in `notes`."""
    starts, widest = [], 0.0
    for cluster in result.clusters:
        for contour in [cluster.outer] + list(cluster.inners):
            bridges = ring_bridges(contour.segments, reach(tolerance), FLOAT_NOISE)
            for k, line in reversed(bridges):
                contour.segments.insert(k + 1, line)
                if len(contour.styles) > k:
                    contour.styles.insert(k + 1, contour.styles[k])
                widest = max(widest, math.dist(line.start, line.end))
                starts.append(line.start)
    if starts:
        result.notes.append(Diagnostic(
            "gap-closed", f"{len(starts)} {'jump' if len(starts) == 1 else 'jumps'} in the contours closed "
                          f"with a new straight segment",
            points=starts, notes=[f"up to {widest:.3g} wide"], level="note"))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

