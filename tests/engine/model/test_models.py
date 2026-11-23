
"""
Test Suite for topo_dxf.models

Pure tests on the data models — they do not require DXF files.

Run:
    python -m unittest tests/test_models.py -v
"""

import unittest


from shapely.geometry import Polygon, LineString, Point

from topo.model import (
    Contour,
    Cluster,
    Result,
    Edge,
)
from topo.model import Overlay
import topo

from topo.model.role import ContourRole
from topo.core.primitives.line import LineSeg

# --- Minimal fake entity — isolates the tests from ezdxf ---

def _ring(polygon):
    return topo.geometry.polygon(polygon.exterior.coords)


class _Void:
    """An overlay element a consumer declares a void of the part."""
    is_void = True
    role = "my_void"

    def __init__(self, segments):
        self.segments = segments


class _FakeEntity:
    """Minimal ezdxf entity for tests that require an entity reference."""
    pass


# ---------------------------------------------------------------------------
# Test Contour
# ---------------------------------------------------------------------------

class TestForgeContour(unittest.TestCase):

    def test_001_area(self):
        """Area computed correctly."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = Contour(segments=_ring(poly), role="outer")
        print(f"\n[Contour] area={contour.area}")
        self.assertEqual(contour.area, 100.0)

    def test_002_bbox(self):
        """Bbox computed correctly."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = Contour(segments=_ring(poly), role="outer")
        print(f"[Contour] bbox={contour.bbox}")
        self.assertEqual(contour.bbox, (0, 0, 10, 10))

    def test_003_role_unknown_preserved(self):
        """role UNKNOWN is a valid value and is preserved."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = Contour(role=ContourRole.UNKNOWN, segments=_ring(poly))
        self.assertEqual(contour.role, ContourRole.UNKNOWN)

    def test_004_role_inner(self):
        """inner role assigned correctly."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = Contour(segments=_ring(poly), role="inner")
        self.assertEqual(contour.role, "inner")

    def test_005_role_preserved(self):
        """Role preserved correctly."""
        poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
        contour = Contour(segments=_ring(poly), role="outer")
        self.assertEqual(contour.role, "outer")

    def test_006_repr_without_the_parent(self):
        """The parent is printed where it is: inside the child the print would grow at every level."""
        outer = Contour(segments=_ring(Polygon([(0,0), (10,0), (10,10), (0,10)])), role="outer")
        inner = Contour(segments=_ring(Polygon([(2,2), (4,2), (4,4), (2,4)])), role="inner",
                        depth=1, parent=outer)
        self.assertNotIn("parent", repr(inner))
        self.assertIs(inner.parent, outer)


# ---------------------------------------------------------------------------
# Test Edge
# ---------------------------------------------------------------------------

class TestEdge(unittest.TestCase):
    """After the refactoring Edge is pure data: role + start/end + segment (native
    primitive) + style. No source_ref, layer or geometry."""

    def _seg(self, start=(0.0, 0.0), end=(100.0, 0.0)):
        return LineSeg(start=start, end=end)

    def test_001_construction(self):
        """Edge correctly built with minimal fields."""
        seg = self._seg()
        edge = Edge(
            role=ContourRole.OUTER,
            start=(0.0, 0.0),
            end=(100.0, 0.0),
            segment=seg,
        )
        print(f"\n[Edge] start={edge.start} end={edge.end} role={edge.role}")
        self.assertEqual(edge.start, (0.0, 0.0))
        self.assertEqual(edge.end, (100.0, 0.0))
        self.assertEqual(edge.role, ContourRole.OUTER)

    def test_002_segment_reference_preserved(self):
        """The geometric primitive passed is not replaced."""
        seg = self._seg()
        edge = Edge(role=ContourRole.UNKNOWN, start=(0, 0), end=(1, 1), segment=seg)
        self.assertIs(edge.segment, seg)

    def test_005_role_preserved(self):
        """role cached on the Edge — assigned by the adapter, never from the DXF layer."""
        edge = Edge(role="bending", start=(0, 0), end=(1, 0),
                    segment=self._seg((0, 0), (1, 0)))
        self.assertEqual(edge.role, "bending")

    def test_006_start_end_are_tuples(self):
        """start and end are (x, y) tuples."""
        edge = Edge(role=ContourRole.UNKNOWN, start=(5.0, 10.0), end=(15.0, 20.0),
                    segment=self._seg((5.0, 10.0), (15.0, 20.0)))
        self.assertEqual(len(edge.start), 2)
        self.assertEqual(len(edge.end), 2)


