"""
08_split_into_pieces.py — several figures in one file, one file each
====================================================================

What you learn
    topo.anchor_texts(result)    which cluster each text belongs to (by containment)
    topo.split(result)           one Result per cluster, plus what no cluster contains; no file format involved
    topo.save_json(..., extra=)  the facts of each cluster as JSON, with your own fields added (a key topo already writes is refused)

separate_figures.dxf holds four separate figures, each with a letter written inside it. The
letter becomes the piece's name, and each piece is written to its own DXF.
split() refuses an invalid result: check is_valid first. It decides nothing:
a text or a curve no cluster contains comes back in outcome.texts / outcome.loose,
and the loop below gives it to the nearest piece (your call: to all, or to none).

Open afterwards
    tutorial_output/08_split_into_pieces/: A.dxf ... D.dxf, and pieces.json.

Your own file
    set INPUT; a piece with no text inside is named piece_<n>.
"""
import _paths  # noqa: F401

import math

import topo
import topo_dxf

# --- CONFIG ------------------------------------------------------------------
INPUT = r"tutorial/files/separate_figures.dxf"
# -----------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
result = topo.heal(doc).faces()
print(f"{INPUT}: valid={result.is_valid}, {len(result.clusters)} cluster(s), {len(result.texts)} text(s)")
if not result.is_valid:
    raise SystemExit([str(e) for e in result.errors])

topo.anchor_texts(result)
names = {}
for text in result.texts:
    print(f"  text {text.text!r} -> cluster {text.cluster_ref}")
    if text.cluster_ref is not None:
        names[text.cluster_ref] = text.text


outcome = topo.split(result)
for text in outcome.texts:
    nearest = min(range(len(outcome.pieces)), key=lambda i: math.dist(
        text.position, topo.geometry.nearest_point(outcome.pieces[i].clusters[0].outer.segments, text.position)))
    print(f"  text {text.text!r} is in no cluster: given to piece {nearest}")
    outcome.pieces[nearest].texts.append(text)

folder = _paths.out("08_split_into_pieces")
for index, piece in enumerate(outcome.pieces):
    cluster = piece.clusters[0]
    path = folder / f"{names.get(index, 'piece_' + str(index + 1))}.dxf"
    topo_dxf.to_dxf(piece).saveas(path)
    print(f"  piece {index}: area {cluster.outer.area:8.1f} mm², {len(cluster.inners)} inner(s) -> {path.name}")

topo.save_json(result, folder / "pieces.json", extra=lambda cluster: {"checked_by": "me"})
print(f"written {folder}")
