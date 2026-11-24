"""
topo/core/readings/network.py
-----------------------------
The repair common to every reading: a Document becomes a network of repaired
edges, once: nodes at `SAME_POINT`, gaps closed up to `max_gap`.
`heal()` returns it; the readings (`faces()`, `outlines()`) start
from here and no longer repair on their own.

Pure: Edges, primitives and model only, no format.
"""

from __future__ import annotations

from ...precision import NEAR_GAP_FACTOR, SAME_POINT
import math
import numbers
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Callable, List, Optional

from ...model.document import Document
from ...model.text import Text
from ...model.role import is_structural_role
from ...model.diagnostic import Diagnostic, plural as _plural
from ..base.cleanup import (NEAR_FULL_ARC_MISSING, closed_touches, dangling_splines, near_free_gaps,
                            open_near_full_arcs, self_crossings)
from ..base.merge import near_copies
from ..base.prepare import normalize, prepare
from ..geometry.measure import FLOAT_NOISE, reach
from ..primitives.mathseg import segment_is_closed
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
    max_gap:     the widest gap closed; 0 (the default) closes none.
    source_file: copied onto every Result read from here; label: onto every Cluster.
    source_format: the document's, copied onto every Result.
    warnings:    advice about the drawing (`Diagnostic`); every reading copies it.
    notes:       what the repair did by itself (`Diagnostic`, level `note`).
    errors, is_valid: with errors no reading finds anything."""
    edges:       List[Edge] = field(default_factory=list)   # repaired, nodes decided
    set_aside:   List[Edge] = field(default_factory=list)   # non-structural roles
    warnings:    List[str] = field(default_factory=list)
    notes:       List[str] = field(default_factory=list)
    errors:      List[str] = field(default_factory=list)
    max_gap:     float = 0.0
    source_file: str = ""
    label:       str = ""
    source_format: str = ""
    _structural: Callable[[str], bool] = field(default=is_structural_role, repr=False)
    _texts:      List[Text] = field(default_factory=list, repr=False)   # of the Document, for every Result

    @property
    def is_valid(self) -> bool:
        """True when the repair raised no error."""
        return not self.errors

    @cached_property
    def _noded(self) -> NodedEdges:
        # the planar network without cutting the crossings: the crossings stay a datum,
        # the cut belongs to the reading that asks for it
        return split_at_crossings(self.edges, SAME_POINT, cut_crossings=False)

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
        # import here: the readings import the repair (repair_edges)
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


def _check_length(name: str, value, *, zero_ok: bool) -> None:
    """A threshold in mm must be a finite, positive number (or zero if `zero_ok`)."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"{name} must be a number in mm, got {type(value).__name__}")
    if not math.isfinite(value) or value < 0 or (value == 0 and not zero_ok):
        bound = "zero or more" if zero_ok else "greater than zero"
        raise ValueError(f"{name} must be a finite number of mm, {bound}; got {value}")


