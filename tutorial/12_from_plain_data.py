"""
12_from_plain_data.py — geometry from any source, as plain dicts
================================================================

What you learn
    topo.load_geometry(entities)   a list of dicts -> Document, no file and no DXF

When the geometry comes from somewhere that is not a DXF (a database, a web
form, another program), describe it as dicts and topo reads it like any drawing.
Types: line, arc, circle, polygon, spline, ellipse. Arc angles are in degrees.
An optional `role` per entity works as in lesson 09.

Open afterwards
    tutorial_output/12_from_plain_data/from_dicts.dxf
"""
import _paths  # noqa: F401

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
ENTITIES = [
    {"type": "line", "start": (0, 0), "end": (100, 0)},
    {"type": "line", "start": (100, 0), "end": (100, 40)},
    {"type": "arc", "center": (80, 40), "radius": 20, "start_angle": 0, "end_angle": 90, "ccw": True},
    {"type": "line", "start": (80, 60), "end": (0, 60)},
    {"type": "line", "start": (0, 60), "end": (0, 0)},
    {"type": "circle", "center": (25, 30), "radius": 8},
    {"type": "polygon", "points": [(50, 20), (70, 20), (60, 40)]},
    {"type": "ellipse", "center": (80, 15), "major_axis": (8, 0), "ratio": 0.5},
    {"type": "line", "start": (-10, 30), "end": (110, 30), "role": "axis"},
]
# -----------------------------------------------------------------------------

doc = topo.load_geometry(ENTITIES)
print(f"{len(doc.edges)} edges, format {doc.source_format}")
result = topo.heal(doc).faces()
print(f"valid={result.is_valid}, {len(result.clusters)} part(s)")
for cluster in result.clusters:
    for contour in [cluster.outer] + cluster.inners:
        shape = topo.geometry.contour_shape(contour)
        print(f"  depth {contour.depth}: {shape.kind.value if shape else 'free form':10s} area {contour.area:8.1f} mm²")
print(f"loose: {[curve.role for curve in result.loose]}")
for message in result.warnings:
    print(f"  {message.level} {message.code}: {message.message}")

path = _paths.out("12_from_plain_data") / "from_dicts.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"written {path}")
