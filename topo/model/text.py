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
    - ``anchor_texts()`` → collega il testo alla geometria: ``cluster_ref``
      (indice della parte che lo contiene), ``target`` (l'elemento su cui cade
      la punta di ``pointer``), ``references`` (gli elementi fra cui misura).
    - agente → legge e modifica questi oggetti; un writer li riemette.

``cluster_ref`` è l'indice in ``result.clusters``, non un ``id()`` — così resta
valido dopo serializzazione. ``target`` e ``references`` sono percorsi
(es. ``"clusters[0].inners[3]"``).
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import List, Optional, Tuple

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
    Un testo della sorgente. ``position`` è il punto d'ancoraggio — dove un
    writer posiziona la stringa e su cui gira il contenimento. ``text`` è la
    stringa come si legge sul disegno.

    ``width_factor``: lo stretch orizzontale rispetto all'altezza (1.0 =
    nessuno). Senza, chi riscrive il testo su uno stile generico perde la
    condensazione dell'originale e il testo sborda dalla sua cella.

    ``pointer``: una polilinea che parte dalla punta (``pointer[0]``) — dove
    il testo indica. ``target`` è l'elemento su cui cade la punta.

    ``measured_points``: i punti sulla geometria fra cui è stato misurato il
    numero ``measure`` (due capi; due punti opposti di un cerchio; un punto
    di un arco). ``measure_is_angle``: il numero è un angolo, non una
    lunghezza. ``references``: gli elementi su cui cadono quei punti.

    ``rendered``: l'immagine che la sorgente disegna attorno (vuota per un
    testo semplice). ``source_kind``: il tipo di entità nel formato sorgente
    ("TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER" in un DXF).

    ``role``: cosa è il testo per un consumer (``"title_block"``,
    ``"part_code"``, ...), come per un edge: topo non lo legge e non lo
    decide (D127); ``unknown`` se nessuno l'ha detto.
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
    target:           Optional[str]    = None
    measured_points:  List[Point]      = field(default_factory=list)
    measure:          Optional[float]  = None
    measure_is_angle: bool             = False
    references:       List[str]        = field(default_factory=list)
    rendered:         RenderedGeometry = field(default_factory=RenderedGeometry)

    def __post_init__(self):
        self.role = normalize_role(self.role)
