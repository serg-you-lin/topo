"""
11_geometry_facts.py — the geometry toolbox
===========================================

What you learn
    topo.geometry.intersections(a, b)        where two segments meet
    topo.geometry.nearest_point(ring, p)     the point of a ring closest to p
    topo.geometry.cut_by(segment, region)    the pieces of a segment outside (or inside) a closed region
    topo.geometry.contour_minus(a, b)        ring a with ring b taken away
    topo.geometry.contour_union(a, b)        the two rings joined
    topo.geometry.concentric_groups(items)   circles that share a centre

Each fact works on topo's own segments, exact on lines and arcs: no
discretization, no shapely. Everything here is built in code; the shapes and
the answers are written to one DXF, one layer per fact.

Open afterwards
    tutorial_output/11_geometry_facts/facts.dxf: turn on one layer at a time.
"""
import _paths  # noqa: F401

import topo
import topo_dxf
from topo.primitives import LineSeg

g = topo.geometry
plate = g.rectangle(80, 40)
hole = g.circle(12, center=(40, 0))                     # sits across the right side of the plate
line = LineSeg((-60, 0), (60, 0))

print("intersections of the line with the circle:", g.intersections(line, hole[0]))
print("point of the plate closest to (70, 35):   ", g.nearest_point(plate, (70, 35)))

outside = g.cut_by(line, hole, keep="outside")
print(f"the line outside the circle: {len(outside)} piece(s)")

minus = g.contour_minus(plate, hole)
union = g.contour_union(plate, hole)
print(f"plate minus circle: {len(minus)} ring(s) of {[type(s).__name__ for s in minus[0]]}")
print(f"plate plus circle:  {len(union)} ring(s) of {len(union[0])} segment(s)")

rings = [g.circle(5), g.circle(9), g.circle(4, center=(-25, 10)), g.circle(7, center=(-25, 10))]
for group in g.concentric_groups(rings):
    print(f"concentric group at {group.center}: radii {[s.length / 2 for s in group.shapes]}")

# un layer per fatto: i ruoli sono solo nomi di layer qui
doc = topo.load_segments(plate + hole + [line], role="shapes")
for role, segments in (("cut_by_outside", outside), ("plate_minus_circle", minus[0]),
                       ("plate_plus_circle", union[0]), ("concentric", [s for r in rings for s in r])):
    doc.edges += topo.load_segments(segments, role=role).edges

result = topo.heal(doc).faces()
path = _paths.out("11_geometry_facts") / "facts.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"\nwritten {path}")
