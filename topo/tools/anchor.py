"""
topo/tools/anchor.py
---------------------------
Ancoraggio dei testi: collega ogni testo del modello alla geometria che lo
riguarda (MAP.md D43, D138). Pura ricostruzione geometrica, zero giudizio,
niente a che fare col significato del disegno.

Fase separata e opzionale — NON viene chiamata da heal(): il chiamante la
attiva quando gli serve (es. prima di split(), per sapere quale
testo va con quale pezzo).

``anchor_texts`` popola ``Text.cluster_ref`` (indice della parte
contenitrice). ``anchor_elements`` — sperimentale, ``topo.experimental``
(D228) — popola ``Text.target`` (l'elemento su cui cade la punta di
``pointer``, D66) e ``Text.references`` (gli elementi su cui cadono i
``measured_points``, D69): gli oggetti stessi, non percorsi nel risultato
(D177).
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, Tuple

from shapely.geometry import LineString, Point

from ..model.curve import ClosedCurve
from ..core.primitives.polygon_builder import curve_polygon
from ..model.result import Result
from ..model.role import ContourRole, is_structural_role
from ..model.text import Text

POINTER_TARGET_DISTANCE = 0.5   # mm — la punta di una freccia sta sulla linea che indica


def anchor_texts(result: Result, *, snap_distance: float = 0.0) -> None:
    """
    Set ``cluster_ref`` on every text of ``result.texts``.

    ``cluster_ref`` is the index in ``result.clusters`` of the part whose
    outer contour covers the text's position; a text outside every part (a
    title block) keeps ``None``. With ``snap_distance`` > 0 a text covered by
    no part goes to the nearest one within that distance of its outer (D82).

    Which element a dimension or a pointer lands on is
    ``topo.experimental.anchor_elements`` (D228).

    **Mutates** the texts of ``result`` and returns ``None`` (D176).
    """
    refs = _outer_polygons(result)
    if not refs:
        return
    for text in result.texts:
        text.cluster_ref = _assign(text.position, refs, snap_distance)


def anchor_elements(result: Result, *, distance: float = POINTER_TARGET_DISTANCE) -> None:
    """
    Sperimentale (D228): per ogni testo con ``pointer`` imposta ``target``
    (`pointer_target`), per ogni testo con ``measured_points`` ``references``
    (`measured_references`). Gli altri testi restano come sono.

    **Muta** i testi di ``result`` e ritorna ``None``.
    """
    for text in result.texts:
        if text.pointer:
            text.target = pointer_target(result, text, distance=distance)
        if text.measured_points:
            text.references = measured_references(result, text, distance=distance)


def _outer_polygons(result: Result) -> list:
    """(indice, poligono dell'outer) per ogni parte che ne ha uno."""
    return [
        (i, poly)
        for i, p in enumerate(result.clusters)
        if p.outer is not None
        for poly in [curve_polygon(p.outer)]
        if poly is not None and not poly.is_empty
    ]


def pointer_target(result: Result, text: Text, *,
                   distance: float = POINTER_TARGET_DISTANCE) -> Optional[Any]:
    """
    L'elemento su cui cade la punta (``pointer[0]``) di ``text``: un contorno
    di ``result.clusters`` (``outer`` o ``inners``), un oggetto di una
    collezione di ``cluster.overlay``, o un pezzo chiuso di ``result.loose``
    (D162). L'oggetto stesso, non una sua posizione (D177).

    Il bordo più vicino alla punta, se entro ``distance``; altrimenti il più
    piccolo elemento chiuso (non il contorno esterno) che contiene la punta —
    una freccia che finisce dentro un foro; altrimenti ``None`` (una freccia
    fuori dal pezzo).
    """
    if not text.pointer:
        return None
    tip = Point(text.pointer[0])
    elements = list(_elements(result))
    if not elements:
        return None

    found = _on_boundary(elements, tip, distance)
    if found is not None:
        return found

    inside = [(geom.area, key, item) for key, item, geom, poly, outer in elements
              if poly and not outer and geom.covers(tip)]
    return min(inside, key=lambda e: e[:2])[2] if inside else None


def measured_references(result: Result, text: Text, *,
                        distance: float = POINTER_TARGET_DISTANCE) -> list:
    """
    Gli elementi su cui cadono i ``measured_points`` di ``text`` (gli oggetti
    stessi, come ``target``): per ogni punto l'elemento il cui bordo passa
    entro ``distance``, a parità il più piccolo. Senza doppioni, nell'ordine
    dei punti. Due punti opposti su un cerchio danno un elemento (il
    cerchio), due capi uno o due.
    """
    elements = list(_elements(result))
    refs = []
    for point in text.measured_points:
        item = _on_boundary(elements, Point(point), distance) if elements else None
        if item is not None and not any(item is r for r in refs):
            refs.append(item)
    return refs


def _on_boundary(elements, point, distance: float) -> Optional[Any]:
    """L'elemento col bordo più vicino a ``point``, se entro ``distance``."""
    dist, _, _, item = min(((geom.boundary.distance(point) if poly else geom.distance(point),
                             _size(geom, poly), key, item)
                            for key, item, geom, poly, _ in elements),
                           key=lambda e: e[:3])
    return item if dist <= distance else None


def _elements(result: Result) -> Iterator[Tuple[str, Any, Any, bool, bool]]:
    """(chiave, oggetto, geometria shapely, è chiuso, è un contorno esterno)
    per contorni e feature di ogni cluster, poi per i pezzi chiusi di
    ``loose`` senza un ruolo non strutturale (D162): un foro letto da
    outlines(), non una cornice. La chiave è il posto dell'oggetto nel
    risultato e serve solo a rompere le parità in modo deterministico."""
    for ci, cluster in enumerate(result.clusters):
        outer = curve_polygon(cluster.outer) if cluster.outer is not None else None
        if outer is not None:
            yield f"clusters[{ci}].outer", cluster.outer, outer, True, True
        collections = [("inners", cluster.inners)]
        if cluster.overlay is not None:
            collections += list(cluster.overlay.items())
        for name, items in collections:
            for k, item in enumerate(items):
                geom = _item_geometry(item)
                if geom is not None:
                    yield f"clusters[{ci}].{name}[{k}]", item, geom, geom.geom_type == "Polygon", False
    for k, curve in enumerate(result.loose):
        if isinstance(curve, ClosedCurve) and (curve.role == ContourRole.UNKNOWN or is_structural_role(curve.role)):
            geom = _item_geometry(curve)
            if geom is not None:
                yield f"loose[{k}]", curve, geom, geom.geom_type == "Polygon", False


def _item_geometry(item):
    polygon = curve_polygon(item)
    if polygon is not None and not polygon.is_empty:
        return polygon
    points = [p for seg in getattr(item, "segments", None) or [] for p in seg.discretize()]
    return LineString(points) if len(points) >= 2 else None


def _size(geom, closed: bool) -> float:
    """A parità di distanza vince l'elemento più piccolo: un foro sul bordo del pezzo."""
    return geom.area if closed else geom.length


def _assign(position, refs, snap_distance: float) -> Optional[int]:
    probe = Point(position)

    covering = [i for i, poly in refs if poly.covers(probe)]
    if covering:
        return covering[0]
    return _nearest_within(probe, refs, snap_distance)


def _nearest_within(probe: Point, refs, snap_distance: float) -> Optional[int]:
    """L'indice della parte più vicina a ``probe``, se entro ``snap_distance`` (> 0)."""
    if snap_distance <= 0.0 or not refs:
        return None
    idx, dist = min(
        ((i, poly.distance(probe)) for i, poly in refs),
        key=lambda pair: pair[1],
    )
    return idx if dist <= snap_distance else None
