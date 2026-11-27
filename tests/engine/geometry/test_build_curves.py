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

    def test_two_parallels_in_the_same_direction_an_s(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))
        self.assertIsInstance(seg, BSplineSeg)
        self.assertEqual(seg.degree, 3)
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))

    def test_two_parallels_in_opposite_directions_a_u(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (0.0, 5.0), (-1.0, 0.0))
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (0.0, 5.0), (-1.0, 0.0))
        self.assertGreater(seg.point_at(seg.t_range[1] / 2)[0], 0)   # the U leaves towards the lines

    def test_continuity_2_zero_curvature_at_the_ends(self):
        (seg,) = g.blend((0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0), continuity=2)
        self.assertEqual(seg.degree, 5)
        self._check_ends(seg, (0.0, 0.0), (1.0, 0.0), (10.0, 5.0), (1.0, 0.0))
        for t in seg.t_range:
            self.assertAlmostEqual(_turn(seg, t), 0.0, delta=1e-4)

    def test_refuses_coincident_ends_and_null_direction(self):
        with self.assertRaises(ValueError):
            g.blend((1.0, 1.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        with self.assertRaises(ValueError):
            g.blend((0.0, 0.0), (0.0, 0.0), (1.0, 1.0), (0.0, 1.0))


class TestPolynomial(unittest.TestCase):

    def test_the_curve_is_the_graph_of_the_polynomial(self):
        c = [1.0, -2.0, 0.5, 0.25]
        (seg,) = g.polynomial(c, -2.0, 3.0)
        self.assertEqual(seg.degree, 3)
        t0, t1 = seg.t_range
        for k in range(51):
            x, y = seg.point_at(t0 + (t1 - t0) * k / 50)
            self.assertAlmostEqual(y, sum(ci * x ** i for i, ci in enumerate(c)), delta=1e-12)

    def test_degree_one_is_a_line(self):
        self.assertEqual(g.polynomial([3.0, 2.0], 0.0, 4.0), [LineSeg(start=(0.0, 3.0), end=(4.0, 11.0))])
        self.assertEqual(g.polynomial([3.0, 2.0, 0.0], 0.0, 4.0), [LineSeg(start=(0.0, 3.0), end=(4.0, 11.0))])


class TestInvoluteAndClothoid(unittest.TestCase):

    def test_involute_starts_from_the_circle_and_unwinds(self):
        (seg,) = g.involute(10.0, 1.2, center=(5.0, 5.0), angle=90)
        self.assertIsInstance(seg, FormulaSeg)
        start, _ = seg.endpoints()
        self.assertAlmostEqual(start[0], 5.0, delta=1e-12)
        self.assertAlmostEqual(start[1], 15.0, delta=1e-12)
        self.assertAlmostEqual(topo.geometry.segment_length(seg), 10 * 1.2 ** 2 / 2, delta=1e-12)

    def test_clothoid_final_radius(self):
        (seg,) = g.clothoid(4.0, 7.0, start=(1.0, 2.0), angle=45)
        self.assertIsInstance(seg, ClothoidSeg)
        self.assertEqual(seg.endpoints()[0], (1.0, 2.0))
        self.assertAlmostEqual(1 / seg.curvature_at(7.0), 16 / 7, delta=1e-12)   # a²/length
        dx, dy = seg.derivative_at(0.0)
        self.assertAlmostEqual(math.degrees(math.atan2(dy, dx)), 45.0, delta=1e-12)


class TestClothoidCorner(unittest.TestCase):

    def _corner(self, deflection_deg: float, radius: float = 40.0):
        d = math.radians(deflection_deg)
        return g.clothoid_corner((0.0, 0.0), (1.0, 0.0), (math.cos(d), math.sin(d)), radius), d

    def test_two_pieces_head_to_tail_and_symmetric(self):
        for deflection in (60.0, -60.0, 20.0, 150.0):
            with self.subTest(deflection=deflection):
                (first, second), d = self._corner(deflection)
                self.assertTrue(all(isinstance(s, ClothoidSeg) for s in (first, second)))
                self.assertAlmostEqual(math.dist(first.endpoints()[1], second.endpoints()[0]), 0.0, delta=1e-12)
                t_in = math.dist(first.endpoints()[0], (0.0, 0.0))
                t_out = math.dist(second.endpoints()[1], (0.0, 0.0))
                self.assertAlmostEqual(t_in, t_out, delta=1e-12)

    def test_leaves_and_joins_the_lines_tangent(self):
        (first, second), d = self._corner(60.0)
        x0, y0 = first.derivative_at(first.t_range[0])
        self.assertAlmostEqual(math.atan2(y0, x0), 0.0, delta=1e-12)
        x1, y1 = second.derivative_at(second.t_range[1])
        self.assertAlmostEqual(math.atan2(y1, x1), d, delta=1e-12)
        # the ends lie on the two lines: on the x axis, and on the ray at angle d
        self.assertAlmostEqual(first.endpoints()[0][1], 0.0, delta=1e-12)
        q = second.endpoints()[1]
        self.assertAlmostEqual(q[0] * math.sin(d) - q[1] * math.cos(d), 0.0, delta=1e-12)

    def test_curvature_zero_at_the_ends_and_linear(self):
        (first, second), d = self._corner(60.0, radius=40.0)
        length = 40.0 * d
        self.assertAlmostEqual(first.curvature_at(0.0), 0.0, delta=1e-15)
        self.assertAlmostEqual(first.curvature_at(length), 1 / 40.0, delta=1e-12)      # the smallest radius is the one asked
        self.assertAlmostEqual(first.curvature_at(length / 2), 1 / 80.0, delta=1e-12)
        self.assertAlmostEqual(abs(second.curvature_at(0.0)), 1 / 40.0, delta=1e-12)

    def test_turns_the_way_the_corner_does(self):
        (left, _), _ = self._corner(60.0)
        (right, _), _ = self._corner(-60.0)
        self.assertGreater(left.curvature_at(10.0), 0)
        self.assertLess(right.curvature_at(10.0), 0)

    def test_parallel_directions_and_bad_arguments_raise(self):
        with self.assertRaises(ValueError):
            g.clothoid_corner((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), 40.0)
        with self.assertRaises(ValueError):
            g.clothoid_corner((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0), 40.0)
        with self.assertRaises(ValueError):
            g.clothoid_corner((0.0, 0.0), (0.0, 0.0), (0.0, 1.0), 40.0)
        with self.assertRaises(ValueError):
            g.clothoid_corner((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), 0.0)


class TestTriangle(unittest.TestCase):

    def test_given_sides(self):
        sides = g.triangle(3.0, 4.0, 5.0, start=(1.0, 1.0), angle=30)
        self.assertEqual([round(topo.geometry.segment_length(s), 12) for s in sides], [3.0, 4.0, 5.0])
        (cluster,) = topo.heal(topo.load_segments(sides)).faces().clusters
        self.assertAlmostEqual(cluster.area, 6.0, delta=1e-12)

    def test_right_triangle_from_the_legs(self):
        sides = g.right_triangle(3.0, 4.0, start=(10.0, 5.0), angle=30)
        self.assertEqual(sides[0].start, (10.0, 5.0))
        self.assertEqual([round(topo.geometry.segment_length(s), 12) for s in sides], [3.0, 5.0, 4.0])
        # right angle at start: the two legs perpendicular
        (ax, ay), (bx, by) = sides[0].end, sides[2].start
        self.assertAlmostEqual((ax - 10) * (bx - 10) + (ay - 5) * (by - 5), 0.0, delta=1e-12)
        (cluster,) = topo.heal(topo.load_segments(sides)).faces().clusters
        self.assertAlmostEqual(cluster.area, 6.0, delta=1e-12)

    def test_sides_that_do_not_close_refused(self):
        with self.assertRaises(ValueError):
            g.triangle(1.0, 2.0, 3.0)


if __name__ == "__main__":
    unittest.main()
