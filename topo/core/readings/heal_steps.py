"""
topo/core/readings/heal_steps.py
--------------------------------
I passi propri di heal(), uno per funzione: la scala che chiude i giri,
il fallback polygonize, i non-contorno, la gerarchia. Le basi comuni
stanno in `core/base` (D187).

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Set, Tuple

from shapely import STRtree
from shapely.geometry import Point

from ..topology.edge import Edge
from ..topology.graph import build_node_graph
from ..topology.non_contour_edges import non_contour_pieces
from ..topology.noding import split_at_crossings
from ...model.cluster import Cluster
from ...model.diagnostic import Diagnostic
from ...model.role import ContourRole, is_structural_role
from ..base.hierarchy import HierarchyBuilder
from ..geometry.measure import FLOAT_NOISE
from ..geometry.rings import ring_bridges


def find_non_contour_edges(edges: List[Edge], tolerance: float) -> Set[int]:
    """
    id(edge) degli Edge che non chiudono un contorno (catene fra due nodi di
    branching, e non sul bordo della faccia esterna della componente, D111,
    D131): quelli i cui pezzi della rete piana sono tutti non-contorno, lo
    stesso giudizio che fanno le letture (`non_contour_pieces`, D189).
    `tolerance`: due tagli più vicini sono un contatto solo.
    """
    noded = split_at_crossings(edges, tolerance, cut_crossings=False)
    excluded = non_contour_pieces(noded, tolerance)
    verdict: dict = {}
    for piece in noded.pieces:
        key = id(noded.parent_of(piece))
        verdict[key] = verdict.get(key, True) and id(piece) in excluded
    return {key for key, out in verdict.items() if out}


def find_joining_edges(edges: List[Edge], candidate_ids: Set[int]) -> List[Edge]:
    """
    Gli Edge fra `candidate_ids` (di solito i non-contorno) che uniscono due
    forme altrimenti staccate: tolti, i loro due estremi non sono più
    collegati. Fra due forme chiuse è il nodo ambiguo per eccellenza — un
    pezzo con una linea attaccata, o due pezzi? heal() li legge come due e
    lo dice in un warning (D111).
    """
    graph = build_node_graph(edges)
    joining = []
    for edge in edges:
        if id(edge) not in candidate_ids:
            continue
        start, goal = graph.canonical(edge.start), graph.canonical(edge.end)
        if start == goal:
            continue
        seen, todo = {start}, [start]
        while todo and goal not in seen:
            node = todo.pop()
            for other_edge, other in graph[node]:
                if other_edge is not edge and other not in seen:
                    seen.add(other)
                    todo.append(other)
        if goal not in seen:
            joining.append(edge)
    return joining


def free_ends(edges: List[Edge], epsilon: float = 0.0) -> List[Tuple[Tuple, float]]:
    """
    (estremo, distanza dal nodo più vicino) per ogni estremo che nessun altro
    edge tocca, dal più vicino a un nodo: un estremo a pochi mm da un vertice
    è un gap che la tolleranza non ha chiuso. `epsilon`: quello del grafo su
    cui i loop sono stati chiusi, perché un estremo fuso lì non è libero.
    """
    graph = build_node_graph(edges, epsilon=epsilon)
    open_nodes = graph.open_nodes()
    if not open_nodes:
        return []
    nodes = list(graph.nodes)
    tree = STRtree([Point(q) for q in nodes])
    ends = []
    for node in open_nodes:
        hit = tree.query_nearest(Point(node), exclusive=True, return_distance=True)
        ends.append((node, float(hit[1][0]) if len(hit[1]) else math.inf))
    return sorted(ends, key=lambda item: item[1])


def structural_loops(loops: List[list],
                     is_structural: Optional[Callable[[str], bool]] = None) -> List[list]:
    """
    I loop in cui ogni edge con ruolo deciso è strutturale: un solo edge non
    strutturale (engrave, frame, ...) declassa l'intero loop.
    """
    return [loop for loop in loops if all(may_be_contour(e, is_structural) for e, _ in loop)]


def may_be_contour(edge: Edge, is_structural: Optional[Callable[[str], bool]] = None) -> bool:
    """L'edge può essere un contorno: ruolo non deciso, o strutturale."""
    return edge.role == ContourRole.UNKNOWN or (is_structural or is_structural_role)(edge.role)


def build_hierarchy(curves: list, label: str = "", source_file: str = "",
                    is_structural: Optional[Callable[[str], bool]] = None
                    ) -> Tuple[List[Cluster], list]:
    """
    Albero di contenimento sui ClosedCurve: ogni radice è un Cluster
    (outer), i discendenti i suoi inners con `depth`/`parent`. Ritorna
    (cluster, loose): loose è ciò che non è finito in un cluster e non è
    strutturale.
    """
    builder = HierarchyBuilder(label=label, source_file=source_file, is_structural=is_structural)
    return builder.build(curves)


def close_contour_jumps(result, tolerance: float) -> None:
    """
    Ogni contorno consegnato chiude esatto (D206): un salto entro `tolerance`
    fra un segmento e il successivo diventa una retta nuova fra i due capi,
    con lo stile del segmento prima. Nessuna curva si sposta; il poligono
    contava già il salto come la sua corda. **Muta** `result` e lo dice in
    `notes`.
    """
    starts, widest = [], 0.0
    for cluster in result.clusters:
        for contour in [cluster.outer] + list(cluster.inners):
            bridges = ring_bridges(contour.segments, tolerance, FLOAT_NOISE)
            for k, line in reversed(bridges):
                contour.segments.insert(k + 1, line)
                if len(contour.styles) > k:
                    contour.styles.insert(k + 1, contour.styles[k])
                widest = max(widest, math.dist(line.start, line.end))
                starts.append(line.start)
    if starts:
        result.notes.append(Diagnostic(
            "gap-closed", f"{len(starts)} {'jump' if len(starts) == 1 else 'jumps'} in the contours closed "
                          f"with a new straight segment",
            points=starts, notes=[f"up to {widest:.3g} wide (D206, D209)"], level="note"))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

