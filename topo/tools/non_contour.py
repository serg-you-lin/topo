"""
topo/tools/non_contour.py
---------------------------
Exposes to a consumer the same topological criterion `heal()` uses internally
to decide "this edge does not close a contour" — `NonContourEdgeDetector`
(chains between two distinct branching nodes, and not on the border of the
outer face of their connected component).

`heal()` never assigns a meaning to these edges: it excludes them from the
graph and that is all, they stay in `loose` with the role they had (`unknown`
if nobody had decided). A downstream consumer interprets them, for instance a straight
candidate with both ends on the outer contour.

A consumer with an interpretation of its own may want the
same list of candidates WITHOUT any, to apply its own and assign `edge.role`
before calling `heal()`. `non_contour_candidates()` is the hook: same
criterion, no duplication, no second source of truth that could diverge from
heal()'s.

Note: it works on `doc.edges` as they are, BEFORE `heal()` merges overlapping
/co-circular segments and closes tiny gaps (its first internal steps). On a
input with duplicates or gaps below tolerance the result may differ slightly
from what `heal()` would exclude in the end — not a problem: this function
serves to decide `edge.role` BEFORE heal(), the final word on what stays in
the graph is heal()'s own.
"""

from __future__ import annotations

from typing import List

from ..model.document import Document
from ..precision import SAME_POINT
from ..core.topology.edge import Edge
from ..core.readings.heal_steps import find_non_contour_edges


def non_contour_candidates(doc: Document) -> List[Edge]:
    """
    Edges of `doc.edges` that `heal()`'s topological criterion would exclude
    from the contour graph — candidates for "something else", without saying
    what.
    """
    edges = list(doc.edges)
    excluded_ids = find_non_contour_edges(edges, SAME_POINT)
    return [e for e in edges if id(e) in excluded_ids]
