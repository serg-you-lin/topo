"""
topo_dxf/writer.py
------------------
Materializza un Result in un documento DXF NUOVO, lavorando esclusivamente
sui segmenti del modello. Zero accesso a source_ref, entity_ids, msp sorgente.

`to_dxf(result, ...)` → un Drawing con tutto quello che il Result contiene.
Un file per parte: `topo.split(result)` dà un Result per parte, e ognuno
passa da `to_dxf` (D124, D129); `recipes.split_to_files()` è quel ciclo, più
il salvataggio su disco.
"""

from __future__ import annotations

from typing import Callable, List, Mapping, Optional, Set

import ezdxf

from topo.model import (
    Cluster, ContourRole, Document, Result, Text,
    RoleStyle, feature_closed, feature_role, role_str, role_style,
)
from .exporter import (
    dxf_pattern, ensure_linetype, write_segments, write_open_segments, write_native_segments,
)
from .layers import (
    COLOR_ANNOTATION, LAYER_ANNOTATION, LayerMap, color_for_role, role_to_dxf_layer,
)


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def to_dxf(
    result: Result,
    source_doc: Optional[Document] = None,
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
    contour/hole. It reads no existing DXF entities — if passed, `source_doc`
    is only used to carry over the headers ($INSUNITS, $MEASUREMENT). Texts
    and dimensions come from `result.texts` (the model), not from the source.

    With `include_loose=True` (default) the entities the pipeline did not
    classify (`result.loose`) are materialized on the `Trash` layer: a CAM
    operator must be able to see EVERY entity of the starting drawing, even
    spurious arcs, profile fragments, centerlines. Silently omitting them is
    a regression.

    Layer and appearance are the caller's (D123, D128); what it does not say
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
        with a role goes on its role's layer, like an edge (D127, D128).
    No text is discarded: those not covered by any part are written anyway
    (`topo.split()` assigns them to the nearest part, like loose curves).

    `filter_cluster(cluster)` chooses which clusters to write; `loose` and
    texts are all written anyway (for a file per part, the part comes from
    `topo.split()`, which has already divided them). `exclude_types`
    (`{"TEXT", "CIRCLE"}`) removes the DXF entities of those types from the
    document.

    Returns the ezdxf document: the caller must do doc.saveas(...).

    An invalid `result` (e.g. no closed outer contour → zero parts) is
    written anyway, with what there is (`loose`, texts): like `to_svg`, it
    serves to see what topo understood. `allow_invalid=False` → `ValueError`
    instead: the caller who delivers to a machine (D83).
    """
    if not result.is_valid and not allow_invalid:
        raise ValueError(
            "to_dxf(): the Result is not valid, no output. "
            + " ".join(result.errors)
        )
    doc_out = ezdxf.new(dxfversion="R2010")
    # ezdxf.new() di default dichiara $INSUNITS=6 (metri): topo lavora sempre
    # in millimetri, quindi il default va forzato a 4 anche senza source_doc
    # (es. geometria generata, non caricata da un DXF esistente) — altrimenti
    # un importatore che rispetta $INSUNITS scala il pezzo di 1000x.
    doc_out.header["$INSUNITS"]    = 4
    doc_out.header["$MEASUREMENT"] = 1
    if source_doc is not None:
        doc_out.header["$INSUNITS"]    = source_doc.source_meta.get("$INSUNITS", 4)
        doc_out.header["$MEASUREMENT"] = source_doc.source_meta.get("$MEASUREMENT", 1)

    msp = doc_out.modelspace()
    book = _Layers(doc_out, layers, role_styles)
    book.setup(text_layer)

    for cluster in result.clusters:
        if filter_cluster is not None and not filter_cluster(cluster):
            continue

        # Contorno esterno e interni: un contorno si scrive col ruolo di
        # contorno che ha nel grafo (outer o inner), anche se ne porta un altro
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

        # L'overlay di un consumatore (fori, pieghe, ...: D70, D90)
        _write_attached_features(msp, cluster, book)

    if include_loose and result.loose:
        _write_loose(msp, result, book)

    if include_texts and result.texts:
        _write_texts(msp, result.texts, book, text_layer)

    if exclude_types:
        _remove_excluded_entities(msp, {t.upper() for t in exclude_types})

    return doc_out


# ---------------------------------------------------------------------------
# Testi
# ---------------------------------------------------------------------------

def _write_texts(
    msp,
    texts: List[Text],
    book: "_Layers",
    text_layer: str,
) -> None:
    """
    Riscrive i testi della sorgente nel documento di output, tutti: quale
    parte ne porta quali lo decide `topo.split()`.

    Un testo con un ruolo va sul layer del suo ruolo, uno senza su
    `text_layer` (D128).
    """
    for text in texts:
        if text.role != ContourRole.UNKNOWN:
            layer = book.for_role(text.role, text)
        else:
            layer = text_layer
        _emit_text(msp, text, layer)


def _emit_text(msp, text: Text, layer: str) -> None:
    """Con un'immagine (`rendered`: quote e richiami della sorgente) si
    riscrive l'immagine, altrimenti la stringa."""
    attribs = {"layer": layer, "color": 256}

    if text.rendered.is_empty():
        _emit_string(msp, text, attribs)
    else:
        _emit_rendered(msp, text, attribs)


def _emit_string(msp, note: Text, attribs: dict) -> None:
    if not note.text:
        return
    width = note.width_factor or 1.0
    if note.source_kind == "MTEXT":
        # MTEXT non ha un attributo per-entità per lo stretch dei glifi (il suo
        # gruppo 41 è la larghezza di colonna, un'altra cosa): si ottiene con
        # un codice di formattazione inline, non con uno stile dedicato — resta
        # un override numerico, niente stili con nome da inventare o mappare.
        text = note.text if width == 1.0 else f"\\W{width:.4g};{note.text}"
        entity = msp.add_mtext(text, dxfattribs={
            **attribs,
            "char_height": note.height or 2.5,
            "rotation": note.rotation or 0.0,
        })
        entity.set_location(note.position)
    else:
        msp.add_text(note.text, dxfattribs={
            **attribs,
            "height": note.height or 2.5,
            "rotation": note.rotation or 0.0,
            "insert": note.position,
            "width": width,
        })


def _emit_rendered(msp, ann, attribs: dict) -> None:
    """
    Ri-materializza l'immagine appiattita (DIMENSION / LEADER di un DXF). I testi in
    `rendered.texts` sono già il testo visualizzato finale (il blocco DXF lo
    incorpora risolto; i percorsi sintetici passano da `_dimension_text`).
    """
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
        msp.add_text(rt.content, dxfattribs={
            **attribs,
            "height": rt.height or 2.5,
            "rotation": rt.rotation or 0.0,
            "insert": rt.position,
        })


# ---------------------------------------------------------------------------
# Curve sciolte (`result.loose`). Sul layer Trash se non hanno un ruolo;
# su un layer col nome del ruolo se un consumatore ne ha assegnato uno (D31).
# ---------------------------------------------------------------------------

def _write_loose(msp, result: Result, book: "_Layers") -> None:
    """
    Materializza `result.loose`, tutte: in un file per parte le ha
    già divise `topo.split()`.

    Ogni entità va sul layer del suo ruolo (`book.for_role`): di default
    `Trash` se il ruolo è `unknown`, un layer col nome dello slug se un
    consumatore l'ha marcata (`frame`, `title_block`, ...) — D31.
    """
    for curve in result.loose:
        segments = list(getattr(curve, "segments", []) or [])
        if segments:
            styles = list(getattr(curve, "styles", []) or [])
            layer = book.for_role(getattr(curve, "role", ContourRole.UNKNOWN), curve)
            # Il colore resta quello del layer — solo il linetype (tratteggio)
            # della sorgente viene ripristinato fedele.
            write_open_segments(segments, msp, layer, styles)


# ---------------------------------------------------------------------------
# Helpers interni
# ---------------------------------------------------------------------------

def _write_attached_features(msp, cluster: Cluster, book: "_Layers") -> None:
    """
    Ogni collezione di `cluster.overlay` (D70, D90): topo non sa cosa siano.
    Di un elemento legge solo `role` e geometria — i suoi `contours`, se li
    ha, altrimenti l'elemento stesso. Un contorno con `polygon` si scrive
    chiuso, uno senza come una entità per primitiva. Il ruolo di un contorno
    vince su quello dell'elemento solo se non è un ruolo del motore
    (`feature_role`). Un elemento senza ruolo o senza segmenti si salta.
    La scelta del layer riceve l'elemento, non il suo contorno: è l'elemento
    che porta l'informazione (una piega "up" o "down").
    """
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
    """Il ruolo di contorno nel grafo: outer/inner se lo porta, `default` se
    il contorno ha un ruolo di consumatore."""
    role = getattr(contour, "role", None)
    return role if role in (ContourRole.OUTER, ContourRole.INNER) else default


class _Layers:
    """
    I layer di un documento in scrittura (D128): il nome viene dalla scelta
    del chiamante (`layers`) o dal default dell'adapter; un layer nuovo
    nasce col colore della palette di topo per il ruolo e prende il
    `RoleStyle` del chiamante una volta sola — su un layer di più ruoli vince
    il primo.
    """

    def __init__(self, doc, layers: Optional[LayerMap], role_styles: Optional[Mapping[str, RoleStyle]]):
        self.doc = doc
        self.layers = dict(layers or {})
        self.role_styles = dict(role_styles or {})
        self._ready: Set[str] = set()

    def setup(self, text_layer: str) -> None:
        """I layer di ogni documento: quelli dei ruoli del motore e delle
        testi, poi quelli di ogni ruolo con un `RoleStyle` (anche senza
        entità, così il chiamante ci scrive sopra a mano). Un ruolo il cui
        layer è una funzione dell'elemento nasce solo quando si scrive."""
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
        """Il layer di `role` per `element`, creato se serve."""
        name = role_to_dxf_layer(role, element, layers=self.layers)
        self.ensure(name, role)
        return name

    def ensure(self, name: str, role=None, color: Optional[int] = None) -> None:
        if not name or name in self._ready:
            return
        self._ready.add(name)
        if name not in self.doc.layers:
            layer = self.doc.layers.new(name)
            # la palette di topo (D128): indice ACI se ne ha uno esatto, così
            # il default resta un colore DXF "di serie"; il colore del
            # chiamante arriva sotto, in true color
            aci = color if color is not None else color_for_role(role)
            if aci is not None:
                layer.color = aci
            else:
                layer.rgb = role_style(role).color
        style = self.role_styles.get(role_str(role)) if role else None
        if style is not None:
            _apply_role_style(self.doc, self.doc.layers.get(name), role, style)


def _apply_role_style(doc, layer, role, style: RoleStyle) -> None:
    """
    Un `RoleStyle` (D37, D128) sul layer: colore in true color (l'ACI non ha
    un nero puro), tratto registrato al volo, spessore in centesimi di mm.
    Un tratto senza nome prende il nome del ruolo; un nome senza tratto è un
    tipo standard. Un campo a `None` non si tocca.
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
