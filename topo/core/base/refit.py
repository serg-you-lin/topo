"""
topo/core/base/refit.py
-----------------------
Rifit: una curva scritta in un'altra forma torna la primitiva che è. Nessuna
fusione di copie (quelle stanno in `merge.py`): qui un gruppo di pezzi o una
curva diventa un'altra primitiva, entro una soglia.

    refit_tessellations — una catena di tanti LineSeg corti è una curva scritta
                          a punti: rifittata come arco/cerchio/spline
                          (fitting.simplify_points).
    refit_native_curves — una spline entro SAME_POINT da un arco o da
                          un'ellisse diventa quello (fitting.conic_of_spline);
                          un'ellisse coi semiassi uguali, il suo cerchio.
    refit_circle_rings  — un gruppo di pezzi che fa il giro di un cerchio entro
                          POINTS_NOISE è quel cerchio (D236).
    chain_runs          — le catene massimali di lati corti: il percorso che
                          il rifit delle tassellature segue.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from typing import Iterable, List, Tuple

from ...precision import POINTS_NOISE, TESSELLATION_RUN, TESSELLATION_SIDE
from ...model.role import ContourRole
from ..geometry.fitting import conic_of_spline, simplify_points
from ..geometry.measure import SAME_POINT
from ..topology.edge import node_point
from ..geometry.points import fit_circle_kasa
from ..primitives.conics import CircleSeg, EllipseSeg, is_full_circle
from ..primitives.line import LineSeg
from ..primitives.mathseg import Point, segment_endpoints
from ..primitives.spline import BSplineSeg
from ..topology.edge import Edge
from ..topology.graph import build_node_graph, connected_groups


def refit_tessellations(
    edges: Iterable[Edge],
    max_segment: float = TESSELLATION_SIDE,
    min_run: int = TESSELLATION_RUN,
    tolerance: float = POINTS_NOISE,
) -> List[Edge]:
    """
    Una catena di almeno `min_run` LineSeg (`role == UNKNOWN`) più corti di
    `max_segment`, collegati uno dopo l'altro, è una curva scritta a punti:
    diventa le primitive di `simplify_points` (linee, archi, spline entro
    `tolerance`; uno spigolo è una svolta su `max_segment`, D141). Gli
    estremi della catena tengono i nodi originali, così resta attaccata ai
    vicini. Il resto non si tocca.
    """
    edges = list(edges)
    short = [e for e in edges
             if isinstance(e.segment, LineSeg) and e.role == ContourRole.UNKNOWN
             and e.start != e.end
             and math.dist(e.segment.start, e.segment.end) < max_segment]
    replaced, new_edges = set(), []
    for path, closed in chain_runs(short):
        if len(path) < min_run:
            continue
        pts = []
        for edge, rev in path:
            a, b = (edge.segment.end, edge.segment.start) if rev else (edge.segment.start, edge.segment.end)
            if not pts:
                pts.append(a)
            pts.append(b)
        if closed:
            pts = pts[:-1]
        prims = simplify_points(pts, tolerance=tolerance, scale=max_segment, closed=closed, corner_turn_deg=None)
        if not prims:
            continue
        first, last = path[0], path[-1]
        start_node = first[0].end if first[1] else first[0].start
        end_node = last[0].start if last[1] else last[0].end
        # una giunzione è un nodo solo, la fine del pezzo che arriva; l'inizio
        # del successivo (a 1 ulp) non conta, o le due copie staccano la catena (G6e)
        nodes = [node_point(segment_endpoints(prims[0])[0])] + [node_point(segment_endpoints(p)[1]) for p in prims]
        if closed:
            nodes[-1] = nodes[0]
        else:
            nodes[0], nodes[-1] = start_node, end_node
        for k, prim in enumerate(prims):
            new_edges.append(replace(first[0], segment=prim, start=nodes[k], end=nodes[k + 1]))
        replaced |= {id(edge) for edge, _ in path}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def refit_native_curves(edges: Iterable[Edge], tolerance: float = SAME_POINT) -> List[Edge]:
    """
    Una curva del file che è una primitiva più semplice diventa quella (D296),
    stessi capi e stessi nodi: una spline entro `tolerance` da un arco o da
    un'ellisse (`conic_of_spline`); un'ellisse coi semiassi uguali, il suo
    cerchio (esatto). Le altre restano come sono.
    """
    out = []
    for e in edges:
        s, simpler = e.segment, None
        if isinstance(s, BSplineSeg):
            simpler = conic_of_spline(s, tolerance)
        elif type(s) is EllipseSeg and s.ratio == 1.0:
            simpler = _circle_of(s)
        out.append(e if simpler is None else replace(e, segment=simpler))
    return out


def _circle_of(s: EllipseSeg) -> CircleSeg:
    """L'ellisse coi semiassi uguali come cerchio: il suo parametro più l'angolo dell'asse è l'angolo."""
    phi = math.atan2(s.major_axis[1], s.major_axis[0])
    return CircleSeg(center=s.center, radius=math.hypot(*s.major_axis), start_angle=s.start_param + phi,
                     end_angle=s.end_param + phi, ccw=s.ccw)


def refit_circle_rings(edges: Iterable[Edge], tolerance: float = POINTS_NOISE) -> List[Edge]:
    """
    Un gruppo connesso di pezzi `role == UNKNOWN` (niente CircleSeg) il cui
    nucleo (il gruppo senza i rami a capo libero) sta tutto entro `tolerance`
    da un cerchio e gli fa il giro completo è quel cerchio: il nucleo diventa
    un CircleSeg, a qualunque grandezza dei lati. Un ramo a capo libero, o un
    pezzo isolato, che ci corre sopra va col cerchio; gli altri restano. Lo
    scarto si misura sul pezzo intero (per una linea anche il punto più
    vicino al centro), così un poligono vero resta (D236).
    """
    edges = list(edges)
    node_edges: dict = {}
    for k, e in enumerate(edges):
        for p in (e.start, e.end):
            node_edges.setdefault(p, []).append(k)
    pairs = [(ks[0], k) for ks in node_edges.values() for k in ks[1:]]
    loose = [e for e in edges if len(node_edges[e.start]) == 1 and len(node_edges[e.end]) == 1]
    replaced, new_edges = set(), []
    for group in connected_groups(len(edges), pairs):
        core = _without_free_branches([edges[k] for k in group])
        if not core or not all(
                not is_full_circle(e.segment) and e.role == ContourRole.UNKNOWN for e in core):
            continue
        pts = [p[:2] for e in core for p in ([e.segment.start, e.segment.end, _chord_midpoint(e.segment)]
                                             if isinstance(e.segment, LineSeg) else e.segment.discretize(tolerance=tolerance / 10))]
        fit = fit_circle_kasa(pts)
        if fit is None:
            continue
        segments = [e.segment for e in core]
        near, far = _ring_band(segments, fit[0])
        radius = (near + far) / 2   # il raggio a metà fra il punto più vicino e il più lontano
        if radius <= tolerance or far - radius > tolerance or not _full_turn(segments, fit[0], tolerance / radius):
            continue
        circle = CircleSeg(center=fit[0], radius=radius)
        node = node_point(segment_endpoints(circle)[0])
        new_edges.append(replace(core[0], segment=circle, start=node, end=node))
        # un ramo libero, o un pezzo isolato, che corre anch'esso sul cerchio è un tratto doppio del giro
        on_ring = [e for e in [edges[k] for k in group] + loose
                   if e.role == ContourRole.UNKNOWN and not is_full_circle(e.segment)
                   and math.dist(node_point(e.start), fit[0]) <= radius + tolerance
                   and _within_band(e.segment, fit[0], radius, tolerance)]
        replaced |= {id(e) for e in core} | {id(e) for e in on_ring}
    if not replaced:
        return edges
    return [e for e in edges if id(e) not in replaced] + new_edges


def _chord_midpoint(s: LineSeg) -> Point:
    """Il punto di mezzo della linea: col fit sui capi e sui mezzi il cerchio sta fra i due, non sui vertici."""
    return ((s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2)


def _without_free_branches(group: List[Edge]) -> List[Edge]:
    """Il gruppo senza i rami che finiscono in un capo libero (tolti uno alla volta finché ce ne sono)."""
    core = [e for e in group if e.start != e.end or not isinstance(e.segment, LineSeg)]
    while True:
        degree = Counter(p for e in core for p in (e.start, e.end))
        kept = [e for e in core if degree[e.start] > 1 and degree[e.end] > 1]
        if len(kept) == len(core):
            return core
        core = kept


def _full_turn(segments, center, slack: float) -> bool:
    """I pezzi, visti dal centro, coprono tutto il giro: nessuno spicchio scoperto più largo di `slack` radianti."""
    spans = []
    for s in segments:
        pts = [s.start, s.end] if isinstance(s, LineSeg) else s.discretize(tolerance=SAME_POINT)
        angles = [math.atan2(p[1] - center[1], p[0] - center[0]) % (2 * math.pi) for p in pts]
        for u, v in zip(angles, angles[1:]):
            lo, hi = min(u, v), max(u, v)
            spans += [(lo, hi)] if hi - lo <= math.pi else [(hi, 2 * math.pi), (0.0, lo)]
    reach = 0.0
    for lo, hi in sorted(spans):
        if lo > reach + slack:
            return False
        reach = max(reach, hi)
    return reach >= 2 * math.pi - slack


def _within_band(segment, center, radius: float, tolerance: float) -> bool:
    """Il pezzo sta tutto entro `tolerance` dal cerchio."""
    near, far = _ring_band([segment], center)
    return radius - near <= tolerance and far - radius <= tolerance


def _ring_band(segments, center) -> Tuple[float, float]:
    """Distanza minima e massima dei pezzi dal centro: per una linea i capi e il suo punto più vicino, per
    le altre curve i loro punti."""
    near, far = math.inf, 0.0
    for s in segments:
        if isinstance(s, LineSeg):
            (ax, ay), (bx, by) = s.start[:2], s.end[:2]
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = max(0.0, min(1.0, ((center[0] - ax) * dx + (center[1] - ay) * dy) / length2)) if length2 else 0.0
            near = min(near, math.dist(center, (ax + t * dx, ay + t * dy)))
            far = max(far, math.dist(center, s.start[:2]), math.dist(center, s.end[:2]))
        else:
            ds = [math.dist(center, p[:2]) for p in s.discretize(tolerance=SAME_POINT)]
            near, far = min(near, *ds), max(far, *ds)
    return near, far


def chain_runs(short_edges: List[Edge]) -> list:
    """Catene massimali: percorsi fra nodi di grado != 2, o anelli.
    [( [(edge, percorso_al_contrario)], chiusa )]."""
    graph = build_node_graph(short_edges)
    used: set = set()
    runs = []

    def walk(start, first_edge, first_other):
        path, node, edge, other = [], start, first_edge, first_other
        while True:
            used.add(id(edge))
            path.append((edge, graph.canonical(edge.start) != node))
            node = other
            nxt = [(e, o) for e, o in graph[node] if id(e) not in used]
            if len(graph[node]) != 2 or not nxt:
                return path, node
            edge, other = nxt[0]

    for n in [n for n in graph if len(graph[n]) != 2]:
        for e, o in graph[n]:
            if id(e) not in used:
                path, _ = walk(n, e, o)
                runs.append((path, False))
    for n in graph:
        for e, o in graph[n]:
            if id(e) not in used:
                path, last = walk(n, e, o)
                runs.append((path, last == n))
    return runs
