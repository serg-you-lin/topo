# tests/engine/geometry/test_lines.py
"""`splits_contour`, `bridged_runs`, `point_line_distance`: facts between lines and contours."""

import math
import unittest

import topo
from topo.core.geometry.lines import CollinearRun, are_collinear, bridged_runs, point_line_distance, splits_contour

PART = topo.Contour(segments=topo.geometry.rectangle(100, 50, center=(50, 25)), role="outer")


class TestSplitsContour(unittest.TestCase):

    def test_chord_from_border_to_border(self):
        self.assertTrue(splits_contour(PART, (40, 0), (40, 50)))

    def test_chord_not_reaching_the_border_divides_it_by_extension(self):
        self.assertFalse(splits_contour(PART, (40, 0.5), (40, 49.5)))
        self.assertTrue(splits_contour(PART, (40, 0.5), (40, 49.5), reach=1.0))

    def test_inner_stretch_does_not_divide(self):
        self.assertFalse(splits_contour(PART, (40, 10), (40, 20), reach=1.0))

    def test_degenerate_stretch(self):
        self.assertFalse(splits_contour(PART, (40, 10), (40, 10), reach=1.0))


class TestBridgedRuns(unittest.TestCase):

    HOLE = topo.geometry.rectangle(4, 10, center=(40, 25))

    def test_two_stretches_joined_through_a_hole(self):
        segments = [((40, 30), (40, 50)), ((40, 0), (40, 20))]
        (run,) = bridged_runs(segments, [self.HOLE], tolerance=0.1)
        self.assertEqual(run, CollinearRun((40, 0), (40, 50), (1, 0)))

    def test_space_outside_the_hole_does_not_join(self):
        segments = [((40, 0), (40, 15)), ((40, 30), (40, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE], tolerance=0.1), [])

    def test_stretches_on_different_lines(self):
        segments = [((40, 0), (40, 20)), ((41, 30), (41, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE], tolerance=0.1), [])

    def test_lineseg_as_stroke_and_contour_as_bridge(self):
        segments = [topo.primitives.LineSeg((40, 0), (40, 20)), topo.primitives.LineSeg((40, 30), (40, 50))]
        hole = topo.Contour(segments=self.HOLE, role="inner")
        self.assertEqual(len(bridged_runs(segments, [hole], tolerance=0.1)), 1)

    def test_round_bridge(self):
        # the space passes inside a circle Ø12: the true border, not the chords
        segments = [((40, 0), (40, 19)), ((40, 31), (40, 50))]
        self.assertEqual(len(bridged_runs(segments, [topo.geometry.circle(6.0, center=(40, 25))], tolerance=0.1)), 1)

    def test_public_api(self):
        self.assertIs(topo.geometry.bridged_runs, bridged_runs)
        self.assertIs(topo.geometry.splits_contour, splits_contour)


class TestLineFacts(unittest.TestCase):

    def test_distance_from_the_line(self):
        self.assertAlmostEqual(point_line_distance((0, 3), (-5, 0), (5, 0)), 3)
        self.assertAlmostEqual(point_line_distance((3, 4), (0, 0), (0, 0)), 5)

    def test_the_direction_deviation_is_in_the_distance(self):
        # no separate angle, the far end of b deviates by 0.06
        a, b = ((0, 0), (100, 0)), ((0, 0.01), (100, 0.06))
        self.assertTrue(are_collinear(a, b, 0.1))
        self.assertFalse(are_collinear(a, b, 0.05))


if __name__ == "__main__":
    unittest.main()


class TestParallelFamilies(unittest.TestCase):

    def _hatching(self):
        # ten lines at 45 degrees, step 3 along the normal, one split in two, one missing
        u = (math.sqrt(0.5), math.sqrt(0.5))
        n = (-u[1], u[0])
        strokes = []
        for k in (0, 1, 2, 4, 5, 6, 7, 8, 9):
            o = 3 * k
            a, b = (o * n[0], o * n[1]), (o * n[0] + 10 * u[0], o * n[1] + 10 * u[1])
            if k == 5:
                m = (a[0] + 4 * u[0], a[1] + 4 * u[1])
                strokes += [(a, m), (m, b)]
            else:
                strokes.append((a, b))
        return strokes

    def test_rows_and_their_distances(self):
        (family,) = topo.experimental.parallel_families(self._hatching(), tolerance=0.01)
        self.assertEqual(len(family.rows), 9)
        for row, k in zip(family.rows, (0, 1, 2, 4, 5, 6, 7, 8, 9)):
            self.assertAlmostEqual(row.offset, 3 * k, places=9)

    def test_a_split_line_is_one_row(self):
        (family,) = topo.experimental.parallel_families(self._hatching(), tolerance=0.01)
        split = [r for r in family.rows if len(r.members) == 2]
        self.assertEqual(len(split), 1)
        (lo1, hi1), (lo2, hi2) = split[0].intervals
        self.assertAlmostEqual(hi1, lo2, places=9)

    def test_a_stroke_and_its_reverse_are_the_same_family(self):
        fams = topo.experimental.parallel_families([((0, 0), (5, 2)), ((5, 5), (0, 3))], tolerance=0.01)
        self.assertEqual(len(fams), 1)
        self.assertEqual(len(fams[0].rows), 2)

    def test_other_directions_make_other_families(self):
        fams = topo.experimental.parallel_families([((0, 0), (5, 0)), ((0, 0), (0, 5)), ((0, 2), (5, 2))], tolerance=0.01)
        self.assertEqual([len(f.rows) for f in fams], [2, 1])

    def test_nearly_parallel_beyond_tolerance_is_not_the_family(self):
        fams = topo.experimental.parallel_families([((0, 0), (100, 0)), ((0, 5), (100, 6))], tolerance=0.5)
        self.assertEqual(len(fams), 2)
