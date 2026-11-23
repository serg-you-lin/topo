"""
tests/engine/readings/test_gap.py
-----------
TDD tests for the handling of gaps and overlaps at the corners.

Run:
    python -m pytest tests/engine/readings/test_gap.py -v
"""

import unittest
import math


import topo
import topo_dxf
from tests.paths import DATA, drawing

EXAMPLES_DIR = DATA

W, H  = 100.0, 50.0
AREA  = W * H       # 5000.0
GAP   = 0.1
DELTA = 1.0         # tolerance area mm²


def load(name):
    return topo_dxf.load_dxf(str(drawing(name)))


# --- GAP — LINEs too short ---

class TestGapClose(unittest.TestCase):
    """tolerance > gap → profile closed, correct area."""

    def setUp(self):
        doc = load("rect_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.2).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.clusters[0].area
        self.assertAlmostEqual(area, AREA, delta=DELTA,
                               msg=f"Area {area:.4f} != attesa {AREA}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)


class TestGapNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("rect_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


# --- OVERLAP — LINEs too long ---

class TestOverlapClose(unittest.TestCase):
    """tolerance > overlap → trim at the corners, correct area."""

    def setUp(self):
        doc = load("rect_overlap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.2).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.clusters[0].area
        self.assertAlmostEqual(area, AREA, delta=DELTA,
                               msg=f"Area {area:.4f} != attesa {AREA}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)


class TestOverlapNoClose(unittest.TestCase):
    """tolerance < overlap → the sides cross without a node: faces() does not repair
    them, no part, and nothing is lost."""

    def setUp(self):
        doc = load("rect_overlap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts_nothing_lost(self):
        self.assertEqual(self.result.cluster_count, 0)
        self.assertEqual(len(self.result.loose), 4)
        self.assertTrue(self.result.errors)


# --- Parallel LINEs — missing side ---

class TestParallelClose(unittest.TestCase):
    """C profile (7 LINEs) with a gap between two parallel vertical lines.
    tolerance > gap → adds a closing LINE, closed profile."""

    def setUp(self):
        doc = load("gap_parallelo.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.3).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        print("ERRORS:", self.result.errors)
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)


class TestParallelNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("gap_parallelo.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


# --- ARC + LINE — gap between arc and segment ---

class TestArcLineGapClose(unittest.TestCase):
    """Rectangle with a rounded corner (ARC). 0.1 mm gap between the ARC endpoint and
    the adjacent LINE. tolerance > gap → closed profile, 1 part without holes."""

    def setUp(self):
        doc = load("arc_line_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.2).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)

    def test_004_area_plausible(self):
        """Area must be below the full rectangle W*H."""
        area = self.result.clusters[0].area
        self.assertLess(area, W * H)
        self.assertGreater(area, W * H * 0.8)

class TestArcLineGapNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("arc_line_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


# --- ARC + ARC same circle — two semicircles with a gap ---

class TestArcArcSameCircleClose(unittest.TestCase):
    """Two semicircles of the same circle (r=50) with an angular gap of ~0.11°.
    tolerance > gap → closed profile, area ≈ π*r²."""

    RADIUS_C = 50.0
    AREA_C = math.pi * (RADIUS_C ** 2)
    # Numerical tolerance: includes arc discretization + gap-fix.
    DELTA_C = 5.0

    def setUp(self):
        doc = load("arc_arc_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.2).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_area_correct(self):
        area = self.result.clusters[0].area
        self.assertAlmostEqual(area, self.AREA_C, delta=self.DELTA_C,
                               msg=f"Area {area:.2f} != attesa {self.AREA_C:.2f}")

    def test_004_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)


class TestArcArcSameCircleNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("arc_arc_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


# --- ARC + ARC different circles — two arcs with distinct centres ---

class TestArcArcDifferentCircleClose(unittest.TestCase):
    """Two arcs of different circles with a gap of ~0.2 mm at the endpoints.
    tolerance > gap → closed profile, 1 part without holes."""

    def setUp(self):
        doc = load("arc_open.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.5).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)

    def test_004_area_plausible(self):
        area = self.result.clusters[0].area
        self.assertGreater(area, 100.0)


class TestArcArcDifferentCircleNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("arc_open.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


# --- SPLINE + LINE — gap closed by an extra LINE ---

class TestSplineLineGapClose(unittest.TestCase):
    """Rectangle with a SPLINE left side ending 0.2 mm before the corner.
    tolerance > gap → adds a closing LINE, closed profile.
    Expected area: about W*H (small difference from the spline's curvature)."""

    def setUp(self):
        doc = load("spline_line_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.3).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)

    def test_004_area_plausible(self):
        """Area must be close to W*H — the spline is nearly vertical."""
        area = self.result.clusters[0].area
        self.assertAlmostEqual(area, W * H, delta=50.0,
                               msg=f"Area {area:.2f} far from expected {W*H}")


class TestSplineLineGapNoClose(unittest.TestCase):
    """tolerance < gap → profile not closed."""

    def setUp(self):
        doc = load("spline_line_gap.dxf")
        self.result = topo.heal(doc,
                                 max_gap=0.05).faces()

    def test_001_no_parts(self):
        self.assertEqual(self.result.cluster_count, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)