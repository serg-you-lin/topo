"""
test_loops.py
-------------
Tests for topo_dxf.core.topology.loops — LoopFinder and classify_loops.

The tests verify:
- search of closed loops (LoopFinder.find)
- CCW orientation
- arc handling
- outer/inner classification
- dead-end pruning (via Graph.pruned)
- stubs on broken concave arcs: recovery via the full pipeline
"""

import unittest
import math

from shapely.geometry import LinearRing, Polygon, LineString

# Path setup for imports from the project

from topo.core.topology.outer_face import face_loops
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.model.role import ContourRole
from topo import to_shapely


# --- Helper: building pure Edges (no ezdxf) ---

def _edge(start, end):
    """Create a linear Edge."""
    return Edge(
        role=ContourRole.UNKNOWN,
        start=start,
        end=end,
        segment=LineSeg(start=start, end=end),
    )

def _arc_edge(start, end, arc_pts):
    """Create an Edge that discretizes an arc (arc_pts from start to end)."""
    # We use BSplineSeg to represent the arc's discretization
    from topo.core.primitives.spline import BSplineSeg
    return Edge(
        role=ContourRole.UNKNOWN,
        start=start,
        end=end,
        # degree 1 clamped: one node per vertex, the two ends doubled
        segment=BSplineSeg(
            degree=1,
            control_points=arc_pts,
            knots=[0.0] + [float(k) for k in range(len(arc_pts))] + [float(len(arc_pts) - 1)],
        ),
    )


# --- Factory: test geometries ---

def _make_rect_edges(w=100.0, h=50.0, ccw=True):
    if ccw:
        return [
            _edge((0, 0),  (w, 0)),
            _edge((w, 0),  (w, h)),
            _edge((w, h),  (0, h)),
            _edge((0, h),  (0, 0)),
        ]
    else:
        return [
            _edge((0, 0),  (0, h)),
            _edge((0, h),  (w, h)),
            _edge((w, h),  (w, 0)),
            _edge((w, 0),  (0, 0)),
        ]

def _make_rect_with_inner_edges(outer_w=100.0, outer_h=80.0,
                                 inner_w=40.0,  inner_h=30.0):
    ox = (outer_w - inner_w) / 2
    oy = (outer_h - inner_h) / 2
    return [
        # outer
        _edge((0,       0),       (outer_w, 0)),
        _edge((outer_w, 0),       (outer_w, outer_h)),
        _edge((outer_w, outer_h), (0,       outer_h)),
        _edge((0,       outer_h), (0,       0)),
        # inner
        _edge((ox,          oy),           (ox + inner_w, oy)),
        _edge((ox + inner_w, oy),          (ox + inner_w, oy + inner_h)),
        _edge((ox + inner_w, oy + inner_h),(ox,           oy + inner_h)),
        _edge((ox,          oy + inner_h), (ox,           oy)),
    ]

def _make_arc_rect_edges():
    """Rectangle with two circular fillets at the lower corners."""
    def _arc_pts(cx, cy, r, start_deg, end_deg, n=16):
        angles = [math.radians(start_deg + (end_deg - start_deg) * i / n)
                  for i in range(n + 1)]
        return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]

    arc1 = _arc_pts(80, 10, 10, 270, 360)
    arc2 = _arc_pts(20, 10, 10, 180, 270)

    return [
        _edge((10, 60), (90, 60)),
        _edge((90, 60), (90, 10)),
        _arc_edge((90, 10), (80, 0),  arc1),
        _edge((80, 0),  (20, 0)),
        _arc_edge((20, 0),  (10, 10), arc2),
        _edge((10, 10), (10, 60)),
    ]

def _make_separate_rects_edges():
    return [
        _edge((0,  0),  (40, 0)),
        _edge((40, 0),  (40, 30)),
        _edge((40, 30), (0,  30)),
        _edge((0,  30), (0,  0)),

        _edge((60, 0),  (100, 0)),
        _edge((100, 0), (100, 30)),
        _edge((100, 30),(60,  30)),
        _edge((60,  30),(60,  0)),
    ]

