

"""
topo_dxf/adapter.py
-------------------
Traduce entità DXF in primitive Topo.
UNICO punto di conversione DXF → primitive.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from ezdxf.colors import aci2rgb, int2rgb

# Solo nomi pubblici di topo: l'adapter è un consumer come un altro (MAP.md D125)
from topo.primitives import LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg
from topo.model import Edge, EdgeStyle, RoleRule, resolve_role

from .parser import DxfEntityDispatcher


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE', 'ELLIPSE'})

# Linetype "di sistema": non hanno una entry propria nella tabella o non
# portano un pattern (BYLAYER/BYBLOCK ereditano; CONTINUOUS è sempre presente
# in ogni documento ezdxf.new()). Nessun pattern da catturare per questi.
_STANDARD_LINETYPES = frozenset({'BYLAYER', 'BYBLOCK', 'CONTINUOUS'})


# ---------------------------------------------------------------------------
# Aspetto grezzo (linetype/colore) — Cluster E
# ---------------------------------------------------------------------------

def _raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]:
    """
    Pattern grezzo (lunghezza totale + tratti con segno, `+` = tratto,
    `-` = spazio) di un `Linetype` — lo stesso formato voluto da
    `doc.linetypes.add(name, pattern=[...])`.

    NON `Linetype.simplified_line_pattern()`: quello è un rendering per sola
    lettura, ha già perso i segni e la lunghezza totale (pensato per essere
    letto, non per essere ri-registrato) — ri-passarlo a `.add()` produce un
    pattern degenere (tutti tratti pieni, nessun vuoto).
    """
    pattern_length = 0.0
    elements = []
    for tag in lt_entry.pattern_tags.tags:
        if tag.code == 40:
            pattern_length = tag.value
        elif tag.code == 49:
            elements.append(tag.value)
    if len(elements) < 2:
        return None
    return (pattern_length, *elements)


def _color_rgb(aci: int, true_color: Optional[int]) -> Optional[Tuple[int, int, int]]:
    """Il colore effettivo in RGB: il true color se c'è, altrimenti l'indice
    ACI (1–255) col suo RGB canonico. BYBLOCK (0) e un BYLAYER non risolto
    (256) non dicono un colore: None (MAP.md D126)."""
    if true_color is not None:
        return tuple(int2rgb(true_color))
    if 1 <= aci <= 255:
        return tuple(aci2rgb(aci))
    return None


def _entity_style(entity) -> EdgeStyle:
    """
    Cattura l'aspetto EFFETTIVO (linetype/colore) di un'entità DXF in un
    `EdgeStyle` puro — quello che si vede davvero in CAD, non solo l'attributo
    grezzo dell'entità.

    Caso comune: il disegno mette lo stile sul LAYER, non sulla singola
    entità (`entity.dxf.linetype == "ByLayer"`) — il tratteggio vero vive
    nella entry del layer (`doc.layers.get(layer).dxf.linetype`), l'attributo
    dell'entità da solo non lo dice. Senza risolvere BYLAYER al valore del
    layer, ogni entità che eredita lo stile (il caso tipico) sfuggirebbe sia a
    `role_rules` sia al ripristino fedele in output (Cluster E):
    scritta su un layer topo diverso (Trash/Bending/...), che di default è
    continuo, perderebbe silenziosamente il tratteggio.

    Se il linetype risolto non è uno standard, ne risolve anche il pattern
    (durate dei tratti) dalla tabella del documento sorgente — l'unico
    momento in cui topo può ancora leggerla, prima che il riferimento a
    ezdxf sparisca (`model-is-provenance-free-edges`). Il pattern risolto
    viaggia come dato puro fino a write(), che lo ri-registra nel documento
    di output.
    """
    try:
        linetype = entity.dxf.linetype if entity.dxf.hasattr("linetype") else "BYLAYER"
    except Exception:
        linetype = "BYLAYER"

    try:
        color = entity.dxf.color if entity.dxf.hasattr("color") else 256
    except Exception:
        color = 256

    true_color = None
    try:
        if entity.dxf.hasattr("true_color"):
            true_color = entity.dxf.true_color
    except Exception:
        pass

    doc = None
    try:
        doc = entity.doc
    except Exception:
        pass

    layer_entry = None
    if doc is not None and (linetype.upper() == "BYLAYER" or (color == 256 and true_color is None)):
        try:
            layer_entry = doc.layers.get(entity.dxf.layer)
        except Exception:
            layer_entry = None

    if linetype.upper() == "BYLAYER" and layer_entry is not None:
        linetype = layer_entry.dxf.linetype

    if color == 256 and true_color is None and layer_entry is not None:
        color = layer_entry.dxf.color

    desc = ""
    pattern = None
    if linetype.upper() not in _STANDARD_LINETYPES:
        try:
            lt_entry = doc.linetypes.get(linetype) if doc is not None else None
            if lt_entry is not None:
                pattern = _raw_linetype_pattern(lt_entry)
                desc = lt_entry.dxf.description
        except Exception:
            pass

    # BYLAYER/BYBLOCK sono parole del DXF, non tipi di linea: se restano dopo
    # la risoluzione la sorgente non dice niente (D126)
    upper = linetype.upper()
    if upper in ("BYLAYER", "BYBLOCK"):
        linetype, dash = "", None
    elif upper == "CONTINUOUS":
        dash = ()
    else:
        # il pattern DXF apre con la lunghezza totale: il tratto sono i segni
        dash = tuple(pattern[1:]) if pattern else None
    return EdgeStyle(
        linetype=linetype,
        linetype_desc=desc,
        dash=dash,
        color=_color_rgb(color, true_color),
    )


# ---------------------------------------------------------------------------
# TRADUZIONE DXF → PRIMITIVE
# ---------------------------------------------------------------------------
# La traduzione entità DXF → primitiva vive in UN SOLO posto:
# `topo_dxf/parser.py::DxfEntityDispatcher` (MAP.md D7). Prima ce n'erano
# due copie quasi identiche — una qui (`entity_to_primitive`), una in parser.py.


def _segment_key(segment) -> tuple:
    """Chiave univoca per deduplicazione."""
    if isinstance(segment, LineSeg):
        pts = tuple(sorted((
            (round(segment.start[0], 6), round(segment.start[1], 6)),
            (round(segment.end[0], 6), round(segment.end[1], 6)),
        )))
        return ("LINE", pts)
    if isinstance(segment, ArcSeg):
        return (
            "ARC",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6),
            round(segment.start_angle, 6),
            round(segment.end_angle, 6),
            segment.ccw,
        )
    if isinstance(segment, SplineSeg):
        return (
            "SPLINE",
            int(segment.degree),
            tuple((round(x, 6), round(y, 6)) for x, y in segment.control_points),
            tuple(round(k, 9) for k in segment.knots),
            tuple(round(w, 9) for w in (segment.weights or [])),
            bool(segment.closed),
            bool(segment.periodic),
            int(segment.flags),
        )
    if isinstance(segment, CircleSeg):
        return (
            "CIRCLE",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6)
        )
    if isinstance(segment, EllipseSeg):
        return (
            "ELLIPSE",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.major_axis[0], 6),
            round(segment.major_axis[1], 6),
            round(segment.ratio, 6),
            round(segment.start_param, 6),
            round(segment.end_param, 6),
            segment.ccw,
        )
    return (type(segment).__name__, repr(segment))


# ---------------------------------------------------------------------------
# DxfAdapter
# ---------------------------------------------------------------------------

class DxfAdapter:
    """
    Adapter DXF che traduce entità DXF in Edge del dominio Topo.

    Il ruolo di ogni Edge viene da `role_rules` (D63), valutate sul nome del
    layer e sull'aspetto effettivo dell'entità: la prima che matcha vince,
    nessuna → `unknown`. Il layer non esce dall'adapter.
    """

    def __init__(
        self,
        msp,
        exclude_ids: Optional[set] = None,
        ignore_layers: Optional[set] = None,
        role_rules: Sequence[RoleRule] = (),
        skip_layers: Sequence[str] = (),
    ):
        self.msp = msp
        self.exclude_ids = exclude_ids or set()
        self.ignore_layers = ignore_layers or set()
        self.skip_layers = {s.lower() for s in skip_layers}
        self.role_rules = list(role_rules)

    def to_edges(self) -> List[Edge]:
        """Traduce entità DXF in Edge."""
        ignore = {s.lower() for s in self.ignore_layers}

        def _is_excluded(entity) -> bool:
            if id(entity) in self.exclude_ids:
                return True
            layer = (
                entity.dxf.layer.lower()
                if entity.dxf.hasattr("layer")
                else ""
            )
            if layer in self.skip_layers:
                return True
            if not ignore:
                return False
            return any(sl in layer for sl in ignore)

        edges = []
        seen_segment_keys = set()

        def _append_edge(role, segment, style=None):
            key = _segment_key(segment)
            if key in seen_segment_keys:
                return
            seen_segment_keys.add(key)
            edges.append(Edge.of(segment, role, style))

        for entity in self.msp:
            if _is_excluded(entity):
                continue

            dtype = entity.dxftype()
            label = (
                entity.dxf.layer
                if entity.dxf.hasattr("layer")
                else ""
            )
            style = _entity_style(entity)
            role = resolve_role(self.role_rules, label, style)

            # CIRCLE → CircleSeg (preservato!)
            if dtype == "CIRCLE":
                prim = DxfEntityDispatcher(entity).parse()
                if isinstance(prim, CircleSeg):
                    edges.append(Edge.of(prim, role, style))
                continue

            # LWPOLYLINE / POLYLINE → segmenti
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = DxfEntityDispatcher(entity).parse() or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                for segment in primitives:
                    _append_edge(role, segment, style=style)
                continue

            # LINE / ARC / SPLINE / ELLIPSE: una SPLINE o un'ELLIPSE chiusa è un
            # loop degenere come CIRCLE, e lo decide Edge.of, non il tipo DXF
            if dtype not in _SUPPORTED_TYPES:
                continue

            prim = DxfEntityDispatcher(entity).parse()
            if prim is None:
                continue

            edges.append(Edge.of(prim, role, style))

        return edges
