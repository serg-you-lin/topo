"""
tests/engine/readings/test_loose.py
------------------------
`result.loose`: every curve that is no cluster's contour knows which cluster
contains it (`cluster_ref`), a consumer moves it into `cluster.overlay` with
`result.promote`, `split` sends it to the part of its `cluster_ref`.

The drawing: a 200×100 plate centred at the origin with a Ø20 hole at (50, 0),
a line from side to side, a cross centred inside the hole, a small circle
marked by a consumer inside the plate, a line outside everything; further on a
50×50 small plate with a line inside.
"""

import math
import unittest
from dataclasses import dataclass

import topo
from topo.primitives import LineSeg
from topo import to_shapely

fg = topo.geometry


@dataclass
class _Item:
    """What a caller does with several curves: it keeps them as its own contours."""
    contours: list
    role: str = "pair"


def _drawing():
    doc = topo.load_segments([
        fg.rectangle(200, 100),
        fg.circle(10, center=(50, 0)),
        LineSeg(start=(0, -50), end=(0, 50)),          # from side to side
        LineSeg(start=(45, 0), end=(55, 0)),           # cross in the hole
        LineSeg(start=(50, -5), end=(50, 5)),
        LineSeg(start=(150, 0), end=(180, 0)),         # outside everything
        fg.rectangle(50, 50, center=(400, 0)),
        LineSeg(start=(390, 0), end=(410, 0)),         # inside the small plate
    ])
    mark = topo.load_segments(fg.circle(5, center=(-50, 0)), role="mark")
    doc.edges += mark.edges
    return doc


def _at(result, x, y):
    """The loose curve passing through (x, y)."""
    for curve in result.loose:
        pts = topo.geometry.track_points(curve.segments)
        if any(math.dist(p, (x, y)) < 1e-6 for p in pts):
            return curve
    raise AssertionError(f"no loose curve for ({x}, {y})")


