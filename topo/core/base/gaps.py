"""
topo/core/base/gaps.py
------------------------
Pure geometric computation of closing the gaps between segments.

No format: coordinates only. It works on Python coordinates and returns
correction instructions (GapFix).

The caller (adapter) is responsible for:
    - extracting GapEndpoint from the source format
    - applying GapFix to the native document

Public types:
    GapEndpoint   — free endpoint with an opaque ref to the source format
    MoveEndpoint  — instruction: move the endpoint of ref to new_pt
    AddSegment    — instruction: add a segment between pt_a and pt_b
    GapFix        — Union[MoveEndpoint, AddSegment]

Public functions:
    compute_gap_fixes — given a set of free endpoints, compute the fixes
    ambiguous_gap_ends — the ends that do not choose between equally near partners
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

from shapely import STRtree
from shapely.geometry import Point

from ..geometry.measure import FLOAT_NOISE
from ..topology.edge import node_point
from ..geometry.intersections import (
    circle_circle_intersections, circle_line_intersections, closest_to, intersections, line_intersection,
)
from ..geometry.regions import end_tangent, nearest_point
from ..primitives.mathseg import MathSeg, DEFAULT_TOLERANCE, segment_endpoints
from ..primitives.line import LineSeg
from ..primitives.spline import BSplineSeg
from ..primitives.conics import CircleSeg, EllipseSeg, is_arc
from ..topology.noding import GRAPH_EPSILON, edge_geometry
from ..topology.edge import Edge
from ...model.role import ContourRole

Point2D = Tuple[float, float]


# --- Input types ---

@dataclass
class GapEndpoint:
    """Free endpoint in the topological graph.

    Attributes:
        pt   : (x, y) coordinates of the endpoint
        ref  : opaque reference to the source entity — the adapter knows what it is
        role : 'start' | 'end'
        kind : geometric type — 'line' | 'arc' | 'spline' | 'ellipse'
               used by the solver to choose the fix strategy
        meta : extra data the solver may use for the computation
               for LINE: {'start': pt, 'end': pt}
               for ARC:  {'cx': float, 'cy': float, 'radius': float}
               for SPLINE: {} (no data useful to the solver)"""
    pt:   Point2D
    ref:  Any
    role: str
    kind: str
    meta: dict


# --- Output types (GapFix) ---

@dataclass
class MoveEndpoint:
    """Instruction: move the endpoint role of ref to the point new_pt.
    The adapter translates ref → native entity and applies the move."""
    ref:    Any
    role:   str
    new_pt: Point2D


@dataclass
class AddSegment:
    """Instruction: add a straight segment between pt_a and pt_b.
    Used as a fallback when no geometric intersection is found."""
    pt_a: Point2D
    pt_b: Point2D
    # the already decided nodes of the ends it connects: the segment attaches
    # there, not to the grid cell of the real point
    node_a: Optional[Point2D] = None
    node_b: Optional[Point2D] = None


GapFix = Union[MoveEndpoint, AddSegment]


# --- Geometric solver — logic per pair of kinds ---

def _solve_line_line(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    s_a = ep_a.meta['start']
    e_a = ep_a.meta['end']
    s_b = ep_b.meta['start']
    e_b = ep_b.meta['end']
    ix = line_intersection(s_a, e_a, s_b, e_b)
    return _meet_or_bridge(ix, ep_a, ep_b)


def _solve_arc_line(
    ep_arc:  GapEndpoint,
    ep_line: GapEndpoint,
) -> List[GapFix]:
    cx     = ep_arc.meta['cx']
    cy     = ep_arc.meta['cy']
    radius = ep_arc.meta['radius']
    s_l    = ep_line.meta['start']
    e_l    = ep_line.meta['end']
    candidates = circle_line_intersections(cx, cy, radius, s_l, e_l)
    ix = closest_to(candidates, ep_arc.pt, ep_line.pt)
    return _meet_or_bridge(ix, ep_arc, ep_line)


def _solve_arc_arc(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    candidates = circle_circle_intersections(
        ep_a.meta['cx'], ep_a.meta['cy'], ep_a.meta['radius'],
        ep_b.meta['cx'], ep_b.meta['cy'], ep_b.meta['radius'],
    )
    ix = closest_to(candidates, ep_a.pt, ep_b.pt)
    return _meet_or_bridge(ix, ep_a, ep_b)


def _solve_spline_any(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    # Splines have no simple analytic geometry to intersect — straight fallback
    # to the closing segment.
    return [_bridge(ep_a, ep_b)]


# Registry: (kind_a, kind_b) → solver
# Pairs are normalized to a canonical order in compute_gap_fixes.
_SOLVERS = {
    ('line',   'line'):   _solve_line_line,
    ('arc',    'line'):   lambda a, b: _solve_arc_line(a, b),
    ('line',   'arc'):    lambda a, b: _solve_arc_line(b, a),   # riordina
    ('arc',    'arc'):    _solve_arc_arc,
    ('spline', 'line'):   lambda a, b: _solve_spline_any(a, b),
    ('line',   'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'arc'):    lambda a, b: _solve_spline_any(a, b),
    ('arc',    'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'spline'): lambda a, b: _solve_spline_any(a, b),
}


def _bridge(ep_a: GapEndpoint, ep_b: GapEndpoint) -> AddSegment:
    """The segment between two ends, attached to their nodes."""
    return AddSegment(pt_a=ep_a.pt, pt_b=ep_b.pt, node_a=_node(ep_a), node_b=_node(ep_b))


def _node(ep: GapEndpoint) -> Optional[Point2D]:
    if isinstance(ep.ref, Edge):
        return ep.ref.start if ep.role == "start" else ep.ref.end
    return None


def _get_solver(kind_a: str, kind_b: str):
    solver = _SOLVERS.get((kind_a, kind_b))
    if solver is None:
        # unknown kind → AddSegment fallback
        return lambda a, b: [_bridge(a, b)]
    return solver


# --- Public function ---

def compute_gap_fixes(endpoints: List[GapEndpoint], tolerance: float,
                      edges: Sequence[Edge] = (), closed: Optional[list] = None) -> List[GapFix]:
    """Compute the GapFixes of the free ends within `tolerance`, one rule for every
    reading. Each end closes on the nearest point of the network: another free
    end (the two meet or join with a segment, and neither closes anything else),
    or the point where its curve, continued, meets another edge of `edges` — in
    the middle of a curve or on a node of it (never with a bridge across). The
    two ends of the same edge are never a gap (`close_near_full_arcs`). An end
    with its two nearest points equally near does not choose: in a symmetric
    figure no rule gives the same partner in every frame.
    `closed`, if given, receives (end, distance) of every closed gap."""
    candidates = _candidates(endpoints, tolerance, edges)
    ambiguous = _ambiguous_from(candidates, endpoints)
    fixes: List[GapFix] = []
    taken: set = set()
    for d, _, i, target in sorted(candidates, key=lambda c: (c[0], c[1])):
        if i in ambiguous or i in taken:
            continue
        ep = endpoints[i]
        if target[0] == "end":
            j = target[1]
            if j in ambiguous or j in taken:
                continue
            taken.update((i, j))
            if closed is not None:
                closed.append((ep.pt, d))
            other = endpoints[j]
            fixes.extend(_within_reach(_get_solver(ep.kind, other.kind)(ep, other), ep, other, tolerance))
        else:
            taken.add(i)
            if closed is not None:
                closed.append((ep.pt, d))
            fixes.extend(_onto_curve(ep, target[1], target[2], target[3], tolerance))
    return fixes


def near_gaps(endpoints: List[GapEndpoint], tolerance: float, reach_to: float,
              edges: Sequence[Edge] = ()) -> List[Tuple[Point2D, Point2D, float]]:
    """The gaps `compute_gap_fixes` would close with `reach_to` and not with
    `tolerance`: for every free end the nearest partner by the same rule
    (another end, or the meeting of its continued curve), if it is beyond
    `tolerance` and within `reach_to`. Returns (end, partner, distance), once per
    pair, shortest first — what the warning tells the caller. An equally-near end
    has no partner."""
    candidates = _candidates(endpoints, reach_to, edges)
    ambiguous = _ambiguous_from(candidates, endpoints)
    best: dict = {}
    for d, key, i, target in candidates:
        if i not in ambiguous and (i not in best or (d, key) < best[i][:2]):
            best[i] = (d, key, target)
    seen, out = set(), []
    for i, (d, _, target) in sorted(best.items(), key=lambda kv: kv[1][:2]):
        if d <= tolerance:
            continue
        if target[0] == "end":
            pair = frozenset((i, target[1]))
            if pair in seen:
                continue
            seen.add(pair)
            out.append((endpoints[i].pt, endpoints[target[1]].pt, d))
        else:
            out.append((endpoints[i].pt, target[2], d))
    return out


def _candidates(endpoints: List[GapEndpoint], tolerance: float, edges: Sequence[Edge]) -> list:
    """(distance, ordering key, i, target) for every end `i`: ("end", j) another free
    end; ("curve", edge, meeting, node) where the curve of `i`, continued, meets
    another edge (`_continuation`). A meeting on a free end is already the pair of
    ends; one within GRAPH_EPSILON is connected by the noding, not a gap."""
    out = [(d, key, i, ("end", j)) for d, key, i, j in _gap_pairs(endpoints, tolerance)]
    out += [(d, key, j, ("end", i)) for d, key, i, j in _gap_pairs(endpoints, tolerance)]
    if not edges:
        return out
    free = {getattr(ep.ref, ep.role) for ep in endpoints if isinstance(ep.ref, Edge)}
    geoms = [edge_geometry(e) for e in edges]
    tree = STRtree(geoms)
    for i, ep in enumerate(endpoints):
        ahead = _continuation(ep, tolerance)
        if ahead is None:
            continue
        for k in tree.query(Point(ep.pt), predicate="dwithin", distance=tolerance + 2 * DEFAULT_TOLERANCE):
            edge = edges[int(k)]
            if edge is ep.ref:
                continue
            hits = [q for q in intersections(ahead, edge.segment) if math.dist(q, ep.pt) > GRAPH_EPSILON]
            if not hits:
                continue
            meet = min(hits, key=lambda q: math.dist(q, ep.pt))
            d = math.dist(ep.pt, meet)
            if d > tolerance:
                continue
            node = next((n for n, q in zip((edge.start, edge.end), segment_endpoints(edge.segment))
                         if math.dist(meet, q) <= GRAPH_EPSILON), None)
            if node is not None and node in free:
                continue
            out.append((d, (tuple(ep.pt), tuple(meet)), i, ("curve", edge, meet, node)))
    return out


def _continuation(ep: GapEndpoint, reach: float):
    """The curve of end `ep` continued past its end by `reach`: a line with its
    direction, an arc on its circle, a spline or ellipse with the tangent at the
    end. An end closes on a curve only where it meets it: never with a bridge
    across, which the drawing does not suggest. None if it has no direction
    (null stretch)."""
    seg = ep.ref.segment if isinstance(ep.ref, Edge) else None
    if is_arc(seg) and seg.radius > 0:
        step = min(reach / seg.radius, math.pi / 2)
        sign = 1.0 if seg.ccw else -1.0
        if ep.role == "end":
            return CircleSeg(center=seg.center, radius=seg.radius, start_angle=seg.end_angle,
                          end_angle=seg.end_angle + sign * step, ccw=seg.ccw)
        return CircleSeg(center=seg.center, radius=seg.radius, start_angle=seg.start_angle,
                      end_angle=seg.start_angle - sign * step, ccw=not seg.ccw)
    if isinstance(seg, LineSeg):
        far = seg.start if ep.role == "end" else seg.end
        length = math.dist(far, ep.pt)
        if length <= 0:
            return None
        ux, uy = (ep.pt[0] - far[0]) / length, (ep.pt[1] - far[1]) / length
    elif seg is not None:
        # the true tangent at the end, pointing outwards
        tx, ty = end_tangent(seg, at_end=ep.role == "end")
        ux, uy = (tx, ty) if ep.role == "end" else (-tx, -ty)
    else:
        return None
    return LineSeg(start=tuple(ep.pt), end=(ep.pt[0] + ux * reach, ep.pt[1] + uy * reach))


def tied_facing_ends(edges: Sequence[Edge], graph, tolerance: float) -> List[Tuple[GapEndpoint, GapEndpoint, float]]:
    """The pairs of already bound ends (degree >= 2) of different edges facing each
    other: each on the extension of the other's curve within GRAPH_EPSILON, more
    than GRAPH_EPSILON and within `tolerance` apart. A side drawn in two pieces
    with a hole between. Each end in its shortest pair; on a tie, none."""
    ends = _gap_endpoints(list(edges), lambda node: graph.degree(node) >= 2)
    if len(ends) < 2:
        return []
    points = [Point(ep.pt) for ep in ends]
    tree = STRtree(points)
    candidates = []
    for i, ep in enumerate(ends):
        for j in tree.query(points[i], predicate="dwithin", distance=tolerance):
            j = int(j)
            other = ends[j]
            if j <= i or other.ref is ep.ref or _node(other) == _node(ep):
                continue
            d = math.dist(ep.pt, other.pt)
            if GRAPH_EPSILON < d <= tolerance and _ahead(ep, other.pt, tolerance) and _ahead(other, ep.pt, tolerance):
                candidates.append((d, tuple(sorted((tuple(ep.pt), tuple(other.pt)))), i, j))
    lengths: dict = {}
    for d, _, i, j in candidates:
        for k in (i, j):
            lengths.setdefault(k, []).append(d)
    out, taken = [], set()
    for d, _, i, j in sorted(candidates, key=lambda c: (c[0], c[1])):
        if i in taken or j in taken:
            continue
        if any(len(lengths[k]) > 1 and sorted(lengths[k])[1] - d <= FLOAT_NOISE for k in (i, j)):
            continue
        taken.update((i, j))
        out.append((ends[i], ends[j], d))
    return out


def _ahead(ep: GapEndpoint, q: Point2D, reach: float) -> bool:
    """`q` lies on the extension of the curve of `ep`, within GRAPH_EPSILON."""
    ahead = _continuation(ep, reach)
    return ahead is not None and math.dist(nearest_point([ahead], q), q) <= GRAPH_EPSILON


def _ambiguous_from(candidates: list, endpoints: List[GapEndpoint]) -> set:
    """The ends whose two nearest points (distinct beyond GRAPH_EPSILON) are equally
    far within FLOAT_NOISE."""
    by_end: dict = {}
    for d, _, i, target in candidates:
        by_end.setdefault(i, []).append((d, target))
    out = set()
    for i, items in by_end.items():
        items.sort(key=lambda t: t[0])
        places = []
        for d, target in items:
            point = target[2] if target[0] == "curve" else endpoints[target[1]].pt
            if all(math.dist(point, q) > GRAPH_EPSILON for _, q in places):
                places.append((d, point))
            if len(places) == 2:
                break
        if len(places) == 2 and places[1][0] - places[0][0] <= FLOAT_NOISE:
            out.add(i)
    return out


def _onto_curve(ep: GapEndpoint, edge: Edge, meet: Point2D, node, reach: float) -> List[GapFix]:
    """End `ep` carried to where its curve, continued, meets `edge`: a line or an
    arc lengthens up to there; a spline or ellipse, which do not lengthen, take
    the tangent stretch."""
    if ep.kind in ("line", "arc"):
        return [MoveEndpoint(ref=ep.ref, role=ep.role, new_pt=meet)]
    return [AddSegment(pt_a=ep.pt, pt_b=meet, node_a=_node(ep), node_b=node)]


def ambiguous_gap_ends(endpoints: List[GapEndpoint], tolerance: float,
                       edges: Sequence[Edge] = ()) -> List[Point2D]:
    """The ends that `compute_gap_fixes` leaves open because their two nearest
    points within `tolerance` are equally near."""
    return [endpoints[k].pt for k in sorted(_ambiguous_from(_candidates(endpoints, tolerance, edges), endpoints))]


def _gap_pairs(endpoints: List[GapEndpoint], tolerance: float) -> list:
    """(d, ordered coordinates, i, j) for every pair of ends of different edges within `tolerance`."""
    pairs = []
    for i, ep_a in enumerate(endpoints):
        for j in range(i + 1, len(endpoints)):
            ep_b = endpoints[j]
            if ep_a.ref is ep_b.ref:
                continue
            d = math.dist(ep_a.pt, ep_b.pt)
            if d <= tolerance:
                # on equal distance the coordinates decide, never the file order
                pairs.append((d, tuple(sorted((tuple(ep_a.pt), tuple(ep_b.pt)))), i, j))
    return pairs


def _within_reach(fixes: List[GapFix], ep_a: GapEndpoint, ep_b: GapEndpoint,
                  reach: float) -> List[GapFix]:
    """A meeting that moves an end by more than `reach` does not close the gap: two
    nearly parallel lines meet very far away, and whether they do is decided by
    the last bit of the doubles. In its place the segment between the two."""
    origin = {(id(ep.ref), ep.role): ep.pt for ep in (ep_a, ep_b)}
    for fix in fixes:
        if isinstance(fix, MoveEndpoint) and math.dist(origin[(id(fix.ref), fix.role)],
                                                       fix.new_pt) > reach:
            return [_bridge(ep_a, ep_b)]
    return fixes


# --- Edge <-> GapFix bridge — pure geometry, no source format ---

_KIND_BY_SEGMENT = {LineSeg: "line", CircleSeg: "arc", BSplineSeg: "spline", EllipseSeg: "ellipse"}


def _endpoint_meta(segment) -> dict:
    """Data the solver uses to compute the intersection, per segment type."""
    if isinstance(segment, LineSeg):
        return {"start": segment.start, "end": segment.end}
    if is_arc(segment):
        return {"cx": segment.center[0], "cy": segment.center[1], "radius": segment.radius}
    return {}


def _meet_or_bridge(ix: Optional[Point2D], ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]:
    """If the two geometries meet at `ix`, bring both ends there; otherwise close the gap with a segment."""
    if ix is None:
        return [_bridge(ep_a, ep_b)]
    return [
        MoveEndpoint(ref=ep_a.ref, role=ep_a.role, new_pt=ix),
        MoveEndpoint(ref=ep_b.ref, role=ep_b.role, new_pt=ix),
    ]


def free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]:
    """Extract the free endpoints (degree < 2 in the graph) from the Edges.

    It works on pure geometry: the `ref` of every GapEndpoint is the Edge itself.
    Every open curve — loops (full circle, closed curve) have no free endpoints
    by definition."""
    return _gap_endpoints(edges, lambda node: graph.degree(node) < 2)


def _gap_endpoints(edges: List[Edge], keep: Callable[[Point2D], bool]) -> List[GapEndpoint]:
    """GapEndpoint for the ends of every curve whose (rounded) node satisfies
    `keep`. `pt` stays the real unrounded coordinate: the solver needs it to
    compute the intersection."""
    out: List[GapEndpoint] = []
    for edge in edges:
        if edge.start == edge.end:
            continue
        # parabola, hyperbola, formula: an end like a spline's
        kind = _KIND_BY_SEGMENT.get(type(edge.segment)) or ("spline" if isinstance(edge.segment, MathSeg) else None)
        if kind is None:
            continue
        meta = _endpoint_meta(edge.segment)
        raw_start, raw_end = segment_endpoints(edge.segment)
        if keep(edge.start):
            out.append(GapEndpoint(pt=raw_start, ref=edge, role="start", kind=kind, meta=meta))
        if keep(edge.end):
            out.append(GapEndpoint(pt=raw_end, ref=edge, role="end", kind=kind, meta=meta))
    return out


def _moved_segment(segment, role: str, new_pt: Point2D):
    """New segment with the endpoint `role` moved to `new_pt`. None if not handled."""
    if isinstance(segment, LineSeg):
        if role == "start":
            return LineSeg(start=(new_pt[0], new_pt[1]), end=segment.end)
        return LineSeg(start=segment.start, end=(new_pt[0], new_pt[1]))

    if is_arc(segment):
        angle = math.atan2(new_pt[1] - segment.center[1], new_pt[0] - segment.center[0])
        if role == "start":
            return CircleSeg(center=segment.center, radius=segment.radius,
                          start_angle=angle, end_angle=segment.end_angle, ccw=segment.ccw)
        return CircleSeg(center=segment.center, radius=segment.radius,
                      start_angle=segment.start_angle, end_angle=angle, ccw=segment.ccw)

    return None


def apply_gap_fixes(edges: List[Edge], fixes: List[GapFix]) -> List[Edge]:
    """Apply the GapFixes returning a NEW list of Edges — `edges` is not mutated.

    It rebuilds the Edges involved (MoveEndpoint) and adds new ones (AddSegment,
    always a joining LINE)."""
    replacements: dict = {}   # id(original_edge) -> updated Edge
    added: List[Edge] = []

    for fix in fixes:
        if isinstance(fix, MoveEndpoint):
            base = replacements.get(id(fix.ref), fix.ref)
            if not isinstance(base, Edge):
                continue
            # the segment keeps the real point (the polygon is built from it); only the
            # Edge's topological node is rounded
            new_seg = _moved_segment(base.segment, fix.role, fix.new_pt)
            if new_seg is None:
                continue
            node = node_point(fix.new_pt)
            replacements[id(fix.ref)] = Edge(
                role=base.role,
                start=node if fix.role == "start" else base.start,
                end=node if fix.role == "end" else base.end,
                segment=new_seg,
            )
        elif isinstance(fix, AddSegment):
            a = (float(fix.pt_a[0]), float(fix.pt_a[1]))
            b = (float(fix.pt_b[0]), float(fix.pt_b[1]))
            node_a = fix.node_a if fix.node_a is not None else node_point(a)
            node_b = fix.node_b if fix.node_b is not None else node_point(b)
            if node_a == node_b:
                continue
            added.append(Edge(
                role=ContourRole.UNKNOWN,
                start=node_a,
                end=node_b,
                segment=LineSeg(start=a, end=b),
            ))

    if not replacements and not added:
        return list(edges)

    out = [replacements.get(id(e), e) for e in edges]
    out.extend(added)
    return out
