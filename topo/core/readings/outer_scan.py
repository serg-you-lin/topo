"""
topo/core/readings/outer_scan.py
--------------------------------
Classification of the outer borders by ray casting: which Edges are, at some
height at least, the first or the last point met by a ray crossing the
drawing. It does not rebuild the contour — gaps and loops sew it afterwards,
on the original Edges.

A global property (min/max over a whole height), not local connectivity: it
works even where the graph is ambiguous (nearly coincident edges converging
on the same nodes). Scanning on both axes, because a horizontal ray never
sees a horizontal edge.

Pure: Edges and primitives only, no format.
"""

from __future__ import annotations

from ...precision import FLOAT_NOISE
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from ..topology.edge import Edge
from ..primitives.mathseg import MathSeg, DEFAULT_TOLERANCE
from ..primitives.conics import angle_from_start, point_on_circle
from ..primitives.line import LineSeg
from ..primitives.conics import CircleSeg

Point = Tuple[float, float]

AXIS_Y = "y"   # horizontal ray at height y, extremes in x
AXIS_X = "x"   # vertical ray at height x, extremes in y

SIDE_MIN = "min"
SIDE_MAX = "max"

_EPS = FLOAT_NOISE


# --- Result ---

@dataclass
class OuterHit:
    """A ray for which the Edge was the extreme."""
    axis:   str      # AXIS_Y / AXIS_X
    level:  float    # height of the ray
    side:   str      # SIDE_MIN / SIDE_MAX
    point:  Point    # real intersection point


@dataclass
class OuterCandidates:
    """Edges that are candidates for the outer border, with the rays that chose them."""
    edges:   List[Edge]                  = field(default_factory=list)   # input order
    hits:    Dict[int, List[OuterHit]]   = field(default_factory=dict)   # id(edge) -> hit
    n_rays:  int                         = 0

    @property
    def ids(self) -> set:
        return set(self.hits)

    def hits_of(self, edge: Edge) -> List[OuterHit]:
        return self.hits.get(id(edge), [])


# --- Public API ---

def outer_candidate_edges(edges: Iterable[Edge]) -> OuterCandidates:
    """For each axis, a representative height (midpoint) between every pair of
    consecutive event heights — segment ends, arc extremes along the axis — and
    for each the first and last intersection point. The Edge producing them is a
    candidate. Analytic LineSeg/CircleSeg, discretized BSplineSeg/EllipseSeg."""
    edges = list(edges)
    pieces = [p for edge in edges for p in _pieces(edge)]

    hits: Dict[int, List[OuterHit]] = {}
    n_rays = 0
    for axis in (AXIS_Y, AXIS_X):
        n_rays += _scan_axis(pieces, axis, hits)

    candidates = [e for e in edges if id(e) in hits]
    return OuterCandidates(edges=candidates, hits=hits, n_rays=n_rays)


# --- Elementary pieces: lines and circle arcs ---

@dataclass
class _Line:
    edge:  Edge
    p:     Point
    q:     Point


@dataclass
class _Arc:
    edge:   Edge
    center: Point
    radius: float
    start:  float   # radianti
    sweep:  float   # radians, positive
    ccw:    bool


def _pieces(edge: Edge) -> list:
    seg = edge.segment
    if isinstance(seg, LineSeg):
        return [_Line(edge, seg.start, seg.end)]
    if isinstance(seg, CircleSeg):
        return [_Arc(edge, seg.center, seg.radius, seg.start_angle, seg._sweep(), seg.ccw)]
    if isinstance(seg, MathSeg):
        # splines and non-circular conics: on the polygon
        pts = seg.discretize(tolerance=DEFAULT_TOLERANCE)
        return [_Line(edge, pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return []


def _within_sweep(arc: _Arc, pt: Point) -> bool:
    return angle_from_start(arc.center, arc.start, arc.ccw, pt) <= arc.sweep + _EPS / arc.radius


def _arc_point(arc: _Arc, angle: float) -> Point:
    return point_on_circle(arc.center, arc.radius, angle)


def _extent(piece, a: int) -> Tuple[float, float]:
    """(min, max) of the piece along coordinate `a` (0 = x, 1 = y)."""
    if isinstance(piece, _Line):
        return min(piece.p[a], piece.q[a]), max(piece.p[a], piece.q[a])
    end = piece.start + (piece.sweep if piece.ccw else -piece.sweep)
    values = [_arc_point(piece, piece.start)[a], _arc_point(piece, end)[a]]
    c, r = piece.center[a], piece.radius
    for extreme in (c - r, c + r):
        pt = list(piece.center)
        pt[a] = extreme
        if _within_sweep(piece, tuple(pt)):
            values.append(extreme)
    return min(values), max(values)


def _intersections(piece, a: int, level: float) -> List[Point]:
    """Points of the piece with coordinate `a` == level."""
    b = 1 - a
    if isinstance(piece, _Line):
        p, q = piece.p, piece.q
        if abs(q[a] - p[a]) < _EPS:
            return []   # parallel to the ray: the other axis sees it
        t = (level - p[a]) / (q[a] - p[a])
        slack = _EPS / abs(q[a] - p[a])
        if t < -slack or t > 1 + slack:
            return []
        pt = [0.0, 0.0]
        pt[a] = level
        pt[b] = p[b] + t * (q[b] - p[b])
        return [tuple(pt)]

    d = level - piece.center[a]
    if abs(d) > piece.radius:
        return []
    h = math.sqrt(max(piece.radius * piece.radius - d * d, 0.0))
    out = []
    for sign in (-1.0, 1.0):
        pt = [0.0, 0.0]
        pt[a] = level
        pt[b] = piece.center[b] + sign * h
        pt = tuple(pt)
        if _within_sweep(piece, pt):
            out.append(pt)
    return out


# --- Sweep on an axis ---

def _scan_axis(pieces: list, axis: str, hits: Dict[int, List[OuterHit]]) -> int:
    a = 1 if axis == AXIS_Y else 0
    b = 1 - a
    spans = [(_extent(p, a), p) for p in pieces]
    spans.sort(key=lambda s: s[0][0])

    events = sorted({v for (lo, hi), _ in spans for v in (lo, hi)})
    levels = [
        (events[i] + events[i + 1]) / 2
        for i in range(len(events) - 1)
        if events[i + 1] - events[i] > _EPS
    ]

    active: list = []
    nxt = 0
    for level in levels:
        while nxt < len(spans) and spans[nxt][0][0] <= level:
            active.append(spans[nxt])
            nxt += 1
        active = [s for s in active if s[0][1] >= level]

        found = [(pt, piece) for _, piece in active
                 for pt in _intersections(piece, a, level)]
        if not found:
            continue
        lo = min(pt[b] for pt, _ in found)
        hi = max(pt[b] for pt, _ in found)
        for pt, piece in found:
            for side, extreme in ((SIDE_MIN, lo), (SIDE_MAX, hi)):
                if abs(pt[b] - extreme) <= _EPS:
                    hits.setdefault(id(piece.edge), []).append(
                        OuterHit(axis=axis, level=level, side=side, point=pt)
                    )
    return len(levels)
