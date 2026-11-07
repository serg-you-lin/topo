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
    Gli ArcSeg coi due capi liberi sullo stesso cerchio (`_same_circle`, D184):
    un buco fra un arco e il seguente entro `tolerance` E col suo angolo entro
    `max_missing_angle` si chiude (MAP.md D112, D218) — la tolleranza dice se è
    un gap, l'angolo se l'arco prosegue. Chiusi tutti i buchi è un CircleSeg;
    altrimenti gli archi uniti sono un ArcSeg solo, aperto sui buchi rimasti
    (un capo e l'altro dello stesso arco non sono mai un gap). Un arco solo ha
    un buco solo. `tolerance=math.inf` lascia solo l'angolo.
    Ritorna (edge, n_edge_rifatti).
    """
    graph = build_node_graph(edges)
    free = [k for k, e in enumerate(edges) if isinstance(e.segment, ArcSeg) and _both_ends_free(e, graph)]
    pairs = [(m, n) for m in range(len(free)) for n in range(m + 1, len(free))
             if _same_circle(edges[free[m]].segment, edges[free[n]].segment)]
    replaced, drop = {}, set()
    for members in connected_groups(len(free), pairs):
        for chain in _joined_runs([free[m] for m in members], edges, tolerance, max_missing_angle):
            members_k = [span[0] for span in chain if span is not None]
            first = min(members_k)
            replaced[first] = _joined_edge(edges[first], chain)
            drop.update(k for k in members_k if k != first)
    out = [replaced.get(k, e) for k, e in enumerate(edges) if k not in drop]
    return out, len(replaced)


def _joined_runs(group: List[int], edges: List[Edge], tolerance: float, max_missing_angle: float) -> list:
    """Le catene da rifare: [(indice, span)] per catena, in giro sul cerchio;
    span = (lo, sweep, lo_node, hi_node). Un giro intero è una catena con
    `None` in coda; una catena di un arco solo che non chiude il giro non si
    rifà. Archi che si sovrappongono non si giudicano (li fonde
    `merge_cocircular_overlaps`)."""
    spans = []
    for k in group:
        e, seg = edges[k], edges[k].segment
        start, end = segment_endpoints(seg)
        lo, lo_pt, hi_pt, lo_node, hi_node = ((seg.start_angle, start, end, e.start, e.end) if seg.ccw
                                              else (seg.end_angle, end, start, e.end, e.start))
        spans.append((k, (lo % (2 * math.pi), seg._sweep(), lo_pt, hi_pt, lo_node, hi_node)))
    spans.sort(key=lambda s: s[1][0])
    if math.fsum(s[1][1] for s in spans) > 2 * math.pi:
        return []
    joins = []
    for a, (_, (lo, sweep, _, hi_pt, _, _)) in enumerate(spans):
        nxt_lo, _, nxt_pt, _, _, _ = spans[(a + 1) % len(spans)][1]
        missing = (nxt_lo - (lo + sweep)) % (2 * math.pi)
        joins.append(missing <= max_missing_angle and math.dist(hi_pt, nxt_pt) <= tolerance)
    if all(joins):
        return [spans + [None]]
    # si parte dopo un buco che resta aperto: ogni catena è un tratto continuo
    start = joins.index(False) + 1
    order = spans[start:] + spans[:start]
    opened = joins[start:] + joins[:start]
    runs, cur = [], []
    for span, joined in zip(order, opened):
        cur.append(span)
        if not joined:
            runs.append(cur)
            cur = []
    return [r for r in runs if len(r) > 1]


def _joined_edge(edge: Edge, chain: list) -> Edge:
    """L'edge di una catena: un CircleSeg se chiude il giro (`None` in coda),
    altrimenti l'ArcSeg ccw dal primo capo all'ultimo, coi loro nodi."""
    seg = edge.segment
    if chain[-1] is None:
        circle = CircleSeg(center=seg.center, radius=seg.radius)
        node = node_point(segment_endpoints(circle)[0])
        return replace(edge, start=node, end=node, segment=circle)
    lo, _, _, _, lo_node, _ = chain[0][1]
    last_lo, last_sweep, _, _, _, hi_node = chain[-1][1]
    hi = lo + ((last_lo + last_sweep - lo) % (2 * math.pi))
    arc = ArcSeg(center=seg.center, radius=seg.radius, start_angle=lo, end_angle=hi, ccw=True)
    return replace(edge, start=lo_node, end=hi_node, segment=arc)


def _both_ends_free(edge: Edge, graph) -> bool:
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


