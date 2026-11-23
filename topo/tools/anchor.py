"""
topo/tools/anchor.py
---------------------------
Text anchoring: links every text of the model to the part that contains it.
Pure geometric reconstruction, no judgment, nothing to do with the meaning of
the drawing.

A separate, optional phase — NOT called by heal(): the caller turns it on when
needed (e.g. before split(), to know which text goes with which part).

``anchor_texts`` fills ``Text.cluster_ref`` (index of the containing part).
What a callout's tip lands on or what a dimension measures is the consumer's
reading.
"""

from __future__ import annotations

from typing import Optional

from shapely.geometry import Point

from ..core.geometry.shapely_polygons import curve_polygon
from ..model.result import Result


def anchor_texts(result: Result, *, snap_distance: float = 0.0) -> None:
    """
    Set ``cluster_ref`` on every text of ``result.texts``.

    ``cluster_ref`` is the index in ``result.clusters`` of the part whose
    outer contour covers the text's position; a text outside every part (a
    title block) keeps ``None``. With ``snap_distance`` > 0 a text covered by
    no part goes to the nearest one within that distance of its outer.

    **Mutates** the texts of ``result`` and returns ``None``.
    """
    refs = _outer_polygons(result)
    if not refs:
        return
    for text in result.texts:
        text.cluster_ref = _assign(text.position, refs, snap_distance)


def _outer_polygons(result: Result) -> list:
    """(index, polygon of the outer) for every part that has one."""
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
    """The index of the part nearest ``probe``, if within ``snap_distance`` (> 0)."""
    if snap_distance <= 0.0 or not refs:
        return None
    idx, dist = min(
        ((i, poly.distance(probe)) for i, poly in refs),
        key=lambda pair: pair[1],
    )
    return idx if dist <= snap_distance else None
