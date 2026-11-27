"""
core/topology/parity.py
-----------------------
The contours of a planar network by parity: the faces are coloured
inside/outside so that every side separates two different colours.

Theorem: the faces of a planar graph admit this colouring, with every side
between two different colours, if and only if every node has even degree; and
then it is unique, once the outside is fixed. Every side is contour, each
appears exactly once among the loops of the *outside* faces.

Where a node has odd degree the network admits no colouring: the sides that
cannot be contour are removed, and then as little as possible.
  1. a free end or a bridge has the same face on both sides: removed;
  2. of the remaining sides, the set that makes every node even removing first
     as little as possible of the silhouette (the sides on the border of
     their component's outer face, with the outside on one side only), then
     the minimum total length: the minimum-weight T-join on the graph
     (`matching.min_t_join`), with the two criteria in one exact integer
     weight (multiples of FLOAT_NOISE).

Pure: Edges, graph and primitives only, no format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .edge import Edge
from .graph import Graph, build_node_graph
from .loops import segments_from_loop
from .matching import min_t_join
from .noding import GRAPH_EPSILON, edge_geometry
from .outer_face import face_walks, outer_face_passes, simple_rings
from ..geometry.integrals import ring_moments
from ..geometry.measure import FLOAT_NOISE, segment_length
from ..geometry.rings import ring_bbox, ring_contains


@dataclass
class ParityRings:
    """The loops of the contours, and what the reading removed to get there."""
    loops:     List[list]                                  # [(piece, reversed)] counter-clockwise
    dropped:   Set[int] = field(default_factory=set)       # id of the pieces that are not contour
    conflicts: List[tuple] = field(default_factory=list)   # nodes where the colouring does not work out
    rim_used:  bool = False                                # the T-join removes silhouette too
    joining:   Set[int] = field(default_factory=set)       # id of the bridges between two closed figures


def parity_rings(pieces: List[Edge]) -> ParityRings:
    """The loops of the *outside* faces of the planar network `pieces`
    (split_at_crossings, crossings cut), after removing the sides that make a
    node odd (see the module). No choice depends on the order of the pieces."""
    graph = build_node_graph(pieces, sliver=GRAPH_EPSILON)
    pruned = graph.pruned()
    joining = pruned.bridges()
    kept = _without_bridges(pruned)
    drop, rim_used = _t_join(kept)
    kept = kept.without(drop)
    on_graph = {id(e) for conn in kept.nodes.values() for e, _ in conn}
    on_graph |= {id(e) for e in kept.degenerate_loops}
    loops, conflicts = _outside_rings(kept)
    return ParityRings(loops=loops, dropped={id(p) for p in pieces} - on_graph,
                       conflicts=conflicts, rim_used=rim_used, joining=joining)


def _without_bridges(graph: Graph) -> Graph:
    while True:
        cut = graph.bridges()
        if not cut:
            return graph
        graph = graph.without(cut).pruned()


def _t_join(graph: Graph) -> Tuple[Set[int], bool]:
    """(id of the T-join sides on the odd nodes of `graph`, if it removes silhouette).
    The weight of a side puts first its length if it is on the outer border, then
    the length: the silhouette is touched only where no set of interior sides
    alone makes the nodes even, and as little as possible."""
    odd = {n for n, conn in graph.nodes.items() if len(conn) % 2}
    if not odd:
        return set(), False
    pieces = {id(e): e for conn in graph.nodes.values() for e, _ in conn}
    on_rim: Set[int] = set()
    for component in graph.connected_components():
        on_rim |= {k for k, passes in outer_face_passes(graph, component, len(pieces)).items()
                   if passes == 1}
    units = {k: round(segment_length(p.segment) / FLOAT_NOISE) for k, p in pieces.items()}
    # more than the length of any matching can weigh
    scale = len(odd) * (sum(units.values()) + 1)
    sides = []
    for k, p in pieces.items():
        a, b = sorted((graph.canonical(p.start), graph.canonical(p.end)))
        weight = (scale if k in on_rim else 0) * units[k] + units[k]
        # ties are decided by the geometry: the ends, the weight, the midpoint
        mid = edge_geometry(p).interpolate(0.5, normalized=True)
        sides.append(((a, b, weight, (mid.x, mid.y)), k))
    sides.sort()
    nodes = sorted({n for (a, b, _, _), _ in sides for n in (a, b)})
    index = {n: i for i, n in enumerate(nodes)}
    chosen, _ = min_t_join(len(nodes), [(index[a], index[b], w) for (a, b, w, _), _ in sides],
                           [index[n] for n in odd])
    drop = {sides[i][1] for i in chosen}
    return drop, bool(drop & on_rim)


def _outside_rings(graph: Graph) -> Tuple[List[list], List[tuple]]:
    """The simple loops of the outside faces, counter-clockwise, each once; and the
    nodes where two neighbouring faces got the same colour."""
    walks = face_walks(graph)
    side: Dict[tuple, int] = {}
    for w, (walk, _) in enumerate(walks):
        for e, frm, _ in walk:
            side[(id(e), frm)] = w
    # colour relative to the outside of its own component: every side changes colour
    colour: Dict[int, int] = {w: 0 for w, (_, outer) in enumerate(walks) if outer}
    queue = list(colour)
    conflicts: List[tuple] = []
    while queue:
        w = queue.pop()
        for e, frm, to in walks[w][0]:
            other = side.get((id(e), to))
            if other is None:
                continue
            if other in colour:
                if colour[other] == colour[w]:
                    conflicts.append(frm)
            else:
                colour[other] = colour[w] ^ 1
                queue.append(other)

    rings = {w: [_ccw(graph, r) for r in simple_rings(walk)] for w, (walk, _) in enumerate(walks)}
    components = graph.connected_components()
    component_of = {n: k for k, comp in enumerate(components) for n in comp}
    # every component (and every loop closed by itself) is inside the outside loops
    # of the others a number of times: the parity is the colour of its outer face
    fences: List[Tuple[object, list, tuple]] = []
    for w, (walk, _) in enumerate(walks):
        if colour.get(w, 0) == 0:
            for loop in rings[w]:
                segments = segments_from_loop(loop)
                fences.append((component_of[walk[0][1]], segments, ring_bbox(segments)))
    for e in graph.degenerate_loops:
        fences.append((("loop", id(e)), [e.segment], ring_bbox([e.segment])))

    def base_colour(key, point) -> int:
        inside = 0
        for owner, segments, (x0, y0, x1, y1) in fences:
            if owner != key and x0 <= point[0] <= x1 and y0 <= point[1] <= y1 \
                    and ring_contains(segments, point):
                inside ^= 1
        return inside

    base = {k: base_colour(k, min(comp)) for k, comp in enumerate(components)}
    loops, seen = [], set()
    for w, (walk, _) in enumerate(walks):
        if colour.get(w, 0) ^ base[component_of[walk[0][1]]]:
            continue
        for loop in rings[w]:
            key = frozenset(id(e) for e, _ in loop)
            if key not in seen:
                seen.add(key)
                loops.append(loop)
    loops += [[(e, False)] for e in graph.degenerate_loops]
    return loops, sorted(set(conflicts))


def _ccw(graph: Graph, ring: list) -> list:
    loop = [(e, graph.canonical(e.start) != frm) for e, frm, _ in ring]
    if ring_moments(segments_from_loop(loop)).area < 0:
        loop = [(e, not rev) for e, rev in reversed(loop)]
    return loop
