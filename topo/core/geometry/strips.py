"""
topo/core/geometry/strips.py
-----------------------------
Una striscia di larghezza data fra due contorni chiusi, e i contorni aperti
dove la striscia li tocca (MAP.md D134, D142). Geometria pura: anelli di
primitive testa-coda (`contour.segments`), nessuna gerarchia. Chi sono i
contorni affacciati e quali regioni restano staccate lo dice
`topo.tools.strips`, che legge la gerarchia di un cluster.

I tagli cadono nei punti esatti di `intersections`, i pezzi restano primitive
dello stesso tipo (un arco tagliato è un arco).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points

from ..primitives.segments import ArcSeg, CircleSeg, LineSeg
from .intersections import CURVE_TOLERANCE, intersections
from .regions import (
    _JOIN, _at, _ends, _param, _polygon, _polyline, _side, _signed_area, _span, _split,
    nearest_point,
)

Point = Tuple[float, float]

_TOUCH = 10 * CURVE_TOLERANCE   # un incontro più vicino di così a un capo del fianco è il suo attacco


# ---------------------------------------------------------------------------
# Distanza fra due contorni
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Gap:
    """La distanza minima fra due contorni e i due punti, uno per contorno, dove cade."""
    distance: float
    on_a:     Point
    on_b:     Point


def _ring_points(ring: Sequence) -> List[Point]:
    pts = [q for seg in ring for q in _polyline(seg)]
    return pts + pts[:1]


def gap(a: Sequence, b: Sequence) -> Gap:
    """
    La distanza minima fra gli anelli `a` e `b` e la coppia di punti più
    vicini. Prima sulle due discretizzazioni, poi rifinita sulle primitive
    (proiezioni alterne con `nearest_point`): esatta su rette, archi e
    cerchi; su spline ed ellissi entro `CURVE_TOLERANCE`.
    """
    pa, pb = nearest_points(LineString(_ring_points(a)), LineString(_ring_points(b)))
    on_a, on_b = (pa.x, pa.y), (pb.x, pb.y)
    for _ in range(20):
        new_a = nearest_point(a, on_b)
        new_b = nearest_point(b, new_a)
        moved = math.dist(new_a, on_a) + math.dist(new_b, on_b)
        on_a, on_b = new_a, new_b
        if moved < 1e-12:
            break
    return Gap(math.dist(on_a, on_b), on_a, on_b)


# ---------------------------------------------------------------------------
# La striscia
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Strip:
    """
    Una striscia fra i contorni `a` e `b`. `a_at`/`b_at`: dove la sua linea
    di mezzo tocca i due contorni. `a_cuts`/`b_cuts`: dove la toccano i due
    fianchi, nello stesso ordine di `sides` (il fianco `i` va da `a_cuts[i]`
    a `b_cuts[i]`). Il tratto di `a` fra i due `a_cuts` che passa per `a_at`
    è quello coperto dalla striscia, lo stesso per `b`.
    """
    a_at:   Point
    b_at:   Point
    a_cuts: Tuple[Point, Point]
    b_cuts: Tuple[Point, Point]
    sides:  Tuple[LineSeg, LineSeg]

    @property
    def outline(self) -> List[LineSeg]:
        """Il quadrilatero dei quattro tagli, come anello di lati."""
        (a0, a1), (b0, b1) = self.a_cuts, self.b_cuts
        return [LineSeg(start=a0, end=b0), LineSeg(start=b0, end=b1),
                LineSeg(start=b1, end=a1), LineSeg(start=a1, end=a0)]


def _unit(v: Point) -> Point:
    n = math.hypot(*v)
    if n < 1e-12:
        raise ValueError("direzione nulla")
    return (v[0] / n, v[1] / n)


def _tangent_at(ring: Sequence, point: Point) -> Point:
    """Direzione di percorrenza dell'anello nel suo punto più vicino a `point`."""
    seg = min(ring, key=lambda s: math.dist(nearest_point([s], point), point))
    if isinstance(seg, LineSeg):
        return _unit((seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]))
    if isinstance(seg, (ArcSeg, CircleSeg)):
        r = _unit((point[0] - seg.center[0], point[1] - seg.center[1]))
        ccw = seg.ccw if isinstance(seg, ArcSeg) else True
        return (-r[1], r[0]) if ccw else (r[1], -r[0])
    span = _span(seg)
    s = max(0.0, min(span, _param(seg, point)))
    h = span * 1e-4
    p0, p1 = _at(seg, max(0.0, s - h)), _at(seg, min(span, s + h))
    return _unit((p1[0] - p0[0], p1[1] - p0[1]))


