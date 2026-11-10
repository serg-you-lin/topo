"""
03_open_a_dxf.py — open a drawing, see what topo understood, write what it read
===============================================================================

What you learn
    topo_dxf.load_dxf          DXF -> Document: edges (topo's own segments) and texts
    doc.warnings / doc.notes   what to look at in the file / what the loader did by itself
    topo.validate_document     a check of the input before heal(); changes nothing
    result.is_valid            check it before you hand the output to a machine
    topo_dxf.to_dxf(..., allow_invalid=False)   refuse to write an invalid result

After load_dxf the DXF is gone: topo works on its own primitives (LineSeg,
ArcSeg, CircleSeg, EllipseSeg, BSplineSeg). A source layer is not kept; lesson 09
shows how to turn a layer name into a role.

Input
    INPUT = a drawing in tutorial/files; put the path of your own DXF here.

Open afterwards
    the original next to tutorial_output/03_open_a_dxf/<name>_read.dxf
"""
import _paths  # noqa: F401

from collections import Counter
from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/plate.dxf"
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
kinds = Counter(type(edge.segment).__name__ for edge in doc.edges)
print(f"{INPUT}: format {doc.source_format}")
print(f"  {len(doc.edges)} edges: {dict(kinds)}")
for text in doc.texts:
    print(f"  text {text.text!r} at ({text.position[0]:.1f}, {text.position[1]:.1f}), height {text.height}")
for message in doc.warnings + doc.notes:
    print(message)

check = topo.validate_document(doc)
print(f"\nvalidate_document: {len(check.warnings)} warning(s), {len(check.errors)} error(s)")

result = topo.heal(doc).faces()
print(f"faces(): valid={result.is_valid}, {len(result.clusters)} part(s), {len(result.loose)} loose curve(s)")

path = _paths.out("03_open_a_dxf") / f"{Path(INPUT).stem}_read.dxf"
if result.is_valid:
    topo_dxf.to_dxf(result, doc, allow_invalid=False).saveas(path)
    print(f"written {path}")
else:
    print("not written: the result is not valid, read the errors above")
    for error in result.errors:
        print(error)
