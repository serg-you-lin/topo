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

import math
from typing import Optional

from ..core.geometry.regions import nearest_point
from ..model.result import Result


def anchor_texts(result: Result, *, snap_distance: float = 0.0) -> None:
    """
    Set ``cluster_ref`` on every text of ``result.texts``.

    ``cluster_ref`` is the index in ``result.clusters`` of the part whose
    outer contour contains the text's position (border included); a text
    outside every part (a title block) keeps ``None``. With ``snap_distance``
    > 0 a text contained by no part goes to the nearest one within that
    distance of its outer. Computed on the primitives.

    **Mutates** the texts of ``result`` and returns ``None``.
    """
    outers = [(i, c.outer) for i, c in enumerate(result.clusters) if c.outer is not None]
    if not outers:
        return
    for text in result.texts:
        text.cluster_ref = _assign(text.position, outers, snap_distance)


def _assign(position, outers, snap_distance: float) -> Optional[int]:
    for i, outer in outers:
        if outer.contains(position):
            return i
    return _nearest_within(position, outers, snap_distance)


def _nearest_within(position, outers, snap_distance: float) -> Optional[int]:
    """The index of the part nearest ``position``, if within ``snap_distance`` (> 0)."""
    if snap_distance <= 0.0:
        return None
    idx, dist = min(
        ((i, math.dist(position, nearest_point(outer.segments, position))) for i, outer in outers),
        key=lambda pair: pair[1],
    )
    return idx if dist <= snap_distance else None
