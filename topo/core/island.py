"""
core/island.py
--------------
Secondo modo di leggere un Document, accanto a heal(): per isole.

heal() ricostruisce la topologia dall'interno (chi tocca chi, quali giri si
chiudono, come stanno uno dentro l'altro) e trova il pezzo per contenimento.
island() legge il disegno dall'esterno: i pezzi sono gli edge che si
toccano, il contorno esterno di ognuno è la faccia esterna della sua rete
piana, e ogni contorno esterno che non sta dentro un altro è un'isola (D99).
Quello che sta dentro un'isola, chiuso o aperto, è suo per contenimento. È
la lettura giusta per un disegno di viste (3D proiettato, più viste su un
foglio), dove il grafo di heal è ambiguo.

Stesso contratto in uscita: un Result con un Cluster per isola.
Cosa sia un'isola — vista, pezzo, cornice — lo decide il chiamante (D21).

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from shapely.ops import unary_union

from ..model.cluster import Cluster
from ..model.contour import Contour
from ..model.document import Document
from ..model.curve import OpenCurve
from ..model.result import Result
from ..model.role import ContourRole, is_structural_role
from .primitives.polygon_builder import with_polygon
from .primitives.segments import segment_is_closed
from .topology.edge import Edge
from .topology.graph import build_node_graph
from .geometry.integrals import ring_area
from .geometry.shape import merge_runs
from .topology.noding import GRAPH_EPSILON, NODE_DECIMALS, edge_geometry, renode, split_at_crossings
from .topology.non_contour_edges import NonContourEdgeDetector
from .topology.outer_face import OuterFace, outer_face
from .healing.hierarchy import assign_cluster_refs, sort_clusters
from .healing.normalizer import chain_runs
from .healing.steps import loops_to_curves
from .healing.islands import spatial_islands
from .healing.gap_solver import (
    free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, local_gap_fixes, MoveEndpoint,
)
from .healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
    refit_tessellations,
)


@dataclass
class IslandReading:
    """Cosa island() ha deciso su un'isola, pezzo per pezzo."""
    edges:          List[Edge]                               # dell'isola, come arrivano
    outer:          Optional[OuterFace]    = None            # None: nessun giro chiuso
    spurs:          List[Edge]             = field(default_factory=list)   # percorsi andata e ritorno
    outside:        List[Edge]             = field(default_factory=list)   # fuori dal contorno
    non_contour:    List[Edge]             = field(default_factory=list)   # criterio D49
    unclassified:   List[Edge]             = field(default_factory=list)
    nested_in:     Optional[int]          = None            # indice dell'isola che la contiene (anche senza outer)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def island(doc: Document, *, max_gap: float,
           tolerance: Optional[float] = None,
           is_structural: Optional[Callable[[str], bool]] = None) -> Result:
    """
    Legge `doc` per isole. Un Cluster per ogni contorno esterno che non
    sta dentro un altro, col solo `outer`: island() non costruisce inner
    (D161). Tutto il resto — chiuso o aperto, dentro o fuori dal contorno,
    un'isola intera dentro un'altra — va in `loose`, intatto, con
    `cluster_ref` = l'isola che tocca o che lo contiene; `None` se sta fuori
    da ogni isola (D99, D137). Cosa sia è del consumer. Con la cornice nel
    disegno l'unico contorno esterno è la cornice: toglierla è del chiamante.

    max_gap:    due edge più vicini di così si toccano; gap chiusi fra
                estremi liberi, mai spostando un estremo più di così (mm).
                Obbligatorio (D98).
    tolerance:  come heal() — se None, doc.source_meta['tolerance'].
    is_structural: come heal() (D30): un Edge con un ruolo già deciso e non
                strutturale (cornice, cartiglio, ...) resta fuori dalla
                lettura e va in `loose` col suo ruolo. Senza, solo outer/inner
                sono strutturali.
    """
    if not isinstance(doc, Document):
        raise TypeError(
            "topo.island() richiede un Document da topo_dxf.load_dxf(); "
            f"ricevuto {type(doc).__name__}"
        )
    tol = doc.node_tolerance(tolerance)
    structural = is_structural or is_structural_role
    labeled = [e for e in doc.edges if e.role != ContourRole.UNKNOWN and not structural(e.role)]
    labeled_ids = {id(e) for e in labeled}
    edges = [e for e in doc.edges if id(e) not in labeled_ids]
    readings = read_islands(edges, tol, max_gap=max_gap)

    result = Result(source_file=doc.source_path, texts=list(doc.texts))
    result.loose += _open(labeled)
    clusters = {}
    for i, r in enumerate(readings):
        if r.outer is not None and r.nested_in is None:
            clusters[i] = _cluster(r, doc.source_path, tol)
    owned = []   # (curva, cluster che la contiene)
    for i, r in enumerate(readings):
        host = clusters.get(r.nested_in) if r.nested_in is not None else clusters.get(i)
        if host is None or r.outer is None:
            owned += [(f, host) for f in _pieces(r.edges)]
            continue
        if r.nested_in is not None:
            # D161: un'isola dentro un'altra non è un suo inner, va in `loose`
            owned += [(f, host) for f in _pieces(r.edges)]
            continue
        owned += [(f, host) for f in _pieces(r.spurs + r.outside + r.non_contour + r.unclassified)]
    result.clusters = sort_clusters(list(clusters.values()))
    index = {id(c): k for k, c in enumerate(result.clusters)}
    for curve, host in owned:
        curve.cluster_ref = None if host is None else index[id(host)]
    result.loose += [f for f, _ in owned]
    # D137: chi non tocca nessuna isola ha l'isola che lo contiene, se c'è
    # (un asse staccato dentro la vista, la cornice marcata dal chiamante)
    free = [c for c in result.loose if c.cluster_ref is None]
    assign_cluster_refs(free, result.clusters, tol)
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessuna isola con un contorno esterno chiuso.")
    return result


