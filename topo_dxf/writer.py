"""
topo_dxf/writer.py
------------------
Materializes a Result into a NEW DXF document, working exclusively on the
model's segments. No access to source_ref, entity_ids, source msp.

`to_dxf(result, ...)` → a Drawing with everything the Result contains. One
file per part: `topo.split(result).parts` gives a Result per part, and each goes
through `to_dxf`; the loop is the caller's.
"""

from __future__ import annotations

from typing import Callable, List, Mapping, Optional, Set

import ezdxf
from ezdxf.enums import TextEntityAlignment

from topo.model import (
    Cluster, ContourRole, Result, Text,
    RoleStyle, feature_closed, feature_role, role_str, role_style,
)
from .exporter import (
    dxf_pattern, ensure_linetype, write_segments, write_open_segments, write_native_segments,
)
from .layers import (
    COLOR_ANNOTATION, LAYER_ANNOTATION, LayerMap, color_for_role, role_to_dxf_layer,
)


# --- Public API ---

def to_dxf(
    result: Result,
    *, filter_cluster: Optional[Callable[[Cluster], bool]] = None,
    include_texts: bool = True,
    include_loose: bool = True,
    text_layer: str = LAYER_ANNOTATION,
    role_styles: Optional[Mapping[str, RoleStyle]] = None,
    layers: Optional[LayerMap] = None,
    allow_invalid: bool = True,
    exclude_types: Optional[Set[str]] = None,
) -> "ezdxf.document.Drawing":
    """
    Creates a new DXF document (R2010) and materializes the Result in it.

    Iterates the model's clusters and writes the pure segments of every
    contour/hole. It reads no existing DXF entities: the header says mm, the
    unit topo works in. Texts and dimensions come from `result.texts` (the
    model), not from the source.

    With `include_loose=True` (default) the entities the pipeline did not
    classify (`result.loose`) are materialized on the `Trash` layer: a CAM
    operator must be able to see EVERY entity of the starting drawing, even
    spurious arcs, profile fragments, centerlines. Silently omitting them is
    a regression.

    Layer and appearance are the caller's; what it does not say
    is the adapter's default (`topo_dxf/layers.py`):
      - `layers` → `{role: "Name"}` or `{role: function(element) -> name}`:
        with a function the entities of a role are split over several layers
        (the element is the Contour, the element of `cluster.overlay`, the
        curve of `loose` or the Text being written). Default: `OuterContour`,
        `InnerContour`, `Trash` for `unknown`, the slug for every other role.
      - `role_styles` → `{role: RoleStyle}`: color, stroke, thickness.
        It acts on the LAYER, not on the entity: everything written is
        BYLAYER, so it holds for every entity of the role; on a layer shared
        by several roles the first one written wins. A field at `None` stays
        the default.
      - `text_layer` → the layer of texts and dimensions without a role; one
        with a role goes on its role's layer, like an edge.
    No text is discarded: those not covered by any part are written anyway
    (`topo.split()` returns them apart, like the loose curves no part owns).

    `filter_cluster(cluster)` chooses which clusters to write; `loose` and
    texts are all written anyway (for a file per part, the part comes from
    `topo.split()`, which has already divided them). `exclude_types`
    (`{"TEXT", "CIRCLE"}`) removes the DXF entities of those types from the
    document.

    Returns the ezdxf document: the caller must do doc.saveas(...).

    An invalid `result` (e.g. no closed outer contour → zero parts) is
    written anyway, with what there is (`loose`, texts): like `to_svg`, it
    serves to see what topo understood. `allow_invalid=False` → `ValueError`
    instead: the caller who delivers to a machine.
    """
    if not result.is_valid and not allow_invalid:
        raise ValueError(
            "to_dxf(): the Result is not valid, no output. "
            + " ".join(result.errors)
        )
    doc_out = ezdxf.new(dxfversion="R2010")
    # topo works in millimetres, so the output says mm whatever the source declared
    # (a source's declared unit is often wrong): an importer that respects $INSUNITS
    # would otherwise scale the geometry by 1000x.
    doc_out.header["$INSUNITS"]    = 4
    doc_out.header["$MEASUREMENT"] = 1

    msp = doc_out.modelspace()
    book = _Layers(doc_out, layers, role_styles)
    book.setup(text_layer)

    for cluster in result.clusters:
        if filter_cluster is not None and not filter_cluster(cluster):
            continue

        # Outer and inner contours: a contour is written with the contour role it has
        # in the graph (outer or inner), even if it carries another
        write_segments(
            cluster.outer.segments, msp,
            book.for_role(_contour_role(cluster.outer, ContourRole.OUTER), cluster.outer),
            styles=cluster.outer.styles,
        )
        for inner in cluster.inners:
            write_segments(
                inner.segments, msp,
                book.for_role(_contour_role(inner, ContourRole.INNER), inner),
                styles=inner.styles,
            )

        # A consumer's overlay (holes, bends, ...)
        _write_attached_features(msp, cluster, book)

    if include_loose and result.loose:
        _write_loose(msp, result, book)

    _write_fills(msp, result, book, include_loose)

    if include_texts and result.texts:
        _write_texts(msp, result.texts, book, text_layer)

    if exclude_types:
        _remove_excluded_entities(msp, {t.upper() for t in exclude_types})

    return doc_out


