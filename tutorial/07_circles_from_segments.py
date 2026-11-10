"""
07_circles_from_segments.py — when many short lines are a circle
================================================================

What you learn
    heal() rebuilds a circle drawn as many short lines, if the ring stays within
    0.02 mm of one circle all the way round; otherwise it keeps the lines.

circles_from_segments.dxf holds three circles of radius 10, made of 24, 72 and
180 short lines (the number is written under each). How far a ring of n lines
strays from its circle is r * (1 - cos(pi / n)):

    24 lines   0.086 mm   more than 0.02: stays a 24-sided polygon
    72 lines   0.0095 mm  a circle
    180 lines  0.0015 mm  a circle

Open afterwards
    tutorial_output/07_circles_from_segments/<name>_read.dxf: click each inner
    contour in your CAD and see whether it is one CIRCLE or many LINEs.

Your own file
    set INPUT to a drawing exported with circles turned into lines.
"""
import _paths  # noqa: F401

import math
from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/circles_from_segments.dxf"
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
print(f"{INPUT}: {len(doc.edges)} edges in the file")

result = topo.heal(doc).faces()
for cluster in result.clusters:
    for inner in sorted(cluster.inners, key=lambda c: c.centroid[0]):
        kinds = sorted({type(s).__name__ for s in inner.segments})
        shape = topo.geometry.contour_shape(inner)
        print(f"  inner at x={inner.centroid[0]:6.1f}: {len(inner.segments):3d} segment(s) {kinds}, "
              f"read as {shape.kind.value if shape else 'free form'}")

print("\nhow far a ring of n lines strays from a circle of radius 10:")
for n in (24, 72, 180):
    print(f"  n={n:3d}: {10 * (1 - math.cos(math.pi / n)):.4f} mm")

path = _paths.out("07_circles_from_segments") / f"{Path(INPUT).stem}_read.dxf"
topo_dxf.to_dxf(result, doc).saveas(path)
print(f"\nwritten {path}")
