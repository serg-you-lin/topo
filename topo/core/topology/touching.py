"""
topo/core/topology/touching.py
------------------------------
Groups the Edges that touch: two edges are in the same group if the true
distance between their segments is at most `gap_tolerance` (in a chain). No
notion of node, graph or closure — only nearness, so it does not inherit the
ambiguity of connectivity that breaks the graph on projected views.

True distance, not between bboxes: the bbox of a long diagonal (isometric
view) covers an empty rectangle touching the neighbouring views.

A group is a view or a candidate part: which of the two is the caller's call.
`gap_tolerance` too is the caller's: it depends on how the drawing is laid
out, not on the geometry. A hole far from the sides stays a group of its own:
that it is INSIDE another is told only by the outer contour, not by nearness.

Pure: Edges and primitives only, no format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

import numpy as np
import shapely
import shapely.ops

from ..geometry.measure import reach
from ..geometry.strips import refine_gap
from ..primitives.mathseg import DEFAULT_TOLERANCE
from .edge import Edge
from .graph import connected_groups
from .noding import edge_geometry, near_pairs

BBox = Tuple[float, float, float, float]   # xmin, ymin, xmax, ymax


@dataclass
class TouchingGroup:
    """A group of near Edges, with the bbox containing them all."""
    edges:  List[Edge]   = field(default_factory=list)   # input order
    bbox:   BBox         = (0.0, 0.0, 0.0, 0.0)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]


# --- Public API ---

def touching_groups(edges: Iterable[Edge], gap_tolerance: float) -> List[TouchingGroup]:
    """Union-find on the pairs of Edges at true distance <= gap_tolerance
    (`_judged_pairs`). Groups sorted by bbox area, decreasing."""
    edges = list(edges)
    if not edges:
        return []

    geoms = [edge_geometry(e) for e in edges]
    groups = connected_groups(len(edges), _judged_pairs(edges, geoms, gap_tolerance))

    groups_out = []
    for members in groups:
        bounds = [geoms[i].bounds for i in members]
        groups_out.append(TouchingGroup(
            edges=[edges[i] for i in members],
            bbox=(min(b[0] for b in bounds), min(b[1] for b in bounds),
                  max(b[2] for b in bounds), max(b[3] for b in bounds)),
        ))
    groups_out.sort(key=lambda g: g.width * g.height, reverse=True)
    return groups_out


def _judged_pairs(edges: List[Edge], geoms: list, gap_tolerance: float) -> List[Tuple[int, int]]:
    """The pairs of edges at true distance <= `gap_tolerance`. The discretizations
    are wrong by up to DEFAULT_TOLERANCE per curve, and their error turns with
    the drawing: outside the band of 2·DEFAULT_TOLERANCE around the threshold
    they decide, inside the distance on the primitives."""
    band = 2 * DEFAULT_TOLERANCE
    candidates = near_pairs(geoms, gap_tolerance)
    if not candidates:
        return []
    left, right = (np.array(side) for side in zip(*candidates))
    measured = shapely.distance(np.array(geoms, dtype=object)[left], np.array(geoms, dtype=object)[right])
    pairs = []
    for i, j, d in zip(left.tolist(), right.tolist(), measured.tolist()):
        if d > gap_tolerance - band:
            pa, pb = shapely.ops.nearest_points(geoms[i], geoms[j])
            found = refine_gap([edges[i].segment], [edges[j].segment], (pa.x, pa.y), (pb.x, pb.y))
            if found.distance > reach(gap_tolerance):   # the threshold is included

                continue
        pairs.append((i, j))
    return pairs


