"""
06_split.py — un documento DXF per parte (funzione pura)
=======================================================

API topo usate:
    split    Result -> list[Result], uno per parte (senza formato). NON tocca il disco;
             topo_dxf.to_dxf ne scrive uno.

Per salvare davvero: itera il risultato e chiama .saveas(), oppure usa
split_to_files() (vedi 07). Le parti sotto min_area (mm²) vengono scartate.

    python 06_split.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import topo
import topo_dxf
from topo import to_shapely

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/golden/example_4_polylines.dxf"   # 4 parti
TOLERANCE = 0.5
OUTDIR    = "pipeline_output/split_demo"
MIN_AREA  = 50.0
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)

doc = topo_dxf.load_dxf(INPUT, tolerance=TOLERANCE)
result = topo.heal(doc, label="batch")
if not result.is_valid:
    raise SystemExit(f"non valido: {result.errors}")


# namer: callable(i, cluster) -> str — assegna cluster.label, così il nome file
# resta ricavabile a valle come f"{cluster.label}.dxf"
def namer(i, cluster):
    return f"pezzo_{i + 1:02d}"


# topo.split: un Result per parte, senza formato (D129) — il trash e le
# annotazioni vanno alla parte che li contiene o alla più vicina
parts = topo.split(result, namer=namer, min_area=MIN_AREA)

for part in parts:
    cluster = part.clusters[0]
    doc_out = topo_dxf.to_dxf(
        part, doc,
        exclude_types={"TEXT"},     # rimuove i TEXT dal documento figlio
        include_texts=True,
    )
    # quello che faceva on_part: metadati / marcature sul doc figlio
    topo_dxf.write_metadata_to_dxf(doc_out, cluster)
    path = os.path.join(OUTDIR, f"{cluster.label}.dxf")
    doc_out.saveas(path)
    print(f"   {path}  (area {to_shapely(cluster.outer).area:.0f} mm²)")

for w in result.warnings:
    print(f"   warn: {w}")
