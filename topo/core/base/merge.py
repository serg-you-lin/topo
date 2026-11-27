"""
topo/core/base/merge.py
-----------------------
Merging of geometric duplicates, format-agnostic: "two entities should not
count as two" (an identical copy, entity for entity, is removed by the adapter
beforehand). The refit, which rewrites a curve in another form, is in `refit.py`.

    merge_collinear_overlaps  — two or more LineSegs on the same infinite line
                                that cover each other at least in part (also in a
                                chain) are the same line drawn in several pieces.
                                Works on `Edge`, not on opaque keys: it computes
                                real projections to produce the single segment
                                that replaces the group.
    merge_cocircular_overlaps — the same principle, on co-circular CircleSegs.
    weld_degenerate_linesegs  — not overlap but degeneration: a LineSeg shorter
                                than 0.05 mm is noise in the graph, its two ends
                                are welded into one node.
    merge_near_copies         — a line nearly on top of another within a threshold
                                of the caller: never inside a reading, `heal()`
                                only warns (`near_copies`).

Each takes an iterable of Edges and returns the merged ones.
"""

from __future__ import annotations
import math
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Callable, Iterable, List, Tuple

from ..geometry.measure import FLOAT_NOISE, within_diameter, SAME_POINT, unit_vector
from ..primitives.line import LineSeg, distance_to_segment
from ..primitives.mathseg import Point, segment_endpoints
from ..primitives.conics import CircleSeg, is_full_circle
from ..topology.graph import connected_groups
from ..topology.noding import edge_geometry, near_pairs
from ..topology.edge import Edge
from ...model.role import ContourRole


# ---------------------------------------------------------------------------
# merge_collinear_overlaps
# ---------------------------------------------------------------------------

_SAME_OFFSET    = SAME_POINT   # mm — "same line / same circle", not "near"
_CHAIN_GAP_EPS  = FLOAT_NOISE  # guard against floating-point noise, not a user tolerance


def _same_line(a: LineSeg, b: LineSeg) -> bool:
    """`a` and `b` lie on the same infinite line: each end of each at no more than
    `_SAME_OFFSET` from the other's line. The direction is already in: along the
    stretch the two lines deviate by less than `SAME_POINT`. Judged on the true
    segments, never on a rounded key: a grid cell has an edge where two pieces of
    the same line end on different sides, and the edge moves with the frame.

    FIXED thresholds, not the caller's heal tolerance: "same line" is geometric
    precision (noise between pieces born identical), not "near enough to close a
    gap". With the heal tolerance, real distinct parallel lines 0.5 mm apart merged."""
    da, db = (unit_vector((s.end[0] - s.start[0], s.end[1] - s.start[1])) for s in (a, b))
    if da is None or db is None:
        return False
    return max(_off_line(p, a.start, da) for p in (b.start, b.end)) <= _SAME_OFFSET         and max(_off_line(p, b.start, db) for p in (a.start, a.end)) <= _SAME_OFFSET


def _off_line(p, origin, u) -> float:
    return abs((p[0] - origin[0]) * u[1] - (p[1] - origin[1]) * u[0])


def merge_collinear_overlaps(edges: Iterable[Edge], keep_junctions: bool = False) -> List[Edge]:
    """Merge groups of collinear LineSegs (same infinite line, `_same_line`) that
    touch or overlap into one Edge each — in a chain: the first member need not
    touch the last, a sequence of intermediate contacts is enough. Two members
    suffice: the union of two touching 1D intervals is always well defined.

    `keep_junctions=True` (used by `heal()`): two pieces that only TOUCH at a node
    where an edge on another line also arrives do not merge — it is a corner or a
    branch, and the graph of `heal()`, which does not node by itself, would lose it
    for good. `outlines()` nodes the network itself and keeps the default.

    Two ends, two purposes, never mixed: `Edge.start`/`Edge.end` of the merged
    edge carry the ROUNDED point (the node's identity in the graph), to reattach
    exactly to the neighbour's node; the merged `LineSeg` (`edge.segment`) ALWAYS
    carries the real full-precision point, since that is what the export reads.
    The projection `_t` for ordering/overlap stays at full precision in both cases.

    Never candidates: non-LineSeg segments, and edges with a `role` other than
    UNKNOWN (an assigned role is domain data; merging could alter intentional
    geometry). Nothing here looks at where the edge comes from in the source format.

    The replacing segment uses the two real farthest ends along the line (min and
    max projections) — never a fabricated point — and keeps the `style` of the
    group's first edge in input order.

    Returns a new list of Edges in the SAME input order for everything that does
    not merge: a cleanup pre-pass must not reorder edges it does not touch. A merged
    group takes the position of its first member; the other members are absorbed."""
    return _merge_on_carrier(edges, LineSeg, _same_line, _line_spans, _merged_line, keep_junctions)


