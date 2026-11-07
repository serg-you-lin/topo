"""
topo/core/readings/touching.py
------------------------------
Raggruppa gli Edge che si toccano: due edge stanno nello stesso gruppo se la
distanza vera fra i loro segmenti è al massimo `gap_tolerance` (a catena).
Nessuna nozione di nodo, grafo o chiusura — solo vicinanza, quindi non
eredita l'ambiguità della connettività che rompe il grafo sulle viste
proiettate.

Distanza vera, non fra bbox: la bbox di una diagonale lunga (vista
isometrica) copre un rettangolo vuoto che tocca le viste accanto.

Un gruppo è una vista o un pezzo candidato: quale delle due lo decide il
chiamante. Anche `gap_tolerance` è del chiamante: dipende da come è
impaginato il disegno, non dalla geometria. Un foro lontano dai lati resta
un gruppo a sé: che stia DENTRO un altro lo dice solo il contorno esterno,
non la vicinanza.

Puro: solo Edge e primitive, nessun formato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

import numpy as np
import shapely
import shapely.ops
from shapely import STRtree

from ..geometry.strips import refine_gap
from ..primitives.segments import DEFAULT_TOLERANCE
from ..topology.edge import Edge
from ..topology.graph import connected_groups
from ..topology.noding import edge_geometry

BBox = Tuple[float, float, float, float]   # xmin, ymin, xmax, ymax


@dataclass
class TouchingGroup:
    """Gruppo di Edge vicini, con la bbox che li contiene tutti."""
    edges:  List[Edge]   = field(default_factory=list)   # ordine di input
    bbox:   BBox         = (0.0, 0.0, 0.0, 0.0)

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def touching_groups(edges: Iterable[Edge], gap_tolerance: float) -> List[TouchingGroup]:
    """
    Union-find sulle coppie di Edge a distanza vera <= gap_tolerance
    (`_near_pairs`). Gruppi ordinati per area di bbox, decrescente.
    """
    edges = list(edges)
    if not edges:
        return []

    geoms = [edge_geometry(e) for e in edges]
    groups = connected_groups(len(edges), _near_pairs(edges, geoms, gap_tolerance))

    groups_out = []
    for members in groups:
        bounds = [geoms[i].bounds for i in members]
        groups_out.append(TouchingGroup(
            edges=[edges[i] for i in members],
            bbox=(min(b[0] for b in bounds), min(b[1] for b in bounds),
                  max(b[2] for b in bounds), max(b[3] for b in bounds)),
        ))
    groups_out.sort(key=lambda g: g.width * g.height, reverse=True)
    return groups_out


def _near_pairs(edges: List[Edge], geoms: list, gap_tolerance: float) -> List[Tuple[int, int]]:
    """Le coppie di edge a distanza vera <= `gap_tolerance`. Le
    discretizzazioni sbagliano fino a DEFAULT_TOLERANCE per curva, e il loro
    errore gira col disegno (D145): fuori dalla fascia di 2·DEFAULT_TOLERANCE
    attorno alla soglia decidono loro, dentro la distanza sulle primitive."""
    band = 2 * DEFAULT_TOLERANCE
    left, right = STRtree(geoms).query(geoms, predicate="dwithin", distance=gap_tolerance + band)
    keep = left < right
    left, right = left[keep], right[keep]
    measured = shapely.distance(np.array(geoms, dtype=object)[left], np.array(geoms, dtype=object)[right])
    pairs = []
    for i, j, d in zip(left.tolist(), right.tolist(), measured.tolist()):
        if d > gap_tolerance - band:
            pa, pb = shapely.ops.nearest_points(geoms[i], geoms[j])
            found = refine_gap([edges[i].segment], [edges[j].segment], (pa.x, pa.y), (pb.x, pb.y))
            if found.distance > gap_tolerance:
                continue
        pairs.append((i, j))
    return pairs


