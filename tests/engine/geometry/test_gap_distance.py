# tests/engine/geometry/test_gap_distance.py

"""
`topo.geometry.gap` (D251): la distanza minima fra due bordi e la coppia di
punti più vicini, su contorni costruiti con `topo.geometry`.
"""

import math
import unittest

import topo
from topo.core.geometry.measure import FLOAT_NOISE
from topo.core.primitives import ArcSeg, LineSeg


class TestGap(unittest.TestCase):

    def test_due_rettangoli_affiancati(self):
        g = topo.geometry.gap(topo.geometry.rectangle(10, 10, center=(0, 0)), topo.geometry.rectangle(10, 10, center=(17, 3)))
        self.assertIsInstance(g, topo.geometry.Gap)
        self.assertAlmostEqual(g.distance, 7.0, places=9)
        self.assertAlmostEqual(g.on_a[0], 5.0, places=9)
        self.assertAlmostEqual(g.on_b[0], 12.0, places=9)

    def test_tocca_in_un_vertice_e_zero(self):
        # un rombo dentro un quadrato, con un vertice sul lato basso
        g = topo.geometry.gap(topo.geometry.polygon([(0, 0), (100, 0), (100, 60), (0, 60)]),
                topo.geometry.polygon([(50, 0), (80, 20), (50, 40), (20, 20)]))
        self.assertLessEqual(g.distance, FLOAT_NOISE)
        self.assertAlmostEqual(g.on_a[0], 50.0, places=6)

    def test_si_incrociano_e_zero(self):
        for deg in (45, 2, 0.5):
            a = math.radians(deg)
            other = topo.geometry.polygon([(50 + 30 * math.cos(a + k * math.pi / 2), 5 + 30 * math.sin(a + k * math.pi / 2))
                             for k in range(4)])
            self.assertLessEqual(topo.geometry.gap(topo.geometry.rectangle(100, 100, center=(50, 50)), other).distance, FLOAT_NOISE, deg)

    def test_uno_dentro_l_altro_e_la_distanza_fra_i_bordi(self):
        self.assertAlmostEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(8, center=(0, 0))).distance, 2.0, places=9)

    def test_cerchi_esatti(self):
        self.assertAlmostEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(10, center=(25, 0))).distance, 5.0, places=9)
        self.assertLessEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(10, center=(20, 0))).distance, FLOAT_NOISE)

    def test_arco_e_retta(self):
        # mezzo cerchio di raggio 5 sopra l'origine, retta a y = 8
        arc = [ArcSeg(center=(0, 0), radius=5, start_angle=0.0, end_angle=math.pi, ccw=True)]
        g = topo.geometry.gap(arc, [LineSeg(start=(-20, 8), end=(20, 8))])
        self.assertAlmostEqual(g.distance, 3.0, places=9)
        self.assertAlmostEqual(g.on_a[1], 5.0, places=9)

    def test_accetta_un_contorno(self):
        result = topo.heal(topo.load_segments(topo.geometry.rectangle(100, 60, center=(50, 30))
                                              + topo.geometry.rectangle(20, 20, center=(50, 30))), tolerance=0.01).faces()
        cluster = result.clusters[0]
        self.assertAlmostEqual(topo.geometry.gap(cluster.inners[0], cluster.outer).distance, 20.0, places=9)

    def test_bordo_vuoto(self):
        with self.assertRaises(ValueError):
            topo.geometry.gap([], topo.geometry.circle(1, center=(0, 0)))


if __name__ == "__main__":
    unittest.main()