def _line_spans(group: List[Edge]) -> List[_Span]:
    """Span along the common line: `t` is the projection on the direction of the
    first edge, the same for all, hence comparable between edges; the merged
    edge goes in the direction of the first (a canonical direction would depend
    on the frame)."""
    s0, e0 = group[0].segment.start, group[0].segment.end
    ux, uy = e0[0] - s0[0], e0[1] - s0[1]
    length0 = math.hypot(ux, uy)
    ux, uy = (ux / length0, uy / length0) if length0 else (1.0, 0.0)

    def _t(point):
        return (point[0] - s0[0]) * ux + (point[1] - s0[1]) * uy

    spans = []
    for e in group:
        seg = e.segment
        t_start, t_end = _t(seg.start), _t(seg.end)
        if t_start <= t_end:
            spans.append(_Span(t_start, e.start, t_end, e.end, e, (seg.start, seg.end)))
        else:
            spans.append(_Span(t_end, e.end, t_start, e.start, e, (seg.end, seg.start)))
    return _chain(spans)


def _merged_line(lo: _Span, hi: _Span):
    """The merge of a collinear chain: rounded nodes, full-precision segment (see
    the docstring of `merge_collinear_overlaps`)."""
    return lo.lo_node, hi.hi_node, LineSeg(start=lo.extra[0], end=hi.extra[1])


# --- Common engine: union of 1D intervals on a support (line or circle) ---

@dataclass(frozen=True)
class _Span:
    """An edge as an interval [lo, hi] on its support (position along the line, or
    angle on the circle). `lo_node`/`hi_node` are the rounded ends of the Edge —
    the node's identity in the graph, which the merge reuses to reattach to the
    neighbour; `extra` is what the caller needs to build the merged
    full-precision segment."""
    lo:      float
    lo_node: Point
    hi:      float
    hi_node: Point
    edge:    Edge
    extra:   Any


def _chain(spans: List[_Span]) -> List[List[_Span]]:
    """Sort by `lo` and chain the spans that touch or overlap: the union of touching
    1D intervals is always well defined. `_CHAIN_GAP_EPS` is floating-point noise,
    not a tolerance: a true gap stays out of the chain."""
    spans = sorted(spans, key=lambda s: s.lo)
    chains: List[List[_Span]] = [[spans[0]]]
    cur_hi = spans[0].hi
    for span in spans[1:]:
        if span.lo <= cur_hi + _CHAIN_GAP_EPS:
            chains[-1].append(span)
            cur_hi = max(cur_hi, span.hi)
        else:
            chains.append([span])
            cur_hi = span.hi
    return chains


