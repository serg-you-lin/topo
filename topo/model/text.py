"""
topo/model/text.py
------------------
I testi della sorgente come dati di dominio (MAP.md D20, D138): un tipo solo,
`Text`. Una stringa posata nel piano (D257); con, se la sorgente lo dà, il
disegno che la sorgente le traccia attorno (`rendered`). Che sia una nota,
una quota o un richiamo, cosa misura e dove punta è una lettura del
consumatore, anche quando il formato lo dice già (D259): né il tipo d'entità
della sorgente (D256) né le sue affermazioni entrano nel modello.
`halign`/`valign` dicono come la stringa sta attorno a `position`, con lo
stesso significato per ogni formato.

Divisione dei compiti:
    - adapter → read/write formato ↔ modello, solo conoscenza di formato (dove
      sta il testo, come si appiattisce il blocco di una quota DXF).
    - ``anchor_texts()`` → ``cluster_ref`` (indice della parte che lo
      contiene).
    - agente → legge e modifica questi oggetti; un writer li riemette.

``cluster_ref`` è l'indice in ``result.clusters``, non un ``id()`` — così resta
valido dopo serializzazione.
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import List, Optional, Tuple

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

    Serve all'output fedele: in un DXF la geometria di una DIMENSION o di un
    LEADER sta in un blocco anonimo, non nei campi dell'entità; la si conserva
    qui e un writer la ri-materializza.
    """
    _: KW_ONLY
    strokes: List[List[Point]]  = field(default_factory=list)  # polilinee aperte
    fills:   List[List[Point]]  = field(default_factory=list)  # polilinee chiuse
    texts:   List[RenderedText] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.strokes and not self.fills and not self.texts


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
    (a DXF dimension's or leader's own block), empty for a plain text and
    for a source that does not group them. What they mean — what is
    measured, where it points — is a reading (D259).

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

    def __post_init__(self):
        self.role = normalize_role(self.role)
        _check_align(self.halign, self.valign)
