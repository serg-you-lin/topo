"""
topo/core/readings/parity_faces.py
----------------------------------
La lettura per parità di una rete riparata: `topo.experimental.parity_faces`
(D250). Sperimentale: dove la scelta ha pareggi dipende dalle coordinate.

Le facce della rete piana (incroci tagliati) si colorano dentro/fuori in modo
che ogni lato separi due colori diversi; i contorni sono i giri delle facce
fuori. Dove un nodo ha grado dispari si tolgono prima capi liberi e ponti,
poi l'insieme di lati che rende pari ogni nodo togliendo il meno possibile
della sagoma, poi la lunghezza minima (`topology/parity.py`). Il resto —
gerarchia, loose, warning — è quello di `faces()`.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    """
    Read the network by parity: every remaining side separates an inside
    face from an outside one. Experimental (D250).

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
    or mirrored drawing can read differently.
    """
    tol, structural = net.tolerance, net._structural
    label, source_file = net.label, net.source_file
    reach = threshold(tol)

    result = Result(source_file=source_file, source_format=net.source_format, reading="parity",
                    tolerance=net.tolerance, max_gap=net.max_gap)
    result.texts = list(net._texts)
    result.warnings += net.warnings
    result.notes += net.notes
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    labeled, edges = net.set_aside, net.edges

    # la rete piana tagliata anche agli incroci; un edge che il chiamante ha
    # detto non strutturale non entra nella parità
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
                   "length, that leaves every node of even degree (D250)"],
            level="note"))
    if parity.rim_used:
        result.warnings.append(Diagnostic(
            "rim-cut", "no set of inner edges leaves every node of even degree: "
                       "part of the outer boundary is read as no contour",
            notes=["the least outer boundary that does it, then the shortest (D250)"]))
    if parity.conflicts:
        result.warnings.append(Diagnostic(
            "face-colour", f"{_plural(len(parity.conflicts), 'node', 'nodes')} where two "
                           f"neighbouring faces read the same side",
            points=parity.conflicts,
            notes=["the walk round a node does not order branches that leave it tangent (D199)"]))
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
    # in loose ciò che nessun giro prende: l'edge intero se nessun suo pezzo
    # è contorno, altrimenti i suoi pezzi rimasti
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

    clusters, loose = build_hierarchy(curves, label=label, source_file=source_file,
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