def _merge_on_carrier(
    edges: Iterable[Edge],
    segment_type: type,
    same: Callable[[Any, Any], bool],
    chains_of: Callable[[List[Edge]], List[List[_Span]]],
    merged: Callable[[_Span, _Span], Tuple[Point, Point, Any]],
    keep_junctions: bool = False,
) -> List[Edge]:
    """Group by support the edges of `segment_type` with role UNKNOWN — two
    neighbours with `same(a, b)`, in a chain —, split every group into chains
    (`chains_of`) and replace every chain of 2+ with a single Edge:
    (start, end, segment) from `merged(lo, hi)`, role/style of the member that
    comes first in input. The rest of the list stays in input order."""
    edges = list(edges)
    original_index = {id(e): i for i, e in enumerate(edges)}

    typed = [e for e in edges if e.role == ContourRole.UNKNOWN and isinstance(e.segment, segment_type)]
    # only touching pieces can merge: the pairs to judge are the neighbouring ones,
    # the support is decided by `same` on the true segments
    pairs = [(i, j) for i, j in near_pairs([edge_geometry(e) for e in typed], _SAME_OFFSET)
             if same(typed[i].segment, typed[j].segment)]
    groups = connected_groups(len(typed), pairs)
    carrier = {id(typed[i]): k for k, members in enumerate(groups) for i in members}
    buckets = [[typed[i] for i in members] for members in groups]

    carriers_at: dict = {}  # node -> supports of the edges ending there
    for edge in edges:
        if edge.role != ContourRole.UNKNOWN:
            continue
        key = carrier.get(id(edge), ("edge", id(edge)))
        for node in (edge.start, edge.end):
            carriers_at.setdefault(node, set()).add(key)

    replacement: dict = {}  # id(representative) -> merged Edge
    drop: set = set()       # id(edge) absorbed by a merge
    junction = lambda node: len(carriers_at.get(node, ())) > 1
    for group in buckets:
        if len(group) < 2:
            continue
        chains = chains_of(group)
        if keep_junctions:
            chains = [c for whole in chains for c in _split_at_junctions(whole, junction)]
        for chain in chains:
            if len(chain) < 2:
                continue
            lo = min(chain, key=lambda s: s.lo)
            hi = max(chain, key=lambda s: s.hi)
            start, end, segment = merged(lo, hi)
            members = [s.edge for s in chain]
            representative = min(members, key=lambda e: original_index[id(e)])
            replacement[id(representative)] = replace(
                representative, start=start, end=end, segment=segment)
            drop.update(id(e) for e in members if e is not representative)

    return [replacement.get(id(e), e) for e in edges if id(e) not in drop]


def _split_at_junctions(chain: List[_Span], junction: Callable[[Point], bool]) -> List[List[_Span]]:
    """Split a chain where two consecutive spans only TOUCH (no overlap) at a node
    where an edge on another support also ends: there is a corner or a branch, a
    true node of the graph, and merging the two pieces would erase it. A true
    overlap always merges."""
    out = [[chain[0]]]
    cur_hi, cur_node = chain[0].hi, chain[0].hi_node
    for span in chain[1:]:
        touch_only = span.lo >= cur_hi - _CHAIN_GAP_EPS
        if touch_only and (junction(span.lo_node) or junction(cur_node)):
            out.append([span])
        else:
            out[-1].append(span)
        if span.hi > cur_hi:
            cur_hi, cur_node = span.hi, span.hi_node
    return out


# ---------------------------------------------------------------------------
# merge_cocircular_overlaps
# ---------------------------------------------------------------------------

_TWO_PI = 2.0 * math.pi


def _same_circle(a, b) -> bool:
    """Same circle: centres and radii within `_SAME_OFFSET` — see `_same_line`."""
    return math.dist(a.center, b.center) <= _SAME_OFFSET and abs(a.radius - b.radius) <= _SAME_OFFSET


def merge_cocircular_overlaps(edges: Iterable[Edge]) -> List[Edge]:
    """`merge_collinear_overlaps` for CircleSegs (arcs and full turns): merge
    co-circular groups (same centre+radius, `_same_circle`) that touch/overlap
    angularly into one Edge each, chaining on the circular domain [0, 2*pi)
    (unrolling past the 0/2*pi cut when needed). If the total coverage closes a
    full turn, the merged edge has Edge.start == Edge.end (degenerate loop): two
    equal circles are one circle, an arc over a circle vanishes into the circle.

    Same rules as `merge_collinear_overlaps`: excludes non-CircleSeg segments and
    `role != UNKNOWN`; uses the rounded `edge.start`/`edge.end` as the kept ends;
    preserves input order for everything that does not merge."""
    return _merge_on_carrier(edges, CircleSeg, _same_circle, _arc_chains, _merged_arc)


