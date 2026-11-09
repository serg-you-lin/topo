"""
tests/engine/readings/test_known_defect_warnings.py
---------------------------------------------
I due difetti noti della lettura che `heal()` dice con un avviso (D241): una
spline che incrocia se stessa, il nodo di una curva chiusa su un'altra curva
chiusa. Un disegno pulito non ne dà nessuno.
"""

import math
import unittest

import topo
from topo.primitives import BSplineSeg


def _spline(points: list) -> BSplineSeg:
    # spline di grado 1: una spezzata in una curva sola
    n = len(points)
    return BSplineSeg(1, list(points), [0.0] + [float(i) for i in range(n)] + [float(n - 1)])


def _ngon(cx: float, cy: float, r: float, start: float = 0.0) -> list:
    pts = [(cx + r * math.cos(start + 2 * math.pi * k / 24), cy + r * math.sin(start + 2 * math.pi * k / 24))
           for k in range(24)]
    return pts + [pts[0]]


def _codes(segments: list) -> dict:
    network = topo.heal(topo.load_segments(segments))
    return {w.code: w for w in network.warnings}


class TestKnownDefectWarnings(unittest.TestCase):

    def test_una_spline_che_incrocia_se_stessa(self):
        found = _codes([_spline([(0, 0), (100, 0), (100, 100), (0, 100), (20, -10), (10, -10), (0, 0)])])
        self.assertIn("self-crossing", found)
        (x, y), = found["self-crossing"].points
        self.assertAlmostEqual(x, 200 / 11, places=3)
        self.assertAlmostEqual(y, 0.0, places=3)

    def test_il_nodo_di_una_curva_chiusa_su_un_altra(self):
        found = _codes([_spline(_ngon(0, 0, 50)), _spline(_ngon(90, 0, 40, math.pi))])
        self.assertIn("closed-touch", found)
        self.assertTrue(all(math.dist(p, (50, 0)) < 1e-6 for p in found["closed-touch"].points))

    def test_ogni_lettura_copia_l_avviso(self):
        network = topo.heal(topo.load_segments([_spline(_ngon(0, 0, 50)), _spline(_ngon(90, 0, 40, math.pi))]))
        for reading in ("faces", "outlines"):
            with self.subTest(reading=reading):
                self.assertIn("closed-touch", {w.code for w in getattr(network, reading)().warnings})

    def test_un_disegno_pulito_non_avvisa(self):
        found = _codes(topo.geometry.rectangle(200, 100) + topo.geometry.circle(10))
        self.assertNotIn("self-crossing", found)
        self.assertNotIn("closed-touch", found)


if __name__ == "__main__":
    unittest.main()
