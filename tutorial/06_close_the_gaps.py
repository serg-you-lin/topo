"""
06_close_the_gaps.py — tolerance and max_gap, two numbers
=========================================================

What you learn
    heal(doc)                  closes nothing wider than the tolerance (0.05 mm by default)
    heal(doc, max_gap=0.5)     ends closer than 0.5 mm are joined, the gaps between them closed
    network.free_ends          the ends that found no partner
    result.loose               every curve that is no part's contour: nothing is dropped silently

gaps.dxf holds a rectangle whose four corners are open by 0.3 mm, a circle cut
in four arcs with 0.2 mm between them, and one whole circle. The lesson reads
it twice, once per value in MAX_GAPS, and writes one DXF for each.

`tolerance` decides when two ends are the same point; `max_gap` decides how
wide a hole in the drawing topo may close. The notes say what topo did by
itself; compare them with what you see in the two files.

Open afterwards
    tutorial/files/gaps.dxf, then tutorial_output/06_close_the_gaps/gaps_max_gap_*.dxf.
    With the default only the whole circle is a contour, the rest is on Trash;
    with 0.5 the rectangle is the part and both circles are inside it.

Your own file
    set INPUT, and try your own values in MAX_GAPS.
"""
import _paths  # noqa: F401

from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/gaps.dxf"
MAX_GAPS = [None, 0.5]          # None = the default (the tolerance)
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
for max_gap in MAX_GAPS:
    network = topo.heal(doc, max_gap=max_gap)
    result = network.faces()
    print(f"max_gap={network.max_gap}  (tolerance {network.tolerance})")
    print(f"  {len(network.free_ends)} free end(s) left")
    print(f"  valid={result.is_valid}, {len(result.clusters)} part(s), "
          f"inners per part {[len(c.inners) for c in result.clusters]}, {len(result.loose)} loose curve(s)")
    for message in result.warnings + result.errors:
        print(f"  {message.level} {message.code}: {message.message}")
    notes = sorted({n.code for n in result.notes})
    print(f"  notes: {notes}")

    name = "default" if max_gap is None else str(max_gap)
    path = _paths.out("06_close_the_gaps") / f"{Path(INPUT).stem}_max_gap_{name}.dxf"
    topo_dxf.to_dxf(result, doc).saveas(path)
    print(f"  written {path}\n")
