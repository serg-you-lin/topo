"""
topo/core/geometry/shapely_polygons.py
--------------------------------------
The bridge to shapely: the Polygon of a list of primitives or of a closed
curve, and its cache on the curve. While shapely stays, it lives here.
"""

from __future__ import annotations

from typing import List, Optional

from shapely.geometry import Polygon

from ..primitives.mathseg import DEFAULT_TOLERANCE, MathSeg


def build_polygon(
    primitives: List[MathSeg],
    tolerance:  float = DEFAULT_TOLERANCE,   # = topo.precision.SAME_POINT
) -> Optional[Polygon]:
    """Build a shapely Polygon from a list of geometric primitives.

    Every topo primitive discretizes itself (`MathSeg.discretize`). Returns None
    if the geometry is not valid or has fewer than 3 points."""
    if not primitives:
        return None

    pts: list = []
    for i, prim in enumerate(primitives):
        seg_pts = prim.discretize(tolerance=tolerance)
        if i == 0:
            pts.extend(seg_pts)
        else:
            pts.extend(seg_pts[1:])

    return _make_polygon(pts)


# --- Private helper ---

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



# --- The polygon of a closed curve, for operations between curves ---

def curve_polygon(item) -> Optional[Polygon]:
    """The shapely polygon of `item` for questions between several curves
    (containment, proximity, unions): the one the reading gave it, if any; for a
    closed curve without one, built once from the `segments` and kept on the
    object. None for an open curve. Internal use only: outside topo go through
    `topo.to_shapely`."""
    polygon = getattr(item, "_polygon", None)
    if polygon is not None:
        return polygon
    from ...model.curve import ClosedCurve
    # a closed curve, or an empty of the overlay: the segments close a loop
    closed = isinstance(item, ClosedCurve) or getattr(item, "is_void", False)
    if not closed or not getattr(item, "segments", None):
        return None
    polygon = build_polygon(list(item.segments), DEFAULT_TOLERANCE)
    try:
        item._polygon = polygon
    except AttributeError:      # an immutable overlay element: no cache
        pass
    return polygon


def with_polygon(curve, polygon):
    """`curve` with the polygon the reading built for it (merged with the planar
    network, or with the buffer(0) of a dirty ring): `curve_polygon` will give
    that, instead of rebuilding from the `segments`. Returns `curve`."""
    curve._polygon = polygon
    return curve
