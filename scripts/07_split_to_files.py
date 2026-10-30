"""
07_split_to_files.py — pipeline multi-pezzo completa su disco
============================================================

API topo usate:
    heal -> split -> to_dxf(...).saveas() per parte: quattro righe del
    chiamante (la vecchia `split_to_files` le faceva in una, D176).

Nome file: f"{cluster.label}.dxf" dove cluster.label = namer(i, cluster),
senza namer f"{label}_P{i+1}".

    python 07_split_to_files.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import topo
import topo_dxf

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/golden/example_4_polylines.dxf"
TOLERANCE = 0.5
OUTDIR    = "pipeline_output/batch_demo"
LABEL     = "P-1024"
# -------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT, tolerance=TOLERANCE)

import os

result = topo.heal(doc, label=LABEL, source_file=INPUT)
os.makedirs(OUTDIR, exist_ok=True)
parts = topo.split(result, namer=lambda i, cluster: f"{LABEL}_P{i + 1}", min_area=50.0)
for part in parts:
    topo_dxf.to_dxf(part, doc).saveas(f"{OUTDIR}/{part.clusters[0].label}.dxf")

print(f"parti scritte : {len(parts)}  ->  {OUTDIR}/")
print(f"is_valid      : {result.is_valid}")
for w in result.warnings:
    print(f"   warn: {w}")

# il result serve ancora: metadati dell'intero batch
topo.save_json(result, f"{OUTDIR}/{LABEL}.json")
print(f"metadati      : {OUTDIR}/{LABEL}.json")
