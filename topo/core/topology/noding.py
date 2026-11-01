"""
core/topology/noding.py
-----------------------
Rete piana: ogni edge spezzato dove incrocia o tocca un altro edge, così che
due edge si incontrino solo nei nodi, e un nodo sia lo stesso punto per tutti
gli edge che ci arrivano. È la premessa per percorrere la faccia esterna
(outer_face.py): su una rete non piana un incrocio a metà di due edge non è un
nodo e il percorso ci passa sopra.

Ogni contatto si decide una volta sola, per coppia di edge, sulle curve vere
(D180): un incrocio, un estremo entro `GRAPH_EPSILON` dall'altra curva (un T,
o due estremi vicini), due curve che passano entro `GRAPH_EPSILON` senza
incrociarsi (la tangenza mancata). Gli incontri di una stessa coppia entro
`tolerance` lungo uno dei due edge sono un contatto solo: una retta quasi
tangente a un arco lo incrocia in due radici a pochi centesimi (D101). Un
contatto mette una fermata su ognuno dei due edge, e le fermate di un
contatto sono un nodo solo (union-find), come due fermate dello stesso edge
entro `GRAPH_EPSILON`; mai i due estremi di uno stesso edge. Il nodo di un
gruppo è un estremo d'ingresso, se ne contiene (il più piccolo, come
`cluster_points`), altrimenti la media dei punti di contatto: tutti gli edge
del gruppo ricevono la stessa tupla, e il grafo non rigiudica nulla.
`tolerance` non allarga l'identità di nodo: su tutta la rete percola (D101).

Rette, archi e cerchi si misurano in forma chiusa; spline ed ellissi sulla
loro discretizzazione alla griglia dei nodi (D113), e si tagliano esatte
(`sub_segment`); una spline che non si taglia (periodica) resta intera.

Puro: solo Edge e primitive, nessun formato.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Point

from .edge import Edge
from ..geometry.intersections import intersections
from ..primitives.trim import sub_segment
from ..primitives.segments import (
    LineSeg, ArcSeg, CircleSeg, DEFAULT_TOLERANCE, angle_from_start, point_on_circle,
    segment_endpoints, segment_is_closed,
)

from ..geometry.measure import FLOAT_NOISE, NODE_DECIMALS, within_diameter   # tagli ed estremi sulla stessa griglia di tutto topo (D113)
from .graph import cluster_points, connected_groups

GRAPH_EPSILON = 0.01   # mm — due nodi così vicini sono uno solo per il grafo (heal, ripiego D100)

_EPS = 1e-9
_MIN_PIECE = 1e-4   # mm — sotto, lo spezzone non viene creato
_EXACT = (LineSeg, ArcSeg, CircleSeg)


def _is_loop(seg) -> bool:
    """La curva torna su se stessa: un cerchio, o una spline/ellisse coi capi
    entro DEFAULT_TOLERANCE. Una retta o un arco mai: un tratto corto è un
    tratto, con due capi da nodare (D56), non un anello (G6e)."""
    return isinstance(seg, CircleSeg) or (not isinstance(seg, _EXACT) and segment_is_closed(seg))
# mm — spline ed ellissi si misurano su questa discretizzazione: la griglia
# dei nodi, sotto la quale due punti non si distinguono comunque (D113)
_FINE = 10.0 ** -NODE_DECIMALS


@dataclass
class NodedEdges:
    """La rete piana: i pezzi, per ognuno l'Edge da cui viene, e i nodi dove
    due edge si attraversano senza che nessuno dei due finisca lì (D132)."""
    pieces:    List[Edge]            = field(default_factory=list)
    parent:    Dict[int, Edge]       = field(default_factory=dict)   # id(pezzo) -> Edge originale
    crossings: List[tuple]           = field(default_factory=list)
    planar:    bool                  = True    # tagliata anche agli incroci (`cut_crossings`)

    def parent_of(self, piece: Edge) -> Edge:
        return self.parent[id(piece)]

    def whole(self, loop: list) -> list:
        """`loop` [(pezzo, al contrario)] con l'Edge originale al posto dei suoi
        pezzi, dove il giro li percorre tutti di fila: un lato tagliato da un
        contatto torna il segmento del file, coefficienti compresi (D143)."""
        if not loop:
            return loop
        counts: Dict[int, int] = {}
        for piece in self.pieces:
            key = id(self.parent_of(piece))
            counts[key] = counts.get(key, 0) + 1
        parents = [self.parent_of(e) for e, _ in loop]
        k = next((i for i in range(len(loop)) if parents[i] is not parents[i - 1]), 0)
        loop, parents = loop[k:] + loop[:k], parents[k:] + parents[:k]
        out, i = [], 0
        while i < len(loop):
            j = i
            while j + 1 < len(loop) and parents[j + 1] is parents[i] and loop[j + 1][1] == loop[i][1]:
                j += 1
            if j - i + 1 == counts[id(parents[i])] and (j > i or loop[i][0] is not parents[i]):
                out.append((parents[i], loop[i][1]))
            else:
                out.extend(loop[i:j + 1])
            i = j + 1
        return out


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def renode(edges: List[Edge], decimals: int = NODE_DECIMALS) -> List[Edge]:
    """Nodi di ogni Edge ricalcolati dal punto reale del segmento a
    `decimals`: un contatto a T si riconosce solo se estremi e tagli stanno
    sulla stessa griglia. Gli edge chiusi restano come sono.
    Due capi reali entro FLOAT_NOISE sono lo stesso punto (D183) e si
    arrotondano una volta: due copie a 1 ulp di un vertice non cadono in due
    celle (G6e)."""
    ends = [p for e in edges if not _is_loop(e.segment) for p in segment_endpoints(e.segment)]
    same = cluster_points(ends, FLOAT_NOISE)
    return [e if _is_loop(e.segment) else _with_nodes(e, e.segment, decimals, same)
            for e in edges]


def decide_nodes(edges: List[Edge], epsilon: float = GRAPH_EPSILON) -> Tuple[List[Edge], int]:
    """
    I nodi di ogni lettura, decisi una volta: dai punti reali dei segmenti
    (`renode`), poi gli estremi entro `epsilon` l'uno dall'altro sono un nodo
    solo, il più piccolo del gruppo (un estremo reale). Un gruppo più largo
    di `epsilon` è una curva scritta a punti fitti: i suoi nodi restano
    distinti, nessun ordine sceglie quali fondere (D186). Da qui in poi
    l'uguaglianza fra nodi non dipende più da una cella di griglia (D187).

    Un edge aperto i cui due capi diventano lo stesso nodo è più corto di
    `epsilon`: è saldato (D56), cioè tolto, e i vicini si ritrovano sul nodo
    comune. Ritorna (edge, quanti saldati così).
    """
    edges = renode(edges)
    ends = sorted({p for e in edges if not _is_loop(e.segment) for p in (e.start, e.end)})
    index = {p: k for k, p in enumerate(ends)}
    near = cluster_points(ends, epsilon)
    groups = connected_groups(len(ends), [(index[p], index[q]) for p, q in near.items() if p != q])
    target = {}
    for members in groups:
        points = [ends[k] for k in members]
        if len(points) > 1 and within_diameter(points, epsilon):
            target.update((p, points[0]) for p in points)
    if not target:
        return edges, 0
    out, welded = [], 0
    for edge in edges:
        start, end = target.get(edge.start, edge.start), target.get(edge.end, edge.end)
        if start == end and edge.start != edge.end and not _is_loop(edge.segment):
            welded += 1
            continue
        out.append(edge if (start, end) == (edge.start, edge.end) else replace(edge, start=start, end=end))
    return out, welded


def split_at_crossings(edges: List[Edge], tolerance: float,
                       decimals: int = NODE_DECIMALS, cut_crossings: bool = True) -> NodedEdges:
    """
    Spezza ogni edge nei suoi contatti con gli altri (incroci, T, estremi
    vicini, tangenze mancate entro GRAPH_EPSILON; gli incontri di una coppia
    entro `tolerance` sono uno), decisi una volta per coppia sulle curve
    vere; i pezzi che si toccano hanno la stessa tupla di nodo.
    Un edge chiuso (cerchio) con meno di due contatti resta intero.

    `cut_crossings`: un incrocio (due curve che si attraversano e proseguono)
    taglia anche lui. Il contatto lo decide comunque questa funzione; cosa vuol
    dire lo dice la lettura: per outlines() sì (D101), per faces() no — un
    incrocio fra lati di contorno è un disegno rotto (D132), un'asse che
    attraversa un foro non è un lato del foro (D189). Gli incroci sono in
    `crossings` in tutti e due i casi.
    """
    curves = [_Curve(e.segment) for e in edges]
    net = _Contacts(edges, curves, tolerance)
    for i, j in _near_pairs(edges, tolerance):
        net.meet(i, j)
    net.merge_along_edges()
    nodes = net.nodes(decimals)

    noded = NodedEdges(planar=cut_crossings)
    skip = frozenset() if cut_crossings else frozenset(net.crossing_roots())
    for i, edge in enumerate(edges):
        for piece in net.pieces(i, nodes, skip):
            noded.pieces.append(piece)
            noded.parent[id(piece)] = edge
    noded.crossings = sorted(net.crossings(nodes))
    return noded


def interior_crossings(edges: List[Edge], tolerance: float) -> List[tuple]:
    """
    I punti dove due edge si attraversano senza che nessuno dei due finisca
    lì: un taglio interno a tutti e due (D132). Un contatto a T (il capo di
    uno sulla curva dell'altro) non conta. Fra lati di contorno è un disegno
    con lati accavallati, che il grafo di heal non vede.
    """
    return split_at_crossings(edges, tolerance).crossings


def edge_geometry(edge: Edge):
    """L'edge come geometria shapely: LineString discretizzata, Point se degenere."""
    pts = edge.segment.discretize(tolerance=DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


# ---------------------------------------------------------------------------
# Una curva misurata in lunghezza d'arco
# ---------------------------------------------------------------------------

class _Curve:
    """`seg` col parametro s = lunghezza d'arco dall'inizio, in [0, length]
    (ciclico sui chiusi). Esatto su rette, archi e cerchi; su spline ed
    ellissi lungo la discretizzazione fine."""

    def __init__(self, seg):
        self.seg = seg
        self._fine = None
        self._length = None
        self.closed = _is_loop(seg)

    @property
    def length(self) -> float:
        """Su spline ed ellissi la lunghezza della discretizzazione fine: si
        calcola solo se serve (un edge senza contatti non la chiede)."""
        if self._length is None:
            seg = self.seg
            if isinstance(seg, LineSeg):
                self._length = math.dist(seg.start, seg.end)
            elif isinstance(seg, ArcSeg):
                self._length = seg.radius * seg._sweep()
            elif isinstance(seg, CircleSeg):
                self._length = 2 * math.pi * seg.radius
            else:
                self._length = self.fine.length
        return self._length

    @property
    def exact(self) -> bool:
        return isinstance(self.seg, _EXACT)

    @property
    def fine(self) -> LineString:
        """La curva discretizzata a _FINE, una volta sola."""
        if self._fine is None:
            pts = [tuple(q[:2]) for q in self.seg.discretize(tolerance=_FINE)]
            self._fine = LineString(pts) if len(pts) > 1 else LineString([pts[0], pts[0]])
        return self._fine

    def locate(self, pt) -> Tuple[float, float]:
        """(s del punto della curva più vicino a `pt`, distanza)."""
        seg = self.seg
        if isinstance(seg, LineSeg):
            if self.length < _EPS:
                return 0.0, math.dist(seg.start, pt)
            dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
            t = ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / (self.length ** 2)
            t = min(1.0, max(0.0, t))
            return t * self.length, math.dist(pt, (seg.start[0] + t * dx, seg.start[1] + t * dy))
        if isinstance(seg, ArcSeg):
            a = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
            if a <= seg._sweep():
                return seg.radius * a, abs(math.dist(pt, seg.center) - seg.radius)
            start, end = segment_endpoints(seg)
            if math.dist(pt, start) <= math.dist(pt, end):
                return 0.0, math.dist(pt, start)
            return self.length, math.dist(pt, end)
        if isinstance(seg, CircleSeg):
            a = math.atan2(pt[1] - seg.center[1], pt[0] - seg.center[0]) % (2 * math.pi)
            return seg.radius * a, abs(math.dist(pt, seg.center) - seg.radius)
        at = Point(pt)
        return self.fine.project(at), self.fine.distance(at)

    def at(self, s: float):
        seg = self.seg
        if isinstance(seg, LineSeg):
            t = 0.0 if self.length < _EPS else s / self.length
            return (seg.start[0] + t * (seg.end[0] - seg.start[0]), seg.start[1] + t * (seg.end[1] - seg.start[1]))
        if isinstance(seg, ArcSeg):
            return point_on_circle(seg.center, seg.radius,
                                   seg.start_angle + (s if seg.ccw else -s) / seg.radius)
        if isinstance(seg, CircleSeg):
            return point_on_circle(seg.center, seg.radius, s / seg.radius)
        return self.fine.interpolate(s % self.length if self.closed else s).coords[0]

    def piece(self, s0: float, s1: float):
        """Il tratto da s0 a s1 (s0 < s1; su un chiuso s1 può superare
        length), stessa primitiva; None se non si taglia esatto."""
        seg = self.seg
        if isinstance(seg, LineSeg):
            return LineSeg(start=seg.start if s0 == 0.0 else self.at(s0),
                           end=seg.end if s1 == self.length else self.at(s1))
        if isinstance(seg, (ArcSeg, CircleSeg)):
            start, sign, ccw = ((seg.start_angle, 1.0 if seg.ccw else -1.0, seg.ccw)
                                if isinstance(seg, ArcSeg) else (0.0, 1.0, True))
            return ArcSeg(center=seg.center, radius=seg.radius, start_angle=start + sign * s0 / seg.radius,
                          end_angle=start + sign * s1 / seg.radius, ccw=ccw)
        ends = segment_endpoints(seg)
        a = ends[0] if s0 == 0.0 else self.at(s0)
        b = ends[1] if s1 == self.length else self.at(s1)
        return sub_segment(seg, a, b, self.at((s0 + s1) / 2))


# ---------------------------------------------------------------------------
# Contatti
# ---------------------------------------------------------------------------

def _near_pairs(edges: List[Edge], tolerance: float) -> List[Tuple[int, int]]:
    """Le coppie (i < j) da giudicare. Il filtro misura sulle discretizzazioni
    (fino a DEFAULT_TOLERANCE dentro un arco): si allarga di tanto, il
    contatto lo decide `_Contacts.meet` sulle curve."""
    geoms = np.array([edge_geometry(e) for e in edges], dtype=object)
    if len(geoms) < 2:
        return []
    a, b = STRtree(geoms).query(geoms, predicate="dwithin", distance=tolerance + 2 * DEFAULT_TOLERANCE)
    keep = a < b
    return sorted(zip(a[keep].tolist(), b[keep].tolist()))


class _Contacts:
    """Le fermate dei contatti su ogni edge e i nodi che formano (union-find).
    Una fermata è (edge, s, punto, tipo): "end" un estremo dell'edge, "x" un
    incrocio, "t" un estremo d'altri sull'edge, "g" una tangenza mancata."""

    def __init__(self, edges: List[Edge], curves: List[_Curve], tolerance: float):
        self.edges, self.curves, self.tol = edges, curves, tolerance
        # un contatto (incrocio, T, due estremi, tangenza mancata) è entro
        # `node`, e due fermate entro `node` sono un nodo solo: la soglia del
        # grafo. `tolerance` fonde solo gli incontri di una stessa coppia
        # (D101): su tutta la rete percola (D101, tentativo scartato)
        self.node = min(tolerance, GRAPH_EPSILON)
        self.stops: List[tuple] = []
        self.up: List[int] = []
        self.on_edge: Dict[int, List[int]] = defaultdict(list)
        self.ends: Dict[int, Tuple[int, int]] = {}
        self.anchor: Dict[int, int] = {}   # fermata interna -> prima fermata del suo gruppo sull'edge
        self.absorbed: set = set()         # fermate interne fuse con un estremo dell'edge
        self.sides: Dict[int, Dict[int, int]] = {}   # radice -> {edge: estremi nel nodo, 1 inizio 2 fine}
        by_node: Dict[tuple, int] = {}
        for i, edge in enumerate(edges):
            if self._is_open(i):
                # la s della fine si legge quando serve (curve.length)
                pair = (self._stop(i, 0.0, edge.start, "end"), self._stop(i, None, edge.end, "end"))
                self.ends[i] = pair
                self.sides[pair[0]], self.sides[pair[1]] = {i: 1}, {i: 2}
                for k, node in zip(pair, (edge.start, edge.end)):
                    self._union(k, by_node.setdefault(node, k))

    def _is_open(self, i: int) -> bool:
        edge, curve = self.edges[i], self.curves[i]
        return not curve.closed and edge.start != edge.end and (not curve.exact or curve.length > _EPS)

    def _stop(self, i: int, s: float, pt, kind: str) -> int:
        k = len(self.stops)
        self.stops.append((i, s, pt, kind))
        self.up.append(k)
        if kind != "end":
            self.on_edge[i].append(k)
        return k

    def _find(self, k: int) -> int:
        root = k
        while self.up[root] != root:
            root = self.up[root]
        while self.up[k] != root:
            self.up[k], k = root, self.up[k]
        return root

    def _union(self, a: int, b: int) -> bool:
        """Un nodo solo per `a` e `b`, se non mette i due estremi di uno
        stesso edge nello stesso nodo: un lato corto non sparisce."""
        ra, rb = self._find(a), self._find(b)
        if ra == rb:
            return True
        if not self._joinable([ra, rb]):
            return False
        keep, gone = min(ra, rb), max(ra, rb)
        self.up[gone] = keep
        merged = self.sides.pop(gone, {})
        mine = self.sides.setdefault(keep, {})
        for i, mask in merged.items():
            mine[i] = mine.get(i, 0) | mask
        return True

    def _joinable(self, roots) -> bool:
        seen: Dict[int, int] = {}
        for root in set(roots):
            for i, mask in self.sides.get(root, {}).items():
                if seen.get(i, 0) | mask == 3:
                    return False
                seen[i] = seen.get(i, 0) | mask
        return True

    def meet(self, i: int, j: int) -> None:
        """Decide i contatti fra gli edge `i` e `j`, una volta sola."""
        ci, cj = self.curves[i], self.curves[j]
        contacts = []   # [(lato su i, lato su j, tipo)]
        for p in _meetings(ci, cj):
            contacts.append(((i, ci.locate(p)[0], p, None),
                             (j, cj.locate(p)[0], p, None), "x"))
        # un estremo dell'uno entro `node` dalla curva dell'altra: il T, o
        # due estremi (se il punto più vicino è un estremo anche dell'altra)
        for k, other in ((i, j), (j, i)):
            if other not in self.ends:
                continue
            ck = self.curves[k]
            for end, pt in zip(self.ends[other], segment_endpoints(self.edges[other].segment)):
                s, d = ck.locate(pt)
                if d > self.node:
                    continue
                at_end = k in self.ends and (s <= _EPS or s >= ck.length - _EPS)
                mine = (k, s, pt, self.ends[k][0 if s <= _EPS else 1] if at_end else None)
                theirs = (other, 0.0 if end == self.ends[other][0] else self.curves[other].length, pt, end)
                contacts.append((mine, theirs, "t") if k == i else (theirs, mine, "t"))
        if not contacts:
            # la tangenza mancata di poco è un contatto come quella
            # incrociata di poco: nel punto medio fra le due curve
            near = _grazing(ci, cj)
            if near is not None and math.dist(*near) <= self.node:
                mid = ((near[0][0] + near[1][0]) / 2, (near[0][1] + near[1][1]) / 2)
                contacts.append(((i, ci.locate(mid)[0], mid, None),
                                 (j, cj.locate(mid)[0], mid, None), "g"))
        for group in self._same_contact(contacts):
            kind = "x" if any(c[2] == "x" for c in group) else group[0][2]
            stops = [self._place([c[n] for c in group], kind) for n in (0, 1)]
            if not self._union(*stops):
                # un contatto che chiuderebbe un lato su se stesso: le sue
                # fermate nuove non tagliano nulla
                self._drop(stops)

    def _same_contact(self, contacts: list) -> List[list]:
        """I contatti di una coppia entro tolerance lungo uno dei due edge sono
        uno solo (D101: le due radici di una retta quasi tangente a un arco),
        mai però due estremi dello stesso edge: un lato corto non sparisce.
        I più vicini si uniscono per primi."""
        n = len(contacts)
        if n < 2:
            return [contacts] if contacts else []
        up = list(range(n))
        ends = [{c[0][3], c[1][3]} - {None} for c in contacts]

        def find(a):
            while up[a] != a:
                up[a] = up[up[a]]
                a = up[a]
            return a

        candidates = []
        for side in (0, 1):
            curve = self.curves[contacts[0][side][0]]
            order = sorted(range(n), key=lambda c: contacts[c][side][1])
            for a, b in zip(order, order[1:]):
                candidates.append((contacts[b][side][1] - contacts[a][side][1], a, b))
            if curve.closed:
                a, b = order[-1], order[0]
                candidates.append((contacts[b][side][1] + curve.length - contacts[a][side][1], a, b))
        for gap, a, b in sorted(candidates):
            if gap > self.tol:
                break
            ra, rb = find(a), find(b)
            if ra == rb:
                continue
            both = ends[ra] | ends[rb]
            if not self._joinable(self._find(e) for e in both):
                continue
            up[rb], ends[ra] = ra, both
        groups: Dict[int, list] = {}
        for c in range(n):
            groups.setdefault(find(c), []).append(contacts[c])
        return list(groups.values())

    def _drop(self, stops) -> None:
        for k in stops:
            if self.stops[k][3] != "end" and self.up[k] == k:
                self.on_edge[self.stops[k][0]].remove(k)

    def _place(self, sides: list, kind: str) -> int:
        """La fermata di un contatto su un edge: il suo estremo, se il
        contatto lo tocca, altrimenti una nuova al centro dei suoi lati."""
        for _, _, _, end in sides:
            if end is not None:
                return end
        k, curve = sides[0][0], self.curves[sides[0][0]]
        s = [side[1] for side in sides]
        if curve.closed and max(s) - min(s) > curve.length / 2:   # a cavallo dell'inizio
            s = [x if x >= curve.length / 2 else x + curve.length for x in s]
        mean = sum(s) / len(s)
        pt = (sum(side[2][0] for side in sides) / len(sides), sum(side[2][1] for side in sides) / len(sides))
        return self._stop(k, mean % curve.length if curve.closed else mean, pt, kind)

    def merge_along_edges(self) -> None:
        """Due fermate dello stesso edge entro `node` lungo l'edge sono un
        nodo solo, e una entro `node` da un estremo dell'edge è quell'estremo:
        la stessa soglia con cui il grafo fonde due estremi vicini. Il gruppo
        si misura dalla sua prima fermata."""
        r = self.node
        for i, ks in self.on_edge.items():
            curve = self.curves[i]
            ks.sort(key=lambda k: self.stops[k][1])
            first = None
            for k in ks:
                s = self.stops[k][1]
                if i in self.ends and min(s, curve.length - s) <= r and                         self._union(k, self.ends[i][0 if s <= curve.length - s else 1]):
                    self.absorbed.add(k)
                    continue
                if first is None or s - self.stops[first][1] > r or not self._union(k, first):
                    first = k
                self.anchor[k] = first
            live = [k for k in ks if k not in self.absorbed]
            if curve.closed and len(live) > 1:
                head, tail = live[0], live[-1]
                if self.anchor[head] != self.anchor[tail] and (
                        self.stops[head][1] + curve.length - self.stops[tail][1] <= r):
                    self._union(head, tail)
                    tail_group = self.anchor[tail]
                    for k in live:
                        if self.anchor[k] == tail_group:
                            self.anchor[k] = self.anchor[head]

    def nodes(self, decimals: int) -> Dict[int, tuple]:
        """{radice: tupla del nodo}: l'estremo d'ingresso del gruppo, se ne ha
        uno solo; la media dei suoi estremi distinti, se ne ha più d'uno (fra
        due capi nessuno vale più dell'altro, G6e); altrimenti la media dei
        punti di contatto. Le medie stanno sulla griglia dei nodi."""
        ends: Dict[int, list] = defaultdict(list)
        points: Dict[int, list] = defaultdict(list)
        for k, (i, _, pt, kind) in enumerate(self.stops):
            root = self._find(k)
            (ends if kind == "end" else points)[root].append(pt)
        out = {}
        for root in set(ends) | set(points):
            distinct = set(ends[root])
            if len(distinct) == 1:
                out[root] = distinct.pop()
            else:
                pts = list(distinct) or points[root]
                out[root] = (round(math.fsum(p[0] for p in pts) / len(pts), decimals),
                             round(math.fsum(p[1] for p in pts) / len(pts), decimals))
        return out

    def crossing_roots(self) -> set:
        """I nodi senza estremi con almeno un incrocio fra due edge diversi:
        due curve che si attraversano e proseguono tutte e due."""
        groups: Dict[int, list] = defaultdict(list)
        for k, stop in enumerate(self.stops):
            groups[self._find(k)].append(stop)
        return {root for root, stops in groups.items()
                if all(kind != "end" for _, _, _, kind in stops)
                and any(kind == "x" for _, _, _, kind in stops)
                and len({i for i, _, _, _ in stops}) > 1}

    def crossings(self, nodes: Dict[int, tuple]) -> List[tuple]:
        return [nodes[root] for root in self.crossing_roots()]

    def pieces(self, i: int, nodes: Dict[int, tuple], skip: frozenset = frozenset()) -> List[Edge]:
        """L'edge `i` tagliato ai suoi gruppi di fermate, coi nodi condivisi;
        non ai nodi di `skip`."""
        edge, curve = self.edges[i], self.curves[i]
        groups: Dict[int, list] = {}
        for k in self.on_edge.get(i, []):
            if k not in self.absorbed and self._find(k) not in skip:
                groups.setdefault(self.anchor[k], []).append(k)
        cuts = []
        for ks in groups.values():
            s = [self.stops[k][1] for k in ks]
            if curve.closed and max(s) - min(s) > curve.length / 2:   # gruppo a cavallo dell'inizio
                s = [x if x >= curve.length / 2 else x + curve.length for x in s]
            cuts.append(((sum(s) / len(s)) % curve.length if curve.closed else sum(s) / len(s),
                         nodes[self._find(ks[0])]))
        cuts.sort()
        if i not in self.ends and not curve.closed:   # un capo solo: nessun tratto da tagliare
            return [edge]
        if i in self.ends:
            start, end = (nodes[self._find(k)] for k in self.ends[i])
            bounds = [(0.0, start)]
            for s, node in cuts:
                if s - bounds[-1][0] > _MIN_PIECE and curve.length - s > _MIN_PIECE:
                    bounds.append((s, node))
            bounds.append((curve.length, end))
        else:
            if len(cuts) < 2:
                return [edge]
            bounds = []
            for s, node in cuts:
                if not bounds or s - bounds[-1][0] > _MIN_PIECE:
                    bounds.append((s, node))
            if len(bounds) > 1 and bounds[0][0] + curve.length - bounds[-1][0] <= _MIN_PIECE:
                bounds.pop()
            if len(bounds) < 2:
                return [edge]
            if not curve.exact:
                # una spline o un'ellisse chiusa si taglia anche all'inizio:
                # un tratto non scavalca la sua cucitura
                seam = (0.0, edge.start)
                if bounds[0][0] > _MIN_PIECE and curve.length - bounds[-1][0] > _MIN_PIECE:
                    bounds.insert(0, seam)
                bounds.append((curve.length, bounds[0][1]) if bounds[0][0] == 0.0
                              else (bounds[0][0] + curve.length, bounds[0][1]))
            else:
                bounds.append((bounds[0][0] + curve.length, bounds[0][1]))
        if len(bounds) == 2 and i in self.ends:
            if (bounds[0][1], bounds[1][1]) == (edge.start, edge.end):
                return [edge]
            return [replace(edge, start=bounds[0][1], end=bounds[1][1])]
        segs = [curve.piece(s0, s1) for (s0, _), (s1, _) in zip(bounds, bounds[1:])]
        if any(seg is None for seg in segs):
            return [edge] if i not in self.ends else [replace(edge, start=bounds[0][1], end=bounds[-1][1])]
        return [replace(edge, segment=seg, start=n0, end=n1)
                for seg, (_, n0), (_, n1) in zip(segs, bounds, bounds[1:])]


def _meetings(a: _Curve, b: _Curve) -> list:
    """Dove `a` e `b` si incrociano o si toccano: in forma chiusa fra rette,
    archi e cerchi, sulle discretizzazioni fini se c'è una spline o
    un'ellisse. Un tratto in comune non è un punto: non conta."""
    if a.exact and b.exact:
        return intersections(a.seg, b.seg)
    hit = a.fine.intersection(b.fine)
    return [p.coords[0] for p in getattr(hit, "geoms", [hit]) if p.geom_type == "Point"]


def _grazing(a: _Curve, b: _Curve) -> Optional[tuple]:
    """(punto di `a`, punto di `b`) più vicini fra due curve che non si
    incontrano, presi a metà di tutte e due; None se il più vicino è un
    estremo (lo giudica il T) o fra due rette (sempre un estremo)."""
    sa, sb = a.seg, b.seg
    if isinstance(sa, LineSeg) and isinstance(sb, LineSeg):
        return None
    if a.exact and b.exact:
        if isinstance(sb, LineSeg):
            found = _line_circle_near(sb, sa)
            return None if found is None else (found[1], found[0])
        if isinstance(sa, LineSeg):
            return _line_circle_near(sa, sb)
        return _circle_circle_near(a, b)
    p, q = shapely.shortest_line(a.fine, b.fine).coords
    return (p, q) if _inside(a, p) and _inside(b, q) else None


def _inside(curve: _Curve, pt) -> bool:
    if curve.closed:
        return True
    s, _ = curve.locate(pt)
    return _MIN_PIECE < s < curve.length - _MIN_PIECE


def _line_circle_near(line: LineSeg, arc) -> Optional[tuple]:
    """(piede sulla retta, punto dell'arco) della perpendicolare dal centro."""
    dx, dy = line.end[0] - line.start[0], line.end[1] - line.start[1]
    l2 = dx * dx + dy * dy
    if l2 < _EPS:
        return None
    c = arc.center
    t = ((c[0] - line.start[0]) * dx + (c[1] - line.start[1]) * dy) / l2
    if not 0.0 < t < 1.0:
        return None
    foot = (line.start[0] + t * dx, line.start[1] + t * dy)
    near = _radial(c, arc.radius, foot)
    if near is None or not _on_arc(arc, near):
        return None
    return foot, near


def _circle_circle_near(a: _Curve, b: _Curve) -> Optional[tuple]:
    """I due punti più vicini fra due archi, sulla retta dei centri."""
    ca, cb = a.seg, b.seg
    d = math.dist(ca.center, cb.center)
    if d < _EPS:
        return None
    best = None
    for sign in (1.0, -1.0):   # i due punti di b sulla retta dei centri
        q = (cb.center[0] + sign * (ca.center[0] - cb.center[0]) * cb.radius / d,
             cb.center[1] + sign * (ca.center[1] - cb.center[1]) * cb.radius / d)
        p = _radial(ca.center, ca.radius, q)
        if p is None or not (_on_arc(ca, p) and _on_arc(cb, q)):
            continue
        if best is None or math.dist(p, q) < math.dist(*best):
            best = (p, q)
    return best


def _radial(center, radius, pt):
    """Il punto del cerchio più vicino a `pt`; None se `pt` è il centro."""
    d = math.dist(center, pt)
    if d < _EPS:
        return None
    return (center[0] + (pt[0] - center[0]) * radius / d, center[1] + (pt[1] - center[1]) * radius / d)


def _on_arc(seg, pt) -> bool:
    """`pt` (sul cerchio) cade dentro l'arco, lontano dagli estremi."""
    if isinstance(seg, CircleSeg):
        return True
    s = angle_from_start(seg.center, seg.start_angle, seg.ccw, pt)
    return _MIN_PIECE / seg.radius < s < seg._sweep() - _MIN_PIECE / seg.radius


# ---------------------------------------------------------------------------
# Nodi
# ---------------------------------------------------------------------------

def _with_nodes(edge, seg, decimals, same=None):
    s, e = segment_endpoints(seg)
    if same is not None:
        s, e = same.get(s, s), same.get(e, e)
    r = lambda pt: (round(pt[0], decimals), round(pt[1], decimals))
    return replace(edge, start=r(s), end=r(e), segment=seg)
