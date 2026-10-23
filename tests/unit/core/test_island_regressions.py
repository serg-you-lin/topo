# tests/unit/core/test_island_regressions.py

"""
Regressioni isolate su `read_island()`, trovate l'11 ottobre aprendo
`anch_02.dxf` (golden_islands) in un viewer e viste sbagliate a occhio da
Federico — non intercettate da nessun golden esistente (vedi TODO.md).
Ogni fixture è un ritaglio minimo del foglio reale, salvato con l'API di
topo stessa (mai ezdxf diretto): `tests/data/regressions/*.dxf`.
"""

import unittest
from pathlib import Path

import topo
import topo_dxf
from topo.core.island import read_island

FIXTURES = Path(__file__).resolve().parent.parent.parent / "data" / "regressions"
TOLERANCE = 0.05
MAX_GAP = 0.5


class TestTangentSpike(unittest.TestCase):
    """71 edge di una sola asola della stessa vista isometrica. Pulita su
    1b5b02e (D99, punta a x=1506.30), rotta già su 091970a (D100, "the outer
    face is the boundary of the union of the closed faces") — D101 e' innocente
    su questo caso."""

    def test_la_punta_arrotondata_non_ha_una_spike(self):
        doc = topo_dxf.load_dxf(str(FIXTURES / "island_tangent_spike.dxf"), tolerance=TOLERANCE)
        reading = read_island(doc.edges, tolerance=TOLERANCE, max_gap=MAX_GAP)
        self.assertIsNotNone(reading.outer)
        # 1011.359 a discretizzazione fine; 1011.27 coi punti di ezdxf (D135)
        self.assertAlmostEqual(reading.outer.polygon.area, 1011.35, places=1)
        max_x = max(x for x, _ in reading.outer.polygon.exterior.coords)
        # pulito (D99) = 1506.30; rotto (D100, oggi) = 1506.63 (spike di 0.33mm)
        self.assertLess(max_x, 1506.4,
                         "vertice spurio sulla punta arrotondata, oltre la curva liscia")


if __name__ == "__main__":
    unittest.main(verbosity=2)
