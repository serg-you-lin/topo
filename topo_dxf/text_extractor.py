"""
topo_dxf/text_extractor.py
--------------------------
Reads the text entities of a DXF modelspace (TEXT, MTEXT, DIMENSION, LEADER,
MULTILEADER) and translates them into ``topo.model.Text``.

It is for texts what ``DxfAdapter.to_edges()`` is for geometry: the only point
where DXF texts are read. After ``extract()`` the source modelspace is no
longer needed.

Task: format knowledge only — where the text is, how a dimension's anonymous
block is flattened, what ``<>`` means. It does NOT decide what a text means:
that is for ``anchor_texts()`` and the consumers.

Handled types: TEXT, MTEXT, DIMENSION, LEADER, MULTILEADER.
It does not handle INSERT — they are assumed already exploded by load_dxf().

DIMENSION / LEADER / MULTILEADER have no "own" geometry in the DXF fields:
their image (measure lines, leaders, arrows, text) is in an anonymous block
expandable with ``virtual_entities()``. We flatten it here into pure
primitives and keep it in ``Text.rendered`` (RenderedGeometry), so ``write()``
re-materializes it faithful to the original.
"""

from __future__ import annotations

from topo.precision import SAME_POINT
import re
from typing import List, Optional, Sequence, Tuple

from topo.model import (
    Text, RenderedGeometry, RenderedText, RoleRule, resolve_role,
    MeasuredDistance, MeasuredRadius, MeasuredDiameter, MeasuredAngle,
)
from ezdxf.tools.text import plain_mtext

from .mtext import clean_mtext, mleader_text

TEXT_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"})

# Maximum chord error to discretize arcs/curves (mm).
_ARC_SAGITTA = SAME_POINT


class DxfTextExtractor:
    """Translate the text entities of a msp into list[Text]."""

    def __init__(self, msp, role_rules: Sequence[RoleRule] = ()):
        self.msp = msp
        self.role_rules = list(role_rules)

    def extract(self) -> List[Text]:
        out: List[Text] = []
        for entity in self.msp:
            if entity.dxftype() not in TEXT_TYPES:
                continue
            text = _to_text(entity, self.role_rules)
            if text is not None:
                out.append(text)
        return out


def _to_text(entity, role_rules: Sequence[RoleRule] = ()) -> Optional[Text]:
    kind = entity.dxftype()
    # The role from the same rules as the edges, on the layer name: only those on
    # the name count, a text's appearance is not read. The layer stays here.
    role = resolve_role(role_rules, entity.dxf.get("layer", "0"))

    if kind in ("TEXT", "MTEXT"):
        content = _extract_content(entity)
        placement = text_placement(entity)
        if not content or placement is None:
            return None
        pos, halign, valign = placement
        dxf = entity.dxf
        raw_h = dxf.get("char_height", 2.5) if kind == "MTEXT" else dxf.get("height", 2.5)
        return Text(
            position=pos,
            role=role,
            text=content,
            height=_f(raw_h) or 2.5,
            rotation=_f(dxf.get("rotation", 0.0)) or 0.0,
            halign=halign,
            valign=valign,
            width_factor=_width_factor(entity),
        )

    pos = text_anchor(entity)

    if kind == "DIMENSION":
        return _dimension_text_of(entity, pos, role)

    if kind in ("LEADER", "MULTILEADER"):
        return _leader_text(entity, pos, role)

    return None


# --- Anchor point — where `write` repositions the text ---

# Attachment point of an MTEXT (group 71, 1..9) → (halign, valign). MTEXT has no
# baseline: the bottom row is `bottom`.
_MTEXT_ALIGN = {
    1: ("left", "top"), 2: ("center", "top"), 3: ("right", "top"),
    4: ("left", "center"), 5: ("center", "center"), 6: ("right", "center"),
    7: ("left", "bottom"), 8: ("center", "bottom"), 9: ("right", "bottom"),
}
# Alignment of a TEXT (ezdxf `TextEntityAlignment`) → (halign, valign).
_TEXT_ALIGN = {
    "LEFT": ("left", "baseline"), "CENTER": ("center", "baseline"),
    "RIGHT": ("right", "baseline"), "MIDDLE": ("center", "center"),
    "ALIGNED": ("center", "baseline"), "FIT": ("center", "baseline"),
    "BOTTOM_LEFT": ("left", "bottom"), "BOTTOM_CENTER": ("center", "bottom"),
    "BOTTOM_RIGHT": ("right", "bottom"), "MIDDLE_LEFT": ("left", "center"),
    "MIDDLE_CENTER": ("center", "center"), "MIDDLE_RIGHT": ("right", "center"),
    "TOP_LEFT": ("left", "top"), "TOP_CENTER": ("center", "top"),
    "TOP_RIGHT": ("right", "top"),
}


