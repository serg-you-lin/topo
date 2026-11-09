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
from ...model.diagnostic import Diagnostic, plural as _plural
from ..base.cleanup import (NEAR_FULL_ARC_MISSING, closed_touches, dangling_splines, near_free_gaps,
                            open_near_full_arcs, self_crossings)
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
    warnings:    advice about the drawing (`Diagnostic`, D233); every reading copies it.
    notes:       what the repair did by itself (`Diagnostic`, level `note`).
    errors, is_valid: with errors no reading finds anything.
    """
    edges:       List[Edge] = field(default_factory=list)   # riparati, nodi decisi
    set_aside:   List[Edge] = field(default_factory=list)   # ruoli non strutturali (D30)
    warnings:    List[str] = field(default_factory=list)
    notes:       List[str] = field(default_factory=list)
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
        net.errors.append(Diagnostic("empty", "the document has no edges", level="error"))
        return net
    prepared = prepare(doc.edges, net._structural)
    net.set_aside = prepared.labeled
    if not prepared.edges and not prepared.labeled:
        net.errors.append(Diagnostic("empty", "the document has no edge left to read", level="error"))
        return net
    if prepared.labeled and is_structural is None:
        net.warnings.append(_set_aside_warning(prepared.labeled))
    # una retta quasi sopra un'altra: topo la legge com'è, il chiamante decide (D226, D227)
    copies = near_copies(prepared.edges, tol)
    if copies:
        net.warnings.append(_near_copy_warning(copies))

    # un gap largo quanto la soglia si chiude a ogni riferimento, non a
    # seconda dell'ultimo bit (D183)
    clean = normalize(prepared.edges, reach(gap), keep_junctions=True)
    for count, code, what in (
            (clean.merged_lines, "merged-lines", ("overlapping collinear segment", "overlapping collinear segments")),
            (clean.merged_arcs, "merged-arcs", ("overlapping arc or circle on one circle",
                                                "overlapping arcs or circles on one circle")),
            (clean.welded + prepared.welded, "welded", ("line segment shorter than 0.05 welded into its node",
                                                        "line segments shorter than 0.05 welded into their nodes"))):
        if count:
            net.notes.append(Diagnostic(code, f"{count} {what[count > 1]} merged" if code != "welded"
                                        else f"{count} {what[count > 1]}", level="note"))
    if clean.full_arcs:
        net.notes.append(Diagnostic(
            "arc-joined", f"{_plural(clean.full_arcs, 'arc', 'arcs')} on one circle joined across their holes",
            notes=[f"holes within tolerance and at most {math.degrees(NEAR_FULL_ARC_MISSING):.0f}° (D218)"],
            level="note"))
    if clean.ambiguous:
        net.warnings.append(Diagnostic(
            "tie", f"{_plural(len(clean.ambiguous), 'free end', 'free ends')} with two partners at the same "
                   f"distance, left open",
            points=clean.ambiguous,
            notes=["a symmetric figure: no rule in the geometry picks one partner (D185)"],
            help="no threshold fixes it: remove one of the two partners from the drawing"))
    net.edges = _no_degenerate(clean.edges)
    # quello che si è quasi chiuso, uno per tipo, coi punti dal più vicino (D227)
    arcs = open_near_full_arcs(net.edges, reach(gap))
    if arcs:
        net.warnings.append(_open_arc_warning(arcs))
    gaps = near_free_gaps(net.edges, reach(gap), reach(_NEAR_GAP_REACH * gap))
    if gaps:
        net.warnings.append(_near_gap_warning(gaps, gap))
    loops = self_crossings(net.edges)   # D241
    if loops:
        net.warnings.append(Diagnostic(
            "self-crossing", f"{_plural(len(loops), 'curve crosses', 'curves cross')} itself, not cut there",
            points=loops))
    touches = closed_touches(net.edges, tol)   # D241
    if touches:
        net.warnings.append(Diagnostic(
            "closed-touch", f"{_plural(len(touches), 'closed curve', 'closed curves')} with its node on "
                            f"another closed curve; outlines() may keep only one",
            points=touches))
    dangling = dangling_splines(net.edges)
    if dangling:
        net.notes.append(Diagnostic(
            "open-spline", f"{_plural(len(dangling), 'open spline', 'open splines')} with an end that reaches "
                           f"no other edge", points=[e.start for e in dangling], level="note"))
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


def _set_aside_warning(labeled: List[Edge]) -> Diagnostic:
    roles = sorted({e.role for e in labeled})
    return Diagnostic(
        "set-aside", f"{_plural(len(labeled), 'edge', 'edges')} with a role other than outer/inner/unknown "
                     f"set aside, in loose",
        points=[e.start for e in labeled],
        notes=[f"roles: {', '.join(roles)}; without is_structural only outer/inner/unknown make contours"],
        help="topo.heal(doc, is_structural=...) with a predicate that accepts the roles that are contours")
