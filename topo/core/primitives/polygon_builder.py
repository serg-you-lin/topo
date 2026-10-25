"""
core/primitives/polygon_builder.py
-----------------------------------
Funzione pura per costruire un Polygon shapely da una lista di primitive.

Zero dipendenze da ezdxf o qualsiasi formato specifico.
Chiamata dall'adapter DXF (e futuri adapter) — non la possiede.
"""

from __future__ import annotations

from typing import List, Optional

from shapely.geometry import Polygon

from . import LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg
from .segments import DEFAULT_TOLERANCE


def build_polygon(
    primitives: List[LineSeg | ArcSeg | BSplineSeg | CircleSeg | EllipseSeg],
    tolerance:  float = 0.01,
) -> Optional[Polygon]:
    """
    Costruisce un Polygon shapely da una lista di primitive geometriche.

    Ogni primitiva di topo si discretizza da sé (LineSeg, ArcSeg, CircleSeg,
    BSplineSeg, EllipseSeg).
    Restituisce None se la geometria non è valida o ha meno di 3 punti.
    """
    if not primitives:
        return None

    pts: list = []
    for i, prim in enumerate(primitives):
        seg_pts = prim.discretize(tolerance)
        if i == 0:
            pts.extend(seg_pts)
        else:
            pts.extend(seg_pts[1:])

    return _make_polygon(pts)


# ---------------------------------------------------------------------------
# Helper privato
# ---------------------------------------------------------------------------

def _make_polygon(pts: list) -> Optional[Polygon]:
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda p: p.area)
        return poly if not poly.is_empty else None
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Il poligono di una curva chiusa, per le operazioni fra curve
# ---------------------------------------------------------------------------

def curve_polygon(item) -> Optional[Polygon]:
    """
    Il poligono shapely di `item` per le domande fra più curve (contenimento,
    vicinanza, unioni — D166, D167): quello che la lettura gli ha dato, se
    c'è; per una curva chiusa senza, costruito una volta dai `segments` e
    tenuto sull'oggetto. None per una curva aperta. Solo uso interno: fuori
    da topo si passa da `topo.to_shapely`.
    """
    polygon = getattr(item, "polygon", None)
    if polygon is not None:
        return polygon
    from ...model.curve import ClosedCurve
    if isinstance(item, ClosedCurve) and item.segments:
        item.polygon = build_polygon(item.segments, DEFAULT_TOLERANCE)
        return item.polygon
    return None
