

"""
topo_dxf/adapter.py
-------------------
Translates DXF entities into Topo primitives. The ONLY point of conversion
DXF → primitives.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Callable, List, Optional, Sequence, Tuple, Union

from ezdxf.colors import aci2rgb, int2rgb

# Only public topo names: the adapter is a consumer like any other
from topo.primitives import LineSeg, BSplineSeg, CircleSeg, EllipseSeg
from topo.model import Diagnostic, Edge, EdgeStyle, RoleRule, resolve_role

from .parser import DxfEntityDispatcher


# --- Constants ---

_SUPPORTED_TYPES = frozenset({'LINE', 'ARC', 'SPLINE', 'ELLIPSE'})
# every type that to_edges turns into curves
_CURVE_TYPES = _SUPPORTED_TYPES | {'CIRCLE', 'LWPOLYLINE', 'POLYLINE'}

# "System" linetypes: they have no entry of their own in the table or carry no
# pattern (BYLAYER/BYBLOCK inherit; CONTINUOUS is always present in every
# ezdxf.new() document). No pattern to capture for these.
_STANDARD_LINETYPES = frozenset({'BYLAYER', 'BYBLOCK', 'CONTINUOUS'})


# --- Raw appearance (linetype/colour) ---

def _raw_linetype_pattern(lt_entry) -> Optional[Tuple[float, ...]]:
    """Raw pattern (total length + signed strokes, `+` = stroke, `-` = gap) of a
    `Linetype` — the same format wanted by `doc.linetypes.add(name, pattern=[...])`.

    NOT `Linetype.simplified_line_pattern()`: that is a read-only rendering, it
    has already lost the signs and the total length — handing it back to `.add()`
    produces a degenerate pattern (all solid strokes, no gaps)."""
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
    """The effective colour as RGB: the true colour if present, otherwise the ACI
    index (1–255) with its canonical RGB. BYBLOCK (0) and an unresolved BYLAYER
    (256) do not tell a colour: None."""
    if true_color is not None:
        return tuple(int2rgb(true_color))
    if 1 <= aci <= 255:
        return tuple(aci2rgb(aci))
    return None


def _entity_style(entity) -> EdgeStyle:
    """Capture the EFFECTIVE appearance (linetype/colour) of a DXF entity in a pure
    `EdgeStyle` — what is really seen in CAD, not only the entity's raw attribute.

    Common case: the drawing puts the style on the LAYER, not on the single
    entity (`entity.dxf.linetype == "ByLayer"`) — the real dashing lives in the
    layer's entry (`doc.layers.get(layer).dxf.linetype`), the entity's attribute
    alone does not say it. Without resolving BYLAYER to the layer's value, every
    entity that inherits the style (the typical case) would escape both
    `role_rules` and the faithful restore on output: written on a different topo
    layer (Trash/Bending/...), continuous by default, it would silently lose the
    dashing.

    If the resolved linetype is not a standard one, its pattern (stroke lengths)
    is also resolved from the source document's table — the only moment topo can
    still read it, before the reference to ezdxf is gone. The resolved pattern
    travels as pure data up to write(), which re-registers it in the output document."""
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

    # BYLAYER/BYBLOCK are DXF words, not line types: if they remain after
    # resolution the source says nothing
    upper = linetype.upper()
    if upper in ("BYLAYER", "BYBLOCK"):
        linetype, dash = "", None
    elif upper == "CONTINUOUS":
        dash = ()
    else:
        # the DXF pattern opens with the total length: the stroke is the marks
        dash = tuple(pattern[1:]) if pattern else None
    return EdgeStyle(
        linetype=linetype,
        linetype_desc=desc,
        dash=dash,
        color=_color_rgb(color, true_color),
    )


# --- DXF → PRIMITIVES TRANSLATION ---
# The translation DXF entity → primitive lives in ONE place only:
# `topo_dxf/parser.py::DxfEntityDispatcher`.


def _segment_key(segment) -> tuple:
    """Unique key for deduplication."""
    if isinstance(segment, LineSeg):
        pts = tuple(sorted((
            (round(segment.start[0], 6), round(segment.start[1], 6)),
            (round(segment.end[0], 6), round(segment.end[1], 6)),
        )))
        return ("LINE", pts)
    if (isinstance(segment, CircleSeg) and not segment.full):
        return (
            "ARC",
            round(segment.center[0], 6),
            round(segment.center[1], 6),
            round(segment.radius, 6),
            round(segment.start_angle, 6),
            round(segment.end_angle, 6),
            segment.ccw,
        )
    if isinstance(segment, BSplineSeg):
        return (
            "SPLINE",
            int(segment.degree),
            tuple((round(x, 6), round(y, 6)) for x, y in segment.control_points),
            tuple(round(k, 9) for k in segment.knots),
            tuple(round(w, 9) for w in (segment.weights or [])),
            bool(segment.closed),
            bool(segment.periodic),
        )
    if (isinstance(segment, CircleSeg) and segment.full):
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

def layer_skipper(skip_layers) -> Callable[[str], bool]:
    """The predicate "this layer is skipped" from `skip_layers`: a function
    `name -> bool` passes as it is and receives the layer name as in the file; a
    sequence of names matches by exact name, case-insensitive."""
    if callable(skip_layers):
        return skip_layers
    names = {s.lower() for s in skip_layers}
    return lambda layer: layer.lower() in names


class DxfAdapter:
    """DXF adapter that translates DXF entities into Edges of the Topo domain.

    The role of every Edge comes from `role_rules`, evaluated on the layer name
    and on the entity's effective appearance: the first that matches wins, none →
    `unknown`. The layer does not leave the adapter."""

    def __init__(
        self,
        msp,
        exclude_ids: Optional[set] = None,
        role_rules: Sequence[RoleRule] = (),
        skip_layers: Union[Sequence[str], Callable[[str], bool]] = (),
        filled_handles: Optional[set] = None,
    ):
        self.msp = msp
        # entities born from the border of a filled area: their sides are `filled`
        self.filled_handles = filled_handles or set()
        self.exclude_ids = exclude_ids or set()
        self.skip_layer = layer_skipper(skip_layers)
        self.role_rules = list(role_rules)
        # one message per type of degenerate entity discarded by to_edges
        self.warnings: List[str] = []

    def to_edges(self) -> List[Edge]:
        """Translate DXF entities into Edges."""
        # a curve on a skipped layer does not vanish silently: it is counted per layer
        # and becomes a warning
        skipped = Counter()

        def _is_excluded(entity) -> bool:
            if id(entity) in self.exclude_ids:
                return True
            layer = entity.dxf.layer if entity.dxf.hasattr("layer") else ""
            if not self.skip_layer(layer):
                return False
            if entity.dxftype() in _CURVE_TYPES:
                skipped[layer] += 1
            return True

        edges = []
        seen_segment_keys = set()
        degenerate = Counter()

        def _parse(entity, dtype):
            # a curve of zero measure (radius 0, null axis) or with a non-finite coordinate
            # is not a curve: the primitive rejects it, here it becomes a warning instead
            # of a crash
            try:
                return DxfEntityDispatcher(entity).parse()
            except ValueError:
                degenerate[dtype] += 1
                return None

        def _append_edge(role, segment, style=None):
            key = _segment_key(segment)
            if key in seen_segment_keys:
                return
            seen_segment_keys.add(key)
            edges.append(Edge.of(segment, role, style=style))

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
            if entity.dxf.handle in self.filled_handles:
                style = replace(style, filled=True)
            role = resolve_role(self.role_rules, label, style)

            # CIRCLE → CircleSeg (preserved!)
            if dtype == "CIRCLE":
                prim = _parse(entity, dtype)
                if (isinstance(prim, CircleSeg) and prim.full):
                    edges.append(Edge.of(prim, role, style=style))
                continue

            # LWPOLYLINE / POLYLINE → segments
            if dtype in ("LWPOLYLINE", "POLYLINE"):
                primitives = _parse(entity, dtype) or []
                if not isinstance(primitives, list):
                    primitives = [primitives]
                for segment in primitives:
                    _append_edge(role, segment, style=style)
                continue

            # LINE / ARC / SPLINE / ELLIPSE: a closed SPLINE or ELLIPSE is a degenerate
            # loop like CIRCLE, and Edge.of decides it, not the DXF type
            if dtype not in _SUPPORTED_TYPES:
                continue

            prim = _parse(entity, dtype)
            if prim is None:
                continue

            edges.append(Edge.of(prim, role, style=style))

        if degenerate:
            self.warnings.append(Diagnostic(
                "dxf-no-curve", f"entities with no curve left out: {sum(degenerate.values())}",
                notes=[f"{n} {dtype}" for dtype, n in sorted(degenerate.items())]
                      + ["zero radius or axis, or a coordinate that is not finite: a point or no position"]))
        if skipped:
            self.warnings.append(Diagnostic(
                "dxf-layer-skipped", f"curves on skipped layers left out: {sum(skipped.values())}",
                notes=[f"{n} on layer {layer!r}" for layer, n in sorted(skipped.items())],
                help="topo_dxf.load_dxf(path, skip_layers=()) reads every layer"))
        return edges
