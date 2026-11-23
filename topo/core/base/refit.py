"""
topo/core/base/refit.py
-----------------------
Refit: a curve written in another form comes back as primitives. No merging of
copies (those are in `merge.py`): here a group of pieces or a curve becomes
another primitive, within a threshold.

    refit_tessellations — a chain of many short LineSegs is a curve written as
                          points: refitted as arc/circle/spline
                          (fitting.simplify_points) within POINTS_NOISE of the
                          points; a smaller detail is lost.
    refit_native_curves — a spline within SAME_POINT of an arc or an ellipse
                          becomes that (fitting.conic_of_spline); an ellipse
                          with equal semi-axes, its circle.
    refit_circle_rings  — a group of pieces going round a circle within
                          POINTS_NOISE is that circle.
    chain_runs          — the maximal chains of short sides: the path the
                          refit of tessellations follows.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from typing import Iterable, List, Tuple

from ...precision import POINTS_NOISE, TESSELLATION_RUN, TESSELLATION_SIDE
from ...model.role import ContourRole
from ..geometry.fitting import conic_of_spline, simplify_points
from ..geometry.measure import SAME_POINT
from ..topology.edge import node_point
from ..geometry.points import fit_circle_kasa
from ..primitives.conics import CircleSeg, EllipseSeg, is_full_circle
from ..primitives.line import LineSeg
from ..primitives.mathseg import Point, segment_endpoints
from ..primitives.spline import BSplineSeg
from ..topology.edge import Edge
from ..topology.graph import build_node_graph, connected_groups


def refit_tessellations(
    edges: Iterable[Edge],
    max_segment: float = TESSELLATION_SIDE,
    min_run: int = TESSELLATION_RUN,
    tolerance: float = POINTS_NOISE,
) -> List[Edge]:
    """A chain of at least `min_run` LineSegs (`role == UNKNOWN`) shorter than
    `max_segment`, connected one after the other, is a curve written as points:
    it becomes the primitives of `simplify_points` (lines, arcs, splines within
    `tolerance`; a corner is a turn over `max_segment`). The ends of the chain
    keep the original nodes, so it stays attached to the neighbours. The rest is
    not touched."""
    edges = list(edges)
    short = [e for e in edges
             if isinstance(e.segment, LineSeg) and e.role == ContourRole.UNKNOWN
             and e.start != e.end
             and math.dist(e.segment.start, e.segment.end) < max_segment]
    replaced, new_edges = set(), []
    for path, closed in chain_runs(short):
        if len(path) < min_run:
            continue
        pts = []
        for edge, rev in path:
            a, b = (edge.segment.end, edge.segment.start) if rev else (edge.segment.start, edge.segment.end)
            if not pts:
                pts.append(a)
            pts.append(b)
        if closed:
            pts = pts[:-1]
        prims = simplify_points(pts, tolerance=tolerance, scale=max_segment, closed=closed, corner_turn_deg=None)
        if not prims:
            continue
        first, last = path[0], path[-1]
        start_node = first[0].end if first[1] else first[0].start
        end_node = last[0].start if last[1] else last[0].end
        # a junction is a single node, the end of the arriving piece; the start of the
        # next (1 ulp away) does not count, or the two copies detach the chain
        nodes = [node_point(segment_endpoints(prims[0])[0])] + [node_point(segment_endpoints(p)[1]) for p in prims]
        if closed:
            nodes[-1] = nodes[0]
        else:
            nodes[0], nodes[-1] = start_node, end_node
        for k, prim in enumerate(prims):
            new_edges.append(replace(first[0], segment=prim, start=nodes[k], end=nodes[k + 1]))
        replaced |= {id(edge) for edge, _ in path}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def refit_native_curves(edges: Iterable[Edge], tolerance: float = SAME_POINT) -> List[Edge]:
    """A curve of the file that is a simpler primitive becomes that, same ends and
    same nodes: a spline within `tolerance` of an arc or an ellipse
    (`conic_of_spline`); an ellipse with equal semi-axes, its circle (exact). The
    others stay as they are."""
    out = []
    for e in edges:
        s, simpler = e.segment, None
        if isinstance(s, BSplineSeg):
            simpler = conic_of_spline(s, tolerance)
        elif type(s) is EllipseSeg and s.ratio == 1.0:
            simpler = _circle_of(s)
        out.append(e if simpler is None else replace(e, segment=simpler))
    return out


def _circle_of(s: EllipseSeg) -> CircleSeg:
    """The ellipse with equal semi-axes as a circle: its parameter plus the axis angle is the angle."""
    phi = math.atan2(s.major_axis[1], s.major_axis[0])
    return CircleSeg(center=s.center, radius=math.hypot(*s.major_axis), start_angle=s.start_param + phi,
                     end_angle=s.end_param + phi, ccw=s.ccw)


def refit_circle_rings(edges: Iterable[Edge], tolerance: float = POINTS_NOISE) -> List[Edge]:
    """A connected group of `role == UNKNOWN` pieces (no CircleSeg) whose core (the
    group without the free-ended branches) lies wholly within `tolerance` of a
    circle and goes completely round it is that circle: the core becomes a
    CircleSeg, at any size of the sides. A free-ended branch, or an isolated
    piece, running over it goes with the circle; the others stay. The deviation
    is measured on the whole piece (for a line also the point nearest the
    centre), so a true polygon stays."""
    edges = list(edges)
    node_edges: dict = {}
    for k, e in enumerate(edges):
        for p in (e.start, e.end):
            node_edges.setdefault(p, []).append(k)
    pairs = [(ks[0], k) for ks in node_edges.values() for k in ks[1:]]
    loose = [e for e in edges if len(node_edges[e.start]) == 1 and len(node_edges[e.end]) == 1]
    replaced, new_edges = set(), []
    for group in connected_groups(len(edges), pairs):
        core = _without_free_branches([edges[k] for k in group])
        if not core or not all(
                not is_full_circle(e.segment) and e.role == ContourRole.UNKNOWN for e in core):
            continue
        pts = [p[:2] for e in core for p in ([e.segment.start, e.segment.end, _chord_midpoint(e.segment)]
                                             if isinstance(e.segment, LineSeg) else e.segment.discretize(tolerance=tolerance / 10))]
        fit = fit_circle_kasa(pts)
        if fit is None:
            continue
        segments = [e.segment for e in core]
        near, far = _ring_band(segments, fit[0])
        radius = (near + far) / 2   # the radius midway between the nearest and the farthest point
        if radius <= tolerance or far - radius > tolerance or not _full_turn(segments, fit[0], tolerance / radius):
            continue
        circle = CircleSeg(center=fit[0], radius=radius)
        node = node_point(segment_endpoints(circle)[0])
        new_edges.append(replace(core[0], segment=circle, start=node, end=node))
        # a free branch, or an isolated piece, also running on the circle is a double stretch of the loop
        on_ring = [e for e in [edges[k] for k in group] + loose
                   if e.role == ContourRole.UNKNOWN and not is_full_circle(e.segment)
                   and math.dist(node_point(e.start), fit[0]) <= radius + tolerance
                   and _within_band(e.segment, fit[0], radius, tolerance)]
        replaced |= {id(e) for e in core} | {id(e) for e in on_ring}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def _chord_midpoint(s: LineSeg) -> Point:
    """The midpoint of the line: with the fit on the ends and the middles the circle lies between the two, not on the vertices."""
    return ((s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2)


def _without_free_branches(group: List[Edge]) -> List[Edge]:
    """The group without the branches ending in a free end (removed one at a time while there are any)."""
    core = [e for e in group if e.start != e.end or not isinstance(e.segment, LineSeg)]
    while True:
        degree = Counter(p for e in core for p in (e.start, e.end))
        kept = [e for e in core if degree[e.start] > 1 and degree[e.end] > 1]
        if len(kept) == len(core):
            return core
        core = kept


def _full_turn(segments, center, slack: float) -> bool:
    """The pieces, seen from the centre, cover the whole turn: no uncovered wedge wider than `slack` radians."""
    spans = []
    for s in segments:
        pts = [s.start, s.end] if isinstance(s, LineSeg) else s.discretize(tolerance=SAME_POINT)
        angles = [math.atan2(p[1] - center[1], p[0] - center[0]) % (2 * math.pi) for p in pts]
        for u, v in zip(angles, angles[1:]):
            lo, hi = min(u, v), max(u, v)
            spans += [(lo, hi)] if hi - lo <= math.pi else [(hi, 2 * math.pi), (0.0, lo)]
    reach = 0.0
    for lo, hi in sorted(spans):
        if lo > reach + slack:
            return False
        reach = max(reach, hi)
    return reach >= 2 * math.pi - slack


def _within_band(segment, center, radius: float, tolerance: float) -> bool:
    """The piece lies wholly within `tolerance` of the circle."""
    near, far = _ring_band([segment], center)
    return radius - near <= tolerance and far - radius <= tolerance


def _ring_band(segments, center) -> Tuple[float, float]:
    """Minimum and maximum distance of the pieces from the centre: for a line its ends and its nearest point, for
    the other curves their points."""
    near, far = math.inf, 0.0
    for s in segments:
        if isinstance(s, LineSeg):
            (ax, ay), (bx, by) = s.start[:2], s.end[:2]
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((center[0] - ax) * dx + (center[1] - ay) * dy) / length2)) if length2 else 0.0
            near = min(near, math.dist(center, (ax + t * dx, ay + t * dy)))
            far = max(far, math.dist(center, s.start[:2]), math.dist(center, s.end[:2]))
        else:
            ds = [math.dist(center, p[:2]) for p in s.discretize(tolerance=SAME_POINT)]
            near, far = min(near, *ds), max(far, *ds)
    return near, far


def chain_runs(short_edges: List[Edge]) -> list:
    """Maximal chains: paths between nodes of degree != 2, or rings.
    [( [(edge, path_reversed)], closed )].
    """
    graph = build_node_graph(short_edges)
    used: set = set()
    runs = []

    def walk(start, first_edge, first_other):
        path, node, edge, other = [], start, first_edge, first_other
        while True:
            used.add(id(edge))
            path.append((edge, graph.canonical(edge.start) != node))
            node = other
            nxt = [(e, o) for e, o in graph[node] if id(e) not in used]
            if len(graph[node]) != 2 or not nxt:
                return path, node
            edge, other = nxt[0]

    for n in [n for n in graph if len(graph[n]) != 2]:
        for e, o in graph[n]:
            if id(e) not in used:
                path, _ = walk(n, e, o)
                runs.append((path, False))
    for n in graph:
        for e, o in graph[n]:
            if id(e) not in used:
                path, last = walk(n, e, o)
                runs.append((path, last == n))
    return runs