# ---------------------------------------------------------------------------
# Test Cluster
# ---------------------------------------------------------------------------

class TestForgeCluster(unittest.TestCase):

    def _make_outer(self, coords=None):
        if coords is None:
            coords = [(0,0), (100,0), (100,100), (0,100)]
        return Contour(role=ContourRole.OUTER, segments=_ring(Polygon(coords)))

    def test_001_no_holes_area(self):
        """Correct area without holes."""
        cluster = Cluster(outer=self._make_outer(), label="test")
        print(f"\n[Cluster] area={cluster.area}, holes={len(cluster.features('holes'))}")
        self.assertEqual(cluster.area, 10000.0)

    def test_002_no_holes_count(self):
        """Empty hole list by default."""
        cluster = Cluster(outer=self._make_outer(), label="test")
        self.assertEqual(len(cluster.features("holes")), 0)

    def test_003_with_hole_net_area(self):
        """Net area = outer - an overlay void (is_void)."""
        import math
        outer = self._make_outer()
        cluster = Cluster(outer=outer, overlay=Overlay())
        cluster.overlay.attach("holes", [_Void(topo.geometry.circle(5.0, center=(50, 50)))])
        expected = 10000.0 - math.pi * 25.0
        print(f"\n[Cluster with hole] area={cluster.area:.4f} expected≈{expected:.4f}")
        self.assertAlmostEqual(cluster.area, expected, delta=0.01)

    def test_004_to_shapely_with_void(self):
        """to_shapely removes the overlay's void from the material."""
        outer = self._make_outer()
        cluster = Cluster(outer=outer, overlay=Overlay())
        cluster.overlay.attach("holes", [_Void(topo.geometry.circle(5.0, center=(50, 50)))])
        result_poly = topo.to_shapely(cluster)
        print(f"[Cluster] interiors={len(list(result_poly.interiors))}")
        self.assertEqual(len(list(result_poly.interiors)), 1)

    def test_005_bbox(self):
        """Bbox matches the outer."""
        cluster = Cluster(outer=self._make_outer())
        print(f"[Cluster] bbox={cluster.bbox}")
        self.assertEqual(cluster.bbox, (0, 0, 100, 100))

    def test_006_bending_lines_default_empty(self):
        """bending_lines is an empty list by default."""
        cluster = Cluster(outer=self._make_outer())
        self.assertIsInstance(cluster.features("bending_lines"), list)
        self.assertEqual(len(cluster.features("bending_lines")), 0)

    def test_007_engrave_lines_default_empty(self):
        """engrave_lines is an empty list by default."""
        cluster = Cluster(outer=self._make_outer())
        self.assertIsInstance(cluster.features("engrave_lines"), list)
        self.assertEqual(len(cluster.features("engrave_lines")), 0)

    def test_008_to_dict_geometry_only(self):
        """to_dict gives the geometric facts, no coordinates nor process fields."""
        cluster = Cluster(outer=self._make_outer())
        d = cluster.to_dict()
        self.assertEqual(set(d), {"label", "area", "outer_perimeter", "inner_perimeter",
                                  "inner_count", "bbox", "overlay"})
        self.assertEqual(d["overlay"], {})

    def test_009_inners_independent(self):
        """Two Clusters do not share the same inners list."""
        p1 = Cluster(outer=self._make_outer())
        p2 = Cluster(outer=self._make_outer())
        inner_poly = Polygon([(10,10), (20,10), (20,20), (10,20)])
        p1.inners.append(Contour(role=ContourRole.INNER, segments=_ring(inner_poly)))
        print(f"[Cluster] p1.inners={len(p1.inners)} p2.inners={len(p2.inners)}")
        self.assertEqual(len(p2.inners), 0)


