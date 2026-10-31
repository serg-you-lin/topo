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

import math
from typing import Callable, Optional

from ...model.document import Document
from ..geometry.measure import reach as threshold
from ...model.curve import ClosedCurve
from ...model.result import Result
from ...model.role import is_structural_role
from ..base.curves import loops_to_curves, loose_curves
from ..topology.noding import GRAPH_EPSILON, split_at_crossings
from ..topology.outer_face import face_loops
from ..topology.non_contour_edges import non_contour_pieces
from ..base.hierarchy import assign_cluster_refs
from ..base.prepare import normalize, prepare
from .heal_steps import (
    find_joining_edges, free_ends, structural_loops, build_hierarchy,
)
from ..base.cleanup import NEAR_FULL_ARC_MISSING, dangling_splines


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
    tol = doc.node_tolerance(override=tolerance)
    # un gap largo quanto la tolleranza si chiude a ogni riferimento, non a
    # seconda dell'ultimo bit (D183): i passi confrontano con `reach`
    reach = threshold(tol)
    structural = is_structural or is_structural_role

    result = Result(source_file=source_file)
    result.texts = list(doc.texts)
    if not doc.edges:
        result.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        result.is_valid = False
        return result

    # le basi comuni a ogni lettura (D187)
    prepared = prepare(doc.edges, structural)
    if not prepared.edges and not prepared.labeled:
        result.errors.append("Nessuna geometria trovata.")
        result.is_valid = False
        return result
    labeled = prepared.labeled
    if labeled and is_structural is None:
        result.warnings.append(_LABELED_WITHOUT_PREDICATE.format(n=len(labeled)))

    clean = normalize(prepared.edges, reach, keep_junctions=True)
    for count, what in ((clean.merged_lines, "segmenti collineari sovrapposti fusi"),
                        (clean.merged_arcs, "archi co-circolari sovrapposti fusi"),
                        (clean.welded + prepared.welded, "LineSeg degeneri (sub-tolleranza) saldati")):
        if count:
            result.warnings.append(f"{count} {what} prima della ricerca loop.")
    if clean.full_arcs:
        result.warnings.append(f"{clean.full_arcs} archi quasi completi (gap entro tolleranza, mancano al "
                               f"più {math.degrees(NEAR_FULL_ARC_MISSING):.0f}°) chiusi in cerchio.")
    if clean.ambiguous:
        first = ", ".join(f"({p[0]:.2f}, {p[1]:.2f})" for p in clean.ambiguous[:4])
        result.warnings.append(f"{len(clean.ambiguous)} estremi liberi con due compagni alla stessa distanza "
                               f"(figura simmetrica): nessun gap chiuso lì, decide il disegno ({first}).")
    edges = clean.edges
    if dangling_splines(edges):
        result.warnings.append(
            "SPLINE con endpoint non connesso trovata — "
            "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
            "Verificare manualmente la correttezza del file."
        )

    # la rete piana, i non-contorno su di lei, i giri delle facce limitate:
    # la stessa rete, lo stesso giudizio e lo stesso cammino di island() (D189)
    noded = split_at_crossings(edges, tol, cut_crossings=False)
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
        result.warnings += _loose_ends_warnings(noded.pieces, non_contour)
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

_LABELED_WITHOUT_PREDICATE = (
    "{n} edge con un ruolo diverso da "
    "outer/inner/unknown, trattati come non strutturali di "
    "default (heal() chiamato senza is_structural=...): un "
    "ruolo come 'hole' non viene riconosciuto come contorno "
    "di pezzo e finisce in `loose`. Passa a heal() un "
    "is_structural che lo riconosca."
)


def _loose_ends_warnings(pieces: list, non_contour_ids: set) -> list[str]:
    """Quello che resta aperto anche quando qualcosa si chiude (D111): gli
    estremi liberi della rete, e gli edge che uniscono due forme altrimenti
    staccate."""
    warnings = []
    ends = free_ends(pieces, GRAPH_EPSILON)
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


