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


from shapely import STRtree
from shapely.geometry import Point

from ..geometry.measure import SAME_POINT, node_point
from ..geometry.regions import nearest_point, translation_onto
from ..primitives.segments import (ArcSeg, CircleSeg, BSplineSeg, LineSeg, DEFAULT_TOLERANCE,
                                   segment_endpoints, segment_is_closed)
from ..topology.noding import edge_geometry
from ..topology.edge import Edge
from ..topology.graph import build_node_graph, connected_groups
from ...model.role import ContourRole, is_structural_role
from .normalizer import _same_circle, merge_cocircular_overlaps
from .gap_solver import (free_endpoints_from_edges, compute_gap_fixes, apply_gap_fixes, ambiguous_gap_ends, near_gaps,
                         tied_facing_ends)


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
NEAR_FULL_ARC_HINT = math.radians(8.0)      # fin qui heal() avvisa che manca poco; un filetto (~90°) mai (D227)


def close_near_full_arcs(edges: List[Edge], tolerance: float,
                         max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> Tuple[List[Edge], int]:
    """
    Gli ArcSeg coi due capi liberi sullo stesso cerchio (`_same_circle`, D184):
    un buco fra un arco e il seguente entro `tolerance` E col suo angolo entro
    `max_missing_angle` si chiude (MAP.md D112, D218) — la tolleranza dice se è
    un gap, l'angolo se l'arco prosegue. Chiusi tutti i buchi è un CircleSeg;
    altrimenti gli archi uniti sono un ArcSeg solo, aperto sui buchi rimasti
    (un capo e l'altro dello stesso arco non sono mai un gap). Un arco solo ha
    un buco solo. `tolerance=math.inf` lascia solo l'angolo. Prima fonde gli
    archi dello stesso cerchio che si toccano (`merge_cocircular_overlaps`):
    due archi uniti in un capo hanno un capo legato ciascuno, e chi la chiama
    da sé non deve saperlo (D227).
    Ritorna (edge, n_edge_rifatti).
    """
    edges = merge_cocircular_overlaps(edges)
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


def open_near_full_arcs(edges: List[Edge], tolerance: float,
                        max_missing_angle: float = NEAR_FULL_ARC_MISSING) -> List[Tuple[Edge, float, float]]:
    """
    Gli ArcSeg coi due capi liberi che `close_near_full_arcs` lascia aperti
    solo per l'angolo: la corda del buco sta in `tolerance`, l'angolo mancante
    supera `max_missing_angle` ma non `NEAR_FULL_ARC_HINT` — oltre, l'arco è
    aperto di proposito (un filetto). Ritorna (edge, angolo mancante, corda) —
    ciò che l'avviso dice al chiamante (D227).
    """
    graph = build_node_graph(edges)
    found = []
    for e in edges:
        if not isinstance(e.segment, ArcSeg) or not _both_ends_free(e, graph):
            continue
        start, end = segment_endpoints(e.segment)
        missing, chord = 2 * math.pi - e.segment._sweep(), math.dist(start, end)
        if max_missing_angle < missing <= NEAR_FULL_ARC_HINT and chord <= tolerance:
            found.append((e, missing, chord))
    return found


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


def close_free_gaps(edges: List[Edge], tolerance: float, closed: Optional[list] = None) -> List[Edge]:
    """
    Chiude i gap fra estremi liberi entro `tolerance` col gap solver
    (estensione all'intersezione reale o linea di congiunzione), a coppie (D112).
    `closed`, se dato, riceve (estremo, distanza) di ogni gap chiuso.
    """
    graph = build_node_graph(edges)
    endpoints = free_endpoints_from_edges(edges, graph)
    if not endpoints:
        return list(edges)
    fixes = compute_gap_fixes(endpoints, tolerance, edges, closed)
    if not fixes:
        return list(edges)
    return apply_gap_fixes(edges, fixes)


def join_tied_facing_ends(edges: List[Edge], gap: float, joined: Optional[list] = None) -> List[Edge]:
    """
    Due estremi già legati che si guardano lungo il proprio prolungamento,
    entro `gap`, si uniscono con un tratto nuovo: il lato disegnato in due
    pezzi con un buco in mezzo (D272). Nessuna curva si sposta. `joined`, se
    dato, riceve (estremo, distanza) di ogni unione.
    """
    out = list(edges)
    for a, b, d in tied_facing_ends(edges, build_node_graph(edges), gap):
        out.append(Edge(role=ContourRole.UNKNOWN, start=getattr(a.ref, a.role), end=getattr(b.ref, b.role),
                        segment=LineSeg(start=tuple(a.pt), end=tuple(b.pt))))
        if joined is not None:
            joined.append((tuple(a.pt), d))
    return out


def move_onto_targets(edges: List[Edge], gap: float, moved: Optional[list] = None) -> List[Edge]:
    """
    Una curva aperta coi due capi liberi (nessun nodo la lega ad altro: spostarla
    non strappa niente) ed entro `gap` da due curve diverse (i suoi target),
    almeno uno staccato, si sposta intera della traslazione unica che li porta
    tutti e due sui target: il raccordo disegnato qualche millesimo di fianco
    al lato (D271). Non si sposta verso un arco o cerchio
    con un altro concentrico (un filetto), né una retta che passa per il
    centro del cerchio target (un asse). `moved`, se dato, riceve (punto,
    spostamento) di ogni curva spostata.
    """
    edges = list(edges)
    geoms = [edge_geometry(e) for e in edges]
    tree = STRtree(geoms)
    rounds = [e.segment for e in edges if isinstance(e.segment, (ArcSeg, CircleSeg))]
    graph = build_node_graph(edges)
    out = list(edges)
    for k, edge in enumerate(edges):
        seg = edge.segment
        if segment_is_closed(seg) or edge.start == edge.end                 or graph.degree(edge.start) != 1 or graph.degree(edge.end) != 1:
            continue
        ends = segment_endpoints(seg)
        found = [_target(p, k, edges, geoms, tree, gap) for p in ends]
        if None in found or found[0][1] == found[1][1] or max(d for d, _ in found) <= SAME_POINT:
            continue
        if any(d > SAME_POINT and not _may_land(seg, edges[j].segment, rounds, gap) for d, j in found):
            continue
        t = translation_onto(ends[0], ends[1], edges[found[0][1]].segment, edges[found[1][1]].segment)
        if t is None or math.hypot(*t) > gap:
            continue
        shifted = seg.translated(*t)
        a, b = segment_endpoints(shifted)
        out[k] = replace(edge, segment=shifted, start=node_point(a), end=node_point(b))
        if moved is not None:
            moved.append((ends[0], math.hypot(*t)))
    return out


def _target(p, k: int, edges: List[Edge], geoms: list, tree, gap: float):
    """(distanza, indice) della curva più vicina a `p` entro `gap`, fuori da `k`."""
    best = None
    for j in tree.query(Point(p), predicate="dwithin", distance=gap + 2 * DEFAULT_TOLERANCE):
        j = int(j)
        if j == k:
            continue
        d = math.dist(p, nearest_point([edges[j].segment], p))
        if d <= gap and (best is None or d < best[0]):
            best = (d, j)
    return best


def _may_land(seg, target, rounds: list, gap: float) -> bool:
    """Un capo staccato può cadere su `target`: no se è un arco o cerchio con
    un altro concentrico (filetto), no se `seg` è una retta per il suo centro (asse)."""
    if not isinstance(target, (ArcSeg, CircleSeg)):
        return True
    if any(r is not target and math.dist(r.center, target.center) <= gap for r in rounds):
        return False
    if isinstance(seg, LineSeg):
        (ax, ay), (bx, by) = seg.start, seg.end
        length = math.hypot(bx - ax, by - ay)
        cx, cy = target.center
        if length > 0 and abs((bx - ax) * (ay - cy) - (by - ay) * (ax - cx)) / length <= gap:
            return False
    return True


def near_free_gaps(edges: List[Edge], tolerance: float, reach_to: float) -> list:
    """I gap fra estremi liberi che `close_free_gaps` chiuderebbe entro
    `reach_to` ma non entro `tolerance`: (estremo, compagno, distanza) (D227)."""
    return near_gaps(free_endpoints_from_edges(edges, build_node_graph(edges)), tolerance, reach_to, edges)


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


def self_crossings(edges: List[Edge]) -> List[Tuple[float, float]]:
    """I punti dove una spline incrocia se stessa (le altre primitive non possono)."""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    found = []
    for e in edges:
        if not isinstance(e.segment, BSplineSeg):
            continue
        line = LineString(e.segment.discretize())
        if line.is_simple:
            continue
        # la curva nodata su se stessa: a un incrocio arrivano 4 pezzi
        ends = {}
        for piece in unary_union(line).geoms:
            for p in (piece.coords[0], piece.coords[-1]):
                ends[p] = ends.get(p, 0) + 1
        found += [p for p, n in ends.items() if n >= 4]
    return found


def closed_touches(edges: List[Edge], tolerance: float) -> List[Tuple[float, float]]:
    """I nodi di una curva chiusa che stanno su un'altra curva chiusa."""
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    from ..primitives.segments import segment_is_closed
    closed = [e for e in edges if segment_is_closed(e.segment)]
    if len(closed) < 2:
        return []
    lines = [LineString(e.segment.discretize()) for e in closed]
    tree = STRtree(lines)
    found = []
    for i, e in enumerate(closed):
        node = Point(e.start)
        if any(j != i and lines[j].distance(node) <= tolerance for j in tree.query(node.buffer(tolerance))):
            found.append(tuple(e.start))
    return found
