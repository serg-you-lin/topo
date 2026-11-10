"""
13_your_drawings.py — every drawing in a folder, repaired, with a report
========================================================================

What you learn
    the whole path on many files: load_dxf -> heal -> faces() or outlines() -> to_dxf
    topo.experimental.save_svg   a picture of the result for any browser (experimental)

Point FOLDER at your own drawings. For each DXF the lesson writes, in
tutorial_output/13_your_drawings/:
    <name>_read.dxf   what topo read, to open next to your original
    <name>.svg        the same as a picture
    report.txt        one block per file: parts, loose curves, every message

A file that makes topo fail becomes a line in the report and the others go on.
If a result looks wrong to you, the report and that drawing are what we need
to fix it (send only drawings you are allowed to share).
"""
import _paths  # noqa: F401

import traceback
from pathlib import Path

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
FOLDER = r"tutorial/files"
READING = "faces"          # "faces" or "outlines" (lesson 10)
MAX_GAP = None             # None = the tolerance; e.g. 0.5 closes gaps up to 0.5 mm (lesson 06)
# -----------------------------------------------------------------------------

out = _paths.out("13_your_drawings")
lines = [f"folder {Path(FOLDER).resolve()}  reading {READING}  max_gap {MAX_GAP}", ""]
for path in sorted(Path(FOLDER).glob("*.dxf")):
    try:
        doc = topo_dxf.load_dxf(path)
        result = getattr(topo.heal(doc, max_gap=MAX_GAP), READING)()
        topo_dxf.to_dxf(result, doc).saveas(out / f"{path.stem}_read.dxf")
        topo.experimental.save_svg(result, str(out / f"{path.stem}.svg"))
        inners = sum(len(c.inners) for c in result.clusters)
        summary = (f"{path.name}: valid={result.is_valid}, {len(result.clusters)} part(s), "
                   f"{inners} inner(s), {len(result.loose)} loose curve(s)")
        lines.append(summary)
        for message in doc.warnings + doc.notes + result.errors + result.warnings:
            lines.append(f"    {message.level} {message.code}: {message.message}")
    except Exception:
        summary = f"{path.name}: FAILED"
        lines.append(summary)
        lines += ["    " + row for row in traceback.format_exc().splitlines()]
    print(summary)

report = out / "report.txt"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nwritten {out}")
