"""
model/curve.py

Gerarchia base del dominio topo: una curva è una sequenza di segmenti,
chiusa o aperta. Nome geometrico, non di processo (MAP.md D114).

Curve
├── ClosedCurve   — contorno chiuso (loop): i segments chiudono un giro
└── OpenCurve     — tracciato aperto

Tutte le entità del modello ereditano da qui:
    Hole(ClosedCurve), Contour(ClosedCurve)
    BendingLine(OpenCurve), Engraving(OpenCurve)

Note:
    - segments è List[LineSeg | ArcSeg | BSplineSeg] — primitive pure, zero ezdxf
    - styles è List[EdgeStyle], allineata 1:1 a segments — aspetto grezzo
      (linetype/colore) dell'entità sorgente di ogni segmento (Cluster E).
      Può essere più corta di segments o vuota (geometria sintetizzata, es.
      ponti di gap-closing o il fallback polygonize): chi la consuma in
      write() tratta un indice mancante come "nessuno stile noto".
    - nessun tipo shapely nel modello (D166): il poligono per le domande fra
      più curve è una cache privata, `core.primitives.polygon_builder.curve_polygon`
    - role è l'unico canale semantico interno — mai leggere layer DXF nel core
"""

from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Any, List, Optional, Tuple

from topo.core.geometry.integrals import ring_area, ring_centroid
from topo.core.geometry.rings import ON_BOUNDARY, ring_bbox, ring_contains, ring_points
from topo.core.primitives.segments import ArcSeg, LineSeg, BSplineSeg, DEFAULT_TOLERANCE
from topo.model.style import EdgeStyle


@dataclass
class Curve:
    """
    Radice della gerarchia. Porta solo identità semantica e traceability.

    Non istanziare direttamente — usare ClosedCurve o OpenCurve.
    """
    role:       str          # costante ContourRole, o slug di un consumatore


@dataclass
class ClosedCurve(Curve):
    """
    Curva chiusa: una lista di segmenti che chiude un giro. I suoi fatti
    (area, bbox, baricentro, contains) sono calcolati sui segmenti (D166).

    Non porta `diameter` / `center`: la geometria circolare di un contorno è
    ricavata al bisogno da `core.geometry.measure.circular_geometry()` e stoccata
    sull'oggetto `Hole` da `detect_flat()` (D15), non sul contorno grezzo.
    """
    segments: List[LineSeg | ArcSeg | BSplineSeg] = field(default_factory=list)
    _: KW_ONLY
    styles:   List[EdgeStyle]                  = field(default_factory=list)
    cluster_ref: Optional[int]                 = None   # in result.loose: indice del cluster che la contiene (D137)
    # poligono della lettura, solo per le domande fra più curve (curve_polygon, D166)
    _polygon:    Any = field(default=None, init=False, repr=False, compare=False)

    @property
    def area(self) -> float:
        """Area esatta, integrata sui `segments` (Green, MAP.md D165): non
        dipende dalla tolleranza della discretizzazione."""
        return ring_area(self.segments) if self.segments else 0.0

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Exact (xmin, ymin, xmax, ymax) of the `segments`: arcs and ellipses
        reach their true extremes, not their chords (MAP.md D166)."""
        return ring_bbox(self.segments) if self.segments else (0.0, 0.0, 0.0, 0.0)

    @property
    def centroid(self) -> Tuple[float, float]:
        """Exact centroid of the enclosed area, integrated on the `segments`
        (Green, MAP.md D165). `ValueError` if the ring encloses no area."""
        return ring_centroid(self.segments)

    def contains(self, point: Tuple[float, float], *, tolerance: float = ON_BOUNDARY) -> bool:
        """True if `point` lies in the closed region: inside, or on the
        boundary within `tolerance`. Computed on the `segments`."""
        return ring_contains(self.segments, point, tolerance)

    def points(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Tuple[float, float]]:
        """The ring discretized within `tolerance`, as plain (x, y) tuples in
        order; the first point is not repeated at the end."""
        return ring_points(self.segments, tolerance)


@dataclass
class OpenCurve(Curve):
    """
    Curva aperta: segmenti che non chiudono un giro.
    """
    segments:    List[LineSeg | ArcSeg | BSplineSeg] = field(default_factory=list)
    _: KW_ONLY
    styles:      List[EdgeStyle]                  = field(default_factory=list)
    cluster_ref: Optional[int]                    = None   # in result.loose: indice del cluster che la contiene (D99, D137)