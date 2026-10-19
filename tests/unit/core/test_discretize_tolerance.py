"""
tests/unit/core/test_discretize_tolerance.py
--------------------------------------------
La promessa geometrica della 1.0 (D143) parte da qui: `discretize(tol)` di
cerchio, arco ed ellisse resta entro `tol` dalla curva vera a ogni scala.
La freccia è assoluta, quindi i lati devono crescere con il raggio: un tetto
fisso sul numero di lati la viola oltre una certa dimensione (il vecchio
tetto di 128 lati del cerchio sforava da r ≈ 33 a tol 0.01).

Misura: la curva campionata fitta, per ogni campione la distanza dal tratto
della polilinea più vicino; i vertici stanno sulla curva, quindi il massimo
è lo scostamento vero.
"""

import math
import unittest

from topo.core.primitives.segments import (
    ArcSeg,
    CircleSeg,
    EllipseSeg,
    _point_to_segment_distance,
)

TOL = 0.01
RADII = (0.005, 1.0, 10.0, 33.0, 100.0, 500.0, 2000.0)


def _deviation(poly, curve_pts) -> float:
    """Scostamento massimo dei campioni della curva dalla polilinea."""
    worst = 0.0
    for p in curve_pts:
        # vertice più vicino, poi i due tratti che lo toccano
        j = min(range(len(poly)), key=lambda i: (poly[i][0] - p[0]) ** 2 + (poly[i][1] - p[1]) ** 2)
        d = min(
            _point_to_segment_distance(p, poly[k], poly[k + 1])
            for k in (j - 1, j) if 0 <= k < len(poly) - 1
        )
        worst = max(worst, d)
    return worst


def _samples(f, t0: float, t1: float, n: int = 4000):
    return [f(t0 + (t1 - t0) * i / n) for i in range(n + 1)]


class TestDiscretizeWithinTolerance(unittest.TestCase):

    def test_circle_every_radius(self):
        for r in RADII:
            with self.subTest(r=r):
                poly = CircleSeg((0.0, 0.0), r).discretize(TOL)
                curve = _samples(lambda t: (r * math.cos(t), r * math.sin(t)), 0.0, 2 * math.pi)
                self.assertLessEqual(_deviation(poly, curve), TOL)

    def test_circle_sides_grow_with_radius(self):
        # nessun tetto: a r 2000 servono ~π·√(r/2·tol) ≈ 994 lati
        self.assertGreater(len(CircleSeg((0.0, 0.0), 2000.0).discretize(TOL)) - 1, 900)

    def test_arc_every_radius(self):
        for r in RADII:
            with self.subTest(r=r):
                arc = ArcSeg((0.0, 0.0), r, 0.0, 1.5 * math.pi)
                curve = _samples(lambda t: (r * math.cos(t), r * math.sin(t)), 0.0, 1.5 * math.pi)
                self.assertLessEqual(_deviation(arc.discretize(TOL), curve), TOL)

    def test_ellipse_every_scale_and_ratio(self):
        for a, ratio in ((10.0, 1.0), (100.0, 0.5), (500.0, 0.1), (2000.0, 0.02), (1.0, 0.05)):
            with self.subTest(a=a, ratio=ratio):
                e = EllipseSeg((0.0, 0.0), (a, 0.0), ratio, 0.0, 2 * math.pi)
                curve = _samples(e._point_at, 0.0, 2 * math.pi, 20000)
                self.assertLessEqual(_deviation(e.discretize(TOL), curve), TOL)


class TestArcOnCircleGrid(unittest.TestCase):
    """
    D145: un arco usa la griglia del suo cerchio (ancorata all'angolo 0), così
    lo stesso cerchio dà lo stesso poligono comunque il file lo abbia tagliato.
    """

    R = 50.0

    def _circle(self):
        return CircleSeg((3.0, -2.0), self.R).discretize(TOL)

    def _arc(self, a0, a1, ccw=True):
        return ArcSeg((3.0, -2.0), self.R, a0, a1, ccw).discretize(TOL)

    def _same(self, pts_a, pts_b):
        self.assertEqual(len(pts_a), len(pts_b))
        for p, q in zip(pts_a, pts_b):
            self.assertAlmostEqual(p[0], q[0], places=9)
            self.assertAlmostEqual(p[1], q[1], places=9)

    def test_four_quarters_are_the_circle(self):
        circle = self._circle()
        n = len(circle) - 1
        self.assertEqual(n % 4, 0, "griglia scelta per avere i quarti sui vertici")
        joined = [circle[0]]
        for q in range(4):
            joined += self._arc(q * math.pi / 2, (q + 1) * math.pi / 2)[1:]
        self._same(joined, circle)

    def test_off_grid_arc_is_a_piece_of_the_circle(self):
        # estremi fuori griglia: i vertici interni sono quelli del cerchio,
        # i due tratti di testa più corti del passo
        circle = self._circle()
        step = 2 * math.pi / (len(circle) - 1)
        a0, a1 = 0.3 * step, 10.7 * step
        arc = self._arc(a0, a1)
        self._same(arc[1:-1], circle[1:11])
        self.assertLess(math.dist(arc[0], arc[1]), math.dist(circle[0], circle[1]))
        self.assertLess(math.dist(arc[-2], arc[-1]), math.dist(circle[0], circle[1]))

    def test_reversed_arc_gives_the_same_points_backwards(self):
        fwd = self._arc(0.37, 2.9)
        back = ArcSeg((3.0, -2.0), self.R, 0.37, 2.9).reversed().discretize(TOL)
        self._same(back, fwd[::-1])

    def test_arc_shorter_than_a_step_is_one_chord(self):
        step = 2 * math.pi / (len(self._circle()) - 1)
        self.assertEqual(len(self._arc(0.2 * step, 0.7 * step)), 2)

    def test_endpoint_on_a_grid_point_gives_no_degenerate_side(self):
        step = 2 * math.pi / (len(self._circle()) - 1)
        arc = self._arc(3 * step + 1e-13, 9 * step - 1e-13)
        for p, q in zip(arc, arc[1:]):
            self.assertGreater(math.dist(p, q), 1e-6)


if __name__ == "__main__":
    unittest.main()
