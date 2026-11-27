"""
topo
----
Deterministic 2D geometry engine: it repairs vector geometry and reads its
structure - closed contours, what lies inside what, what is connected.
Geometry and roles, no file format: files come in and go out
through the adapters, sibling packages in the same distribution (the README shows them).

Public API - everything you need is here.
You do not have to import the internal modules directly.

    import topo

    box = topo.geometry.rectangle(100, 60)
    disc = topo.geometry.circle(8, center=(20, 15))
    doc = topo.load_segments(box + disc)      # or a Document from an adapter

    network = topo.heal(doc, label="shape")   # the repair, once
    result = network.faces()                  # or network.outlines() for projections side by side
    # what a contour means is a consumer's reading, written to cluster.overlay

    topo.save_json(result, "shape.json")
    parts = topo.split(result).pieces          # one Result per cluster, no format
"""

from .core.geometry_input import load_geometry, load_segments
from .core.readings.heal import heal
from .core.readings.network import Network
from .tools.anchor       import anchor_texts
# One Result per part, no format: every exporter writes one.
from .tools.split        import split, Split
from .rules.validator     import validate_document, validate_result
from .io.json_export      import to_json, save_json
# Explicit conversion to shapely for overlay, buffer, WKT: the model does not
# expose shapely types.
from .io.shapes           import to_shapely
from .model         import (
    Result, Cluster, Contour, Document,
    Text,
    # what a text measures, with the source's points
    MeasuredDistance, MeasuredRadius, MeasuredDiameter, MeasuredAngle,
    Overlay,
    # a warning as in Rust: text + fields, with the threshold that fixes it
    Diagnostic,
)
# A consumer that marks the geometry before heal() (a border, a label box)
# sets `edge.role` on the Edges of `doc.edges` with a slug cleaned by
# normalize_role, and is_structural_role says whether that role is part of a
# contour or something that heal keeps out of the graph.
from .model.role      import normalize_role, is_structural_role
# The caller's rules that assign the role at load.
from .model.role_rule import RoleRule, name_rules
# RoleStyle: how the caller wants a role drawn, with no format. The
# {role: RoleStyle} dictionary is theirs and they pass it to every exporter.
from .model.style     import RoleStyle
# The same criterion heal() uses internally to exclude an edge from the contour
# graph (chains between two branching nodes, not on the outer border) — without
# saying what that edge is. A consumer that wants to decide `edge.role` before
# heal() with an interpretation of its own (not "bending" as detect_flat() does)
# calls it on doc.edges.
from .tools.non_contour import non_contour_candidates
# The geometry: facts with geometric names (shape of a contour, concentric
# circles, chords, covered rectangles, ...), all in `topo.geometry`.
from .core import geometry
# Every fixed topo threshold, in one file and not reassignable.
from . import precision
# Everything exposed with no stability promise: the steps of faces() and
# outlines(), the viewer, the text reading, rotate_*, simplify_points. Written in
# full: `topo.experimental.<name>`.
from . import experimental
# The geometric primitives and the model types, public: `topo.primitives`,
# `topo.model`. What is under `topo.core` is internal.
from . import primitives, model
from .inspect             import inspect_document, inspect_result

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
    try:
        __version__ = _pkg_version("g-topo")
    except PackageNotFoundError:
        __version__ = "0.0.0+dev"
except ImportError:  # pragma: no cover
    __version__ = "0.0.0+dev"

__all__ = [
    # Input geometry (the files come in through the adapters)
    "load_geometry",
    "load_segments",
    # Validazione
    "validate_document",
    "validate_result",
    # Workflow
    "heal",
    "Network",
    "split",
    "anchor_texts",
    "geometry",
    "precision",
    "experimental",
    "primitives",
    "model",
    # Export
    "to_json",
    "save_json",
    "to_shapely",
    # Utilities
    # Inspection / debug (Document → Result; the raw file is inspected by its adapter)
    "inspect_document",
    "inspect_result",
    # Modelli
    "Result",
    "Split",
    "Cluster",
    "Contour",
    "Document",
    "Text",
    "MeasuredDistance",
    "MeasuredRadius",
    "MeasuredDiameter",
    "MeasuredAngle",
    "Overlay",
    "Diagnostic",
    # Roles — hook for a consumer that marks the geometry pre-heal
    "normalize_role",
    "is_structural_role",
    "RoleRule",
    "name_rules",
    "RoleStyle",
    "non_contour_candidates",
]