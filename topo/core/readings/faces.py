"""
topo/core/readings/faces.py
---------------------------
The reading from the inside of a repaired network: `Network.faces()`.

It rebuilds the topology (who touches whom, which loops close, how they lie
inside one another) and finds the figure by containment. It is the reading for
flat figures, a nesting of separate ones. The steps are in
`base/cleanup.py` (common) and `readings/heal_steps.py`, public: here is only
their default composition, plus the warnings that tell it.

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
from ..topology.outer_face import face_loops
from ..topology.non_contour_edges import non_contour_pieces
from ..base.hierarchy import assign_cluster_refs
from .heal_steps import find_joining_edges, structural_loops, build_hierarchy, close_contour_jumps

if TYPE_CHECKING:
    from .network import Network


def read_faces(net: Network) -> Result:
    """A Cluster per closed outer contour of the network, with the inners by
    containment (`Network.faces()`)."""
    tol, structural = SAME_POINT, net._structural
    label, source_file = net.label, net.source_file
    reach = threshold(tol)

    result = Result(source_file=source_file, source_format=net.source_format, reading="faces",
                    max_gap=net.max_gap)
    result.texts = list(net._texts)
    result.warnings += net.warnings
    result.notes += net.notes
    if not net.is_valid:
        result.errors += net.errors
        return result
    labeled, edges = net.set_aside, net.edges

    # the planar network, the non-contours on it, the loops of the bounded faces:
    # the same network, the same judgment and the same walk as outlines()
    noded = net._noded
    non_contour = non_contour_pieces(noded, tol)
    excluded = {id(noded.parent_of(p)) for p in noded.pieces if id(p) in non_contour}
    if excluded:
        starts = [noded.parent_of(p).start for p in noded.pieces if id(p) in non_contour]
        result.notes.append(Diagnostic(
            "non-contour", f"{_plural(len(excluded), 'edge', 'edges')} read as no contour",
            points=list(dict.fromkeys(starts)),
            notes=["chains between two branching nodes that the outer boundary does not run once"],
            level="note"))
    loops = [noded.whole(loop) for loop in face_loops([p for p in noded.pieces if id(p) not in non_contour])]
    # a loop that does not become a contour (no area) takes nothing: its edges go
    # whole to loose, like those no loop touches
    closed, used = [], set()
    for loop in structural_loops(loops, structural):
        curves = loops_to_curves([loop])
        if len(curves) == 1 and isinstance(curves[0], ClosedCurve):
            closed += curves
            used |= {id(e) for e, _ in loop}
    kept = closed
    if kept:
        result.notes += _loose_ends_notes(net.free_ends, noded.pieces, non_contour)
        result.warnings += _crossing_warnings(noded.crossings)
    else:
        result.notes.append(Diagnostic("no-loop", "no loop of the edges bounds a face", level="note"))
    # to loose whatever no loop takes: the whole edge if none of its pieces is a
    # contour, otherwise its remaining pieces
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
        # no piece, but the edges set aside stay in loose
        result.loose = loose_curves(labeled)
        result.errors.append(Diagnostic("no-closed-outer", "nothing closes after the repair", level="error"))
        return result

    clusters, loose = build_hierarchy(curves, label=label,
                                      is_structural=structural)
    result.clusters = clusters
    result.loose = loose + loose_curves(labeled)
    assign_cluster_refs(result.loose, clusters, reach)
    if not clusters:
        # The geometry composes no closed outer contour: the result is not a figure, it
        # is an unworkable file. `loose` stays for diagnostics, but a writer refuses to
        # write only that.
        result.errors.append(Diagnostic(
            "no-closed-outer", "no closed outer contour, so no figure",
            points=[p for p, _ in net.free_ends] + list(noded.crossings),
            notes=_no_outer_notes(net, noded.crossings), level="error"))
        return result

    close_contour_jumps(result, tol)
    from ...rules.validator import validate_result
    validate_result(result)
    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _loose_ends_notes(ends: list, pieces: list, non_contour_ids: set) -> list:
    """What stays open even when something closes: the free ends of the network, and
    the edges joining two otherwise detached shapes."""
    notes = []
    if ends:
        notes.append(Diagnostic(
            "free-end", f"{_plural(len(ends), 'free end that closes', 'free ends that close')} nothing, in loose",
            points=[p for p, _ in ends],
            notes=[f"{_span([d for _, d in ends])} mm from the nearest node"],
            level="note"))
    joining = find_joining_edges(pieces, non_contour_ids)
    if joining:
        notes.append(Diagnostic(
            "joining-edge", f"{_plural(len(joining), 'edge joins', 'edges join')} two shapes otherwise apart: "
                            f"no contour, each shape read by itself",
            points=[e.start for e in joining], level="note"))
    return notes


def _span(values: list) -> str:
    """`a to b` of the values, or one number when they agree to three figures."""
    lo, hi = format(min(values), ".3g"), format(max(values), ".3g")
    return lo if lo == hi else f"{lo} to {hi}"


def _no_outer_notes(net, crossings: list) -> list:
    """Why nothing closed, from what the network holds: free ends, crossings not cut."""
    notes = []
    if net.free_ends:
        notes.append(f"{_plural(len(net.free_ends), 'free end meets', 'free ends meet')} nothing within max_gap")
    if crossings:
        notes.append(f"{_plural(len(crossings), 'crossing', 'crossings')} with no shared node: this reading "
                     f"does not cut a side where another crosses it; outlines() does")
    if any(w.code == "self-crossing" for w in net.warnings):
        notes.append("a curve crosses itself and is not cut there (warning self-crossing)")
    return notes


def _crossing_warnings(points: list) -> list:
    """Contour sides crossing without a node: each side stays as drawn, the
    reading does not cut it there."""
    if not points:
        return []
    return [Diagnostic(
        "crossing", f"{_plural(len(points), 'crossing', 'crossings')} between contour sides with no shared node",
        points=points, notes=["the sides cross in the input; each contour is read as drawn"],
        help="if the sides are meant to meet there, split them at the crossing in the input")]
