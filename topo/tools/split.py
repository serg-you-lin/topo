"""
topo/tools/split.py
-------------------
Un Result per parte (MAP.md D124, D129). Scegliere le parti è una decisione
sul modello, non su un formato: quali cluster tenere (`min_area`), come si
chiamano (`namer` → `cluster.label`), quali curve sciolte e quali testi
viaggiano con ognuna. Ogni exporter scrive poi una parte nel suo formato
(`topo_dxf.to_dxf`, `topo.experimental.to_svg`): lo stesso split esporta
parti in DXF, SVG o PDF.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Callable, List, Optional

from shapely.geometry import Point

from ..core.geometry.measure import track_points
from ..core.primitives.polygon_builder import curve_polygon
from ..model import Cluster, Result
from ..model.diagnostic import Diagnostic, plural

def split(
    result: Result,
    *, namer: Optional[Callable[[int, Cluster], str]] = None,
    min_area: float = 0.0,
) -> List[Result]:
    """
    One `Result` per part, in the order of the kept parts.

    Each part is a `Result` with a single cluster, the loose curves and the
    texts that belong to it. A curve goes to the cluster of its
    `cluster_ref` (D137); a text goes to the part that contains it. Those
    that no part contains go to the part closest to its outer contour among
    ALL the parts (including those discarded by `min_area`). Nothing is
    duplicated: every element lives in one part only, copied with
    `cluster_ref` referring to the part (0 if its cluster contains it,
    `None` otherwise). A promoted curve (`result.promote`) is already in its
    cluster. The other `Result` fields (source, warnings) are copied.
    `Text.target`/`references` of a text point to the elements of its own
    part (the copies of the loose curves); an element of another part is not
    in that `Result`: `target` becomes `None`, the reference leaves
    `references` (D177).

    `namer(i, cluster)` — if given — returns the `label` of the part's
    cluster, so a file name can be derived downstream
    (`f"{cluster.label}.dxf"`); without it, the i-th part is
    `f"{label}_P{i + 1}"`. By default it discards nothing (D232): a part
    below `min_area` (drawing units squared; `<= 0`: no filter) is discarded
    with a warning in `result.warnings` and in those of every part: even if
    it discards them all, the discard can be read.

    **Mutates** only `result.warnings` (D176): a part's cluster is a copy
    with its own `label`, the original does not change.

    Raises `ValueError` if `result` is not valid: one file per part makes no
    sense without parts (D83).
    """
    if not result.is_valid:
        raise ValueError(
            "split(): the Result is not valid, no output. "
            + " ".join(result.errors)
        )

    outers = _outer_polygons(result.clusters)
    loose_of = _assign_loose(result, outers)
    texts_of = _assign(result.texts, outers, lambda a: a.position, covering=True)

    kept = [i for i, c in enumerate(result.clusters) if cluster_passes_min_area(c, min_area)]
    dropped = [c for i, c in enumerate(result.clusters) if i not in kept]
    if dropped:
        result.warnings.append(Diagnostic(
            "dropped-part", f"{plural(len(dropped), 'part', 'parts')} dropped, area under min_area {min_area:g}",
            points=[c.outer.segments[0].start for c in dropped],
            notes=[f"smallest {min(c.outer.area for c in dropped):.4g}, largest {max(c.outer.area for c in dropped):.4g}"],
            help="topo.split(result) keeps every part (min_area=0.0, the default)"))
    parts: List[Result] = []
    for i in kept:
        cluster = result.clusters[i]
        label = namer(i, cluster) if namer else f"{cluster.label}_P{i + 1}"
        loose = _local(loose_of.get(id(cluster), []), i)
        texts = _local(texts_of.get(id(cluster), []), i)
        _relink(texts, cluster, loose_of.get(id(cluster), []), loose)
        parts.append(replace(
            result,
            clusters=[replace(cluster, label=label)],
            loose=loose,
            texts=texts,
            warnings=list(result.warnings),
            errors=list(result.errors),
        ))
    return parts


def cluster_passes_min_area(cluster: Cluster, min_area: float) -> bool:
    """True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro)."""
    return not (min_area > 0 and cluster.outer.area < min_area)


def _assign(items, outers, probe_of, covering: bool) -> dict[int, list]:
    """
    id(cluster) → gli elementi che gli appartengono. Con `covering` vince la
    prima parte che contiene il punto, altrimenti la più vicina; senza, la
    più vicina e basta.
    Un elemento senza un punto rappresentativo va alla prima parte.
    """
    owned: dict[int, list] = {}
    if not outers:
        return owned
    for item in items:
        probe = probe_of(item)
        if probe is None:
            target = outers[0][0]
        else:
            point = Point(probe)
            inside = [c for c, poly in outers if poly.covers(point)] if covering else []
            target = inside[0] if inside else min(
                outers, key=lambda cp: cp[1].distance(point))[0]
        owned.setdefault(id(target), []).append(item)
    return owned


def _assign_loose(result: Result, outers) -> dict[int, list]:
    """id(cluster) → le curve sciolte che gli vanno, nell'ordine di
    `result.loose`: quelle col suo `cluster_ref`, e quelle che nessun
    cluster contiene se è la parte più vicina."""
    free = _assign([c for c in result.loose if c.cluster_ref is None],
                   outers, _probe_point, covering=False)
    target = {id(c): key for key, curves in free.items() for c in curves}
    owned: dict[int, list] = {}
    for curve in result.loose:
        key = (id(result.clusters[curve.cluster_ref]) if curve.cluster_ref is not None
               else target.get(id(curve)))
        if key is not None:
            owned.setdefault(key, []).append(curve)
    return owned


def _local(items: list, i: int) -> list:
    """Copie di `items` con `cluster_ref` riferito al Result di una parte sola."""
    out = []
    for item in items:
        local = copy.copy(item)
        local.cluster_ref = 0 if item.cluster_ref == i else None
        out.append(local)
    return out


def _relink(texts: list, cluster: Cluster, loose: list, local_loose: list) -> None:
    """Riporta `target`/`references` dei testi di una parte sugli elementi
    della parte: i contorni e le feature del cluster sono gli stessi oggetti,
    le curve sciolte sono copie. Il resto non sta nella parte (D177)."""
    own = {id(c): c for c in [cluster.outer, *cluster.inners]}
    if cluster.overlay is not None:
        own.update((id(item), item) for _, items in cluster.overlay.items() for item in items)
    own.update((id(orig), copy_) for orig, copy_ in zip(loose, local_loose))
    for text in texts:
        text.target = own.get(id(text.target)) if text.target is not None else None
        text.references = [own[id(r)] for r in text.references if id(r) in own]


def _probe_point(curve) -> Optional[tuple]:
    """Punto rappresentativo di una curva, per darla alla parte più vicina."""
    poly = curve_polygon(curve)
    if poly is not None:
        c = poly.representative_point()
        return (c.x, c.y)

    pts = track_points(getattr(curve, "segments", []) or [])
    if pts:
        mid = pts[len(pts) // 2]
        return (mid[0], mid[1])
    return None


def _outer_polygons(clusters) -> list:
    """(cluster, poligono dell'outer) per ogni cluster che ne ha uno."""
    return [
        (c, poly)
        for c in clusters
        if c.outer is not None
        for poly in [curve_polygon(c.outer)]
        if poly is not None
    ]
