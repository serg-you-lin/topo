"""
tests/engine/readings/test_diagnostic_texts.py

A diagnostic says only what the geometry shows: the causes of `no-closed-outer`
are those the network holds, `self-intersecting` points at the crossing, a count
of one reads in the singular and a length carries its unit.
"""

import unittest

import topo
from topo.primitives import LineSeg
from topo.model import Cluster, Contour, ContourRole, Result

BOW_TIE = [LineSeg((0, 0), (10, 10)), LineSeg((10, 10), (10, 0)),
           LineSeg((10, 0), (0, 10)), LineSeg((0, 10), (0, 0))]


class TestNoClosedOuterCauses(unittest.TestCase):

    def test_a_crossing_not_cut_is_the_cause_not_free_ends(self):
        result = topo.heal(topo.load_segments(BOW_TIE)).faces()
        [error] = [e for e in result.errors if e.code == "no-closed-outer"]
        self.assertEqual(error.points, ((5.0, 5.0),))
        self.assertEqual(len(error.notes), 1)
        self.assertIn("crossing", error.notes[0])
        self.assertNotIn("free end", error.notes[0])

    def test_an_open_line_is_two_free_ends(self):
        result = topo.heal(topo.load_segments([LineSeg((0, 0), (10, 0))])).faces()
        [error] = [e for e in result.errors if e.code == "no-closed-outer"]
        self.assertEqual(error.notes, ("2 free ends meet nothing within max_gap",))


class TestSelfIntersectingPoint(unittest.TestCase):

    def test_the_point_is_the_crossing(self):
        outer = Contour(ContourRole.OUTER, segments=list(BOW_TIE))
        result = Result(clusters=[Cluster(outer=outer)])
        topo.validate_result(result)
        [warning] = [w for w in result.warnings if w.code == "self-intersecting"]
        self.assertEqual(warning.points, ((5.0, 5.0),))


class TestPointsOnAnyPrimitive(unittest.TestCase):

    def test_a_dropped_circle_part_is_reported_at_its_start(self):
        segs = topo.geometry.rectangle(100, 50) + topo.geometry.circle(1, center=(200, 0))
        result = topo.heal(topo.load_segments(segs)).faces()
        topo.split(result, min_area=10)
        [warning] = [w for w in result.warnings if w.code == "dropped-part"]
        self.assertEqual(warning.points, ((201.0, 0.0),))

    def test_polygons_of_near_tangent_curves_are_no_crossing(self):
        # a circle inside a square, tangent to two sides: the outer is the square,
        # its ring does not cross itself
        segs = topo.geometry.rectangle(10, 10) + topo.geometry.circle(5)
        result = topo.heal(topo.load_segments(segs)).faces()
        self.assertEqual([w.code for w in result.warnings if w.code == "self-intersecting"], [])

    def test_a_curl_is_reported_where_it_crosses(self):
        pts = [(0, 0), (10, 0), (10, 10), (4, 10), (4, 4), (6, 4), (6, 12), (0, 12)]
        ring = [LineSeg(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        result = Result(clusters=[Cluster(outer=Contour(ContourRole.OUTER, segments=ring))])
        topo.validate_result(result)
        [warning] = [w for w in result.warnings if w.code == "self-intersecting"]
        self.assertEqual(warning.points, ((6.0, 10.0),))


class TestCountsAndUnits(unittest.TestCase):

    def test_one_free_end_in_the_singular_with_mm(self):
        segs = topo.geometry.rectangle(100, 50) + [LineSeg((0, -25), (0, -15))]
        result = topo.heal(topo.load_segments(segs)).faces()
        [note] = [n for n in result.notes if n.code == "free-end"]
        self.assertEqual(note.message, "1 free end that closes nothing, in loose")
        self.assertEqual(note.notes, ("10 mm from the nearest node",))


if __name__ == "__main__":
    unittest.main()
