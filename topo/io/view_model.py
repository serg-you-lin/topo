"""
io/view_model.py
----------------
`to_view_model(result)` — serializza un `Result` in un dizionario JSON
**orientato al rendering**: coordinate di OGNI feature (outer, inner, overlay
di un consumatore, curve sciolte) + ruolo + colore, pronto da disegnare.

È il pendant di `to_json` (che dà solo metadati, zero geometria) e la versione
completa di `to_nester_input` (che dà solo outer + inner). Lo consumano `to_svg`
e qualunque front-end esterno (una dashboard JS che renderizza con SVG/Canvas).

Tutta la geometria è **discretizzata a polilinee** (liste di punti `[x, y]`):
archi, cerchi e spline vengono appiattiti (MAP.md D12). Un elemento
dell'overlay che porta `center` + `diameter` nel suo `to_dict()` li riporta,
così un renderer può disegnare un cerchio vero invece del poligono a N lati.

Sistema di coordinate: quello del modello = quello del file sorgente (Y verso
l'alto). Un renderer SVG deve ribaltare la Y (lo fa `to_svg`).
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..model import Result, RoleStyle, role_style
from ..model.role import ContourRole, feature_role, role_str as _role_str
from ..core.geometry.measure import track_points

def _color(role, role_styles: Mapping[str, RoleStyle]) -> str:
    """Hex CSS di un ruolo: la palette di topo con sopra la mappa del
    chiamante (`role_style`, D128) — qui solo tradotta."""
    r, g, b = role_style(role, role_styles).color
    return f"#{r:02x}{g:02x}{b:02x}"


def _round_points(seq) -> list:
    """Lista di punti (2D o 3D) → lista di [x, y] arrotondati."""
    return [[round(p[0], 4), round(p[1], 4)] for p in seq]


def _poly_points(polygon) -> list:
    """Vertici dell'anello esterno di un polygon shapely come lista di [x, y]."""
    if polygon is None or polygon.is_empty:
        return []
    return _round_points(polygon.exterior.coords)


def _track(segments, tolerance: float) -> list:
    """Traccia aperta (lista di segmenti nativi) discretizzata a lista di [x, y]."""
    return _round_points(track_points(segments, tolerance))


def _contour_entry(contour, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    role = getattr(contour, "role", ContourRole.UNKNOWN)
    pts = _poly_points(getattr(contour, "polygon", None)) or _track(
        getattr(contour, "segments", []), tolerance
    )
    return {"role": _role_str(role), "color": _color(role, role_styles), "points": pts, "closed": True}


def _feature_entries(item, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> list:
    """
    Un elemento dell'overlay (MAP.md D90) → una voce per contorno: ruolo,
    colore, punti, `closed` (ha un `polygon`), più i campi scalari del suo
    `to_dict()` se ne ha uno (un renderer disegna un cerchio vero se trova
    `center` + `diameter`).
    """
    role = getattr(item, "role", None)
    contours = getattr(item, "contours", None)
    if contours is None:
        contours = [item]
    extra = {}
    if callable(getattr(item, "to_dict", None)):
        for key, value in item.to_dict().items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                extra[key] = value
            elif isinstance(value, (tuple, list)) and all(isinstance(v, (int, float)) for v in value):
                extra[key] = [round(v, 4) for v in value]
    entries = []
    for contour in contours:
        c_role = feature_role(contour, role) or ContourRole.UNKNOWN
        polygon = getattr(contour, "polygon", None)
        pts = _poly_points(polygon) if polygon is not None else _track(
            getattr(contour, "segments", []) or [], tolerance
        )
        entries.append({**extra, "role": _role_str(c_role), "color": _color(c_role, role_styles),
                        "points": pts, "closed": polygon is not None})
    return entries


def _features(cluster, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    """`cluster.detected` per nome → lista di voci disegnabili."""
    if cluster.detected is None:
        return {}
    return {
        name: [e for item in items for e in _feature_entries(item, tolerance, role_styles)]
        for name, items in cluster.detected.items()
    }


def _loose_entry(curve, tolerance: float, role_styles: Mapping[str, RoleStyle]) -> dict:
    role = getattr(curve, "role", ContourRole.UNKNOWN)
    poly = getattr(curve, "polygon", None)
    if poly is not None:
        pts, closed = _poly_points(poly), True
    else:
        pts, closed = _track(getattr(curve, "segments", []), tolerance), False
    return {"role": _role_str(role), "color": _color(role, role_styles), "points": pts, "closed": closed}


def _annotation_entry(ann) -> dict:
    return {
        "kind":     ann.kind,
        "position": [round(ann.position[0], 4), round(ann.position[1], 4)],
        "text":     ann.display_text,
        "height":   getattr(ann, "height", 2.5) or 2.5,
        "rotation": getattr(ann, "rotation", 0.0) or 0.0,
    }


def _bbox_of(clusters) -> Optional[list]:
    boxes = [p.outer.bbox for p in clusters if p.outer is not None and p.outer.polygon is not None]
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
    tolerance: float = 0.05,
    include_loose: bool = True,
    include_annotations: bool = True,
    role_styles: Optional[Mapping[str, RoleStyle]] = None,
) -> dict:
    """
    `Result` → dizionario JSON-ready con la geometria di ogni feature.

    Args:
        result:              il `Result` da serializzare.
        tolerance:           tolleranza di discretizzazione per archi/cerchi/
                             spline delle tracce aperte (le tracce chiuse usano
                             il polygon già discretizzato al load).
        include_loose:       includi `result.loose`.
        include_annotations: includi `result.annotations`.
        role_styles:         `{ruolo: RoleStyle}` del chiamante (D128),
                             sopra la palette di topo: ne legge il colore.

    Non muta `result`. Non solleva su `result` non valido — ritorna comunque il
    dizionario con `is_valid=False` e le parti che ci sono (utile per debuggare
    un file che non healizza).
    """
    role_styles = dict(role_styles or {})
    parts_out = []
    for cluster in result.clusters:
        parts_out.append({
            "label":  cluster.label,
            "bbox":   list(cluster.bbox),
            "area":   round(cluster.area, 4),
            "outer":  _contour_entry(cluster.outer, tolerance, role_styles),
            "inners": [_contour_entry(i, tolerance, role_styles) for i in cluster.inners],
            # l'overlay di un consumatore, per nome (MAP.md D44, D90)
            "features": _features(cluster, tolerance, role_styles),
            "summary": cluster.summary,
            "custom":  cluster.custom,
        })

    vm = {
        "source_file": result.source_file,
        "is_valid":    result.is_valid,
        "cluster_count":  result.cluster_count,
        "bbox":        _bbox_of(result.clusters),
        "warnings":    list(result.warnings),
        "errors":      list(result.errors),
        "clusters":       parts_out,
        "palette":     _palette_dict(role_styles),
    }
    if include_loose:
        vm["loose"] = [_loose_entry(t, tolerance, role_styles) for t in result.loose]
    if include_annotations:
        vm["annotations"] = [_annotation_entry(a) for a in result.annotations]
    return vm


def _palette_dict(role_styles: Mapping[str, RoleStyle]) -> dict:
    """
    role (stringa) → colore hex, per la legenda di un renderer: i tre ruoli
    del motore e ogni ruolo a cui il chiamante dà un colore.
    """
    engine = [r.value for r in ContourRole]
    roles = engine + [r for r in role_styles if r not in engine]
    return {role: _color(role, role_styles) for role in roles}