class TestClusterRef(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = topo.heal(_drawing()).faces()

    def test_two_parts_the_plate_is_the_largest(self):
        self.assertEqual(len(self.result.clusters), 2)
        self.assertAlmostEqual(to_shapely(self.result.clusters[0].outer).area, 20000, delta=1)

    def test_line_from_side_to_side_lies_in_the_plate(self):
        self.assertEqual(_at(self.result, 0, -50).cluster_ref, 0)

    def test_cross_in_the_hole_lies_in_the_plate(self):
        self.assertEqual(_at(self.result, 45, 0).cluster_ref, 0)
        self.assertEqual(_at(self.result, 50, 5).cluster_ref, 0)

    def test_marked_closed_curve_lies_in_the_plate(self):
        mark = next(c for c in self.result.loose if c.role == "mark")
        self.assertIsNotNone(to_shapely(mark))
        self.assertEqual(mark.cluster_ref, 0)

    def test_line_outside_everything_has_no_cluster(self):
        self.assertIsNone(_at(self.result, 150, 0).cluster_ref)

    def test_line_in_the_small_plate(self):
        self.assertEqual(_at(self.result, 390, 0).cluster_ref, 1)


class TestPromote(unittest.TestCase):

    def setUp(self):
        self.result = topo.heal(_drawing()).faces()

    def test_moves_from_loose_to_overlay(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        self.result.promote(line, plate, "lines")
        self.assertFalse(any(c is line for c in self.result.loose))
        self.assertIs(plate.overlay.get("lines")[0], line)

    def test_the_caller_attaches_what_they_made_of_it(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        axis = _Item([line], role="axis")
        self.result.promote(line, plate, "axes", item=axis)
        self.assertEqual(plate.overlay.get("axes"), [axis])

    def test_item_without_geometry_raises_and_touches_nothing(self):
        # the curves would leave loose without reaching any file
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        for item in ("axis", ("axis", line), _Item([])):
            with self.assertRaises(ValueError):
                self.result.promote(line, plate, "axes", item=item)
        self.assertTrue(any(c is line for c in self.result.loose))
        self.assertIsNone(plate.overlay)

    def test_also_a_curve_outside_every_cluster(self):
        guide = _at(self.result, 150, 0)
        self.result.promote(guide, self.result.clusters[1], "guides")
        self.assertIs(self.result.clusters[1].overlay.get("guides")[0], guide)

    def test_twice_raises(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        self.result.promote(line, plate, "lines")
        with self.assertRaises(ValueError):
            self.result.promote(line, plate, "lines")
        self.assertEqual(len(plate.overlay.get("lines")), 1)

    def test_cluster_of_another_result_raises(self):
        other = topo.heal(_drawing()).faces().clusters[0]
        line = _at(self.result, 0, -50)
        with self.assertRaises(ValueError):
            self.result.promote(line, other, "lines")
        self.assertTrue(any(c is line for c in self.result.loose))


class TestPromoteGroup(unittest.TestCase):
    """Several curves, a single item: a hole and its seat."""

    def setUp(self):
        self.result = topo.heal(_drawing()).faces()
        self.line = _at(self.result, 0, -50)
        self.guide = _at(self.result, 150, 0)
        self.plate = self.result.clusters[0]
        self.before = len(self.result.loose)

    def test_two_curves_one_item(self):
        pair = _Item([self.line, self.guide])
        self.result.promote([self.line, self.guide], self.plate, "pairs", item=pair)
        self.assertEqual(self.plate.overlay.get("pairs"), [pair])
        self.assertEqual(len(self.result.loose), self.before - 2)
        self.assertFalse(any(c is self.line or c is self.guide for c in self.result.loose))

    def test_a_curve_in_a_list_is_the_curve_itself(self):
        self.result.promote([self.line], self.plate, "lines")
        self.assertIs(self.plate.overlay.get("lines")[0], self.line)

    def test_without_item_raises_and_touches_nothing(self):
        with self.assertRaises(ValueError):
            self.result.promote([self.line, self.guide], self.plate, "pairs")
        self.assertEqual(len(self.result.loose), self.before)
        self.assertIsNone(self.plate.overlay)

    def test_an_absent_curve_does_not_move_the_others(self):
        self.result.promote(self.guide, self.plate, "guides")
        with self.assertRaises(ValueError):
            self.result.promote([self.line, self.guide], self.plate, "pairs", item=_Item([self.line, self.guide]))
        self.assertTrue(any(c is self.line for c in self.result.loose))
        self.assertEqual(self.plate.overlay.get("pairs"), [])

    def test_duplicate_raises(self):
        with self.assertRaises(ValueError):
            self.result.promote([self.line, self.line], self.plate, "pairs", item=_Item([self.line, self.guide]))
        self.assertEqual(len(self.result.loose), self.before)

    def test_void_raises(self):
        with self.assertRaises(ValueError):
            self.result.promote([], self.plate, "pairs", item=_Item([]))


class TestSplit(unittest.TestCase):

    def setUp(self):
        self.result = topo.heal(_drawing()).faces()
        self.outcome = topo.split(self.result)
        self.plate, self.small = self.outcome.parts

    def test_every_curve_goes_to_its_cluster(self):
        self.assertEqual(len(self.plate.loose) + len(self.small.loose) + len(self.outcome.loose),
                         len(self.result.loose))
        refs = [c.cluster_ref for c in self.plate.loose]
        self.assertIn(0, refs)
        self.assertEqual([c.cluster_ref for c in self.small.loose], [0])

    def test_the_outside_one_comes_back_apart_without_cluster_ref(self):
        outside = _at(self.outcome, 150, 0)
        self.assertIsNone(outside.cluster_ref)
        self.assertEqual(len(self.plate.loose) + len(self.small.loose) + len(self.outcome.loose),
                         len(self.result.loose))
        with self.assertRaises(AssertionError):
            _at(self.plate, 150, 0)

    def test_the_original_does_not_change(self):
        self.assertEqual(_at(self.result, 390, 0).cluster_ref, 1)

    def test_a_promoted_curve_travels_with_its_cluster(self):
        result = topo.heal(_drawing()).faces()
        guide = _at(result, 150, 0)
        result.promote(guide, result.clusters[1], "guides")
        outcome = topo.split(result)
        plate, small = outcome.parts
        self.assertEqual(small.clusters[0].overlay.get("guides"), [guide])
        self.assertFalse(any(c.cluster_ref is None for c in plate.loose))
        self.assertEqual(outcome.loose, [])


class TestRotate(unittest.TestCase):

    def test_loose_closed_curve_rotates_with_the_rest(self):
        result = topo.heal(_drawing()).faces()
        rotated = topo.experimental.rotate_result(result, math.pi / 2)
        mark = next(c for c in rotated.loose if c.role == "mark")
        c = to_shapely(mark).centroid
        self.assertAlmostEqual(c.x, 0, places=3)
        self.assertAlmostEqual(c.y, -50, places=3)


if __name__ == "__main__":
    unittest.main()
