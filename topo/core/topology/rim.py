"""
topo/core/topology/rim.py
--------------------------
The segments of a face read from its border: when a face's polygon is known
(the union of faces, a lobe of a loop touching itself) but the network's
edges do not close in a loop that follows it, the polygon's ring is walked and
each of its stretches becomes the edge it lies on, cut between the two ends.
The order comes from the ring, the shape from the edges: arcs stay arcs,
splines stay splines.

Pure: Edges, primitives and shapely only.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List

from shapely import STRtree
from shapely.geometry import Point as ShapelyPoint, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import substring

from .edge import Edge
from .noding import edge_geometry
from ..geometry.measure import FLOAT_NOISE, reach
from ..geometry.rings import ring_bridges
from ..primitives.line import LineSeg
from ..primitives.mathseg import segment_endpoints, segment_is_closed
from ..primitives.trim import sub_segment


def face_segments(edges: List[Edge], polygon: Polygon, band: float):
    """(segments, styles, used) along the outer border of `polygon`, counter-clockwise.
    A border side lies on an edge if it is less than `band` from it; the border is
    divided among the edges with the fewest changes (`_rim_runs`), and each stretch
    is its edge cut between the two ends (`sub_segment`) — whole if it covers it
    all. An edge running on the border only in part (a crossing that shapely nodes
    and the planar network does not) thus gives just its part. `used`: {edge
    index: [(a, b)]}, the ends of the stretches the border took from each
    (`off_rim`)."""
    pts = list(orient(polygon, 1.0).exterior.coords)[:-1]
    n = len(pts)
    geoms = [edge_geometry(e) for e in edges]
    runs = _rim_runs(pts, geoms, _side_cover(pts, geoms, band))
    segments, styles, used = [], [], {}
    for (j, _), first, last in runs:
        edge = edges[j]
        a, b = pts[first % n], pts[last % n]
        used.setdefault(j, []).append((a, b))
        via = pts[(first + 1) % n] if last - first > 1 else ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        piece = _trimmed(edge.segment, a, b, via, band)
        if piece is None:
            # spline with no exact cut (periodic): the stretch stays the ring's, within the
            # discretization tolerance
            chain = [LineSeg(start=pts[i % n], end=pts[(i + 1) % n]) for i in range(first, last)]
        else:
            chain = [piece]
        segments += chain
        styles += [edge.style] * len(chain)
    # two neighbouring stretches each end on its own curve, within `band` of the
    # same ring vertex: up to 2 * band from each other. The jump becomes a new
    # line, no curve moves
    for k, line in reversed(ring_bridges(segments, reach(2 * band), FLOAT_NOISE)):
        segments.insert(k + 1, line)
        styles.insert(k + 1, styles[k])
    return segments, styles, used


def off_rim(edge: Edge, taken: list, ring, band: float) -> List[Edge]:
    """The stretches of `edge` that the border did not take: `taken` are the ends
    (a, b) of the stretches used (`face_segments`), `ring` the border ring. The
    edge is cut at those ends and every piece that moves away from the ring by
    more than `band` stays (its maximum distance, not that of the midpoint: a
    short protrusion starts from the border); an original end of the edge keeps
    its node. Empty if the border takes the whole edge (every input piece comes
    out once, either in the contour or in `loose`)."""
    geom = edge_geometry(edge)
    if geom.geom_type != "LineString" or geom.length <= band:
        return []
    length = geom.length
    closed = segment_is_closed(edge.segment)
    # exact abscissae: two nearly equal cuts give a stretch on the ring, which
    # `_farthest` discards; a grid moved the end with the motion
    cuts = sorted({geom.project(ShapelyPoint(q)) for a, b in taken for q in (a, b)})
    if closed:
        spans = list(zip(cuts, cuts[1:] + [cuts[0] + length])) if cuts else []
    else:
        bounds = [0.0] + [c for c in cuts if band < c < length - band] + [length]
        spans = list(zip(bounds, bounds[1:]))
    out = []
    for d0, d1 in spans:
        if _farthest(geom, d0, d1, ring) <= band:
            continue
        mid = geom.interpolate((d0 + d1) / 2 % length)
        a, b = geom.interpolate(d0 % length), geom.interpolate(d1 % length)
        a, b = (a.x, a.y), (b.x, b.y)
        if not closed:
            a = edge.start if d0 == 0.0 else a
            b = edge.end if d1 == length else b
        piece = sub_segment(edge.segment, a, b, (mid.x, mid.y))
        if piece is None:
            # spline with no exact cut: the stretch of its discretization
            coords = _stretch(geom, d0, d1)
            chain = [LineSeg(start=coords[i], end=coords[i + 1]) for i in range(len(coords) - 1)]
        else:
            chain = [piece]
        for seg in chain:
            s0, s1 = segment_endpoints(seg)
            out.append(replace(edge, segment=seg,
                               start=edge.start if seg is chain[0] and a == edge.start else s0,
                               end=edge.end if seg is chain[-1] and b == edge.end else s1))
    return out


def _stretch(geom, d0: float, d1: float) -> list:
    """The vertices of `geom` from `d0` to `d1` (arc lengths; `d1` beyond the length
    wraps around the ring of a closed curve)."""
    length = geom.length
    if d1 <= length:
        return list(substring(geom, d0, d1).coords)
    return list(substring(geom, d0, length).coords) + list(substring(geom, 0.0, d1 - length).coords)[1:]


def _farthest(geom, d0: float, d1: float, ring) -> float:
    """The maximum distance from `ring` of the stretch of `geom` from `d0` to `d1`,
    on the vertices of its discretization."""
    return max(ring.distance(ShapelyPoint(q)) for q in _stretch(geom, d0, d1))


def _side_cover(pts: list, geoms: list, band: float) -> List[set]:
    """For every side of the ring, the (edge, direction) pairs running along it: the
    midpoint and the two ends of the side within `band` (at least the nearest to
    the midpoint). An edge touching only the midpoint (a protrusion) does not
    cover the side. The direction says whether the side walks the edge like it
    (+1) or backwards (-1). A stretch keeps a single direction — where the ring
    goes back along the same edge (the tip of a face between two nearly tangent
    curves) the stretch ends."""
    tree = STRtree(geoms)
    cover = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        mid = ShapelyPoint((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        ends = (ShapelyPoint(p), ShapelyPoint(q))
        near = [int(j) for j in tree.query(mid, predicate="dwithin", distance=band)
                if all(geoms[int(j)].distance(e) <= band for e in ends)]
        near = near or [int(tree.query_nearest(mid)[0])]
        cover.append({(j, _sense(geoms[j], mid, p, q, band)) for j in near})
    return cover


def _sense(geom, mid, p, q, step: float) -> int:
    """+1 if the side p→q goes the direction of `geom` near `mid`, -1 if against."""
    if geom.length == 0:
        return 1
    d = geom.project(mid)
    a = geom.interpolate(max(d - step, 0.0))
    b = geom.interpolate(min(d + step, geom.length))
    return 1 if (b.x - a.x) * (q[0] - p[0]) + (b.y - a.y) * (q[1] - p[1]) >= 0 else -1


def _rim_runs(pts: list, geoms: list, cover: List[set]) -> list:
    """[((edge, direction), first vertex, last vertex)] along the ring: greedy
    cover at maximum reach — an edge is kept while it covers, then pass to the one
    that covers farthest — which gives the fewest stretches; where two edges both
    cover (overlapping, or nearly tangent) the cut falls on the vertex nearest to
    both, their contact point. Vertex indices not reduced modulo n: increasing,
    last = first + n."""
    n = len(cover)

    def reach(j: tuple, k: int) -> int:
        m = 0
        while m < n and j in cover[(k + m) % n]:
            m += 1
        return m

    def best(k: int) -> tuple:
        return max(sorted(cover[k % n]), key=lambda j: reach(j, k))

    s = min(range(n), key=lambda i: (len(cover[i]), i))
    owners, starts = [best(s)], [s]
    k = s + reach(owners[0], s)
    while k < s + n:
        owners.append(best(k))
        starts.append(k)
        k += reach(owners[-1], k)
    if len(owners) == 1:
        return [(owners[0], s, s + n)]
    if owners[-1] == owners[0]:
        owners.pop()
        starts[0] = starts.pop() - n

    count = len(owners)
    cuts: List[int] = []
    for i in range(count):
        before, after = owners[i - 1], owners[i]
        low = cuts[-1] + 1 if cuts else starts[i - 1] - (n if i == 0 else 0) + 1
        high = starts[i + 1] - 1 if i + 1 < count else min(starts[0] + n, cuts[0] + n) - 1
        lo = starts[i]
        while lo - 1 >= low and {before, after} <= cover[(lo - 1) % n]:
            lo -= 1
        hi = starts[i]
        while hi + 1 <= high and {before, after} <= cover[hi % n]:
            hi += 1

        def gap(v: int) -> float:
            at = ShapelyPoint(pts[v % n])
            return geoms[before[0]].distance(at) + geoms[after[0]].distance(at)

        # overlapping, `gap` is 0 along the whole common stretch and the motion makes it
        # noise: equal within FLOAT_NOISE, the vertex where the coverage changes decides
        gaps = {v: gap(v) for v in range(lo, hi + 1)}
        least = min(gaps.values())
        cuts.append(min((v for v, g in gaps.items() if g <= least + FLOAT_NOISE),
                        key=lambda v: abs(v - starts[i])))
    return [(owners[i], cuts[i], cuts[i + 1] if i + 1 < count else cuts[0] + n)
            for i in range(count)]


def _trimmed(seg, a, b, via, band: float):
    """`seg` from `a` to `b`: an end within `band` of an end of `seg` is that end
    (the true node, not its projection); if both are, the whole segment. An end at
    the same distance from both ends (within FLOAT_NOISE: the middle of a short
    segment) is the node of neither and stays where it is."""
    s0, s1 = segment_endpoints(seg)

    def node(p):
        d0, d1 = math.dist(p, s0), math.dist(p, s1)
        if abs(d0 - d1) <= FLOAT_NOISE:
            return None
        end, d = (s0, d0) if d0 < d1 else (s1, d1)
        return end if d <= band else None

    if math.dist(s0, s1) > band:
        sa, sb = node(a), node(b)
        if sa is not None and sb is not None and sa != sb:
            return seg if sa == s0 else seg.reversed()
        a = a if sa is None else sa
        b = b if sb is None else sb
    return sub_segment(seg, a, b, via)
