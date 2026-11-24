"""
topo/core/readings/parity_faces.py
----------------------------------
The parity reading of a repaired network: `topo.experimental.parity_faces`.
Experimental: where the choice has ties it depends on the coordinates.

The faces of the planar network (crossings cut) are coloured inside/outside so
that every side separates two different colours; the contours are the loops of
the outside faces. Where a node has odd degree, free ends and bridges are
removed first, then the set of sides that makes every node even removing as
little as possible of the silhouette, then the minimum length
(`topology/parity.py`). The rest — hierarchy, loose, warnings — is that of
`faces()`.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...precision import SAME_POINT
from ..geometry.measure import reach as threshold
from ...model.curve import ClosedCurve
from ...model.diagnostic import Diagnostic, plural as _plural
from ...model.result import Result
from ..base.curves import loops_to_curves, loose_curves
from ..base.hierarchy import assign_cluster_refs
from ..topology.noding import split_at_crossings
from ..topology.parity import parity_rings
from .faces import _crossing_warnings, _loose_ends_notes
from .heal_steps import build_hierarchy, close_contour_jumps, may_be_contour

if TYPE_CHECKING:
    from .network import Network


def parity_faces(net: Network) -> Result:
    """Read the network by parity: every remaining side separates an inside
    face from an outside one. Experimental.

    The faces of a planar network admit an inside/outside colouring with
    every side between two colours if and only if every node has even
    degree, and then it is unique: where all nodes are even, this is the
    only reading in which every side is a contour. Where a node is odd, the
    reading removes free ends and bridges (the same face on both sides),
    then the set of sides that makes every node even removing first the
    least length of the outer boundary, then the least length overall
    (a minimum T-join, exact). Crossings are cut. Edges with a decided
    non-structural role take no part.

    Not guaranteed: where two such sets have the same length (symmetric
    drawings), which one is removed depends on the coordinates, so a moved
    or mirrored drawing can read differently."""
    tol, structural = SAME_POINT, net._structural
    label, source_file = net.label, net.source_file
    reach = threshold(tol)

    result = Result(source_file=source_file, source_format=net.source_format, reading="parity",
                    max_gap=net.max_gap)
    result.texts = list(net._texts)
    result.warnings += net.warnings
    result.notes += net.notes
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    labeled, edges = net.set_aside, net.edges

    # the planar network cut also at the crossings; an edge the caller declared non-structural does not enter the parity
    noded = split_at_crossings(edges, tol)
    parity = parity_rings([p for p in noded.pieces if may_be_contour(noded.parent_of(p), structural)])
    dropped = parity.dropped
    if dropped:
        starts = [noded.parent_of(p).start for p in noded.pieces if id(p) in dropped]
        excluded = {id(noded.parent_of(p)) for p in noded.pieces if id(p) in dropped}
        result.notes.append(Diagnostic(
            "non-contour", f"{_plural(len(excluded), 'edge', 'edges')} read as no contour",
            points=list(dict.fromkeys(starts)),
            notes=["free ends, bridges, and the least outer boundary, then the shortest "
                   "length, that leaves every node of even degree"],
            level="note"))
    if parity.rim_used:
        result.warnings.append(Diagnostic(
            "rim-cut", "no set of inner edges leaves every node of even degree: "
                       "part of the outer boundary is read as no contour",
            notes=["the least outer boundary that does it, then the shortest"]))
    if parity.conflicts:
        result.warnings.append(Diagnostic(
            "face-colour", f"{_plural(len(parity.conflicts), 'node', 'nodes')} where two "
                           f"neighbouring faces read the same side",
            points=parity.conflicts,
            notes=["the walk round a node does not order branches that leave it tangent"]))
    closed, used = [], set()
    for loop in (noded.whole(loop) for loop in parity.loops):
        curves = loops_to_curves([loop])
        if len(curves) == 1 and isinstance(curves[0], ClosedCurve):
            closed += curves
            used |= {id(e) for e, _ in loop}
    if closed:
        result.notes += _loose_ends_notes(net.free_ends, noded.pieces, parity.joining)
        result.warnings += _crossing_warnings(net.crossings)
    else:
        result.notes.append(Diagnostic("no-loop", "the edges close no loop", level="note"))
    # to loose whatever no loop takes: the whole edge if none of its pieces is a
    # contour, otherwise its remaining pieces
    #
    pieces_of: dict = {}
    for piece in noded.pieces:
        pieces_of.setdefault(id(noded.parent_of(piece)), []).append(piece)
    rest = []
    for edge in edges:
        if id(edge) in used:
            continue
        pieces = pieces_of.get(id(edge), [])
        rest += [p for p in pieces if id(p) not in used] if any(id(p) in used for p in pieces) else [edge]
    curves = closed + loose_curves(rest)
    if not curves:
        result.loose = loose_curves(labeled)
        result.errors.append(Diagnostic("no-closed-outer", "nothing closes after the repair", level="error"))
        result.is_valid = False
        return result

    clusters, loose = build_hierarchy(curves, label=label,
                                      is_structural=structural)
    result.clusters = clusters
    result.loose = loose + loose_curves(labeled)
    assign_cluster_refs(result.loose, clusters, reach)
    if not clusters:
        result.errors.append(Diagnostic(
            "no-closed-outer", "no closed outer contour, so no part",
            points=[p for p, _ in net.free_ends],
            notes=["the free ends meet nothing within max_gap"], level="error"))
        result.is_valid = False
        return result

    close_contour_jumps(result, tol)
    from ...rules.validator import validate_result
    validate_result(result)
    return result
