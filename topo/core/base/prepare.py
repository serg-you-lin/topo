"""
topo/core/base/prepare.py
-------------------------
Le basi comuni di ogni lettura (D187): `heal()`, `island()` e qualunque
ricetta un chiamante si componga partono da qui, con le stesse regole. Una
lettura sceglie solo come cerca il contorno; tutto quello che viene prima è
geometria del disegno e si decide una volta, in un posto.

    prepare    — coordinate non finite e ruoli non strutturali messi da parte,
                 nodi decisi una volta (`decide_nodes`)
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
from .normalizer import (merge_cocircular_overlaps, merge_collinear_overlaps, refit_tessellations, weld_degenerate_linesegs)
from .cleanup import (ambiguous_free_ends, close_free_gaps, close_near_full_arcs, split_labeled, split_non_finite)


@dataclass
class Prepared:
    """Gli edge pronti per una lettura, e quello che `prepare` ha messo da parte."""
    edges:   List[Edge] = field(default_factory=list)   # finiti, strutturali, nodi decisi
    labeled: List[Edge] = field(default_factory=list)   # ruolo deciso e non strutturale (D30)
    broken:  List[Edge] = field(default_factory=list)   # una coordinata non finita
    welded:  int = 0                                    # più corti di GRAPH_EPSILON, saldati (D56)


def prepare(edges: List[Edge],
            is_structural: Optional[Callable[[str], bool]] = None) -> Prepared:
    """Coordinate non finite e ruoli non strutturali da parte, poi i nodi
    decisi una volta per tutte le letture (D187)."""
    finite, broken = split_non_finite(list(edges))
    kept, labeled = split_labeled(finite, is_structural)
    noded, welded = decide_nodes(kept)
    return Prepared(edges=noded, labeled=labeled, broken=broken, welded=welded)


@dataclass
class Normalized:
    """Gli edge normalizzati e quanti ne ha toccati ogni passo."""
    edges:          List[Edge] = field(default_factory=list)
    merged_lines:   int = 0
    merged_arcs:    int = 0
    welded:         int = 0
    full_arcs:      int = 0
    ambiguous:      list = field(default_factory=list)   # estremi senza compagno scelto (D185)


def normalize(edges: List[Edge], gap: float, *, keep_junctions: bool) -> Normalized:
    """
    Le pulizie di ogni lettura: le stesse funzioni, nello stesso ordine, per
    tutti (D187, D189). `gap`: la distanza fino a cui due estremi liberi si
    chiudono, già comprensiva del margine (`geometry.measure.reach`).

    Curve scritte a punti rifittate (D60 riaperto), doppioni collineari e
    cocircolari fusi, tratti degeneri saldati, archi quasi completi chiusi,
    gap a coppie: ogni estremo chiude al più un gap, col compagno più vicino;
    a pari merito nessuno (D112, D185).

    keep_junctions: due pezzi collineari che si toccano solo in un innesto
                    non si fondono (D110). Resta finché heal() non noda i
                    contatti come island().
    """
    out = Normalized()
    edges = refit_tessellations(edges)
    merged = merge_collinear_overlaps(edges, keep_junctions=keep_junctions)
    out.merged_lines, edges = len(edges) - len(merged), merged
    merged = merge_cocircular_overlaps(edges)
    out.merged_arcs, edges = len(edges) - len(merged), merged
    merged = weld_degenerate_linesegs(edges)
    out.welded, edges = len(edges) - len(merged), merged
    edges, out.full_arcs = close_near_full_arcs(edges, gap)
    out.ambiguous = ambiguous_free_ends(edges, gap)
    out.edges = close_free_gaps(edges, gap)
    return out
