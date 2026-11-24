"""
test_healer.py
--------------
Unit test for topo.heal().

It verifies only the Result — clusters, inners, holes, trash. It does NOT
verify effects on the msp (layers, colours, LWPOLYLINEs written) → test_writeback.py

Then run:
    python -m pytest tests/engine/readings/test_healer.py -v
"""

import math
import unittest


import topo
import topo_dxf
from tests.paths import DATA

EXAMPLES_DIR = DATA


def load(name):
    return EXAMPLES_DIR / name


# --- 4-LINE rectangle ---

class TestHealerRectLines(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_lines.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_is_valid(self):
        self.assertTrue(self.result.is_valid)

    def test_004_correct_area(self):
        self.assertAlmostEqual(self.result.clusters[0].area, 5000, delta=50)

    def test_005_no_holes(self):
        self.assertEqual(len(self.result.clusters[0].inners), 0)


    


# --- Rectangle with a hole (LINE) ---

class TestHealerRectWithHole(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_with_hole_lines.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_has_hole(self):
        self.assertGreaterEqual(len(self.result.clusters[0].inners), 1)

    def test_003_outer_area(self):
        self.assertAlmostEqual(self.result.clusters[0].outer.area, 20000, delta=200)


# --- Already clean file (LWPOLYLINE) ---

class TestHealerCleanFile(unittest.TestCase):

    def test_001_does_not_crash(self):
        doc = topo_dxf.load_dxf(load("pline_with_hole.dxf"))
        result = topo.heal(doc).faces()
        self.assertIsNotNone(result)

    def test_002_finds_one_part(self):
        doc = topo_dxf.load_dxf(load("pline_with_hole.dxf"))
        result = topo.heal(doc).faces()
        self.assertEqual(len(result.clusters), 1)

    def test_003_has_one_inner(self):
        doc = topo_dxf.load_dxf(load("pline_with_hole.dxf"))
        result = topo.heal(doc).faces()
        self.assertEqual(len(result.clusters[0].inners), 1)


# --- Outer CIRCLE (round flange) ---

class TestHealerCircleOuter(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("circle_outer_with_hole.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_inner_classified(self):
        self.assertGreaterEqual(len(self.result.clusters[0].features("holes")) + len(self.result.clusters[0].inners), 1)


# --- Small CIRCLE → inner contour (a hole is a process reading: snapbend) ---

class TestHealerCircleHole(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_with_circle_hole.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_circle_is_an_inner(self):
        self.assertEqual(len(self.result.clusters[0].inners), 1)
        self.assertEqual(self.result.clusters[0].overlay, None)


# --- Large CIRCLE → INNER (stays an inner contour even after detect) ---

class TestHealerCircleInner(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_with_circle_inner.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_inner_present_and_role(self):
        from topo.model.role import ContourRole
        inners = self.result.clusters[0].inners
        self.assertEqual(len(inners), 1)
        self.assertEqual(inners[0].role, ContourRole.INNER)
        self.assertEqual(len(self.result.clusters[0].features("holes")), 0)


# --- Concentric pair → countersink ---
# heal() sees both CIRCLEs as inners; detect_flat(features="holes") recognizes
# them as a countersink (small → Hole, large ring absorbed).

class TestHealerCountersink(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_with_countersink.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_sees_both_circles_as_inners(self):
        # heal() does not tell a countersink apart — it sees both as inners
        self.assertEqual(len(self.result.clusters[0].features("holes")), 0)
        self.assertGreaterEqual(len(self.result.clusters[0].inners), 2)

    def test_003_area_by_parity(self):
        # Ø30 void (depth 1), Ø10 island inside it (depth 2): the true area is
        # 200·100 − π·15² + π·5², not outer minus the union. Deviation from the polygon
        # within tol × perimeter of the two circles
        c = self.result.clusters[0]
        self.assertEqual(sorted(i.depth for i in c.inners), [1, 2])
        exact = 200 * 100 - math.pi * 15 ** 2 + math.pi * 5 ** 2
        self.assertAlmostEqual(c.area, exact, delta=0.01 * 2 * math.pi * (15 + 5))


# --- Outer LWPOLYLINE + inner LINE loop ---

class TestHealerInnerLoopInsideLwpolyline(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_with_inner_mark.dxf"))
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_inner_loop_classified_as_inner(self):
        self.assertEqual(len(self.result.clusters[0].inners), 1)


# --- Deduplication of duplicate entities ---

class TestHealerDeduplication(unittest.TestCase):

    def setUp(self):
        doc = topo_dxf.load_dxf(load("rect_lines_duplicated.dxf"), explode_inserts=True)
        self.result = topo.heal(doc).faces()

    def test_001_finds_one_part(self):
        self.assertEqual(len(self.result.clusters), 1)

    def test_002_no_errors(self):
        self.assertEqual(len(self.result.errors), 0)

    def test_003_correct_area(self):
        self.assertAlmostEqual(self.result.clusters[0].area, 5000, delta=50)


# ---------------------------------------------------------------------------
# Validate input (Document)
# ---------------------------------------------------------------------------

class TestValidateInput(unittest.TestCase):

    def test_001_open_lines_no_forecast(self):
        # lines that heal() will close: no fact to state about the input, and a
        # forecast about heal() is no longer made by validate_document
        check = topo.validate_document(topo_dxf.load_dxf(load("rect_lines.dxf")))
        self.assertEqual(check.warnings, [])
        self.assertTrue(check.is_valid)

    def test_001b_null_stretch_and_void_document(self):
        g = topo.geometry
        doc = topo.load_segments(g.rectangle(10, 10) + [topo.primitives.LineSeg(start=(3, 3), end=(3, 3))])
        check = topo.validate_document(doc)
        self.assertEqual([(w.code, w.at) for w in check.warnings], [("zero-length", (3.0, 3.0))])
        empty = topo.validate_document(topo.load_segments([]))
        self.assertEqual([e.code for e in empty.errors], ["empty"])
        self.assertFalse(empty.is_valid)

    def test_002_clean_file_no_errors(self):
        check = topo.validate_document(topo_dxf.load_dxf(load("pline_with_hole.dxf")))
        self.assertEqual(len(check.errors), 0)
        self.assertTrue(check.is_valid)


if __name__ == "__main__":
    unittest.main(verbosity=2)