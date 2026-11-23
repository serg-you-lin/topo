"""
tests/engine/primitives/test_clothoid.py
----------------------------------------
`ClothoidSeg`: the Euler spiral, κ(s) = s/A². The Fresnel integrals to machine
precision, the curvature that grows like the arc length, the exact length, the
polygon within the tolerance. Micro-cases with the answer in closed form.
"""

import math
import unittest

import topo
from topo.core.primitives.clothoid import ClothoidSeg, fresnel
from topo.core.primitives.line import LineSeg

CLOTHOID = ClothoidSeg(origin=(0.0, 0.0), angle=0.0, a=4.0, start_param=0.0, end_param=7.0)


class TestFresnel(unittest.TestCase):

    def test_known_values(self):
        # C(1), S(1) and the limits C, S → 1/2 for x → ∞ (Abramowitz & Stegun 7.3 tables)
        c, s = fresnel(1.0)
        self.assertAlmostEqual(c, 0.7798934003768228, delta=1e-15)
        self.assertAlmostEqual(s, 0.4382591473903548, delta=1e-15)
        c, s = fresnel(1e4)
        self.assertAlmostEqual(c, 0.5, delta=1e-4)
        self.assertAlmostEqual(s, 0.5, delta=1e-4)

    def test_odd_and_continuous_at_the_method_change(self):
        self.assertEqual(fresnel(-2.3), tuple(-v for v in fresnel(2.3)))
        below, above = fresnel(1.5 - 1e-12), fresnel(1.5 + 1e-12)
        self.assertLess(max(abs(p - q) for p, q in zip(below, above)), 1e-11)


class TestCurve(unittest.TestCase):

    def test_curvature_grows_like_the_length(self):
        # κ(s) = s/a²; curvature from the numerical second derivative, |P'| = 1
        h = 1e-4
        for t in (1.0, 3.5, 6.0):
            (ax, ay), (bx, by) = CLOTHOID.derivative_at(t - h), CLOTHOID.derivative_at(t + h)
            dx, dy = CLOTHOID.derivative_at(t)
            kappa = (dx * (by - ay) - dy * (bx - ax)) / (2 * h)
            self.assertAlmostEqual(kappa, t / 16, delta=1e-7)
            self.assertAlmostEqual(CLOTHOID.curvature_at(t), t / 16, delta=1e-15)
            self.assertAlmostEqual(math.hypot(dx, dy), 1.0, delta=1e-15)

    def test_exact_length(self):
        self.assertEqual(topo.geometry.segment_length(CLOTHOID), 7.0)

    def test_final_tangent(self):
        # θ(s) = s²/(2a²): at s = 7 the tangent is at 49/32 rad
        dx, dy = CLOTHOID.derivative_at(7.0)
        self.assertAlmostEqual(math.atan2(dy, dx), 49 / 32, delta=1e-15)

    def test_polygon_within_the_tolerance(self):
        pts = CLOTHOID.discretize(tolerance=0.001)
        polyline = [LineSeg(p, q) for p, q in zip(pts, pts[1:])]
        worst = max(math.dist(CLOTHOID.point_at(7 * k / 3000),
                              topo.geometry.nearest_point(polyline, CLOTHOID.point_at(7 * k / 3000)))
                    for k in range(3001))
        self.assertLessEqual(worst, 0.001)

    def test_stretch_between_two_points(self):
        a, b = CLOTHOID.point_at(2.0), CLOTHOID.point_at(5.5)
        piece = topo.primitives.sub_segment(CLOTHOID, a, b, CLOTHOID.point_at(3.0))
        self.assertIsInstance(piece, ClothoidSeg)
        self.assertAlmostEqual(topo.geometry.segment_length(piece), 3.5, delta=1e-9)

    def test_inside_the_engine(self):
        a, b = CLOTHOID.endpoints()
        ring = [CLOTHOID, LineSeg(b, a)]
        (cluster,) = topo.heal(topo.load_segments(ring)).faces().clusters
        self.assertGreater(cluster.area, 0)
        self.assertEqual(len(cluster.outer.segments), 2)


if __name__ == "__main__":
    unittest.main()
