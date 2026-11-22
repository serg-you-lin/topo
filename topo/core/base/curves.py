"""
topo/core/base/curves.py
------------------------
Da giri ed edge a curve del modello, per ogni lettura (D187, D189): un giro
diventa un contorno chiuso, o le sue curve aperte se non racchiude niente
(D151); quello che nessun contorno prende va in `loose` con una regola sola
(D162), ruolo intatto. Niente si perde: un edge chiuso da solo esce chiuso.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import List, Optional

from shapely.geometry import Polygon

from ..geometry.integrals import ring_area
from ..geometry.measure import SAME_POINT, segment_length
from ..geometry.polygons import with_polygon
from ..geometry.rings import ring_scale
from ..primitives import LineSeg
from ..primitives.mathseg import segment_is_closed
from ..topology.edge import Edge
from ..topology.loops import loop_geometry
from ...model.curve import ClosedCurve, OpenCurve
from ...model.role import ContourRole
from .refit import chain_runs


def loop_to_closed_curve(
    loop,
    role: ContourRole = ContourRole.UNKNOWN,
    polygon=None,
    segments: list = None,
    styles: list = None,
) -> Optional[ClosedCurve]:
    from ..topology.loops import loop_points

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
        # largo in media meno di SAME_POINT (2·area/perimetro): i due lati
        # sono lo stesso tratto, non c'è un contorno (D279)
        if not segments or 2 * ring_area(segments) <= SAME_POINT * ring_scale(segments):
            return None

        return with_polygon(ClosedCurve(role=role, segments=segments, styles=styles or []), poly)
    except Exception:
        return None


def loops_to_curves(loops: List[list]) -> List[ClosedCurve | OpenCurve]:
    """
    Un ClosedCurve per loop, col ruolo del primo edge. Un loop che non fa un
    contorno (poligono nullo, largo meno di SAME_POINT, D279) torna come un
    OpenCurve per edge, così finisce in `loose` invece di sparire (D151).
    """
    curves = []
    for loop in loops:
        role = loop[0][0].role if loop else ContourRole.UNKNOWN
        geometry = loop_geometry(loop)
        curve = None
        if geometry is not None:
            segments, styles, polygon = geometry
            curve = loop_to_closed_curve(loop, role=role, polygon=polygon, segments=segments,
                                         styles=styles)
        if curve is not None:
            curves.append(curve)
        else:
            curves += _open(edge for edge, _ in loop)
    return curves


def loose_curves(edges: List[Edge]) -> list:
    """Le curve di `loose` (D162): un pezzo che chiude da sé — un segmento
    chiuso, o una catena in cui ogni nodo ha grado 2 — è un ClosedCurve,
    perché non c'è niente da scegliere; il resto un OpenCurve per edge. Il
    ruolo di ogni edge resta il suo."""
    edges = list(edges)
    single = [e for e in edges if e.segment is not None and segment_is_closed(e.segment)]
    rest = [e for e in edges if not (e.segment is not None and segment_is_closed(e.segment))]
    rings = [[(e, False)] for e in single] + [path for path, closed in chain_runs(rest) if closed]
    ringed = {id(e) for ring in rings for e, _ in ring}
    return loops_to_curves(rings) + _open(e for e in rest if id(e) not in ringed)


def _open(edges) -> List[OpenCurve]:
    """Un OpenCurve per edge col suo segmento nativo, anche se chiuso da solo
    (un cerchio scartato non è un contorno). Esclusi solo i tratti di
    lunghezza nulla."""
    curves = []
    for edge in edges:
        seg = edge.segment or LineSeg(start=edge.start, end=edge.end)
        if segment_length(seg) > 0:
            curves.append(OpenCurve(role=edge.role, segments=[seg], styles=[edge.style]))
    return curves
