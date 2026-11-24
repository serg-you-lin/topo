"""
model/result.py

The Result: what a reading (`faces()`, `outlines()`) returns — the clusters
found, the loose curves, the texts and the diagnostics.
"""
from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from dataclasses import field
from typing import Any, List, Optional, Sequence
from .curve import ClosedCurve, OpenCurve
from .cluster import Cluster
from .overlay import Overlay, _feature_drawable
from .text import Text


@dataclass
class Result:
    """What a reading (`Network.faces()`, `Network.outlines()`) hands to the
    caller: the pieces found + validation info.

    Fields:
        warnings  : advice about the drawing; notes : what topo did on its
                    own; errors : nothing to read — all `Diagnostic`.
        source_format, reading, max_gap : where the geometry comes
                    from and how it was read, copied from the network.
        texts     : the source's texts (list[Text]), copied here by
                    heal() from the Document. They are format-independent
                    domain data: every renderer (an adapter's writer,
                    to_svg) draws them from the model, without
                    re-reading the source.
        loose     : every curve that is no cluster's contour: chains that
                    close nothing, open traces, closed curves with a
                    non-structural role. What they are is decided by the
                    consumer, who moves them into `cluster.overlay` with
                    `promote()`. `cluster_ref` says which cluster contains them."""
    clusters:               List[Cluster]        = field(default_factory=list)
    _: KW_ONLY
    source_file:         str                    = ""
    source_format:       str                    = ""
    reading:             str                    = ""
    max_gap:             float                  = 0.0
    warnings:            List[str]              = field(default_factory=list)
    notes:               List[str]              = field(default_factory=list)
    errors:              List[str]              = field(default_factory=list)
    loose:               List[OpenCurve | ClosedCurve] = field(default_factory=list)
    texts:               List[Text]             = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when the reading raised no error: computed, never set."""
        return not self.errors

    def promote(self, curves: OpenCurve | ClosedCurve | Sequence[OpenCurve | ClosedCurve],
                cluster: Cluster, name: str, *, item: Optional[Any] = None) -> None:
        """Remove `curves` (one curve or more) from `loose` and put a single `item` in
        the collection `name` of `cluster.overlay`, creating it if missing. `item` is
        the object the caller made of them; with a single curve it may be missing and
        then it is the curve itself.

        It does not matter where the curves are: even a curve outside every cluster
        (`cluster_ref is None`) attaches to the one the caller chooses.

        Raises `ValueError`, touching nothing, if a curve is not in `loose` or is
        given twice, if `curves` is empty, if `cluster` is not in `clusters`, if there
        are several curves and `item` is missing, or if `item` carries no geometry to
        draw: the curves would leave `loose` without reaching any file. Nothing is
        written twice or lost."""
        group = [curves] if isinstance(curves, (OpenCurve, ClosedCurve)) else list(curves)
        if not group:
            raise ValueError("promote(): no curve")
        if item is None and len(group) > 1:
            raise ValueError("promote(): several curves make one item, and item is missing")
        at = {id(c): k for k, c in enumerate(self.loose)}
        if len({id(c) for c in group}) < len(group):
            raise ValueError("promote(): a curve is given twice")
        if any(id(c) not in at for c in group):
            raise ValueError("promote(): a curve is not in result.loose")
        if not any(c is cluster for c in self.clusters):
            raise ValueError("promote(): the cluster is not in result.clusters")
        if item is not None and not _feature_drawable(item):
            raise ValueError("promote(): item carries no geometry (no `contours` or `segments` with a role): "
                             "the curves would leave result.loose and reach no output")
        if cluster.overlay is None:
            cluster.overlay = Overlay()
        cluster.overlay.add(name, group[0] if item is None else item)
        for k in sorted((at[id(c)] for c in group), reverse=True):
            del self.loose[k]

    def to_dict(self) -> dict:
        """The `Result` as plain data, geometry only: where it comes from, how it was
        read, whether it is valid, the warnings, and the facts of every cluster
        (`Cluster.to_dict`). No coordinates: the exact curves are carried by an
        adapter's writer. It is the only source of `topo.to_json`."""
        return {
            "source_file":   self.source_file,
            "source_format": self.source_format,
            "reading":       self.reading,
            "max_gap":       self.max_gap,
            "is_valid":      self.is_valid,
            "warnings":      [str(w) for w in self.warnings],
            "notes":         [str(n) for n in self.notes],
            "errors":        [str(e) for e in self.errors],
            "loose_count":   len(self.loose),
            "text_count":    len(self.texts),
            "clusters":      [c.to_dict() for c in self.clusters],
        }