def build_network(doc: Document, *, max_gap: Optional[float] = None,
                  is_structural: Optional[Callable[[str], bool]] = None,
                  source_file: str = "", label: str = "") -> Network:
    """Repair `doc` once for all the readings: non-structural roles aside, nodes
    decided, `normalize` cleanups with the gaps up to `max_gap` (None: none),
    degenerate stretches removed."""
    tol = SAME_POINT   # the one threshold, not a parameter
    if max_gap is not None:
        _check_length("max_gap", max_gap, zero_ok=True)
    # a hole closes only up to the caller's max_gap; without it, none
    gap = 0.0 if max_gap is None else max_gap
    net = Network(max_gap=gap, source_file=source_file, label=label,
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
    # a line nearly on top of another: topo reads it as it is, the caller decides
    copies = near_copies(prepared.edges, tol)
    if copies:
        net.warnings.append(_near_copy_warning(copies))

    # a gap as wide as the threshold closes in every frame, not depending on the
    # last bit
    clean = normalize(prepared.edges, reach(gap), keep_junctions=True)
    for count, code, what in (
            (clean.merged_lines, "merged-lines", ("overlapping collinear segment", "overlapping collinear segments")),
            (clean.merged_arcs, "merged-arcs", ("overlapping arc or circle on one circle",
                                                "overlapping arcs or circles on one circle")),
            (prepared.welded, "welded", (f"line segment shorter than {SAME_POINT:g} welded into its node",
                                         f"line segments shorter than {SAME_POINT:g} welded into their nodes"))):
        if count:
            net.notes.append(Diagnostic(code, f"{count} {what[count > 1]} merged" if code != "welded"
                                        else f"{count} {what[count > 1]}", level="note"))
    if clean.full_arcs:
        net.notes.append(Diagnostic(
            "arc-joined", f"{_plural(clean.full_arcs, 'arc', 'arcs')} on one circle joined across their holes",
            notes=[f"holes within max_gap and at most {math.degrees(NEAR_FULL_ARC_MISSING):.0f}°"],
            level="note"))
    closed = [(pt, d) for pt, d in clean.gaps if d > FLOAT_NOISE]
    if closed:
        net.notes.append(_ends_joined_note(closed, gap))
    if clean.moved:
        net.notes.append(_curves_moved_note(clean.moved, gap))
    if clean.bent:
        net.notes.append(Diagnostic(
            "arc-bent", f"{_plural(len(clean.bent), 'arc', 'arcs')} redrawn through the free end beside it, its own ends kept",
            points=[pt for pt, _ in sorted(clean.bent, key=lambda c: -c[1])],
            notes=[f"{_range_text([d for _, d in clean.bent], '.4f')} mm, max_gap {gap:g} mm"], level="note"))
    if clean.tied:
        net.notes.append(Diagnostic(
            "tied-ends-joined", f"{_plural(len(clean.tied), 'gap', 'gaps')} between ends already tied, facing each other, closed",
            points=[pt for pt, _ in sorted(clean.tied, key=lambda c: -c[1])],
            notes=[f"{_range_text([d for _, d in clean.tied], '.4f')} mm, max_gap {gap:g} mm"], level="note"))
    if clean.ambiguous:
        net.warnings.append(Diagnostic(
            "tie", f"{_plural(len(clean.ambiguous), 'free end', 'free ends')} with two partners at the same "
                   f"distance, left open",
            points=clean.ambiguous,
            notes=["a symmetric figure: no rule in the geometry picks one partner"],
            help="no threshold fixes it: remove one of the two partners from the drawing"))
    net.edges = _no_degenerate(clean.edges)
    # what almost closed, one per type, with the points nearest first
    arcs = open_near_full_arcs(net.edges, reach(gap))
    if arcs:
        net.warnings.append(_open_arc_warning(arcs))
    gaps = near_free_gaps(net.edges, reach(gap), reach(_NEAR_GAP_REACH * max(gap, tol)))
    if gaps:
        net.warnings.append(_near_gap_warning(gaps, gap))
    loops = self_crossings(net.edges)
    if loops:
        net.warnings.append(Diagnostic(
            "self-crossing", f"{_plural(len(loops), 'curve crosses', 'curves cross')} itself, not cut there",
            points=loops))
    touches = closed_touches(net.edges, tol)
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
    """The same repair on loose edges, for whoever reads without a Document
    (experimental): nodes decided, `normalize`, degenerates removed."""
    noded, _ = decide_nodes(edges)
    return _no_degenerate(normalize(noded, reach(max_gap), keep_junctions=True).edges)


def _no_degenerate(edges: List[Edge]) -> List[Edge]:
    """A stretch reduced to a point is not a curve (a circle is)."""
    return [e for e in edges if e.start != e.end or segment_is_closed(e.segment)]


def _ceil_2(x: float) -> float:
    """`x` rounded up to two significant figures: the suggested threshold must
    suffice, not nearly suffice."""
    if x <= 0:
        return x
    step = 10 ** (math.floor(math.log10(x)) - 1)
    return math.ceil(x / step - 1e-9) * step


_NEAR_GAP_REACH = NEAR_GAP_FACTOR   # a gap up to twice the threshold "is nearly there"; beyond, it is geometry


def _range_text(values, fmt: str) -> str:
    lo, hi = min(values), max(values)
    a, b = format(lo, fmt), format(hi, fmt)
    return a if a == b else f"{a} to {b}"


def _near_copy_warning(pairs: list) -> Diagnostic:
    offset = max(p.offset for p in pairs)
    return Diagnostic(
        "near-copy", f"{_plural(len(pairs), 'line', 'lines')} nearly on top of a longer one, not merged",
        points=[p.at for p in pairs],
        notes=[f"{_range_text([p.offset for p in pairs], '.2g')} mm apart; not the same line "
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
        notes=[f"{_range_text([math.degrees(m) for _, m, _ in arcs], '.2f')}° missing "
               f"({_range_text([c for _, _, c in arcs], '.3f')} mm), over the "
               f"{math.degrees(NEAR_FULL_ARC_MISSING):.0f}° that close an arc"],
        help=f"doc.edges, _ = topo.experimental.close_near_full_arcs(doc.edges, tolerance, "
             f"max_missing_angle=math.radians({_ceil_2(deg):g})) before heal() closes them",
        param="max_missing_angle", value=arcs[-1][1])


def _ends_joined_note(closed: list, gap: float) -> Diagnostic:
    return Diagnostic(
        "ends-joined", f"{_plural(len(closed), 'gap', 'gaps')} between free ends closed",
        points=[pt for pt, _ in sorted(closed, key=lambda c: -c[1])],
        notes=[f"{_range_text([d for _, d in closed], '.4f')} mm, max_gap {gap:g} mm"],
        level="note")


def _curves_moved_note(moved: list, gap: float) -> Diagnostic:
    return Diagnostic(
        "curves-moved", f"{_plural(len(moved), 'curve', 'curves')} moved whole, each onto the two curves its ends reach",
        points=[pt for pt, _ in sorted(moved, key=lambda m: -m[1])],
        notes=[f"{_range_text([d for _, d in moved], '.4f')} mm, max_gap {gap:g} mm"],
        level="note")


def _near_gap_warning(gaps: list, gap: float) -> Diagnostic:
    longest = max(d for _, _, d in gaps)
    return Diagnostic(
        "near-gap", f"{_plural(len(gaps), 'gap', 'gaps')} just over the gap limit, left open",
        points=[a for a, _, _ in gaps],
        notes=[f"{_range_text([d for _, _, d in gaps], '.4f')} mm, limit {gap:g} mm (max_gap, default 0)"],
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
