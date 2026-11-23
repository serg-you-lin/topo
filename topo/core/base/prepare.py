"""
topo/core/base/prepare.py
-------------------------
The common foundations of every reading: `faces()`, `outlines()` and any
recipe a caller composes start from here, with the same rules. A reading
chooses only how it looks for the contour; everything before is the drawing's
geometry and is decided once, in one place.

    prepare    — non-structural roles set aside, nodes decided once
                 (`decide_nodes`)
    normalize  — collinear and co-circular duplicates, degenerate stretches,
                 nearly complete arcs, gaps: the same functions for all;
                 differences between readings are named parameters

Pure: Edges and primitives only, no format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..topology.edge import Edge
from ..topology.noding import decide_nodes
from .merge import merge_cocircular_overlaps, merge_collinear_overlaps
from .refit import (refit_circle_rings,
                    refit_native_curves, refit_tessellations)
from .cleanup import (ambiguous_free_ends, bend_arcs_through_free_ends, close_free_gaps, close_near_full_arcs,
                      join_tied_facing_ends, move_onto_targets, split_labeled)


@dataclass
class Prepared:
    """The edges ready for a reading, and what `prepare` set aside."""
    edges:   List[Edge] = field(default_factory=list)   # strutturali, nodi decisi
    labeled: List[Edge] = field(default_factory=list)   # decided, non-structural role
    welded:  int = 0                                    # shorter than GRAPH_EPSILON, welded


def prepare(edges: List[Edge],
            is_structural: Optional[Callable[[str], bool]] = None) -> Prepared:
    """Non-structural roles aside, then the nodes decided once for all readings. A
    non-finite coordinate does not get here: the primitive rejects it."""
    kept, labeled = split_labeled(list(edges), is_structural)
    noded, welded = decide_nodes(kept)
    return Prepared(edges=noded, labeled=labeled, welded=welded)


@dataclass
class Normalized:
    """The normalized edges and how many each step touched."""
    edges:          List[Edge] = field(default_factory=list)
    merged_lines:   int = 0
    merged_arcs:    int = 0
    full_arcs:      int = 0
    ambiguous:      list = field(default_factory=list)   # ends with no partner chosen
    gaps:           list = field(default_factory=list)   # (end, distance) of the closed gaps
    moved:          list = field(default_factory=list)   # (point, displacement) of the moved curves
    tied:           list = field(default_factory=list)   # (end, distance) of the bound ends joined
    bent:           list = field(default_factory=list)   # (end, distance) of the arcs redrawn for an end


def normalize(edges: List[Edge], gap: float, *, keep_junctions: bool) -> Normalized:
    """The cleanups of every reading: the same functions, in the same order, for
    all. `gap`: the distance up to which two free ends close, already including
    the margin (`geometry.measure.reach`).

    Curves written as points refitted, collinear and co-circular duplicates
    merged, nearly complete arcs closed, gaps pairwise: each end closes at most
    one gap, with the nearest partner; on a tie none.

    keep_junctions: two collinear pieces touching only at a branch do not merge.
    It stays until heal() nodes the contacts like outlines()."""
    out = Normalized()
    edges = refit_tessellations(edges)
    # a curve of the file that is an arc, an ellipse or a circle becomes that
    edges = refit_native_curves(edges)
    merged = merge_collinear_overlaps(edges, keep_junctions=keep_junctions)
    out.merged_lines, edges = len(edges) - len(merged), merged
    merged = merge_cocircular_overlaps(edges)
    out.merged_arcs, edges = len(edges) - len(merged), merged
    edges, out.full_arcs = close_near_full_arcs(edges, gap)
    # a curve with its ends beside its targets moves onto them before a gap binds
    # them elsewhere; the nodes are decided again from the new points
    edges = move_onto_targets(edges, gap, out.moved)
    if out.moved:
        edges, _ = decide_nodes(edges)
    # an arc nailed at its ends passes through the free end beside its belly
    edges = bend_arcs_through_free_ends(edges, gap, out.bent)
    out.ambiguous = ambiguous_free_ends(edges, gap)
    closed = close_free_gaps(edges, gap, out.gaps)
    # a side in two pieces with ends already bound: the hole along its line
    closed = join_tied_facing_ends(closed, gap, out.tied)
    # closing a gap lengthens the two halves towards each other: they overlap on the
    # gap's stretch, and that stretch stays double in the network
    merged = merge_collinear_overlaps(closed, keep_junctions=keep_junctions)
    out.merged_lines += len(closed) - len(merged)
    # only now is the ring of a hole written as points closed: it becomes its circle
    out.edges = refit_circle_rings(merged)
    return out