# --- Texts ---
#

def _write_texts(
    msp,
    texts: List[Text],
    book: "_Layers",
    text_layer: str,
) -> None:
    """Rewrite the source's texts into the output document, all of them: which part
    carries which is decided by `topo.split()`.

    A text with a role goes on the layer of its role, one without on `text_layer`."""
    for text in texts:
        if text.role != ContourRole.UNKNOWN:
            layer = book.for_role(text.role, text)
        else:
            layer = text_layer
        _emit_text(msp, text, layer)


def _emit_text(msp, text: Text, layer: str) -> None:
    """With an image (`rendered`: the source's dimensions and callouts) the image is
    rewritten, otherwise the string."""
    attribs = {"layer": layer, "color": 256}

    if text.rendered.is_empty():
        _emit_string(msp, text, attribs)
    else:
        _emit_rendered(msp, text, attribs)


# (halign, valign) of the model → MTEXT attachment / TEXT alignment. MTEXT has
# no baseline: `baseline` becomes `bottom` there.
_MTEXT_ATTACH = {
    ("left", "top"): 1, ("center", "top"): 2, ("right", "top"): 3,
    ("left", "center"): 4, ("center", "center"): 5, ("right", "center"): 6,
    ("left", "bottom"): 7, ("center", "bottom"): 8, ("right", "bottom"): 9,
}
_TEXT_ALIGN = {
    ("left", "baseline"): "LEFT", ("center", "baseline"): "CENTER",
    ("right", "baseline"): "RIGHT",
    ("left", "bottom"): "BOTTOM_LEFT", ("center", "bottom"): "BOTTOM_CENTER",
    ("right", "bottom"): "BOTTOM_RIGHT",
    ("left", "center"): "MIDDLE_LEFT", ("center", "center"): "MIDDLE_CENTER",
    ("right", "center"): "MIDDLE_RIGHT",
    ("left", "top"): "TOP_LEFT", ("center", "top"): "TOP_CENTER",
    ("right", "top"): "TOP_RIGHT",
}


def _add_string(msp, content: str, position, *, height: float, rotation: float,
                halign: str, valign: str, width: float, attribs: dict) -> None:
    """A string at the model's point and alignment: TEXT if it is on one line, MTEXT
    if it has more than one (TEXT does not wrap)."""
    if "\n" in content:
        # MTEXT has no per-entity attribute for the glyph stretch (its group 41 is the
        # column width, another thing): it is obtained with an inline formatting code,
        # not with a dedicated style — it stays a numeric override, no named styles to
        # invent or map.
        body = content.replace("\n", "\\P")
        body = body if width == 1.0 else f"\\W{width:.4g};{body}"
        v = "bottom" if valign == "baseline" else valign
        entity = msp.add_mtext(body, dxfattribs={
            **attribs,
            "char_height": height,
            "rotation": rotation,
            "attachment_point": _MTEXT_ATTACH[(halign, v)],
        })
        entity.set_location(position)
        return
    entity = msp.add_text(content, dxfattribs={
        **attribs, "height": height, "rotation": rotation, "width": width,
    })
    entity.set_placement(position, align=TextEntityAlignment[_TEXT_ALIGN[(halign, valign)]])


