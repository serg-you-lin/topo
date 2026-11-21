"""
topo/model/text.py
------------------
I testi della sorgente come dati di dominio (MAP.md D20, D138): un tipo solo,
`Text`. Una stringa posata nel piano (D257); con, se la sorgente lo dà, il
disegno che la sorgente le traccia attorno (`rendered`) e cosa misura coi
punti che la sorgente scrive (`measures`, D264). Che sia una nota, una quota o
un richiamo e dove punta è una lettura del consumatore (D259); il tipo
d'entità della sorgente non entra nel modello (D256).
`halign`/`valign` dicono come la stringa sta attorno a `position`, con lo
stesso significato per ogni formato.

Divisione dei compiti:
    - adapter → read/write formato ↔ modello, solo conoscenza di formato (dove
      sta il testo, come si appiattisce il blocco di una quota).
    - ``anchor_texts()`` → ``cluster_ref`` (indice della parte che lo
      contiene).
    - agente → legge e modifica questi oggetti; un writer li riemette.

``cluster_ref`` è l'indice in ``result.clusters``, non un ``id()`` — così resta
valido dopo serializzazione.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import List, Optional, Tuple, Union

from .role import ContourRole, normalize_role

Point = Tuple[float, float]

# Come la stringa sta attorno al suo punto (D256): orizzontale e verticale.
HALIGNS = ("left", "center", "right")
VALIGNS = ("baseline", "bottom", "center", "top")


def _check_align(halign: str, valign: str) -> None:
    if halign not in HALIGNS:
        raise ValueError(f"halign {halign!r}: one of {', '.join(HALIGNS)}")
    if valign not in VALIGNS:
        raise ValueError(f"valign {valign!r}: one of {', '.join(VALIGNS)}")


@dataclass
class RenderedText:
    """Una stringa dentro l'immagine appiattita di un testo (`Text.rendered`)."""
    content:  str
    position: Point
    _: KW_ONLY
    height:   float = 2.5
    rotation: float = 0.0
    halign:   str   = "left"
    valign:   str   = "baseline"

    def __post_init__(self):
        _check_align(self.halign, self.valign)


@dataclass
class RenderedGeometry:
    """
    L'immagine che la sorgente disegna attorno a una stringa (linee, frecce,
    altri testi), già appiattita in primitive pure.

    Serve all'output fedele: in certi formati la geometria di una quota o di
    un richiamo sta in un blocco a parte, non nei campi dell'entità; la si
    conserva qui e un writer la ri-materializza.
    """
    _: KW_ONLY
    strokes: List[List[Point]]  = field(default_factory=list)  # polilinee aperte
    fills:   List[List[Point]]  = field(default_factory=list)  # polilinee chiuse
    texts:   List[RenderedText] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.strokes and not self.fills and not self.texts


@dataclass(frozen=True)
class MeasuredDistance:
    """
    What a dimension measures when it is a distance, as its source writes it
    (`Text.measures`). ``first``/``second``: the two measured points;
    ``line_at``: a point the measure line passes through; ``direction``: the
    measure's direction in degrees, ``None`` = along ``first`` → ``second``.
    ``decimals``: how many decimals the source writes the number with.
    ``drawn_to_real``: drawn length → real length; the number is the
    distance between the points times it (a view drawn at 1:4 has 4, a
    detail at 4:1 has 0.25). ``None`` if the source does not say, or writes the
    number by hand: then the number is `Text.text` as written.
    """
    first:         Point
    second:        Point
    line_at:       Point
    direction:     Optional[float] = None
    _: KW_ONLY
    decimals:      Optional[int]   = None
    drawn_to_real: Optional[float] = None


@dataclass(frozen=True)
class MeasuredRadius:
    """A radius, as the source writes it: ``center`` and a point ``on_circle``;
    the other fields as in `MeasuredDistance`."""
    center:      Point
    on_circle:   Point
    _: KW_ONLY
    decimals:      Optional[int]   = None
    drawn_to_real: Optional[float] = None


@dataclass(frozen=True)
class MeasuredDiameter:
    """A diameter, as the source writes it: two opposite points of the circle;
    the other fields as in `MeasuredDistance`."""
    on_circle:   Point
    opposite:    Point
    _: KW_ONLY
    decimals:      Optional[int]   = None
    drawn_to_real: Optional[float] = None


@dataclass(frozen=True)
class MeasuredAngle:
    """
    An angle between two legs, as the source writes it: each leg is two
    points of its line; ``arc_at`` is a point the measure arc passes through,
    so it picks which of the four angles the legs make. ``decimals`` as in
    `MeasuredDistance`.
    """
    first_leg:   Tuple[Point, Point]
    second_leg:  Tuple[Point, Point]
    arc_at:      Point
    _: KW_ONLY
    decimals:    Optional[int]   = None


Measure = Union[MeasuredDistance, MeasuredRadius, MeasuredDiameter, MeasuredAngle]


@dataclass
class Text:
    """
    A text of the source. ``position`` is the anchor point — where a writer
    places the string and on which containment works. ``text`` is the string
    as it reads on the drawing.

    ``width_factor``: the horizontal stretch relative to the height (1.0 =
    none). Without it, whoever rewrites the text on a generic style loses the
    original's condensation and the text overflows its cell.

    ``halign`` (``left``/``center``/``right``) and ``valign``
    (``baseline``/``bottom``/``center``/``top``): where ``position`` lies on
    the string, the same for every format; ``left``/``baseline`` when the
    source does not say. Unknown value → ``ValueError``.

    ``rendered``: the strokes, fills and strings the source draws with it
    (a dimension's or leader's own block), empty for a plain text and
    for a source that does not group them; never built by topo (D262).
    Where a pointer lands is a reading (D259).

    ``measures``: what the text measures, with the points its source writes
    (``MeasuredDistance``, ``MeasuredRadius``, ``MeasuredDiameter``,
    ``MeasuredAngle``), ``None`` for any other text or when the source does
    not say. A ``<>`` in ``text`` is where the measure goes when the source
    writes no number (D264).

    ``role``: what the text is for a consumer (``"title_block"``,
    ``"part_code"``, ...), as for an edge: topo does not read it and does not
    decide it (D127); ``unknown`` if nobody said.
    """
    position:         Point
    text:             str              = ""
    _: KW_ONLY
    height:           float            = 2.5
    rotation:         float            = 0.0
    width_factor:     float            = 1.0
    role:             str              = ContourRole.UNKNOWN.value
    origin:           Optional[str]    = None   # provenienza nella sorgente — diagnostica
    cluster_ref:      Optional[int]    = None   # indice in result.clusters della parte che lo contiene
    halign:           str              = "left"
    valign:           str              = "baseline"
    rendered:         RenderedGeometry = field(default_factory=RenderedGeometry)
    measures:         Optional[Measure] = None

    def __post_init__(self):
        self.role = normalize_role(self.role)
        _check_align(self.halign, self.valign)
