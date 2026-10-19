"""
topo/tools/strips.py
---------------------
Unire regioni piene annidate con strisce (MAP.md D134, D142). topo dà i fatti
e la costruzione, il chiamante la politica (quante strisce, dove, quale
regione con quale):

1. `facing_boundaries`: per ogni regione vuota di un cluster, il suo bordo e
   quelli delle regioni piene direttamente dentro. Solo fra questi passa una
   striscia: due regioni dentro regioni vuote diverse hanno materiale in
   mezzo, e sono escluse per costruzione.
2. `gap`: distanza minima fra due bordi e i due punti più vicini.
3. `link`: la striscia fra due bordi affacciati (genitore–figlio e
   fratello–fratello) in un punto e con una larghezza; rifiutata se
   attraversa un altro bordo o un'altra striscia.
4. `unconnected_regions`: le regioni piene che, date le strisce, non sono
   collegate alla regione piena più esterna.

`open_boundaries` è la costruzione: i bordi toccati dalle strisce, aperti in
catene di primitive, e i fianchi delle strisce.

Sperimentale (D140): non è in `topo.*` né nella superficie stabile; si
importa da `topo.tools.strips`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from ..core.geometry.strips import Gap, Strip, gap as _ring_gap, open_ring, strip_between
from ..core.primitives.segments import LineSeg, Point

__all__ = [
    "facing_boundaries", "Facing", "gap", "Gap", "link", "Link", "Strip",
    "unconnected_regions", "open_boundaries", "Opened",
]


@dataclass
class Facing:
    """
    Una regione vuota (`region`, un contorno di profondità dispari) e le
    regioni piene direttamente dentro (`inside`): i bordi che si guardano.
    """
    region: "Contour"
    inside: List["Contour"] = field(default_factory=list)

    @property
    def boundaries(self) -> List["Contour"]:
        return [self.region, *self.inside]


def facing_boundaries(cluster) -> List[Facing]:
    """Fatto 1: un `Facing` per ogni regione vuota di `cluster`, nell'ordine di `cluster.inners`."""
    groups = [Facing(region=c) for c in cluster.inners if c.depth % 2 == 1]
    by_region = {id(g.region): g for g in groups}
    for c in cluster.inners:
        if c.depth % 2 == 0 and c.parent is not None and id(c.parent) in by_region:
            by_region[id(c.parent)].inside.append(c)
    return groups


def gap(a: "Contour", b: "Contour") -> Gap:
    """Fatto 2: distanza minima fra i bordi `a` e `b` e i due punti più vicini."""
    return _ring_gap(a.segments, b.segments)


@dataclass(frozen=True)
class Link:
    """Una striscia (`strip`) fra i bordi `a` e `b` di un `Facing`."""
    a:     "Contour"
    b:     "Contour"
    strip: Strip


def link(facing: Facing, a: "Contour", b: "Contour", at: Point, width: float,
         placed: Sequence[Link] = ()) -> Link:
    """
    Fatto 3: la striscia larga `width` fra `a` e `b`, due bordi di `facing`,
    nel punto `at` (vedi `topo.core.geometry.strips.strip_between` per la
    direzione). Ostacoli: gli altri bordi di `facing` e le strisce di
    `placed`. `ValueError` col perché se è rifiutata, o se `a` e `b` non
    sono due bordi distinti di `facing`.
    """
    ids = [id(c) for c in facing.boundaries]
    if a is b or id(a) not in ids or id(b) not in ids:
        raise ValueError("link(): `a` e `b` devono essere due bordi distinti di `facing`")
    others = [c.segments for c in facing.boundaries if c is not a and c is not b]
    strip = strip_between(a.segments, b.segments, at, width, obstacles=others,
                          placed=[p.strip for p in placed])
    return Link(a=a, b=b, strip=strip)


def _region_of(contour, cluster) -> "Contour":
    """La regione piena a cui appartiene un bordo: lui se è pieno, la regione che contiene il vuoto se è vuoto."""
    if contour.depth % 2 == 0:
        return contour
    return contour.parent if contour.parent is not None else cluster.outer


def unconnected_regions(cluster, links: Sequence[Link]) -> List["Contour"]:
    """
    Fatto 4: le regioni piene di `cluster` (contorni di profondità pari
    dentro `cluster.outer`) che nessuna catena di `links` collega a
    `cluster.outer`, nell'ordine di `cluster.inners`.
    """
    root: Dict[int, int] = {}

    def find(k: int) -> int:
        while root.setdefault(k, k) != k:
            root[k] = root[root[k]]
            k = root[k]
        return k

    for item in links:
        root[find(id(_region_of(item.a, cluster)))] = find(id(_region_of(item.b, cluster)))
    outer = find(id(cluster.outer))
    return [c for c in cluster.inners if c.depth % 2 == 0 and find(id(c)) != outer]


@dataclass
class Opened:
    """
    `boundaries`: ogni bordo toccato da una striscia, con le catene aperte di
    primitive che ne restano. `sides`: i fianchi delle strisce, due per
    striscia nell'ordine di `links`. I bordi che nessuna striscia tocca non
    ci sono: restano interi.
    """
    boundaries: List[Tuple["Contour", List[list]]]
    sides:      List[LineSeg]


def open_boundaries(links: Sequence[Link]) -> Opened:
    """
    La costruzione: ogni bordo toccato si apre una volta sola, sui tagli di
    tutte le sue strisce insieme (aprirlo una striscia alla volta darebbe
    tratti sovrapposti che non chiudono più). `ValueError` se due strisce si
    sovrappongono sullo stesso bordo.
    """
    covered: Dict[int, Tuple["Contour", list]] = {}
    sides: List[LineSeg] = []
    for item in links:
        s = item.strip
        covered.setdefault(id(item.a), (item.a, []))[1].append((*s.a_cuts, s.a_at))
        covered.setdefault(id(item.b), (item.b, []))[1].append((*s.b_cuts, s.b_at))
        sides.extend(s.sides)
    return Opened(boundaries=[(c, open_ring(c.segments, spans)) for c, spans in covered.values()],
                  sides=sides)
