"""
topo/model/text.py
------------------
The source's texts as domain data: a single type, `Text`. A string laid on the
plane; with, if the source gives it, the drawing the source traces around it
(`rendered`) and what it measures with the points the source writes
(`measures`). Whether it is a note, a dimension or a callout and where it
points is a consumer's reading; the source's entity type does not enter the
model. `halign`/`valign` say how the string sits around `position`, with the
same meaning for every format.

Division of tasks:
    - adapter → read/write format ↔ model, format knowledge only (where the
      text is, how a dimension's block is flattened).
    - ``anchor_texts()`` → ``cluster_ref`` (index of the part that contains it).
    - agent → reads and edits these objects; a writer re-emits them.

``cluster_ref`` is the index in ``result.clusters``, not an ``id()`` — so it
stays valid after serialization.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import List, Optional, Tuple, Union

from .role import ContourRole, normalize_role

Point = Tuple[float, float]

# How the string sits around its point: horizontal and vertical.
HALIGNS = ("left", "center", "right")
VALIGNS = ("baseline", "bottom", "center", "top")


def _check_align(halign: str, valign: str) -> None:
    if halign not in HALIGNS:
        raise ValueError(f"halign {halign!r}: one of {', '.join(HALIGNS)}")
    if valign not in VALIGNS:
        raise ValueError(f"valign {valign!r}: one of {', '.join(VALIGNS)}")


@dataclass
class RenderedText:
    """A string inside the flattened image of a text (`Text.rendered`)."""
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
    """The image the source draws around a string (lines, arrows, other texts),
    already flattened into pure primitives.

    It serves faithful output: in some formats the geometry of a dimension or a
    callout is in a separate block, not in the entity's fields; it is kept here
    and a writer re-materializes it."""
    _: KW_ONLY
    strokes: List[List[Point]]  = field(default_factory=list)  # open polylines
    fills:   List[List[Point]]  = field(default_factory=list)  # closed polylines
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
    """A text of the source. ``position`` is the anchor point — where a writer
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
    for a source that does not group them; never built by topo.
    Where a pointer lands is a reading.

    ``measures``: what the text measures, with the points its source writes
    (``MeasuredDistance``, ``MeasuredRadius``, ``MeasuredDiameter``,
    ``MeasuredAngle``), ``None`` for any other text or when the source does
    not say. A ``<>`` in ``text`` is where the measure goes when the source
    writes no number.

    ``role``: what the text is for a consumer (``"title_block"``,
    ``"part_code"``, ...), as for an edge: topo does not read it and does not
    decide it; ``unknown`` if nobody said."""
    position:         Point
    text:             str              = ""
    _: KW_ONLY
    height:           float            = 2.5
    rotation:         float            = 0.0
    width_factor:     float            = 1.0
    role:             str              = ContourRole.UNKNOWN.value
    origin:           Optional[str]    = None   # provenance in the source — diagnostics
    cluster_ref:      Optional[int]    = None   # index in result.clusters of the part that contains it

    halign:           str              = "left"
    valign:           str              = "baseline"
    rendered:         RenderedGeometry = field(default_factory=RenderedGeometry)
    measures:         Optional[Measure] = None

    def __post_init__(self):
        self.role = normalize_role(self.role)
        _check_align(self.halign, self.valign)
