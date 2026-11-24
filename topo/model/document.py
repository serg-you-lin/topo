"""
model/document.py
-----------------
The Document — output of an adapter (or of `topo.load_geometry`) and the only input of topo.heal().

Fields:

    edges      : parsed geometry (pure Edges) — input for heal()
    texts       : the source's texts — pure data, input for write()
    source_path : path of the opened file
    source_format: what the geometry comes from, told by the adapter
                  (the name the adapter chooses, e.g. `pdf` or `geometry`; open string)
    notes       : what the adapter did by itself on the file (exploded
                  INSERTs, duplicates removed, Z brought onto the plane), `Diagnostic`
    warnings    : diagnostics collected by the adapter on the raw file — audit,
                  unexploded INSERTs, entities with Z != 0 brought onto the
                  plane, duplicates removed. topo.validate_document(doc) re-raises them.

No field carries an object of a format library: edges and texts are pure data
produced by the adapter.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import TYPE_CHECKING, List

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
    source_path: str                 = ""
    source_format: str               = ""
    warnings:    List[str]           = field(default_factory=list)
    notes:       List[str]           = field(default_factory=list)
