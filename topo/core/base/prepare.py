"""
topo/core/base/prepare.py
-------------------------
Le basi comuni di ogni lettura (D187): `faces()`, `outlines()` e qualunque
ricetta un chiamante si componga partono da qui, con le stesse regole. Una
lettura sceglie solo come cerca il contorno; tutto quello che viene prima è
geometria del disegno e si decide una volta, in un posto.

    prepare    — ruoli non strutturali messi da parte, nodi decisi
                 una volta (`decide_nodes`)
    normalize  — doppioni collineari e cocircolari, tratti degeneri, archi
                 quasi completi, gap: le stesse funzioni per tutti; le
                 differenze fra letture sono parametri con un nome, ognuno
                 con la sua decisione in MAP

Puro: solo Edge e primitive, nessun formato.
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
    """Gli edge pronti per una lettura, e quello che `prepare` ha messo da parte."""
    edges:   List[Edge] = field(default_factory=list)   # strutturali, nodi decisi
    labeled: List[Edge] = field(default_factory=list)   # ruolo deciso e non strutturale (D30)
    welded:  int = 0                                    # più corti di GRAPH_EPSILON, saldati (D56)


def prepare(edges: List[Edge],
            is_structural: Optional[Callable[[str], bool]] = None) -> Prepared:
    """Ruoli non strutturali da parte, poi i nodi decisi una volta per tutte
    le letture (D187). Una coordinata non finita non arriva fin qui: la
    primitiva la rifiuta (D190)."""
    kept, labeled = split_labeled(list(edges), is_structural)
    noded, welded = decide_nodes(kept)
    return Prepared(edges=noded, labeled=labeled, welded=welded)


@dataclass
class Normalized:
    """Gli edge normalizzati e quanti ne ha toccati ogni passo."""
    edges:          List[Edge] = field(default_factory=list)
    merged_lines:   int = 0
    merged_arcs:    int = 0
    full_arcs:      int = 0
    ambiguous:      list = field(default_factory=list)   # estremi senza compagno scelto (D185)
    gaps:           list = field(default_factory=list)   # (estremo, distanza) dei gap chiusi
    moved:          list = field(default_factory=list)   # (punto, spostamento) delle curve spostate (D271)
    tied:           list = field(default_factory=list)   # (estremo, distanza) dei capi legati uniti (D272)
    bent:           list = field(default_factory=list)   # (capo, distanza) degli archi ridisegnati per un capo (D273)


def normalize(edges: List[Edge], gap: float, *, keep_junctions: bool) -> Normalized:
    """
    Le pulizie di ogni lettura: le stesse funzioni, nello stesso ordine, per
    tutti (D187, D189). `gap`: la distanza fino a cui due estremi liberi si
    chiudono, già comprensiva del margine (`geometry.measure.reach`).

    Curve scritte a punti rifittate (D60 riaperto), doppioni collineari e
    cocircolari fusi, archi quasi completi chiusi,
    gap a coppie: ogni estremo chiude al più un gap, col compagno più vicino;
    a pari merito nessuno (D112, D185).

    keep_junctions: due pezzi collineari che si toccano solo in un innesto
                    non si fondono (D110). Resta finché heal() non noda i
                    contatti come outlines().
    """
    out = Normalized()
    edges = refit_tessellations(edges)
    # una curva del file che è un arco, un'ellisse o un cerchio diventa quello (D296)
    edges = refit_native_curves(edges)
    merged = merge_collinear_overlaps(edges, keep_junctions=keep_junctions)
    out.merged_lines, edges = len(edges) - len(merged), merged
    merged = merge_cocircular_overlaps(edges)
    out.merged_arcs, edges = len(edges) - len(merged), merged
    edges, out.full_arcs = close_near_full_arcs(edges, gap)
    # una curva coi capi di fianco ai suoi target si sposta su di loro prima
    # che un gap li leghi altrove (D271); i nodi si ridecidono dai punti nuovi
    edges = move_onto_targets(edges, gap, out.moved)
    if out.moved:
        edges, _ = decide_nodes(edges)
    # un arco inchiodato ai capi passa per il capo libero di fianco alla sua pancia (D273)
    edges = bend_arcs_through_free_ends(edges, gap, out.bent)
    out.ambiguous = ambiguous_free_ends(edges, gap)
    closed = close_free_gaps(edges, gap, out.gaps)
    # un lato in due pezzi coi capi già legati: il buco lungo la sua retta (D272)
    closed = join_tied_facing_ends(closed, gap, out.tied)
    # chiudere un gap allunga le due metà una verso l'altra: si sovrappongono
    # sul tratto del gap, e quel tratto resta doppio nella rete (G15)
    merged = merge_collinear_overlaps(closed, keep_junctions=keep_junctions)
    out.merged_lines += len(closed) - len(merged)
    # solo ora l'anello di un foro scritto a punti è chiuso: diventa il suo cerchio (D236)
    out.edges = refit_circle_rings(merged)
    return out
