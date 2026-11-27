"""
topo/core/geometry/__init__.py
-------------------------------
topo's geometry, in one place: `topo.geometry.<name>`.
Facts with geometric names - "circle", nothing more: what they mean is
decided by the consumer.

Public (below):
    build.py          build shapes and curves as segments: polygon, rectangle, regular_polygon, circle, ellipse,
                      stadium, triangle, right_triangle; blend, polynomial, involute, clothoid, clothoid_corner
    shape.py          shape of a closed contour
    concentric.py     concentric circles; arcs around a circle
    lines.py          a chord that splits a contour; runs of collinear strokes joined across contours; hatching of a segment
    regions.py        point on a contour (vertex, fillet, side); stroke cut by a region; contour minus region
    strips.py         distance between two boundaries and the closest pair (`gap`, `Gap`)
    axis.py           rectangles covered by strokes, lines that cross them, sides on another's edge, dimension on the axes;
                      strokes on the axes
    measure.py        length of a segment and how much of it lies in a box,
                      the vertices of an open trace
    lines.py          also: strokes grouped by line

Building blocks (imported from the submodule, internal):
    measure.py        a segment's reach in a direction, the longest segment, a threshold with its float margin (reach)
    numeric.py        golden-section search (maximum, minimum)
    shapely_polygons.py  the bridge to shapely: a contour as a Polygon
    points.py         point sequences: duplicates, spacing, Douglas-Peucker, circle fit
    spline_fit.py     b-spline through points / within a tolerance of them
    curve_tests.py    do the points lie on a chord, a circle, a conic, a smooth curve?
    corners.py        corners of a sampled sequence
    strips.py         a strip between two contours, an open contour where the strips cover it
                      (the facts on the hierarchy are in topo.tools.strips)
    intersections.py  line/line, circle/line, circle/circle
                      (public: `intersections(a, b)` between any two primitives)
    lines.py, axis.py also: distance from a line, collinearity, intervals, strokes inside a box
    measure.py        also: angle of a chord, length of a polyline
"""

from .build import (polygon, rectangle, regular_polygon, circle, ellipse, stadium, triangle, right_triangle,
                    blend, polynomial,
                    involute, clothoid, clothoid_corner)
from .shape import contour_shape, ContourShape, ShapeKind
from .concentric import (
    concentric_groups, ConcentricGroup,
    arcs_around, ArcAround,
)
from .lines import splits_contour, bridged_runs, CollinearRun, dash_line, group_collinear_lines
from .measure import (
    segment_length, length_inside,
    track_points,
)
from .regions import point_on_contour, ContourPoint, nearest_point, cut_by, contour_minus, contour_union
from .intersections import intersections
from .strips import gap, Gap
from .axis import (
    covered_rectangles, CoveredRectangle, spanning_lines, sides_on_border, axis_aligned_share,
    axis_lines, AxisLine,
)

__all__ = [
    "polygon", "rectangle", "regular_polygon", "circle", "ellipse", "stadium", "triangle", "right_triangle",
    "blend", "polynomial", "involute", "clothoid", "clothoid_corner",
    "contour_shape", "ContourShape", "ShapeKind",
    "concentric_groups", "ConcentricGroup",
    "arcs_around", "ArcAround",
    "splits_contour", "bridged_runs", "CollinearRun", "dash_line", "group_collinear_lines",
    "segment_length", "length_inside",
    "track_points",
    "point_on_contour", "ContourPoint", "nearest_point", "cut_by", "contour_minus", "contour_union", "intersections",
    "gap", "Gap",
    "covered_rectangles", "CoveredRectangle", "spanning_lines", "sides_on_border", "axis_aligned_share",
    "axis_lines", "AxisLine",
]
