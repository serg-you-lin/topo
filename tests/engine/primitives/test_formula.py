"""
tests/engine/primitives/test_formula.py
---------------------------------------
`FormulaSeg`: the curve given by x(t), y(t) in a closed grammar. Outside the
grammar it is rejected; the derivative is symbolic; area and length are exact
on the formula; the engine reads it like the others. Micro-cases with the
answer in closed form: the circle's involute.
"""

import math
import pickle
import unittest

import topo
from topo.core.primitives.formula import FormulaSeg
from topo.core.primitives.line import LineSeg

# involute of the circle of radius 10: length r·T²/2, area swept from the centre r²·T³/6
INVOLUTE = FormulaSeg("r*(cos(t) + t*sin(t))", "r*(sin(t) - t*cos(t))", 0.0, 1.2, params={"r": 10.0})


class TestGrammar(unittest.TestCase):

    def test_outside_the_grammar_refused(self):
        for text in ("__import__('os')", "t.real", "[t]", "lambda: 1", "open(t)", "t if t else 1", "q * t", "sin(t, t)"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                FormulaSeg(text, "t", 0.0, 1.0)

    def test_undefined_at_the_ends_refused(self):
        with self.assertRaises(ValueError):
            FormulaSeg("t", "log(t)", 0.0, 1.0)

    def test_is_kept_and_compared(self):
        copy = pickle.loads(pickle.dumps(INVOLUTE))
        self.assertEqual(copy, INVOLUTE)
        self.assertEqual(copy.point_at(0.7), INVOLUTE.point_at(0.7))


class TestDerivative(unittest.TestCase):

    def test_symbolic_on_every_rule(self):
        # sum, product, quotient, constant and variable power, composition
        seg = FormulaSeg("t*sin(t) + 2**t", "sqrt(1 + t**2) / cosh(t) - atan(t)**3", -1.0, 2.0)
        h = 1e-6
        for t in (0.2, 1.0, 2.7):
            (ax, ay), (bx, by) = seg.point_at(t - h), seg.point_at(t + h)
            dx, dy = seg.derivative_at(t)
            self.assertAlmostEqual(dx, (bx - ax) / (2 * h), delta=1e-7)
            self.assertAlmostEqual(dy, (by - ay) / (2 * h), delta=1e-7)


class TestInTheEngine(unittest.TestCase):

    def _tooth(self):
        a, b = INVOLUTE.endpoints()
        return [INVOLUTE, LineSeg(b, (0.0, 0.0)), LineSeg((0.0, 0.0), a)]

    def test_exact_length(self):
        self.assertAlmostEqual(topo.geometry.segment_length(INVOLUTE), 10 * 1.2 ** 2 / 2, delta=1e-12)

    def test_exact_area(self):
        (cluster,) = topo.heal(topo.load_segments(self._tooth())).faces().clusters
        self.assertAlmostEqual(cluster.area, 10 ** 2 * 1.2 ** 3 / 6, delta=1e-12)

    def test_stretch_between_two_points(self):
        a, b = INVOLUTE.point_at(0.3), INVOLUTE.point_at(0.9)
        piece = topo.primitives.sub_segment(INVOLUTE, a, b, INVOLUTE.point_at(0.6))
        self.assertIsInstance(piece, FormulaSeg)
        for p, q in zip(piece.endpoints(), (a, b)):
            self.assertLess(math.dist(p, q), 1e-9)

    def test_polygon_within_the_tolerance(self):
        pts = INVOLUTE.discretize(tolerance=0.001)
        nearest = topo.geometry.nearest_point
        polyline = [LineSeg(p, q) for p, q in zip(pts, pts[1:])]
        worst = max(math.dist(INVOLUTE.point_at(1.2 * k / 3000), nearest(polyline, INVOLUTE.point_at(1.2 * k / 3000)))
                    for k in range(3001))
        self.assertLessEqual(worst, 0.001)


if __name__ == "__main__":
    unittest.main()
