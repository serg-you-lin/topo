"""
topo/tools/split.py
-------------------
One Result per part. A part is a cluster with the loose curves and the texts
that belong to it; what no part contains comes back apart, and the caller
decides where it goes. Every exporter then writes a part in its format (an
adapter's writer, `topo.experimental.to_svg`): the same split exports parts in
every format.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from typing import List

from ..model import Result
from ..model.curve import ClosedCurve, OpenCurve
from ..model.text import Text


@dataclass
class Split:
    """What `split` returns: the pieces, and what no piece contains.

    Fields:
        pieces: one `Result` per cluster, in the order of `result.clusters`.
        loose : the loose curves with no `cluster_ref`.
        texts : the texts no piece owns: no `cluster_ref`, and no outer contour
                contains their position."""
    pieces: List[Result]                 = field(default_factory=list)
    loose: List[OpenCurve | ClosedCurve] = field(default_factory=list)
    texts: List[Text]                    = field(default_factory=list)


def split(result: Result) -> Split:
    """
    The parts of `result`, and what belongs to none.

    Each part is a `Result` with a single cluster, the loose curves and the
    texts that belong to it, the cluster labelled `f"{label}_P{i + 1}"`. A loose
    curve goes to the part of its `cluster_ref`. A text goes to the part of its
    `cluster_ref` (`anchor_texts` sets it, with the caller's `snap_distance`),
    else to the first part whose outer contour contains its position, border
    included. What no part owns lands in `Split.loose` and `Split.texts`:
    nothing is assigned by distance. Nothing is duplicated and nothing is lost:
    every element is in one place only, copied with `cluster_ref` referring to
    the part (0 if it was the part's, `None` otherwise). A promoted curve
    (`result.promote`) is already in its cluster. The other `Result` fields
    (source, warnings) are copied into every part.

    **Mutates** nothing: a part's cluster is a copy with its own `label`.

    Raises `ValueError` if `result` is not valid: one file per part makes no
    sense without pieces.
    """
    if not result.is_valid:
        raise ValueError(
            "split(): the Result is not valid, no output. "
            + " ".join(result.errors)
        )

    loose_of, loose_out = _owners(result.loose, lambda c: c.cluster_ref)
    texts_of, texts_out = _owners(result.texts, lambda t: _text_owner(t, result.clusters))

    pieces = [
        replace(
            result,
            clusters=[replace(cluster, label=f"{cluster.label}_P{i + 1}")],
            loose=_local(loose_of.get(i, []), i),
            texts=_local(texts_of.get(i, []), i),
            warnings=list(result.warnings),
            errors=list(result.errors),
        )
        for i, cluster in enumerate(result.clusters)
    ]
    return Split(pieces, [copy.copy(c) for c in loose_out], [copy.copy(t) for t in texts_out])


def _owners(items: list, owner_of) -> tuple[dict[int, list], list]:
    """(cluster index → its items, the items no cluster owns), in the order of `items`."""
    owned: dict[int, list] = {}
    outside: list = []
    for item in items:
        i = owner_of(item)
        if i is None:
            outside.append(item)
        else:
            owned.setdefault(i, []).append(item)
    return owned, outside


def _text_owner(text: Text, clusters) -> int | None:
    """The cluster a text follows: its `cluster_ref`, else the first whose outer contains it."""
    if text.cluster_ref is not None:
        return text.cluster_ref
    for i, cluster in enumerate(clusters):
        if cluster.outer is not None and cluster.outer.contains(text.position):
            return i
    return None


def _local(items: list, i: int) -> list:
    """Copies of `items` with `cluster_ref` referring to the Result of a single part."""
    out = []
    for item in items:
        local = copy.copy(item)
        local.cluster_ref = 0 if item.cluster_ref == i else None
        out.append(local)
    return out
