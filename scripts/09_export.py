"""
09_export.py — il Result come JSON, solo geometria (D230)
==========================================================

API topo usate:
    to_json      Result -> str  (fatti per parte, NIENTE coordinate)
    save_json    idem, scritto su file
    extra=       i campi del chiamante per ogni cluster (qui un esempio)

    python 09_export.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import os
import topo
import topo_dxf

# --- CONFIG ----------------------------------------------------------------
INPUT     = r"tests/data/Multifeature.dxf"
TOLERANCE = 0.5
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

os.makedirs(OUTDIR, exist_ok=True)
base = os.path.splitext(os.path.basename(INPUT))[0]

doc = topo_dxf.load_dxf(INPUT, tolerance=TOLERANCE)
result = topo.heal(doc, label=base).faces()

# JSON su stdout
print(topo.to_json(result, indent=2)[:600], "...\n")

# JSON su file, con un campo del chiamante: topo non sa cosa sia
topo.save_json(result, os.path.join(OUTDIR, f"{base}.json"),
               extra=lambda cluster: {"part_code": cluster.label.upper()})
print(f"scritto {base}.json in {OUTDIR}/")
