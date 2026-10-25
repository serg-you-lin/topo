"""
16_strips_on_fixture.py — strisce fra due contorni annidati su un fixture
=========================================================================

Carica `cerchi_concentrici_detect_is_counter_tabs_join.dxf` (rettangolo +
2 cerchi concentrici, r=9 e r~4.12) e unisce il disco interno (profondità 2)
al bordo della regione vuota che lo contiene (l'anello r=9, profondità 1)
con 4 strisce (MAP.md D134, D142). La politica — quante strisce e dove — è
di questo script: quattro punti a 90° sul disco.

Il resto del disegno (il rettangolo) resta intatto. Scrive
`pipeline_output/cerchi_concentrici_con_strisce.dxf`.

    python scripts/16_strips_on_fixture.py
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import math
import os

import topo
import topo_dxf
from topo.tools.strips import facing_boundaries, link, open_boundaries, unconnected_regions
from topo import to_shapely

# --- CONFIG ------------------------------------------------------------
INPUT = r"tests/data/cerchi_concentrici_detect_is_counter_tabs_join.dxf"
STRIP_COUNT = 4
STRIP_WIDTH = 2.0
OUTDIR = "pipeline_output"
# -------------------------------------------------------------------------

doc = topo_dxf.load_dxf(INPUT)
cluster = topo.heal(doc).clusters[0]

links = []
for facing in facing_boundaries(cluster):
    for region in facing.inside:
        c = to_shapely(region).centroid
        r = math.sqrt(to_shapely(region).area / math.pi)
        for k in range(STRIP_COUNT):
            angle = 2 * math.pi * k / STRIP_COUNT
            at = (c.x + r * math.cos(angle), c.y + r * math.sin(angle))
            links.append(link(facing, facing.region, region, at, STRIP_WIDTH, placed=links))
print(f"{len(links)} strisce, regioni non collegate: {len(unconnected_regions(cluster, links))}")

opened = open_boundaries(links)
touched = {id(c) for c, _ in opened.boundaries}
segments = [s for c in (cluster.outer, *cluster.inners) if id(c) not in touched for s in c.segments]
for contour, chains in opened.boundaries:
    print(f"  bordo di profondità {contour.depth}: {len(chains)} catene")
    segments += [s for chain in chains for s in chain]
segments += opened.sides

out = topo.load_segments(segments)
os.makedirs(OUTDIR, exist_ok=True)
path = os.path.join(OUTDIR, "cerchi_concentrici_con_strisce.dxf")
topo_dxf.to_dxf(topo.heal(out), out).saveas(path)
print(f"scritto {path}")
