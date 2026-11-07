"""
tests/readings.py
-----------------
Una sola lettura `outlines()` per geometria in tutta la suite (i file gemelli contano una volta): invarianti,
golden e ancoraggio leggono gli stessi fogli con gli
stessi parametri. Ogni chiamata riceve una copia indipendente (documento e
risultato), perché alcuni test li modificano (`anchor_texts` scrive
`cluster_ref` sul posto).

Le invarianti leggono anche ogni disegno scritto in un altro modo
(`scrambled`, D158): una lettura in più per disegno, una sola (D160), e
per i disegni distinti una per ognuno degli angoli in più (D180).
"""

import hashlib
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import topo
import topo_dxf
from topo.model.document import Document

from tests.invariants import ROTATION, scrambled


@lru_cache(maxsize=None)
def _document(path: str) -> Tuple[bytes, str]:
    """Il documento di `path` e l'impronta di geometria e testi: due file
    gemelli danno la stessa lettura, che si fa una volta sola."""
    doc = topo_dxf.load_dxf(path)
    key = geometry_key(doc) + hashlib.sha1(repr(doc.texts).encode()).hexdigest()
    return pickle.dumps(doc), key


_OUTLINES: dict = {}   # (impronta, max_gap) → risultato di outlines()


def outline_reading(path: Path, max_gap: float) -> Tuple[Document, topo.Result]:
    """(documento, risultato) di `heal(load_dxf(path), max_gap=max_gap).outlines()`,
    letti una volta per sessione (una per gemelli) e restituiti come copia nuova."""
    data, key = _document(str(Path(path).resolve()))
    doc = pickle.loads(data)
    if (key, max_gap) not in _OUTLINES:
        _OUTLINES[(key, max_gap)] = pickle.dumps(topo.heal(doc, max_gap=max_gap).outlines())
    return doc, pickle.loads(_OUTLINES[(key, max_gap)])



@lru_cache(maxsize=None)
def _scrambled_bytes(path: str, max_gap: float, angle: float, seed: int) -> bytes:
    return pickle.dumps(topo.heal(scrambled(topo_dxf.load_dxf(path), angle, seed), max_gap=max_gap).outlines())


def outline_scrambled(path: Path, max_gap: float, angle: float = ROTATION, seed: int = 0) -> topo.Result:
    """`outlines()` di `scrambled(load_dxf(path), angle, seed)`, letto una volta
    per sessione e restituito come copia nuova."""
    return pickle.loads(_scrambled_bytes(str(Path(path).resolve()), max_gap, angle, seed))


def geometry_key(doc: Document) -> str:
    """Un'impronta della geometria di `doc`: due file diversi con le stesse
    curve (disegni gemelli) hanno la stessa, e si leggono una volta (D180)."""
    shapes = sorted(repr((e.segment, e.role)) for e in doc.edges)
    return hashlib.sha1("\n".join(shapes).encode()).hexdigest()