def text_placement(entity) -> Optional[Tuple[Tuple[float, float], str, str]]:
    """(point, halign, valign) of a TEXT/MTEXT: the point to which the source hooks
    the string and how the string sits around it.

    MTEXT: the insertion point with its attachment. TEXT: the insertion if
    left-aligned on the baseline, otherwise the alignment point (group 11, the one
    the CAD respects); ALIGNED/FIT lie between the two points, and the anchor is
    their midpoint. None without a point."""
    t = entity.dxftype()
    if t == "MTEXT":
        ins = entity.dxf.get("insert")
        if ins is None:
            return None
        halign, valign = _MTEXT_ALIGN.get(entity.dxf.get("attachment_point", 1), ("left", "top"))
        return (float(ins[0]), float(ins[1])), halign, valign
    try:
        align, p1, p2 = entity.get_placement()
    except Exception:
        return None
    name = align.name
    halign, valign = _TEXT_ALIGN[name]
    if name == "LEFT" or p2 is None:
        p = p1
    elif name in ("ALIGNED", "FIT"):
        p = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    else:
        p = p2
    if p is None:
        return None
    return (float(p[0]), float(p[1])), halign, valign


def text_anchor(entity) -> Optional[Tuple[float, float]]:
    """XY anchor point of a dimension or a callout.

    MULTILEADER and DIMENSION keep it in nested structures; LEADER has none and
    falls back (then it is derived from the flattened geometry). Returns None if
    no source is available."""
    t = entity.dxftype()
    if t == "MULTILEADER":
        return _mleader_anchor(entity)
    if t == "DIMENSION":
        return _dimension_anchor(entity)
    return _fallback_anchor(entity)


def _mleader_anchor(entity) -> Optional[Tuple[float, float]]:
    """First vertex of the leader of a MULTILEADER."""
    try:
        leader = entity.context.mleader
        if leader and leader.vertices:
            v = leader.vertices[0]
            return (v[0], v[1])
    except Exception:
        pass
    return None


def _dimension_anchor(entity) -> Optional[Tuple[float, float]]:
    """Def-point of a DIMENSION."""
    try:
        return (entity.dxf.defpoint.x, entity.dxf.defpoint.y)
    except Exception:
        return None


def _fallback_anchor(entity) -> Optional[Tuple[float, float]]:
    """Cerca un qualsiasi attributo-punto usabile."""
    for attr in ("center", "insert", "start", "defpoint"):
        if hasattr(entity.dxf, attr):
            try:
                pt = getattr(entity.dxf, attr)
                return (pt.x, pt.y)
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# TEXT / MTEXT — testo semplice
# ---------------------------------------------------------------------------

def _extract_content(entity) -> str:
    """Clean text of the entity, empty string if it has none."""
    t = entity.dxftype()
    if t == "TEXT":
        # edge spaces included: the text's anchor counts them
        raw = entity.dxf.get("text", "") or ""
        return raw if raw.strip() else ""
    if t == "MTEXT":
        return clean_mtext(entity.text)
    return ""


def _width_factor(entity) -> float:
    """Effective horizontal stretch of the text (1.0 = none).

    TEXT carries its own override (DXF group 41) that wins if it is not the
    neutral default; MTEXT has no usable per-entity equivalent (its group 41 is
    the column width, not the glyph stretch) — in that case, and when TEXT has no
    explicit override, the value is read from the STYLE assigned to the entity
    (where SolidWorks title blocks, say, really keep the condensation)."""
    if entity.dxftype() == "TEXT":
        try:
            own = float(entity.dxf.get("width", 1.0))
        except (TypeError, ValueError):
            own = 1.0
        if own != 1.0:
            return own

    try:
        style = entity.doc.styles.get(entity.dxf.get("style", "Standard"))
        return float(style.dxf.width)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# DIMENSION
