"""
topo/core/readings/heal.py
--------------------------
`heal()`: un Document diventa la rete riparata (D202), una volta sola. Le
letture sono metodi della rete: `faces()` dall'interno, `outlines())
dall'esterno.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

from typing import Callable, Optional

from ...model.document import Document
from .network import Network, build_network


def heal(doc: Document, *, max_gap: Optional[float] = None,
         is_structural: Optional[Callable[[str], bool]] = None,
         source_file: str = "", label: str = "") -> Network:
    """
    Repair `doc` once and return the repaired `Network`; read it with
    `.faces()` (from the inside: outers with their inners) or `.outlines()`
    (from the outside: one outline per group of touching edges).

    A curve written as many short lines (10 or more, each under
    `topo.precision.TESSELLATION_SIDE`) is replaced by lines, arcs, conics
    and splines within `topo.precision.POINTS_NOISE` of its points: a detail
    smaller than that (a corner, a hook) can be smoothed away (D321).

    max_gap:       the widest gap closed between free ends, and the distance
                   at which `outlines()` groups edges. None: no gap is closed
                   (D267). Two points closer than `topo.precision.SAME_POINT`
                   are always one point (D268, D269); it is not a parameter.
    is_structural: `Callable[[str], bool]` — "is this role part of a contour?".
                   Edges whose role is not structural stay out of every
                   reading and go to `loose` with their role. Without it only
                   outer/inner/unknown are structural, with a warning when
                   other roles are present.
    source_file:   copied onto every Result and Cluster. Empty: `doc.source_path`.
    label:         copied onto every Cluster read from the network.
    """
    if not isinstance(doc, Document):
        raise TypeError(
            f"topo.heal() takes a Document, got {type(doc).__name__}"
        )
    return build_network(doc, max_gap=max_gap, is_structural=is_structural,
                         source_file=source_file or doc.source_path, label=label)
