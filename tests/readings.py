"""
tests/readings.py
-----------------
Una sola lettura `island()` per disegno in tutta la suite: invarianti,
golden, ancoraggio e budget di `to_text` leggono gli stessi fogli con gli
stessi parametri. Ogni chiamata riceve una copia indipendente (documento e
risultato), perché alcuni test li modificano (`anchor_texts` scrive
`cluster_ref` sul posto).

Le invarianti leggono anche ogni disegno scritto in un altro modo
(`scrambled`, D158): una lettura in più per disegno, una sola (D160).
"""

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import topo
import topo_dxf
from topo.model.document import Document

from tests.invariants import scrambled


@lru_cache(maxsize=None)
def _island_bytes(path: str, max_gap: float) -> bytes:
    doc = topo_dxf.load_dxf(path)
    return pickle.dumps((doc, topo.island(doc, max_gap=max_gap)))


def island_reading(path: Path, max_gap: float) -> Tuple[Document, topo.Result]:
    """(documento, risultato) di `island(load_dxf(path), max_gap=max_gap)`,
    letti una volta per sessione e restituiti come copia nuova."""
    return pickle.loads(_island_bytes(str(Path(path).resolve()), max_gap))



@lru_cache(maxsize=None)
def _scrambled_bytes(path: str, max_gap: float) -> bytes:
    return pickle.dumps(topo.island(scrambled(topo_dxf.load_dxf(path)), max_gap=max_gap))


def island_scrambled(path: Path, max_gap: float) -> topo.Result:
    """`island()` di `scrambled(load_dxf(path))`, letto una volta per
    sessione e restituito come copia nuova."""
    return pickle.loads(_scrambled_bytes(str(Path(path).resolve()), max_gap))
