"""
topo/tools/split.py
-------------------
One Result per part. Choosing the parts is a decision on the model, not on a
format: which clusters to keep (`min_area`), what they are called (`namer` →
`cluster.label`), which loose curves and which texts travel with each. Every
exporter then writes a part in its format (an adapter's writer,
`topo.experimental.to_svg`): the same split exports parts in every format.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Callable, List, Optional

from shapely.geometry import Point

from ..core.geometry.measure import track_points
from ..core.geometry.shapely_polygons import curve_polygon
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
    `cluster_ref`; a text goes to the part that contains it. Those
    that no part contains go to the part closest to its outer contour among
    ALL the parts (including those discarded by `min_area`). Nothing is
    duplicated: every element lives in one part only, copied with
    `cluster_ref` referring to the part (0 if its cluster contains it,
    `None` otherwise). A promoted curve (`result.promote`) is already in its
    cluster. The other `Result` fields (source, warnings) are copied.

    `namer(i, cluster)` — if given — returns the `label` of the part's
    cluster, so a file name can be derived downstream
    (`f"{cluster.label}.svg"`); without it, the i-th part is
    `f"{label}_P{i + 1}"`. By default it discards nothing: a part
    below `min_area` (mm²; `<= 0`: no filter) is discarded
    with a warning in `result.warnings` and in those of every part: even if
    it discards them all, the discard can be read.

    **Mutates** only `result.warnings`: a part's cluster is a copy
    with its own `label`, the original does not change.

    Raises `ValueError` if `result` is not valid: one file per part makes no
    sense without parts.
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
            "dropped-part", f"{plural(len(dropped), 'part', 'parts')} dropped, area under min_area {min_area:g} mm²",
            points=[c.outer.segments[0].endpoints()[0] for c in dropped],
            notes=[f"smallest {min(c.outer.area for c in dropped):.4g} mm², largest {max(c.outer.area for c in dropped):.4g} mm²"],
            help="topo.split(result) keeps every part (min_area=0.0, the default)"))
    parts: List[Result] = []
    for i in kept:
        cluster = result.clusters[i]
        label = namer(i, cluster) if namer else f"{cluster.label}_P{i + 1}"
        loose = _local(loose_of.get(id(cluster), []), i)
        texts = _local(texts_of.get(id(cluster), []), i)
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
    """True if the part exceeds the minimum area threshold (min_area <= 0 = no filter)."""
    return not (min_area > 0 and cluster.outer.area < min_area)


def _assign(items, outers, probe_of, covering: bool) -> dict[int, list]:
    """id(cluster) → the elements that belong to it. With `covering` the first part
    containing the point wins, otherwise the nearest; without, the nearest only.
    An element with no representative point goes to the first part."""
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
    """id(cluster) → the loose curves that go to it, in the order of `result.loose`:
    those with its `cluster_ref`, and those no cluster contains if it is the
    nearest part."""
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
    """Copies of `items` with `cluster_ref` referring to the Result of a single part."""
    out = []
    for item in items:
        local = copy.copy(item)
        local.cluster_ref = 0 if item.cluster_ref == i else None
        out.append(local)
    return out


def _probe_point(curve) -> Optional[tuple]:
    """Representative point of a curve, to give it to the nearest part."""
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
    """(cluster, polygon of the outer) for every cluster that has one."""
    return [
        (c, poly)
        for c in clusters
        if c.outer is not None
        for poly in [curve_polygon(c.outer)]
        if poly is not None
    ]
