"""
tests/engine/base/test_hierarchy_builder.py

Tests for HierarchyBuilder.

HierarchyBuilder builds ONLY the containment tree —
`Cluster(outer, inners=[Contour...])`, no `Hole`. The hole / countersink
classification is `detect_flat()`'s.

The ClosedCurve/OpenCurve proxies are built directly with native primitives —
no DXF adapter, no real file.
"""

import math
import unittest
from shapely.geometry import Polygon

from topo.core.primitives.line import LineSeg
from topo.model.curve import ClosedCurve, OpenCurve
from topo.model.role import ContourRole
from topo.core.base.hierarchy import HierarchyBuilder
import topo
from topo import to_shapely


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_proxy(polygon, *, role=ContourRole.UNKNOWN):
    return ClosedCurve(role=role, segments=topo.geometry.polygon(polygon.exterior.coords))


def _make_open_proxy(pts, *, role=ContourRole.UNKNOWN):
    segments = [
        LineSeg(start=pts[i], end=pts[i + 1])
        for i in range(len(pts) - 1)
    ]
    return OpenCurve(role=role, segments=segments)


def _circle_proxy(cx, cy, r):
    poly = Polygon(
        [(cx + r * math.cos(a * math.pi / 180),
          cy + r * math.sin(a * math.pi / 180))
         for a in range(0, 360, 5)]
    )
    return _make_proxy(poly)


def _rect_proxy(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return _make_proxy(poly)


def _make_builder():
    return HierarchyBuilder(
        label="",
    )


class TestVirtualModelRemoved(unittest.TestCase):
    def test_closed_shape_has_no_virtual_flag(self):
        proxy = _make_proxy(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]))
        self.assertFalse(hasattr(proxy, "is_virtual"))
        self.assertFalse(hasattr(proxy, "vs_id"))


# --- Test 1 — outer + inner contour ---

class TestOuterWithInner(unittest.TestCase):
    """- 1 large proxy (100×100) → OUTER
    - 1 contained circular proxy d=5 → inner (heal does NOT promote it to a hole)

    Expected: 1 Cluster, 0 holes, 1 inner, empty trash.
    """

    def setUp(self):
        self.outer = _rect_proxy(0, 0, 100, 100)
        self.inner = _circle_proxy(50, 50, 2.5)
        self.clusters, self.trash = _make_builder().build([self.outer, self.inner])

    def test_produces_a_part(self):
        self.assertEqual(len(self.clusters), 1)

    def test_outer_area(self):
        self.assertAlmostEqual(to_shapely(self.clusters[0].outer).area, 10000.0, delta=1.0)

    def test_zero_holes(self):
        self.assertEqual(len(self.clusters[0].features("holes")), 0)

    def test_an_inner(self):
        self.assertEqual(len(self.clusters[0].inners), 1)
        self.assertEqual(self.clusters[0].inners[0].role, ContourRole.INNER)

    def test_trash_empty(self):
        self.assertEqual(len(self.trash), 0)


# --- Test 2 — three-level nesting (countersink): heal flattens everything into inners ---
#

class TestNestingFlattened(unittest.TestCase):
    """- outer   : 100×100 rectangle
    - middle  : circle d=20 inside outer
    - small   : circle d=8  inside middle

    heal() no longer recognizes the countersink from the nesting: it delivers both
    circles as flat inners. The recognition is detect_flat()'s."""

    def setUp(self):
        outer   = _rect_proxy(0, 0, 100, 100)
        medio   = _circle_proxy(50, 50, 10)   # d=20
        piccolo = _circle_proxy(50, 50, 4)    # d=8
        self.clusters, self.trash = _make_builder().build([outer, medio, piccolo])

    def test_produces_a_part(self):
        self.assertEqual(len(self.clusters), 1)

    def test_zero_holes(self):
        self.assertEqual(len(self.clusters[0].features("holes")), 0)

    def test_two_inners(self):
        self.assertEqual(len(self.clusters[0].inners), 2)


# --- Test 2bis — same hierarchy, but depth/parent are no longer lost ---

class TestNestingDepthAndParent(unittest.TestCase):
    """Same three-level hierarchy as TestNestingFlattened: outer (100x100) → middle
    (d=20) → small (d=8). heal() still flattens everything into `cluster.inners`,
    but every Contour carries `depth`/`parent` — the data a tab tool (Smoother)
    reads to know who is whose grandchild, instead of recomputing the containment itself."""

    def setUp(self):
        self.outer_proxy   = _rect_proxy(0, 0, 100, 100)
        self.medio_proxy   = _circle_proxy(50, 50, 10)   # d=20, direct child
        self.piccolo_proxy = _circle_proxy(50, 50, 4)    # d=8,  nipote
        self.clusters, _ = _make_builder().build(
            [self.outer_proxy, self.medio_proxy, self.piccolo_proxy]
        )
        self.cluster = self.clusters[0]
        # decreasing area: inners[0] is always the middle one, inners[1] the small one
        # (_build_tree sorts the proxies by area before placing them).
        self.medio, self.piccolo = self.cluster.inners

    def test_outer_depth_zero_without_parent(self):
        self.assertEqual(self.cluster.outer.depth, 0)
        self.assertIsNone(self.cluster.outer.parent)

    def test_direct_child_depth_one_parent_is_outer(self):
        self.assertEqual(self.medio.depth, 1)
        self.assertIs(self.medio.parent, self.cluster.outer)

    def test_grandchild_depth_two_parent_is_the_child_not_the_outer(self):
        self.assertEqual(self.piccolo.depth, 2)
        self.assertIs(self.piccolo.parent, self.medio)
        self.assertIsNot(self.piccolo.parent, self.cluster.outer)


