"""
io/svg.py
---------
`to_svg(result)` — SVG renderer of the topo model.
Outside the stable 1.0: the viewer is `topo.experimental`.

SVG **output only**: a visual representation of the `Result`, for a UI, a
report, a quick preview. Not for cutting — arcs, circles and splines are
discretized to polylines (via `to_view_model`).

One colour per role: topo's palette, with the caller's `role_styles` on top.
Y is flipped (the model has Y up, SVG down).
"""

from __future__ import annotations

from ..precision import SAME_POINT
import html
from typing import Mapping, Optional

from ..model import Result, RoleStyle
from .view_model import to_view_model


def _fmt(pts) -> str:
    """List of [x, y] → string 'x0,y0 x1,y1 …' for points= of polyline/polygon."""
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in pts)


def _shape(entry: dict, stroke_w: float, true_circles: bool) -> str:
    pts = entry.get("points") or []
    color = entry.get("color", "#ff0000")

    if true_circles and (entry.get("diameter") or 0) > 0 and entry.get("center"):
        cx, cy = entry["center"]
        r = entry["diameter"] / 2.0
        return (f'<circle cx="{cx:.4f}" cy="{cy:.4f}" r="{r:.4f}" '
                f'fill="none" stroke="{color}" stroke-width="{stroke_w:.4f}"/>')

    if len(pts) < 2:
        return ""
    tag = "polygon" if entry.get("closed") else "polyline"
    return (f'<{tag} points="{_fmt(pts)}" fill="none" '
            f'stroke="{color}" stroke-width="{stroke_w:.4f}"/>')


def to_svg(
    result: Result,
    tolerance: float = SAME_POINT,
    include_loose: bool = True,
    include_texts: bool = True,
    padding: float = 0.03,
    background: Optional[str] = "#1e1e1e",
    true_circles: bool = True,
    stroke_width: Optional[float] = None,
    size: Optional[str] = None,
    units: Optional[str] = None,
    allow_invalid: bool = True,
    role_styles: Optional[Mapping[str, RoleStyle]] = None,
) -> str:
    """`Result` → complete SVG string (`<svg>…</svg>`).

    Args:
        tolerance:           discretization of arcs/splines in open traces.
        include_loose:       also draw `result.loose` (red).
        include_texts: draw the source's texts.
        padding:             margin around the image, fraction of the bbox side.
        background:          background colour (`None` = transparent).
        true_circles:        draw as a real `<circle>` an overlay entry that
                             carries Ø/centre, instead of the N-sided polygon.
        stroke_width:        line width in the units of the input; `None` = auto
                             (bbox diagonal / 400).
        size:                `width`/`height` attributes of the `<svg>`. `None`
                             (default) OMITS them: the SVG scales to fill the
                             container (or the browser window) — it is vector,
                             zoom as much as you like. Pass a string like `"800"`
                             to fix the width in px (the height follows the
                             `viewBox` ratio).
        units:               `"mm"` → SVG **in real scale** for a 1:1 CAM/laser
                             import (`width="…mm" height="…mm"`, padding and
                             background forced to 0/None). Ignores `size` and
                             `padding`. NB: arcs/circles/splines stay
                             discretized — for high-fidelity cutting use an
                             adapter's writer, which writes the curves, not the
                             SVG. `None` = SVG for viewing.
        role_styles:         the caller's `{role: RoleStyle}`: the colour of
                             every role, as in every exporter.

    An invalid `result` is drawn anyway (empty or with `loose` only);
    `allow_invalid=False` → `ValueError`, for whoever delivers to a machine (same
    contract as every exporter)."""
    if not result.is_valid and not allow_invalid:
        raise ValueError(
            "to_svg(): the Result is not valid, no output. "
            + " ".join(result.errors)
        )
    cam = units == "mm"
    if cam:
        padding = 0.0
        background = None
    vm = to_view_model(
        result, tolerance=tolerance,
        include_loose=include_loose, include_texts=include_texts,
        role_styles=role_styles,
    )

    bbox = vm.get("bbox") or _scan_bbox(vm)
    if bbox is None:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'

    minx, miny, maxx, maxy = bbox
    w = max(maxx - minx, 1e-6)
    h = max(maxy - miny, 1e-6)
    pad = max(w, h) * padding
    vminx, vminy = minx - pad, miny - pad
    vw, vh = w + 2 * pad, h + 2 * pad
    sw = stroke_width if stroke_width is not None else (w * w + h * h) ** 0.5 / 400.0

    if cam:
        dims = f' width="{vw:.4f}mm" height="{vh:.4f}mm"'
    elif size is None:
        dims = ""
    else:
        wpx = float(size)
        dims = f' width="{wpx:.0f}" height="{wpx * vh / vw:.0f}"'
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vminx:.4f} {vminy:.4f} '
        f'{vw:.4f} {vh:.4f}"{dims} preserveAspectRatio="xMidYMid meet">'
    ]
    if background:
        out.append(f'<rect x="{vminx:.4f}" y="{vminy:.4f}" width="{vw:.4f}" '
                   f'height="{vh:.4f}" fill="{background}"/>')

    # Y-flip: (x, y) → (x, miny+maxy - y), stays inside [miny, maxy]
    flip = miny + maxy
    out.append(f'<g transform="matrix(1 0 0 -1 0 {flip:.4f})" '
               f'stroke-linejoin="round" stroke-linecap="round">')

    for i, cluster in enumerate(vm["clusters"]):
        out.append(f'<g data-cluster="{html.escape(str(cluster.get("label") or i))}">')
        out.append(_shape(cluster["outer"], sw, False))
        for inner in cluster["inners"]:
            out.append(_shape(inner, sw, False))
        for entries in cluster["features"].values():
            for entry in entries:
                out.append(_shape(entry, sw, true_circles))
        out.append("</g>")

    for t in vm.get("loose", []):
        out.append(_shape(t, sw, False))

    out.append("</g>")  # end flipped group

    # Texts: outside the flipped group (otherwise they would be mirrored)
    for ann in vm.get("texts", []):
        txt = (ann.get("text") or "").strip()
        if not txt:
            continue
        x, y = ann["position"]
        fy = flip - y
        size = ann.get("height") or 2.5
        rot = ann.get("rotation") or 0.0
        transform = f' transform="rotate({-rot:.2f} {x:.4f} {fy:.4f})"' if rot else ""
        out.append(
            f'<text x="{x:.4f}" y="{fy:.4f}" font-size="{size:.4f}" '
            f'fill="#c8c8c8" font-family="sans-serif"{transform}>{html.escape(txt)}</text>'
        )

    out.append("</svg>")
    return "\n".join(s for s in out if s)


def save_svg(result: Result, path: str, **kwargs) -> None:
    """Write `to_svg(result, **kwargs)` to a file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_svg(result, **kwargs))


def _scan_bbox(vm: dict) -> Optional[list]:
    """bbox from all the points of the view model — fallback when vm['bbox'] is None."""
    xs, ys = [], []

    def _collect(entry):
        for p in entry.get("points") or []:
            xs.append(p[0]); ys.append(p[1])

    for cluster in vm.get("clusters", []):
        _collect(cluster["outer"])
        for e in cluster["inners"]:
            _collect(e)
        for entries in cluster["features"].values():
            for e in entries:
                _collect(e)
    for t in vm.get("loose", []):
        _collect(t)

    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]
