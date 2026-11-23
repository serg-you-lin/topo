"""
core/topology/noding.py
-----------------------
Planar network: every edge split where it crosses or touches another edge, so
that two edges meet only at nodes, and a node is the same point for all the
edges arriving there. It is the premise for walking the outer face
(outer_face.py): on a non-planar network a crossing in the middle of two
edges is not a node and the walk passes over it.

Every contact is decided once, per pair of edges, on the true curves: a
crossing, an end within `GRAPH_EPSILON` of the other curve (a T, or two near
ends), two curves passing within `GRAPH_EPSILON` without crossing (the missed
tangency). The meetings of a same pair within `tolerance` along one of the
two edges are one contact: a nearly tangent line to an arc crosses it at two
roots a few hundredths apart. A contact puts a stop on each of the two edges,
and the stops of a contact are a single node (union-find), like two stops of
the same edge within `GRAPH_EPSILON`; never the two ends of the same edge.
The node of a group is an entry end, if it contains one (the smallest, like
`cluster_points`), otherwise the mean of the contact points: all the edges of
the group receive the same tuple, and the graph does not rejudge anything.
`tolerance` does not widen node identity: across the whole network it
percolates.

Lines, arcs and circles are measured in closed form; the other curves on
their `_FINE` discretization, and are cut exactly (`sub_segment`); a spline
that cannot be cut (periodic) stays whole.

Pure: Edges and primitives only, no format.
"""

from __future__ import annotations

from ...precision import FLOAT_NOISE as _FLOAT_NOISE
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Point

from .edge import Edge
from ..geometry.intersections import intersections
from ..primitives.trim import sub_segment
from ..primitives.line import LineSeg
from ..primitives.mathseg import DEFAULT_TOLERANCE, segment_endpoints, segment_is_closed
from ..primitives.conics import angle_from_start, point_on_circle
from ..primitives.conics import CircleSeg, is_full_circle

from ..geometry.measure import FLOAT_NOISE, SAME_POINT, reach, within_diameter
from .edge import node_point
from .graph import cluster_points, connected_groups

GRAPH_EPSILON = SAME_POINT   # mm — two nodes this close are one for the graph (heal, polygonize fallback)

_EPS = _FLOAT_NOISE
_MIN_PIECE = SAME_POINT   # mm — below this, the piece is not created
_EXACT = (LineSeg, CircleSeg)


def _is_loop(seg) -> bool:
    """The curve returns on itself: a circle, or another curve with ends within
    DEFAULT_TOLERANCE. A line or an arc never: a short stretch is a stretch, with
    two ends to node, not a ring."""
    return is_full_circle(seg) or (not isinstance(seg, _EXACT) and segment_is_closed(seg))
# mm — the other curves are measured on this discretization (the value of the
# old node grid, kept when the grid went away)
_FINE = SAME_POINT


@dataclass
class NodedEdges:
    """The planar network: the pieces, for each the Edge it comes from, and the
    nodes where two edges cross with neither ending there."""
    pieces:    List[Edge]            = field(default_factory=list)
    parent:    Dict[int, Edge]       = field(default_factory=dict)   # id(piece) -> original Edge
    crossings: List[tuple]           = field(default_factory=list)
    planar:    bool                  = True    # cut also at the crossings (`cut_crossings`)
    trimmed:   set                   = field(default_factory=set)    # id(Edge) shortened up to a crossing

    def parent_of(self, piece: Edge) -> Edge:
        return self.parent[id(piece)]

    def whole(self, loop: list) -> list:
        """`loop` [(piece, reversed)] with the original Edge in place of its pieces,
        where the loop walks them all in a row: a side cut by a contact comes back as
        the file's segment, coefficients included; not one shortened to a crossing,
        which would bring back the overhanging end."""
        if not loop:
            return loop
        counts: Dict[int, int] = {}
        for piece in self.pieces:
            key = id(self.parent_of(piece))
            counts[key] = counts.get(key, 0) + 1
        parents = [self.parent_of(e) for e, _ in loop]
        k = next((i for i in range(len(loop)) if parents[i] is not parents[i - 1]), 0)
        loop, parents = loop[k:] + loop[:k], parents[k:] + parents[:k]
        out, i = [], 0
        while i < len(loop):
            j = i
            while j + 1 < len(loop) and parents[j + 1] is parents[i] and loop[j + 1][1] == loop[i][1]:
                j += 1
            if j - i + 1 == counts[id(parents[i])] and (j > i or loop[i][0] is not parents[i])                     and id(parents[i]) not in self.trimmed:
                out.append((parents[i], loop[i][1]))
            else:
                out.extend(loop[i:j + 1])
            i = j + 1
        return out