# ---------------------------------------------------------------------------

def _dimension_text_of(entity, pos, role: str) -> Optional[Text]:
    rendered = _render_block(entity)
    override = _dimension_override(entity)
    measures = dimension_measures(entity)

    if rendered.is_empty():
        return _bare_dimension(entity, pos, role, _shown_text(override, rendered), measures)

    if pos is None:
        pos = _bbox_center(
            rendered.strokes + rendered.fills + [[t.position] for t in rendered.texts]
        )
        if pos is None:
            return None

    return Text(
        role=role,
        text=_shown_text(override, rendered),
        rendered=rendered,
        measures=measures,
        **_on_string(rendered, pos),
    )


def _bare_dimension(entity, pos, role: str, text: str, measures) -> Optional[Text]:
    """Dimension with no block (the way QCAD writes them): the file draws nothing of
    it, not even the number. The file's string with the open ``<>`` remains,
    centred on the text midpoint (code 11), and what it measures. Without that
    point `pos` stays."""
    if not text.strip():
        return None
    tm = entity.dxf.get("text_midpoint")
    if tm is not None:
        return Text(position=(float(tm[0]), float(tm[1])), text=text, role=role,
                    halign="center", valign="center", measures=measures)
    if pos is None:
        return None
    return Text(position=pos, text=text, role=role, measures=measures)


def dimension_measures(entity):
    """What a DIMENSION measures, with the file's definition points: linear/aligned →
    `MeasuredDistance`, radius → `MeasuredRadius`, diameter → `MeasuredDiameter`,
    angular between two lines → `MeasuredAngle`. None for the other types
    (3-point angular, ordinate) or if a point is missing."""
    dxf = entity.dxf

    def pt(name):
        v = dxf.get(name)
        return None if v is None else (float(v[0]), float(v[1]))

    try:
        kind = int(dxf.get("dimtype", 0)) & 7
    except (TypeError, ValueError):
        return None
    decimals, factor = _dimension_style(entity, angular=kind == 2)
    style = {} if written_by_hand(entity) else {"decimals": decimals}
    if kind != 2 and style:
        style["drawn_to_real"] = factor
    if kind in (0, 1):
        pts = pt("defpoint2"), pt("defpoint3"), pt("defpoint")
        if None in pts:
            return None
        direction = _f(dxf.get("angle", 0.0)) if kind == 0 else None
        return MeasuredDistance(*pts, direction, **style)
    if kind == 4:
        pts = pt("defpoint"), pt("defpoint4")
        return None if None in pts else MeasuredRadius(*pts, **style)
    if kind == 3:
        pts = pt("defpoint4"), pt("defpoint")
        return None if None in pts else MeasuredDiameter(*pts, **style)
    if kind == 2:
        pts = pt("defpoint"), pt("defpoint4"), pt("defpoint3"), pt("defpoint2"), pt("defpoint5")
        if None in pts:
            return None
        return MeasuredAngle((pts[0], pts[1]), (pts[2], pts[3]), pts[4], **style)
    return None


def _dimension_style(entity, angular: bool):
    """What the dimension says about its number: decimals (`dimdec`, `dimadec` for an
    angle) and factor from drawn to true length (`dimlfac`). The appearance
    (height, rotation) is the consumer's."""
    try:
        o = entity.override()
        dec = o.get("dimadec" if angular else "dimdec")
        lfac = o.get("dimlfac")
    except Exception:
        return None, None
    return None if dec is None else int(dec), None if lfac is None else float(lfac)


def written_by_hand(entity) -> bool:
    """The dimension has the number written by hand: the file's text field is not
    empty and has no `<>`, so decimals and factor do not produce it."""
    raw = entity.dxf.get("text", "") or ""
    return bool(raw.strip()) and "<>" not in raw


def hand_written_dimensions(msp) -> int:
    """How many DIMENSIONs have the number written by hand."""
    return sum(1 for e in msp.query("DIMENSION") if written_by_hand(e))


def bare_dimensions(msp) -> int:
    """How many DIMENSIONs do not carry their drawing in the file (no geometry
    block): of those only the string remains."""
    return sum(1 for e in msp.query("DIMENSION") if e.get_geometry_block() is None)


