"""
io/view_model.py
----------------
`to_view_model(result)` — serializes a `Result` into a **rendering-oriented**
JSON dictionary: coordinates of EVERY feature (outer, inner, a consumer's
overlay, loose curves) + role + colour, ready to draw.
Outside the stable 1.0: the viewer is `topo.experimental`.

It is the counterpart of `to_json` (which gives only facts, no coordinates).
`to_svg` and any external front-end consume it (a JS dashboard that renders
with SVG/Canvas).

All the geometry is **discretized to polylines** (lists of `[x, y]` points):
arcs, circles and splines are flattened. An overlay element carrying `center` +
`diameter` in its `to_dict()` brings them back, so a renderer can draw a true
circle instead of the N-sided polygon.

Coordinate system: the model's = the source file's (Y up). An SVG renderer
must flip Y (`to_svg` does).
"""

from __future__ import annotations

from ..precision import SAME_POINT
from typing import Mapping, Optional

from ..model import Result, RoleStyle, feature_closed, role_style
from ..model.overlay import _feature_contours
from ..model.role import ContourRole, feature_role, role_str as _role_str
from ..core.geometry.measure import track_points
from ..core.geometry.shapely_polygons import build_polygon, curve_polygon
from ..core.primitives.mathseg import DEFAULT_TOLERANCE

def _color(role, role_styles: Mapping[str, RoleStyle]) -> str:
    """CSS hex of a role: topo's palette with the caller's map on top
    (`role_style`) — only translated here."""
    r, g, b = role_style(role, role_styles=role_styles).color
    return f"#{r:02x}{g:02x}{b:02x}"


def _round_points(seq) -> list:
    """List of points (2D or 3D) → list of rounded [x, y]."""
    return [[round(p[0], 4), round(p[1], 4)] for p in seq]


def _poly_points(polygon) -> list:
    """Vertices of the outer ring of a shapely polygon as a list of [x, y]."""
    if polygon is None or polygon.is_empty:
        return []
    return _round_points(polygon.exterior.coords)


def _track(segments, tolerance: float) -> list:
    """Open trace (list of native segments) discretized to a list of [x, y]."""
    return _round_points(track_points(segments, tolerance=tolerance))


def _contour_entry(contour, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    role = getattr(contour, "role", ContourRole.UNKNOWN)
    pts = _poly_points(curve_polygon(contour)) or _track(
        getattr(contour, "segments", []), tolerance
    )
    return {"role": _role_str(role), "color": _color(role, role_styles), "points": pts, "closed": True}


def _feature_entries(item, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> list:
    """An overlay element → one entry per contour: role, colour, points, `closed`
    (`model.feature_closed`), plus the scalar fields of its `to_dict()` if it has
    one (a renderer draws a true circle if it finds `center` + `diameter`)."""
    role = getattr(item, "role", None)
    extra = {}
    if callable(getattr(item, "to_dict", None)):
        for key, value in item.to_dict().items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                extra[key] = value
            elif isinstance(value, (tuple, list)) and all(isinstance(v, (int, float)) for v in value):
                extra[key] = [round(v, 4) for v in value]
    entries = []
    for contour in _feature_contours(item):
        c_role = feature_role(contour, role) or ContourRole.UNKNOWN
        segments = getattr(contour, "segments", []) or []
        closed = feature_closed(contour, item)
        polygon = (curve_polygon(contour) or build_polygon(list(segments), DEFAULT_TOLERANCE)
                   if closed and segments else None)
        pts = _poly_points(polygon) if polygon is not None else _track(segments, tolerance)
        entries.append({**extra, "role": _role_str(c_role), "color": _color(c_role, role_styles),
                        "points": pts, "closed": polygon is not None})
    return entries


def _features(cluster, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    """`cluster.overlay` by name → list of drawable entries."""
    if cluster.overlay is None:
        return {}
    return {
        name: [e for item in items for e in _feature_entries(item, tolerance, role_styles)]
        for name, items in cluster.overlay.items()
    }


def _loose_entry(curve, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    role = getattr(curve, "role", ContourRole.UNKNOWN)
    poly = curve_polygon(curve)
    if poly is not None:
        pts, closed = _poly_points(poly), True
    else:
        pts, closed = _track(getattr(curve, "segments", []), tolerance), False
    return {"role": _role_str(role), "color": _color(role, role_styles), "points": pts, "closed": closed}


def _text_entry(text) -> dict:
    return {
        "position":    [round(text.position[0], 4), round(text.position[1], 4)],
        "halign":      text.halign,
        "valign":      text.valign,
        "text":        text.text,
        "height":      text.height or 2.5,
        "rotation":    text.rotation or 0.0,
    }


def _bbox_of(clusters) -> Optional[list]:
    boxes = [p.outer.bbox for p in clusters if p.outer is not None and p.outer.segments]
    if not boxes:
        return None
    return [
        round(min(b[0] for b in boxes), 4),
        round(min(b[1] for b in boxes), 4),
        round(max(b[2] for b in boxes), 4),
        round(max(b[3] for b in boxes), 4),
    ]


def to_view_model(
    result: Result,
    tolerance: float = SAME_POINT,
    include_loose: bool = True,
    include_texts: bool = True,
    role_styles: Optional[Mapping[str, RoleStyle]] = None,
) -> dict:
    """`Result` → JSON-ready dictionary with the geometry of every feature.

    Args:
        result:              the `Result` to serialize.
        tolerance:           discretization tolerance for arcs/circles/splines of
                             open traces (closed traces use the polygon already
                             discretized at load).
        include_loose:       include `result.loose`.
        include_texts: include `result.texts`.
        role_styles:         the caller's `{role: RoleStyle}`, on top of topo's
                             palette: it reads its colour.

    It does not mutate `result`. It does not raise on an invalid `result` — it
    returns the dictionary anyway with `is_valid=False` and the parts that exist
    (useful for debugging a file that does not heal)."""
    role_styles = dict(role_styles or {})
    parts_out = []
    for cluster in result.clusters:
        parts_out.append({
            "label":  cluster.label,
            "bbox":   list(cluster.bbox),
            "area":   round(cluster.area, 4),
            "outer":  _contour_entry(cluster.outer, tolerance, role_styles),
            "inners": [_contour_entry(i, tolerance, role_styles) for i in cluster.inners],
            # a consumer's overlay, by name
            "features": _features(cluster, tolerance, role_styles),
            "summary": cluster.summary,
        })

    vm = {
        "source_file": result.source_file,
        "is_valid":    result.is_valid,
        "cluster_count":  len(result.clusters),
        "bbox":        _bbox_of(result.clusters),
        "warnings":    list(result.warnings),
        "errors":      list(result.errors),
        "clusters":       parts_out,
        "palette":     _palette_dict(role_styles),
    }
    if include_loose:
        vm["loose"] = [_loose_entry(t, tolerance, role_styles) for t in result.loose]
    if include_texts:
        vm["texts"] = [_text_entry(t) for t in result.texts]
    return vm


def _palette_dict(role_styles: Mapping[str, RoleStyle]) -> dict:
    """role (string) → hex colour, for a renderer's legend: the three engine roles
    and every role to which the caller gives a colour."""
    engine = [r.value for r in ContourRole]
    roles = engine + [r for r in role_styles if r not in engine]
    return {role: _color(role, role_styles) for role in roles}
