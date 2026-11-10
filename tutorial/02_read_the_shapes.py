"""
02_read_the_shapes.py — ask the model, don't parse an export
============================================================

What you learn
    Contour.area / .centroid / .bbox / .depth   facts computed on the exact segments
    topo.geometry.contour_shape                 which simple shape a contour is (circle, stadium, polygon...)
    topo.to_shapely                             the explicit door to shapely, when you need it

contour_shape reports the same numbers the builders of lesson 01 take, so a
shape you build is a shape you read back. `depth` counts nesting: 0 is a part's
outer, 1 a contour inside it, 2 a contour inside that one, and so on.

Input
    INPUT = the plate drawing in tutorial/files; put the path of your own DXF here.
"""
import _paths  # noqa: F401

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/plate.dxf"
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
result = topo.heal(doc).faces()
print(f"{INPUT}: valid={result.is_valid}, {len(result.clusters)} part(s)\n")

for i, cluster in enumerate(result.clusters):
    print(f"part {i}")
    for contour in [cluster.outer] + cluster.inners:
        shape = topo.geometry.contour_shape(contour)
        kind = shape.kind.value if shape else "free form"
        cx, cy = contour.centroid
        print(f"  depth {contour.depth}  {kind:10s} area {contour.area:9.2f} mm²  centroid ({cx:7.2f}, {cy:7.2f})", end="")
        if shape:
            angle = "-" if shape.angle is None else f"{shape.angle:.1f}°"
            print(f"  length {shape.length:.2f} width {shape.width:.2f} angle {angle}")
        else:
            print()

    polygon = topo.to_shapely(cluster)
    print(f"  as shapely: {polygon.geom_type}, area {polygon.area:.2f} mm² (the outer minus its inners)\n")
