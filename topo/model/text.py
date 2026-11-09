"""
topo/model/text.py
------------------
I testi della sorgente come dati di dominio (MAP.md D20, D138): un tipo solo,
`Text`. Una stringa in un punto; con, se la sorgente li dà, una polilinea che
punta a qualcosa (`pointer`, la punta per prima) e i punti fra cui il numero
che mostra è stato misurato (`measured_points`, `measure`). Che sia una nota,
una quota o un richiamo è una lettura del consumatore, anche quando il formato
lo dice già: il formato resta in `source_kind`, per riscriverlo fedele.

Divisione dei compiti:
    - adapter → read/write formato ↔ modello, solo conoscenza di formato (dove
      sta il testo, come si appiattisce il blocco di una quota DXF).
    - ``anchor_texts()`` → ``cluster_ref`` (indice della parte che lo
      contiene); ``topo.experimental.anchor_elements()`` (D228) → ``target``
      (l'elemento su cui cade la punta di ``pointer``), ``references`` (gli
      elementi fra cui misura).
    - agente → legge e modifica questi oggetti; un writer li riemette.

``cluster_ref`` è l'indice in ``result.clusters``, non un ``id()`` — così resta
valido dopo serializzazione. ``target`` e ``references`` sono gli oggetti
stessi (contorno, feature, curva di ``loose``): restano giusti se un consumer
riordina le collezioni o promuove una curva (D177).
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Any, List, Optional, Tuple

from .role import ContourRole, normalize_role

Point = Tuple[float, float]


@dataclass
class RenderedText:
    """Una stringa dentro l'immagine appiattita di un testo (`Text.rendered`)."""
    content:  str
    position: Point
    _: KW_ONLY
    height:   float = 2.5
    rotation: float = 0.0


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

    ``pointer``: a polyline starting at the tip (``pointer[0]``) — where the
    text points. ``target`` is the element the tip falls on.

    ``measured_points``: the points on the geometry between which the number
    ``measure`` was measured (two ends; two opposite points of a circle; a
    point of an arc). ``measure_is_angle``: the number is an angle, not a
    length. ``references``: the elements the points fall on.

    ``rendered``: the image the source draws around it (empty for a plain
    text). ``source_kind``: the entity type in the source format ("TEXT",
    "MTEXT", "DIMENSION", "LEADER", "MULTILEADER" in a DXF).

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
    source_kind:      str              = ""
    pointer:          List[Point]      = field(default_factory=list)
    target:           Optional[Any]    = field(default=None, repr=False, compare=False)
    measured_points:  List[Point]      = field(default_factory=list)
    measure:          Optional[float]  = None
    measure_is_angle: bool             = False
    references:       List[Any]        = field(default_factory=list, repr=False, compare=False)
    rendered:         RenderedGeometry = field(default_factory=RenderedGeometry)

    def __post_init__(self):
        self.role = normalize_role(self.role)