def _emit_string(msp, note: Text, attribs: dict) -> None:
    if not note.text:
        return
    _add_string(msp, note.text, note.position, height=note.height or 2.5,
                rotation=note.rotation or 0.0, halign=note.halign, valign=note.valign,
                width=note.width_factor or 1.0, attribs=attribs)


def _emit_rendered(msp, ann, attribs: dict) -> None:
    """Re-materialize the flattened image (DIMENSION / LEADER of a DXF). The texts
    in `rendered.texts` are already the final displayed text (the DXF block embeds
    it resolved)."""
    rendered = ann.rendered
    for pts in rendered.strokes:
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs=attribs, close=False)
    for pts in rendered.fills:
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs=attribs, close=True)
    for rt in rendered.texts:
        if not rt.content:
            continue
        _add_string(msp, rt.content, rt.position, height=rt.height or 2.5,
                    rotation=rt.rotation or 0.0, halign=rt.halign, valign=rt.valign,
                    width=1.0, attribs=attribs)


# --- Loose curves (`result.loose`). On the Trash layer if they have no role; on a layer named after the role if a consumer assigned one. ---

def _write_loose(msp, result: Result, book: "_Layers") -> None:
    """Materialize `result.loose`, all of it: in a file per part `topo.split()` has
    already divided them.

    Every entity goes on the layer of its role (`book.for_role`): by default
    `Trash` if the role is `unknown`, a layer named after the slug if a consumer
    marked it (`frame`, `title_block`, ...)."""
    for curve in result.loose:
        segments = list(getattr(curve, "segments", []) or [])
        if segments:
            styles = list(getattr(curve, "styles", []) or [])
            layer = book.for_role(getattr(curve, "role", ContourRole.UNKNOWN), curve)
            # The colour stays the layer's — only the source's linetype (dashing) is
            # restored faithfully.
            write_open_segments(segments, msp, layer, styles)


def _write_fills(msp, result: Result, book: "_Layers", include_loose: bool) -> None:
    """Filled areas come back filled: the sides with `EdgeStyle.filled`, already
    written as lines, are put back into loops (`face_loops`, layer by layer) and
    every loop becomes a solid HATCH on the layer of its sides. The fill's border
    follows the discretized curves; the written curves stay exact."""
    import topo
    from topo.model import Edge

    curves = [(c.outer, _contour_role(c.outer, ContourRole.OUTER)) for c in result.clusters
              if c.outer is not None]
    curves += [(i, _contour_role(i, ContourRole.INNER)) for c in result.clusters for i in c.inners]
    if include_loose:
        curves += [(c, getattr(c, "role", ContourRole.UNKNOWN)) for c in result.loose]
    by_layer: dict = {}
    for curve, role in curves:
        styles = list(getattr(curve, "styles", []) or [])
        segments = list(getattr(curve, "segments", []) or [])
        for segment, style in zip(segments, styles):
            if style is not None and style.filled:
                layer = book.for_role(role, curve)
                by_layer.setdefault(layer, []).append(Edge.of(segment, "unknown", style=style))
    for layer, edges in by_layer.items():
        for loop in topo.experimental.face_loops(edges):
            points = []
            for edge, backwards in loop:
                pts = [tuple(p[:2]) for p in edge.segment.discretize()]
                points.extend(reversed(pts) if backwards else pts)
            if len(points) >= 3:
                hatch = msp.add_hatch(color=256, dxfattribs={"layer": layer})
                hatch.paths.add_polyline_path(points, is_closed=True)


# --- Internal helpers ---

