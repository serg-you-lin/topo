"""
topo_pdf/graph_adapter.py
-------------------------
Traduce entità vettoriali sanificate del PDF in Edge topologici per il core.
"""

# Solo nomi pubblici di topo: l'adapter è un consumer come un altro (MAP.md D125)
from topo.model import ContourRole, Edge
from topo.primitives import LineSeg, SplineSeg


def map_sanitized_item_to_edge(item: tuple, page_idx: int) -> Edge | list[Edge] | None:
    cmd = item[0]

    if cmd == "l":
        p1, p2 = item[1], item[2]
        return Edge.of(LineSeg(start=p1, end=p2), ContourRole.UNKNOWN)

    elif cmd in ("re", "qu"):
        pts = item[1]
        # poligono chiuso → segmenti separati
        return [
            Edge.of(LineSeg(start=pts[i], end=pts[(i + 1) % len(pts)]), ContourRole.UNKNOWN)
            for i in range(len(pts))
        ]

    elif cmd == "c_poly":
        pts = item[1]
        return Edge.of(SplineSeg(degree=3, control_points=pts, knots=[]), ContourRole.UNKNOWN)

    return None
