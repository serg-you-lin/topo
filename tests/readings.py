"""
tests/readings.py
-----------------
A single `outlines()` reading per geometry in the whole suite (twin files count
once): invariants, golden and anchoring read the same sheets with the same
parameters. Every call gets an independent copy (document and result), because
some tests modify them (`anchor_texts` writes `cluster_ref` in place).

The invariants also read every drawing written another way (`scrambled`): one
more reading per drawing, a single one, and for distinct drawings one for each
of the extra angles.
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
    """The document of `path` and the fingerprint of geometry and texts: two twin
    files give the same reading, which is done once."""
    doc = topo_dxf.load_dxf(path)
    key = geometry_key(doc) + hashlib.sha1(repr(doc.texts).encode()).hexdigest()
    return pickle.dumps(doc), key


_OUTLINES: dict = {}   # (fingerprint, max_gap) → result of outlines()


def outline_reading(path: Path, max_gap: float) -> Tuple[Document, topo.Result]:
    """(document, result) of `heal(load_dxf(path), max_gap=max_gap).outlines()`, read
    once per session (one per twins) and returned as a new copy."""
    data, key = _document(str(Path(path).resolve()))
    doc = pickle.loads(data)
    if (key, max_gap) not in _OUTLINES:
        _OUTLINES[(key, max_gap)] = pickle.dumps(topo.heal(doc, max_gap=max_gap).outlines())
    return doc, pickle.loads(_OUTLINES[(key, max_gap)])



@lru_cache(maxsize=None)
def _scrambled_bytes(path: str, max_gap: float, angle: float, seed: int) -> bytes:
    return pickle.dumps(topo.heal(scrambled(topo_dxf.load_dxf(path), angle, seed), max_gap=max_gap).outlines())


def outline_scrambled(path: Path, max_gap: float, angle: float = ROTATION, seed: int = 0) -> topo.Result:
    """`outlines()` of `scrambled(load_dxf(path), angle, seed)`, read once per
    session and returned as a new copy."""
    return pickle.loads(_scrambled_bytes(str(Path(path).resolve()), max_gap, angle, seed))


def geometry_key(doc: Document) -> str:
    """A fingerprint of the geometry of `doc`: two different files with the same
    curves (twin drawings) have the same one, and are read once."""
    shapes = sorted(repr((e.segment, e.role)) for e in doc.edges)
    return hashlib.sha1("\n".join(shapes).encode()).hexdigest()