def _make_stub_in_loop_edges():
    return [
        _edge((0,   0),  (100, 0)),
        _edge((100, 0),  (100, 50)),
        _edge((100, 50), (0,   50)),
        _edge((0,   50), (0,   0)),
        _edge((50,  0),  (50,  25)),  # stub
    ]

def _make_rect_with_split_arcs_and_stubs(
    w=1000.0, h=500.0, r=3.0, stub_len=5.0
):
    """Rectangle with 4 corners filleted by concave arcs broken into two halves.
    Every break point has a stub towards the inside."""
    def arc_pts(cx, cy, r, start_deg, end_deg, n=8):
        angles = [math.radians(start_deg + (end_deg - start_deg) * i / (n-1))
                  for i in range(n)]
        return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]

    edges = []
    # straight sides
    edges.append(_edge((r, 0),       (w - r, 0)))
    edges.append(_edge((w, r),       (w, h - r)))
    edges.append(_edge((w - r, h),   (r, h)))
    edges.append(_edge((0, h - r),   (0, r)))

    # bottom-left corner (180° -> 270°)
    split_bl = (r - r * math.cos(math.radians(45)),
                r - r * math.sin(math.radians(45)))
    pts_bl_1 = arc_pts(r, r, r, 180, 225, 5)
    pts_bl_2 = arc_pts(r, r, r, 225, 270, 5)
    edges.append(_arc_edge(pts_bl_1[0],  pts_bl_1[-1],  pts_bl_1))
    edges.append(_arc_edge(pts_bl_2[0],  pts_bl_2[-1],  pts_bl_2))
    stub_end_bl = (split_bl[0] + stub_len * math.cos(math.radians(45)),
                   split_bl[1] + stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_bl, stub_end_bl))

    # bottom-right corner (270° -> 360°)
    pts_br_1 = arc_pts(w - r, r, r, 270, 315, 5)
    pts_br_2 = arc_pts(w - r, r, r, 315, 360, 5)
    edges.append(_arc_edge(pts_br_1[0], pts_br_1[-1], pts_br_1))
    edges.append(_arc_edge(pts_br_2[0], pts_br_2[-1], pts_br_2))
    split_br = pts_br_1[-1]
    stub_end_br = (split_br[0] - stub_len * math.cos(math.radians(45)),
                   split_br[1] + stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_br, stub_end_br))

    # top-right corner (0° -> 90°)
    pts_tr_1 = arc_pts(w - r, h - r, r, 0, 45, 5)
    pts_tr_2 = arc_pts(w - r, h - r, r, 45, 90, 5)
    edges.append(_arc_edge(pts_tr_1[0], pts_tr_1[-1], pts_tr_1))
    edges.append(_arc_edge(pts_tr_2[0], pts_tr_2[-1], pts_tr_2))
    split_tr = pts_tr_1[-1]
    stub_end_tr = (split_tr[0] - stub_len * math.cos(math.radians(45)),
                   split_tr[1] - stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_tr, stub_end_tr))

    # top-left corner (90° -> 180°)
    pts_tl_1 = arc_pts(r, h - r, r, 90, 135, 5)
    pts_tl_2 = arc_pts(r, h - r, r, 135, 180, 5)
    edges.append(_arc_edge(pts_tl_1[0], pts_tl_1[-1], pts_tl_1))
    edges.append(_arc_edge(pts_tl_2[0], pts_tl_2[-1], pts_tl_2))
    split_tl = pts_tl_1[-1]
    stub_end_tl = (split_tl[0] + stub_len * math.cos(math.radians(45)),
                   split_tl[1] - stub_len * math.sin(math.radians(45)))
    edges.append(_edge(split_tl, stub_end_tl))

    return edges


# --- Helper: loop → Polygon ---

def _loop_to_polygon(loop) -> Polygon:
    """Convert a Loop into a Shapely Polygon."""
    pts = []
    for edge, rev in loop:
        coords = list(edge.segment.discretize(tolerance=0.01))
        if rev:
            coords = list(reversed(coords))
        pts.append(coords[0])
    return Polygon(pts) if len(pts) >= 3 else None