def read_islands(edges: List[Edge], tolerance: float, max_gap: float) -> List[IslandReading]:
    """
    I pezzi a contatto (`spatial_islands` a `max_gap`) + `read_island` per
    ognuno, e l'annidamento: un pezzo che sta dentro il contorno di un altro
    — col suo contorno, o senza contorno con tutti i suoi edge — porta in
    `nested_in` l'indice del più esterno che lo contiene.
    """
    readings = [read_island(isl.edges, tolerance, max_gap=max_gap)
                for isl in spatial_islands(edges, max(tolerance, max_gap))]
    outers = [(j, r.outer.polygon.buffer(tolerance), ring_area(r.outer.segments))
              for j, r in enumerate(readings) if r.outer is not None]
    for i, r in enumerate(readings):
        if r.outer is not None:
            small, area = r.outer.polygon, ring_area(r.outer.segments)
        else:
            small, area = unary_union([edge_geometry(e) for e in r.edges]), 0.0
        hosts = [(j, big_area) for j, probe, big_area in outers
                 if j != i and big_area > area and probe.contains(small)]
        if hosts:
            r.nested_in = max(hosts, key=lambda h: h[1])[0]
    return readings


def read_island(edges: List[Edge], tolerance: float, max_gap: float) -> IslandReading:
    """
    Un'isola: normalizza (nodi dagli estremi reali, tassellature rifittate,
    merge/weld di heal, gap fino a `max_gap`), rende la rete piana, ne
    percorre la faccia esterna, poi classifica il resto, che va tutto in
    `loose` (D161): fuori dal contorno, non-contorno (D49), non classificati.
    """
    normalized = _normalize(edges, tolerance, max_gap)
    noded = split_at_crossings(normalized, tolerance)
    pieces = noded.pieces
    face = outer_face(pieces, epsilon=GRAPH_EPSILON)

    reading = IslandReading(edges=list(edges), outer=face)
    taken = set()
    if face is not None:
        taken = {id(e) for e in face.edges} | {id(e) for e in face.spurs}
        reading.spurs = list(face.spurs)
    rest = [e for e in pieces if id(e) not in taken] + (face.rest if face is not None else [])
    if face is not None:
        probe = face.polygon.buffer(tolerance)
        reading.outside = [e for e in rest if not probe.contains(edge_geometry(e))]
        outside_ids = {id(e) for e in reading.outside}
        rest = [e for e in rest if id(e) not in outside_ids]
    # D161: dentro il contorno nessun inner, tutto il resto va in `loose`
    full_graph = build_node_graph(pieces, epsilon=GRAPH_EPSILON)
    non_contour_ids = NonContourEdgeDetector(tolerance).detect(full_graph, pieces)
    reading.non_contour = [e for e in rest if id(e) in non_contour_ids]
    reading.unclassified = [e for e in rest if id(e) not in non_contour_ids]
    return reading


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _normalize(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]:
    """Stessi passi di heal, ma sulla griglia fine della rete piana: prima i
    nodi dagli estremi reali (renode), poi tassellature, merge, weld e gap —
    così la saldatura resta valida anche dopo lo spezzamento."""
    edges = refit_tessellations(renode(edges), node_decimals=NODE_DECIMALS)
    edges = weld_degenerate_linesegs(merge_cocircular_overlaps(merge_collinear_overlaps(edges)))
    gap = max(tolerance, max_gap)
    graph = build_node_graph(edges)
    fixes = compute_gap_fixes(free_endpoints_from_edges(edges, graph), gap, pairwise=False)
    fixes = _drop_redundant_meets(fixes, graph)
    fixes = local_gap_fixes(fixes, gap)
    if fixes:
        edges = apply_gap_fixes(edges, fixes)
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _drop_redundant_meets(fixes: list, graph) -> list:
    """Scarta un fix "incontro" (due `MoveEndpoint` sullo stesso punto, la
    retta/arco di ognuno prolungato fino all'intersezione con l'altro)
    quando i due estremi di partenza sono già nella stessa componente
    connessa del grafo: non è un gap da chiudere, un giro li collega già
    altrove senza bisogno di questi due — saldarli comunque apre un secondo
    percorso parallelo spurio (sliver) accanto al contorno che si chiude già
    da solo (stessa famiglia di D100/D101, un passo prima: nel gap-fix,
    invece che nel noding). Un fix fra componenti diverse resta: lì è un
    gap vero, l'unico modo di collegarli."""
    by_point: dict = {}
    for fix in fixes:
        if isinstance(fix, MoveEndpoint):
            by_point.setdefault(fix.new_pt, []).append(fix)
    component_of: dict = {}
    for i, component in enumerate(graph.connected_components()):
        for node in component:
            component_of[node] = i
    drop_ids = set()
    for pair in by_point.values():
        if len(pair) != 2:
            continue
        fa, fb = pair
        node_a = graph.canonical(fa.ref.start if fa.role == "start" else fa.ref.end)
        node_b = graph.canonical(fb.ref.start if fb.role == "start" else fb.ref.end)
        if component_of.get(node_a) == component_of.get(node_b):
            drop_ids.update(id(f) for f in pair)
    return [f for f in fixes if id(f) not in drop_ids]


