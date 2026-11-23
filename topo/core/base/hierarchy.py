"""
topo/core/base/hierarchy.py
---------------------------
The containment tree of closed contours: which is inside which (shapely), and
the clusters that come out of it, ordered. The loop that becomes a curve is in
`curves.py`.
"""

from typing import Optional

from ...model.curve import ClosedCurve
from ...model.cluster import Cluster
from ...model.contour import Contour
from ...model.role import ContourRole, is_structural_role
from ..geometry.shapely_polygons import curve_polygon, with_polygon
from ..geometry.measure import FLOAT_NOISE, noise_runs, track_points
from ..geometry.rings import ring_scale
from ..geometry.regions import enclosing



# --- Containment tree ---

def _place(proxy: ClosedCurve, nodes: list) -> bool:
    for node in nodes:
        if curve_polygon(node[0]).contains(curve_polygon(proxy)):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def sort_clusters(clusters: list) -> list:
    """The clusters from the largest: exact area of the outer, then on equal area the
    (xmin, ymin) corner of the bbox — between two congruent copies the only fact
    that tells them apart. Equal means within the noise (FLOAT_NOISE on the
    perimeter for the area, FLOAT_NOISE for xmin), not in the same cell of a grid."""
    ordered = []
    by_area = sorted(clusters, key=lambda c: -c.outer.area)
    for same_area in noise_runs(by_area, lambda a, b: a.outer.area - b.outer.area
                           <= FLOAT_NOISE * ring_scale(a.outer.segments)):
        by_x = sorted(same_area, key=lambda c: c.bbox[0])
        for same_x in noise_runs(by_x, lambda a, b: b.bbox[0] - a.bbox[0] <= FLOAT_NOISE):
            ordered += sorted(same_x, key=lambda c: c.bbox[1])
    return ordered


def _build_tree(proxies: list) -> list:
    proxies_sorted = sorted(proxies, key=lambda p: round(p.area, 6), reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# --- Semantic construction ---

def _make_inner(
    proxy: ClosedCurve,
    parent_role: ContourRole = ContourRole.UNKNOWN,
    depth: int = 1,
    parent: Optional[Contour] = None,
) -> Contour:
    role = (
        proxy.role if proxy.role not in (ContourRole.UNKNOWN, ContourRole.INNER)
        else parent_role if parent_role not in (ContourRole.UNKNOWN, ContourRole.INNER)
        else ContourRole.INNER
    )
    return with_polygon(Contour(
        role=role,
        segments=list(proxy.segments),
        styles=list(getattr(proxy, "styles", []) or []),
        depth=depth,
        parent=parent,
    ), curve_polygon(proxy))


def _collect_inners(
    children: list,
    inners: list,
    classified_proxies: set,
    parent_role: ContourRole = ContourRole.UNKNOWN,
    depth: int = 1,
    parent: Optional[Contour] = None,
):
    """Flatten the containment tree into `cluster.inners` (every descendant of an
    outer becomes a `Contour`, at any depth), but keep the shape of the tree:
    each contour carries `depth` (0 for the outer, 1 for a direct child, 2 for a
    grandchild, ...) and `parent` (the `Contour` that directly contains it). A
    consumer of the cluster can thus climb the containment chain without
    recomputing it — it is the data `topo.tools.strips` reads to know which
    borders face each other.

    heal() stops here — it no longer decides hole vs inner nor recognizes
    countersinks from the nesting. detect_flat(features="holes") re-derives the
    nesting by containment between polygons and promotes the holes."""
    for child_proxy, grandchildren in children:
        classified_proxies.add(id(child_proxy))
        contour = _make_inner(child_proxy, parent_role=parent_role, depth=depth, parent=parent)
        inners.append(contour)
        if grandchildren:
            _collect_inners(
                grandchildren, inners, classified_proxies,
                parent_role=parent_role, depth=depth + 1, parent=contour,
            )


# ---------------------------------------------------------------------------
# HierarchyBuilder
# ---------------------------------------------------------------------------

class HierarchyBuilder:
    def __init__(self, label: str, source_file: str, is_structural=None):
        self.label       = label
        self.source_file = source_file
        # Same predicate as split_labeled / structural_loops — injected by the caller
        # (snapbend: a hole is a part contour) or, by default, only outer/inner
        # (model.role.is_structural_role).
        self._is_structural = is_structural or is_structural_role

    def build(self, proxies: list) -> tuple[list[Cluster], list]:
        self._classified_proxies: set[int] = set()

        valid = [p for p in proxies if curve_polygon(p) is not None]
        if not valid:
            return [], self._collect_loose(proxies)

        tree  = _build_tree(valid)
        clusters = self._build_parts(tree)
        loose = self._collect_loose(proxies)

        return sort_clusters(clusters), loose

    def _build_parts(self, tree: list) -> list[Cluster]:
        clusters = []

        for root_node in tree:
            father_proxy, children = root_node

            outer = with_polygon(Contour(
                role=ContourRole.OUTER,
                segments=list(father_proxy.segments),
                styles=list(getattr(father_proxy, "styles", []) or []),
                depth=0,
                parent=None,
            ), curve_polygon(father_proxy))
            self._classified_proxies.add(id(father_proxy))

            inners = []
            _collect_inners(
                children, inners, self._classified_proxies,
                parent_role=father_proxy.role, depth=1, parent=outer,
            )

            cluster = Cluster(
                outer=outer,
                inners=inners,
                label=self.label,
                source_file=self.source_file,
            )
            clusters.append(cluster)

        return clusters

    def _collect_loose(self, proxies: list) -> list:
        return [
            p for p in proxies
            if id(p) not in self._classified_proxies
            and not self._is_structural(getattr(p, "role", ContourRole.UNKNOWN))
        ]


# --- cluster_ref of the loose curves ---

def assign_cluster_refs(curves: list, clusters: list, tolerance: float) -> None:
    """Write on every curve of `curves` (`result.loose`) `cluster_ref`: the index in
    `clusters` of the cluster whose outer contour contains it wholly, border and
    holes included; `None` if none (`geometry.regions.enclosing`).
    """
    tracks = [
        list(poly.exterior.coords) if poly is not None
        else track_points(getattr(c, "segments", []) or [])
        for c in curves
        for poly in [curve_polygon(c)]
    ]
    outers = [curve_polygon(c.outer) if c.outer is not None else None for c in clusters]
    for curve, ref in zip(curves, enclosing(tracks, outers, tolerance)):
        curve.cluster_ref = ref
