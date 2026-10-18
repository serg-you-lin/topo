"""
core/topology/edge.py
----------------------
Rappresentazione topologica di una entità geometrica lineare — l'unità che
graph.py / loop_finder.py / non_contour_edges.py / gap_solver.py usano per
costruire e percorrere il grafo. Non è una primitiva geometrica (quelle sono
LineSeg/ArcSeg/SplineSeg/CircleSeg/EllipseSeg in core/primitives/segments.py,
math puro senza semantica): `Edge` ne avvolge una con ruolo, provenienza e
stile — dati di dominio, zero riferimento all'entità sorgente di alcun formato.

Vive in core/ (non più in adapters/bridge/, D18) perché è core il suo
consumatore principale: ogni adapter (DXF, PDF, ...) costruisce Edge, ma è
il core a definirne la forma, esattamente come per le primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

from ..primitives.segments import (
    LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg, segment_endpoints, segment_is_closed,
)
from ..geometry.measure import round_point
from ...model.style import EdgeStyle

Segment = Union[LineSeg, ArcSeg, SplineSeg, CircleSeg, EllipseSeg]


@dataclass
class Edge:
    """
    Layer intermedio tra l'entità sorgente grezza (di qualsiasi formato) e il
    topology engine. Dati puri — nessun riferimento all'entità sorgente.

    Campi:
        role       : ruolo semantico (stringa: costante ContourRole o slug di un
                     consumatore) — assegnato dall'adapter prima di costruire
                     l'Edge, mai derivato dal layer DXF qui dentro
        start      : endpoint arrotondato alla tolerance
        end        : endpoint arrotondato alla tolerance
        segment    : primitiva geometrica nativa — mai discretizzata qui,
                     la discretizzazione avviene nel LoopFinder via .discretize()
        style      : aspetto grezzo (linetype/colore) dell'entità sorgente —
                     captato dall'adapter, mai interpretato qui (Cluster E).

    Deliberatamente NIENTE campo che dica "veniva da una LWPOLYLINE chiusa"
    o simili: se un percorso è già chiuso è un fatto che il grafo di topo
    scopre da sé (`Graph.degenerate_loops`, un loop trovato dal
    `LoopFinder`) — non un'informazione che l'adapter può accorciare
    consegnandola come flag. Un flag così è la provenienza nel formato
    sorgente travestita da proprietà topologica: un adapter PDF/SVG non
    avrebbe modo di popolarlo, e il core non deve mai aver bisogno che lo
    faccia (trovato e tolto: MAP.md, seguito D50).
    """
    role:    str
    start:   Tuple[float, float]
    end:     Tuple[float, float]
    segment: Segment
    style:   EdgeStyle = field(default_factory=EdgeStyle)

    @classmethod
    def of(cls, segment: Segment, role: str, style: Optional[EdgeStyle] = None) -> "Edge":
        """
        L'Edge di `segment`: gli estremi sulla griglia dei nodi di topo (D113),
        che un adapter non deve conoscere. Una curva chiusa (cerchio, spline o
        ellisse con gli estremi entro la tolleranza) ha un nodo solo: è un loop
        degenere, che il grafo riconosce da sé. Una linea o un arco cortissimi
        restano due nodi — sono lati, non loop.

        È il modo in cui un adapter costruisce un Edge (MAP.md D125).
        """
        start, end = segment_endpoints(segment)
        start = round_point(start)
        if isinstance(segment, (CircleSeg, SplineSeg, EllipseSeg)) and segment_is_closed(segment):
            end = start
        else:
            end = round_point(end)
        return cls(role=role, start=start, end=end, segment=segment, style=style or EdgeStyle())
