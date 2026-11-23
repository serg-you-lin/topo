"""
topo_pdf/geometry_adapter.py
---------------------------------
Mathematical and geometric functions for the conversion of PDF data.

It handles the pt -> mm scale, the Y-axis flip and the approximation of Bezier
curves as line segments."""

# CONVERSION FACTOR: from PDF points (pt) to millimetres (mm)
# 1 inch = 72 points = 25.4 mm -> 25.4 / 72
PT_TO_MM = 25.4 / 72.0


def transform_point(x: float, y: float, page_height: float) -> tuple[float, float]:
    """Convert a point from PDF points (pt) to millimetres (mm) and flip the Y axis
    to bring it into the standard Cartesian system (origin at the bottom left)."""
    x_mm = x * PT_TO_MM
    y_mm = (page_height - y) * PT_TO_MM
    return (x_mm, y_mm)


def sample_bezier_cubic(p1: tuple, p2: tuple, p3: tuple, p4: tuple, num_segments: int = 16) -> list[tuple[float, float]]:
    """Sample a cubic Bezier curve into a set of linear points (a polyline).

    Parameters:
        p1: Start point (x, y) in mm
        p2: First control point (x, y) in mm
        p3: Second control point (x, y) in mm
        p4: End point (x, y) in mm
        num_segments: Number of segments to divide the curve into (default 16)"""
    points = []
    for i in range(num_segments + 1):
        t = i / float(num_segments)
        
        # cubic Bezier polynomial formula
        c_1 = (1 - t) ** 3
        c_2 = 3 * ((1 - t) ** 2) * t
        c_3 = 3 * (1 - t) * (t ** 2)
        c_4 = t ** 3
        
        x = c_1 * p1[0] + c_2 * p2[0] + c_3 * p3[0] + c_4 * p4[0]
        y = c_1 * p1[1] + c_2 * p2[1] + c_3 * p3[1] + c_4 * p4[1]
        
        points.append((x, y))
        
    return points