def _on_string(rendered: RenderedGeometry, pos) -> dict:
    """Point, alignment, height and rotation of a text with its drawing: those of its
    first string, in the source's order, so `position` is where the string reads
    as for any other text. Without strings `pos` stays."""
    if not rendered.texts:
        return {"position": pos}
    first = rendered.texts[0]
    return {"position": first.position, "halign": first.halign, "valign": first.valign,
            "height": first.height, "rotation": first.rotation}


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _shown_text(override: Optional[str], rendered: RenderedGeometry) -> str:
    """The string the dimension shows: the override with ``<>`` replaced by the
    measure; without override, the image's texts; without image, the measure."""
    if override is not None:
        return override.replace("<>", _shown_value(rendered, override))
    if rendered.texts:
        return "".join(t.content for t in rendered.texts)
    return _shown_value(rendered)


def _shown_value(rendered: RenderedGeometry, override: str = "") -> str:
    """The measure as the drawing writes it (precision, comma): a string that is just
    a number, otherwise the first number of the texts that the override does not
    already write (``R5`` for ``R<>``, ``10`` of ``10±0.2`` for ``<>±0.2``). topo
    never computes it: no number, ``<>`` stays."""
    for t in rendered.texts:
        if _NUMBER.fullmatch(t.content.strip()):
            return t.content.strip()
    written = set(_NUMBER.findall(override.replace("<>", " ")))
    for t in rendered.texts:
        for n in _NUMBER.findall(t.content):
            if n not in written:
                return n
    return "<>"


def _dimension_override(entity) -> Optional[str]:
    """Explicit override of the dimension text, or None if the dimension shows the measure.

    DXF field `text`: "" / "<>" → computed measure (no override); " " →
    suppressed text; "...<>" → prefix/suffix; other → override. `_shown_text`
    resolves "<>" with the measure."""
    raw = entity.dxf.get("text", "") or ""
    if raw in ("", "<>"):
        return None
    if raw.strip():
        raw = plain_mtext(raw).strip()   # MTEXT formatting codes (\A1; ...)
        if raw in ("", "<>"):
            return None
    for code, char in _SPECIAL_CODES.items():
        raw = raw.replace(code, char).replace(code.upper(), char)
    return _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), raw)


# Special DXF text codes → character (diameter, degree, plus-minus).
_SPECIAL_CODES = {"%%c": "Ø", "%%d": "°", "%%p": "±"}
_UNICODE_ESCAPE = re.compile(r"\\[Uu]\+([0-9A-Fa-f]{4})")   # "\U+00B0" → "°"


# ---------------------------------------------------------------------------
# LEADER / MULTILEADER
# ---------------------------------------------------------------------------

def carries_string(entity) -> bool:
    """A LEADER/MULTILEADER carries a string of its own: in the entity's field or
    among the entities of its block. Without, it is geometry: the same rule for
    the text extractor and for the loader that explodes it."""
    if clean_mtext(mleader_text(entity)):
        return True
    try:
        return any(v.dxftype() in ("TEXT", "MTEXT") and _text_item(v) is not None
                   for v in _flatten_virtual(entity))
    except Exception:
        return False


def _leader_text(entity, pos, role: str) -> Optional[Text]:
    rendered = _render_block(entity)
    if rendered.is_empty():
        return None

    # The leader's text: first the entity's dedicated field, then the first
    # flattened text in the block.
    text = clean_mtext(mleader_text(entity))
    if not text and rendered.texts:
        text = rendered.texts[0].content
    if not text:
        # no string of its own: it is geometry, the loader explodes it
        return None
    vertices = _leader_vertices(entity)

    if pos is None:
        # Fallback to the anchor: first vertex of the leader (where it points), then the
        # centre of the image. Many MULTILEADERs (e.g. Solid Edge) expose neither anchor
        # nor vertices nor geometry: there the only anchor is the position of the
        # flattened text.
        if vertices:
            pos = vertices[0]
        else:
            pos = _bbox_center(
                rendered.strokes + rendered.fills
                + [[t.position] for t in rendered.texts]
            )
        if pos is None:
            return None

    return Text(
        role=role,
        text=text,
        rendered=rendered,
        **_on_string(rendered, pos),
    )


