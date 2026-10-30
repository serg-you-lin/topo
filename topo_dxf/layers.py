"""
topo_dxf/layers.py
------------------
Dove l'adapter DXF scrive un ruolo quando il chiamante non lo dice, e come
traduce in DXF il colore della palette di topo (MAP.md D123, D128).

topo non ha layer: i nomi qui sono il default dell'adapter DXF, non una
regola di topo. Il chiamante sceglie i layer con `to_dxf(layers=...)`. Il
colore non è dell'adapter: è la palette di topo (`topo.model.role_style`),
qui solo scritta come indice ACI quando ne ha uno esatto.

Un ruolo che il default non nomina va su un layer col nome del suo slug: la
sua geometria non è spazzatura e resta distinta (D31). `unknown` va su
`Trash`.
"""

from typing import Callable, Mapping, Optional, Union

from ezdxf.colors import aci2rgb

from topo.model import ContourRole, role_str, role_style

# Testi e quote senza ruolo: il "foreground" del DXF (bianco su fondo scuro,
# nero su fondo chiaro) — un colore che esiste solo in DXF, non un ruolo
COLOR_ANNOTATION = 7

# ---------------------------------------------------------------------------
# Nomi di layer di default
# ---------------------------------------------------------------------------
LAYER_OUTER      = "OuterContour"
LAYER_INNER      = "InnerContour"
LAYER_ANNOTATION = "Annotation"
TRASH_LAYER      = "Trash"

# I layer che il writer usa per ciò che non è geometria di parte: rileggendo
# un file già passato da topo (round-trip, ri-heal) il lettore li salta,
# senza doverlo chiedere al chiamante — `load_dxf(skip_layers=...)`, `()`
# per leggere tutto (D129)
SKIP_LAYERS: tuple[str, ...] = (TRASH_LAYER, LAYER_ANNOTATION)


# ruolo → layer di default
DEFAULT_LAYERS: dict[str, str] = {
    ContourRole.OUTER.value:   LAYER_OUTER,
    ContourRole.INNER.value:   LAYER_INNER,
    ContourRole.UNKNOWN.value: TRASH_LAYER,
}

# Il layer di un ruolo come lo dà il chiamante: un nome, o una funzione
# dell'elemento scritto (un Contour, un elemento di `cluster.detected`,
# una curva di `loose`, un Text) che ne ritorna il nome — così le entità
# di un ruolo possono dividersi su più layer (una piega "up" e una "down").
LayerChoice = Union[str, Callable[[object], str]]
LayerMap = Mapping[str, LayerChoice]


def role_to_dxf_layer(role, element: object = None, *, layers: Optional[LayerMap] = None) -> str:
    """
    Nome del layer DXF per `role`. La scelta del chiamante (`layers`, chiavi
    già normalizzate a slug) vince: un nome, o la funzione chiamata con
    `element`. Altrimenti il default: `OuterContour`/`InnerContour`/`Trash`
    per i ruoli del motore, lo slug stesso per ogni altro ruolo (D31).
    """
    slug = _slug(role)
    choice = (layers or {}).get(slug)
    if callable(choice):
        return choice(element)
    if choice:
        return choice
    return DEFAULT_LAYERS.get(slug, slug)


# RGB → indice ACI, solo per i colori che hanno un indice esatto
_ACI_BY_RGB: dict[tuple, int] = {}
for _aci in range(255, 0, -1):          # a parità di RGB vince l'indice più basso
    _ACI_BY_RGB[tuple(aci2rgb(_aci))] = _aci


def color_for_role(role) -> Optional[int]:
    """Il colore della palette di topo per `role` (D128) come indice ACI:
    verde 3, giallo 2, rosso 1, grigio 8. None se non ne ha uno esatto."""
    return _ACI_BY_RGB.get(tuple(role_style(role).color or ()))


def _slug(role) -> str:
    return role_str(role) if role else ContourRole.UNKNOWN.value


# I layer di default col loro colore — creati in ogni documento scritto
ALL_LAYERS: dict[str, int] = {
    LAYER_OUTER:      color_for_role(ContourRole.OUTER),
    LAYER_INNER:      color_for_role(ContourRole.INNER),
    LAYER_ANNOTATION: COLOR_ANNOTATION,
    TRASH_LAYER:      color_for_role(ContourRole.UNKNOWN),
}
