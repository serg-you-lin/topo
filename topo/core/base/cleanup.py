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


from ..geometry.measure import round_point
from ..primitives.segments import ArcSeg, CircleSeg, BSplineSeg, segment_endpoints
from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ...model.role import ContourRole, is_structural_role
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
    Un ArcSeg coi due capi liberi diventa CircleSeg (stesso centro e raggio)
    solo se il gap fra i capi è entro `tolerance` E l'angolo mancante è entro
    `max_missing_angle` (MAP.md D112): la tolleranza dice se il buco è un gap,
    l'angolo se l'arco è un cerchio. `tolerance=math.inf` lascia solo l'angolo.
    Ritorna (edge, n_archi_chiusi).
    """
    graph = build_node_graph(edges)
    closed, out = 0, []
    for edge in edges:
        seg = edge.segment
        if isinstance(seg, ArcSeg) and _is_near_full_arc(edge, graph, tolerance, max_missing_angle):
            node = round_point(segment_endpoints(CircleSeg(center=seg.center, radius=seg.radius))[0])
            edge = replace(edge, start=node, end=node,
                           segment=CircleSeg(center=seg.center, radius=seg.radius))
            closed += 1
        out.append(edge)
    return out, closed


def _is_near_full_arc(edge: Edge, graph, tolerance: float, max_missing_angle: float) -> bool:
    seg = edge.segment
    if 2 * math.pi - seg._sweep() > max_missing_angle:
        return False
    start, end = segment_endpoints(seg)
    if math.dist(start, end) > tolerance:
        return False
    # un capo che tocca altra geometria non è libero: l'arco fa parte di un giro.
    # Capi fusi nello stesso nodo: il self-loop sta fra i degeneri, quindi il
    # nodo deve restare senza altri edge (la punta di uno spigolo non è un cerchio)
    if edge.start == edge.end:
        return graph.degree(edge.start) == 0
    return graph.degree(edge.start) == 1 and graph.degree(edge.end) == 1


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


