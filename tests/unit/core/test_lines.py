# tests/unit/core/test_lines.py
"""`splits_contour`, `bridged_runs`, `point_line_distance`: fatti fra rette e contorni (D93, D166)."""

import unittest

import topo
from topo.core.geometry.lines import CollinearRun, are_collinear, bridged_runs, point_line_distance, splits_contour

PART = topo.Contour(segments=topo.geometry.rectangle(100, 50, (50, 25)), role="outer")


class TestSplitsContour(unittest.TestCase):

    def test_corda_da_bordo_a_bordo(self):
        self.assertTrue(splits_contour(PART, (40, 0), (40, 50)))

    def test_corda_che_non_arriva_al_bordo_lo_divide_col_prolungamento(self):
        self.assertFalse(splits_contour(PART, (40, 0.5), (40, 49.5)))
        self.assertTrue(splits_contour(PART, (40, 0.5), (40, 49.5), reach=1.0))

    def test_tratto_interno_non_divide(self):
        self.assertFalse(splits_contour(PART, (40, 10), (40, 20), reach=1.0))

    def test_tratto_degenere(self):
        self.assertFalse(splits_contour(PART, (40, 10), (40, 10), reach=1.0))


class TestBridgedRuns(unittest.TestCase):

    HOLE = topo.geometry.rectangle(4, 10, (40, 25))

    def test_due_tratti_uniti_attraverso_un_foro(self):
        segments = [((40, 30), (40, 50)), ((40, 0), (40, 20))]
        (run,) = bridged_runs(segments, [self.HOLE])
        self.assertEqual(run, CollinearRun((40, 0), (40, 50), (1, 0)))

    def test_spazio_fuori_dal_foro_non_unisce(self):
        segments = [((40, 0), (40, 15)), ((40, 30), (40, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE]), [])

    def test_tratti_su_rette_diverse(self):
        segments = [((40, 0), (40, 20)), ((41, 30), (41, 50))]
        self.assertEqual(bridged_runs(segments, [self.HOLE]), [])

    def test_lineseg_come_tratto_e_contorno_come_ponte(self):
        segments = [topo.primitives.LineSeg((40, 0), (40, 20)), topo.primitives.LineSeg((40, 30), (40, 50))]
        hole = topo.Contour(segments=self.HOLE, role="inner")
        self.assertEqual(len(bridged_runs(segments, [hole])), 1)

    def test_ponte_rotondo(self):
        # lo spazio passa dentro un cerchio Ø12: il bordo vero, non le corde
        segments = [((40, 0), (40, 19)), ((40, 31), (40, 50))]
        self.assertEqual(len(bridged_runs(segments, [topo.geometry.circle(6.0, (40, 25))])), 1)

    def test_api_pubblica(self):
        self.assertIs(topo.geometry.bridged_runs, bridged_runs)
        self.assertIs(topo.geometry.splits_contour, splits_contour)


class TestLineFacts(unittest.TestCase):

    def test_distanza_dalla_retta(self):
        self.assertAlmostEqual(point_line_distance((0, 3), (-5, 0), (5, 0)), 3)
        self.assertAlmostEqual(point_line_distance((3, 4), (0, 0), (0, 0)), 5)

    def test_collineari_con_tolleranza_angolare(self):
        a, b = ((0, 0), (100, 0)), ((0, 0.01), (100, 0.06))
        self.assertFalse(are_collinear(a, b))
        self.assertTrue(are_collinear(a, b, angle_tolerance=1e-3))


if __name__ == "__main__":
    unittest.main()
