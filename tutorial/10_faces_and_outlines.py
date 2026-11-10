"""
10_faces_and_outlines.py — two readings of the same repaired drawing
====================================================================

What you learn
    network = topo.heal(doc, max_gap=...)   the drawing repaired once
    network.faces()      every closed region, each inside the one that contains it
    network.outlines()   the outer border of each group of lines that touch;
                         what lies inside it goes to `loose`, uninterpreted

Both read the same network; they are two readings, never two steps: do not feed
the output of one to the other. Which one fits is a question about your
geometry: do you want every region a set of lines closes, or the border around
everything that is connected?

isometric.dxf is an isometric view of a solid: the two readings give very
different counts there; open both files and see which regions each one found.
sheet_of_parts.dxf is separate flat parts: both find the same four, faces()
with the holes in `inners`, outlines() with them in `loose`.

Open afterwards
    tutorial_output/10_faces_and_outlines/<name>_faces.dxf and <name>_outlines.dxf,
    side by side for each file in INPUTS.

Your own file
    add its path to INPUTS; set MAX_GAP to the widest gap your drawing should close.
"""
import _paths  # noqa: F401

from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUTS = [r"tutorial/files/isometric.dxf", r"tutorial/files/sheet_of_parts.dxf"]
MAX_GAP = 0.5
# -----------------------------------------------------------------------------

for path in INPUTS:
    doc = topo_dxf.load_dxf(path)
    network = topo.heal(doc, max_gap=MAX_GAP)
    print(f"{path}: {len(doc.edges)} edges")
    for reading in ("faces", "outlines"):
        result = getattr(network, reading)()
        inners = sum(len(c.inners) for c in result.clusters)
        print(f"  {reading:9s} valid={result.is_valid}  {len(result.clusters):3d} part(s)  "
              f"{inners:3d} inner(s)  {len(result.loose):4d} loose curve(s)")
        out = _paths.out("10_faces_and_outlines") / f"{Path(path).stem}_{reading}.dxf"
        topo_dxf.to_dxf(result, doc).saveas(out)
    print()
print(f"written {_paths.out('10_faces_and_outlines')}")