# --- Public API ---

def renode(edges: List[Edge]) -> List[Edge]:
    """Nodes of every Edge recomputed from the segment's real point. Two real ends
    within FLOAT_NOISE are the same point: a single node, not two copies 1 ulp
    apart. A closed curve has a single node, its start, as in `Edge.of`, however
    the Edge was written."""
    ends = [p for e in edges if not _is_loop(e.segment) for p in segment_endpoints(e.segment)]
    same = cluster_points(ends, FLOAT_NOISE)
    return [_loop_node(e) if _is_loop(e.segment) else _with_nodes(e, e.segment, same)
            for e in edges]


def decide_nodes(edges: List[Edge], epsilon: float = GRAPH_EPSILON) -> Tuple[List[Edge], int]:
    """The nodes of every reading, decided once: from the real points of the
    segments (`renode`), then the ends within `epsilon` of each other are a single
    node, the smallest of the group (a real end). A group wider than `epsilon` is
    a curve written as dense points: its nodes stay distinct, no order chooses
    which to merge. From here on the equality between nodes no longer depends on
    a grid cell.

    An open edge whose two ends become the same node is shorter than `epsilon`:
    it is welded, that is removed, and the neighbours find themselves on the
    common node. Returns (edges, how many welded this way)."""
    edges = renode(edges)
    ends = sorted({p for e in edges if not _is_loop(e.segment) for p in (e.start, e.end)})
    index = {p: k for k, p in enumerate(ends)}
    near = cluster_points(ends, epsilon)
    groups = connected_groups(len(ends), [(index[p], index[q]) for p, q in near.items() if p != q])
    target = {}
    for members in groups:
        points = [ends[k] for k in members]
        if len(points) > 1 and within_diameter(points, epsilon):
            target.update((p, points[0]) for p in points)
    if not target:
        return edges, 0
    out, welded = [], 0
    for edge in edges:
        start, end = target.get(edge.start, edge.start), target.get(edge.end, edge.end)
        if start == end and edge.start != edge.end and not _is_loop(edge.segment):
            welded += 1
            continue
        out.append(edge if (start, end) == (edge.start, edge.end) else replace(edge, start=start, end=end))
    return out, welded


def split_at_crossings(edges: List[Edge], tolerance: float,
                       cut_crossings: bool = True) -> NodedEdges:
    """Split every edge at its contacts with the others (crossings, T, near ends,
    missed tangencies within GRAPH_EPSILON; the meetings of a pair within
    `tolerance` are one), decided once per pair on the true curves; the touching
    pieces have the same node tuple. A closed edge (circle) with fewer than two
    contacts stays whole.

    `cut_crossings`: a crossing (two curves crossing and continuing) cuts too. The
    contact is decided by this function anyway; what it means is told by the
    reading: for outlines() yes, for faces() no — a crossing between contour sides
    is a broken drawing, an axis crossing a hole is not a side of the hole. The
    crossings are in `crossings` in both cases."""
    curves = [_Curve(e.segment) for e in edges]
    net = _Contacts(edges, curves, tolerance)
    for i, j in near_pairs([edge_geometry(e) for e in edges], tolerance):
        net.meet(i, j)
    net.merge_along_edges()
    nodes = net.nodes()

    noded = NodedEdges(planar=cut_crossings)
    skip = frozenset() if cut_crossings else frozenset(net.crossing_roots())
    for i, edge in enumerate(edges):
        if i in net.ends and net._span_to_crossings(i) != (0.0, curves[i].length):
            noded.trimmed.add(id(edge))
        for piece in net.pieces(i, nodes, skip):
            noded.pieces.append(piece)
            noded.parent[id(piece)] = edge
    noded.crossings = sorted(net.crossings(nodes))
    return noded


def interior_crossings(edges: List[Edge], tolerance: float) -> List[tuple]:
    """The points where two edges cross with neither ending there: a cut interior to
    both. A T contact (the end of one on the other's curve) does not count.
    Between contour sides it is a drawing with overlapping sides, which the heal
    graph does not see."""
    return split_at_crossings(edges, tolerance).crossings