# ---------------------------------------------------------------------------
# Test Result
# ---------------------------------------------------------------------------

class TestForgeResult(unittest.TestCase):

    def _make_result(self):
        outer_poly = Polygon([(0,0), (50,0), (50,50), (0,50)])
        outer = Contour(role=ContourRole.OUTER, segments=_ring(outer_poly))
        cluster  = Cluster(outer=outer, label="piece_1", source_file="test.dxf")
        return Result(clusters=[cluster], source_file="test.dxf")

    def test_001_part_count(self):
        """cluster_count correct."""
        result = self._make_result()
        print(f"\n[Result] cluster_count={result.cluster_count}")
        self.assertEqual(result.cluster_count, 1)

    def test_002_is_valid_default(self):
        """is_valid is True by default."""
        result = self._make_result()
        self.assertTrue(result.is_valid)

    def test_003_has_issues_false(self):
        """has_issues is False without warnings or errors."""
        result = self._make_result()
        self.assertFalse(result.has_issues)

    def test_004_has_issues_true(self):
        """has_issues is True if there are warnings."""
        result = self._make_result()
        result.warnings.append("something is wrong")
        print(f"[Result] has_issues={result.has_issues}")
        self.assertTrue(result.has_issues)

    def test_005_to_dict_keys(self):
        """to_dict has the right keys."""
        result = self._make_result()
        d = result.to_dict()
        print(f"[Result] keys={list(d.keys())}")
        self.assertIn("clusters", d)
        self.assertIn("source_format", d)
        self.assertIn("reading", d)
        self.assertIn("is_valid", d)
        self.assertIn("source_file", d)

    def test_006_to_dict_values(self):
        """to_dict ha i valori corretti."""
        result = self._make_result()
        d = result.to_dict()
        print(f"[Result] cluster label={d['clusters'][0]['label']}")
        self.assertEqual(len(d["clusters"]), 1)
        self.assertEqual(d["clusters"][0]["label"], "piece_1")
        self.assertTrue(d["is_valid"])


class TestDiagnostic(unittest.TestCase):
    """A warning is a str in the Rust format, with the fields for whoever programs."""

    def _d(self):
        from topo.model import Diagnostic
        return Diagnostic("open-arc", "arc left open", points=[(1, 2)], notes=["5.68° missing"],
                          help="close_near_full_arcs(...)", param="max_missing_angle", value=0.099)

    def test_the_text_is_rusts(self):
        self.assertEqual(self._d(), "warning[open-arc]: arc left open\n  --> (1.000, 2.000)\n"
                                    "  = note: 5.68° missing\n  = help: close_near_full_arcs(...)")

    def test_one_per_type_the_text_shows_three_points_points_all(self):
        from topo.model import Diagnostic
        d = Diagnostic("near-gap", "5 gaps", points=[(k, 0) for k in range(5)])
        self.assertEqual((len(d.points), d.at, str(d).count("-->")), (5, (0.0, 0.0), 3))
        self.assertIn("... and 2 more in .points", d)

    def test_copy_and_pickle_keep_the_fields(self):
        import copy
        import pickle
        for d in (copy.deepcopy(self._d()), pickle.loads(pickle.dumps(self._d()))):
            self.assertEqual((d, d.code, d.at, d.param, d.value), (self._d(), "open-arc", (1.0, 2.0), "max_missing_angle", 0.099))


if __name__ == "__main__":
    unittest.main(verbosity=2)