def _leader_vertices(entity) -> List[Tuple[float, float]]:
    t = entity.dxftype()
    try:
        if t == "LEADER":
            return [(float(v[0]), float(v[1])) for v in entity.vertices]
        if t == "MULTILEADER":
            return [(float(v[0]), float(v[1]))
                    for v in entity.context.mleader.vertices]
    except Exception:
        pass
    return []


# --- Flattening of the anonymous block (DIMENSION / LEADER / MULTILEADER) ---

def _render_block(entity) -> RenderedGeometry:
    """Expand the entity's image into pure strokes/fills/texts."""
    strokes: List[List[Tuple[float, float]]] = []
    fills: List[List[Tuple[float, float]]] = []
    texts: List[RenderedText] = []

    try:
        vents = list(_flatten_virtual(entity))
    except Exception:
        vents = []

    for v in vents:
        t = v.dxftype()
        if t == "LINE":
            strokes.append([_xy(v.dxf.start), _xy(v.dxf.end)])
        elif t == "ARC":
            pts = _flattened_points(v)
            if len(pts) >= 2:
                strokes.append(pts)
        elif t == "CIRCLE":
            pts = _flattened_points(v)
            if pts:
                fills.append(pts)
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts, closed = _polyline_points(v)
            if len(pts) >= 2:
                (fills if closed else strokes).append(pts)
        elif t in ("SOLID", "TRACE"):
            pts = _solid_points(v)
            if len(pts) >= 3:
                fills.append(pts)
        elif t in ("TEXT", "MTEXT"):
            item = _text_item(v)
            if item is not None:
                texts.append(item)

    return RenderedGeometry(strokes=strokes, fills=fills, texts=texts)


def _flatten_virtual(entity):
    """Espande `virtual_entities()` ricorsivamente sugli INSERT (frecce a blocco)."""
    for v in entity.virtual_entities():
        if v.dxftype() == "INSERT":
            yield from _flatten_virtual(v)
        else:
            yield v


def _text_item(v) -> Optional[RenderedText]:
    t = v.dxftype()
    content = clean_mtext(v.text) if t == "MTEXT" else (v.dxf.get("text", "") or "")
    content = content if content.strip() else ""
    if not content:
        return None
    placement = text_placement(v)
    if placement is None:
        return None
    pos, halign, valign = placement
    raw_h = v.dxf.get("char_height", 2.5) if t == "MTEXT" else v.dxf.get("height", 2.5)
    return RenderedText(
        content=content,
        position=pos,
        height=_f(raw_h) or 2.5,
        rotation=_f(v.dxf.get("rotation", 0.0)) or 0.0,
        halign=halign,
        valign=valign,
    )


def _bbox_center(polylines) -> Optional[Tuple[float, float]]:
    xs = [p[0] for pl in polylines for p in pl]
    ys = [p[1] for pl in polylines for p in pl]
    if not xs:
        return None
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _xy(p) -> Tuple[float, float]:
    return (float(p[0]), float(p[1]))


def _flattened_points(entity) -> List[Tuple[float, float]]:
    """Points of an ARC or CIRCLE flattened at the sagitta `_ARC_SAGITTA`."""
    try:
        return [(float(p[0]), float(p[1])) for p in entity.flattening(_ARC_SAGITTA)]
    except Exception:
        return []


def _polyline_points(pl) -> Tuple[List[Tuple[float, float]], bool]:
    t = pl.dxftype()
    try:
        if t == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y, *_ in pl.get_points("xyb")]
            return pts, bool(pl.closed)
        pts = [(float(p[0]), float(p[1])) for p in pl.points()]
        return pts, bool(pl.is_closed)
    except Exception:
        return [], False


def _solid_points(solid) -> List[Tuple[float, float]]:
    """SOLID/TRACE: 4 vertici in ordine 'a farfalla' → poligono convesso."""
    vs = []
    for name in ("vtx0", "vtx1", "vtx3", "vtx2"):  # 3<->2 per de-farfallare
        p = solid.dxf.get(name)
        if p is not None:
            vs.append((float(p[0]), float(p[1])))
    if len(vs) == 4 and vs[2] == vs[3]:
        vs = vs[:3]
    return vs


def _f(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
