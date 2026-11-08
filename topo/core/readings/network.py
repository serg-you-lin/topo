"""
topo/core/readings/network.py
-----------------------------
La riparazione comune a ogni lettura (D202): un Document diventa una rete di
edge riparati, una volta sola, con due numeri — `tolerance` per i nodi e
`max_gap` per i gap. `heal()` la restituisce; le letture (`faces()`,
`outlines()`) partono da qui e non riparano più per conto loro.

Puro: solo Edge, primitive e modello, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Callable, List, Optional

from ...model.document import Document
from ...model.text import Text
from ...model.role import is_structural_role
from ...model.diagnostic import Diagnostic
from ..base.cleanup import NEAR_FULL_ARC_MISSING, dangling_splines, near_free_gaps, open_near_full_arcs
from ..base.normalizer import near_copies
from ..base.prepare import normalize, prepare
from ..geometry.measure import reach
from ..primitives.segments import segment_is_closed
from ..topology.edge import Edge
from ..topology.noding import GRAPH_EPSILON, NodedEdges, decide_nodes, split_at_crossings
from .heal_steps import free_ends

if TYPE_CHECKING:
    from ...model.result import Result


@dataclass(kw_only=True)
class Network:
    """The repaired drawing, built once by `heal()` and read by `faces()` or
    `outlines()`.

    edges:       the repaired edges (doubles merged, gaps closed, nodes decided).
    set_aside:   edges whose role is not structural; every reading puts them
                 in `loose` with their role.
    crossings:   points where two edges cross without a shared node.
    free_ends:   (point, distance to the nearest node) of every end no other
                 edge reaches.
    tolerance:   the node tolerance used (from the document when not given).
    max_gap:     the widest gap closed (at least `tolerance`).
    source_file, label: copied onto every Result and Cluster read from here.
    source_format: the document's (D231), copied onto every Result.
    warnings, errors, is_valid: what the repair did; with errors no reading
                 finds anything.
    """
    edges:       List[Edge] = field(default_factory=list)   # riparati, nodi decisi
    set_aside:   List[Edge] = field(default_factory=list)   # ruoli non strutturali (D30)
    warnings:    List[str] = field(default_factory=list)
    errors:      List[str] = field(default_factory=list)
    tolerance:   float = 0.0
    max_gap:     float = 0.0
    source_file: str = ""
    label:       str = ""
    source_format: str = ""
    _structural: Callable[[str], bool] = field(default=is_structural_role, repr=False)
    _texts:      List[Text] = field(default_factory=list, repr=False)   # del Document, per ogni Result

    @property
    def is_valid(self) -> bool:
        """True when the repair raised no error."""
        return not self.errors

    @cached_property
    def _noded(self) -> NodedEdges:
        # la rete piana senza tagliare gli incroci (D132): gli incroci restano
        # un dato, il taglio è della lettura che lo chiede
        return split_at_crossings(self.edges, self.tolerance, cut_crossings=False)

    @property
    def crossings(self) -> list:
        """Points where two edges cross without a shared node."""
        return self._noded.crossings

    @property
    def free_ends(self) -> list:
        """(point, distance to the nearest node) for every end no other edge reaches."""
        return free_ends(self._noded.pieces, GRAPH_EPSILON)

    def faces(self) -> Result:
        """Read the network from the inside: one Cluster per closed outer
        contour, with its inners by containment. The reading for a flat
        drawing (a cutting file, a nesting of separate parts)."""
        # import qui: le letture importano la riparazione (repair_edges)
        from .faces import read_faces
        return read_faces(self)

    def outlines(self) -> Result:
        """Read the network from the outside: the edges that touch within
        `max_gap` are a group, the outer face of each group is its outline,
        and every outline not inside another is a Cluster with only its
        `outer`. Everything else goes to `loose` with the Cluster it touches
        or lies in. The reading for a sheet of views."""
        from .outline import read_network_outlines
        return read_network_outlines(self)


def build_network(doc: Document, *, tolerance: Optional[float] = None,
                  max_gap: Optional[float] = None,
                  is_structural: Optional[Callable[[str], bool]] = None,
                  source_file: str = "", label: str = "") -> Network:
    """
    Ripara `doc` una volta per tutte le letture (D187, D202): ruoli non
    strutturali da parte, nodi decisi, pulizie di `normalize` con i gap fino a
    `max_gap` (default `tolerance`), tratti degeneri tolti.
    """
    tol = doc.node_tolerance(override=tolerance)
    gap = tol if max_gap is None else max(tol, max_gap)
    net = Network(tolerance=tol, max_gap=gap, source_file=source_file, label=label,
                  source_format=doc.source_format,
                  _structural=is_structural or is_structural_role, _texts=list(doc.texts))
    if not doc.edges:
        net.errors.append("Modelspace vuoto: nessuna geometria trovata.")
        return net
    prepared = prepare(doc.edges, net._structural)
    net.set_aside = prepared.labeled
    if not prepared.edges and not prepared.labeled:
        net.errors.append("Nessuna geometria trovata.")
        return net
    if prepared.labeled and is_structural is None:
        net.warnings.append(_LABELED_WITHOUT_PREDICATE.format(n=len(prepared.labeled)))
    # una retta quasi sopra un'altra: topo la legge com'è, il chiamante decide (D226, D227)
    copies = near_copies(prepared.edges, tol)
    if copies:
        net.warnings.append(_near_copy_warning(copies))

    # un gap largo quanto la soglia si chiude a ogni riferimento, non a
    # seconda dell'ultimo bit (D183)
    clean = normalize(prepared.edges, reach(gap), keep_junctions=True)
    for count, what in ((clean.merged_lines, "segmenti collineari sovrapposti fusi"),
                        (clean.merged_arcs, "archi o cerchi co-circolari sovrapposti fusi"),
                        (clean.welded + prepared.welded, "LineSeg degeneri (sub-tolleranza) saldati")):
        if count:
            net.warnings.append(f"{count} {what} prima della ricerca loop.")
    if clean.full_arcs:
        net.warnings.append(f"{clean.full_arcs} archi sullo stesso cerchio chiusi o uniti sui buchi (entro "
                            f"tolleranza e al più {math.degrees(NEAR_FULL_ARC_MISSING):.0f}°).")
    if clean.ambiguous:
        first = ", ".join(f"({p[0]:.2f}, {p[1]:.2f})" for p in clean.ambiguous[:4])
        net.warnings.append(f"{len(clean.ambiguous)} estremi liberi con due compagni alla stessa distanza "
                            f"(figura simmetrica): nessun gap chiuso lì, decide il disegno ({first}).")
    net.edges = _no_degenerate(clean.edges)
    # quello che si è quasi chiuso, uno per tipo, coi punti dal più vicino (D227)
    arcs = open_near_full_arcs(net.edges, reach(gap))
    if arcs:
        net.warnings.append(_open_arc_warning(arcs))
    gaps = near_free_gaps(net.edges, reach(gap), reach(_NEAR_GAP_REACH * gap))
    if gaps:
        net.warnings.append(_near_gap_warning(gaps, gap))
    if dangling_splines(net.edges):
        net.warnings.append(
            "SPLINE con endpoint non connesso trovata — "
            "gap tra SPLINE e altre entità gestito con una linea di congiunzione. "
            "Verificare manualmente la correttezza del file."
        )
    return net


def repair_edges(edges: List[Edge], tolerance: float, max_gap: float) -> List[Edge]:
    """La stessa riparazione su edge sciolti, per chi legge senza un Document
    (experimental): nodi decisi, `normalize`, degeneri tolti."""
    noded, _ = decide_nodes(edges)
    return _no_degenerate(normalize(noded, reach(max(tolerance, max_gap)), keep_junctions=True).edges)


def _no_degenerate(edges: List[Edge]) -> List[Edge]:
    """Un tratto ridotto a un punto non è una curva (un cerchio sì)."""
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _ceil_2(x: float) -> float:
    """`x` arrotondato per eccesso a due cifre significative: la soglia
    suggerita deve bastare, non quasi bastare."""
    if x <= 0:
        return x
    step = 10 ** (math.floor(math.log10(x)) - 1)
    return math.ceil(x / step - 1e-9) * step


_NEAR_GAP_REACH = 2.0   # un gap fino al doppio della soglia "c'è quasi"; oltre è geometria (D227)


def _span(values, fmt: str) -> str:
    lo, hi = min(values), max(values)
    return format(lo, fmt) if lo == hi else f"{format(lo, fmt)} to {format(hi, fmt)}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _near_copy_warning(pairs: list) -> Diagnostic:
    offset = max(p.offset for p in pairs)
    return Diagnostic(
        "near-copy", f"{_plural(len(pairs), 'line', 'lines')} nearly on top of a longer one, not merged",
        points=[p.at for p in pairs],
        notes=[f"{_span([p.offset for p in pairs], '.2g')} mm apart; not one line for D184 "
               f"(parallel within 1e-7, ends within 1e-3 mm), so topo reads both"],
        help=f"doc.edges = topo.experimental.merge_near_copies(doc.edges, distance={_ceil_2(offset):g}) "
             f"before heal() keeps the longer of each pair",
        param="distance", value=offset)


def _open_arc_warning(arcs: list) -> Diagnostic:
    arcs = sorted(arcs, key=lambda a: a[1])
    deg = math.degrees(arcs[-1][1])
    return Diagnostic(
        "open-arc", f"{_plural(len(arcs), 'arc', 'arcs')} nearly a full circle, left open",
        points=[e.segment.center for e, _, _ in arcs],
        notes=[f"{_span([math.degrees(m) for _, m, _ in arcs], '.2f')}° missing "
               f"({_span([c for _, _, c in arcs], '.3f')} mm), over the "
               f"{math.degrees(NEAR_FULL_ARC_MISSING):.0f}° that close an arc (D218)"],
        help=f"doc.edges, _ = topo.experimental.close_near_full_arcs(doc.edges, tolerance, "
             f"max_missing_angle=math.radians({_ceil_2(deg):g})) before heal() closes them",
        param="max_missing_angle", value=arcs[-1][1])


def _near_gap_warning(gaps: list, gap: float) -> Diagnostic:
    longest = max(d for _, _, d in gaps)
    return Diagnostic(
        "near-gap", f"{_plural(len(gaps), 'gap', 'gaps')} just over the gap limit, left open",
        points=[a for a, _, _ in gaps],
        notes=[f"{_span([d for _, _, d in gaps], '.4f')} mm, limit {gap:g} mm (max_gap, default the tolerance)"],
        help=f"topo.heal(doc, ..., max_gap={_ceil_2(longest):g}) closes them all, and every other gap up to that",
        param="max_gap", value=longest)


_LABELED_WITHOUT_PREDICATE = (
    "{n} edge con un ruolo diverso da "
    "outer/inner/unknown, trattati come non strutturali di "
    "default (heal() chiamato senza is_structural=...): un "
    "ruolo come 'hole' non viene riconosciuto come contorno "
    "di pezzo e finisce in `loose`. Passa a heal() un "
    "is_structural che lo riconosca."
)