def _normal_toward(ring: Sequence, point: Point, other: Sequence) -> Point:
    """
    Normale all'anello `ring` nel suo punto `point`, dal lato dove sta
    l'anello `other`: verso l'interno se `ring` lo contiene, verso l'esterno
    altrimenti. Il lato si legge dal verso di percorrenza (area con segno),
    esatto anche dove il contorno è sottile o concavo.
    """
    t = _tangent_at(ring, point)
    right = (t[1], -t[0])
    outward = right if _signed_area(ring) > 0 else (-right[0], -right[1])
    inside = _side(_polygon(ring), _ends(other[0])[0]) > 0
    return (-outward[0], -outward[1]) if inside else outward


def _hits(ring: Sequence, line: LineSeg) -> List[Point]:
    return [p for seg in ring for p in intersections(line, seg)]


def _reach(ring: Sequence, start: Point, direction: Point, length: float) -> List[Point]:
    """Dove la semiretta da `start` verso `direction` incontra `ring`, dal più vicino."""
    line = LineSeg(start=start, end=(start[0] + direction[0] * length, start[1] + direction[1] * length))
    hits = [p for p in _hits(ring, line) if math.dist(p, start) > _TOUCH]
    return sorted(hits, key=lambda p: math.dist(p, start))


def _size(*rings: Sequence) -> float:
    pts = [q for ring in rings for q in _ring_points(ring)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def strip_between(a: Sequence, b: Sequence, at: Point, width: float,
                  obstacles: Sequence[Sequence] = (), placed: Sequence[Strip] = ()) -> Strip:
    """
    La striscia di larghezza `width` fra gli anelli `a` e `b`, nel punto
    `at` scelto dal chiamante. `at` si proietta sul più vicino dei due
    anelli e la linea di mezzo parte lì perpendicolare all'anello, dal lato
    dove sta l'altro; se in quella direzione l'altro non c'è, va verso il
    suo punto più vicino. Mai il punto più vicino e basta: da un lato dritto
    può stare di fianco, e la striscia correrebbe lungo il lato invece di
    uscirne. I due fianchi sono le parallele a `±width/2`, tagliate dove
    incontrano `a` e `b` vicino alla linea di mezzo.

    Rifiutata (`ValueError`, col perché) se un fianco non incontra `a` o
    `b`, se un fianco attraversa un anello di `obstacles` o di nuovo `a` o
    `b`, se un anello di `obstacles` sta dentro la striscia, se tocca una
    striscia di `placed`. Gli ostacoli sono gli altri contorni affacciati
    (`topo.tools.strips.facing_boundaries`).
    """
    if width <= 0:
        raise ValueError(f"width deve essere > 0, non {width}")
    a, b = list(a), list(b)
    length = 4 * _size(a, b) + 4 * width
    on_a, on_b = nearest_point(a, at), nearest_point(b, at)
    flip = math.dist(at, on_b) < math.dist(at, on_a)
    start_ring, end_ring, start = (b, a, on_b) if flip else (a, b, on_a)

    hits = _reach(end_ring, start, _normal_toward(start_ring, start, end_ring), length)
    end = hits[0] if hits else nearest_point(end_ring, start)
    direction = _unit((end[0] - start[0], end[1] - start[1]))
    across = (-direction[1] * width / 2, direction[0] * width / 2)

    def cut(ring: Sequence, near: Point, sign: float, which: str) -> Point:
        o = (sign * across[0], sign * across[1])
        line = LineSeg(start=(near[0] + o[0] - direction[0] * length, near[1] + o[1] - direction[1] * length),
                       end=(near[0] + o[0] + direction[0] * length, near[1] + o[1] + direction[1] * length))
        found = _hits(ring, line)
        if not found:
            raise ValueError(f"un fianco della striscia larga {width} non incontra {which}")
        return nearest_point(ring, min(found, key=lambda p: math.dist(p, near)))

    start_cuts = (cut(start_ring, start, 1.0, "il contorno di partenza"),
                  cut(start_ring, start, -1.0, "il contorno di partenza"))
    end_cuts = (cut(end_ring, end, 1.0, "il contorno d'arrivo"), cut(end_ring, end, -1.0, "il contorno d'arrivo"))
    if flip:
        found = Strip(a_at=end, b_at=start, a_cuts=end_cuts, b_cuts=start_cuts,
                      sides=(LineSeg(start=end_cuts[0], end=start_cuts[0]),
                             LineSeg(start=end_cuts[1], end=start_cuts[1])))
    else:
        found = Strip(a_at=start, b_at=end, a_cuts=start_cuts, b_cuts=end_cuts,
                      sides=(LineSeg(start=start_cuts[0], end=end_cuts[0]),
                             LineSeg(start=start_cuts[1], end=end_cuts[1])))
    _refuse_crossings(found, a, b, obstacles, placed)
    return found


def _refuse_crossings(strip: Strip, a: Sequence, b: Sequence, obstacles: Sequence[Sequence],
                      placed: Sequence[Strip]) -> None:
    for side in strip.sides:
        if math.dist(side.start, side.end) <= _TOUCH:
            raise ValueError("la striscia ha un fianco di lunghezza nulla: i due contorni si toccano lì")
        ends = (side.start, side.end)
        for name, ring in [("di nuovo un suo contorno", a), ("di nuovo un suo contorno", b),
                           *(("un altro contorno", r) for r in obstacles),
                           *(("un'altra striscia", s.outline) for s in placed)]:
            if any(min(math.dist(p, e) for e in ends) > _TOUCH for p in _hits(ring, side)):
                raise ValueError(f"la striscia attraversa {name}")
    quad = Polygon([s.start for s in strip.outline])
    for ring in obstacles:
        if quad.contains(LineString(_ring_points(ring)).interpolate(0)):
            raise ValueError("un altro contorno sta dentro la striscia")
    for other in placed:
        if quad.intersects(Polygon([s.start for s in other.outline])):
            raise ValueError("la striscia si sovrappone a un'altra striscia")


# ---------------------------------------------------------------------------
# Un contorno aperto dove lo toccano le strisce
# ---------------------------------------------------------------------------

def open_ring(ring: Sequence, covered: Sequence[Tuple[Point, Point, Point]]) -> List[list]:
    """
    L'anello `ring` senza i tratti coperti: ognuno è `(capo, capo, punto)`,
    i due capi sull'anello e un punto del tratto fra loro (per una striscia:
    `a_cuts` e `a_at`). Ritorna le catene aperte di primitive che restano,
    nel verso dell'anello. `ValueError` se due tratti si sovrappongono o un
    capo non sta sull'anello.
    """
    ring = list(ring)
    if not covered:
        return [ring]
    cuts = [nearest_point(ring, p) for c in covered for p in c[:2]]
    for c, p in zip([p for c in covered for p in c[:2]], cuts):
        if math.dist(c, p) > _TOUCH:
            raise ValueError("un capo di un tratto coperto non sta sull'anello")
    pieces = [piece for seg in ring for piece in _split(seg, cuts)]

    def at_cut(p: Point) -> bool:
        return any(math.dist(p, c) <= _JOIN for c in cuts)

    first = next((k for k, piece in enumerate(pieces) if at_cut(_ends(piece)[0])), None)
    if first is None:
        raise ValueError("i tratti coperti non tagliano l'anello")
    pieces = pieces[first:] + pieces[:first]
    chains: List[list] = []
    for piece in pieces:
        if not chains or at_cut(_ends(piece)[0]):
            chains.append([piece])
        else:
            chains[-1].append(piece)

    dropped = [0] * len(covered)
    kept = []
    for chain in chains:
        ends = (_ends(chain[0])[0], _ends(chain[-1])[1])
        under = None
        for k, (c0, c1, inside) in enumerate(covered):
            same = ({_snap(ends[0], cuts), _snap(ends[1], cuts)} == {_snap(c0, cuts), _snap(c1, cuts)})
            if same and math.dist(nearest_point(chain, inside), inside) <= _TOUCH:
                under = k
        if under is None:
            kept.append(chain)
        else:
            dropped[under] += 1
    if any(n != 1 for n in dropped):
        raise ValueError("due tratti coperti si sovrappongono sull'anello")
    return kept


def _snap(p: Point, cuts: Sequence[Point]) -> int:
    """Indice del primo taglio che coincide con `p` (due tagli coincidenti contano come uno)."""
    k = min(range(len(cuts)), key=lambda i: math.dist(p, cuts[i]))
    return next(i for i in range(len(cuts)) if math.dist(cuts[i], cuts[k]) <= _JOIN)
