"""
topo/tools/anchor.py
---------------------------
Ancoraggio dei testi: collega ogni testo del modello alla parte che lo
contiene (MAP.md D43, D138). Pura ricostruzione geometrica, zero giudizio,
niente a che fare col significato del disegno.

Fase separata e opzionale — NON viene chiamata da heal(): il chiamante la
attiva quando gli serve (es. prima di split(), per sapere quale
testo va con quale pezzo).

``anchor_texts`` popola ``Text.cluster_ref`` (indice della parte
contenitrice). Su cosa cade la punta di un richiamo o cosa misura una quota
è una lettura del consumer (D259).
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import Point

from ..core.geometry.polygons import curve_polygon
from ..model.result import Result


def anchor_texts(result: Result, *, snap_distance: float = 0.0) -> None:
    """
    Set ``cluster_ref`` on every text of ``result.texts``.

    ``cluster_ref`` is the index in ``result.clusters`` of the part whose
    outer contour covers the text's position; a text outside every part (a
    title block) keeps ``None``. With ``snap_distance`` > 0 a text covered by
    no part goes to the nearest one within that distance of its outer (D82).

    **Mutates** the texts of ``result`` and returns ``None`` (D176).
    """
    refs = _outer_polygons(result)
    if not refs:
        return
    for text in result.texts:
        text.cluster_ref = _assign(text.position, refs, snap_distance)


def _outer_polygons(result: Result) -> list:
    """(indice, poligono dell'outer) per ogni parte che ne ha uno."""
    return [
        (i, poly)
        for i, p in enumerate(result.clusters)
        if p.outer is not None
        for poly in [curve_polygon(p.outer)]
        if poly is not None and not poly.is_empty
    ]


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
