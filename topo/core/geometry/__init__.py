"""
topo/core/geometry/__init__.py
-------------------------------
La geometria di topo, un posto solo: `topo.geometry.<nome>` (MAP.md D95).
Fatti con nomi geometrici — "cerchio", mai "foro": cosa significano lo
decide il consumatore.

Pubblici (qui sotto):
    build.py          costruire forme come segmenti: polygon, rectangle, regular_polygon, circle, ellipse, stadium
    shape.py          forma di un contorno chiuso; cerchi concentrici; archi attorno a un cerchio
    lines.py          una corda che divide un poligono; file di tratti collineari unite attraverso dei poligoni; tratteggio di un segmento
    regions.py        punto su un contorno (vertice, raccordo, lato); tratto tagliato da una regione; contorno meno regione
    axis.py           rettangoli coperti da tratti, linee che li attraversano, lati sul bordo di un altro, quota sugli assi;
                      tratti sugli assi, tratti dentro un riquadro, intervalli uniti
    measure.py        lunghezza di un segmento e quanta ne sta in un riquadro, angolo di una corda,
                      tracce aperte (vertici, lunghezza, "è un tratto dritto?")
    lines.py          anche: tratti raggruppati per retta

Mattoni (si importano dal sottomodulo, interni):
    measure.py        arrotondamento dei nodi, "è circolare?" (bounding box: per una misura usa contour_shape)
    points.py         sequenze di punti: spigoli, doppioni, fit di cerchio, b-spline
    strips.py         una striscia fra due contorni, distanza fra due contorni, un contorno aperto
                      dove le strisce lo coprono (D142; i fatti sulla gerarchia in topo.tools.strips)
    intersections.py  retta/retta, cerchio/retta, cerchio/cerchio
                      (pubblica: `intersections(a, b)` fra due primitive qualunque)
    lines.py, axis.py anche: distanza da una retta, collinearità, intervalli, tratti dentro un riquadro
"""

from .build import polygon, rectangle, regular_polygon, circle, ellipse, stadium
from .shape import (
    contour_shape, ContourShape, ShapeKind,
    concentric_groups, ConcentricGroup,
    arcs_around, ArcAround,
)
from .lines import splits_polygon, bridged_runs, CollinearRun, dash_line, group_collinear_lines
from .measure import (
    segment_length, length_inside, chord_angle_deg,
    track_points, track_length, track_shape_type,
)
from .regions import point_on_contour, ContourPoint, nearest_point, cut_by, contour_minus
from .intersections import intersections
from .axis import (
    covered_rectangles, CoveredRectangle, spanning_lines, sides_on_border, axis_aligned_share,
    axis_lines, AxisLine, items_inside, merge_intervals,
)

__all__ = [
    "polygon", "rectangle", "regular_polygon", "circle", "ellipse", "stadium",
    "contour_shape", "ContourShape", "ShapeKind",
    "concentric_groups", "ConcentricGroup",
    "arcs_around", "ArcAround",
    "splits_polygon", "bridged_runs", "CollinearRun", "dash_line", "group_collinear_lines",
    "segment_length", "length_inside", "chord_angle_deg",
    "track_points", "track_length", "track_shape_type",
    "point_on_contour", "ContourPoint", "nearest_point", "cut_by", "contour_minus", "intersections",
    "covered_rectangles", "CoveredRectangle", "spanning_lines", "sides_on_border", "axis_aligned_share",
    "axis_lines", "AxisLine", "items_inside", "merge_intervals",
]
