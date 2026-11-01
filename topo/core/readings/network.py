"""
topo/core/readings/network.py
-----------------------------
La riparazione comune a ogni lettura (D202): un Document diventa una rete di
edge riparati, una volta sola, con due numeri — `tolerance` per i nodi e
`max_gap` per i gap. Le letture (heal, island) partono da qui e non
riparano più per conto loro.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable, List, Optional

from ...model.document import Document
from ...model.role import is_structural_role
from ..base.cleanup import NEAR_FULL_ARC_MISSING, dangling_splines
from ..base.prepare import normalize, prepare
from ..geometry.measure import reach
from ..primitives.segments import segment_is_closed
from ..topology.edge import Edge
from ..topology.noding import GRAPH_EPSILON, NodedEdges, decide_nodes, split_at_crossings
from .heal_steps import free_ends


@dataclass
class Network:
    """Il disegno riparato: gli edge, quello messo da parte, cosa è stato fatto."""
    edges:       List[Edge] = field(default_factory=list)   # riparati, nodi decisi
    set_aside:   List[Edge] = field(default_factory=list)   # ruoli non strutturali (D30)
    warnings:    List[str] = field(default_factory=list)
    errors:      List[str] = field(default_factory=list)
    tolerance:   float = 0.0
    max_gap:     float = 0.0
    structural:  Callable[[str], bool] = is_structural_role
    source_file: str = ""
    label:       str = ""

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @cached_property
    def noded(self) -> NodedEdges:
        """La rete piana senza tagliare gli incroci (D132): gli incroci restano
        un dato, il taglio è della lettura che lo chiede."""
        return split_at_crossings(self.edges, self.tolerance, cut_crossings=False)

    @property
    def crossings(self) -> list:
        return self.noded.crossings

    @property
    def free_ends(self) -> list:
        return free_ends(self.noded.pieces, GRAPH_EPSILON)


def build_network(doc: Document, *, tolerance: Optional[float] = None,
                  max_gap: Optional[float] = None,
                  is_structural: Optional[Callable[[str], bool]] = None,
                  source_file: str = "", label: str = "") -> Network:
    """
    Ripara `doc` una volta per tutte le letture (D187, D202): ruoli non
    strutturali da parte, nodi decisi, pulizie di `normalize` con i gap fino a
    `max_gap` (default `tolerance`), tratti degeneri tolti.
    """
    tol = doc.node_tolerance(override=tolerance)
    gap = tol if max_gap is None else max(tol, max_gap)
    net = Network(tolerance=tol, max_gap=gap, structural=is_structural or is_structural_role,
                  source_file=source_file, label=label)
    if not doc.edges:
        net.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        return net
    prepared = prepare(doc.edges, net.structural)
    net.set_aside = prepared.labeled
    if not prepared.edges and not prepared.labeled:
        net.errors.append("Nessuna geometria trovata.")
        return net
    if prepared.labeled and is_structural is None:
        net.warnings.append(_LABELED_WITHOUT_PREDICATE.format(n=len(prepared.labeled)))

    # un gap largo quanto la soglia si chiude a ogni riferimento, non a
    # seconda dell'ultimo bit (D183)
    clean = normalize(prepared.edges, reach(gap), keep_junctions=True)
    for count, what in ((clean.merged_lines, "segmenti collineari sovrapposti fusi"),
                        (clean.merged_arcs, "archi co-circolari sovrapposti fusi"),
                        (clean.welded + prepared.welded, "LineSeg degeneri (sub-tolleranza) saldati")):
        if count:
            net.warnings.append(f"{count} {what} prima della ricerca loop.")
    if clean.full_arcs:
        net.warnings.append(f"{clean.full_arcs} archi quasi completi (gap entro tolleranza, mancano al "
                            f"più {math.degrees(NEAR_FULL_ARC_MISSING):.0f}°) chiusi in cerchio.")
    if clean.ambiguous:
        first = ", ".join(f"({p[0]:.2f}, {p[1]:.2f})" for p in clean.ambiguous[:4])
        net.warnings.append(f"{len(clean.ambiguous)} estremi liberi con due compagni alla stessa distanza "
                            f"(figura simmetrica): nessun gap chiuso lì, decide il disegno ({first}).")
    net.edges = _no_degenerate(clean.edges)
    if dangling_splines(net.edges):
        net.warnings.append(
            "SPLINE con endpoint non connesso trovata — "
            "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
            "Verificare manualmente la correttezza del file."
        )
    return net


def repair_edges(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]:
    """La stessa riparazione su edge sciolti, per chi legge senza un Document
    (experimental): nodi decisi, `normalize`, degeneri tolti."""
    noded, _ = decide_nodes(edges)
    return _no_degenerate(normalize(noded, reach(max(tolerance, max_gap)), keep_junctions=True).edges)


def _no_degenerate(edges: List[Edge]) -> List[Edge]:
    """Un tratto ridotto a un punto non è una curva (un cerchio sì)."""
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


_LABELED_WITHOUT_PREDICATE = (
    "{n} edge con un ruolo diverso da "
    "outer/inner/unknown, trattati come non strutturali di "
    "default (heal() chiamato senza is_structural=...): un "
    "ruolo come 'hole' non viene riconosciuto come contorno "
    "di pezzo e finisce in `loose`. Passa a heal() un "
    "is_structural che lo riconosca."
)
