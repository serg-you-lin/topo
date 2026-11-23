"""
topo/tools/rotate.py
-----------------------
Rotate the geometry of a Result (or of a single Cluster) about a centre —
optionally aligning the longest structural segment to the horizontal.

One heal(), not two: a rigid rotation does NOT change the topology (who
contains whom, which loops exist stay identical — only the coordinates
change), so there is no need to rebuild the containment tree after rotating.
`rotate_result`/`rotate_cluster` transform DIRECTLY the structures `heal()`
already produced (polygons, segments) — they do not go back to the raw
pre-heal geometry and do not call `heal()` again. For the same reason
`rotate_cluster` is cheap and repeatable: a future nester can call it in a loop
to try many angles on a single part, without paying the cost of a `heal()` at
each attempt.

What is NOT rotated, on purpose, not by oversight:
- `cluster.overlay` — free-schema overlay, topo does not know what it
  contains; if you already did `detect_flat()`, that data (bend lines, typed
  holes, ...) stays in the old coordinates after a rotation. Do
  `detect_flat()` AFTER rotating, not before.
- `result.texts` — same limit as `rotate_document`: no real case has asked
  for them yet. If present, a warning is added instead of silently leaving
  them in the wrong place.

The mechanics are here (`rotate_cluster`, meant to be called many times with
different angles); deciding how many degrees to try / the packing
optimization stay out of scope (nesting stays out of topo).
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Optional, Tuple

from shapely.affinity import rotate as _shapely_rotate

from ..core.geometry.measure import longest_segment, chord_angle_deg
from ..core.topology.edge import node_point
from ..core.primitives.mathseg import segment_endpoints
from ..core.geometry.shapely_polygons import curve_polygon, with_polygon
from ..model.cluster import Cluster
from ..model.contour import Contour
from ..model.diagnostic import Diagnostic, plural
from ..model.document import Document
from ..model.curve import ClosedCurve, OpenCurve
from ..model.result import Result

Point = Tuple[float, float]


# Segment selection — "which entity to align"
# STRUCTURAL filter (cluster.outer vs cluster.inners), not on `contour.role`:
# `role` does not reliably tell outer from inner. `cluster.outer` is always
# unambiguously the outer, but an `inner` with no role of its own INHERITS the
# parent's role if the parent had an explicit one: an outer labelled "outer"
# produces inner holes also "outer" if they have none of their own. Filtering by
# string would be ambiguous in the common case.
#
# For a finer criterion than "outer" / "outer+inner" compose the list yourself:
# `cluster.outer.segments`/`cluster.inners[i].segments` are already public, and
# `longest_segment()`/`chord_angle_deg()` are already generic.

def structural_segments(result: Result, include_inners: bool = False) -> list:
    """Native segments of the structural contours of every cluster: always
    `cluster.outer`; also `cluster.inners` (inner holes/loops not yet typed — the
    hole/countersink/... typing lives in `detect_flat()`, a separate overlay) if
    `include_inners=True`."""
    segments = []
    for cluster in result.clusters:
        segments.extend(cluster.outer.segments)
        if include_inners:
            for inner in cluster.inners:
                segments.extend(inner.segments)
    return segments


def longest_structural_segment(
    result: Result, include_inners: bool = False
) -> Tuple[Optional[object], float, Optional[float]]:
    """`(segment, length, angle_deg)` of the longest segment among
    `structural_segments(result, include_inners)`. `(None, 0.0, None)` if there
    is no cluster."""
    seg, length = longest_segment(structural_segments(result, include_inners))
    if seg is None:
        return None, 0.0, None
    start, end = segment_endpoints(seg)
    return seg, length, chord_angle_deg(start, end)


# --- Rotation — pure primitives, reusable in a loop (nester) ---

def _rotate_contour(contour: ClosedCurve, angle_rad: float, origin: Point) -> ClosedCurve:
    rotated = replace(contour, segments=[s.rotated(angle_rad, origin=origin) for s in contour.segments])
    polygon = curve_polygon(contour)
    if polygon is not None:
        with_polygon(rotated, _shapely_rotate(polygon, angle_rad, origin=origin, use_radians=True))
    return rotated


def rotate_cluster(cluster: Cluster, angle_rad: float, origin: Point = (0.0, 0.0)) -> Cluster:
    """New `Cluster` with `outer`/`inners` rotated by `angle_rad` (radians, CCW) about
    `origin` — native segments (`.rotated()`) and polygon
    (`shapely.affinity.rotate`) at once, no `heal()`.

    `cluster.overlay` is NOT touched — see the module. The `depth`/`parent` tree
    between outer and inners is preserved (the new `Contour`s point to the NEW
    rotated objects, not the old ones).

    Meant for a loop: cheap (geometric transformations only, no topology
    rebuilding), so suited to trying many angles on the same part (nester)."""
    new_outer = _rotate_contour(cluster.outer, angle_rad, origin)
    id_map = {id(cluster.outer): new_outer}

    new_inners: List[Contour] = []
    for inner in cluster.inners:
        new_inner = _rotate_contour(inner, angle_rad, origin)
        id_map[id(inner)] = new_inner
        new_inners.append(new_inner)

    new_outer.parent = None
    for old_inner, new_inner in zip(cluster.inners, new_inners):
        new_inner.parent = id_map.get(id(old_inner.parent)) if old_inner.parent is not None else None

    return replace(cluster, outer=new_outer, inners=new_inners)


def rotate_result(result: Result, angle_rad: float, origin: Point = (0.0, 0.0)) -> Result:
    """New `Result` with every cluster (`rotate_cluster`) and `loose` rotated by
    `angle_rad` about `origin`. No `heal()` called again: a rigid rotation does not
    change the topology, only the coordinates.

    `result.texts` are not rotated — if present, a warning is added instead of
    leaving them still without notice. `cluster.overlay` is not touched — if
    present on some cluster, a warning reminds to redo `detect_flat()` after the
    rotation."""
    new_clusters = [rotate_cluster(c, angle_rad, origin) for c in result.clusters]
    new_loose = [
        replace(t, segments=[s.rotated(angle_rad, origin=origin) for s in t.segments])
        if isinstance(t, OpenCurve) else _rotate_contour(t, angle_rad, origin)
        for t in result.loose
    ]

    new_warnings = list(result.warnings)
    if result.texts:
        new_warnings.append(_texts_not_rotated("rotate_result", result.texts))
    if any(c.overlay is not None for c in result.clusters):
        new_warnings.append(Diagnostic(
            "not-rotated", "rotate_result(): cluster.overlay is not rotated",
            notes=["topo does not know what a consumer stored there"],
            help="run the consumer's reading again after the rotation"))

    return replace(
        result,
        clusters=new_clusters,
        loose=new_loose,
        warnings=new_warnings,
    )


def rotate_document(
    doc: Document,
    angle_rad: float,
    origin: Point = (0.0, 0.0),
) -> Document:
    """New `Document` with every `edge.segment` rotated by `angle_rad` (radians, CCW)
    about `origin`, with the nodes on the rotated true points (`node_point`).

    Pre-heal primitive: useful when the angle is already known from elsewhere (no
    need to measure it on this same document) and you want to rotate before
    passing to `heal()` the first time. For "measure the angle on the longest outer
    AND rotate", see `rotate_to_longest` — which works on an already sound
    `Result`, a single `heal()` in all.

    Texts are not rotated — same limit as `rotate_result`."""
    new_edges: List = []
    for edge in doc.edges:
        seg = edge.segment.rotated(angle_rad, origin=origin)
        start, end = segment_endpoints(seg)
        new_edges.append(replace(edge, segment=seg, start=node_point(start), end=node_point(end)))

    new_warnings = list(doc.warnings)
    if doc.texts:
        new_warnings.append(_texts_not_rotated("rotate_document", doc.texts))

    return replace(doc, edges=new_edges, warnings=new_warnings)


def _texts_not_rotated(where: str, texts) -> Diagnostic:
    return Diagnostic(
        "not-rotated", f"{where}(): {plural(len(texts), 'text', 'texts')} not rotated (not supported yet)",
        points=[t.position for t in texts])


# Orchestrator — "align the longest segment", a single heal() upstream

def _result_bbox_center(result: Result) -> Point:
    """Centre of the joined bbox of the outers of all the clusters — see `rotate_to_longest`."""
    boxes = [c.outer.bbox for c in result.clusters if c.outer.segments]
    if not boxes:
        return (0.0, 0.0)
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[2] for b in boxes)
    maxy = max(b[3] for b in boxes)
    return ((minx + maxx) / 2.0, (miny + maxy) / 2.0)


def rotate_to_longest(
    result: Result,
    include_inners: bool = False,
    target_angle_deg: float = 0.0,
    origin: Optional[Point] = None,
) -> Tuple[Result, float]:
    """Rotate `result` (already sound, from a `heal()` the caller already did) so
    that its longest structural segment — see `structural_segments`: only the
    outers by default, also the inners if `include_inners=True` — becomes
    horizontal (or `target_angle_deg`, if given). A single `heal()` in all: the
    one the caller already did to produce `result`.

    `origin` defaults to the centre of the joined bbox of the outers (the shape
    does not change with `origin`, only where it ends up in the plane).

    Returns `(rotated_result, angle_deg_applied)`. If there is no cluster, returns
    `result` unchanged and `0.0`."""
    _, _, angle_deg = longest_structural_segment(result, include_inners)
    if angle_deg is None:
        return result, 0.0

    if origin is None:
        origin = _result_bbox_center(result)

    rotation_deg = target_angle_deg - angle_deg
    rotated = rotate_result(result, math.radians(rotation_deg), origin)
    return rotated, rotation_deg
