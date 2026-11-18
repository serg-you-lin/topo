"""
topo/core/geometry/__init__.py
-------------------------------
topo's geometry, in one place: `topo.geometry.<name>` (MAP.md D95).
Facts with geometric names - "circle", never "hole": what they mean is
decided by the consumer.

Public (below):
    build.py          build shapes as segments: polygon, rectangle, regular_polygon, circle, ellipse, stadium
    shape.py          shape of a closed contour; concentric circles; arcs around a circle
    lines.py          a chord that splits a contour; runs of collinear strokes joined across contours; hatching of a segment
    regions.py        point on a contour (vertex, fillet, side); stroke cut by a region; contour minus region
    strips.py         distance between two boundaries and the closest pair (`gap`, `Gap`)
    axis.py           rectangles covered by strokes, lines that cross them, sides on another's edge, dimension on the axes;
                      strokes on the axes, strokes inside a box, merged intervals
    measure.py        length of a segment and how much of it lies in a box, angle of a chord,
                      open traces (vertices, length, "is it a straight stroke?")
    lines.py          also: strokes grouped by line

Building blocks (imported from the submodule, internal):
    measure.py        rounding of nodes, "is it circular?" (bounding box: for a measure use contour_shape)
    points.py         point sequences: corners, duplicates, circle fit, b-spline
    strips.py         a strip between two contours, an open contour where the strips cover it
                      (D142; the facts on the hierarchy are in topo.tools.strips)
    intersections.py  line/line, circle/line, circle/circle
                      (public: `intersections(a, b)` between any two primitives)
    lines.py, axis.py also: distance from a line, collinearity, intervals, strokes inside a box
"""

from .build import polygon, rectangle, regular_polygon, circle, ellipse, stadium
from .shape import (
    contour_shape, ContourShape, ShapeKind,
    concentric_groups, ConcentricGroup,
    arcs_around, ArcAround,
)
from .lines import splits_contour, bridged_runs, CollinearRun, dash_line, group_collinear_lines
from .measure import (
    segment_length, length_inside, chord_angle_deg,
    track_points, track_length,
)
from .regions import point_on_contour, ContourPoint, nearest_point, cut_by, contour_minus, contour_union
from .intersections import intersections
from .strips import gap, Gap
from .axis import (
    covered_rectangles, CoveredRectangle, spanning_lines, sides_on_border, axis_aligned_share,
    axis_lines, AxisLine, items_inside, merge_intervals,
)

__all__ = [
    "polygon", "rectangle", "regular_polygon", "circle", "ellipse", "stadium",
    "contour_shape", "ContourShape", "ShapeKind",
    "concentric_groups", "ConcentricGroup",
    "arcs_around", "ArcAround",
    "splits_contour", "bridged_runs", "CollinearRun", "dash_line", "group_collinear_lines",
    "segment_length", "length_inside", "chord_angle_deg",
    "track_points", "track_length",
    "point_on_contour", "ContourPoint", "nearest_point", "cut_by", "contour_minus", "contour_union", "intersections",
    "gap", "Gap",
    "covered_rectangles", "CoveredRectangle", "spanning_lines", "sides_on_border", "axis_aligned_share",
    "axis_lines", "AxisLine", "items_inside", "merge_intervals",
]
