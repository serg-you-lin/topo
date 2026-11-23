# tests/engine/geometry/test_gap_distance.py

"""`topo.geometry.gap`: the minimum distance between two boundaries and the pair
of nearest points, on contours built with `topo.geometry`."""

import math
import unittest

import topo
from topo.core.geometry.measure import FLOAT_NOISE
from topo.core.primitives import CircleSeg, LineSeg


class TestGap(unittest.TestCase):

    def test_two_rectangles_side_by_side(self):
        g = topo.geometry.gap(topo.geometry.rectangle(10, 10, center=(0, 0)), topo.geometry.rectangle(10, 10, center=(17, 3)))
        self.assertIsInstance(g, topo.geometry.Gap)
        self.assertAlmostEqual(g.distance, 7.0, places=9)
        self.assertAlmostEqual(g.on_a[0], 5.0, places=9)
        self.assertAlmostEqual(g.on_b[0], 12.0, places=9)

    def test_touches_at_a_vertex_is_zero(self):
        # a rhombus inside a square, with a vertex on the bottom side
        g = topo.geometry.gap(topo.geometry.polygon([(0, 0), (100, 0), (100, 60), (0, 60)]),
                topo.geometry.polygon([(50, 0), (80, 20), (50, 40), (20, 20)]))
        self.assertLessEqual(g.distance, FLOAT_NOISE)
        self.assertAlmostEqual(g.on_a[0], 50.0, places=6)

    def test_they_cross_and_zero(self):
        for deg in (45, 2, 0.5):
            a = math.radians(deg)
            other = topo.geometry.polygon([(50 + 30 * math.cos(a + k * math.pi / 2), 5 + 30 * math.sin(a + k * math.pi / 2))
                             for k in range(4)])
            self.assertLessEqual(topo.geometry.gap(topo.geometry.rectangle(100, 100, center=(50, 50)), other).distance, FLOAT_NOISE, deg)

    def test_one_inside_the_other_and_the_distance_between_the_borders(self):
        self.assertAlmostEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(8, center=(0, 0))).distance, 2.0, places=9)

    def test_exact_circles(self):
        self.assertAlmostEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(10, center=(25, 0))).distance, 5.0, places=9)
        self.assertLessEqual(topo.geometry.gap(topo.geometry.circle(10, center=(0, 0)), topo.geometry.circle(10, center=(20, 0))).distance, FLOAT_NOISE)

    def test_arc_and_line(self):
        # semicircle of radius 5 above the origin, line at y = 8
        arc = [CircleSeg(center=(0, 0), radius=5, start_angle=0.0, end_angle=math.pi, ccw=True)]
        g = topo.geometry.gap(arc, [LineSeg(start=(-20, 8), end=(20, 8))])
        self.assertAlmostEqual(g.distance, 3.0, places=9)
        self.assertAlmostEqual(g.on_a[1], 5.0, places=9)

    def test_accepts_a_contour(self):
        result = topo.heal(topo.load_segments(topo.geometry.rectangle(100, 60, center=(50, 30))
                                              + topo.geometry.rectangle(20, 20, center=(50, 30)))).faces()
        cluster = result.clusters[0]
        self.assertAlmostEqual(topo.geometry.gap(cluster.inners[0], cluster.outer).distance, 20.0, places=9)

    def test_empty_border(self):
        with self.assertRaises(ValueError):
            topo.geometry.gap([], topo.geometry.circle(1, center=(0, 0)))


if __name__ == "__main__":
    unittest.main()