# --- Test 3 — trash ---

class TestTrash(unittest.TestCase):
    """- 1 outer proxy (100×100)
    - 1 OpenCurve role=UNKNOWN outside the outer

    Expected: the floating open proxy ends in trash, the outer produces 1 Cluster."""

    def setUp(self):
        self.outer    = _rect_proxy(0, 0, 100, 100)
        self.floating = _make_open_proxy([(200, 200), (210, 200)], role=ContourRole.UNKNOWN)
        self.clusters, self.trash = _make_builder().build([self.outer, self.floating])

    def test_a_part_produced(self):
        self.assertGreaterEqual(len(self.clusters), 1)

    def test_floating_in_trash(self):
        self.assertIn(self.floating, self.trash)

    def test_outer_not_in_trash(self):
        self.assertFalse(
            any(
                getattr(t, "polygon", None) is not None
                and to_shapely(t).equals(to_shapely(self.outer))
                for t in self.trash
            )
        )


# --- Test 4 — segments copied from the proxy to the model ---

class TestSegmentsCopied(unittest.TestCase):
    """HierarchyBuilder copies proxy.segments onto outer and inner.

    The segments are stubs — what matters is that they arrive intact."""

    def setUp(self):
        from topo.core.primitives import LineSeg, CircleSeg

        self.seg_outer = [
            LineSeg(start=(0, 0),   end=(100, 0)),
            LineSeg(start=(100, 0), end=(100, 100)),
            LineSeg(start=(100, 100), end=(0, 100)),
            LineSeg(start=(0, 100), end=(0, 0)),
        ]
        self.seg_inner = [
            CircleSeg(center=(50, 50), radius=2.5,
                   start_angle=0.0, end_angle=6.2831, ccw=True),
        ]

        outer = _rect_proxy(0, 0, 100, 100)
        outer.segments = list(self.seg_outer)

        inner = _circle_proxy(50, 50, 2.5)
        inner.segments = list(self.seg_inner)

        self.clusters, _ = _make_builder().build([outer, inner])

    def test_outer_segments_copied(self):
        self.assertEqual(self.clusters[0].outer.segments, self.seg_outer)

    def test_inner_segments_copied(self):
        self.assertEqual(self.clusters[0].inners[0].segments, self.seg_inner)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCopiesOrderUnderMotion(unittest.TestCase):
    """two congruent copies are ordered by the bbox corner. The area rounded to 1e-6
    called them equal only if they fell in the same cell: with the area at mid-cell
    (10.0000005) the last bit, which the motion changes, decided the order. Proof:
    at every translation the copy on the left (or below) comes first. Rotations are
    not proved: there which copy is on the left really changes."""

    W, H = 10.0, 1.00000005
    MOTIONS = [(0.0, dx, dy) for dx in (0.0, 0.3, 1.7, 13.1, 250.0, 2.5e6) for dy in (0.0, 0.7, -9.3, -1.5e6)]

    @staticmethod
    def _rectangle(x0, y0, w, h):
        p = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        return [LineSeg(start=p[i], end=p[(i + 1) % 4]) for i in range(4)]

    def _first_corner(self, offset, motion):
        from tests.invariants import rigid
        segment, point = rigid(*motion)
        segs = self._rectangle(0, 0, self.W, self.H) + self._rectangle(*offset, self.W, self.H)
        result = topo.heal(topo.load_segments([segment(s) for s in segs])).faces()
        self.assertEqual(len(result.clusters), 2)
        return result.clusters[0].bbox[:2], point((0.0, 0.0))

    def test_copies_side_by_side_the_left_first(self):
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                corner, origin = self._first_corner((20, 0), motion)
                self.assertAlmostEqual(corner[0], origin[0], delta=1e-3)

    def test_copies_stacked_the_low_first(self):
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                corner, origin = self._first_corner((0, 5), motion)
                self.assertAlmostEqual(corner[1], origin[1], delta=1e-3)


class TestTreeOrderUnderMotion(unittest.TestCase):
    """`_build_tree` places the contours from the largest by `round(area, 6)`. The
    order decides the shape of the tree only between two contours one of which
    contains the other, and there the areas differ by far more than 1e-6 (on the
    drawings: 344 pairs within 1e-5, none nested). Proof: a plate with two
    congruent holes with the area at mid-cell gives at every translation a cluster
    with two inners of depth 1. It does not prove the order of the two inners
    between themselves, which is not a contract."""

    MOTIONS = [(0.0, dx, dy) for dx in (0.0, 0.3, 13.1, 250.0, 2.5e6) for dy in (0.0, -9.3, -1.5e6)]

    def test_two_congruent_holes_stay_children_of_the_plate(self):
        from tests.invariants import rigid
        rect = TestCopiesOrderUnderMotion._rectangle
        segs = rect(0, 0, 40, 10) + rect(2, 2, 10, 1.00000005) + rect(22, 2, 10, 1.00000005)
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                result = topo.heal(topo.load_segments([segment(s) for s in segs])).faces()
                self.assertEqual(len(result.clusters), 1)
                self.assertEqual([c.depth for c in result.clusters[0].inners], [1, 1])