def _arc_chains(group: List[Edge]) -> List[List[_Span]]:
    """Angular chains of a group on the same circle. If the last chain closes the
    turn into the first, it joins them: the first is unrolled by +2*pi (only the
    angle used for ordering; the nodes stay the real ones)."""
    spans = []
    for e in group:
        seg = e.segment
        if is_full_circle(seg):
            spans.append(_Span(0.0, e.start, _TWO_PI, e.end, e, (seg.center, seg.radius)))
            continue
        if seg.ccw:
            lo, lo_node, hi_node = seg.start_angle % _TWO_PI, e.start, e.end
        else:
            lo, lo_node, hi_node = seg.end_angle % _TWO_PI, e.end, e.start
        spans.append(_Span(lo, lo_node, lo + seg._sweep(), hi_node, e, (seg.center, seg.radius)))
    chains = _chain(spans)

    if len(chains) > 1:
        first_lo = chains[0][0].lo
        last_hi = max(s.hi for s in chains[-1])
        if last_hi >= first_lo + _TWO_PI - _CHAIN_GAP_EPS:
            shifted = [replace(s, lo=s.lo + _TWO_PI, hi=s.hi + _TWO_PI) for s in chains[0]]
            chains[-1] = chains[-1] + shifted
            chains.pop(0)
    return chains


def _merged_arc(lo: _Span, hi: _Span):
    """The merge of a co-circular chain: an arc, or a circle if it closes the turn —
    the same primitive as a native CIRCLE, no trace of which fragment was first."""
    center, radius = lo.extra
    if hi.hi - lo.lo >= _TWO_PI - _CHAIN_GAP_EPS:
        circle = CircleSeg(center=center, radius=radius)
        point = segment_endpoints(circle)[0]
        return point, point, circle
    arc = CircleSeg(center=center, radius=radius, start_angle=lo.lo, end_angle=hi.hi, ccw=True)
    return lo.lo_node, hi.hi_node, arc


# ---------------------------------------------------------------------------
# merge_near_copies
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NearCopy:
    """A line nearly on top of another: `copy` lies wholly within `offset` of the
    segment `kept`, the longer (on equal length, the first in order)."""
    kept: Edge
    copy: Edge
    offset: float

    @property
    def at(self) -> Point:
        """The midpoint of the copy: where to look."""
        a, b = self.copy.segment.start, self.copy.segment.end
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _over(p, seg: LineSeg) -> bool:
    """The projection of `p` on the line of `seg` falls inside `seg` (within FLOAT_NOISE)."""
    (ax, ay), (bx, by) = seg.start[:2], seg.end[:2]
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    along = ((p[0] - ax) * dx + (p[1] - ay) * dy) / length
    return -FLOAT_NOISE <= along <= length + FLOAT_NOISE


def _line_length(e: Edge) -> float:
    return math.dist(e.segment.start[:2], e.segment.end[:2])


def near_copies(edges: Iterable[Edge], distance: float) -> List[NearCopy]:
    """The pairs of LineSegs with the same role in which the shorter lies wholly on
    top of the longer (both ends project inside it) and within `distance` of it: a
    segment is convex, so the two ends of the short one are enough. The piece
    beyond the long one's end continues the contour and is not a copy. Pairs of
    UNKNOWN role already on the same line (`_same_line`) are merged by
    `merge_collinear_overlaps` and do not appear here (it never takes an assigned
    role, so there they do); nor do those overlapping only in part. Each copy once, with the nearest line; nearest first."""
    lines = [e for e in edges if isinstance(e.segment, LineSeg) and e.start != e.end]
    nearest = {}
    for i, j in near_pairs([edge_geometry(e) for e in lines], distance):
        a, b = lines[i], lines[j]
        if a.role != b.role or (a.role == ContourRole.UNKNOWN and _same_line(a.segment, b.segment)):
            continue
        kept, copy = (b, a) if _line_length(b) > _line_length(a) + FLOAT_NOISE else (a, b)
        # on top of the long one, not beyond its end: the piece continuing the contour is not a copy
        if not all(_over(p, kept.segment) for p in (copy.segment.start, copy.segment.end)):
            continue
        offset = max(distance_to_segment(p, kept.segment.start, kept.segment.end) for p in (copy.segment.start, copy.segment.end))
        # a copy is a copy of the nearest line, not of every line within the threshold
        if offset <= distance and (id(copy) not in nearest or offset < nearest[id(copy)].offset):
            nearest[id(copy)] = NearCopy(kept, copy, offset)
    return sorted(nearest.values(), key=lambda p: p.offset)


