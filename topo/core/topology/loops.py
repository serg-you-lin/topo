"""
core/topology/loops.py
----------------------
From a loop [(edge, reversed)] to its segments, styles, points and polygon,
and the Edges no loop takes into open curves. The loops are found by the faces
of the planar network (`outer_face.face_loops`).
"""

from typing import Optional, Tuple

from shapely.geometry import Polygon

from ..geometry.shapely_polygons import build_polygon
from ..primitives.mathseg import DEFAULT_TOLERANCE
from .graph import _edge_coords


def loop_points(loop: list) -> list:
    """The points of a loop [(edge, reversed)], concatenated without repeating the
    junction nodes."""
    pts = []
    for edge, rev in loop:
        coords = _edge_coords(edge, rev)
        if not coords:
            continue
        if not pts:
            pts.extend(coords)
        elif coords[0] == pts[-1]:
            pts.extend(coords[1:])
        else:
            pts.extend(coords)
    return pts


def segments_from_loop(loop) -> list:
    """Native segments of a loop, oriented in the direction of travel.

    It parses NOTHING: every Edge already carries its primitive (`edge.segment`,
    translated by the adapter at load). Here it is taken, reversed with
    `.reversed()` if the Edge is walked backwards in the loop, and concatenated.
    Pure domain logic."""
    out = []
    for edge, rev in loop:
        seg = edge.segment
        if seg is None:
            continue
        if isinstance(seg, list):
            # In production a loop Edge never carries a list (polylines are already exploded
            # into single Edges): branch for the tests.
            out.extend(seg)
        else:
            out.append(seg.reversed() if rev else seg)
    return out


def edge_styles_from_loop(loop) -> list:
    """Raw styles (linetype/colour) of a loop, aligned 1:1 with
    `segments_from_loop(loop)` — same order, same expansion for the test Edges
    carrying a list of segments. The style does not depend on the direction of
    travel: unlike the native segment it is never reversed."""
    out = []
    for edge, _rev in loop:
        seg = edge.segment
        if seg is None:
            continue
        if isinstance(seg, list):
            out.extend([edge.style] * len(seg))
        else:
            out.append(edge.style)
    return out


def loop_geometry(loop) -> Optional[Tuple[list, list, Polygon]]:
    """(segments, styles, polygon) of a loop; None if the segments do not close a
    valid polygon."""
    segments = segments_from_loop(loop)
    polygon = build_polygon(segments, DEFAULT_TOLERANCE)
    if polygon is None:
        return None
    return segments, edge_styles_from_loop(loop), polygon


# --- Edge → OpenCurve — traces not consumed by structural loops ---

