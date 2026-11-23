"""
tests/adapters/dxf/test_ellipse_roundtrip.py
---------------------------------------------
End-to-end test (real ezdxf, not a mock) for ELLIPSE: load -> heal -> to_dxf
-> reload, for a full (standalone) ellipse and an elliptical arc mixed with
lines. It verifies that the ELLIPSE comes out native in output (never
discretized to a spline) and that the roundtrip reproduces the same geometry.

Run:
    python -m pytest tests/adapters/dxf/test_ellipse_roundtrip.py -v
"""

import math
import unittest

import ezdxf

import topo
import topo_dxf


class TestFullEllipseOuter(unittest.TestCase):
    """A full ELLIPSE, the file's only geometry: one cluster, elliptical outer."""

    def setUp(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_ellipse(center=(5, 5), major_axis=(10, 0), ratio=0.5)
        self.fdoc = topo_dxf.document_from_msp(msp)
        self.result = topo.heal(self.fdoc).faces()

    def test_001_one_valid_cluster(self):
        self.assertTrue(self.result.is_valid)
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_area_matches_ellipse_formula(self):
        # area = pi * a * b, a=10 (semi-major axis), b=5 (ratio 0.5)
        expected = math.pi * 10 * 5
        area = self.result.clusters[0].outer.area
        self.assertAlmostEqual(area, expected, delta=1.0)

    def test_003_writes_native_ellipse(self):
        doc_out = topo_dxf.to_dxf(self.result, self.fdoc)
        ellipses = list(doc_out.modelspace().query("ELLIPSE"))
        self.assertEqual(len(ellipses), 1)
        e = ellipses[0]
        self.assertAlmostEqual(e.dxf.center.x, 5.0, places=6)
        self.assertAlmostEqual(e.dxf.center.y, 5.0, places=6)
        self.assertAlmostEqual(e.dxf.major_axis.x, 10.0, places=6)
        self.assertAlmostEqual(e.dxf.major_axis.y, 0.0, places=6)
        self.assertAlmostEqual(e.dxf.ratio, 0.5, places=6)

    def test_004_no_spline_written(self):
        """An ellipse must never come out as a SPLINE — it is an exact conic, not an
        approximation (the same principle as splines never discretized)."""
        doc_out = topo_dxf.to_dxf(self.result, self.fdoc)
        self.assertEqual(len(list(doc_out.modelspace().query("SPLINE"))), 0)

    def test_005_roundtrip_area_stable(self):
        """Reloading the output with topo itself finds the same area."""
        doc_out = topo_dxf.to_dxf(self.result, self.fdoc)
        reloaded = topo.heal(topo_dxf.document_from_msp(doc_out.modelspace())).faces()
        self.assertEqual(reloaded.cluster_count, 1)
        self.assertAlmostEqual(
            reloaded.clusters[0].outer.area,
            self.result.clusters[0].outer.area,
            delta=0.5,
        )


class TestEllipticalArcMixedWithLines(unittest.TestCase):
    """A quarter ellipse (open arc) + 2 LINEs close a contour."""

    def setUp(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        # quarter ellipse from (20,0) to (0,10) — CCW, param 0 -> pi/2
        msp.add_ellipse(center=(0, 0), major_axis=(20, 0), ratio=0.5,
                         start_param=0.0, end_param=math.pi / 2)
        msp.add_line((0, 10), (0, 0))
        msp.add_line((0, 0), (20, 0))
        self.fdoc = topo_dxf.document_from_msp(msp)
        self.result = topo.heal(self.fdoc).faces()

    def test_001_closes_into_one_valid_cluster(self):
        self.assertTrue(self.result.is_valid, self.result.errors)
        self.assertEqual(self.result.cluster_count, 1)

    def test_002_area_matches_quarter_ellipse(self):
        # sector bounded by the two semi-axes and the arc = a quarter of the ellipse's
        # total area (a=20, b=10)
        expected = 0.25 * math.pi * 20 * 10
        area = self.result.clusters[0].outer.area
        self.assertAlmostEqual(area, expected, delta=1.0)

    def test_003_writes_native_ellipse_not_spline(self):
        doc_out = topo_dxf.to_dxf(self.result, self.fdoc)
        msp_out = doc_out.modelspace()
        self.assertEqual(len(list(msp_out.query("ELLIPSE"))), 1)
        self.assertEqual(len(list(msp_out.query("SPLINE"))), 0)

    def test_004_roundtrip_area_stable(self):
        doc_out = topo_dxf.to_dxf(self.result, self.fdoc)
        reloaded = topo.heal(topo_dxf.document_from_msp(doc_out.modelspace())).faces()
        self.assertEqual(reloaded.cluster_count, 1)
        self.assertAlmostEqual(
            reloaded.clusters[0].outer.area,
            self.result.clusters[0].outer.area,
            delta=0.5,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
