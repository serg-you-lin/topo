"""
04_z_levels.py — a drawing with heights: topo reads it on the plane
===================================================================

What you learn
    load_dxf(flatten_z=True)   (the default) a 3D DXF is brought onto the XY plane
    the note dxf-flattened     how many entities had a Z different from 0
    topo.name_rules            keep each source layer as a role, so the output has the same layers

topo is 2D. A DXF can carry heights: a line climbing in Z, a polyline at an
elevation, a circle drawn on a plane that is not XY, a 3D spline. What topo
should keep of each is its projection seen from above (the XY plane).

The file z_levels.dxf has one case per layer. LAYERS below lists them, so each
comes out on a layer with the same name.

Open afterwards
    tutorial/files/z_levels.dxf next to tutorial_output/04_z_levels/z_levels_read.dxf,
    both seen from above (plan view). Turn on one layer at a time and compare: the
    projection of each original entity should lie on what topo read.

Your own file
    set INPUT, and list in LAYERS the layer names you want to compare one by one
    (an empty list puts everything on topo's default layers).
"""
import _paths  # noqa: F401

from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/z_levels.dxf"
LAYERS = [
    "line_sloped", "lines_z12", "polyline_elevation20", "polyline2d_elevation9", "polyline_3d",
    "spline_3d", "circle_z7", "circle_upside_down", "arc_upside_down", "circle_tilted45",
    "arc_tilted45", "ellipse_z5", "ellipse_axis_tilted",
]
# -----------------------------------------------------------------------------

rules = topo.name_rules({name: name for name in LAYERS})
doc = topo_dxf.load_dxf(INPUT, role_rules=rules)
for message in doc.notes + doc.warnings:
    print(message)

print(f"\n{len(doc.edges)} edges read; per layer, what topo holds:")
for name in LAYERS or ["unknown"]:
    role = topo.normalize_role(name)
    for edge in (e for e in doc.edges if e.role == role):
        print(f"  {name:24s} {edge.segment}")

result = topo.heal(doc).faces()
path = _paths.out("04_z_levels") / f"{Path(INPUT).stem}_read.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"\nwritten {path}")
