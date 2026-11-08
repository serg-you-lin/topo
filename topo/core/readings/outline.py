"""
topo/core/readings/outline.py
-----------------------------
La lettura dall'esterno di una rete riparata: `Network.outlines()`.

`faces()` ricostruisce la topologia dall'interno e trova il pezzo per
contenimento. `outlines()` legge il disegno dall'esterno: i gruppi sono gli
edge che si toccano entro `max_gap`, il contorno esterno di ognuno è la
faccia esterna della sua rete piana con gli incroci tagliati, e ogni contorno
esterno che non sta dentro un altro è un Cluster (D99). Quello che sta dentro,
chiuso o aperto, è suo per contenimento. È la lettura giusta per un disegno di
viste (3D proiettato, più viste su un foglio), dove il grafo di faces() è
ambiguo. Cosa sia un contorno — vista, pezzo, cornice — lo decide il
chiamante (D21).

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional


from ...model.cluster import Cluster
from ...model.contour import Contour
from ...model.result import Result
from ...model.role import ContourRole
from ..primitives.polygon_builder import curve_polygon, with_polygon
from ..primitives.segments import segment_endpoints
from ..topology.edge import Edge
from ..geometry.integrals import ring_area
from ..geometry.rings import ring_bbox, ring_contains
from ..geometry.shape import merge_runs
from ..topology.noding import GRAPH_EPSILON, edge_geometry, split_at_crossings
from ..topology.outer_face import OuterFace, outer_face
from ..base.hierarchy import assign_cluster_refs, sort_clusters
from ..base.curves import loose_curves
from ..topology.non_contour_edges import non_contour_pieces
from .touching import touching_groups
from .network import repair_edges
from .heal_steps import close_contour_jumps

if TYPE_CHECKING:
    from .network import Network


@dataclass
class OutlineReading:
    """Cosa outlines() ha deciso su un gruppo, pezzo per pezzo."""
    edges:          List[Edge]                               # del gruppo, come arrivano
    outer:          Optional[OuterFace]    = None            # None: nessun giro chiuso
    spurs:          List[Edge]             = field(default_factory=list)   # percorsi andata e ritorno
    outside:        List[Edge]             = field(default_factory=list)   # fuori dal contorno
    non_contour:    List[Edge]             = field(default_factory=list)   # criterio D49
    unclassified:   List[Edge]             = field(default_factory=list)
    nested_in:     Optional[int]          = None            # indice del gruppo che lo contiene (anche senza outer)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def read_network_outlines(net: Network) -> Result:
    """
    Un Cluster per ogni contorno esterno che non sta dentro un altro, col solo
    `outer`: nessun inner (D161). Tutto il resto — chiuso o aperto, dentro o
    fuori dal contorno, un gruppo intero dentro un altro — va in `loose`,
    dalla rete riparata (D203), con `cluster_ref` = il Cluster che tocca o che
    lo contiene; `None` se sta fuori da ognuno (D99, D137). Con la cornice nel
    disegno l'unico contorno esterno è la cornice: toglierla è del chiamante.
    """
    tol = net.tolerance
    result = Result(source_file=net.source_file, source_format=net.source_format, reading="outlines",
                    tolerance=net.tolerance, max_gap=net.max_gap, texts=list(net._texts))
    result.warnings += net.warnings
    if not net.is_valid:
        result.errors += net.errors
        result.is_valid = False
        return result
    readings = _read_groups(net.edges, tol, net.max_gap)
    result.loose += loose_curves(net.set_aside)
    clusters = {}
    for i, r in enumerate(readings):
        if r.outer is not None and r.nested_in is None:
            clusters[i] = _cluster(r, net.source_file, net.label)
    owned = []   # (curva, cluster che la contiene)
    for i, r in enumerate(readings):
        host = clusters.get(r.nested_in) if r.nested_in is not None else clusters.get(i)
        if host is None or r.outer is None:
            owned += [(f, host) for f in loose_curves(r.edges)]
            continue
        if r.nested_in is not None:
            # D161: un gruppo dentro un altro non è un suo inner, va in `loose`
            owned += [(f, host) for f in loose_curves(r.edges)]
            continue
        owned += [(f, host) for f in loose_curves(r.spurs + r.outside + r.non_contour + r.unclassified)]
    result.clusters = sort_clusters(list(clusters.values()))
    index = {id(c): k for k, c in enumerate(result.clusters)}
    for curve, host in owned:
        curve.cluster_ref = None if host is None else index[id(host)]
    result.loose += [f for f, _ in owned]
    # D137: chi non tocca nessun contorno ha il Cluster che lo contiene, se c'è
    # (un asse staccato dentro la vista, la cornice marcata dal chiamante)
    free = [c for c in result.loose if c.cluster_ref is None]
    assign_cluster_refs(free, result.clusters, tol)
    if not result.clusters:
        result.is_valid = False
        result.errors.append("Nessun gruppo con un contorno esterno chiuso.")
        return result
    close_contour_jumps(result, tol)
    from ...rules.validator import validate_result
    validate_result(result)
    return result


def read_outlines(edges: List[Edge], tolerance: float, max_gap: float) -> List[OutlineReading]:
    """
    Gli edge riparati come heal() (`network.repair_edges`), poi i pezzi a
    contatto (`touching_groups` a `max_gap`) letti uno per uno, e
    l'annidamento: un pezzo che sta dentro il contorno di un altro — col suo
    contorno, o senza contorno con tutti i suoi edge — porta in `nested_in`
    l'indice del più esterno che lo contiene.
    """
    return _read_groups(repair_edges(edges, tolerance, max_gap), tolerance, max(tolerance, max_gap))


def read_outline(edges: List[Edge], tolerance: float, max_gap: float) -> OutlineReading:
    """
    Un gruppo: gli edge riparati come heal() (`network.repair_edges`), la
    rete piana, la sua faccia esterna, poi il resto, che va tutto in `loose`
    (D161): fuori dal contorno, non-contorno (D49), non classificati.
    """
    return _read_group(repair_edges(edges, tolerance, max_gap), tolerance)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _read_groups(edges: List[Edge], tolerance: float, gap: float) -> List[OutlineReading]:
    """Edge già riparati: i gruppi a contatto entro `gap`, letti, e annidati."""
    readings = [_read_group(g.edges, tolerance) for g in touching_groups(edges, gap)]
    # il riquadro esatto di ogni ospite, allargato di GRAPH_EPSILON (ben oltre
    # il bordo di ring_contains e l'errore della spline): un punto fuori non
    # sta né dentro né sul bordo, e si salta l'avvolgimento sulle curve vere
    outers = [(j, r.outer.segments, ring_area(r.outer.segments), ring_bbox(r.outer.segments))
              for j, r in enumerate(readings) if r.outer is not None]
    e = GRAPH_EPSILON
    for i, r in enumerate(readings):
        # due gruppi distano più della soglia sulle curve vere (D200): un
        # punto del pezzo sta dentro un ospite solo se ci sta tutto il pezzo
        if r.outer is not None:
            point, area = segment_endpoints(r.outer.segments[0])[0], ring_area(r.outer.segments)
        else:
            point, area = r.edges[0].start, 0.0
        hosts = [(j, big_area) for j, ring, big_area, (x0, y0, x1, y1) in outers
                 if j != i and big_area > area and x0 - e <= point[0] <= x1 + e and y0 - e <= point[1] <= y1 + e
                 and ring_contains(ring, point)]
        if hosts:
            r.nested_in = max(hosts, key=lambda h: h[1])[0]
    return readings


def _read_group(edges: List[Edge], tolerance: float) -> OutlineReading:
    """Un gruppo di edge già riparati: la rete piana con gli incroci tagliati
    (D101), la faccia esterna, il resto classificato."""
    noded = split_at_crossings(edges, tolerance)
    pieces = noded.pieces
    face = outer_face(pieces, epsilon=GRAPH_EPSILON)

    reading = OutlineReading(edges=list(edges), outer=face)
    taken = set()
    if face is not None:
        taken = {id(e) for e in face.edges} | {id(e) for e in face.spurs}
        reading.spurs = list(face.spurs)
    rest = [e for e in pieces if id(e) not in taken] + (face.rest if face is not None else [])
    if face is not None:
        probe = curve_polygon(face).buffer(tolerance)
        reading.outside = [e for e in rest if not probe.contains(edge_geometry(e))]
        outside_ids = {id(e) for e in reading.outside}
        rest = [e for e in rest if id(e) not in outside_ids]
    # D161: dentro il contorno nessun inner, tutto il resto va in `loose`
    non_contour_ids = non_contour_pieces(noded, tolerance)
    reading.non_contour = [e for e in rest if id(e) in non_contour_ids]
    reading.unclassified = [e for e in rest if id(e) not in non_contour_ids]
    return reading


def _cluster(reading: OutlineReading, source_file: str, label: str) -> Cluster:
    face = reading.outer
    outer = _contour(face.segments, face.styles, curve_polygon(face), ContourRole.OUTER, None)
    return Cluster(outer=outer, source_file=source_file, label=label)


def _contour(segments, styles, polygon, role, parent) -> Contour:
    """Il poligono resta quello dei pezzi della rete piana; i segmenti sono
    ricomposti dove il taglio li aveva spezzati (`geometry.shape.merge_runs`)."""
    segments, styles = merge_runs(list(segments), list(styles))
    return with_polygon(Contour(role=role, segments=segments, styles=styles,
                                depth=0 if parent is None else 1, parent=parent), polygon)


