"""
01_build_a_part.py — draw a part in code, let topo read it
==========================================================

What you learn
    topo.geometry.rectangle / circle / stadium   closed shapes as topo segments
    topo.load_segments                           segments -> Document (no file needed)
    topo.heal(doc).faces()                       Document -> Result: parts, outer and inner contours
    topo_dxf.to_dxf                              Result -> a new DXF

A Document is the drawing as topo received it: edges, no topology. heal()
repairs it once and gives a Network; faces() reads the network as closed
contours, each inside the one that contains it. A Cluster is one part: its
`outer` contour and the `inners` inside it.

Open afterwards
    tutorial_output/01_build_a_part/part.dxf
    the outer contour is on layer OuterContour, the three inner ones on InnerContour.

Try this
    move the circle so it overlaps the plate border, run again, and read what
    topo says about it.
"""
import _paths  # noqa: F401

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
PLATE = (200, 100)                  # length, width in mm
CIRCLE_CENTER = (-60, 0)
# -----------------------------------------------------------------------------

segments = (topo.geometry.rectangle(*PLATE)
            + topo.geometry.circle(10, center=CIRCLE_CENTER)
            + topo.geometry.stadium(60, 20, center=(30, 20))
            + topo.geometry.regular_polygon(6, 12, center=(30, -25)))

doc = topo.load_segments(segments)
print(f"Document: {len(doc.edges)} edges, {len(doc.texts)} texts")

result = topo.heal(doc).faces()
print(f"Result:   valid={result.is_valid}, {len(result.clusters)} part(s), {len(result.loose)} loose curve(s)")
for problem in result.warnings + result.errors:
    print(problem)

for cluster in result.clusters:
    print(f"  part {cluster.label!r}: outer area {cluster.outer.area:.1f} mm², {len(cluster.inners)} inner contour(s)")
    for inner in cluster.inners:
        print(f"    inner: area {inner.area:8.1f} mm², {len(inner.segments)} segment(s): "
              f"{sorted({type(s).__name__ for s in inner.segments})}")

path = _paths.out("01_build_a_part") / "part.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"\nwritten {path}")
