"""
topo/core/readings/faces.py
---------------------------
La lettura dall'interno di una rete riparata: `Network.faces()`.

Ricostruisce la topologia (chi tocca chi, quali giri si chiudono, come stanno
uno dentro l'altro) e trova il pezzo per contenimento. È la lettura per un
disegno piano — un file di taglio, un nesting di pezzi separati. I passi sono
in `base/cleanup.py` (comuni, D187) e `readings/heal_steps.py`, pubblici: qui
c'è solo la loro composizione di default, più i warning che la raccontano.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    """Un Cluster per contorno esterno chiuso della rete, con gli inners per
    contenimento (`Network.faces()`)."""
    tol, structural = net.tolerance, net._structural
    label, source_file = net.label, net.source_file
    reach = threshold(tol)

    result = Result(source_file=source_file, source_format=net.source_format, reading="faces",
                    tolerance=net.tolerance, max_gap=net.max_gap)
    result.texts = list(net._texts)
    result.warnings += net.warnings
    result.notes += net.notes
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    labeled, edges = net.set_aside, net.edges

    # la rete piana, i non-contorno su di lei, i giri delle facce limitate:
    # la stessa rete, lo stesso giudizio e lo stesso cammino di outlines() (D189)
    noded = net._noded
    non_contour = non_contour_pieces(noded, tol)
    excluded = {id(noded.parent_of(p)) for p in noded.pieces if id(p) in non_contour}
    if excluded:
        starts = [noded.parent_of(p).start for p in noded.pieces if id(p) in non_contour]
        result.notes.append(Diagnostic(
            "non-contour", f"{_plural(len(excluded), 'edge', 'edges')} read as no contour",
            points=list(dict.fromkeys(starts)),
            notes=["chains between two branching nodes that the outer boundary does not run once (D111, D131)"],
            level="note"))
    loops = [noded.whole(loop) for loop in face_loops([p for p in noded.pieces if id(p) not in non_contour])]
    # un giro che non diventa un contorno (senza area, D151) non prende niente:
    # i suoi edge vanno in loose interi, come quelli che nessun giro tocca
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
        result.errors.append(Diagnostic("no-closed-outer", "nothing closes after the repair", level="error"))
        result.is_valid = False
        return result

    clusters, loose = build_hierarchy(curves, label=label, source_file=source_file,
                                      is_structural=structural)
    result.clusters = clusters
    result.loose = loose + loose_curves(labeled)
    assign_cluster_refs(result.loose, clusters, reach)
    if not clusters:
        # La geometria non compone nessun contorno esterno chiuso: il
        # risultato non è un pezzo, è un file non lavorabile. `loose` resta
        # per la diagnostica, ma to_dxf() si rifiuta di scrivere solo quella.
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _loose_ends_notes(ends: list, pieces: list, non_contour_ids: set) -> list:
    """Quello che resta aperto anche quando qualcosa si chiude (D111): gli
    estremi liberi della rete, e gli edge che uniscono due forme altrimenti
    staccate."""
    notes = []
    if ends:
        notes.append(Diagnostic(
            "free-end", f"{_plural(len(ends), 'free end', 'free ends')} that close nothing, in loose",
            points=[p for p, _ in ends],
            notes=[f"{min(d for _, d in ends):.3g} to {max(d for _, d in ends):.3g} from the nearest node"],
            level="note"))
    joining = find_joining_edges(pieces, non_contour_ids)
    if joining:
        notes.append(Diagnostic(
            "joining-edge", f"{_plural(len(joining), 'edge joins', 'edges join')} two shapes otherwise apart: "
                            f"no contour, each shape read by itself",
            points=[e.start for e in joining], level="note"))
    return notes


def _crossing_warnings(points: list) -> list:
    """Lati di contorno che si attraversano senza un nodo (D132): il disegno è
    rotto lì; la rete piana li noda per leggere le facce, e heal() lo dice."""
    if not points:
        return []
    return [Diagnostic(
        "crossing", f"{_plural(len(points), 'crossing', 'crossings')} between contour sides with no shared node",
        points=points, notes=["the sides overlap in the drawing"],
        help="in the drawing, split the sides at the crossing or shorten them until they touch")]
