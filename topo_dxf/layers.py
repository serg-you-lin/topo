"""
topo_dxf/layers.py
------------------
Where the DXF adapter writes a role when the caller does not say, and how it
translates topo's palette colour into DXF.

topo has no layers: the names here are the DXF adapter's default, not a topo
rule. The caller chooses the layers with `to_dxf(layers=...)`. The colour is
not the adapter's: it is topo's palette (`topo.model.role_style`), only
written here as an ACI index when it has an exact one.

A role the default does not name goes on a layer named after its slug: its
geometry is not trash and stays distinct. `unknown` goes on `Trash`.
"""

from typing import Callable, Mapping, Optional, Union

from ezdxf.colors import aci2rgb

from topo.model import ContourRole, role_str, role_style

# Texts and dimensions with no role: the DXF "foreground" (white on a dark
# background, black on a light one) — a colour that exists only in DXF, not a role
COLOR_ANNOTATION = 7

# Default layer names
LAYER_OUTER      = "OuterContour"
LAYER_INNER      = "InnerContour"
LAYER_ANNOTATION = "Annotation"
TRASH_LAYER      = "Trash"

# The layers the writer uses for what is not part geometry: whoever re-reads a
# file already passed through topo (round-trip, re-heal) and does not want them
# passes them to `load_dxf(skip_layers=SKIP_LAYERS)`; by default everything is read
SKIP_LAYERS: tuple[str, ...] = (TRASH_LAYER, LAYER_ANNOTATION)


# role → default layer
DEFAULT_LAYERS: dict[str, str] = {
    ContourRole.OUTER.value:   LAYER_OUTER,
    ContourRole.INNER.value:   LAYER_INNER,
    ContourRole.UNKNOWN.value: TRASH_LAYER,
}

# A role's layer as the caller gives it: a name, or a function of the written
# element (a Contour, an element of `cluster.overlay`, a `loose` curve, a Text)
# that returns its name — so the entities of a role can split over several
# layers (an "up" and a "down" bend).
LayerChoice = Union[str, Callable[[object], str]]
LayerMap = Mapping[str, LayerChoice]
LayerMap.__doc__ = """
The type of the `layers` argument of `to_dxf`: a mapping `{role: layer name}`
or `{role: function(element) -> layer name}`.
"""


def role_to_dxf_layer(role, element: object = None, *, layers: Optional[LayerMap] = None) -> str:
    """
    Name of the DXF layer for `role`. The caller's choice (`layers`, keys
    already normalized to slugs) wins: a name, or the function called with
    `element`. Otherwise the default: `OuterContour`/`InnerContour`/`Trash`
    for the engine's roles, the slug itself for every other role.
    """
    slug = _slug(role)
    choice = (layers or {}).get(slug)
    if callable(choice):
        return choice(element)
    if choice:
        return choice
    return DEFAULT_LAYERS.get(slug, slug)


# RGB → ACI index, only for colours that have an exact index
_ACI_BY_RGB: dict[tuple, int] = {}
for _aci in range(255, 0, -1):          # on equal RGB the lowest index wins
    _ACI_BY_RGB[tuple(aci2rgb(_aci))] = _aci


def color_for_role(role) -> Optional[int]:
    """The colour of topo's palette for `role` as an ACI index: green 3, yellow 2,
    red 1, grey 8. None if it has no exact one."""
    return _ACI_BY_RGB.get(tuple(role_style(role).color or ()))


def _slug(role) -> str:
    return role_str(role) if role else ContourRole.UNKNOWN.value


# The default layers with their colour — created in every written document
ALL_LAYERS: dict[str, int] = {
    LAYER_OUTER:      color_for_role(ContourRole.OUTER),
    LAYER_INNER:      color_for_role(ContourRole.INNER),
    LAYER_ANNOTATION: COLOR_ANNOTATION,
    TRASH_LAYER:      color_for_role(ContourRole.UNKNOWN),
}
