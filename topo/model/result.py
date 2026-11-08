from __future__ import annotations

from dataclasses import KW_ONLY, dataclass
from dataclasses import field
from typing import Any, List, Optional, Sequence
from .curve import ClosedCurve, OpenCurve
from .cluster import Cluster
from .detected import DetectedFeatures
from .text import Text


@dataclass
class Result:
    """
    Ciò che una lettura (`Network.faces()`, `Network.outlines()`) dà al
    chiamante: i pezzi trovati + info di validazione.

    Campi:
        source_format, reading, tolerance, max_gap : da che cosa arriva la
                    geometria e come è stata letta, copiati dalla rete (D231).
        texts     : i testi della sorgente (list[Text], D138), copiati
                    qui da heal() dal Document. Sono dati di dominio
                    indipendenti dal formato: ogni renderer (to_dxf, un
                    futuro to_svg/to_pdf) li disegna dal modello, senza
                    rileggere la sorgente.
        loose     : ogni curva che non è contorno di nessun cluster (MAP.md
                    D137): catene che non chiudono niente, tracce aperte,
                    curve chiuse con un ruolo non strutturale. Cosa sono lo
                    decide il consumatore, che le sposta in `cluster.detected`
                    con `promote()`. `cluster_ref` dice quale cluster le
                    contiene.
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
        nella collezione `name` di `cluster.detected`, creandolo se manca
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
            raise ValueError("promote(): nessuna curva")
        if item is None and len(group) > 1:
            raise ValueError("promote(): più curve sono un solo item, e item manca")
        at = {id(c): k for k, c in enumerate(self.loose)}
        if len({id(c) for c in group}) < len(group):
            raise ValueError("promote(): una curva è data due volte")
        if any(id(c) not in at for c in group):
            raise ValueError("promote(): una curva non è in result.loose")
        if not any(c is cluster for c in self.clusters):
            raise ValueError("promote(): il cluster non è in result.clusters")
        if cluster.detected is None:
            cluster.detected = DetectedFeatures()
        cluster.detected.add(name, group[0] if item is None else item)
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
            "errors":        [str(e) for e in self.errors],
            "loose_count":   len(self.loose),
            "text_count":    len(self.texts),
            "clusters":      [c.to_dict() for c in self.clusters],
        }