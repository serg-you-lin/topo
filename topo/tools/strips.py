"""
topo/tools/strips.py
---------------------
Joining nested solid regions with strips. topo gives the facts and the
construction, the caller the policy (how many strips, where, which region
with which):

1. `facing_boundaries`: for every empty region of a cluster, its boundary and
   those of the solid regions directly inside. A strip passes only between
   these: two regions inside different empty regions have filled
   area in between, and are excluded by construction.
2. the distance between two boundaries is `topo.geometry.gap`.
3. `link`: the strip between two facing boundaries (parent–child and
   sibling–sibling) at a point and with a width; rejected if it crosses
   another boundary or another strip.
4. `unconnected_regions`: the solid regions that, given the strips, are not
   connected to the outermost solid region.

`open_boundaries` is the construction: the boundaries touched by strips,
opened into chains of primitives, and the strips' sides.

Experimental: not in `topo.*` nor in the stable surface; imported from
`topo.tools.strips`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from ..core.geometry.strips import Strip, open_ring, strip_between
from ..core.primitives.line import LineSeg
from ..core.primitives.mathseg import Point

__all__ = [
    "facing_boundaries", "Facing", "link", "Link", "Strip",
    "unconnected_regions", "open_boundaries", "Opened",
]


@dataclass
class Facing:
    """An empty region (`region`, a contour of odd depth) and the solid regions
    directly inside (`inside`): the boundaries that face each other."""
    region: "Contour"
    inside: List["Contour"] = field(default_factory=list)

    @property
    def boundaries(self) -> List["Contour"]:
        return [self.region, *self.inside]


def facing_boundaries(cluster) -> List[Facing]:
    """Fact 1: a `Facing` for every empty region of `cluster`, in the order of `cluster.inners`."""
    groups = [Facing(region=c) for c in cluster.inners if c.depth % 2 == 1]
    by_region = {id(g.region): g for g in groups}
    for c in cluster.inners:
        if c.depth % 2 == 0 and c.parent is not None and id(c.parent) in by_region:
            by_region[id(c.parent)].inside.append(c)
    return groups


@dataclass(frozen=True)
class Link:
    """A strip (`strip`) between the boundaries `a` and `b` of a `Facing`."""
    a:     "Contour"
    b:     "Contour"
    strip: Strip


def link(facing: Facing, a: "Contour", b: "Contour", at: Point, width: float,
         placed: Sequence[Link] = ()) -> Link:
    """Fact 3: the strip of width `width` between `a` and `b`, two boundaries of
    `facing`, at the point `at` (see `topo.core.geometry.strips.strip_between` for
    the direction). Obstacles: the other boundaries of `facing` and the strips of
    `placed`. `ValueError` with the reason if it is rejected, or if `a` and `b`
    are not two distinct boundaries of `facing`."""
    ids = [id(c) for c in facing.boundaries]
    if a is b or id(a) not in ids or id(b) not in ids:
        raise ValueError("link(): `a` and `b` must be two distinct boundaries of `facing`")
    others = [c.segments for c in facing.boundaries if c is not a and c is not b]
    strip = strip_between(a.segments, b.segments, at, width, obstacles=others,
                          placed=[p.strip for p in placed])
    return Link(a=a, b=b, strip=strip)


def _region_of(contour, cluster) -> "Contour":
    """The solid region a boundary belongs to: itself if solid, the region containing the void if it is a void."""
    if contour.depth % 2 == 0:
        return contour
    return contour.parent if contour.parent is not None else cluster.outer


def unconnected_regions(cluster, links: Sequence[Link]) -> List["Contour"]:
    """Fact 4: the solid regions of `cluster` (contours of even depth inside
    `cluster.outer`) that no chain of `links` connects to `cluster.outer`, in the
    order of `cluster.inners`."""
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
    """`boundaries`: every boundary touched by a strip, with the open chains of
    primitives that remain of it. `sides`: the strips' sides, two per strip in
    the order of `links`. The boundaries no strip touches are not there: they stay whole."""
    boundaries: List[Tuple["Contour", List[list]]]
    sides:      List[LineSeg]


def open_boundaries(links: Sequence[Link]) -> Opened:
    """The construction: every touched boundary is opened once, on the cuts of all
    its strips together (opening it one strip at a time would give overlapping
    stretches that no longer close). `ValueError` if two strips overlap on the
    same boundary.
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
