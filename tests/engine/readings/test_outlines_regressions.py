# tests/engine/readings/test_outlines_regressions.py

"""Isolated regressions on `read_outline()`, found on 11 October by opening
`anch_02.dxf` (golden_outlines) in a viewer and judged wrong by eye by Federico
— not caught by any existing golden. Every fixture is a minimal
cut of the real sheet, saved with topo's own API (never ezdxf directly):
`tests/data/regressions/*.dxf`."""

import unittest

import topo
import topo_dxf
from topo.core.readings.outline import read_outline
from topo import to_shapely
from tests.paths import DATA

FIXTURES = DATA / "regressions"
TOLERANCE = 0.05
MAX_GAP = 0.5


class TestTangentSpike(unittest.TestCase):
    """71 edges of a single slot of the same isometric view. Clean on 1b5b02e (tip at
    x=1506.30), broken already on 091970a ("the outer face is the boundary of the
    union of the closed faces")."""

    def test_the_rounded_tip_has_no_spike(self):
        doc = topo_dxf.load_dxf(str(FIXTURES / "outline_tangent_spike.dxf"))
        reading = read_outline(doc.edges, tolerance=TOLERANCE, max_gap=MAX_GAP)
        self.assertIsNotNone(reading.outer)
        # 1011.359 at fine discretization; 1011.27 with ezdxf's points
        self.assertAlmostEqual(to_shapely(reading.outer).area, 1011.35, places=1)
        max_x = max(x for x, _ in to_shapely(reading.outer).exterior.coords)
        # clean = 1506.30; broken (today) = 1506.63 (0.33 mm spike)
        self.assertLess(max_x, 1506.4,
                         "spurious vertex on the rounded tip, beyond the smooth curve")


if __name__ == "__main__":
    unittest.main(verbosity=2)
