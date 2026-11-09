from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from dataclasses import field
from typing import Any, List, Optional, Sequence
from .curve import ClosedCurve, OpenCurve
from .cluster import Cluster
from .overlay import Overlay
from .text import Text


@dataclass
class Result:
    """
    What a reading (`Network.faces()`, `Network.outlines()`) hands to the
    caller: the pieces found + validation info.

    Fields:
        warnings  : advice about the drawing; notes : what topo did on its
                    own; errors : nothing to read — all `Diagnostic` (D233).
        source_format, reading, tolerance, max_gap : where the geometry comes
                    from and how it was read, copied from the network (D231).
        texts     : the source's texts (list[Text], D138), copied here by
                    heal() from the Document. They are format-independent
                    domain data: every renderer (to_dxf, a future
                    to_svg/to_pdf) draws them from the model, without
                    re-reading the source.
        loose     : every curve that is no cluster's contour (MAP.md
                    D137): chains that close nothing, open traces, closed
                    curves with a non-structural role. What they are is
                    decided by the consumer, who moves them into
                    `cluster.overlay` with `promote()`. `cluster_ref` says
                    which cluster contains them.
    """
    clusters:               List[Cluster]        = field(default_factory=list)
    _: KW_ONLY
    source_file:         str                    = ""
    source_format:       str                    = ""
    reading:             str                    = ""
    tolerance:           float                  = 0.0
    max_gap:             float                  = 0.0
    is_valid:            bool                   = True
    warnings:            List[str]              = field(default_factory=list)
    notes:               List[str]              = field(default_factory=list)
    errors:              List[str]              = field(default_factory=list)
    loose:               List[OpenCurve | ClosedCurve] = field(default_factory=list)
    texts:               List[Text]             = field(default_factory=list)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    @property
    def has_issues(self) -> bool:
        return bool(self.warnings or self.errors)

    def promote(self, curves: OpenCurve | ClosedCurve | Sequence[OpenCurve | ClosedCurve],
                cluster: Cluster, name: str, *, item: Optional[Any] = None) -> None:
        """
        Toglie `curves` (una curva o più) da `loose` e mette un solo `item`
        nella collezione `name` di `cluster.overlay`, creandolo se manca
        (D137, D172, D173). `item` è l'oggetto che il chiamante ne ha fatto;
        con una curva sola può mancare e allora è la curva stessa.

        Non conta dove stanno le curve: anche una curva fuori da ogni cluster
        (`cluster_ref is None`) si attacca a quello che il chiamante sceglie.

        Solleva `ValueError`, senza toccare niente, se una curva non è in
        `loose` o è data due volte, se `curves` è vuoto, se `cluster` non è
        in `clusters`, o se le curve sono più d'una e `item` manca: niente
        viene scritto due volte né perso.
        """
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
        if cluster.overlay is None:
            cluster.overlay = Overlay()
        cluster.overlay.add(name, group[0] if item is None else item)
        for k in sorted((at[id(c)] for c in group), reverse=True):
            del self.loose[k]

    def to_dict(self) -> dict:
        """
        Il `Result` come dati semplici, solo geometria (D230, D231): da dove
        arriva, come è stato letto, se è valido, gli avvisi, e i fatti di ogni
        cluster (`Cluster.to_dict`). Nessuna coordinata: le curve esatte le
        porta il DXF. È la sola fonte di `topo.to_json`.
        """
        return {
            "source_file":   self.source_file,
            "source_format": self.source_format,
            "reading":       self.reading,
            "tolerance":     self.tolerance,
            "max_gap":       self.max_gap,
            "is_valid":      self.is_valid,
            "warnings":      [str(w) for w in self.warnings],
            "notes":         [str(n) for n in self.notes],
            "errors":        [str(e) for e in self.errors],
            "loose_count":   len(self.loose),
            "text_count":    len(self.texts),
            "clusters":      [c.to_dict() for c in self.clusters],
        }