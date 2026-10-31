"""
topo/core/topology/loop_finder.py
---------------------------------
Da un giro [(edge, al contrario)] ai suoi segmenti, stili, punti e poligono,
e gli Edge che nessun giro prende in curve aperte. I giri li trovano le facce
della rete piana (`outer_face.face_loops`, D189).
"""

from typing import Optional, Tuple

from shapely.geometry import Polygon

from ..primitives.polygon_builder import build_polygon
from ..primitives.segments import DEFAULT_TOLERANCE
from .graph import _edge_coords


def loop_points(loop: list) -> list:
    """I punti di un giro [(edge, al contrario)], concatenati senza ripetere i
    nodi di giunzione."""
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
    """
    Segmenti nativi di un loop, orientati nel verso di percorrenza.

    NON parsa niente: ogni Edge porta già la sua primitiva (`edge.segment`,
    tradotta dall'adapter al load). Qui la si prende, la si inverte con
    `.reversed()` se l'Edge è percorso al contrario nel loop, e la si
    concatena. Logica di dominio pura — nessuna dipendenza da ezdxf.

    (Ex `adapters/dxf/parser.py::parse_loop` — spostata qui e rinominata,
    MAP.md D6: non apparteneva all'adapter e il nome era fuorviante.)
    """
    out = []
    for edge, rev in loop:
        seg = edge.segment
        if seg is None:
            continue
        if isinstance(seg, list):
            # In produzione un Edge di loop non porta mai una lista (le
            # polilinee sono già esplose in Edge singoli): ramo per i test.
            out.extend(seg)
        else:
            out.append(seg.reversed() if rev else seg)
    return out


def edge_styles_from_loop(loop) -> list:
    """
    Stili grezzi (linetype/colore) di un loop, allineati 1:1 con
    `segments_from_loop(loop)` — stesso ordine, stessa espansione per gli Edge
    di test che portano una lista di segmenti. Lo stile non dipende dal verso
    di percorrenza: a differenza del segmento nativo non va mai invertito.
    """
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
    """(segmenti, stili, poligono) di un loop; None se i segmenti non chiudono
    un poligono valido."""
    segments = segments_from_loop(loop)
    polygon = build_polygon(segments, DEFAULT_TOLERANCE)
    if polygon is None:
        return None
    return segments, edge_styles_from_loop(loop), polygon


# ---------------------------------------------------------------------------
# Edge → OpenCurve — tracce non consumate da loop strutturali
# ---------------------------------------------------------------------------