def merge_near_copies(edges: Iterable[Edge], *, distance: float) -> List[Edge]:
    """The lines nearly on top of one another within `distance` (`near_copies`)
    become one: the longer stays; on equal length (within `FLOAT_NOISE`) the
    median, with ends midway between the near ends and the role and style of the
    first in order. topo never calls it by itself: `heal()` warns of the pairs
    within its tolerance, the caller decides whether and where to merge them. The
    rest passes in input order."""
    edges = list(edges)
    dropped, median = set(), {}
    for pair in near_copies(edges, distance):
        if id(pair.kept) in dropped or id(pair.copy) in dropped:
            continue
        dropped.add(id(pair.copy))
        if abs(_line_length(pair.kept) - _line_length(pair.copy)) <= FLOAT_NOISE:
            median.setdefault(id(pair.kept), _median_line(pair.kept, pair.copy))
    return [median.get(id(e), e) for e in edges if id(e) not in dropped]


def _median_line(a: Edge, b: Edge) -> Edge:
    """The line midway between two copies of equal length: each end of `a` with the nearest end of `b`."""
    (p, q), (r, s) = (a.segment.start[:2], a.segment.end[:2]), (b.segment.start[:2], b.segment.end[:2])
    if math.dist(p, r) + math.dist(q, s) > math.dist(p, s) + math.dist(q, r):
        r, s = s, r
    seg = LineSeg(start=((p[0] + r[0]) / 2, (p[1] + r[1]) / 2), end=((q[0] + s[0]) / 2, (q[1] + s[1]) / 2))
    return Edge.of(seg, a.role, style=a.style)


# ---------------------------------------------------------------------------
# weld_degenerate_linesegs
# ---------------------------------------------------------------------------

_DEGENERATE_LENGTH_EPS = SAME_POINT  # mm — fixed, not the caller's tolerance


def weld_degenerate_linesegs(edges: Iterable[Edge]) -> List[Edge]:
    """Weld (not delete) the `role == UNKNOWN` LineSegs of real length below
    `_DEGENERATE_LENGTH_EPS`: the Edge disappears, its two nodes become one and
    every other Edge touching them is remapped there — the chain stays connected.
    Only the nodes (Edge.start/end) move, the `segment` keeps the real point.
    Input order preserved.

    The whole group is judged: connected short stretches all weld if their nodes
    are at most `_DEGENERATE_LENGTH_EPS` from one another, otherwise none — a
    curve drawn in short stretches does not collapse to a point, and which
    stretches to weld is not decided by an order that changes with the frame. A
    stretch with a free end (no other edge touches it) stays: it is a tip, not a
    double node."""
    edges = list(edges)
    # a free tip has no two nodes to join: welding it would delete the stretch and
    # move the free end, which no gap would then find
    degree: Counter = Counter()
    for edge in edges:
        degree[edge.start] += 1
        degree[edge.end] += 1
    candidates = [edge for edge in edges
                  if degree[edge.start] >= 2 and degree[edge.end] >= 2
                  and isinstance(edge.segment, LineSeg) and edge.role == ContourRole.UNKNOWN
                  and math.dist(edge.segment.start, edge.segment.end) < _DEGENERATE_LENGTH_EPS]
    if not candidates:
        return edges

    nodes = sorted({p for e in candidates for p in (e.start, e.end)})
    index = {p: k for k, p in enumerate(nodes)}
    groups = connected_groups(len(nodes), [(index[e.start], index[e.end]) for e in candidates])
    target: dict = {}
    for members in groups:
        points = [nodes[k] for k in members]
        if len(points) > 1 and within_diameter(points, _DEGENERATE_LENGTH_EPS):
            # the representative is the group's minimum node, a real end
            target.update((p, points[0]) for p in points)
    degenerate_ids = {id(e) for e in candidates if e.start in target}
    if not degenerate_ids:
        return edges

    result: List[Edge] = []
    for edge in edges:
        if id(edge) in degenerate_ids:
            continue
        new_start, new_end = target.get(edge.start, edge.start), target.get(edge.end, edge.end)
        if new_start != edge.start or new_end != edge.end:
            edge = replace(edge, start=new_start, end=new_end)
        result.append(edge)
    return result