def _cluster(reading: IslandReading, source_file: str, tolerance: float) -> Cluster:
    face = reading.outer
    outer = _contour(face.segments, face.styles, face.polygon, ContourRole.OUTER, None)
    return Cluster(outer=outer, source_file=source_file)


def _contour(segments, styles, polygon, role, parent) -> Contour:
    """Il poligono resta quello dei pezzi della rete piana; i segmenti sono
    ricomposti dove il taglio li aveva spezzati (`geometry.shape.merge_runs`)."""
    segments, styles = merge_runs(list(segments), list(styles))
    return with_polygon(Contour(role=role, segments=segments, styles=styles,
                                depth=0 if parent is None else 1, parent=parent), polygon)


def _open(edges: List[Edge]) -> list:
    return [OpenCurve(role=e.role, segments=[e.segment], styles=[e.style]) for e in edges]


def _pieces(edges: List[Edge]) -> list:
    """Le curve di `loose` di un'isola (D162): un pezzo che chiude da sé —
    un segmento chiuso, o una catena in cui ogni nodo ha grado 2 — è un
    ClosedCurve, perché non c'è niente da scegliere; il resto un OpenCurve
    per edge, come `_open`."""
    single = [e for e in edges if segment_is_closed(e.segment)]
    rest = [e for e in edges if not segment_is_closed(e.segment)]
    runs = chain_runs(rest)
    rings = [[(e, False)] for e in single] + [path for path, closed in runs if closed]
    ringed = {id(e) for ring in rings for e, _ in ring}
    return loops_to_curves(rings) + _open([e for e in rest if id(e) not in ringed])

