"""
model/document.py
-----------------
Il Document — output di un adapter (o di `topo.load_geometry`) e unico input di topo.heal().

il loader restituisce questo oggetto di

    edges       : geometria parsata (Edge puri) — input per heal()
    texts       : i testi della sorgente (D138) — dati puri, input per write()
    source_meta : header rilevanti del file sorgente ($INSUNITS, $MEASUREMENT, …)
    source_path : percorso del file aperto
    source_format: da che cosa arriva la geometria, detto dall'adapter
                  (il nome che l'adapter sceglie, es. `pdf` o `geometry`; stringa aperta, D231)
    notes       : cosa l'adapter ha fatto da sé sul file (INSERT esplosi,
                  duplicati tolti, Z riportate sul piano), `Diagnostic` (D233)
    warnings    : diagnostica raccolta dall'adapter sul file grezzo — audit,
                  INSERT non esplosi, entità con Z != 0 riportate sul piano,
                  duplicati rimossi. topo.validate_document(doc) le rilancia.

Nessun campo porta un oggetto di una libreria di formato: edges e texts sono dati puri
prodotti dall'adapter, source_meta è un dizionario di primitivi.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

from .text import Text

if TYPE_CHECKING:
    from ..core.topology.edge import Edge



@dataclass
class Document:
    """
    Domain document produced by an adapter or by
    `topo.load_geometry` / `topo.load_segments`.

    Contract: `heal()` works only on this object and on the Result derived
    from it — never on a format library's objects.
    """
    edges:       List["Edge"]        = field(default_factory=list)
    _: KW_ONLY
    texts:       List[Text]           = field(default_factory=list)
    source_meta: Dict[str, Any]      = field(default_factory=dict)
    source_path: str                 = ""
    source_format: str               = ""
    warnings:    List[str]           = field(default_factory=list)
    notes:       List[str]           = field(default_factory=list)