# --- Test: LoopFinder.find() – basic rectangle ---

class TestFaceLoopsRect(unittest.TestCase):
    def setUp(self):
        edges = _make_rect_edges(ccw=True)
        self.loops = face_loops(edges)

    def test_finds_one_loop(self):
        self.assertEqual(len(self.loops), 1)

    def test_loop_has_four_edges(self):
        self.assertEqual(len(self.loops[0]), 4)

    def test_loop_is_closed(self):
        loop = self.loops[0]
        first_edge, first_rev = loop[0]
        last_edge,  last_rev  = loop[-1]

        first_coords = list(first_edge.segment.discretize(tolerance=0.01))
        first_start = first_coords[0] if not first_rev else first_coords[-1]

        last_coords = list(last_edge.segment.discretize(tolerance=0.01))
        last_exit = last_coords[-1] if not last_rev else last_coords[0]

        self.assertAlmostEqual(first_start[0], last_exit[0], places=1)
        self.assertAlmostEqual(first_start[1], last_exit[1], places=1)


# --- Test: CCW orientation ---

class TestLoopOrientationCCW(unittest.TestCase):
    def setUp(self):
        edges = _make_rect_edges(ccw=True)
        loops = face_loops(edges)
        self.poly = _loop_to_polygon(loops[0])

    def test_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_is_ccw(self):
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw)

    def test_area_correct(self):
        self.assertAlmostEqual(self.poly.area, 100 * 50, delta=1.0)


class TestLoopOrientationCW(unittest.TestCase):
    def setUp(self):
        edges = _make_rect_edges(ccw=False)
        loops = face_loops(edges)
        self.poly = _loop_to_polygon(loops[0])

    def test_polygon_valid(self):
        self.assertIsNotNone(self.poly)
        self.assertTrue(self.poly.is_valid)

    def test_is_ccw(self):
        ring = LinearRing(self.poly.exterior.coords)
        self.assertTrue(ring.is_ccw)

    def test_area_correct(self):
        self.assertAlmostEqual(self.poly.area, 100 * 50, delta=1.0)


# --- Test: geometry with fillets ---

class TestLoopWithArcs(unittest.TestCase):
    def setUp(self):
        edges = _make_arc_rect_edges()
        self.loops = face_loops(edges)
        self.polygons = [_loop_to_polygon(l) for l in self.loops]
        self.valid_polys = [p for p in self.polygons
                            if p is not None and p.is_valid]

    def test_finds_at_least_one_loop(self):
        self.assertGreaterEqual(len(self.loops), 1)

    def test_largest_loop_is_outer_profile(self):
        max_area = max(p.area for p in self.valid_polys)
        self.assertGreater(max_area, 4000.0)

    def test_all_loops_ccw(self):
        for i, poly in enumerate(self.valid_polys):
            ring = LinearRing(poly.exterior.coords)
            self.assertTrue(ring.is_ccw,
                            f"Loop {i+1} is not CCW (area={poly.area:.1f})")


# --- Test: stubs on broken concave arcs — recovery via the full pipeline ---

class TestSplitArcStubs(unittest.TestCase):
    """Concave arcs broken into two halves + stub LINEs towards the inside attached
    at the break point (a node of degree 3).

    The stubs enter and leave the same node: the face walk walks them back and
    forth and makes no loop of them; they end in `loose` without being lost. The
    test verifies the PRODUCT's outcome."""

    def setUp(self):
        import topo
        from topo.model.document import Document
        edges = _make_rect_with_split_arcs_and_stubs()
        self.result = topo.heal(Document(edges=edges)).faces()

    def test_a_single_part(self):
        self.assertEqual(self.result.cluster_count, 1)

    def test_area_rectified(self):
        poly = to_shapely(self.result.clusters[0].outer)
        self.assertAlmostEqual(poly.area, 1000.0 * 500.0, delta=500.0)

    def test_stubs_not_lost_end_in_trash(self):
        # one stub per corner: outside the contour, but materialized in trash
        self.assertGreaterEqual(len(self.result.loose), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)