def _write_attached_features(msp, cluster: Cluster, book: "_Layers") -> None:
    """Every collection of `cluster.overlay`: topo does not know what they are. Of an
    element it reads only `role` and geometry — its `contours`, if it has them,
    otherwise the element itself. A contour with `polygon` is written closed, one
    without as one entity per primitive. A contour's role wins over the element's
    only if it is not an engine role (`feature_role`). An element with no role or
    no segments is skipped. The layer choice receives the element, not its
    contour: it is the element that carries the information (an "up" or "down" bend)."""
    if cluster.overlay is None:
        return
    for _name, items in cluster.overlay.items():
        for item in items:
            role = getattr(item, "role", None)
            contours = getattr(item, "contours", None)
            if contours is None:
                contours = [item]
            for contour in contours:
                c_role = feature_role(contour, role)
                segments = getattr(contour, "segments", None)
                if not c_role or not segments:
                    continue
                layer = book.for_role(c_role, item)
                styles = getattr(contour, "styles", None)
                if feature_closed(contour, item):
                    write_segments(segments, msp, layer, styles=styles)
                else:
                    write_native_segments(segments, msp, layer, styles=styles)


def _remove_excluded_entities(msp, excluded_upper: Set[str]) -> None:
    to_delete = [e for e in msp if e.dxftype().upper() in excluded_upper]
    for e in to_delete:
        msp.delete_entity(e)


def _contour_role(contour, default: ContourRole):
    """The contour role in the graph: outer/inner if it carries it, `default` if the
    contour has a consumer's role."""
    role = getattr(contour, "role", None)
    return role if role in (ContourRole.OUTER, ContourRole.INNER) else default


class _Layers:
    """The layers of a document being written: the name comes from the caller's
    choice (`layers`) or from the adapter's default; a new layer is born with
    topo's palette colour for the role and takes the caller's `RoleStyle` once —
    on a layer of several roles the first wins."""

    def __init__(self, doc, layers: Optional[LayerMap], role_styles: Optional[Mapping[str, RoleStyle]]):
        self.doc = doc
        self.layers = dict(layers or {})
        self.role_styles = dict(role_styles or {})
        self._ready: Set[str] = set()

    def setup(self, text_layer: str) -> None:
        """The layers of every document: those of the engine roles and of the texts, then
        those of every role with a `RoleStyle` (even with no entities, so the caller
        can write on them by hand). A role whose layer is a function of the element
        is born only when written."""
        for role in (ContourRole.OUTER, ContourRole.INNER):
            self._setup_role(role)
        self.ensure(text_layer, color=COLOR_ANNOTATION)
        self._setup_role(ContourRole.UNKNOWN)
        for role in self.role_styles:
            self._setup_role(role)

    def _setup_role(self, role) -> None:
        if not callable(self.layers.get(role_str(role))):
            self.for_role(role)

    def for_role(self, role, element: object = None) -> str:
        """The layer of `role` for `element`, created if needed."""
        name = role_to_dxf_layer(role, element, layers=self.layers)
        self.ensure(name, role)
        return name

    def ensure(self, name: str, role=None, color: Optional[int] = None) -> None:
        if not name or name in self._ready:
            return
        self._ready.add(name)
        if name not in self.doc.layers:
            layer = self.doc.layers.new(name)
            # topo's palette: ACI index if it has an exact one, so the default stays a
            # "stock" DXF colour; the caller's colour arrives below, in true colour
            aci = color if color is not None else color_for_role(role)
            if aci is not None:
                layer.color = aci
            else:
                layer.rgb = role_style(role).color
        style = self.role_styles.get(role_str(role)) if role else None
        if style is not None:
            _apply_role_style(self.doc, self.doc.layers.get(name), role, style)


def _apply_role_style(doc, layer, role, style: RoleStyle) -> None:
    """A `RoleStyle` on the layer: colour in true colour (ACI has no pure black),
    stroke registered on the fly, thickness in hundredths of a mm. A stroke with
    no name takes the role's name; a name with no stroke is a standard type. A
    field at `None` is not touched.
    """
    if style.color is not None:
        layer.rgb = style.color
    if style.linetype is not None or style.dash is not None:
        if style.dash == ():
            name = style.linetype or "CONTINUOUS"
        else:
            name = style.linetype or f"{role_str(role).upper()}_DASH"
        linetype = ensure_linetype(doc, name, dxf_pattern(style.dash))
        if linetype is None:
            raise ValueError(
                f"RoleStyle for {role_str(role)!r}: linetype {name!r} unknown "
                "(neither in the document nor among the standard ones) and no dash given"
            )
        layer.dxf.linetype = linetype
    if style.lineweight is not None:
        layer.dxf.lineweight = round(style.lineweight * 100)
