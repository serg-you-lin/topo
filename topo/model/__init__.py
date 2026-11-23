"""
topo/model/__init__.py
----------------------
The public model types: document, result, cluster, contours, curves, texts,
styles, overlay, roles, role rules and `Edge` — what an adapter needs to build
a `Document`. Written `topo.model.<Name>`; the four most used (`Document`,
`Result`, `Cluster`, `Contour`) are also in `topo.<Name>`.
"""
from .text import (
    Text, RenderedGeometry, RenderedText,
    MeasuredDistance, MeasuredRadius, MeasuredDiameter, MeasuredAngle,
)
from .document import Document
from .contour import Contour
from .cluster import Cluster
from .result import Result
from .curve import Curve, ClosedCurve, OpenCurve
from .style import EdgeStyle, RoleStyle, DEFAULT_ROLE_STYLES, CONSUMER_ROLE_STYLE, role_style
from .overlay import Overlay, feature_closed
from .role import ContourRole, role_str, normalize_role, is_structural_role, feature_role
from .role_rule import RoleRule, resolve_role, name_rules
from .diagnostic import Diagnostic

__all__ = [
    "Document",
    "Text",
    "RenderedGeometry",
    "RenderedText",
    "MeasuredDistance",
    "MeasuredRadius",
    "MeasuredDiameter",
    "MeasuredAngle",
    "Contour",
    "Cluster",
    "Result",
    "Curve",
    "ClosedCurve",
    "OpenCurve",
    "EdgeStyle",
    "RoleStyle",
    "DEFAULT_ROLE_STYLES",
    "CONSUMER_ROLE_STYLE",
    "role_style",
    "Overlay",
    "feature_closed",
    "ContourRole",
    "role_str",
    "normalize_role",
    "is_structural_role",
    "feature_role",
    "RoleRule",
    "resolve_role",
    "name_rules",
    "Diagnostic",
    "Edge",
]


def __getattr__(name):
    # Edge lives in core/topology (the graph uses it) and imports model.style:
    # loaded on first access so as not to close a circular import.
    if name == "Edge":
        from ..core.topology.edge import Edge
        return Edge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
