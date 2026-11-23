"""
test_geometry_loader.py
------------------------
Unit tests for core/geometry_input.py (topo.load_geometry).

It verifies the contract: pure Python dicts → Document → heal() → to_dxf(),
exactly like load_dxf, but without a source file. It covers the two real use
cases: a rectangle with a hole (polyline + circle) and an annular sector like
a cone development (arc + line, with degrees→radians conversion).
"""

import math
import unittest


import topo
import topo_dxf
from topo.core.geometry_input import GeometryReader, load_geometry
from topo.model.role import ContourRole


class TestGeometryReader(unittest.TestCase):

    def test_line_edge_roundtrips_coordinates(self):
        edge = GeometryReader([])._line_edge(
            {"start": (0, 0), "end": (10, 0), "role": "outer"}, ContourRole.OUTER
        )
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (10.0, 0.0))
        self.assertEqual(edge.role, ContourRole.OUTER)

    def test_arc_angles_are_degrees_not_radians(self):
        edge = GeometryReader([])._arc_edge(
            {"center": (0, 0), "radius": 10, "start_angle": 0, "end_angle": 90},
            ContourRole.OUTER,
        )
        # end point 90 degrees from a circle of radius 10 -> (0, 10)
        self.assertAlmostEqual(edge.end[0], 0.0, places=3)
        self.assertAlmostEqual(edge.end[1], 10.0, places=3)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            GeometryReader([{"type": "hexagon"}]).to_edges()

    def test_spline_edge_endpoints_from_control_points(self):
        # clamped spline: the first and last control points are the ends.
        edge = GeometryReader([])._spline_edge(
            {
                "control_points": [(0, 0), (5, 10), (10, 0)],
                "knots": [0, 0, 0, 1, 1, 1],
                "degree": 2,
                "role": "outer",
            },
            ContourRole.OUTER,
        )
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (10.0, 0.0))
        self.assertEqual(edge.role, ContourRole.OUTER)


class TestLoadGeometryRectangleWithHole(unittest.TestCase):
    """Rectangle (closed polyline) with an inner circle — the simple case."""

    def setUp(self):
        self.doc = load_geometry([
            {
                "type": "polygon",
                "points": [(0, 0), (100, 0), (100, 50), (0, 50)],
                "role": "outer",
            },
            {"type": "circle", "center": (20, 25), "radius": 5},
        ])

    def test_returns_topo_document(self):
        self.assertIsInstance(self.doc, topo.Document)
        self.assertTrue(self.doc.edges)

    def test_heal_finds_one_part_with_one_inner(self):
        result = topo.heal(self.doc, label="rect_test").faces()
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.cluster_count, 1)
        cluster = result.clusters[0]
        self.assertAlmostEqual(cluster.outer.area, 100 * 50, delta=1e-6)
        self.assertEqual(len(cluster.inners), 1)

    def test_to_dxf_writes_a_valid_document(self):
        result = topo.heal(self.doc, label="rect_test").faces()
        doc_out = topo_dxf.to_dxf(result)
        self.assertGreater(len(doc_out.modelspace()), 0)


class TestLoadGeometryConeSector(unittest.TestCase):
    """Annular sector (2 arcs + 2 lines) — the same shape as a cone development."""

    def setUp(self):
        r_int, r_est = 10.0, 20.0
        a0, a1 = -45.0, 45.0

        def polar(r, deg):
            rad = math.radians(deg)
            return (r * math.cos(rad), r * math.sin(rad))

        p_int_1, p_est_1 = polar(r_int, a0), polar(r_est, a0)
        p_int_2, p_est_2 = polar(r_int, a1), polar(r_est, a1)

        self.expected_area = (a1 - a0) / 360.0 * math.pi * (r_est**2 - r_int**2)

        self.doc = load_geometry([
            {"type": "arc", "center": (0, 0), "radius": r_est,
             "start_angle": a0, "end_angle": a1, "ccw": True, "role": "outer"},
            {"type": "line", "start": p_est_2, "end": p_int_2, "role": "outer"},
            {"type": "arc", "center": (0, 0), "radius": r_int,
             "start_angle": a1, "end_angle": a0, "ccw": False, "role": "outer"},
            {"type": "line", "start": p_int_1, "end": p_est_1, "role": "outer"},
        ])

    def test_forms_a_single_closed_part_with_correct_area(self):
        result = topo.heal(self.doc, label="cono_sector_test").faces()
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(
            result.clusters[0].outer.area, self.expected_area, delta=self.expected_area * 0.01
        )

    def test_to_dxf_keeps_arcs_native_not_discretized(self):
        result = topo.heal(self.doc, label="cono_sector_test").faces()
        doc_out = topo_dxf.to_dxf(result)
        msp = doc_out.modelspace()
        # write_segments emits an LWPOLYLINE with bulge for a mixed line/arc contour
        # (exact representation, not a discretization) — we only check that the output
        # round does not blow up and produces geometry, the bulge's fidelity is covered elsewhere.
        polylines = list(msp.query("LWPOLYLINE"))
        self.assertEqual(len(polylines), 1)
        self.assertTrue(any(abs(b) > 1e-9 for _, _, _, _, b in polylines[0].get_points()))


class TestLoadGeometrySplineFromSimplifyPoints(unittest.TestCase):
    """The real case that opened the "spline" type: a contour rebuilt by
    topo.experimental.simplify_points() (Smoother) — the resulting BSplineSeg must
    be able to go back into load_geometry() without reinventing its fields by hand."""

    def setUp(self):
        # regular 16-gon: over a scale of 25 it turns ~29°, below the 35° of a corner;
        # sides shorter than the scale -> no line; without arcs -> the whole contour
        # refitted into a single BSplineSeg.
        n, r = 16, 50.0
        points = [
            (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
        segments = topo.experimental.simplify_points(points, tolerance=0.01, scale=25.0, closed=True, arcs=False, corner_turn_deg=35)
        self.assertEqual(len(segments), 1)
        seg = segments[0]

        self.doc = load_geometry([
            {
                "type": "spline",
                "control_points": seg.control_points,
                "knots": seg.knots,
                "degree": seg.degree,
                "role": "outer",
            },
        ])
        # area of the 16-gon the points approximate — reference for the test
        self.polygon_area = 0.5 * n * r * r * math.sin(2 * math.pi / n)

    def test_heal_finds_one_closed_part(self):
        result = topo.heal(self.doc, label="spline_loop_test").faces()
        self.assertTrue(result.is_valid, result.errors)
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(
            result.clusters[0].outer.area, self.polygon_area, delta=self.polygon_area * 0.1
        )

    def test_to_dxf_keeps_spline_native_not_discretized(self):
        result = topo.heal(self.doc, label="spline_loop_test").faces()
        doc_out = topo_dxf.to_dxf(result)
        msp = doc_out.modelspace()
        self.assertEqual(len(list(msp.query("SPLINE"))), 1)
        self.assertEqual(len(list(msp.query("LWPOLYLINE"))), 0)


if __name__ == "__main__":
    unittest.main()
