"""
topo/core/readings/heal.py
--------------------------
Primo modo di leggere un Document, accanto a island(): dall'interno.

heal() ricostruisce la topologia (chi tocca chi, quali giri si chiudono, come
stanno uno dentro l'altro) e trova il pezzo per contenimento. È la ricetta per
un disegno piano — un file di taglio, un nesting di pezzi separati. I passi
sono in `base/cleanup.py` (comuni, D187) e `readings/heal_steps.py`, pubblici: qui c'è solo la loro composizione di
default, più i warning che la raccontano.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import Callable, Optional

from ...model.document import Document
from ..geometry.measure import reach as threshold
from ...model.curve import ClosedCurve
from ...model.result import Result
from ..base.curves import loops_to_curves, loose_curves
from ..topology.outer_face import face_loops
from ..topology.non_contour_edges import non_contour_pieces
from ..base.hierarchy import assign_cluster_refs
from .heal_steps import find_joining_edges, structural_loops, build_hierarchy
from .network import build_network


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def heal(doc: Document, *, tolerance: Optional[float] = None, label: str = "",
         source_file: str = "",
         is_structural: Optional[Callable[[str], bool]] = None) -> Result:
    """
    Legge `doc` dall'interno: un Cluster per contorno esterno chiuso,
    con gli inners per contenimento.

    tolerance: se None viene ripresa da doc.source_meta['tolerance']
               (quella usata per arrotondare i nodi in load_dxf).
    I ruoli arrivano già sugli Edge: li assegna il loader (role_rules, D63).
    is_structural: predicato `Callable[[str], bool]` — "questo ruolo è
               topologia di contorno di pezzo?" — usato per decidere quali
               Edge già etichettati restano nel grafo prima della ricerca
               loop. Il motore da solo conosce solo outer/inner; un
               consumatore passa il suo (snapbend: un foro è contorno di
               pezzo). Senza, un edge etichettato "hole" viene trattato come
               non strutturale e heal() lo segnala con un warning.
    """
    if not isinstance(doc, Document):
        raise TypeError(
            "topo.heal() richiede un Document da topo_dxf.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )
    # la riparazione comune a ogni lettura (D202)
    net = build_network(doc, tolerance=tolerance, is_structural=is_structural,
                        source_file=source_file, label=label)
    tol, structural = net.tolerance, net.structural
    reach = threshold(tol)

    result = Result(source_file=source_file)
    result.texts = list(doc.texts)
    result.warnings += net.warnings
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    labeled, edges = net.set_aside, net.edges

    # la rete piana, i non-contorno su di lei, i giri delle facce limitate:
    # la stessa rete, lo stesso giudizio e lo stesso cammino di island() (D189)
    noded = net.noded
    non_contour = non_contour_pieces(noded, tol)
    excluded = {id(noded.parent_of(p)) for p in noded.pieces if id(p) in non_contour}
    if excluded:
        result.warnings.append(
            f"{len(excluded)} edge non di contorno "
            f"esclusi dal grafo (catene fra due nodi di branching, non sul bordo esterno)."
        )
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
        result.warnings += _loose_ends_warnings(net.free_ends, noded.pieces, non_contour)
        result.warnings += _crossing_warnings(noded.crossings)
    else:
        result.warnings.append("LINE/ARC non formano giri chiusi — "
                               "potrebbero essere marcature o geometria aperta.")
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
        result.errors.append("Nessuna geometria chiusa trovata dopo healing.")
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
        result.errors.append(
            "Nessun contorno esterno chiuso: nessuna parte generabile dal file. "
            "Gli endpoint liberi non si congiungono entro la tolleranza richiesta."
        )
        result.is_valid = False
        return result

    from ...rules.validator import validate_result
    validate_result(result)
    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _loose_ends_warnings(ends: list, pieces: list, non_contour_ids: set) -> list[str]:
    """Quello che resta aperto anche quando qualcosa si chiude (D111): gli
    estremi liberi della rete, e gli edge che uniscono due forme altrimenti
    staccate."""
    warnings = []
    if ends:
        first = ", ".join(f"({p[0]:.1f}, {p[1]:.1f}) a {d:.2f} mm dal nodo più vicino" for p, d in ends[:4])
        warnings.append(f"{len(ends)} estremi liberi non chiudono niente e restano in loose "
                        f"(i più vicini a un nodo: {first}).")
    joining = find_joining_edges(pieces, non_contour_ids)
    if joining:
        first = ", ".join(f"({e.start[0]:.1f}, {e.start[1]:.1f})→({e.end[0]:.1f}, {e.end[1]:.1f})"
                          for e in joining[:4])
        warnings.append(f"{len(joining)} edge uniscono due forme altrimenti staccate: esclusi dal "
                        f"contorno, ogni forma è letta per conto suo ({first}).")
    return warnings


def _crossing_warnings(points: list) -> list[str]:
    """Lati di contorno che si attraversano senza un nodo (D132): il disegno è
    rotto lì; la rete piana li noda per leggere le facce, e heal() lo dice."""
    if not points:
        return []
    first = ", ".join(f"({p[0]:.2f}, {p[1]:.2f})" for p in points[:4])
    return [f"{len(points)} incroci fra lati di contorno senza un nodo in comune ({first}): "
            f"lati accavallati nel disegno. Da correggere nel disegno: spezzare i lati "
            f"nell'incrocio, o accorciarli fino a farli toccare."]


