"""
topo/core/base/cleanup.py
-------------------------
Le pulizie di ogni lettura, una per funzione: ruoli non strutturali, archi quasi completi, gap fra estremi liberi, spline
penzolanti (D187). `prepare` e `normalize` le compongono; un chiamante con
un'altra ricetta le compone come gli serve.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable, List, Optional, Tuple


from ..geometry.measure import node_point
from ..primitives.segments import ArcSeg, CircleSeg, BSplineSeg, segment_endpoints
from ..topology.edge import Edge
from ..topology.graph import build_node_graph, connected_groups
from ...model.role import ContourRole, is_structural_role
from .normalizer import _same_circle
from .gap_solver import free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, ambiguous_gap_ends


def split_labeled(edges: List[Edge],
                  is_structural: Optional[Callable[[str], bool]] = None
                  ) -> Tuple[List[Edge], List[Edge]]:
    """
    Separa gli Edge con un ruolo già deciso e non strutturale (cornice,
    marcatura, un manifatturiero non riconosciuto senza predicato — D30):
    ritorna (restano nel grafo, etichettati). Senza `is_structural`, solo
    outer/inner sono strutturali.
    """
    structural = is_structural or is_structural_role
    labeled = [e for e in edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    if not labeled:
        return list(edges), []
    labeled_ids = {id(e) for e in labeled}
    return [e for e in edges if id(e) not in labeled_ids], labeled


NEAR_FULL_ARC_MISSING = math.radians(2.0)   # angolo mancante oltre il quale un arco non è un cerchio (D112)


def close_near_full_arcs(edges: List[Edge], tolerance: float,
                         max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]:
    """
    Gli ArcSeg coi due capi liberi sullo stesso cerchio (`_same_circle`, D184)
    diventano un CircleSeg solo se ogni buco fra un arco e il seguente è entro
    `tolerance` E il suo angolo entro `max_missing_angle` (MAP.md D112, D218):
    la tolleranza dice se il buco è un gap, l'angolo se l'arco è un cerchio.
    Un arco solo ha un buco solo; due archi due buchi, ognuno giudicato da sé.
    `tolerance=math.inf` lascia solo l'angolo. Ritorna (edge, n_cerchi_fatti).
    """
    graph = build_node_graph(edges)
    free = [k for k, e in enumerate(edges) if isinstance(e.segment, ArcSeg) and _both_ends_free(e, graph)]
    pairs = [(a, b) for i, a in enumerate(free) for b in free[i + 1:]
             if _same_circle(edges[a].segment, edges[b].segment)]
    replaced, drop = {}, set()
    for members in connected_groups(len(free), [(free.index(a), free.index(b)) for a, b in pairs]):
        group = [free[m] for m in members]
        if not _closes_circle([edges[k] for k in group], tolerance, max_missing_angle):
            continue
        first = min(group)
        seg = edges[first].segment
        circle = CircleSeg(center=seg.center, radius=seg.radius)
        node = node_point(segment_endpoints(circle)[0])
        replaced[first] = replace(edges[first], start=node, end=node, segment=circle)
        drop.update(k for k in group if k != first)
    out = [replaced.get(k, e) for k, e in enumerate(edges) if k not in drop]
    return out, len(replaced)


def _both_ends_free(edge: Edge, graph) -> bool:
    # un capo che tocca altra geometria non è libero: l'arco fa parte di un giro.
    # Capi fusi nello stesso nodo: il self-loop sta fra i degeneri, quindi il
    # nodo deve restare senza altri edge (la punta di uno spigolo non è un cerchio)
    if edge.start == edge.end:
        return graph.degree(edge.start) == 0
    return graph.degree(edge.start) == 1 and graph.degree(edge.end) == 1


def _closes_circle(arcs: List[Edge], tolerance: float, max_missing_angle: float) -> bool:
    """Gli archi, in giro sul cerchio, lasciano solo buchi entro `tolerance` e
    `max_missing_angle`, ognuno; due archi che si sovrappongono non chiudono
    (li fonde `merge_cocircular_overlaps`, non questa regola)."""
    spans = []
    for e in arcs:
        seg = e.segment
        start, end = segment_endpoints(seg)
        lo, lo_pt, hi_pt = ((seg.start_angle, start, end) if seg.ccw else (seg.end_angle, end, start))
        spans.append((lo % (2 * math.pi), seg._sweep(), lo_pt, hi_pt))
    spans.sort(key=lambda s: s[0])
    for k, (lo, sweep, _, hi_pt) in enumerate(spans):
        nxt_lo, _, nxt_pt, _ = spans[(k + 1) % len(spans)]
        missing = (nxt_lo - (lo + sweep)) % (2 * math.pi)
        if missing > max_missing_angle or math.dist(hi_pt, nxt_pt) > tolerance:
            return False
    return math.fsum(s[1] for s in spans) <= 2 * math.pi


def close_free_gaps(edges: List[Edge], tolerance: float) -> List[Edge]:
    """
    Chiude i gap fra estremi liberi entro `tolerance` col gap solver
    (estensione all'intersezione reale o linea di congiunzione), a coppie (D112).
    """
    graph = build_node_graph(edges)
    endpoints = free_endpoints_from_edges(edges, graph)
    if not endpoints:
        return list(edges)
    fixes = compute_gap_fixes(endpoints, tolerance, edges)
    if not fixes:
        return list(edges)
    return apply_gap_fixes(edges, fixes)


def ambiguous_free_ends(edges: List[Edge], tolerance: float) -> List[Tuple[float, float]]:
    """Gli estremi liberi che `close_free_gaps` lascia aperti: due punti
    più vicini a pari merito, nessuno scelto (D185)."""
    return ambiguous_gap_ends(free_endpoints_from_edges(edges, build_node_graph(edges)), tolerance, edges)


def dangling_splines(edges: List[Edge]) -> List[Edge]:
    """BSplineSeg aperte con almeno un estremo non collegato a nient'altro."""
    open_splines = [e for e in edges if isinstance(e.segment, BSplineSeg) and e.start != e.end]
    if not open_splines:
        return []
    graph = build_node_graph(edges)
    return [e for e in open_splines if graph.degree(e.start) < 2 or graph.degree(e.end) < 2]


