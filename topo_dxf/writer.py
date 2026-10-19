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
    RoleStyle, feature_role, role_str, role_style,
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
    filter_cluster: Optional[Callable[[Cluster], bool]] = None,
    include_texts: bool = True,
    include_loose: bool = True,
    text_layer: str = LAYER_ANNOTATION,
    role_styles: Optional[Mapping[str, RoleStyle]] = None,
    layers: Optional[LayerMap] = None,
    allow_invalid: bool = True,
    exclude_types: Optional[Set[str]] = None,
) -> "ezdxf.document.Drawing":
    """
    Crea un documento DXF nuovo (R2010) e vi materializza il Result.

    Itera i clusters del modello e scrive i segmenti puri di ogni contorno/hole.
    Non legge entità DXF esistenti — se passato, `source_doc` serve solo per
    riportare gli header ($INSUNITS, $MEASUREMENT). Testi e quote arrivano da
    `result.texts` (il modello), non dalla sorgente.

    Con `include_loose=True` (default) le entità che il pipeline non ha
    classificato (`result.loose`) vengono materializzate sul layer
    `Trash`: un operatore CAM deve poter vedere OGNI entità del disegno di
    partenza, anche archi spuri, frammenti di profilo, centerline. Ometterle
    silenziosamente è una regressione.

    Layer e aspetto sono del chiamante (D123, D128); quello che non dice è il
    default dell'adapter (`topo_dxf/layers.py`):
      - `layers` → `{ruolo: "Nome"}` o `{ruolo: funzione(elemento) -> nome}`:
        con una funzione le entità di un ruolo si dividono su più layer
        (l'elemento è il Contour, l'elemento di `cluster.detected`, la
        curva di `loose` o il Text che si sta scrivendo). Default: `OuterContour`,
        `InnerContour`, `Trash` per `unknown`, lo slug per ogni altro ruolo.
      - `role_styles` → `{ruolo: RoleStyle}`: colore, tratto, spessore.
        Agisce sul LAYER, non sull'entità: tutto ciò che si scrive è BYLAYER,
        quindi vale per ogni entità del ruolo; su un layer condiviso da più
        ruoli vince il primo scritto. Un campo a `None` resta il default.
      - `text_layer` → il layer di testi e quote senza ruolo; uno con
        un ruolo va sul layer del suo ruolo, come un edge (D127, D128).
    Nessun testo viene scartato: quelli non coperti da alcuna parte
    vengono comunque scritti (`topo.split()` li assegna alla parte più
    vicina, come le curve sciolte).

    `filter_cluster(cluster)` sceglie quali cluster scrivere; `loose` e
    testi si scrivono comunque tutti (per un file per parte, la parte
    viene da `topo.split()`, che li ha già divisi). `exclude_types`
    (`{"TEXT", "CIRCLE"}`) toglie dal documento le entità DXF di quei tipi.

    Restituisce il documento ezdxf: sta al chiamante fare doc.saveas(...).

    Un `result` non valido (es. nessun contorno esterno chiuso → zero parti)
    viene scritto lo stesso, con quello che c'è (`loose`, testi): come
    `to_svg`, serve a vedere cosa ha capito topo. `allow_invalid=False` →
    `ValueError` invece: il chiamante che consegna a una macchina (D83).
    """
    if not result.is_valid and not allow_invalid:
        raise ValueError(
            "to_dxf(): il Result non è valido, nessun output generato. "
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
    Ogni collezione di `cluster.detected` (D70, D90): topo non sa cosa siano.
    Di un elemento legge solo `role` e geometria — i suoi `contours`, se li
    ha, altrimenti l'elemento stesso. Un contorno con `polygon` si scrive
    chiuso, uno senza come una entità per primitiva. Il ruolo di un contorno
    vince su quello dell'elemento solo se non è un ruolo del motore
    (`feature_role`). Un elemento senza ruolo o senza segmenti si salta.
    La scelta del layer riceve l'elemento, non il suo contorno: è l'elemento
    che porta l'informazione (una piega "up" o "down").
    """
    if cluster.detected is None:
        return
    for _name, items in cluster.detected.items():
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
                if getattr(contour, "polygon", None) is not None:
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
        name = role_to_dxf_layer(role, element, self.layers)
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
                f"RoleStyle per {role_str(role)!r}: linetype {name!r} sconosciuto "
                "(né nel documento né tra gli standard) e senza tratto"
            )
        layer.dxf.linetype = linetype
    if style.lineweight is not None:
        layer.dxf.lineweight = round(style.lineweight * 100)
