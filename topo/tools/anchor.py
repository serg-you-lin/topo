"""
topo/tools/anchor.py
---------------------------
Ancoraggio dei testi: collega ogni testo del modello alla geometria che lo
riguarda (MAP.md D43, D138). Pura ricostruzione geometrica, zero giudizio,
niente a che fare col significato del disegno.

Fase separata e opzionale — NON viene chiamata da heal(): il chiamante la
attiva quando gli serve (es. prima di split() o di inject(), per sapere quale
testo va con quale pezzo).

Popola ``Text.cluster_ref`` (indice della parte contenitrice), ``Text.target``
(l'elemento su cui cade la punta di ``pointer``, D66) e ``Text.references``
(gli elementi su cui cadono i ``measured_points``, D69).
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional, Tuple

from shapely.geometry import LineString, Point

from ..model.curve import ClosedCurve
from ..core.primitives.polygon_builder import curve_polygon
from ..model.result import Result
from ..model.role import ContourRole, is_structural_role
from ..model.text import Text

POINTER_TARGET_DISTANCE = 0.5   # mm — la punta di una freccia sta sulla linea che indica


def anchor_texts(result: Result, snap_distance: float = 0.0,
                 pointer_distance: float = POINTER_TARGET_DISTANCE) -> Result:
    """
    Assegna ``cluster_ref`` a ogni testo di ``result.texts``.

    ``cluster_ref`` è l'indice in ``result.clusters`` della parte il cui contorno
    esterno contiene la posizione del testo. I testi fuori da ogni parte (es.
    il cartiglio) restano con ``cluster_ref = None``.

    ``snap_distance`` > 0: un testo non contenuto da nessuna parte viene
    comunque assegnato alla parte più vicina se dista meno di ``snap_distance``
    dal suo contorno — utile per i testi che il CAD posiziona appena fuori dal
    pezzo. Con il default 0.0 vale solo il contenimento stretto.

    Per ogni testo con ``pointer`` calcola anche ``target`` (vedi
    `pointer_target`), per ogni testo con ``measured_points`` ``references``
    (vedi `measured_references`).

    Muta i testi in-place e ritorna il ``result``.
    """
    refs = [
        (i, poly)
        for i, p in enumerate(result.clusters)
        if p.outer is not None
        for poly in [curve_polygon(p.outer)]
        if poly is not None and not poly.is_empty
    ]
    if not refs:
        return result

    for text in result.texts:
        text.cluster_ref = _assign(text.position, refs, snap_distance)
        if text.pointer:
            text.target = pointer_target(result, text, pointer_distance)
        if text.measured_points:
            text.references = measured_references(result, text, pointer_distance)

    return result


def pointer_target(result: Result, text: Text,
                   distance: float = POINTER_TARGET_DISTANCE) -> Optional[str]:
    """
    L'elemento indicato dalla punta (``pointer[0]``) di ``text``, come
    percorso in ``result``: ``"clusters[0].outer"``, ``"clusters[0].inners[3]"``,
    ``"clusters[1].holes[2]"`` (qualunque collezione di ``cluster.detected``),
    ``"loose[4]"`` (un pezzo chiuso in ``result.loose``, D162).

    Il bordo più vicino alla punta, se entro ``distance``; altrimenti il più
    piccolo elemento chiuso (non il contorno esterno) che contiene la punta —
    una freccia che finisce dentro un foro; altrimenti ``None`` (una freccia
    fuori dal pezzo). ``resolve_target`` fa il passo inverso.
    """
    if not text.pointer:
        return None
    tip = Point(text.pointer[0])
    elements = list(_elements(result))
    if not elements:
        return None

    path = _on_boundary(elements, tip, distance)
    if path is not None:
        return path

    inside = [(geom.area, path) for path, geom, poly in elements
              if poly and not path.endswith(".outer") and geom.covers(tip)]
    return min(inside)[1] if inside else None


def measured_references(result: Result, text: Text,
                        distance: float = POINTER_TARGET_DISTANCE) -> list:
    """
    Gli elementi su cui cadono i ``measured_points`` di ``text``, come
    percorsi in ``result`` (stesso formato di ``target``): per ogni punto
    l'elemento il cui bordo passa entro ``distance``, a parità il più
    piccolo. Senza doppioni, nell'ordine dei punti. Due punti opposti su un
    cerchio danno un elemento (il cerchio), due capi uno o due.
    """
    elements = list(_elements(result))
    refs = []
    for point in text.measured_points:
        path = _on_boundary(elements, Point(point), distance) if elements else None
        if path is not None and path not in refs:
            refs.append(path)
    return refs


def _on_boundary(elements, point, distance: float) -> Optional[str]:
    """L'elemento col bordo più vicino a ``point``, se entro ``distance``."""
    dist, _, path = min((geom.boundary.distance(point) if poly else geom.distance(point),
                         _size(geom, poly), path) for path, geom, poly in elements)
    return path if dist <= distance else None


def resolve_target(result: Result, target: Optional[str]) -> Any:
    """L'oggetto (contorno, feature o curva di ``loose``) a cui punta un ``target``, o ``None``."""
    if not target:
        return None
    m = _LOOSE.fullmatch(target)
    if m is not None:
        k = int(m.group(1))
        return result.loose[k] if k < len(result.loose) else None
    m = _TARGET.fullmatch(target)
    if m is None:
        return None
    ci, name, k = int(m.group(1)), m.group(2), m.group(3)
    if ci >= len(result.clusters):
        return None
    cluster = result.clusters[ci]
    if name == "outer":
        return cluster.outer
    items = cluster.inners if name == "inners" else cluster.features(name)
    k = int(k) if k is not None else -1
    return items[k] if 0 <= k < len(items) else None


_TARGET = re.compile(r"clusters\[(\d+)\]\.(\w+)(?:\[(\d+)\])?")
_LOOSE = re.compile(r"loose\[(\d+)\]")


def _elements(result: Result) -> Iterator[Tuple[str, Any, bool]]:
    """(percorso, geometria shapely, è chiuso) per contorni e feature di ogni
    cluster, poi per i pezzi chiusi di ``loose`` senza un ruolo non
    strutturale (D162): un foro letto da island(), non una cornice."""
    for ci, cluster in enumerate(result.clusters):
        outer = curve_polygon(cluster.outer) if cluster.outer is not None else None
        if outer is not None:
            yield f"clusters[{ci}].outer", outer, True
        collections = [("inners", cluster.inners)]
        if cluster.detected is not None:
            collections += list(cluster.detected.items())
        for name, items in collections:
            for k, item in enumerate(items):
                geom = _item_geometry(item)
                if geom is not None:
                    yield f"clusters[{ci}].{name}[{k}]", geom, geom.geom_type == "Polygon"
    for k, curve in enumerate(result.loose):
        if isinstance(curve, ClosedCurve) and (curve.role == ContourRole.UNKNOWN or is_structural_role(curve.role)):
            geom = _item_geometry(curve)
            if geom is not None:
                yield f"loose[{k}]", geom, geom.geom_type == "Polygon"


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
