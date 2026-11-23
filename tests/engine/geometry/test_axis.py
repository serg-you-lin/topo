# tests/engine/geometry/test_axis.py
"""`topo.core.geometry.axis`: intervals, covered rectangles, lines crossing a rectangle."""

import math
import unittest

import topo
from topo.core.geometry.axis import (axis_aligned_share, axis_lines, cluster_values, covered_rectangles,
                             interval_coverage, items_inside, merge_intervals, spanning_lines)
from topo.core.geometry.build import polygon
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg


def _rect(x0, y0, x1, y1):
    return polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


class TestIntervals(unittest.TestCase):

    def test_union_case(self):
        self.assertEqual(merge_intervals([(5, 8), (0, 2), (1, 3)]), [(0, 3), (5, 8)])
        self.assertEqual(merge_intervals([(0, 2), (2.5, 4)], tolerance=0.5), [(0, 4)])

    def test_coverage(self):
        self.assertAlmostEqual(interval_coverage([(0, 4), (6, 10)], 0, 10), 0.8)
        self.assertAlmostEqual(interval_coverage([(-5, 20)], 0, 10), 1.0)
        self.assertEqual(interval_coverage([(0, 1)], 3, 3), 0.0)

    def test_groups_values(self):
        self.assertEqual(cluster_values([10.0, 0.0, 1.0, 10.5], tolerance=1.5), [0.0, 10.0])


class TestCoveredRectangles(unittest.TestCase):

    def test_double_border_two_rectangles(self):
        items = _rect(0, 0, 420, 297) + _rect(10, 10, 410, 287)
        rects = covered_rectangles(items, min_side=100, eps=0.5, cluster_tolerance=1.5, coverage=0.85)
        bboxes = sorted(r.bbox for r in rects)
        self.assertIn((0.0, 0.0, 420.0, 297.0), bboxes)
        self.assertIn((10.0, 10.0, 410.0, 287.0), bboxes)

    def test_side_broken_by_notches_stays_covered(self):
        top = [LineSeg(start=(x, 100), end=(x + 19, 100)) for x in range(0, 200, 20)]
        items = [LineSeg(start=(0, 0), end=(200, 0)), LineSeg(start=(200, 0), end=(200, 100)),
                 LineSeg(start=(0, 100), end=(0, 0))] + top + [LineSeg(start=(50, 100), end=(150, 100))]
        (rect,) = covered_rectangles(items, min_side=50, eps=0.5, cluster_tolerance=1.5, coverage=0.85)
        self.assertEqual(rect.bbox, (0.0, 0.0, 200.0, 100.0))
        self.assertAlmostEqual(rect.ratio, 2.0)

    def test_missing_side(self):
        self.assertEqual(covered_rectangles(_rect(0, 0, 100, 50)[:3], min_side=10, eps=0.5, cluster_tolerance=1.5, coverage=0.85), [])

    def test_public_api(self):
        self.assertIs(topo.geometry.covered_rectangles, covered_rectangles)


class TestCoveredRectanglesUnderMotion(unittest.TestCase):
    """the rectangles found were deduplicated on a key rounded to 0.1. The
    coordinates come from `cluster_values`, farther apart than `cluster_tolerance`:
    with the threshold below 0.1 two true rectangles (right side at 100 and at
    100.03) ended in the same cell or in two depending on where the motion put the
    cell. Proof: in place and at translations and quarter turns the three
    rectangles come out (the two full ones and the strip between the two right
    sides). It proves nothing inside the readings: no topo reading calls
    `covered_rectangles`."""

    MOTIONS = [(0.0, 0.0, 0.0), (0.0, 0.04, 0.0), (0.0, 0.07, -3.3),
               (math.pi / 2, 0.0, 0.0), (math.pi / 2, 12.345, 0.06)]

    def test_two_near_sides_three_rectangles(self):
        from tests.invariants import rigid
        corners = [(0.0, 0.0, 100.0, 50.0), (0.0, 0.0, 100.03, 50.0), (100.0, 0.0, 100.03, 50.0)]
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                move_seg, move_pt = rigid(*motion)
                items = [move_seg(s) for s in (LineSeg(start=(0, 0), end=(100.03, 0)),
                                               LineSeg(start=(0, 50), end=(100.03, 50)),
                                               LineSeg(start=(0, 0), end=(0, 50)),
                                               LineSeg(start=(100, 0), end=(100, 50)),
                                               LineSeg(start=(100.03, 0), end=(100.03, 50)))]
                rects = covered_rectangles(items, min_side=10, eps=0.004, cluster_tolerance=0.01, coverage=0.85)
                expected = []
                for x0, y0, x1, y1 in corners:
                    pts = [move_pt(p) for p in ((x0, y0), (x1, y1))]
                    expected.append((min(p[0] for p in pts), min(p[1] for p in pts),
                                     max(p[0] for p in pts), max(p[1] for p in pts)))
                got = sorted(r.bbox for r in rects)
                self.assertEqual(len(got), 3)
                for g, e in zip(got, sorted(expected)):
                    for a, b in zip(g, e):
                        self.assertAlmostEqual(a, b, places=6)


class TestSpanningLines(unittest.TestCase):

    def test_rows_and_columns(self):
        items = _rect(0, 0, 100, 40) + [LineSeg(start=(0, 20), end=(100, 20)),
                                        LineSeg(start=(60, 0), end=(60, 40)),
                                        LineSeg(start=(0, 30), end=(30, 30))]   # too short
        self.assertEqual(spanning_lines((0, 0, 100, 40), items, eps=0.5, cluster_tolerance=1.5, coverage=0.85), ([20.0], [60.0]))


class TestMeasures(unittest.TestCase):

    def test_stretches_inside(self):
        items = [LineSeg(start=(1, 1), end=(9, 9)), LineSeg(start=(1, 1), end=(11, 1))]
        self.assertEqual(items_inside((0, 0, 10, 10), items), items[:1])
        self.assertEqual(len(items_inside((0, 0, 10, 10), items, margin=1.5)), 2)

    def test_dimension_aligned_to_the_axes(self):
        segs = [LineSeg(start=(0, 0), end=(30, 0)), LineSeg(start=(0, 0), end=(10, 10 * 3 ** 0.5))]
        self.assertAlmostEqual(axis_aligned_share(segs, angle_tolerance=2.0), 30 / 50)
        self.assertIsNone(axis_aligned_share([CircleSeg(center=(0, 0), radius=1, start_angle=0, end_angle=1)], angle_tolerance=2.0))

    def test_horizontals_and_verticals(self):
        horiz, vert = axis_lines(_rect(0, 0, 10, 5), eps=0.5)
        self.assertEqual(sorted(h.at for h in horiz), [0.0, 5.0])
        self.assertEqual(sorted(v.at for v in vert), [0.0, 10.0])



class TestSidesOnBorder(unittest.TestCase):

    def test_box_in_the_corner(self):
        # bottom right: touches the bottom and the right side of the border
        self.assertEqual(topo.geometry.sides_on_border((300, 10, 400, 60), (10, 10, 400, 280), tolerance=1.0),
                         ["bottom", "right"])

    def test_box_in_the_middle(self):
        self.assertEqual(topo.geometry.sides_on_border((150, 100, 250, 125), (10, 10, 400, 280), tolerance=1.0), [])


if __name__ == "__main__":
    unittest.main()
