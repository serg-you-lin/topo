"""
topo/tools/split.py
-------------------
Un Result per parte (MAP.md D124, D129). Scegliere le parti è una decisione
sul modello, non su un formato: quali cluster tenere (`min_area`), come si
chiamano (`namer` → `cluster.label`), quali entità trash e quali annotazioni
viaggiano con ognuna. Ogni exporter scrive poi una parte nel suo formato
(`topo_dxf.to_dxf`, `topo.to_svg`, `topo.to_text`): lo stesso split esporta
parti in DXF, SVG o PDF.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, List, Optional

from shapely.geometry import Point

from ..core.geometry.measure import track_points
from ..model import Cluster, Result

DEFAULT_MIN_CLUSTER_AREA = 50.0  # mm²


def split(
    result: Result,
    namer: Optional[Callable[[int, Cluster], str]] = None,
    min_area: float = DEFAULT_MIN_CLUSTER_AREA,
) -> List[Result]:
    """
    Un `Result` per parte, nell'ordine delle parti tenute.

    Ogni parte è un `Result` con un solo cluster, le entità trash e le
    annotazioni che le appartengono: quelle che contiene o, se nessuna parte
    le contiene, quelle più vicine al suo contorno esterno fra TUTTE le parti
    (anche quelle scartate da `min_area`). Niente viene duplicato: ogni
    entità sta in una parte sola. Gli altri campi del `Result` (sorgente,
    avvisi) sono copiati.

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
    trash_of = _assign(result.trash_entities, outers, _trash_probe_point, covering=False)
    annotations_of = _assign(result.annotations, outers, lambda a: a.position, covering=True)

    parts: List[Result] = []
    for i, cluster in enumerate(result.clusters):
        if not cluster_passes_min_area(cluster, min_area):
            result.warnings.append(
                f"Part {i} scartato: area {cluster.outer.polygon.area:.2f} mm² "
                f"sotto soglia {min_area} mm²"
            )
            continue

        cluster.label = namer(i, cluster) if namer else f"{cluster.label}_P{i + 1}"
        parts.append(replace(
            result,
            clusters=[cluster],
            trash_entities=trash_of.get(id(cluster), []),
            annotations=annotations_of.get(id(cluster), []),
            warnings=list(result.warnings),
            errors=list(result.errors),
        ))
    return parts


def cluster_passes_min_area(cluster: Cluster, min_area: float) -> bool:
    """True se la parte supera la soglia di area minima (min_area <= 0 = nessun filtro)."""
    return not (min_area > 0 and cluster.outer.polygon.area < min_area)


def _assign(items, outers, probe_of, covering: bool) -> dict[int, list]:
    """
    id(cluster) → gli elementi che gli appartengono. Con `covering` vince la
    prima parte che contiene il punto, altrimenti la più vicina; senza, la
    più vicina e basta (il trash, che sta fuori dalle parti per definizione).
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


def _trash_probe_point(trash) -> Optional[tuple]:
    """Punto rappresentativo di un'entità trash, per assegnarla a una parte."""
    poly = getattr(trash, "polygon", None)
    if poly is not None:
        c = poly.representative_point()
        return (c.x, c.y)

    pts = track_points(getattr(trash, "segments", []) or [])
    if pts:
        mid = pts[len(pts) // 2]
        return (mid[0], mid[1])
    return None


def _outer_polygons(clusters) -> list:
    """(cluster, poligono dell'outer) per ogni cluster che ne ha uno."""
    return [
        (c, c.outer.polygon)
        for c in clusters
        if c.outer is not None and c.outer.polygon is not None
    ]
