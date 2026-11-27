"""
topo/core/base/cleanup.py
-------------------------
The cleanups of every reading, one per function: non-structural roles, nearly
complete arcs, gaps between free ends, dangling splines. `prepare` and
`normalize` compose them; a caller with another recipe composes them as needed.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable, List, Optional, Tuple


from shapely import STRtree
from shapely.geometry import Point

from ..geometry.measure import FLOAT_NOISE, SAME_POINT, segment_length
from ..topology.edge import node_point
from ...precision import NEAR_FULL_ARC_MISSING_DEG, NEAR_GAP_FACTOR
from ..geometry.points import circle_through
from ..geometry.regions import end_tangent, nearest_point, translation_meeting
from ..primitives.spline import BSplineSeg
from ..primitives.line import LineSeg
from ..primitives.mathseg import DEFAULT_TOLERANCE, segment_endpoints, segment_is_closed
from ..primitives.conics import CircleSeg, is_arc
from ..topology.noding import edge_geometry
from ..topology.edge import Edge
from ..topology.graph import build_node_graph, connected_groups
from ...model.role import ContourRole, is_structural_role
from .merge import _same_circle, merge_cocircular_overlaps
from .gaps import (free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, ambiguous_gap_ends, near_gaps,
                         tied_facing_ends, _moved_segment)


def split_labeled(edges: List[Edge],
                  is_structural: Optional[Callable[[str], bool]] = None
                  ) -> Tuple[List[Edge], List[Edge]]:
    """Separate the Edges with an already decided, non-structural role (frame,
    marking, an unrecognized manufacturing one with no predicate): returns
    (stay in the graph, labelled). Without `is_structural`, only outer/inner are
    structural."""
    structural = is_structural or is_structural_role
    labeled = [e for e in edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    if not labeled:
        return list(edges), []
    labeled_ids = {id(e) for e in labeled}
    return [e for e in edges if id(e) not in labeled_ids], labeled


NEAR_FULL_ARC_MISSING = math.radians(NEAR_FULL_ARC_MISSING_DEG)   # missing angle beyond which an arc is not a circle


def close_near_full_arcs(edges: List[Edge], tolerance: float,
                         max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]:
    """The arcs with both ends free on the same circle (`_same_circle`): a gap
    between an arc and the next within `tolerance` AND with its angle within
    `max_missing_angle` is closed — the tolerance says whether it is a gap, the
    angle whether the arc continues. With all gaps closed it is a CircleSeg;
    otherwise the joined arcs are one arc, open on the remaining gaps (the two
    ends of the same arc are never a gap). A single arc has a single gap.
    `tolerance=math.inf` leaves only the angle. It first merges the arcs of the
    same circle that touch (`merge_cocircular_overlaps`): two arcs joined at one
    end have one end bound each, and whoever calls it need not know.
    Returns (edges, number of edges rebuilt)."""
    edges = merge_cocircular_overlaps(edges)
    graph = build_node_graph(edges)
    free = [k for k, e in enumerate(edges) if is_arc(e.segment) and _both_ends_free(e, graph)]
    pairs = [(m, n) for m in range(len(free)) for n in range(m + 1, len(free))
             if _same_circle(edges[free[m]].segment, edges[free[n]].segment)]
    replaced, drop = {}, set()
    for members in connected_groups(len(free), pairs):
        for chain in _joined_runs([free[m] for m in members], edges, tolerance, max_missing_angle):
            members_k = [span[0] for span in chain if span is not None]
            first = min(members_k)
            replaced[first] = _joined_edge(edges[first], chain)
            drop.update(k for k in members_k if k != first)
    out = [replaced.get(k, e) for k, e in enumerate(edges) if k not in drop]
    return out, len(replaced)


def open_near_full_arcs(edges: List[Edge], tolerance: float,
                        max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> List[Tuple[Edge, float, float]]:
    """The arcs with both ends free that `close_near_full_arcs` leaves open only
    for the angle: the chord of the gap is within `tolerance`, the missing angle
    exceeds `max_missing_angle` but not `NEAR_GAP_FACTOR` times it — the same
    "nearly" as a gap; beyond, the arc is open on purpose. Returns (edges,
    missing angle, chord) — what the warning tells the caller."""
    graph = build_node_graph(edges)
    found = []
    for e in edges:
        if not is_arc(e.segment) or not _both_ends_free(e, graph):
            continue
        start, end = segment_endpoints(e.segment)
        missing, chord = 2 * math.pi - e.segment._sweep(), math.dist(start, end)
        if max_missing_angle < missing <= NEAR_GAP_FACTOR * max_missing_angle and chord <= tolerance:
            found.append((e, missing, chord))
    return found


def _joined_runs(group: List[int], edges: List[Edge], tolerance: float, max_missing_angle: float) -> list:
    """The chains to rebuild: [(index, span)] per chain, going round the circle;
    span = (lo, sweep, lo_node, hi_node). A full turn is a chain with `None` at
    the tail; a one-arc chain that does not close the circle is not rebuilt.
    Overlapping arcs are not judged (`merge_cocircular_overlaps` merges them)."""
    spans = []
    for k in group:
        e, seg = edges[k], edges[k].segment
        start, end = segment_endpoints(seg)
        lo, lo_pt, hi_pt, lo_node, hi_node = ((seg.start_angle, start, end, e.start, e.end) if seg.ccw
                                              else (seg.end_angle, end, start, e.end, e.start))
        spans.append((k, (lo % (2 * math.pi), seg._sweep(), lo_pt, hi_pt, lo_node, hi_node)))
    spans.sort(key=lambda s: s[1][0])
    if math.fsum(s[1][1] for s in spans) > 2 * math.pi:
        return []
    joins = []
    for a, (_, (lo, sweep, _, hi_pt, _, _)) in enumerate(spans):
        nxt_lo, _, nxt_pt, _, _, _ = spans[(a + 1) % len(spans)][1]
        missing = (nxt_lo - (lo + sweep)) % (2 * math.pi)
        joins.append(missing <= max_missing_angle and math.dist(hi_pt, nxt_pt) <= tolerance)
    if all(joins):
        return [spans + [None]]
    # start after a gap that stays open: every chain is a continuous stretch
    start = joins.index(False) + 1
    order = spans[start:] + spans[:start]
    opened = joins[start:] + joins[:start]
    runs, cur = [], []
    for span, joined in zip(order, opened):
        cur.append(span)
        if not joined:
            runs.append(cur)
            cur = []
    return [r for r in runs if len(r) > 1]


def _joined_edge(edge: Edge, chain: list) -> Edge:
    """The edge of a chain: a CircleSeg if it closes the circle (`None` at the
    tail), otherwise the ccw arc from the first end to the last, with their nodes."""
    seg = edge.segment
    if chain[-1] is None:
        circle = CircleSeg(center=seg.center, radius=seg.radius)
        node = node_point(segment_endpoints(circle)[0])
        return replace(edge, start=node, end=node, segment=circle)
    lo, _, _, _, lo_node, _ = chain[0][1]
    last_lo, last_sweep, _, _, _, hi_node = chain[-1][1]
    hi = lo + ((last_lo + last_sweep - lo) % (2 * math.pi))
    arc = CircleSeg(center=seg.center, radius=seg.radius, start_angle=lo, end_angle=hi, ccw=True)
    return replace(edge, start=lo_node, end=hi_node, segment=arc)


def _both_ends_free(edge: Edge, graph) -> bool:
    # an end touching other geometry is not free: the arc belongs to a loop. Ends
    # merged in the same node: the self-loop is among the degenerate ones, so the
    # node must stay without other edges (the tip of a corner is not a circle)
    if edge.start == edge.end:
        return graph.degree(edge.start) == 0
    return graph.degree(edge.start) == 1 and graph.degree(edge.end) == 1


def close_free_gaps(edges: List[Edge], tolerance: float, closed: Optional[list] = None) -> List[Edge]:
    """Close the gaps between free ends within `tolerance` with the gap solver
    (extension to the real intersection or a joining line), pairwise.
    `closed`, if given, receives (end, distance) of every closed gap."""
    graph = build_node_graph(edges)
    endpoints = free_endpoints_from_edges(edges, graph)
    if not endpoints:
        return list(edges)
    fixes = compute_gap_fixes(endpoints, tolerance, edges, closed)
    if not fixes:
        return list(edges)
    return apply_gap_fixes(edges, fixes)


def join_tied_facing_ends(edges: List[Edge], gap: float, joined: Optional[list] = None) -> List[Edge]:
    """Two already bound ends facing each other along their own extension, within
    `gap`, are joined by a new stretch: the side drawn in two pieces with a gap
    between. No curve moves. `joined`, if given, receives (end, distance) of every
    join."""
    out = list(edges)
    for a, b, d in tied_facing_ends(edges, build_node_graph(edges), gap):
        out.append(Edge(role=ContourRole.UNKNOWN, start=getattr(a.ref, a.role), end=getattr(b.ref, b.role),
                        segment=LineSeg(start=tuple(a.pt), end=tuple(b.pt))))
        if joined is not None:
            joined.append((tuple(a.pt), d))
    return out


def bend_arcs_through_free_ends(edges: List[Edge], gap: float, bent: Optional[list] = None) -> List[Edge]:
    """An arc with fixed ends and, beside its belly within `gap`, the free end of a
    curve bound at the other end that arrives tangent: the arc is redrawn through
    its two ends and that end. No line moves. Not if the new arc deviates from
    the old by more than `gap`, not towards a concentric pair nor on an axis. `bent`, if
    given, receives (end, distance) of every redrawn arc."""
    edges = list(edges)
    geoms = [edge_geometry(e) for e in edges]
    tree = STRtree(geoms)
    rounds = [e.segment for e in edges if isinstance(e.segment, CircleSeg)]
    graph = build_node_graph(edges)
    out, done = list(edges), set()
    for i, edge in enumerate(edges):
        if segment_is_closed(edge.segment) or edge.start == edge.end:
            continue
        for p, node, other in zip(segment_endpoints(edge.segment), (edge.start, edge.end), (edge.end, edge.start)):
            if graph.degree(node) != 1 or graph.degree(other) < 2:
                continue
            found = _target(p, i, edges, geoms, tree, gap)
            if found is None or found[0] <= SAME_POINT or found[1] in done:
                continue
            d, k = found
            arc = edges[k].segment
            if not is_arc(arc) or not _may_land(edge.segment, arc, rounds, gap):
                continue
            a, b = segment_endpoints(arc)
            foot = nearest_point([arc], p)
            if min(math.dist(foot, q) for q in (a, b)) <= SAME_POINT:
                continue
            # only a curve arriving tangent to the arc: it was meant to continue in it (the
            # straight side of a slot); one arriving askew ends there on purpose.
            # Tangent: along the whole curve the direction deviates by less than SAME_POINT
            ux, uy = end_tangent(edge.segment, node == edge.end)
            rx, ry = foot[0] - arc.center[0], foot[1] - arc.center[1]
            if segment_length(edge.segment) * abs(ux * rx + uy * ry) > SAME_POINT * math.hypot(rx, ry):
                continue
            circle = circle_through(a, p, b)
            if circle is None:
                continue
            (cx, cy), radius = circle
            new = CircleSeg(center=(cx, cy), radius=radius, start_angle=math.atan2(a[1] - cy, a[0] - cx),
                         end_angle=math.atan2(b[1] - cy, b[0] - cx), ccw=arc.ccw)
            if math.dist(nearest_point([new], p), p) > FLOAT_NOISE:
                continue        # the end falls on the other arc of the circle
            if max(math.dist(q, nearest_point([arc], q)) for q in new.discretize(tolerance=DEFAULT_TOLERANCE)) > gap:
                continue
            out[k] = replace(edges[k], segment=new)
            done.add(k)
            if bent is not None:
                bent.append((p, d))
    return out


def move_onto_targets(edges: List[Edge], gap: float, moved: Optional[list] = None) -> List[Edge]:
    """A fillet (open arc, spline, ellipse: never a line) drawn a few thousandths
    beside what it must touch moves whole. Constraints, all together: a free end
    of it falls on the nearest curve within `gap`; an end bound to a single line
    stays on that line's extension, which lengthens or shortens up to there; the
    free end of another curve within `gap` of the fillet falls on the moved
    fillet. It moves by the unique translation satisfying them, if it does not
    exceed `gap` and if at least one constraint was detached. A line never moves,
    it lengthens or shortens. Not towards a concentric pair (arc or circle with another
    concentric one), not on an axis (line through the centre). `moved`, if given,
    receives (point, displacement) of every moved fillet."""
    edges = list(edges)
    geoms = [edge_geometry(e) for e in edges]
    tree = STRtree(geoms)
    rounds = [e.segment for e in edges if isinstance(e.segment, CircleSeg)]
    graph = build_node_graph(edges)
    at_node: dict = {}
    for k, edge in enumerate(edges):
        for node in {edge.start, edge.end}:
            at_node.setdefault(node, []).append(k)
    # detached free ends, under the nearest curve: whoever can touch it by moving it
    beside: dict = {}
    for k, edge in enumerate(edges):
        if segment_is_closed(edge.segment) or edge.start == edge.end:
            continue
        for p, node in zip(segment_endpoints(edge.segment), (edge.start, edge.end)):
            if graph.degree(node) == 1:
                found = _target(p, k, edges, geoms, tree, gap)
                if found is not None and found[0] > SAME_POINT:
                    beside.setdefault(found[1], []).append((p, k))
    out, touched = list(edges), set()
    for k, edge in enumerate(edges):
        seg = edge.segment
        if isinstance(seg, LineSeg) or segment_is_closed(seg) or edge.start == edge.end:
            continue
        plan = _fillet_constraints(k, edges, geoms, tree, graph, at_node, rounds, gap)
        if plan is None:
            continue
        constraints, stretch, reach, detached = plan
        reached = {j for j, _ in reach}
        for q, owner in beside.get(k, []):
            # the target line lengthens up to the fillet: its end is not an extra constraint
            if owner not in reached and _may_land(edges[owner].segment, seg, rounds, gap):
                constraints.append((q, seg, -1))
                detached = True
        if not detached or len(constraints) < 2:
            continue
        t = translation_meeting(constraints)
        if t is None or math.hypot(*t) > gap:
            continue
        shifted = seg.translated(*t)
        a, b = segment_endpoints(shifted)
        grow = _reached_ends(reach, edge, a, b, edges, graph)
        if grow is None:
            continue
        # a line is blocked per end: two fillets can lengthen it, one per side
        involved = {(k, None)} | {(j, node) for j, node in stretch} | {(j, getattr(edges[j], role)) for j, role, _ in grow}
        if involved & touched:
            continue
        out[k] = replace(edge, segment=shifted, start=node_point(a), end=node_point(b))
        for j, node in stretch:
            new_pt = a if node == edge.start else b
            line = out[j]
            role = "start" if line.start == node else "end"
            out[j] = replace(line, segment=_moved_segment(line.segment, role, new_pt), **{role: node_point(new_pt)})
        for j, role, new_pt in grow:
            out[j] = replace(out[j], segment=_moved_segment(out[j].segment, role, new_pt), **{role: node_point(new_pt)})
        touched |= involved
        if moved is not None:
            moved.append((segment_endpoints(seg)[0], math.hypot(*t)))
    return out


def _reached_ends(reach: list, edge: Edge, a, b, edges: List[Edge], graph):
    """The target lines to lengthen up to the moved end of the fillet:
    [(index, end of the line, point)]. An end falling inside the line lengthens
    nothing; beyond its end, the line lengthens if that end is free. None if a
    bound end would have to lengthen."""
    out = []
    for j, node in reach:
        pt = a if node == edge.start else b
        line = edges[j].segment
        (sx, sy), (ex, ey) = line.start, line.end
        length2 = (ex - sx) ** 2 + (ey - sy) ** 2
        u = ((pt[0] - sx) * (ex - sx) + (pt[1] - sy) * (ey - sy)) / length2 if length2 else 0.0
        if 0.0 <= u <= 1.0:
            continue
        role = "start" if u < 0.0 else "end"
        if graph.degree(getattr(edges[j], role)) != 1:
            return None
        out.append((j, role, pt))
    return out


def _fillet_constraints(k: int, edges: List[Edge], geoms: list, tree, graph, at_node: dict, rounds: list, gap: float):
    """(constraints, bound lines to lengthen, target lines, whether there is a
    detached constraint) of the ends of fillet `k`; None if an end is bound to
    something that is not a single line, or if a detached end would fall on a
    concentric pair or an axis."""
    seg = edges[k].segment
    constraints, stretch, reach, detached = [], [], [], False
    for p, node in zip(segment_endpoints(seg), (edges[k].start, edges[k].end)):
        degree = graph.degree(node)
        if degree == 1:
            found = _target(p, k, edges, geoms, tree, gap)
            if found is None:
                continue
            d, j = found
            if d > SAME_POINT:
                if not _may_land(seg, edges[j].segment, rounds, gap):
                    return None
                detached = True
            if isinstance(edges[j].segment, LineSeg):
                # on a line its extension counts: if the end falls there beyond its end, the
                # line lengthens up to there
                constraints.append((p, _carrier(edges[j].segment, gap), 1))
                reach.append((j, node))
            else:
                constraints.append((p, edges[j].segment, 1))
        elif degree == 2:
            j = next(i for i in at_node[node] if i != k)
            if not isinstance(edges[j].segment, LineSeg):
                return None
            constraints.append((p, _carrier(edges[j].segment, gap), 1))
            stretch.append((j, node))
        else:
            return None
    return constraints, stretch, reach, detached


def _carrier(line: LineSeg, gap: float) -> LineSeg:
    """The line of `line` extended by `2 * gap` at both ends: the end sliding on it
    stays inside."""
    (ax, ay), (bx, by) = line.start, line.end
    length = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / length * 2 * gap, (by - ay) / length * 2 * gap
    return LineSeg(start=(ax - ux, ay - uy), end=(bx + ux, by + uy))


def _target(p, k: int, edges: List[Edge], geoms: list, tree, gap: float):
    """(distance, index) of the curve nearest `p` within `gap`, outside `k`."""
    best = None
    for j in tree.query(Point(p), predicate="dwithin", distance=gap + 2 * DEFAULT_TOLERANCE):
        j = int(j)
        if j == k:
            continue
        d = math.dist(p, nearest_point([edges[j].segment], p))
        if d <= gap and (best is None or d < best[0]):
            best = (d, j)
    return best


def _may_land(seg, target, rounds: list, gap: float) -> bool:
    """A detached end can fall on `target`: no if it is an arc or circle with
    another concentric one, no if `seg` is a line through its centre (axis)."""
    if not isinstance(target, CircleSeg):
        return True
    if any(r is not target and math.dist(r.center, target.center) <= gap for r in rounds):
        return False
    if isinstance(seg, LineSeg):
        (ax, ay), (bx, by) = seg.start, seg.end
        length = math.hypot(bx - ax, by - ay)
        cx, cy = target.center
        if length > 0 and abs((bx - ax) * (ay - cy) - (by - ay) * (ax - cx)) / length <= gap:
            return False
    return True


def near_free_gaps(edges: List[Edge], tolerance: float, reach_to: float) -> list:
    """The gaps between free ends that `close_free_gaps` would close within
    `reach_to` but not within `tolerance`: (end, partner, distance)."""
    return near_gaps(free_endpoints_from_edges(edges, build_node_graph(edges)), tolerance, reach_to, edges)


def ambiguous_free_ends(edges: List[Edge], tolerance: float) -> List[Tuple[float, float]]:
    """The free ends that `close_free_gaps` leaves open: two equally near points,
    none chosen."""
    return ambiguous_gap_ends(free_endpoints_from_edges(edges, build_node_graph(edges)), tolerance, edges)


def dangling_splines(edges: List[Edge]) -> List[Edge]:
    """Open BSplineSegs with at least one end not connected to anything else."""
    open_splines = [e for e in edges if isinstance(e.segment, BSplineSeg) and e.start != e.end]
    if not open_splines:
        return []
    graph = build_node_graph(edges)
    return [e for e in open_splines if graph.degree(e.start) < 2 or graph.degree(e.end) < 2]


def self_crossings(edges: List[Edge]) -> List[Tuple[float, float]]:
    """The points where a spline crosses itself (the other primitives cannot)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    found = []
    for e in edges:
        if not isinstance(e.segment, BSplineSeg):
            continue
        line = LineString(e.segment.discretize())
        if line.is_simple:
            continue
        # the curve knotted on itself: 4 pieces arrive at a crossing
        ends = {}
        for piece in unary_union(line).geoms:
            for p in (piece.coords[0], piece.coords[-1]):
                ends[p] = ends.get(p, 0) + 1
        found += [p for p, n in ends.items() if n >= 4]
    return found


def closed_touches(edges: List[Edge], tolerance: float) -> List[Tuple[float, float]]:
    """The nodes of a closed curve lying on another closed curve."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    from ..primitives.mathseg import segment_is_closed
    closed = [e for e in edges if segment_is_closed(e.segment)]
    if len(closed) < 2:
        return []
    lines = [LineString(e.segment.discretize()) for e in closed]
    tree = STRtree(lines)
    found = []
    for i, e in enumerate(closed):
        node = Point(e.start)
        if any(j != i and lines[j].distance(node) <= tolerance for j in tree.query(node.buffer(tolerance))):
            found.append(tuple(e.start))
    return found
