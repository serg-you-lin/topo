"""
topo/core/base/gap_solver.py
----------------------------
Calcolo geometrico puro della chiusura dei gap tra segmenti.

Zero dipendenze da ezdxf, PDF, SVG o qualsiasi formato.
Lavora su coordinate Python e restituisce istruzioni di correzione (GapFix).

Il chiamante (adapter) è responsabile di:
    - estrarre GapEndpoint dal formato sorgente
    - applicare GapFix al documento nativo

Tipi pubblici:
    GapEndpoint   — endpoint libero con ref opaco al formato sorgente
    MoveEndpoint  — istruzione: sposta endpoint di ref a new_pt
    AddSegment    — istruzione: aggiungi segmento tra pt_a e pt_b
    GapFix        — Union[MoveEndpoint, AddSegment]

Funzioni pubbliche:
    compute_gap_fixes — dato un insieme di endpoint liberi, calcola i fix
    ambiguous_gap_ends — gli estremi che non scelgono fra compagni a pari merito
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

from shapely import STRtree
from shapely.geometry import Point

from ..geometry.measure import FLOAT_NOISE, round_point
from ..geometry.intersections import (_distance, _line_intersection, _circle_line_intersections, _circle_circle_intersections, _closest_to)
from ..geometry.intersections import intersections
from ..geometry.regions import nearest_point
from ..primitives.segments import DEFAULT_TOLERANCE, LineSeg, ArcSeg, BSplineSeg, segment_endpoints
from ..topology.noding import GRAPH_EPSILON, edge_geometry
from ..topology.edge import Edge
from ...model.role import ContourRole

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Tipi di input
# ---------------------------------------------------------------------------

@dataclass
class GapEndpoint:
    """
    Endpoint libero nel grafo topologico.

    Attributi:
        pt   : coordinate (x, y) dell'endpoint
        ref  : riferimento opaco all'entità sorgente — l'adapter sa cos'è
        role : 'start' | 'end'
        kind : tipo geometrico — 'line' | 'arc' | 'spline' | altro
               usato dal solver per scegliere la strategia di fix
        meta : dati aggiuntivi che il solver può usare per il calcolo
               per LINE: {'start': pt, 'end': pt}
               per ARC:  {'cx': float, 'cy': float, 'radius': float}
               per SPLINE: {} (nessun dato utile al solver)
    """
    pt:   Point2D
    ref:  Any
    role: str
    kind: str
    meta: dict


# ---------------------------------------------------------------------------
# Tipi di output (GapFix)
# ---------------------------------------------------------------------------

@dataclass
class MoveEndpoint:
    """
    Istruzione: sposta l'endpoint role di ref al punto new_pt.
    L'adapter traduce ref → entità nativa e applica lo spostamento.
    """
    ref:    Any
    role:   str
    new_pt: Point2D


@dataclass
class AddSegment:
    """
    Istruzione: aggiungi un segmento retto tra pt_a e pt_b.
    Usato come fallback quando non si trova un'intersezione geometrica.
    """
    pt_a: Point2D
    pt_b: Point2D
    # i nodi già decisi degli estremi che collega (D187): il segmento si
    # attacca lì, non alla cella di griglia del punto reale
    node_a: Optional[Point2D] = None
    node_b: Optional[Point2D] = None


GapFix = Union[MoveEndpoint, AddSegment]


# ---------------------------------------------------------------------------
# Solver geometrico — logica per coppia di kind
# ---------------------------------------------------------------------------

def _solve_line_line(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    s_a = ep_a.meta['start']
    e_a = ep_a.meta['end']
    s_b = ep_b.meta['start']
    e_b = ep_b.meta['end']
    ix = _line_intersection(s_a, e_a, s_b, e_b)
    return _meet_or_bridge(ix, ep_a, ep_b)


def _solve_arc_line(
    ep_arc:  GapEndpoint,
    ep_line: GapEndpoint,
) -> List[GapFix]:
    cx     = ep_arc.meta['cx']
    cy     = ep_arc.meta['cy']
    radius = ep_arc.meta['radius']
    s_l    = ep_line.meta['start']
    e_l    = ep_line.meta['end']
    candidates = _circle_line_intersections(cx, cy, radius, s_l, e_l)
    ix = _closest_to(candidates, ep_arc.pt, ep_line.pt)
    return _meet_or_bridge(ix, ep_arc, ep_line)


def _solve_arc_arc(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    candidates = _circle_circle_intersections(
        ep_a.meta['cx'], ep_a.meta['cy'], ep_a.meta['radius'],
        ep_b.meta['cx'], ep_b.meta['cy'], ep_b.meta['radius'],
    )
    ix = _closest_to(candidates, ep_a.pt, ep_b.pt)
    return _meet_or_bridge(ix, ep_a, ep_b)


def _solve_spline_any(
    ep_a: GapEndpoint,
    ep_b: GapEndpoint,
) -> List[GapFix]:
    # Le spline non hanno una geometria analitica semplice da intersecare —
    # fallback diretto al segmento di chiusura.
    return [_bridge(ep_a, ep_b)]


# Registry: (kind_a, kind_b) → solver
# Le coppie sono normalizzate in ordine canonico in compute_gap_fixes.
_SOLVERS = {
    ('line',   'line'):   _solve_line_line,
    ('arc',    'line'):   lambda a, b: _solve_arc_line(a, b),
    ('line',   'arc'):    lambda a, b: _solve_arc_line(b, a),   # riordina
    ('arc',    'arc'):    _solve_arc_arc,
    ('spline', 'line'):   lambda a, b: _solve_spline_any(a, b),
    ('line',   'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'arc'):    lambda a, b: _solve_spline_any(a, b),
    ('arc',    'spline'): lambda a, b: _solve_spline_any(a, b),
    ('spline', 'spline'): lambda a, b: _solve_spline_any(a, b),
}


def _bridge(ep_a: GapEndpoint, ep_b: GapEndpoint) -> AddSegment:
    """Il segmento fra due estremi, attaccato ai loro nodi."""
    return AddSegment(pt_a=ep_a.pt, pt_b=ep_b.pt, node_a=_node(ep_a), node_b=_node(ep_b))


def _node(ep: GapEndpoint) -> Optional[Point2D]:
    if isinstance(ep.ref, Edge):
        return ep.ref.start if ep.role == "start" else ep.ref.end
    return None


def _get_solver(kind_a: str, kind_b: str):
    solver = _SOLVERS.get((kind_a, kind_b))
    if solver is None:
        # kind sconosciuto → fallback AddSegment
        return lambda a, b: [_bridge(a, b)]
    return solver


# ---------------------------------------------------------------------------
# Funzione pubblica
# ---------------------------------------------------------------------------

def compute_gap_fixes(endpoints: List[GapEndpoint], tolerance: float,
                      edges: Sequence[Edge] = ()) -> List[GapFix]:
    """
    Calcola i GapFix degli estremi liberi entro `tolerance`, una regola sola
    per ogni lettura (D112, D189). Ogni estremo si chiude sul punto più vicino
    della rete: un altro estremo libero (i due si incontrano o si uniscono con
    un segmento, e nessuno dei due chiude altro), oppure il punto dove la sua
    curva, proseguita, incontra un altro edge di `edges` — a metà di una curva
    o su un suo nodo (mai con un ponte di traverso). I due capi dello stesso
    edge non sono mai un gap (`close_near_full_arcs`). Un estremo coi due
    punti più vicini a pari merito non sceglie: in una figura simmetrica
    nessuna regola dà lo stesso compagno in ogni riferimento (D185).
    """
    candidates = _candidates(endpoints, tolerance, edges)
    ambiguous = _ambiguous_from(candidates, endpoints)
    fixes: List[GapFix] = []
    taken: set = set()
    for d, _, i, target in sorted(candidates, key=lambda c: (c[0], c[1])):
        if i in ambiguous or i in taken:
            continue
        ep = endpoints[i]
        if target[0] == "end":
            j = target[1]
            if j in ambiguous or j in taken:
                continue
            taken.update((i, j))
            other = endpoints[j]
            fixes.extend(_within_reach(_get_solver(ep.kind, other.kind)(ep, other), ep, other, tolerance))
        else:
            taken.add(i)
            fixes.extend(_onto_curve(ep, target[1], target[2], target[3], tolerance))
    return fixes


def _candidates(endpoints: List[GapEndpoint], tolerance: float, edges: Sequence[Edge]) -> list:
    """(distanza, chiave d'ordine, i, bersaglio) per ogni estremo `i`: ("end", j) un
    altro estremo libero; ("curve", edge, incontro, nodo) dove la curva di `i`,
    proseguita, incontra un altro edge (`_continuation`). Un incontro su un
    estremo libero è già la coppia di estremi; uno entro GRAPH_EPSILON lo
    collega il noding (D180), non è un gap."""
    out = [(d, key, i, ("end", j)) for d, key, i, j in _gap_pairs(endpoints, tolerance)]
    out += [(d, key, j, ("end", i)) for d, key, i, j in _gap_pairs(endpoints, tolerance)]
    if not edges:
        return out
    free = {getattr(ep.ref, ep.role) for ep in endpoints if isinstance(ep.ref, Edge)}
    geoms = [edge_geometry(e) for e in edges]
    tree = STRtree(geoms)
    for i, ep in enumerate(endpoints):
        ahead = _continuation(ep, tolerance)
        if ahead is None:
            continue
        for k in tree.query(Point(ep.pt), predicate="dwithin", distance=tolerance + 2 * DEFAULT_TOLERANCE):
            edge = edges[int(k)]
            if edge is ep.ref:
                continue
            hits = [q for q in intersections(ahead, edge.segment) if _distance(q, ep.pt) > GRAPH_EPSILON]
            if not hits:
                continue
            meet = min(hits, key=lambda q: _distance(q, ep.pt))
            d = _distance(ep.pt, meet)
            if d > tolerance:
                continue
            node = next((n for n, q in zip((edge.start, edge.end), segment_endpoints(edge.segment))
                         if _distance(meet, q) <= GRAPH_EPSILON), None)
            if node is not None and node in free:
                continue
            out.append((d, (tuple(ep.pt), tuple(meet)), i, ("curve", edge, meet, node)))
    return out


def _continuation(ep: GapEndpoint, reach: float):
    """La curva dell'estremo `ep` proseguita oltre il suo capo per `reach`: una
    retta col suo verso, un arco sul suo cerchio, una spline o un'ellisse con la
    tangente al capo. Un capo si chiude su una curva solo dove questa la
    incontra: mai con un ponte di traverso, che il disegno non suggerisce (D189).
    None se non ha una direzione (tratto nullo)."""
    seg = ep.ref.segment if isinstance(ep.ref, Edge) else None
    if isinstance(seg, ArcSeg) and seg.radius > 0:
        step = min(reach / seg.radius, math.pi / 2)
        sign = 1.0 if seg.ccw else -1.0
        if ep.role == "end":
            return ArcSeg(center=seg.center, radius=seg.radius, start_angle=seg.end_angle,
                          end_angle=seg.end_angle + sign * step, ccw=seg.ccw)
        return ArcSeg(center=seg.center, radius=seg.radius, start_angle=seg.start_angle,
                      end_angle=seg.start_angle - sign * step, ccw=not seg.ccw)
    if isinstance(seg, LineSeg):
        far = seg.start if ep.role == "end" else seg.end
    elif seg is not None:
        pts = seg.discretize(tolerance=DEFAULT_TOLERANCE)
        if len(pts) < 2:
            return None
        far = pts[-2] if ep.role == "end" else pts[1]
    else:
        return None
    length = _distance(far, ep.pt)
    if length <= 0:
        return None
    ux, uy = (ep.pt[0] - far[0]) / length, (ep.pt[1] - far[1]) / length
    return LineSeg(start=tuple(ep.pt), end=(ep.pt[0] + ux * reach, ep.pt[1] + uy * reach))


def _ambiguous_from(candidates: list, endpoints: List[GapEndpoint]) -> set:
    """Gli estremi i cui due punti più vicini (distinti oltre GRAPH_EPSILON) distano
    uguale entro FLOAT_NOISE (D185)."""
    by_end: dict = {}
    for d, _, i, target in candidates:
        by_end.setdefault(i, []).append((d, target))
    out = set()
    for i, items in by_end.items():
        items.sort(key=lambda t: t[0])
        places = []
        for d, target in items:
            point = target[2] if target[0] == "curve" else endpoints[target[1]].pt
            if all(_distance(point, q) > GRAPH_EPSILON for _, q in places):
                places.append((d, point))
            if len(places) == 2:
                break
        if len(places) == 2 and places[1][0] - places[0][0] <= FLOAT_NOISE:
            out.add(i)
    return out


def _onto_curve(ep: GapEndpoint, edge: Edge, meet: Point2D, node, reach: float) -> List[GapFix]:
    """L'estremo `ep` portato dove la sua curva, proseguita, incontra `edge`:
    una retta o un arco si allungano fino a lì; una spline o un'ellisse, che
    non si allungano, prendono il tratto di tangente."""
    if ep.kind in ("line", "arc"):
        return [MoveEndpoint(ref=ep.ref, role=ep.role, new_pt=meet)]
    return [AddSegment(pt_a=ep.pt, pt_b=meet, node_a=_node(ep), node_b=node)]


def ambiguous_gap_ends(endpoints: List[GapEndpoint], tolerance: float,
                       edges: Sequence[Edge] = ()) -> List[Point2D]:
    """Gli estremi che `compute_gap_fixes` lascia aperti perché i loro due punti
    più vicini entro `tolerance` sono a pari merito (D185)."""
    return [endpoints[k].pt for k in sorted(_ambiguous_from(_candidates(endpoints, tolerance, edges), endpoints))]


def _gap_pairs(endpoints: List[GapEndpoint], tolerance: float) -> list:
    """(d, coordinate ordinate, i, j) per ogni coppia di estremi di edge diversi entro `tolerance`."""
    pairs = []
    for i, ep_a in enumerate(endpoints):
        for j in range(i + 1, len(endpoints)):
            ep_b = endpoints[j]
            if ep_a.ref is ep_b.ref:
                continue
            d = _distance(ep_a.pt, ep_b.pt)
            if d <= tolerance:
                # a parità di distanza decidono le coordinate, mai l'ordine del file
                pairs.append((d, tuple(sorted((tuple(ep_a.pt), tuple(ep_b.pt)))), i, j))
    return pairs


def _within_reach(fixes: List[GapFix], ep_a: GapEndpoint, ep_b: GapEndpoint,
                  reach: float) -> List[GapFix]:
    """Un incontro che sposta un estremo più di `reach` non chiude il gap: due
    rette quasi parallele si incontrano lontanissimo, e se lo fanno lo decide
    l'ultimo bit dei double (D60, G6e). Al suo posto il segmento fra i due."""
    origin = {(id(ep.ref), ep.role): ep.pt for ep in (ep_a, ep_b)}
    for fix in fixes:
        if isinstance(fix, MoveEndpoint) and _distance(origin[(id(fix.ref), fix.role)],
                                                       fix.new_pt) > reach:
            return [_bridge(ep_a, ep_b)]
    return fixes


# ---------------------------------------------------------------------------
# Ponte Edge <-> GapFix — geometria pura, zero formato sorgente
# ---------------------------------------------------------------------------

_KIND_BY_SEGMENT = {LineSeg: "line", ArcSeg: "arc", BSplineSeg: "spline"}


def _endpoint_meta(segment) -> dict:
    """Dati che il solver usa per calcolare l'intersezione, per tipo di segmento."""
    if isinstance(segment, LineSeg):
        return {"start": segment.start, "end": segment.end}
    if isinstance(segment, ArcSeg):
        return {"cx": segment.center[0], "cy": segment.center[1], "radius": segment.radius}
    return {}


def _meet_or_bridge(ix: Optional[Point2D], ep_a: GapEndpoint, ep_b: GapEndpoint) -> List[GapFix]:
    """Se le due geometrie si incontrano in `ix`, porta lì entrambi gli estremi;
    altrimenti chiudi il gap con un segmento."""
    if ix is None:
        return [_bridge(ep_a, ep_b)]
    return [
        MoveEndpoint(ref=ep_a.ref, role=ep_a.role, new_pt=ix),
        MoveEndpoint(ref=ep_b.ref, role=ep_b.role, new_pt=ix),
    ]


def free_endpoints_from_edges(edges: List[Edge], graph) -> List[GapEndpoint]:
    """
    Estrae gli endpoint liberi (grado < 2 nel grafo) dagli Edge.

    Sostituisce DxfAdapter.extract_free_endpoints: lavora su geometria pura,
    il `ref` di ogni GapEndpoint è l'Edge stesso.
    Considera solo LINE / ARC / SPLINE — i loop degeneri (CIRCLE, SPLINE chiusa)
    non hanno endpoint liberi per definizione.
    """
    return _gap_endpoints(edges, lambda node: graph.degree(node) < 2)


def _gap_endpoints(edges: List[Edge], keep: Callable[[Point2D], bool]) -> List[GapEndpoint]:
    """GapEndpoint per gli estremi di LINE / ARC / SPLINE il cui nodo (arrotondato)
    soddisfa `keep`. `pt` resta la coordinata reale non arrotondata: il solver
    ne ha bisogno per calcolare l'intersezione."""
    out: List[GapEndpoint] = []
    for edge in edges:
        if edge.start == edge.end:
            continue
        kind = _KIND_BY_SEGMENT.get(type(edge.segment))
        if kind is None:
            continue
        meta = _endpoint_meta(edge.segment)
        raw_start, raw_end = segment_endpoints(edge.segment)
        if keep(edge.start):
            out.append(GapEndpoint(pt=raw_start, ref=edge, role="start", kind=kind, meta=meta))
        if keep(edge.end):
            out.append(GapEndpoint(pt=raw_end, ref=edge, role="end", kind=kind, meta=meta))
    return out


def _moved_segment(segment, role: str, new_pt: Point2D):
    """Nuovo segmento con l'endpoint `role` spostato su `new_pt`. None se non gestito."""
    if isinstance(segment, LineSeg):
        if role == "start":
            return LineSeg(start=(new_pt[0], new_pt[1]), end=segment.end)
        return LineSeg(start=segment.start, end=(new_pt[0], new_pt[1]))

    if isinstance(segment, ArcSeg):
        angle = math.atan2(new_pt[1] - segment.center[1], new_pt[0] - segment.center[0])
        if role == "start":
            return ArcSeg(center=segment.center, radius=segment.radius,
                          start_angle=angle, end_angle=segment.end_angle, ccw=segment.ccw)
        return ArcSeg(center=segment.center, radius=segment.radius,
                      start_angle=segment.start_angle, end_angle=angle, ccw=segment.ccw)

    return None


def apply_gap_fixes(edges: List[Edge], fixes: List[GapFix]) -> List[Edge]:
    """
    Applica i GapFix restituendo una NUOVA lista di Edge — `edges` non viene mutata.

    Sostituisce DxfAdapter.apply_gap_fixes: invece di mutare entità ezdxf,
    ricostruisce gli Edge coinvolti (MoveEndpoint) e ne aggiunge di nuovi
    (AddSegment, sempre una LINE di congiunzione).
    """
    replacements: dict = {}   # id(edge_originale) -> Edge aggiornato
    added: List[Edge] = []

    for fix in fixes:
        if isinstance(fix, MoveEndpoint):
            base = replacements.get(id(fix.ref), fix.ref)
            if not isinstance(base, Edge):
                continue
            # Il segmento conserva il punto reale (il poligono si costruisce da
            # qui); solo il nodo topologico dell'Edge viene arrotondato.
            new_seg = _moved_segment(base.segment, fix.role, fix.new_pt)
            if new_seg is None:
                continue
            node = round_point(fix.new_pt)
            replacements[id(fix.ref)] = Edge(
                role=base.role,
                start=node if fix.role == "start" else base.start,
                end=node if fix.role == "end" else base.end,
                segment=new_seg,
            )
        elif isinstance(fix, AddSegment):
            a = (float(fix.pt_a[0]), float(fix.pt_a[1]))
            b = (float(fix.pt_b[0]), float(fix.pt_b[1]))
            node_a = fix.node_a if fix.node_a is not None else round_point(a)
            node_b = fix.node_b if fix.node_b is not None else round_point(b)
            if node_a == node_b:
                continue
            added.append(Edge(
                role=ContourRole.UNKNOWN,
                start=node_a,
                end=node_b,
                segment=LineSeg(start=a, end=b),
            ))

    if not replacements and not added:
        return list(edges)

    out = [replacements.get(id(e), e) for e in edges]
    out.extend(added)
    return out
