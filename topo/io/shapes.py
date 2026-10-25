"""
topo/io/shapes.py
-----------------
`to_shapely`: la geometria di topo come oggetti shapely, per chi ha bisogno di
overlay, buffer o WKT (MAP.md D166). Una conversione esplicita, come un
formato: il modello non espone tipi shapely, li costruisce questa funzione.
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union

from ..core.geometry.measure import track_points
from ..core.primitives.polygon_builder import build_polygon, curve_polygon
from ..core.primitives.segments import DEFAULT_TOLERANCE
from ..model import Cluster, OpenCurve


def to_shapely(item, tolerance: Optional[float] = None):
    """
    Convert topo geometry to a shapely object (MAP.md D166).

    - a closed curve (`Contour`, a `ClosedCurve` in `loose`, or anything
      with a closed ring of `segments`) → `Polygon`;
    - an `OpenCurve` → `LineString`;
    - a `Cluster` → its material by the even-odd rule of `area` (D89): the
      outer with its depth-1 holes, every depth-2 island with its depth-3
      holes, and so on, minus the overlay voids → `Polygon`, or
      `MultiPolygon` when islands sit inside holes.

    `tolerance=None` gives the polygon the reading itself used (the same
    vertices topo's own containment tests see); a number rebuilds it from
    the `segments` within that tolerance. `ValueError` if the segments
    enclose no valid polygon, `TypeError` if `item` carries no geometry.
    """
    if isinstance(item, Cluster):
        return _cluster(item, tolerance)
    segments = getattr(item, "segments", None)
    if not segments:
        raise TypeError(f"to_shapely(): {type(item).__name__} non porta `segments`")
    if isinstance(item, OpenCurve):
        return LineString(track_points(segments, tolerance or DEFAULT_TOLERANCE))
    return _ring(item, tolerance)


def _ring(item, tolerance: Optional[float]) -> Polygon:
    polygon = curve_polygon(item) if tolerance is None else None
    if polygon is None:
        polygon = build_polygon(list(item.segments), tolerance or DEFAULT_TOLERANCE)
    if polygon is None:
        raise ValueError("to_shapely(): i segmenti non racchiudono un poligono valido")
    return polygon


def _cluster(cluster: Cluster, tolerance: Optional[float]):
    """Pari-dispari sulla gerarchia: ogni contorno a depth pari è un guscio,
    i suoi figli a depth dispari i suoi buchi."""
    contours = [cluster.outer] + list(cluster.inners)
    pieces = []
    for shell in contours:
        if shell.depth % 2:
            continue
        holes = [c for c in cluster.inners
                 if c.depth == shell.depth + 1 and (c.parent or cluster.outer) is shell]
        outline = _ring(shell, tolerance)
        pieces.append(Polygon(outline.exterior.coords,
                              [_ring(h, tolerance).exterior.coords for h in holes]))
    material = unary_union(pieces)
    voids = [_ring(v, tolerance) if getattr(v, "segments", None) else v.polygon
             for v in cluster.overlay_voids]
    if voids:
        material = material.difference(unary_union(voids))
    if isinstance(material, (Polygon, MultiPolygon)):
        return material
    return MultiPolygon([g for g in getattr(material, "geoms", []) if isinstance(g, Polygon)])
