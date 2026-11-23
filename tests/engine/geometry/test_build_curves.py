"""
tests/engine/geometry/test_build_curves.py
------------------------------------------
The curve constructors of `topo.geometry`: the fillet between two ends, the
graph of a polynomial, the involute, the clothoid, the triangle from the
sides. Micro-cases with the answer in closed form.
"""

import math
import unittest

import topo
from topo.primitives import BSplineSeg, ClothoidSeg, FormulaSeg, LineSeg

g = topo.geometry


def _turn(seg, t: float) -> float:
    """Signed curvature from the first and second derivative (numerical on the exact derivative)."""
    h = 1e-5
    (ax, ay), (bx, by) = seg.derivative_at(t - h if t > h else t), seg.derivative_at(t + h)
    span = (t + h) - (t - h if t > h else t)
    dx, dy = seg.derivative_at(t)
    return (dx * (by - ay) - dy * (bx - ax)) / span / math.hypot(dx, dy) ** 3


class TestBlend(unittest.TestCase):

    def _check_ends(self, seg, start, start_dir, end, end_dir):
        t0, t1 = seg.t_range
        self.assertEqual(seg.endpoints(), (start, end))
        for t, d in ((t0, start_dir), (t1, end_dir)):
            dx, dy = seg.derivative_at(t)
            self.assertAlmostEqual(dx * d[1] - dy * d[0], 0.0, delta=1e-12)   # parallela
            self.assertGreater(dx * d[0] + dy * d[1], 0)                       # in the same direction

    def test_due_parallele_nello_stesso_verso_una_esse(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))
        self.assertIsInstance(seg, BSplineSeg)
        self.assertEqual(seg.degree, 3)
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))

    def test_due_parallele_in_versi_opposti_una_u(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (0.0, 5.0), (-1.0, 0.0))
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (0.0, 5.0), (-1.0, 0.0))
        self.assertGreater(seg.point_at(seg.t_range[1] / 2)[0], 0)   # la U esce verso le rette

    def test_continuita_2_curvatura_zero_ai_capi(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0), continuity=2)
        self.assertEqual(seg.degree, 5)
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))
        for t in seg.t_range:
            self.assertAlmostEqual(_turn(seg, t), 0.0, delta=1e-4)

    def test_rifiuta_capi_coincidenti_e_direzione_nulla(self):
        with self.assertRaises(ValueError):
            g.blend((1.0, 1.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        with self.assertRaises(ValueError):
            g.blend((0.0, 0.0), (0.0, 0.0), (1.0, 1.0), (0.0, 1.0))


class TestPolynomial(unittest.TestCase):

    def test_la_curva_e_il_grafico_del_polinomio(self):
        c = [1.0, -2.0, 0.5, 0.25]
        (seg,) = g.polynomial(c, -2.0, 3.0)
        self.assertEqual(seg.degree, 3)
        t0, t1 = seg.t_range
        for k in range(51):
            x, y = seg.point_at(t0 + (t1 - t0) * k / 50)
            self.assertAlmostEqual(y, sum(ci * x ** i for i, ci in enumerate(c)), delta=1e-12)

    def test_grado_uno_e_una_retta(self):
        self.assertEqual(g.polynomial([3.0, 2.0], 0.0, 4.0), [LineSeg(start=(0.0, 3.0), end=(4.0, 11.0))])
        self.assertEqual(g.polynomial([3.0, 2.0, 0.0], 0.0, 4.0), [LineSeg(start=(0.0, 3.0), end=(4.0, 11.0))])


class TestInvoluteAndClothoid(unittest.TestCase):

    def test_evolvente_parte_dal_cerchio_e_si_srotola(self):
        (seg,) = g.involute(10.0, 1.2, center=(5.0, 5.0), angle=90)
        self.assertIsInstance(seg, FormulaSeg)
        start, _ = seg.endpoints()
        self.assertAlmostEqual(start[0], 5.0, delta=1e-12)
        self.assertAlmostEqual(start[1], 15.0, delta=1e-12)
        self.assertAlmostEqual(topo.geometry.segment_length(seg), 10 * 1.2 ** 2 / 2, delta=1e-12)

    def test_clotoide_raggio_finale(self):
        (seg,) = g.clothoid(4.0, 7.0, start=(1.0, 2.0), angle=45)
        self.assertIsInstance(seg, ClothoidSeg)
        self.assertEqual(seg.endpoints()[0], (1.0, 2.0))
        self.assertAlmostEqual(1 / seg.curvature_at(7.0), 16 / 7, delta=1e-12)   # a²/length
        dx, dy = seg.derivative_at(0.0)
        self.assertAlmostEqual(math.degrees(math.atan2(dy, dx)), 45.0, delta=1e-12)


class TestTriangle(unittest.TestCase):

    def test_lati_dati(self):
        sides = g.triangle(3.0, 4.0, 5.0, start=(1.0, 1.0), angle=30)
        self.assertEqual([round(topo.geometry.segment_length(s), 12) for s in sides], [3.0, 4.0, 5.0])
        (cluster,) = topo.heal(topo.load_segments(sides)).faces().clusters
        self.assertAlmostEqual(cluster.area, 6.0, delta=1e-12)

    def test_triangolo_rettangolo_dai_cateti(self):
        sides = g.right_triangle(3.0, 4.0, start=(10.0, 5.0), angle=30)
        self.assertEqual(sides[0].start, (10.0, 5.0))
        self.assertEqual([round(topo.geometry.segment_length(s), 12) for s in sides], [3.0, 5.0, 4.0])
        # right angle at start: the two legs perpendicular
        (ax, ay), (bx, by) = sides[0].end, sides[2].start
        self.assertAlmostEqual((ax - 10) * (bx - 10) + (ay - 5) * (by - 5), 0.0, delta=1e-12)
        (cluster,) = topo.heal(topo.load_segments(sides)).faces().clusters
        self.assertAlmostEqual(cluster.area, 6.0, delta=1e-12)

    def test_lati_che_non_chiudono_rifiutati(self):
        with self.assertRaises(ValueError):
            g.triangle(1.0, 2.0, 3.0)


if __name__ == "__main__":
    unittest.main()
