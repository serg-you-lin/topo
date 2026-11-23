"""
core/topology/outer_face.py
---------------------------
Outer contour of a planar network (noding.py) as the border of its outer
face: an exact, deterministic definition, with no greedy choices.

For each connected component: start from the leftmost point of the geometry —
necessarily on the outer border, even in the middle of an edge — and walk the
edge downwards, so that the outside is on the right; at every node take the
edge that turns least counter-clockwise with respect to the one it arrived
from. An edge walked back and forth is a protrusion (axis, mark, attached
dimension): it is not contour. The network's contour is the outer face of
maximum area among the components (and the loops closed by themselves, like a
circle). If the loop encloses less than the union of the component's closed
faces (nodes not coinciding to the thousandth, arcs tangent to lines), the
contour is the border of that union.

Pure: Edges, graph and primitives only, no format.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import polygonize, unary_union

from ..geometry.measure import SAME_POINT
from .edge import Edge
from ..geometry.integrals import ring_area, ring_moments
from ..geometry.regions import end_tangent
from .noding import GRAPH_EPSILON, edge_geometry
from .graph import Graph, build_node_graph
from .loops import loop_geometry, segments_from_loop
from .rim import face_segments, off_rim
from ..primitives.mathseg import DEFAULT_TOLERANCE


UNION_GRID = SAME_POINT        # mm — grid of the union of faces: below that of the nodes, only the arithmetic decides


@dataclass
class OuterFace:
    """The outer contour found, and what the walk discarded."""
    loop:      list                         # [(Edge, reversed)] as from the LoopFinder
    segments:  list                         # oriented primitives of the contour
    styles:    list
    spurs:     List[Edge] = field(default_factory=list)   # back-and-forth walks
    # the stretches off the border of the loop's edges that run over it only in
    # part (fallback): new Edges, the rest exact from those edges
    rest:      List[Edge] = field(default_factory=list)
    # the face polygon, for questions between several curves (curve_polygon)
    _polygon:  Optional[Polygon] = field(default=None, repr=False, compare=False)

    @property
    def edges(self) -> List[Edge]:
        return [e for e, _ in self.loop]


# --- Public API ---

def outer_face(edges: List[Edge], epsilon: float = 0.0) -> Optional[OuterFace]:
    """Outer contour of the network `edges` (already planar: split_at_crossings). The
    nodes are the pieces' tuples, decided by the noding on the true curves;
    `epsilon` is the threshold of slivers and the band of the union's border.
    None if there is no closed loop."""
    graph = build_node_graph(edges, sliver=epsilon)
    best, spurs = None, []
    for component in graph.connected_components():
        count = outer_face_passes(graph, component, len(edges))
        spurs += [e for e in edges if count.get(id(e), 0) >= 2]
        boundary = [e for e in edges if count.get(id(e)) == 1]
        found = _largest_loop(boundary, epsilon) if boundary else None
        if found is not None and (best is None or _area(found) > _area(best)):
            best = found
    alone = _largest_loop(graph.degenerate_loops, epsilon)
    if alone is not None and (best is None or _area(alone) > _area(best)):
        best = alone
    # the outer face is the border of the union of the closed faces of the whole
    # network, even if the graph sees it in several disconnected components; if the
    # loop encloses less, the union holds
    united = _faces_union_loop(edges, epsilon)
    if united is not None and (best is None or _area(united) > _area(best) * (1 + 1e-6)):
        best = united
    if best is None:
        return None
    loop, segments, styles, polygon = best[:4]
    rest = best[4] if len(best) > 4 else []
    # the walk counts twice also an edge that the chosen loop uses: whoever is in
    # the contour is contour, not a protrusion
    in_loop = {id(e) for e, _ in loop}
    spurs = [e for e in spurs if id(e) not in in_loop]
    return OuterFace(loop=loop, segments=segments, styles=styles, spurs=spurs, rest=rest,
                     _polygon=polygon)


def outer_face_passes(graph: Graph, component, n_edges: int) -> dict:
    """{id(edge): how many times the border of the outer face of `component` walks
    it}. 1 = the edge borders the outside on one side only: it is border; 2 =
    protrusion or bridge, outside on both sides; absent = the edge has a face
    closed on both sides (a chord)."""
    count: dict = {}
    for edge, _, _ in _outer_face_walk(graph, component, n_edges):
        count[id(edge)] = count.get(id(edge), 0) + 1
    return count


# --- Walk ---

def _outer_face_walk(graph: Graph, component, n_edges: int) -> list:
    """[(edge, from node, to node)] along the border of the outer face."""
    step = _stepper(graph)
    first = _first_step(graph, component)
    walk = [first]
    for _ in range(4 * n_edges + 10):
        nxt = step(*walk[-1])
        if nxt == first:
            break
        walk.append(nxt)
    return walk


def face_walks(graph: Graph) -> List[tuple]:
    """Every face of the planar network `graph`, as (loop, outer): the loop is
    [(edge, from node, to node)], every side of every edge walked once, with the
    same turn as the outer border (`_stepper`); `outer` says whether it is the
    outer face of a component (the one starting from its leftmost point,
    `_first_step`). No choice depends on the order of the edges."""
    step = _stepper(graph)
    outer = {(id(e), frm) for e, frm, _ in (_first_step(graph, c) for c in graph.connected_components())}
    used, walks = set(), []
    for node in graph.nodes:
        for edge, other in graph[node]:
            start = (edge, node, other)
            if (id(edge), node) in used:
                continue
            walk, cur = [], start
            while (id(cur[0]), cur[1]) not in used:
                used.add((id(cur[0]), cur[1]))
                walk.append(cur)
                cur = step(*cur)
            if cur[0] is start[0] and cur[1] == start[1]:
                walks.append((walk, any((id(e), frm) in outer for e, frm, _ in walk)))
    return walks


def face_loops(edges: List[Edge], epsilon: float = GRAPH_EPSILON) -> List[list]:
    """The loops of the bounded faces of the planar network `edges`
    (split_at_crossings; nodes are the pieces' tuples; `epsilon` the sliver
    threshold), divided into simple loops, each once, as [(edge, path_reversed)]
    counter-clockwise; plus the pieces closed by themselves (a circle). What
    heal() calls contours."""
    graph = build_node_graph(edges, sliver=epsilon)
    loops, seen = [], set()
    for walk, is_outer in face_walks(graph):
        if is_outer:
            continue
        for ring in simple_rings(walk):
            key = frozenset(id(e) for e, _, _ in ring)
            if key in seen:
                continue
            seen.add(key)
            loop = [(e, graph.canonical(e.start) != frm) for e, frm, _ in ring]
            # counter-clockwise direction from the signed area on the primitives
            if ring_moments(segments_from_loop(loop)).area < 0:
                loop = [(e, not rev) for e, rev in reversed(loop)]
            loops.append(loop)
    return loops + [[(e, False)] for e in graph.degenerate_loops]


def simple_rings(walk: list) -> List[list]:
    """The simple loops of a face: where the loop passes again through a node a loop
    is detached (two loops touching at a point are two loops). A back and forth on
    the same edge is not a loop. Each loop as [(edge, from node, to node)]."""
    rings, stack, at = [], [], {}
    for item in walk:
        node = item[1]
        if node in at:
            k = at[node]
            ring = stack[k:]
            del stack[k:]
            for _, n, _ in ring:
                at.pop(n, None)
            rings.append(ring)
        at[node] = len(stack)
        stack.append(item)
    if stack:
        rings.append(stack)
    return [r for r in rings if len({id(e) for e, _, _ in r}) > 1 or len(r) == 1 and r[0][1] == r[0][2]]


def _stepper(graph: Graph):
    """The step of the walk: arriving at a node by an edge, take the edge that turns
    least counter-clockwise with respect to the one arrived from; go back only if
    there is no other. One function for the outer face and for all the faces."""
    angles: dict = {}

    def angle(edge, node):
        key = (id(edge), node)
        if key not in angles:
            angles[key] = _leaving_angle(edge, node, graph)
        return angles[key]

    def step(edge, frm, node):
        back_angle = angle(edge, node)
        best, best_turn = None, None
        for nxt, other in graph[node]:
            turn = (angle(nxt, node) - back_angle) % (2 * math.pi)
            if nxt is edge or turn < 1e-9:
                turn = 2 * math.pi       # go back: only if there is no other
            if best_turn is None or turn < best_turn:
                best, best_turn = (nxt, node, other), turn
        return best

    return step


def _first_step(graph: Graph, component):
    """The edge containing the component's leftmost point, walked downwards; if that
    point is a node, the first edge counter-clockwise starting from west."""
    best = None   # (leftmost point, edge, its points, index)
    for node in component:
        for edge, _ in graph[node]:
            pts = edge.segment.discretize(tolerance=DEFAULT_TOLERANCE)
            i = min(range(len(pts)), key=lambda k: (pts[k][0], pts[k][1]))
            if best is None or (pts[i][0], pts[i][1]) < best[0]:
                best = ((pts[i][0], pts[i][1]), edge, pts, i)
    _, edge, pts, i = best
    a, b = graph.canonical(edge.start), graph.canonical(edge.end)
    if 0 < i < len(pts) - 1:
        going_down = pts[i + 1][1] - pts[i - 1][1] < 0
        return (edge, a, b) if going_down else (edge, b, a)
    start = a if i == 0 else b
    choice = min(graph[start],
                 key=lambda eo: (_leaving_angle(eo[0], start, graph) - math.pi) % (2 * math.pi))
    return (choice[0], start, choice[1])


def _leaving_angle(edge: Edge, node, graph: Graph) -> float:
    """Direction in which `edge` leaves `node`, read where the curve has deviated by
    SAME_POINT from its tangent (or at mid-edge, a line): a fillet tangent to a
    line starts like it and differs only there. It is measured from the node, not
    from the curve's first point: a contact within tolerance puts the node that
    far from the curve, and two pieces parallel at that distance leave it with
    different directions."""
    pts = edge.segment.discretize(tolerance=DEFAULT_TOLERANCE)
    backwards = graph.canonical(edge.start) != node
    if backwards:
        pts = list(reversed(pts))
    tx, ty = end_tangent(edge.segment, at_end=backwards)
    if backwards:
        tx, ty = -tx, -ty
    norm = math.hypot(tx, ty)
    total = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    reach = total / 2
    walked, target = 0.0, pts[-1]
    x0, y0 = pts[0]
    off = 0.0
    for i in range(len(pts) - 1):
        step = math.dist(pts[i], pts[i + 1])
        next_off = abs(tx * (pts[i + 1][1] - y0) - ty * (pts[i + 1][0] - x0)) / norm if norm else 0.0
        if step > 0 and (walked + step >= reach or next_off >= SAME_POINT):
            t = min((reach - walked) / step,
                    (SAME_POINT - off) / (next_off - off) if next_off >= SAME_POINT > off else 1.0)
            t = min(max(t, 0.0), 1.0)
            target = (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]),
                      pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
            break
        walked, off = walked + step, next_off
    return math.atan2(target[1] - node[1], target[0] - node[0])


def _faces_union_loop(edges: List[Edge], epsilon: float):
    """(loop, segments, styles, polygon) on the border of the union of the closed
    faces of the network, with the contacts within `epsilon` (`_network`); None if
    the network closes no face. If the border edges do not close in a graph loop,
    the polygon is the union, the loop is the edges lying wholly on it, and the
    segments are read walking the union's ring (`rim.face_segments`); an edge
    running over it only in part belongs to the loop, and its remainder
    (`rim.off_rim`) is the fifth element."""
    faces = list(polygonize(_network(edges, epsilon)))
    if not faces:
        return None
    union = unary_union(faces)
    region = max(getattr(union, "geoms", [union]), key=lambda g: g.area)
    band = 2 * max(epsilon, 1e-6)
    rim = region.exterior.buffer(band)
    on_rim = [e for e in edges if rim.contains(edge_geometry(e))]
    found = _largest_loop(on_rim, epsilon) if on_rim else None
    if found is not None and found[3].area >= region.area * 0.99:
        return found
    if not on_rim:
        return None
    outer = Polygon(region.exterior)
    segments, styles, used = face_segments(edges, outer, band)
    on_rim_ids = {id(e) for e in on_rim}
    partial = [edges[j] for j in sorted(used) if id(edges[j]) not in on_rim_ids]
    rest = [piece for j in sorted(used) if id(edges[j]) not in on_rim_ids
            for piece in off_rim(edges[j], used[j], region.exterior, band)]
    return [(e, False) for e in on_rim + partial], segments, styles, outer, rest


def _network(edges: List[Edge], epsilon: float):
    """The network of `edges` as shapely lines, with the ends on the graph's nodes.
    The contacts are already decided by the noding, once on the curves: here no
    connection by distance between discretizations."""
    graph = build_node_graph(edges, sliver=epsilon)
    return shapely.unary_union(_on_nodes(edges, graph), grid_size=UNION_GRID)


def _on_nodes(edges: List[Edge], graph: Graph) -> list:
    """The geometries of `edges` with the ends on the graph's nodes: two ends within
    `epsilon` touch by distance, as in the walk, not because they fall in the
    same cell of a grid fixed to the axes. A piece closed by itself (circle) stays as it is."""
    geometries = [edge_geometry(e) for e in edges]
    lines = [k for k, g in enumerate(geometries) if g.geom_type == "LineString"]
    coords, owner = shapely.get_coordinates([geometries[k] for k in lines], return_index=True)
    first = np.searchsorted(owner, np.arange(len(lines)))
    last = np.append(first[1:], len(owner)) - 1
    for n, k in enumerate(lines):
        if edges[k].start != edges[k].end:
            coords[first[n]] = graph.canonical(edges[k].start)
            coords[last[n]] = graph.canonical(edges[k].end)
    others = [g for g in geometries if g.geom_type != "LineString"]
    return list(shapely.linestrings(coords, indices=owner)) + others


def _largest_loop(edges: List[Edge], epsilon: float):
    """(loop, segments, styles, polygon) of the loop of maximum area."""
    best = None
    for loop in face_loops(edges, epsilon):
        geometry = loop_geometry(loop)
        if geometry is not None and (best is None or ring_area(geometry[0]) > _area(best)):
            best = (loop, *geometry)
    return best


def _area(found) -> float:
    """Exact area of a candidate's loop (loop, segments, ...), on the primitives."""
    return ring_area(found[1])
