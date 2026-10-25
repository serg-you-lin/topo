"""
topo/tools/split.py
-------------------
Un Result per parte (MAP.md D124, D129). Scegliere le parti è una decisione
sul modello, non su un formato: quali cluster tenere (`min_area`), come si
chiamano (`namer` → `cluster.label`), quali curve sciolte e quali testi
viaggiano con ognuna. Ogni exporter scrive poi una parte nel suo formato
(`topo_dxf.to_dxf`, `topo.to_svg`, `topo.to_text`): lo stesso split esporta
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

DEFAULT_MIN_CLUSTER_AREA = 50.0  # mm²


def split(
    result: Result,
    namer: Optional[Callable[[int, Cluster], str]] = None,
    min_area: float = DEFAULT_MIN_CLUSTER_AREA,
) -> List[Result]:
    """
    Un `Result` per parte, nell'ordine delle parti tenute.

    Ogni parte è un `Result` con un solo cluster, le curve sciolte e i
    testi che le appartengono. Una curva va al cluster del suo
    `cluster_ref` (D137); un testo alla parte che lo contiene. Quelli
    che nessuna parte contiene vanno alla più vicina al suo contorno esterno
    fra TUTTE le parti (anche quelle scartate da `min_area`). Niente viene
    duplicato: ogni elemento sta in una parte sola, copiato con
    `cluster_ref` riferito alla parte (0 se il suo cluster la contiene,
    `None` altrimenti). Una curva promossa (`topo.promote`) sta già nel suo
    cluster. Gli altri campi del `Result` (sorgente, avvisi) sono copiati.

    `namer(i, cluster)` — se passato — assegna `cluster.label`, così il nome
    di un file resta ricavabile a valle (`f"{cluster.label}.dxf"`); senza,
    la parte i-esima è `f"{label}_P{i + 1}"`. Una parte sotto `min_area` mm²
    (`<= 0`: nessun filtro) è scartata con un avviso in `result.warnings`.

    Solleva `ValueError` se `result` non è valido: un file per parte non ha
    senso senza parti (D83).
    """
    if not result.is_valid:
        raise ValueError(
            "split(): il Result non è valido, nessun output generato. "
            + " ".join(result.errors)
        )

    outers = _outer_polygons(result.clusters)
    loose_of = _assign_loose(result, outers)
    texts_of = _assign(result.texts, outers, lambda a: a.position, covering=True)

    parts: List[Result] = []
    for i, cluster in enumerate(result.clusters):
        if not cluster_passes_min_area(cluster, min_area):
            result.warnings.append(
                f"Part {i} scartato: area {cluster.outer.area:.2f} mm² "
                f"sotto soglia {min_area} mm²"
            )
            continue

        cluster.label = namer(i, cluster) if namer else f"{cluster.label}_P{i + 1}"
        parts.append(replace(
            result,
            clusters=[cluster],
            loose=_local(loose_of.get(id(cluster), []), i),
            texts=_local(texts_of.get(id(cluster), []), i),
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
