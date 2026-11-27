"""
tests/adapters/dxf/test_degenerate_curves.py
-------------------------------------------
A curve of zero measure (ARC or CIRCLE of radius 0, a null chord with bulge in
a polyline) is a point, not a curve. The primitive rejects it; loading goes on
and reports it in `doc.warnings`, instead of stopping on the whole drawing
(CIRCLE) or crashing downstream in `discretize` (ARC). The same for a NaN or
infinite coordinate: no position, no curve. ezdxf is used here only to write
the degenerate entity the file carries: topo's APIs do not build it, and that
is the point.
"""

import math
import unittest

import ezdxf

import topo
import topo_dxf
from topo.primitives import BSplineSeg, CircleSeg, EllipseSeg, LineSeg


class TestDegeneratePrimitives(unittest.TestCase):

    def test_001_arc_of_radius_0_refused(self):
        with self.assertRaises(ValueError):
            CircleSeg((1.0, 2.0), 0.0, 0.0, 1.0)

    def test_002_null_chord_refused(self):
        # numpy divides 0/0 without error: before, a NaN arc of radius 0 came out
        import numpy as np
        p = (np.float64(2.0), np.float64(2.0))
        with self.assertRaises(ValueError):
            CircleSeg.from_ends(p, p, 4 * math.atan(0.5))

    def test_003_degenerate_ellipse_refused(self):
        with self.assertRaises(ValueError):
            EllipseSeg((0.0, 0.0), (0.0, 0.0), 0.5, 0.0, 2 * math.pi)
        with self.assertRaises(ValueError):
            EllipseSeg((0.0, 0.0), (10.0, 0.0), 0.0, 0.0, 2 * math.pi)

    def test_004_non_finite_coordinate_refused(self):
        nan, inf = math.nan, math.inf
        for build in (lambda: LineSeg((nan, 0.0), (1.0, 1.0)),
                      lambda: CircleSeg((0.0, inf), 1.0, 0.0, 1.0),
                      lambda: CircleSeg((0.0, 0.0), 1.0, nan, 1.0),
                      lambda: CircleSeg((0.0, 0.0), inf),
                      lambda: EllipseSeg((0.0, 0.0), (10.0, 0.0), 0.5, 0.0, inf),
                      lambda: BSplineSeg(2, [(0.0, 0.0), (1.0, nan), (2.0, 0.0)], [0, 0, 0, 1, 1, 1]),
                      lambda: BSplineSeg(2, [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)], [0, 0, 0, 1, 1, 1],
                                         [1.0, inf, 1.0])):
            with self.assertRaises(ValueError):
                build()


class TestNonFiniteEntitiesInADrawing(unittest.TestCase):

    def test_001_drawing_loads_and_warns(self):
        msp = ezdxf.new().modelspace()
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
        msp.add_line((math.nan, 0), (5, 5))
        msp.add_circle((math.inf, 1), 2)
        doc = topo_dxf.document_from_msp(msp)
        [warning] = [w for w in doc.warnings if w.code == "dxf-no-curve"]
        self.assertEqual(warning.message, "entities with no curve left out: 2")
        self.assertEqual(warning.notes[:2], ("1 CIRCLE", "1 LINE"))
        result = topo.heal(doc).faces()
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.clusters), 1)


class TestDegenerateEntitiesInADrawing(unittest.TestCase):

    def setUp(self):
        msp = ezdxf.new().modelspace()
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
        msp.add_arc((3, 3), 0, 0, 90)
        msp.add_circle((6, 6), 0)
        # repeated vertex with bulge: a null chord
        msp.add_lwpolyline([(2, 2, 0.5), (2, 2, 0), (4, 4, 0)], format="xyb")
        self.doc = topo_dxf.document_from_msp(msp)

    def test_001_drawing_loads_and_warns(self):
        [warning] = [w for w in self.doc.warnings if w.code == "dxf-no-curve"]
        self.assertEqual(warning.message, "entities with no curve left out: 2")
        self.assertEqual(warning.notes[:2], ("1 ARC", "1 CIRCLE"))

    def test_002_only_the_true_geometry_remains(self):
        result = topo.heal(self.doc).faces()
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(len(result.loose), 1)    # the stretch (2,2)-(4,4)
        for curve in result.loose:
            for seg in curve.segments:
                self.assertFalse(any(math.isnan(c) for p in seg.discretize() for c in p))


if __name__ == "__main__":
    unittest.main()
