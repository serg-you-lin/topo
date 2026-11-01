# topo/core/base/hierarchy.py

from typing import Optional
from shapely.geometry import Polygon

from ...model.curve import ClosedCurve
from ...model.cluster import Cluster
from ...model.contour import Contour
from ...model.role import ContourRole, is_structural_role
from ..primitives.polygon_builder import curve_polygon, with_polygon
from ..geometry.integrals import ring_area
from ..geometry.measure import FLOAT_NOISE, circular_geometry, track_points
from ..geometry.rings import ring_perimeter
from ..geometry.regions import enclosing


MIN_CONTOUR_AREA = 1e-3
MIN_SINGLE_LOOP_DIAMETER = 0.05


# ---------------------------------------------------------------------------
# Conversione loop → ClosedCurve
# ---------------------------------------------------------------------------

def loop_to_closed_curve(
    loop,
    role: ContourRole = ContourRole.UNKNOWN,
    polygon=None,
    segments: list = None,
    styles: list = None,
) -> Optional[ClosedCurve]:
    from ..topology.loop_finder import loop_points

    if polygon is not None:
        poly = polygon
    else:
        pts = loop_points(loop)
        if len(pts) < 3:
            return None
        poly = Polygon(pts)

    try:
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None
        if not segments or ring_area(segments) <= MIN_CONTOUR_AREA:
            return None

        # Guard sui micro-cerchi: un loop di una singola primitiva circolare
        # con diametro sotto soglia è rumore, non un contorno. La
        # classificazione hole/inner vera e propria è di detect_flat() (D15) —
        # qui `diameter`/`center` NON vengono stoccati sulla curva.
        if len(loop) == 1:
            diameter, _ = circular_geometry(poly, segments)
            if diameter is not None and diameter < MIN_SINGLE_LOOP_DIAMETER:
                return None

        return with_polygon(ClosedCurve(role=role, segments=segments, styles=styles or []), poly)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Albero di contenimento
# ---------------------------------------------------------------------------

def _place(proxy: ClosedCurve, nodes: list) -> bool:
    for node in nodes:
        if curve_polygon(node[0]).contains(curve_polygon(proxy)):
            if not _place(proxy, node[1]):
                node[1].append([proxy, []])
            return True
    return False


def sort_clusters(clusters: list) -> list:
    """
    I cluster dal più grande: area esatta dell'outer, poi a pari area l'angolo
    (xmin, ymin) del bbox — fra due copie congruenti l'unico fatto che le
    distingue. Pari vuol dire entro il rumore (FLOAT_NOISE sul perimetro per
    l'area, FLOAT_NOISE per xmin), non nella stessa cella di una griglia (D195).
    """
    ordered = []
    by_area = sorted(clusters, key=lambda c: -c.outer.area)
    for same_area in _runs(by_area, lambda a, b: a.outer.area - b.outer.area
                           <= FLOAT_NOISE * ring_perimeter(a.outer.segments)):
        by_x = sorted(same_area, key=lambda c: c.bbox[0])
        for same_x in _runs(by_x, lambda a, b: b.bbox[0] - a.bbox[0] <= FLOAT_NOISE):
            ordered += sorted(same_x, key=lambda c: c.bbox[1])
    return ordered


def _runs(items: list, together) -> list:
    """`items` (già ordinati) spezzati dove due vicini non stanno `together`."""
    runs = []
    for item in items:
        if runs and together(runs[-1][-1], item):
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def _build_tree(proxies: list) -> list:
    proxies_sorted = sorted(proxies, key=lambda p: round(p.area, 6), reverse=True)
    roots = []
    for proxy in proxies_sorted:
        if not _place(proxy, roots):
            roots.append([proxy, []])
    return roots


# ---------------------------------------------------------------------------
# Costruzione semantica
# ---------------------------------------------------------------------------

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
    """
    Appiattisce l'albero di contenimento in `cluster.inners` (ogni discendente
    di un outer diventa un `Contour`, a qualsiasi profondità), ma non
    butta via la forma dell'albero: ogni contorno porta con sé `depth` (0 per
    l'outer, 1 per un figlio diretto, 2 per un nipote, ...) e `parent` (il
    `Contour` che lo contiene direttamente). Chi consuma il cluster può
    quindi risalire la catena di contenimento senza doverla ricalcolare da
    zero — è il dato che `topo.tools.strips` legge per sapere quali bordi
    si affacciano (D134).

    heal() si ferma qui — non decide più hole vs inner né riconosce i
    countersink dal nesting (D15). detect_flat(features="holes") ri-deriva il
    nesting per contenimento fra poligoni e promuove i fori.
    """
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
        # Stesso predicato di split_labeled / structural_loops — iniettato dal chiamante
        # (snapbend: un foro è contorno di pezzo) o, di
        # default, solo outer/inner (model.role.is_structural_role).
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
                custom={},
            )
            clusters.append(cluster)

        return clusters

    def _collect_loose(self, proxies: list) -> list:
        return [
            p for p in proxies
            if id(p) not in self._classified_proxies
            and not self._is_structural(getattr(p, "role", ContourRole.UNKNOWN))
        ]


# ---------------------------------------------------------------------------
# cluster_ref delle curve sciolte (D137)
# ---------------------------------------------------------------------------

def assign_cluster_refs(curves: list, clusters: list, tolerance: float) -> None:
    """
    Scrive su ogni curva di `curves` (`result.loose`) `cluster_ref`: l'indice
    in `clusters` del cluster il cui contorno esterno la contiene tutta, bordo
    e buchi compresi; `None` se nessuno (`geometry.regions.enclosing`).
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