def edge_geometry(edge: Edge):
    """The edge as a shapely geometry: a discretized LineString, a Point if degenerate."""
    pts = edge.segment.discretize(tolerance=DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


# --- A curve measured in arc length ---

class _Curve:
    """`seg` with the parameter s = arc length from the start, in [0, length]
    (cyclic on closed ones). Exact on lines, arcs and circles; on splines and
    ellipses along the fine discretization.
    """

    def __init__(self, seg):
        self.seg = seg
        self._fine = None
        self._length = None
        self.closed = _is_loop(seg)

    @property
    def length(self) -> float:
        """On the other curves the length of the fine discretization: computed only if
        needed (an edge with no contacts does not ask for it)."""
        if self._length is None:
            seg = self.seg
            if isinstance(seg, LineSeg):
                self._length = math.dist(seg.start, seg.end)
            elif isinstance(seg, CircleSeg):
                self._length = seg.radius * seg._sweep()
            else:
                self._length = self.fine.length
        return self._length

    @property
    def exact(self) -> bool:
        return isinstance(self.seg, _EXACT)

    @property
    def fine(self) -> LineString:
        """The curve discretized at _FINE, once."""
        if self._fine is None:
            pts = [tuple(q[:2]) for q in self.seg.discretize(tolerance=_FINE)]
            self._fine = LineString(pts) if len(pts) > 1 else LineString([pts[0], pts[0]])
        return self._fine

    def locate(self, pt) -> Tuple[float, float]:
        """(s of the curve point nearest `pt`, distance)."""
        seg = self.seg
        if isinstance(seg, LineSeg):
            if self.length < _EPS:
                return 0.0, math.dist(seg.start, pt)
            dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
            t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / (self.length ** 2)
            t = min(1.0, max(0.0, t))
            return t * self.length, math.dist(pt, (seg.start[0] + t * dx, seg.start[1] + t * dy))
        if isinstance(seg, CircleSeg):
            a = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
            if seg.full or a <= seg._sweep():
                return seg.radius * a, abs(math.dist(pt, seg.center) - seg.radius)
            start, end = segment_endpoints(seg)
            if math.dist(pt, start) <= math.dist(pt, end):
                return 0.0, math.dist(pt, start)
            return self.length, math.dist(pt, end)
        at = Point(pt)
        return self.fine.project(at), self.fine.distance(at)

    def at(self, s: float):
        seg = self.seg
        if isinstance(seg, LineSeg):
            t = 0.0 if self.length < _EPS else s / self.length
            return (seg.start[0] + t * (seg.end[0] - seg.start[0]), seg.start[1] + t * (seg.end[1] - seg.start[1]))
        if isinstance(seg, CircleSeg):
            return point_on_circle(seg.center, seg.radius,
                                   seg.start_angle + (s if seg.ccw else -s) / seg.radius)
        return self.fine.interpolate(s % self.length if self.closed else s).coords[0]

    def piece(self, s0: float, s1: float):
        """The stretch from s0 to s1 (s0 < s1; on a closed one s1 may exceed length),
        same primitive; None if it cannot be cut exactly."""
        seg = self.seg
        if isinstance(seg, LineSeg):
            return LineSeg(start=seg.start if s0 == 0.0 else self.at(s0),
                           end=seg.end if s1 == self.length else self.at(s1))
        if isinstance(seg, CircleSeg):
            sign = 1.0 if seg.ccw else -1.0
            return CircleSeg(center=seg.center, radius=seg.radius, start_angle=seg.start_angle + sign * s0 / seg.radius,
                             end_angle=seg.start_angle + sign * s1 / seg.radius, ccw=seg.ccw)
        ends = segment_endpoints(seg)
        a = ends[0] if s0 == 0.0 else self.at(s0)
        b = ends[1] if s1 == self.length else self.at(s1)
        return sub_segment(seg, a, b, self.at((s0 + s1) / 2))


# --- Contacts ---

def near_pairs(geoms: list, tolerance: float) -> List[Tuple[int, int]]:
    """The pairs (i < j), in order, of the geometries (`edge_geometry`) within
    `tolerance` + 2·DEFAULT_TOLERANCE: the discretizations are wrong by up to
    DEFAULT_TOLERANCE per curve, and the band covers them. It is only the filter:
    the contact or the true distance is decided by the caller on the curves."""
    geoms = np.array(geoms, dtype=object)
    if len(geoms) < 2:
        return []
    a, b = STRtree(geoms).query(geoms, predicate="dwithin", distance=tolerance + 2 * DEFAULT_TOLERANCE)
    keep = a < b
    return sorted(zip(a[keep].tolist(), b[keep].tolist()))


class _Contacts:
    """The contact stops on every edge and the nodes they form (union-find). A stop is
    (edge, s, point, kind): "end" an end of the edge, "x" a crossing, "t" an end of
    another on the edge, "g" a missed tangency."""

    def __init__(self, edges: List[Edge], curves: List[_Curve], tolerance: float):
        self.edges, self.curves, self.tol = edges, curves, tolerance
        # a contact (crossing, T, two ends, missed tangency) is within `node`, and two
        # stops within `node` are a single node: the graph's threshold. `tolerance`
        # merges only the meetings of a same pair: across the whole network it percolates
        self.node = min(tolerance, GRAPH_EPSILON)
        self.stops: List[tuple] = []
        self.up: List[int] = []
        self.on_edge: Dict[int, List[int]] = defaultdict(list)
        self.ends: Dict[int, Tuple[int, int]] = {}
        self.anchor: Dict[int, int] = {}   # interior stop -> first stop of its group on the edge
        self.trim_at: Dict[int, List[float]] = defaultdict(list)   # stop at an end -> s of the crossings of its contact
        self.absorbed: set = set()         # interior stops merged with an end of the edge
        self.sides: Dict[int, Dict[int, int]] = {}   # root -> {edge: ends in the node, 1 start 2 end}
        self.group_pts: Dict[int, list] = {}          # root -> points of the group (diameter)
        by_node: Dict[tuple, int] = {}
        for i, edge in enumerate(edges):
            if self._is_open(i):
                # the s of the end is read when needed (curve.length)
                pair = (self._stop(i, 0.0, edge.start, "end"), self._stop(i, None, edge.end, "end"))
                self.ends[i] = pair
                self.sides[pair[0]], self.sides[pair[1]] = {i: 1}, {i: 2}
                for k, node in zip(pair, (edge.start, edge.end)):
                    self._union(k, by_node.setdefault(node, k))
        # an end coinciding with another curve's end is a vertex of the drawing: it is never shortened
        count = Counter(node for i in self.ends for node in (edges[i].start, edges[i].end))
        self.shared = {k for i, pair in self.ends.items()
                       for k, node in zip(pair, (edges[i].start, edges[i].end)) if count[node] > 1}

    def _is_open(self, i: int) -> bool:
        edge, curve = self.edges[i], self.curves[i]
        return not curve.closed and edge.start != edge.end and (not curve.exact or curve.length > _EPS)

    def _stop(self, i: int, s: float, pt, kind: str) -> int:
        k = len(self.stops)
        self.stops.append((i, s, pt, kind))
        self.up.append(k)
        self.group_pts[k] = [pt]
        if kind != "end":
            self.on_edge[i].append(k)
        return k

    def _find(self, k: int) -> int:
        root = k
        while self.up[root] != root:
            root = self.up[root]
        while self.up[k] != root:
            self.up[k], k = root, self.up[k]
        return root

    def _union(self, a: int, b: int) -> bool:
        """A single node for `a` and `b`, if it does not put the two ends of the same
        edge in the same node (a short side does not vanish) and if the group stays
        within `node` in diameter: never chained."""
        ra, rb = self._find(a), self._find(b)
        if ra == rb:
            return True
        if not self._joinable([ra, rb]):
            return False
        if not within_diameter(self.group_pts[ra] + self.group_pts[rb], reach(self.node)):
            return False
        keep, gone = min(ra, rb), max(ra, rb)
        self.up[gone] = keep
        self.group_pts[keep] = self.group_pts[keep] + self.group_pts.pop(gone)
        merged = self.sides.pop(gone, {})
        mine = self.sides.setdefault(keep, {})
        for i, mask in merged.items():
            mine[i] = mine.get(i, 0) | mask
        return True

    def _joinable(self, roots) -> bool:
        seen: Dict[int, int] = {}
        for root in set(roots):
            for i, mask in self.sides.get(root, {}).items():
                if seen.get(i, 0) | mask == 3:
                    return False
                seen[i] = seen.get(i, 0) | mask
        return True

    def meet(self, i: int, j: int) -> None:
        """Decide the contacts between edges `i` and `j`, once."""
        ci, cj = self.curves[i], self.curves[j]
        contacts = []   # [(side on i, side on j, kind)]
        for p in _meetings(ci, cj):
            contacts.append(((i, ci.locate(p)[0], p, None),
                             (j, cj.locate(p)[0], p, None), "x"))
        # an end of one within `node` of the other's curve: the T, or two ends (if the
        # nearest point is an end of the other too)
        for k, other in ((i, j), (j, i)):
            if other not in self.ends:
                continue
            ck = self.curves[k]
            for end, pt in zip(self.ends[other], segment_endpoints(self.edges[other].segment)):
                s, d = ck.locate(pt)
                if d > self.node:
                    continue
                at_end = k in self.ends and (s <= _EPS or s >= ck.length - _EPS)
                mine = (k, s, pt, self.ends[k][0 if s <= _EPS else 1] if at_end else None)
                theirs = (other, 0.0 if end == self.ends[other][0] else self.curves[other].length, pt, end)
                contacts.append((mine, theirs, "t") if k == i else (theirs, mine, "t"))
        if not contacts:
            # a slightly missed tangency is a contact like a slightly crossed one: at the
            # midpoint between the two curves
            near = _grazing(ci, cj)
            if near is not None and math.dist(*near) <= self.node:
                mid = ((near[0][0] + near[1][0]) / 2, (near[0][1] + near[1][1]) / 2)
                contacts.append(((i, ci.locate(mid)[0], mid, None),
                                 (j, cj.locate(mid)[0], mid, None), "g"))
        for group in self._same_contact(contacts):
            # a crossing is the point lying on both curves: the contact is cut there, not at
            # the mean with the feet of the near ends; an end in the contact stays the node
            # and its curve is shortened along itself up to the crossing
            kind = "x" if any(c[2] == "x" for c in group) else group[0][2]
            # only a crossing lying on both curves: `intersections` also gives a point just beyond an end
            crossing = [c for c in group if c[2] == "x" and all(
                self.curves[c[m][0]].locate(c[m][2])[1] <= _MIN_PIECE for m in (0, 1))]
            stops, trims = [], []
            for n in (0, 1):
                end = next((c[n][3] for c in group if c[n][3] is not None), None)
                if end is None:
                    stops.append(self._place([c[n] for c in crossing or group], kind))
                    continue
                stops.append(end)
                # only an overhanging end is shortened: one already on the other curve is itself
                # the meeting point (a tangent fillet has an unstable crossing, the end does not)
                edge = group[0][n][0]
                other = self.curves[group[0][1 - n][0]]
                end_pt = segment_endpoints(self.edges[edge].segment)[0 if end == self.ends[edge][0] else 1]
                if crossing and end not in self.shared and other.locate(end_pt)[1] > FLOAT_NOISE:
                    trims.append((end, sum(c[n][1] for c in crossing) / len(crossing)))
            if not self._union(*stops):
                # a contact that would close a side on itself: its new stops cut nothing
                self._drop(stops)
                continue
            for end, s in trims:
                self.trim_at[end].append(s)

    def _same_contact(self, contacts: list) -> List[list]:
        """The contacts of a pair within tolerance along one of the two edges are a
        single one (the two roots of a line nearly tangent to an arc), never however
        two ends of the same edge: a short side does not vanish. The nearest merge first."""
        n = len(contacts)
        if n < 2:
            return [contacts] if contacts else []
        up = list(range(n))
        ends = [{c[0][3], c[1][3]} - {None} for c in contacts]

        def find(a):
            while up[a] != a:
                up[a] = up[up[a]]
                a = up[a]
            return a

        candidates = []
        for side in (0, 1):
            curve = self.curves[contacts[0][side][0]]
            order = sorted(range(n), key=lambda c: contacts[c][side][1])
            for a, b in zip(order, order[1:]):
                candidates.append((contacts[b][side][1] - contacts[a][side][1], a, b))
            if curve.closed:
                a, b = order[-1], order[0]
                candidates.append((contacts[b][side][1] + curve.length - contacts[a][side][1], a, b))
        for gap, a, b in sorted(candidates):
            if gap > self.tol:
                break
            ra, rb = find(a), find(b)
            if ra == rb:
                continue
            # two contacts with different ends are two points of the file: an end does not
            # merge with another end because the pair touches twice
            if ends[ra] and ends[rb] and not ends[ra] & ends[rb]:
                continue
            both = ends[ra] | ends[rb]
            if not self._joinable(self._find(e) for e in both):
                continue
            up[rb], ends[ra] = ra, both
        groups: Dict[int, list] = {}
        for c in range(n):
            groups.setdefault(find(c), []).append(contacts[c])
        return list(groups.values())

    def _drop(self, stops) -> None:
        for k in stops:
            if self.stops[k][3] != "end" and self.up[k] == k:
                self.on_edge[self.stops[k][0]].remove(k)

    def _place(self, sides: list, kind: str) -> int:
        """The stop of a contact on an edge: its end, if the contact touches it,
        otherwise a new one at the centre of its sides."""
        for _, _, _, end in sides:
            if end is not None:
                return end
        k, curve = sides[0][0], self.curves[sides[0][0]]
        s = [side[1] for side in sides]
        if curve.closed and max(s) - min(s) > curve.length / 2:   # straddling the start
            s = [x if x >= curve.length / 2 else x + curve.length for x in s]
        mean = sum(s) / len(s)
        pt = (sum(side[2][0] for side in sides) / len(sides), sum(side[2][1] for side in sides) / len(sides))
        return self._stop(k, mean % curve.length if curve.closed else mean, pt, kind)

    def merge_along_edges(self) -> None:
        """Two stops of the same edge within `node` along the edge are a single node, and
        one within `node` of an end of the edge is that end: the same threshold with
        which the graph merges two near ends. The group is measured from its first stop."""
        r = self.node
        for i, ks in self.on_edge.items():
            curve = self.curves[i]
            ks.sort(key=lambda k: self.stops[k][1])
            first = None
            for k in ks:
                s = self.stops[k][1]
                side = 0 if s <= curve.length - s else 1
                # within `node` in the plane too: the contact point may be beside the curve, and
                # then it is farther from the end than along the edge
                if i in self.ends and min(s, curve.length - s) <= r and \
                        math.dist(self.stops[k][2], segment_endpoints(self.edges[i].segment)[side]) <= r and \
                        self._union(k, self.ends[i][side]):
                    self.absorbed.add(k)
                    continue
                if first is None or s - self.stops[first][1] > r or not self._union(k, first):
                    first = k
                self.anchor[k] = first
            live = [k for k in ks if k not in self.absorbed]
            if curve.closed and len(live) > 1:
                head, tail = live[0], live[-1]
                if self.anchor[head] != self.anchor[tail] and (
                        self.stops[head][1] + curve.length - self.stops[tail][1] <= r):
                    self._union(head, tail)
                    tail_group = self.anchor[tail]
                    for k in live:
                        if self.anchor[k] == tail_group:
                            self.anchor[k] = self.anchor[head]

    def nodes(self) -> Dict[int, tuple]:
        """{root: node tuple}: the entry end of the group, if it has a single one; the
        mean of its distinct ends, if it has more (between two ends neither is better
        than the other); otherwise the mean of the contact points."""
        ends: Dict[int, list] = defaultdict(list)
        points: Dict[int, list] = defaultdict(list)
        for k, (i, _, pt, kind) in enumerate(self.stops):
            root = self._find(k)
            (ends if kind == "end" else points)[root].append(pt)
        out = {}
        for root in set(ends) | set(points):
            distinct = set(ends[root])
            if len(distinct) == 1:
                out[root] = distinct.pop()
            else:
                pts = list(distinct) or points[root]
                out[root] = (math.fsum(p[0] for p in pts) / len(pts),
                             math.fsum(p[1] for p in pts) / len(pts))
        return out

    def _span_to_crossings(self, i: int) -> Tuple[float, float]:
        """(s0, s1) of the edge `i` shortened along itself: an end overhanging a crossing
        of its contact ends at the crossing nearest to it, the point lying on both
        curves; the remainder beyond is not a side. With no crossings, (0, length)."""
        curve = self.curves[i]
        near = {0: list(self.trim_at.get(self.ends[i][0], ())), 1: list(self.trim_at.get(self.ends[i][1], ()))}
        s0 = min(near[0]) if near[0] else 0.0
        s1 = max(near[1]) if near[1] else curve.length
        return (s0, s1) if s1 - s0 > _MIN_PIECE else (0.0, curve.length)

    def crossing_roots(self) -> set:
        """The nodes with no ends and at least one crossing between different edges: two
        curves that cross and both continue."""
        groups: Dict[int, list] = defaultdict(list)
        for k, stop in enumerate(self.stops):
            groups[self._find(k)].append(stop)
        return {root for root, stops in groups.items()
                if all(kind != "end" for _, _, _, kind in stops)
                and any(kind == "x" for _, _, _, kind in stops)
                and len({i for i, _, _, _ in stops}) > 1}

    def crossings(self, nodes: Dict[int, tuple]) -> List[tuple]:
        return [nodes[root] for root in self.crossing_roots()]

    def pieces(self, i: int, nodes: Dict[int, tuple], skip: frozenset = frozenset()) -> List[Edge]:
        """The edge `i` cut at its groups of stops, with the shared nodes; not at the nodes of `skip`."""
        edge, curve = self.edges[i], self.curves[i]
        groups: Dict[int, list] = {}
        for k in self.on_edge.get(i, []):
            if k not in self.absorbed and self._find(k) not in skip:
                groups.setdefault(self.anchor[k], []).append(k)
        cuts = []
        for ks in groups.values():
            # the cut of a group with a crossing lies on the crossing
            s = [self.stops[k][1] for k in ks if self.stops[k][3] == "x"] or [self.stops[k][1] for k in ks]
            if curve.closed and max(s) - min(s) > curve.length / 2:   # group straddling the start
                s = [x if x >= curve.length / 2 else x + curve.length for x in s]
            cuts.append(((sum(s) / len(s)) % curve.length if curve.closed else sum(s) / len(s),
                         nodes[self._find(ks[0])]))
        cuts.sort()
        if i not in self.ends and not curve.closed:   # a single end: no stretch to cut
            return [edge]
        if i in self.ends:
            start, end = (nodes[self._find(k)] for k in self.ends[i])
            s0, s1 = self._span_to_crossings(i)
            bounds = [(s0, start)]
            for s, node in cuts:
                if s - bounds[-1][0] > _MIN_PIECE and s1 - s > _MIN_PIECE:
                    bounds.append((s, node))
            bounds.append((s1, end))
            if (s0, s1) != (0.0, curve.length):
                # shortened up to the crossing: the piece is a new stretch
                segs = [curve.piece(a, b) for (a, _), (b, _) in zip(bounds, bounds[1:])]
                if all(seg is not None for seg in segs):
                    return [replace(edge, segment=seg, start=n0, end=n1)
                            for seg, (_, n0), (_, n1) in zip(segs, bounds, bounds[1:])]
                bounds[0], bounds[-1] = (0.0, start), (curve.length, end)
        else:
            if len(cuts) < 2:
                return [edge]
            bounds = []
            for s, node in cuts:
                if not bounds or s - bounds[-1][0] > _MIN_PIECE:
                    bounds.append((s, node))
            if len(bounds) > 1 and bounds[0][0] + curve.length - bounds[-1][0] <= _MIN_PIECE:
                bounds.pop()
            if len(bounds) < 2:
                return [edge]
            if not curve.exact:
                # a closed spline or ellipse is cut at the start too: a stretch does not cross its seam
                seam = (0.0, edge.start)
                if bounds[0][0] > _MIN_PIECE and curve.length - bounds[-1][0] > _MIN_PIECE:
                    bounds.insert(0, seam)
                bounds.append((curve.length, bounds[0][1]) if bounds[0][0] == 0.0
                              else (bounds[0][0] + curve.length, bounds[0][1]))
            else:
                bounds.append((bounds[0][0] + curve.length, bounds[0][1]))
        if len(bounds) == 2 and i in self.ends:
            if (bounds[0][1], bounds[1][1]) == (edge.start, edge.end):
                return [edge]
            return [replace(edge, start=bounds[0][1], end=bounds[1][1])]
        segs = [curve.piece(s0, s1) for (s0, _), (s1, _) in zip(bounds, bounds[1:])]
        if any(seg is None for seg in segs):
            return [edge] if i not in self.ends else [replace(edge, start=bounds[0][1], end=bounds[-1][1])]
        return [replace(edge, segment=seg, start=n0, end=n1)
                for seg, (_, n0), (_, n1) in zip(segs, bounds, bounds[1:])]


def _meetings(a: _Curve, b: _Curve) -> list:
    """Where `a` and `b` cross or touch: in closed form between lines, arcs and
    circles, on the fine discretizations if there is a spline or an ellipse. A
    shared stretch is not a point: it does not count."""
    if a.exact and b.exact:
        return intersections(a.seg, b.seg)
    hit = a.fine.intersection(b.fine)
    return [p.coords[0] for p in getattr(hit, "geoms", [hit]) if p.geom_type == "Point"]


def _grazing(a: _Curve, b: _Curve) -> Optional[tuple]:
    """(point of `a`, point of `b`) nearest between two curves that do not meet,
    taken midway between both; None if the nearest is an end (judged by the T) or
    between two lines (always an end)."""
    sa, sb = a.seg, b.seg
    if isinstance(sa, LineSeg) and isinstance(sb, LineSeg):
        return None
    if a.exact and b.exact:
        if isinstance(sb, LineSeg):
            found = _line_circle_near(sb, sa)
            return None if found is None else (found[1], found[0])
        if isinstance(sa, LineSeg):
            return _line_circle_near(sa, sb)
        return _circle_circle_near(a, b)
    p, q = shapely.shortest_line(a.fine, b.fine).coords
    return (p, q) if _inside(a, p) and _inside(b, q) else None


def _inside(curve: _Curve, pt) -> bool:
    if curve.closed:
        return True
    s, _ = curve.locate(pt)
    return _MIN_PIECE < s < curve.length - _MIN_PIECE


def _line_circle_near(line: LineSeg, arc) -> Optional[tuple]:
    """(foot on the line, arc point) of the perpendicular from the centre."""
    dx, dy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    l2 = dx * dx + dy * dy
    if l2 < _EPS * _EPS:
        return None
    c = arc.center
    t = ((c[0] - line.start[0]) * dx + (c[1] - line.start[1]) * dy) / l2
    if not 0.0 < t < 1.0:
        return None
    foot = (line.start[0] + t * dx, line.start[1] + t * dy)
    near = _radial(c, arc.radius, foot)
    if near is None or not _inside_arc(arc, near):
        return None
    return foot, near


def _circle_circle_near(a: _Curve, b: _Curve) -> Optional[tuple]:
    """The two nearest points between two arcs, on the line of the centres."""
    ca, cb = a.seg, b.seg
    d = math.dist(ca.center, cb.center)
    if d < _EPS:
        return None
    best = None
    for sign in (1.0, -1.0):   # the two points of b on the line of the centres
        q = (cb.center[0] + sign * (ca.center[0] - cb.center[0]) * cb.radius / d,
             cb.center[1] + sign * (ca.center[1] - cb.center[1]) * cb.radius / d)
        p = _radial(ca.center, ca.radius, q)
        if p is None or not (_inside_arc(ca, p) and _inside_arc(cb, q)):
            continue
        if best is None or math.dist(p, q) < math.dist(*best):
            best = (p, q)
    return best


def _radial(center, radius, pt):
    """The circle point nearest `pt`; None if `pt` is the centre."""
    d = math.dist(center, pt)
    if d < _EPS:
        return None
    return (center[0] + (pt[0] - center[0]) * radius / d, center[1] + (pt[1] - center[1]) * radius / d)


def _inside_arc(seg, pt) -> bool:
    """`pt` (on the circle) falls inside the arc, away from the ends."""
    if is_full_circle(seg):
        return True
    s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    return _MIN_PIECE / seg.radius < s < seg._sweep() - _MIN_PIECE / seg.radius


# --- Nodes ---

def _with_nodes(edge, seg, same=None):
    s, e = segment_endpoints(seg)
    if same is not None:
        s, e = same.get(s, s), same.get(e, e)
    return replace(edge, start=node_point(s), end=node_point(e), segment=seg)


def _loop_node(edge):
    """The Edge of a closed curve with the single node of its start."""
    node = node_point(segment_endpoints(edge.segment)[0])
    return edge if edge.start == edge.end == node else replace(edge, start=node, end=node)
