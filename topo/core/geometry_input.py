"""
topo/core/geometry_input.py
---------------------------
Entry point to build a Document from geometry already known — not from a
file. Same contract as an adapter (it produces a Document, no internal
types), but the "source" is the caller: a parametric generator (a cone or
cylinder development computed elsewhere) or a geometry reconstructor from
points (a contour already vectorized by computer vision).

The caller imports NO internal topo type: the entities are plain Python
dicts. The translation into Edges (nodes, semantic role) is the same as in
every adapter (`Edge.of`). It is not a format, so it does not live among the
adapters: it is an input of topo.

Public functions:
    load_geometry — translates a list of geometric descriptions into a Document
    load_segments — the same, from topo segments (`topo.geometry.rectangle`, ...)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from .geometry.build import polygon
from .primitives.line import LineSeg
from .primitives.spline import BSplineSeg
from .primitives.conics import CircleSeg, EllipseSeg
from .topology.edge import Edge
from ..model.document import Document
from ..model.role import normalize_role

_SUPPORTED_TYPES = frozenset({"line", "arc", "circle", "polygon", "spline", "ellipse"})


def _role_from(entity: Dict[str, Any]) -> str:
    """work_type string (same vocabulary as RoleRule.role) → role. An unknown
    work_type is kept (via normalize_role), not flattened to UNKNOWN.
    """
    return normalize_role(entity.get("role"))


class GeometryReader:
    """Translate pure geometric descriptions (dicts) into topo domain Edges.

    Schema of each entity, by "type":
        line:     {"type": "line", "start": (x,y), "end": (x,y), "role": "outer"}
        arc:      {"type": "arc", "center": (x,y), "radius": r,
                   "start_angle": degrees, "end_angle": degrees,
                   "ccw": True, "role": "outer"}
        circle:   {"type": "circle", "center": (x,y), "radius": r, "role": "hole"}
        polygon:  {"type": "polygon", "points": [(x,y), ...], "role": "outer"}
                  — always closed: the last side returns to the first point
        spline:   {"type": "spline", "control_points": [(x,y), ...], "knots": [...],
                   "degree": 3, "weights": [...], "role": "outer"}
        ellipse:  {"type": "ellipse", "center": (x,y), "major_axis": (x,y),
                   "ratio": 0.5, "start_param": 0.0, "end_param": 2*pi,
                   "ccw": True, "role": "outer"}

    "role" is optional — same vocabulary as RoleRule.role (a work_type string:
    "outer", "hole", "inner", "bending", "engrave", ...). If omitted it stays
    "unknown": no problem for a part's outermost contour, which HierarchyBuilder
    makes OUTER anyway by its position in the containment tree; it only serves to
    have explicit holes/inners recognized before a consumer reclassifies them.

    The angles of "arc" are in DEGREES, not the radians of CircleSeg: more
    natural for whoever hands over numbers computed by hand, like the builders
    of `topo.geometry`.

    The "spline" schema mirrors the BSplineSeg fields 1:1 (control_points,
    knots, degree, weights): the object returned by simplify_points() can be
    passed almost untouched — see topo.core.geometry.fitting. Only
    "control_points"/"knots"/"degree" are required, the rest is optional.

    The "ellipse" schema mirrors the EllipseSeg fields 1:1 (center, major_axis as
    a VECTOR from the centre, ratio, start_param/end_param in radians). Only
    "center"/"major_axis" are required: "ratio"/"start_param"/"end_param"
    default to a full ellipse (1.0 / 0.0 / 2π).

    """

    def __init__(self, entities: List[Dict[str, Any]]):
        self.entities = entities

    def to_edges(self) -> List[Edge]:
        edges: List[Edge] = []
        for i, entity in enumerate(self.entities):
            kind = str(entity.get("type", "")).lower()
            role = _role_from(entity)

            if kind == "line":
                edges.append(self._line_edge(entity, role))
            elif kind == "arc":
                edges.append(self._arc_edge(entity, role))
            elif kind == "circle":
                edges.append(self._circle_edge(entity, role))
            elif kind == "polygon":
                edges.extend(self._polygon_edges(entity, role))
            elif kind == "spline":
                edges.append(self._spline_edge(entity, role))
            elif kind == "ellipse":
                edges.append(self._ellipse_edge(entity, role))
            else:
                raise ValueError(
                    f"load_geometry(): unsupported type at index {i}: "
                    f"{entity.get('type')!r}; valid: {sorted(_SUPPORTED_TYPES)}"
                )
        return edges

    def _line_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        return Edge.of(LineSeg(start=tuple(entity["start"]), end=tuple(entity["end"])), role)

    def _arc_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = CircleSeg(
            center=tuple(entity["center"]),
            radius=float(entity["radius"]),
            start_angle=math.radians(float(entity["start_angle"])),
            end_angle=math.radians(float(entity["end_angle"])),
            ccw=bool(entity.get("ccw", True)),
        )
        return Edge.of(seg, role)

    def _circle_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        return Edge.of(CircleSeg(center=tuple(entity["center"]), radius=float(entity["radius"])), role)

    def _spline_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        weights = entity.get("weights")
        seg = BSplineSeg(
            degree=int(entity.get("degree", 3)),
            control_points=[tuple(p) for p in entity["control_points"]],
            knots=[float(k) for k in entity["knots"]],
            weights=[float(w) for w in weights] if weights else None,
        )
        return Edge.of(seg, role)

    def _ellipse_edge(self, entity: Dict[str, Any], role: str) -> Edge:
        seg = EllipseSeg(
            center=tuple(entity["center"]),
            major_axis=tuple(entity["major_axis"]),
            ratio=float(entity.get("ratio", 1.0)),
            start_param=float(entity.get("start_param", 0.0)),
            end_param=float(entity.get("end_param", math.tau)),
            ccw=bool(entity.get("ccw", True)),
        )
        return Edge.of(seg, role)

    def _polygon_edges(self, entity: Dict[str, Any], role: str) -> List[Edge]:
        return [Edge.of(seg, role) for seg in polygon(entity["points"])]


# --- Public entry point ---

def load_geometry(
    entities: List[Dict[str, Any]],
    *, source_path: str = "",
) -> Document:
    """
    Builds a Document from a list of pure geometric descriptions — same
    contract as an adapter's loader, but the source is not a file: it is geometry already
    computed or reconstructed elsewhere (parametric generators, contours
    vectorized from an image, ...).

    See GeometryReader for the schema of each supported entity "type"
    (line / arc / circle / polygon / spline / ellipse).

    Example — annular sector of a cone development:
        doc = topo.load_geometry([
            {"type": "arc",  "center": (0,0), "radius": r_est,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_1, "end": p_est_1, "role": "outer"},
            {"type": "arc",  "center": (0,0), "radius": r_int,
             "start_angle": -a/2, "end_angle": a/2, "role": "outer"},
            {"type": "line", "start": p_int_2, "end": p_est_2, "role": "outer"},
        ])
        result = topo.heal(doc, label="sviluppo_cono").faces()
        topo.save_json(result, "sviluppo_cono.json")

    Args:
        entities:    list of geometric dicts (see GeometryReader)
        source_path: free label for Document.source_path — not a file, only
                     used for diagnostics/traceability

    Returns:
        Document (edges + source_meta), ready for heal().
    """
    edges = GeometryReader(entities).to_edges()
    return Document(
        edges=edges,
        source_path=source_path or "<load_geometry>",
        source_format="geometry",
        source_meta={},
    )


def load_segments(
    segments,
    *, role: str = "unknown",
    source_path: str = "",
) -> Document:
    """
    A Document from topo segments (`LineSeg`, `CircleSeg`, ...)
    or from lists of segments, as returned by the constructors of
    `topo.geometry` (`rectangle`, `regular_polygon`, `polygon`, `circle`,
    `stadium`). Every edge takes `role`.

        fg = topo.geometry
        doc = topo.load_segments(fg.rectangle(200, 100) + fg.circle(10))
        result = topo.heal(doc).faces()
    """
    role = normalize_role(role)
    flat = []
    for item in segments:
        flat.extend(item if isinstance(item, (list, tuple)) else [item])
    edges = [Edge.of(seg, role) for seg in flat]
    return Document(
        edges=edges,
        source_path=source_path or "<load_segments>",
        source_format="geometry",
        source_meta={},
    )
