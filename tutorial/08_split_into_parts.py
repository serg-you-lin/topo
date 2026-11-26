"""
08_split_into_parts.py — one sheet, several parts, one file each
================================================================

What you learn
    topo.anchor_texts(result)    which part each text belongs to (by containment)
    topo.split(result)           one Result per part, plus what no part contains; no file format involved
    topo.save_json(..., extra=)  the facts of each part as JSON, with your own fields added (a key topo already writes is refused)

sheet_of_parts.dxf holds four parts, each with a letter written inside it. The
letter becomes the part's name, and each part is written to its own DXF.
split() refuses an invalid result: check is_valid first. It decides nothing:
a text or a curve no part contains comes back in outcome.texts / outcome.loose,
and the loop below gives it to the nearest part (your call: to all, or to none).

Open afterwards
    tutorial_output/08_split_into_parts/: A.dxf ... D.dxf, and parts.json.

Your own file
    set INPUT; a part with no text inside is named part_<n>.
"""
import _paths  # noqa: F401

import math

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/sheet_of_parts.dxf"
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
result = topo.heal(doc).faces()
print(f"{INPUT}: valid={result.is_valid}, {len(result.clusters)} part(s), {len(result.texts)} text(s)")
if not result.is_valid:
    raise SystemExit([str(e) for e in result.errors])

topo.anchor_texts(result)
names = {}
for text in result.texts:
    print(f"  text {text.text!r} -> part {text.cluster_ref}")
    if text.cluster_ref is not None:
        names[text.cluster_ref] = text.text


outcome = topo.split(result)
for text in outcome.texts:
    nearest = min(outcome.parts, key=lambda p: math.dist(
        text.position, topo.geometry.nearest_point(p.clusters[0].outer.segments, text.position)))
    print(f"  text {text.text!r} is in no part: given to {nearest.clusters[0].label}")
    nearest.texts.append(text)

folder = _paths.out("08_split_into_parts")
for index, part in enumerate(outcome.parts):
    cluster = part.clusters[0]
    path = folder / f"{names.get(index, 'part_' + str(index + 1))}.dxf"
    topo_dxf.to_dxf(part).saveas(path)
    print(f"  {cluster.label}: area {cluster.outer.area:8.1f} mm², {len(cluster.inners)} inner(s) -> {path.name}")

topo.save_json(result, folder / "parts.json", extra=lambda cluster: {"checked_by": "me"})
print(f"written {folder}")
