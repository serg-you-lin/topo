"""
topo_dxf/parser.py
------------------
Traduce entità ezdxf in primitive geometriche pure (LineSeg, ArcSeg, BSplineSeg).
Unico file che conosce ezdxf e il formato bulge DXF per il parsing.
"""

from __future__ import annotations

import math
from typing import List

from topo.primitives import LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class DxfEntityDispatcher:
    """Centralizza il routing per tipo di entità DXF."""

    def __init__(self, entity):
        self.entity = entity
        self.kind = entity.dxftype()

    def parse(self, rev: bool = False, has_spline: bool = False):
        if self.kind == "LINE":
            return _parse_line(self.entity, rev)[0]
        if self.kind == "ARC":
            return _parse_arc(self.entity, rev)
        if self.kind == "SPLINE":
            return _parse_spline(self.entity, rev)
        if self.kind in ("LWPOLYLINE", "POLYLINE"):
            return _parse_polyline(self.entity, rev)
        if self.kind == "CIRCLE":
            return _parse_circle(self.entity)
        if self.kind == "ELLIPSE":
            return _parse_ellipse(self.entity, rev)
        return None


# ---------------------------------------------------------------------------
# Parsing ezdxf → primitive
# ---------------------------------------------------------------------------

def _parse_line(entity, rev) -> tuple:
    if rev:
        start = (entity.dxf.end.x,   entity.dxf.end.y)
        end   = (entity.dxf.start.x, entity.dxf.start.y)
    else:
        start = (entity.dxf.start.x, entity.dxf.start.y)
        end   = (entity.dxf.end.x,   entity.dxf.end.y)
    return LineSeg(start=start, end=end), end


def _parse_arc(entity, rev) -> ArcSeg:
    cx = entity.dxf.center.x
    cy = entity.dxf.center.y
    r  = entity.dxf.radius
    sa = math.radians(entity.dxf.start_angle)
    ea = math.radians(entity.dxf.end_angle)

    ccw = True
    if rev:
        sa, ea = ea, sa
        ccw = False

    return ArcSeg(center=(cx, cy), radius=r, start_angle=sa, end_angle=ea, ccw=ccw)


def _parse_spline(entity, rev) -> BSplineSeg:
    """
    Solo la geometria (MAP.md D135): grado, punti di controllo, nodi, pesi
    così come sono scritti. Una SPLINE data per soli fit points (e tangenti),
    o senza nodi, diventa punti di controllo e nodi qui, con la stessa
    costruzione del CAD.
    """
    try:
        if entity.control_point_count() and len(entity.knots):
            seg = BSplineSeg(
                degree=int(entity.dxf.degree),
                control_points=[(float(p[0]), float(p[1])) for p in entity.control_points],
                knots=[float(k) for k in entity.knots],
                weights=[float(w) for w in entity.weights] if len(entity.weights) else None,
            )
        else:
            bs = entity.construction_tool()
            seg = BSplineSeg(
                degree=int(bs.degree),
                control_points=[(float(p[0]), float(p[1])) for p in bs.control_points],
                knots=[float(k) for k in bs.knots()],
                weights=[float(w) for w in bs.weights()] if bs.is_rational else None,
            )
    except Exception:
        seg = BSplineSeg(degree=int(getattr(entity.dxf, "degree", 3) or 3),
                         control_points=[], knots=[])
    return seg.reversed() if rev else seg


def _parse_circle(entity) -> CircleSeg:
    return CircleSeg(
        center=(entity.dxf.center.x, entity.dxf.center.y),
        radius=entity.dxf.radius
    )


def _parse_ellipse(entity, rev) -> EllipseSeg:
    """
    Un'ELLIPSE DXF è sempre percorsa CCW da `start_param` a `end_param`
    (nessun flag di verso nel gruppo, come per ARC) — `rev` inverte gli
    stessi due parametri e nega `ccw`, stesso trattamento di `_parse_arc`.
    Un'ellisse piena ha `start_param=0`/`end_param=2π` (default di ezdxf).
    """
    seg = EllipseSeg(
        center=(entity.dxf.center.x, entity.dxf.center.y),
        major_axis=(entity.dxf.major_axis.x, entity.dxf.major_axis.y),
        ratio=entity.dxf.ratio,
        start_param=entity.dxf.start_param,
        end_param=entity.dxf.end_param,
        ccw=True,
    )
    return seg.reversed() if rev else seg


def _parse_polyline(entity, rev) -> list:
    if entity.dxftype() == "POLYLINE":
        points = [
            (v.dxf.location.x, v.dxf.location.y, getattr(v.dxf, "bulge", 0.0))
            for v in entity.vertices
        ]
    else:
        points = list(entity.get_points('xyb'))

    if not points:
        return []

    is_closed = bool(
        getattr(entity, "is_closed", False) or getattr(entity, "closed", False)
    )

    # Polilinea chiusa con vertice di chiusura esplicito (primo == ultimo):
    # scartalo, altrimenti il ciclo `%n` genera un segmento di lunghezza nulla.
    if is_closed and len(points) > 1:
        if (points[0][0], points[0][1]) == (points[-1][0], points[-1][1]):
            points = points[:-1]

    # Semplice reversal: inverte tutto e basta
    if rev:
        points = list(reversed(points))

    primitives = []
    n = len(points)
    edge_count = n if is_closed else max(0, n - 1)
    
    for i in range(edge_count):
        x1, y1, bulge = points[i]
        if is_closed:
            x2, y2, _ = points[(i + 1) % n]
        else:
            x2, y2, _ = points[i + 1]
        
        if abs(bulge) > 1e-9:
            primitives.append(ArcSeg.from_chord(start=(x1, y1), end=(x2, y2), bulge=bulge))
        else:
            primitives.append(LineSeg(start=(x1, y1), end=(x2, y2)))
    return primitives