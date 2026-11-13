# topo/core/topology/parity.py

"""
parity.py
---------
I contorni di una rete piana per parità: le facce si colorano dentro/fuori
in modo che ogni lato separi due colori diversi.

Teorema: le facce di un grafo piano ammettono questa colorazione, con ogni
lato fra due colori diversi, se e solo se ogni nodo ha grado pari; e allora
è unica, fissato fuori l'esterno. Ogni lato è contorno, ognuno compare una
volta sola fra i giri delle facce *fuori*.

Dove un nodo ha grado dispari la rete non ammette colorazione: si tolgono
i lati che non possono essere contorno, e poi il meno possibile.
  1. un capo libero o un ponte ha la stessa faccia dai due lati: via;
  2. dei lati rimasti, l'insieme che rende pari ogni nodo togliendo prima
     il meno possibile della sagoma (i lati sul bordo della faccia esterna
     del loro componente, con l'esterno da un lato solo), poi la lunghezza
     totale minima: il T-join di peso minimo sul grafo (`matching.min_t_join`),
     coi due criteri in un peso intero esatto (multipli di FLOAT_NOISE).

Puro: solo Edge, grafo e primitive, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .edge import Edge
from .graph import Graph, build_node_graph
from .loop_finder import segments_from_loop
from .matching import min_t_join
from .noding import GRAPH_EPSILON, edge_geometry
from .outer_face import face_walks, outer_face_passes, simple_rings
from ..geometry.integrals import ring_moments
from ..geometry.measure import FLOAT_NOISE, segment_length
from ..geometry.rings import ring_bbox, ring_contains


@dataclass
class ParityRings:
    """I giri dei contorni, e cosa la lettura ha tolto per arrivarci."""
    loops:     List[list]                                  # [(pezzo, al contrario)] antiorari
    dropped:   Set[int] = field(default_factory=set)       # id dei pezzi che non sono contorno
    conflicts: List[tuple] = field(default_factory=list)   # nodi dove la colorazione non torna
    rim_used:  bool = False                                # il T-join toglie anche sagoma
    joining:   Set[int] = field(default_factory=set)       # id dei ponti fra due parti chiuse


def parity_rings(pieces: List[Edge]) -> ParityRings:
    """
    I giri delle facce *fuori* della rete piana `pieces` (split_at_crossings,
    incroci tagliati), dopo aver tolto i lati che rendono dispari un nodo
    (vedi il modulo). Nessuna scelta dipende dall'ordine dei pezzi.
    """
    graph = build_node_graph(pieces, sliver=GRAPH_EPSILON)
    pruned = graph.pruned()
    joining = pruned.bridges()
    kept = _without_bridges(pruned)
    drop, rim_used = _t_join(kept)
    kept = kept.without(drop)
    on_graph = {id(e) for conn in kept.nodes.values() for e, _ in conn}
    on_graph |= {id(e) for e in kept.degenerate_loops}
    loops, conflicts = _outside_rings(kept)
    return ParityRings(loops=loops, dropped={id(p) for p in pieces} - on_graph,
                       conflicts=conflicts, rim_used=rim_used, joining=joining)


def _without_bridges(graph: Graph) -> Graph:
    while True:
        cut = graph.bridges()
        if not cut:
            return graph
        graph = graph.without(cut).pruned()


def _t_join(graph: Graph) -> Tuple[Set[int], bool]:
    """(id dei lati del T-join sui nodi dispari di `graph`, se toglie sagoma).
    Il peso di un lato mette prima la sua lunghezza se sta sul bordo
    esterno, poi la lunghezza: la sagoma si tocca solo dove nessun insieme
    di soli lati interni rende pari i nodi, e il meno possibile."""
    odd = {n for n, conn in graph.nodes.items() if len(conn) % 2}
    if not odd:
        return set(), False
    pieces = {id(e): e for conn in graph.nodes.values() for e, _ in conn}
    on_rim: Set[int] = set()
    for component in graph.connected_components():
        on_rim |= {k for k, passes in outer_face_passes(graph, component, len(pieces)).items()
                   if passes == 1}
    units = {k: round(segment_length(p.segment) / FLOAT_NOISE) for k, p in pieces.items()}
    # più di quanto possa pesare la lunghezza di qualunque accoppiamento
    scale = len(odd) * (sum(units.values()) + 1)
    sides = []
    for k, p in pieces.items():
        a, b = sorted((graph.canonical(p.start), graph.canonical(p.end)))
        weight = (scale if k in on_rim else 0) * units[k] + units[k]
        # i pareggi li decide la geometria: i capi, il peso, il punto a metà
        mid = edge_geometry(p).interpolate(0.5, normalized=True)
        sides.append(((a, b, weight, (mid.x, mid.y)), k))
    sides.sort()
    nodes = sorted({n for (a, b, _, _), _ in sides for n in (a, b)})
    index = {n: i for i, n in enumerate(nodes)}
    chosen, _ = min_t_join(len(nodes), [(index[a], index[b], w) for (a, b, w, _), _ in sides],
                           [index[n] for n in odd])
    drop = {sides[i][1] for i in chosen}
    return drop, bool(drop & on_rim)


def _outside_rings(graph: Graph) -> Tuple[List[list], List[tuple]]:
    """I giri semplici delle facce fuori, antiorari, ognuno una volta; e i
    nodi dove due facce vicine hanno avuto lo stesso colore."""
    walks = face_walks(graph)
    side: Dict[tuple, int] = {}
    for w, (walk, _) in enumerate(walks):
        for e, frm, _ in walk:
            side[(id(e), frm)] = w
    # colore relativo all'esterno del proprio componente: ogni lato cambia colore
    colour: Dict[int, int] = {w: 0 for w, (_, outer) in enumerate(walks) if outer}
    queue = list(colour)
    conflicts: List[tuple] = []
    while queue:
        w = queue.pop()
        for e, frm, to in walks[w][0]:
            other = side.get((id(e), to))
            if other is None:
                continue
            if other in colour:
                if colour[other] == colour[w]:
                    conflicts.append(frm)
            else:
                colour[other] = colour[w] ^ 1
                queue.append(other)

    rings = {w: [_ccw(graph, r) for r in simple_rings(walk)] for w, (walk, _) in enumerate(walks)}
    components = graph.connected_components()
    component_of = {n: k for k, comp in enumerate(components) for n in comp}
    # ogni componente (e ogni giro chiuso da solo) è dentro i giri fuori degli
    # altri un numero di volte: la parità è il colore della sua faccia esterna
    fences: List[Tuple[object, list, tuple]] = []
    for w, (walk, _) in enumerate(walks):
        if colour.get(w, 0) == 0:
            for loop in rings[w]:
                segments = segments_from_loop(loop)
                fences.append((component_of[walk[0][1]], segments, ring_bbox(segments)))
    for e in graph.degenerate_loops:
        fences.append((("loop", id(e)), [e.segment], ring_bbox([e.segment])))

    def base_colour(key, point) -> int:
        inside = 0
        for owner, segments, (x0, y0, x1, y1) in fences:
            if owner != key and x0 <= point[0] <= x1 and y0 <= point[1] <= y1 \
                    and ring_contains(segments, point):
                inside ^= 1
        return inside

    base = {k: base_colour(k, min(comp)) for k, comp in enumerate(components)}
    loops, seen = [], set()
    for w, (walk, _) in enumerate(walks):
        if colour.get(w, 0) ^ base[component_of[walk[0][1]]]:
            continue
        for loop in rings[w]:
            key = frozenset(id(e) for e, _ in loop)
            if key not in seen:
                seen.add(key)
                loops.append(loop)
    loops += [[(e, False)] for e in graph.degenerate_loops]
    return loops, sorted(set(conflicts))


def _ccw(graph: Graph, ring: list) -> list:
    loop = [(e, graph.canonical(e.start) != frm) for e, frm, _ in ring]
    if ring_moments(segments_from_loop(loop)).area < 0:
        loop = [(e, not rev) for e, rev in reversed(loop)]
    return loop
