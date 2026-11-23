# tests/engine/geometry/test_build.py
"""Constructors of `topo.geometry` and `topo.load_segments`: building and reading use the same measures."""

import math
import unittest

import topo
from topo.core.geometry import contour_shape
from topo.core.geometry.build import circle, ellipse, polygon, rectangle, regular_polygon, stadium
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg


class TestBuild(unittest.TestCase):

    def test_polygon_closes_by_itself(self):
        segs = polygon([(0, 0), (10, 0), (5, 8)])
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[-1].end, (0, 0))
        self.assertEqual(len(polygon([(0, 0), (10, 0), (5, 8), (0, 0)])), 3)

    def test_polygon_with_fewer_than_three_points(self):
        with self.assertRaises(ValueError):
            polygon([(0, 0), (1, 1)])

    def test_rotated_rectangle_reads_back_equal(self):
        s = contour_shape(rectangle(80, 30, center=(5, 5), angle=20))
        self.assertEqual(s.kind, "rectangle")
        self.assertAlmostEqual(s.length, 80)
        self.assertAlmostEqual(s.width, 30)
        self.assertAlmostEqual(s.angle, 20)
        self.assertAlmostEqual(s.center[0], 5)

    def test_regular_polygon(self):
        segs = regular_polygon(6, 10, center=(1, 2))
        self.assertEqual(len(segs), 6)
        self.assertTrue(all(isinstance(s, LineSeg) for s in segs))
        self.assertAlmostEqual(math.dist(segs[0].start, (1, 2)), 10)
        with self.assertRaises(ValueError):
            regular_polygon(2, 10)

    def test_circle(self):
        (c,) = circle(5, center=(3, 4))
        self.assertIsInstance(c, CircleSeg)
        self.assertEqual(contour_shape([c]).diameter, 10)

    def test_ellipse_reads_back_equal(self):
        s = contour_shape(ellipse(40, 16, center=(3, 4), angle=120))
        self.assertEqual(s.kind, "ellipse")
        self.assertAlmostEqual(s.length, 40)
        self.assertAlmostEqual(s.width, 16)
        self.assertAlmostEqual(s.angle, 120)
        self.assertEqual(s.center, (3, 4))
        with self.assertRaises(ValueError):
            ellipse(10, 20)

    def test_stadium_with_true_arcs(self):
        segs = stadium(60, 20, center=(10, 5), angle=30)
        self.assertEqual(sum((isinstance(s, CircleSeg) and not s.full) for s in segs), 2)
        s = contour_shape(segs)
        self.assertEqual(s.kind, "stadium")
        self.assertAlmostEqual(s.length, 60)
        self.assertAlmostEqual(s.width, 20)
        self.assertAlmostEqual(s.angle, 30)
        with self.assertRaises(ValueError):
            stadium(10, 20)


class TestLoadSegments(unittest.TestCase):

    def test_two_rectangles_and_a_circle(self):
        fg = topo.geometry
        doc = topo.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50) + fg.circle(5, center=(70, 0)))
        result = topo.heal(doc).faces()
        self.assertTrue(result.is_valid)
        (part,) = result.clusters
        self.assertEqual(fg.contour_shape(part.outer).kind, "rectangle")
        self.assertEqual(sorted(fg.contour_shape(i).kind for i in part.inners), ["circle", "rectangle"])
        self.assertAlmostEqual(part.area, 200 * 100 - 100 * 50 - math.pi * 25, places=0)

    def test_nested_lists_and_role(self):
        doc = topo.load_segments([rectangle(10, 10), circle(1)], role="outer")
        self.assertEqual(len(doc.edges), 5)
        self.assertTrue(all(e.role == "outer" for e in doc.edges))

    def test_load_geometry_polygon(self):
        doc = topo.load_geometry([{"type": "polygon", "points": [(0, 0), (10, 0), (10, 5), (0, 5)]}])
        self.assertEqual(len(doc.edges), 4)


if __name__ == "__main__":
    unittest.main()
