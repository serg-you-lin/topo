"""
model/style.py
---------------
Raw visual appearance of a source entity — line type, stroke and colour.

Pure domain data, in a vocabulary no format owns: no colour indices, no style
inherited "from the layer" or "from the block", no pattern in a format's
shape. Every adapter translates its format into these fields at load,
resolving inheritance (a "layer" style is the style the line really has) and
translates it back on output. Captured at load (`Edge.style`), it survives in
the model as `styles` — a list parallel to `segments` on ClosedCurve/OpenCurve
— and an exporter restores its stroke. The colour does not: on output it is
decided by the role, with the caller's map; it stays here because
`RoleRule(color=...)` reads it.

`RoleStyle`, in the same vocabulary, is the other direction: how a role is
drawn on output. topo's palette (`DEFAULT_ROLE_STYLES`) gives the colour to the
roles topo produces — outer green, inner yellow, unknown red — and grey to
every other; the caller's map goes on top. Every exporter asks
`role_style(role, map)` and only translates: the choice is topo's and the
caller's, never a format's.
"""

from __future__ import annotations

from ..precision import MARK_FRACTION
from dataclasses import KW_ONLY, dataclass, fields, replace
from typing import Mapping, Optional, Tuple

from .role import ContourRole, role_str

# Stroke shape: continuous, uniform dash (a single repeated mark: all-equal
# strokes, or only dots), chain (alternating different marks: long stroke +
# short stroke or dot).
DASH_CONTINUOUS = "continuous"
DASH_UNIFORM    = "uniform"
DASH_CHAIN      = "chain"
VALID_DASH_KINDS = {DASH_CONTINUOUS, DASH_UNIFORM, DASH_CHAIN}

# Two marks are "different" if they differ by more than this fraction of the
# pattern's total length: relative, so the pattern's scale does not matter.
_MARK_REL_TOL = MARK_FRACTION


@dataclass
class EdgeStyle:
    """Fields (all optional: an empty `EdgeStyle()` is "the source does not say"):
        linetype      : name of the line type in the source ("HIDDEN",
                        "CENTER", "CONTINUOUS"), "" if it has none
        linetype_desc : its description, if the source carries it
        dash          : the stroke, as signed repeated marks — `> 0`
                        stroke, `0` dot, `< 0` gap (mm). `()` = declared
                        continuous, `None` = not known. A PDF/SVG dash-array
                        `[3, 1]` is `(3, -1)`.
        color         : effective colour (r, g, b) 0–255, None if not known
        filled        : the line is a side of a filled area (a SOLID, a filled
                        HATCH, the outline of a wide polyline; a filled PDF/SVG path)"""
    _: KW_ONLY
    linetype:      str                          = ""
    linetype_desc: str                          = ""
    dash:          Optional[Tuple[float, ...]]  = None
    color:         Optional[Tuple[int, int, int]] = None
    filled:        bool                         = False

    @property
    def is_dashed(self) -> bool:
        """True if the stroke has at least one gap."""
        return any(element < 0 for element in self.dash or ())

    @property
    def dash_kind(self) -> str:
        """Stroke shape: `continuous`, `uniform` or `chain`."""
        if not self.is_dashed:
            return DASH_CONTINUOUS
        marks = [e for e in self.dash if e >= 0]    # strokes (> 0) and dots (= 0)
        total = sum(abs(e) for e in self.dash)
        if max(marks, default=0.0) - min(marks, default=0.0) > _MARK_REL_TOL * total:
            return DASH_CHAIN
        return DASH_UNIFORM


@dataclass(frozen=True)
class RoleStyle:
    """How the caller wants an output role drawn. The caller keeps
    a `{role: RoleStyle}` dict and passes it to every exporter (an adapter's
    writer, `split`, `to_svg`, `to_view_model`): topo keeps none, each exporter has
    its own default for the fields left at `None`.

    Same vocabulary as `EdgeStyle`, no format. Where a role ends up (a layer,
    an SVG group) is not decided here: the exporter decides, with its own
    parameters.

    Fields (all optional):
        color      : (r, g, b) 0–255
        linetype   : name of the line type, for formats that name them;
                     alone it means a standard type of the format ("DASHED")
        dash       : the stroke, signed marks as in `EdgeStyle.dash`
        lineweight : width in mm"""
    _: KW_ONLY
    color:      Optional[Tuple[int, int, int]] = None
    linetype:   Optional[str]                  = None
    dash:       Optional[Tuple[float, ...]]    = None
    lineweight: Optional[float]                = None


# --- topo's palette: the colour of the roles faces()/outlines() produce, the same for every format. A consumer's role that no map names is grey: topo does not know what it is, but it is not trash. ---
DEFAULT_ROLE_STYLES: Mapping[str, RoleStyle] = {
    ContourRole.OUTER.value:   RoleStyle(color=(0, 255, 0)),      # verde
    ContourRole.INNER.value:   RoleStyle(color=(255, 255, 0)),    # giallo
    ContourRole.UNKNOWN.value: RoleStyle(color=(255, 0, 0)),      # rosso
}
CONSUMER_ROLE_STYLE = RoleStyle(color=(128, 128, 128))            # grigio


def role_style(role, *, role_styles: Optional[Mapping[str, RoleStyle]] = None) -> RoleStyle:
    """How `role` is drawn: topo's palette (or the grey of a consumer's role), with
    on top the non-`None` fields of the `RoleStyle` the caller gives for that role
    in `role_styles`. A consumer adds its own roles without rewriting topo's, and
    can change one."""
    slug = role_str(role) if role else ContourRole.UNKNOWN.value
    base = DEFAULT_ROLE_STYLES.get(slug, CONSUMER_ROLE_STYLE)
    own = (role_styles or {}).get(slug)
    if own is None:
        return base
    return replace(base, **{f.name: getattr(own, f.name)
                            for f in fields(own) if getattr(own, f.name) is not None})
