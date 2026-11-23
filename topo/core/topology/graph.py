"""
core/topology/graph.py
----------------------
Builds the topological graph.

All geometry is read from edge.geometry (shapely LineString).

Public types:
    Graph              — typed graph with query methods
    build_node_graph   — builds a Graph from list[Edge]
                         automatically separates degenerate loops (start == end)
                         with epsilon > 0 merges nearby endpoints into one node
    cluster_points     — clustering of 2D points within epsilon (union-find)

Internal geometric utilities:
    _edge_coords       — the edge's points as a list (x, y)     [loops.py]
    _arrival_direction — arrival vector                         [loops.py]
    _angular_deviation — angular deviation between directions   [loops.py]
    _first_coord       — first point of the geometry (generic helper)

Node identity
-------------
Every endpoint is the true point (`node_point`, no grid): two nodes are the
same only if the tuples are equal.

`build_node_graph(edges, epsilon)` with `epsilon > 0` adds a real clustering:
it groups the endpoints within `epsilon` (connected components via union-find)
and gives each cluster a single canonical node. `epsilon = 0.0` (default)
keeps the historical behaviour — exact tuple equality — so existing tests and
callers do not change.

Caution: the clustering is transitive. With a large `epsilon` and real nodes
nearby there is a risk of percolation (a row of points at `0.9*epsilon` from
each other collapses into one node). In practice `epsilon` must stay <= the
healing tolerance: real topological nodes (corners, branches) are much farther apart.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Tuple

from .edge import node_point
from ..primitives.mathseg import segment_endpoints
from ..primitives.conics import CircleSeg, is_arc
from .edge import Edge


# ---------------------------------------------------------------------------
# Dataclass Graph
# ---------------------------------------------------------------------------

@dataclass
class Graph:
    """Queryable topological graph.

    nodes:            dict[point, list[(Edge, opposite_point)]]
    degenerate_loops: list[Edge] — edges with start == end (CIRCLE, closed SPLINE)
                      do not enter the graph: they are already complete loops by definition."""
    nodes:            dict       = field(default_factory=dict)
    degenerate_loops: List[Edge] = field(default_factory=list)
    node_map:         Dict[Tuple, Tuple] = field(default_factory=dict)

    def canonical(self, pt: Tuple) -> Tuple:
        """Canonical node for a rounded endpoint.

        Identity if `node_map` is empty (unclustered graph). Otherwise it translates
        the edge's rounded point into the representative of its cluster — it is how
        loops compares edges with nodes."""
        return self.node_map.get(pt, pt)

    def degree(self, node: Tuple) -> int:
        return len(self.nodes.get(self.canonical(node), []))

    def branching_nodes(self) -> list:
        return [n for n, conn in self.nodes.items() if len(conn) > 2]

    def chains(self) -> List[Tuple[List[Edge], Tuple, Tuple]]:
        """The maximal chains of the graph: consecutive edges through nodes of degree 2,
        with the two nodes where they end (branch or free end). A node of degree 2 is
        not a fork: for the topology the chain is a single arc, broken into stretches.
        A ring of degree-2 nodes only has the two ends equal. Every edge of the graph
        is in exactly one chain."""
        seen: set = set()
        chains: List[Tuple[List[Edge], Tuple, Tuple]] = []

        def follow(start: Tuple, edge: Edge, node: Tuple) -> None:
            run = [edge]
            seen.add(id(edge))
            while len(self.nodes[node]) == 2 and node != start:
                nxt = next(((e, n) for e, n in self.nodes[node] if id(e) not in seen), None)
                if nxt is None:
                    break
                run.append(nxt[0])
                seen.add(id(nxt[0]))
                node = nxt[1]
            chains.append((run, start, node))

        # first from the nodes that are not of degree 2, then the remaining rings
        for wanted_inner in (False, True):
            for node, conn in self.nodes.items():
                if (len(conn) == 2) != wanted_inner:
                    continue
                for edge, other in conn:
                    if id(edge) not in seen:
                        follow(node, edge, other)
        return chains

    def connected_components(self) -> List[set]:
        """Connected components of the graph (BFS on the nodes).

        A sheet with several independent views/parts produces several components —
        nodes never reachable from one another because they share no edge. It serves
        whoever must reason by shape (`NonContourEdgeDetector` and `outer_face`, which
        walk the outer face of each view on its own)."""
        seen: set = set()
        components: List[set] = []
        for start in self.nodes:
            if start in seen:
                continue
            stack = [start]
            comp: set = set()
            while stack:
                n = stack.pop()
                if n in comp:
                    continue
                comp.add(n)
                for _edge, neighbor in self.nodes.get(n, []):
                    if neighbor not in comp:
                        stack.append(neighbor)
            seen |= comp
            components.append(comp)
        return components

    def bridges(self) -> set:
        """id of the bridge edges: removed, their two nodes are no longer connected. A
        bridge has the same face on both sides. Iterative Tarjan; two parallel edges
        between the same nodes are not bridges."""
        disc: dict = {}
        low: dict = {}
        out: set = set()
        clock = 0
        for root in self.nodes:
            if root in disc:
                continue
            disc[root] = low[root] = clock
            clock += 1
            stack = [(root, None, iter(self.nodes[root]))]
            while stack:
                node, via, pending = stack[-1]
                for edge, other in pending:
                    if via is not None and id(edge) == via:
                        continue
                    if other not in disc:
                        disc[other] = low[other] = clock
                        clock += 1
                        stack.append((other, id(edge), iter(self.nodes[other])))
                        break
                    low[node] = min(low[node], disc[other])
                else:
                    stack.pop()
                    if stack:
                        parent = stack[-1][0]
                        low[parent] = min(low[parent], low[node])
                        if low[node] > disc[parent]:
                            out.add(via)
        return out

    def without(self, ids: set) -> 'Graph':
        """A new Graph without the edges `ids` (nodes left without edges disappear)."""
        nodes = {n: [(e, o) for e, o in conn if id(e) not in ids] for n, conn in self.nodes.items()}
        return Graph(nodes={n: conn for n, conn in nodes.items() if conn},
                     degenerate_loops=self.degenerate_loops, node_map=self.node_map)

    def open_nodes(self) -> list:
        """Nodes with a single incident edge — the free ends of the graph.

        A contour that should be closed has 0 open nodes; 2 open nodes = a single
        residual gap; many open nodes = tangled geometry (markings, open traces)
        rather than a contour. `pruned()` removes them silently, so it must be queried
        before pruning to get a localized diagnostic."""
        return [n for n, conn in self.nodes.items() if len(conn) == 1]

    def pruned(self) -> 'Graph':
        """Return a new Graph without dead-end nodes (degree <= 1). The degenerate_loops
        are preserved unchanged — they have no nodes in the graph and are not subject
        to pruning."""
        g = {node: list(neighbors) for node, neighbors in self.nodes.items()}

        changed = True
        while changed:
            changed = False
            leaves = [node for node, neighbors in g.items() if len(neighbors) <= 1]
            for leaf in leaves:
                if leaf not in g:
                    continue
                if g[leaf]:
                    edge, neighbor = g[leaf][0]
                    if neighbor in g:
                        g[neighbor] = [(e, n) for e, n in g[neighbor] if n != leaf]
                del g[leaf]
                changed = True

        return Graph(nodes=g, degenerate_loops=self.degenerate_loops,
                     node_map=self.node_map)

    def __iter__(self):
        return iter(self.nodes)

    def __getitem__(self, node):
        return self.nodes[node]

    def __contains__(self, node):
        return node in self.nodes

    def items(self):
        return self.nodes.items()

    def get(self, node, default=None):
        return self.nodes.get(node, default)


# ---------------------------------------------------------------------------
# Clustering endpoint
# ---------------------------------------------------------------------------

def cluster_points(points: list, epsilon: float) -> Dict[Tuple, Tuple]:
    """Group 2D points within `epsilon` and return {point -> representative}.

    Connected components via union-find: two points end up in the same cluster if
    they are <= epsilon apart, and the relation is transitive. The representative
    of a cluster is its lexicographically smallest point — deterministic and
    always a real endpoint (not a fictitious centroid).

    `epsilon <= 0` or fewer than two points → identity map.

    The comparison is limited to the adjacent cells of a grid of side `epsilon`,
    so the cost is linear in the number of points for typical inputs (no O(n²)
    blow-up on files with thousands of edges)."""
    pts = list(dict.fromkeys(points))
    if epsilon <= 0 or len(pts) < 2:
        return {p: p for p in pts}

    parent = {p: p for p in pts}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rb < ra:
            ra, rb = rb, ra
        parent[rb] = ra

    inv_eps = 1.0 / epsilon
    buckets: Dict[Tuple[int, int], list] = defaultdict(list)
    for p in pts:
        buckets[(math.floor(p[0] * inv_eps), math.floor(p[1] * inv_eps))].append(p)

    eps2 = epsilon * epsilon
    for p in pts:
        cx = math.floor(p[0] * inv_eps)
        cy = math.floor(p[1] * inv_eps)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in buckets.get((cx + dx, cy + dy), ()):
                    if q is p:
                        continue
                    ddx = p[0] - q[0]
                    ddy = p[1] - q[1]
                    if ddx * ddx + ddy * ddy <= eps2:
                        union(p, q)

    return {p: find(p) for p in pts}


def connected_groups(n: int, pairs: Iterable[Tuple[int, int]]) -> List[List[int]]:
    """Connected groups of the indices 0..n-1 joined by the pairs `pairs`
    (union-find). Each group in increasing order, the groups by their smallest
    index: the order does not depend on that of the pairs."""
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in pairs:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Costruzione grafo
# ---------------------------------------------------------------------------

def _close_self_loop(edge: Edge, epsilon: float):
    """An arc that returns to its node, if its development (radius*sweep) exceeds epsilon -> the full circle (a true degenerate loop). Otherwise `None` (sliver)."""
    seg = edge.segment
    if not is_arc(seg):
        return None
    if seg.radius * seg._sweep() <= epsilon:
        return None

    # A full turn is a circle, not "a CircleSeg restarting wherever its original end
    # happened to be" — the same primitive as a native CIRCLE, the same canonical
    # point (`segment_endpoints`).
    closed_segment = CircleSeg(center=seg.center, radius=seg.radius)
    anchor = segment_endpoints(closed_segment)[0]
    return replace(edge, start=anchor, end=anchor, segment=closed_segment)


def build_node_graph(edges: list, epsilon: float = 0.0, *, sliver: Optional[float] = None) -> Graph:
    """Build the Graph from list[Edge].

    Edges with start == end (CIRCLE, closed SPLINE) are separated into
    degenerate_loops — they make no sense as graph nodes because their single
    node would be its own neighbour.

    `epsilon > 0` merges the endpoints within `epsilon` into a single canonical
    node (see cluster_points and the note at the top of the module). With
    `epsilon = 0.0` the nodes stay the exact rounded tuples, as in the historical
    behaviour. `sliver`: the threshold of `_close_self_loop` (by default
    `epsilon`); on an already planar network the nodes are the tuples (epsilon 0)
    and the threshold stays."""
    raw        = defaultdict(list)
    degenerate = []

    if epsilon > 0:
        endpoints = []
        for edge in edges:
            if edge.start != edge.end:
                endpoints.append(edge.start)
                endpoints.append(edge.end)
        node_map = cluster_points(endpoints, epsilon)
    else:
        node_map = {}

    def canon(pt):
        return node_map.get(pt, pt)

    for edge in edges:
        if edge.start == edge.end:
            # Degenerate loop: it does not enter the graph, it goes straight to the loop finder
            degenerate.append(edge)
            continue

        s = canon(edge.start)
        e = canon(edge.end)
        if s == e:
            # Endpoints collapsed by the clustering: sliver, unless the edge has a real,
            # non-negligible development.
            closed = _close_self_loop(edge, epsilon if sliver is None else sliver)
            if closed is not None:
                degenerate.append(closed)
            continue

        raw[s].append((edge, e))
        raw[e].append((edge, s))

    return Graph(nodes=dict(raw), degenerate_loops=degenerate, node_map=node_map)


# ---------------------------------------------------------------------------
# Utility geometriche (usate da loops.py)
# ---------------------------------------------------------------------------

def _edge_coords(edge: Edge, reversed_flag: bool) -> list:
    pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
    if reversed_flag:
        pts = list(reversed(pts))
    return pts


def _first_coord(edge: Edge):
    pts = edge.segment.discretize() if edge.segment else [edge.start, edge.end]
    if pts:
        return node_point(pts[0])
    return node_point(edge.start)


def _arrival_direction(edge: Edge, rev: bool):
    coords = _edge_coords(edge, rev)
    if len(coords) < 2:
        return None
    dx = coords[-1][0] - coords[-2][0]
    dy = coords[-1][1] - coords[-2][1]
    return (dx, dy)


def _angular_deviation(arrival_dir, edge: Edge, rev: bool):
    if arrival_dir is None:
        return 0.0
    coords = _edge_coords(edge, rev)
    if len(coords) < 2:
        return 0.0
    dx = coords[1][0] - coords[0][0]
    dy = coords[1][1] - coords[0][1]
    cross = arrival_dir[0] * dy - arrival_dir[1] * dx
    dot   = arrival_dir[0] * dx + arrival_dir[1] * dy
    return abs(math.atan2(cross, dot))