"""
test_geometry_regions.py
------------------------
Primitives for a caller's algorithms: `intersections` between two primitives,
`point_on_contour`, `cut_by`, `contour_minus`, `contour_union`,
`Contour.from_segments`. Every region is any closed contour: the same tests
run with a disc and with a rectangle.
"""

import math
import unittest

import topo
from topo.core.primitives import CircleSeg, LineSeg, BSplineSeg
from topo.core.geometry.shapely_polygons import build_polygon
from topo.model.contour import Contour
from topo import to_shapely

g = topo.geometry
SQUARE = g.rectangle(10, 10, center=(5, 5))          # 0..10 x 0..10, antiorario
# an L: 10x10 minus the square 5..10 x 5..10, concave corner at (5, 5)
L_SHAPE = g.polygon([(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)])


def _area(ring):
    return build_polygon(ring, 1e-5).area


def _signed(ring):
    pts = [q for s in ring for q in s.discretize(tolerance=1e-4)[:-1]]
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


def _rounded(points, nd=9):
    return sorted((round(x, nd), round(y, nd)) for x, y in points)


class TestIntersections(unittest.TestCase):

    def test_line_line(self):
        self.assertEqual(_rounded(g.intersections(LineSeg((0, 0), (10, 0)), LineSeg((5, -1), (5, 1)))),
                         [(5, 0)])

    def test_lines_that_would_meet_only_if_extended_do_not(self):
        self.assertEqual(g.intersections(LineSeg((0, 0), (10, 0)), LineSeg((5, 1), (5, 2))), [])

    def test_line_circle_and_line_arc_only_inside_the_sweep(self):
        line = LineSeg((0, 0), (10, 0))
        self.assertEqual(_rounded(g.intersections(line, CircleSeg((5, 0), 2))), [(3, 0), (7, 0)])
        # upper semicircle from 0 to π: touches the line at both ends
        self.assertEqual(_rounded(g.intersections(line, CircleSeg((5, 0), 2, 0, math.pi, True))),
                         [(3, 0), (7, 0)])
        # quarter from 0 to π/2: only the end at (7, 0)
        self.assertEqual(_rounded(g.intersections(line, CircleSeg((5, 0), 2, 0, math.pi / 2, True))),
                         [(7, 0)])

    def test_arc_arc_exact(self):
        pts = g.intersections(CircleSeg((0, 0), 5), CircleSeg((6, 0), 5))
        self.assertEqual(_rounded(pts), [(3, -4), (3, 4)])

    def test_tangent_gives_one_point(self):
        self.assertEqual(_rounded(g.intersections(LineSeg((-5, 2), (5, 2)), CircleSeg((0, 0), 2))), [(0, 2)])

    def test_overlapping_lines_give_no_point(self):
        self.assertEqual(g.intersections(LineSeg((0, 0), (10, 0)), LineSeg((5, 0), (15, 0))), [])

    def test_spline_within_curve_tolerance(self):
        spline = BSplineSeg(degree=2, control_points=[(0, -5), (5, 10), (10, -5)],
                           knots=[0, 0, 0, 1, 1, 1])
        pts = g.intersections(spline, LineSeg((0, 0), (10, 0)))
        self.assertEqual(len(pts), 2)
        for x, y in pts:
            self.assertAlmostEqual(y, 0, places=3)


class TestPointOnContour(unittest.TestCase):

    def test_convex_vertex(self):
        p = g.point_on_contour(SQUARE, (10, 0))
        self.assertEqual((p.kind, p.turn_deg, p.concave), ("vertex", 90.0, False))
        self.assertEqual(p.segments, (0, 1))

    def test_concave_vertex(self):
        p = g.point_on_contour(L_SHAPE, (5, 5))
        self.assertEqual((p.kind, p.concave), ("vertex", True))
        self.assertAlmostEqual(p.turn_deg, 90)

    def test_concavity_does_not_depend_on_the_direction_of_the_ring(self):
        backwards = [s.reversed() for s in reversed(L_SHAPE)]
        self.assertTrue(g.point_on_contour(backwards, (5, 5)).concave)
        self.assertFalse(g.point_on_contour(backwards, (10, 0)).concave)

    def test_line_tangent_to_arc_is_smooth(self):
        stadium = g.stadium(20, 6)
        joints = [s.start for s in stadium if isinstance(s, LineSeg)]
        for joint in joints:
            self.assertEqual(g.point_on_contour(stadium, joint).kind, "smooth")

    def test_middle_of_a_side_and_far_away(self):
        p = g.point_on_contour(SQUARE, (4, 0.0005))
        self.assertEqual((p.kind, p.segments), ("edge", (0,)))
        self.assertIsNone(g.point_on_contour(SQUARE, (4, 1)))


class TestCuspUnderMotion(unittest.TestCase):
    """concave is the sign of `cross * area`. At a cusp (the contour goes back, 180°)
    `cross` is 0. Proof: under motion the answer does not change, because the two
    sides of a zero-width cusp are the exact reverse of each other even moved
    (cross stays exactly 0), and on a cusp 1e-9 wide the sign of cross is
    geometry, not noise. It does not prove that the zero-width answer is right: a
    cut towards the inside comes out convex. It does not prove the line inside the
    readings: `point_on_contour` is not called by `faces()` nor by `outlines()`."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (2.4, -0.37, 0.61), (math.pi / 2, 0.0, 0.0)]
    RINGS = {
        "tip outward": ([(0, 0), (10, 0), (10, 5), (15, 5), (10, 5), (10, 10), (0, 10)], (15, 5)),
        "cut inside": ([(0, 0), (10, 0), (10, 5), (5, 5), (10, 5), (10, 10), (0, 10)], (5, 5)),
        "narrow tip": ([(0, 0), (10, 0), (10, 5), (15, 5 + 1e-9), (10, 5 + 2e-9),
                           (10, 10), (0, 10)], (15, 5 + 1e-9)),
    }

    def test_the_answer_does_not_depend_on_the_motion(self):
        from tests.invariants import rigid
        for name, (ring, tip) in self.RINGS.items():
            answers = set()
            for motion in self.MOTIONS:
                move_seg, move_pt = rigid(*motion)
                segs = [move_seg(LineSeg(start=ring[i], end=ring[(i + 1) % len(ring)]))
                        for i in range(len(ring))]
                p = g.point_on_contour(segs, move_pt(tip), tolerance=1e-12)
                answers.add((p.kind, round(p.turn_deg, 6), p.concave))
            with self.subTest(ring=name):
                self.assertEqual(len(answers), 1, answers)
        # the narrow cusp towards the outside is convex: the sign of cross is true
        self.assertEqual(answers, {("vertex", 180.0, False)})


class TestNearestPoint(unittest.TestCase):
    """The contour point nearest any point (e.g. a click)."""

    def test_middle_of_a_side_not_a_vertex(self):
        self.assertEqual(_rounded([g.nearest_point(SQUARE, (4, -3))]), [(4, 0)])
        self.assertEqual(_rounded([g.nearest_point(SQUARE, (4, 3))]), [(4, 0)])

    def test_beyond_a_corner_is_the_corner(self):
        self.assertEqual(_rounded([g.nearest_point(SQUARE, (13, -2))]), [(10, 0)])

    def test_circle_and_arc_exact(self):
        self.assertEqual(_rounded([g.nearest_point(g.circle(5), (0, 9))]), [(0, 5)])
        # quarter from 0 to π/2: a point below the x axis falls on the end (5, 0), not beyond the sweep
        quarter = [CircleSeg((0, 0), 5, 0, math.pi / 2, True)]
        self.assertEqual(_rounded([g.nearest_point(quarter, (6, -4))]), [(5, 0)])

    def test_feeds_point_on_contour(self):
        p = g.point_on_contour(L_SHAPE, g.nearest_point(L_SHAPE, (4, 4)))
        self.assertEqual((p.kind, p.point), ("vertex", (5.0, 5.0)))

    def test_spline_within_curve_tolerance(self):
        spline = BSplineSeg(degree=2, control_points=[(0, 0), (5, 10), (10, 0)], knots=[0, 0, 0, 1, 1, 1])
        x, y = g.nearest_point([spline], (5, 20))
        self.assertAlmostEqual(x, 5, places=3)
        self.assertAlmostEqual(y, 5, places=3)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            g.nearest_point([], (0, 0))


class TestCutBy(unittest.TestCase):

    def test_line_through_a_disk(self):
        out = g.cut_by(LineSeg((0, 0), (10, 0)), g.circle(2, center=(5, 0)))
        self.assertEqual([(s.start, s.end) for s in out], [((0, 0), (3.0, 0.0)), ((7.0, 0.0), (10, 0))])
        inside = g.cut_by(LineSeg((0, 0), (10, 0)), g.circle(2, center=(5, 0)), keep="inside")
        self.assertEqual([(s.start, s.end) for s in inside], [((3.0, 0.0), (7.0, 0.0))])

    def test_same_call_with_a_square(self):
        out = g.cut_by(LineSeg((0, 0), (10, 0)), g.rectangle(4, 4, center=(5, 0)))
        self.assertEqual([(s.start, s.end) for s in out], [((0, 0), (3.0, 0.0)), ((7.0, 0.0), (10, 0))])

    def test_end_inside_shortens(self):
        out = g.cut_by(LineSeg((0, 0), (10, 0)), g.circle(1.5))
        self.assertEqual([(s.start, s.end) for s in out], [((1.5, 0.0), (10, 0))])

    def test_arc_stays_an_arc(self):
        out = g.cut_by(CircleSeg((0, 0), 5, 0, math.pi, True), g.rectangle(4, 20, center=(0, 5)))
        self.assertEqual(len(out), 2)
        for arc in out:
            self.assertIsInstance(arc, CircleSeg)
            self.assertEqual((arc.center, arc.radius), ((0, 0), 5))

    def test_piece_along_the_border_raises(self):
        with self.assertRaises(ValueError):
            g.cut_by(LineSeg((-5, 0), (15, 0)), SQUARE)


class TestContourMinus(unittest.TestCase):

    def test_disk_on_a_corner(self):
        rings = g.contour_minus(SQUARE, g.circle(2))
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 100 - math.pi, places=4)
        self.assertEqual([type(s).__name__ for s in rings[0]].count("CircleSeg"), 1)

    def test_square_on_a_corner(self):
        rings = g.contour_minus(SQUARE, g.rectangle(4, 4))
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 96)

    def test_concave_corner_of_an_l(self):
        rings = g.contour_minus(L_SHAPE, g.circle(1.5, center=(5, 5)))
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 75 - 3 * math.pi * 1.5 ** 2 / 4, places=4)

    def test_a_cut_through_gives_two_rings(self):
        rings = g.contour_minus(SQUARE, g.rectangle(2, 20, center=(5, 5)))
        self.assertEqual(sorted(round(_area(r), 6) for r in rings), [40, 40])

    def test_region_inside_is_a_hole_with_the_opposite_direction(self):
        rings = g.contour_minus(SQUARE, g.circle(1, center=(5, 5)))
        self.assertEqual(len(rings), 2)
        self.assertGreater(_signed(rings[0]), 0)
        self.assertLess(_signed(rings[1]), 0)

    def test_region_covering_and_region_apart(self):
        self.assertEqual(g.contour_minus(SQUARE, g.circle(50, center=(5, 5))), [])
        self.assertEqual(g.contour_minus(SQUARE, g.circle(1, center=(50, 50))), [SQUARE])

    def test_direction_of_the_contour_is_kept(self):
        backwards = [s.reversed() for s in reversed(SQUARE)]
        rings = g.contour_minus(backwards, g.circle(2))
        self.assertLess(_signed(rings[0]), 0)
        self.assertAlmostEqual(_area(rings[0]), 100 - math.pi, places=4)

    def test_result_is_a_valid_contour(self):
        ring = g.contour_minus(L_SHAPE, g.circle(1.5, center=(5, 5)))[0]
        contour = Contour.from_segments(ring, role="outer")
        self.assertTrue(to_shapely(contour).is_valid)

    def test_shared_border_raises(self):
        with self.assertRaises(ValueError):
            g.contour_minus(SQUARE, g.rectangle(10, 10, center=(15, 5)))


class TestContourUnion(unittest.TestCase):

    def _kinds(self, ring):
        return [type(s).__name__ for s in ring]

    def test_side_by_side_the_shared_border_disappears(self):
        rings = g.contour_union(SQUARE, g.rectangle(10, 10, center=(15, 5)))
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 200)
        # where the border continues on the same line there is no corner
        self.assertEqual(self._kinds(rings[0]), ["LineSeg"] * 4)

    def test_a_shorter_neighbour_leaves_the_rest_of_the_side(self):
        rings = g.contour_union(SQUARE, g.rectangle(4, 4, center=(12, 5)))
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 116)
        self.assertEqual(len(rings[0]), 8)

    def test_overlapping_and_identical(self):
        rings = g.contour_union(SQUARE, g.rectangle(10, 10, center=(10, 5)))
        self.assertEqual([round(_area(r), 6) for r in rings], [150])
        self.assertEqual(len(rings[0]), 4)
        self.assertEqual([round(_area(r), 6) for r in g.contour_union(SQUARE, SQUARE)], [100])

    def test_apart_inside_and_touching_in_a_point(self):
        self.assertEqual(len(g.contour_union(SQUARE, g.circle(1, center=(50, 50)))), 2)
        self.assertEqual([round(_area(r), 6) for r in g.contour_union(SQUARE, g.circle(1, center=(5, 5)))],
                         [100])
        # a touch at a point: two rings, not a figure eight
        for other in (g.rectangle(10, 10, center=(15, 15)), g.circle(5, center=(15, 5))):
            rings = g.contour_union(SQUARE, other)
            self.assertEqual(len(rings), 2)
            self.assertAlmostEqual(sum(_area(r) for r in rings), 100 + _area(other), places=4)

    def test_a_closed_gap_is_a_hole_with_the_opposite_direction(self):
        u_shape = g.polygon([(0, 0), (9, 0), (9, 9), (6, 9), (6, 3), (3, 3), (3, 9), (0, 9)])
        rings = g.contour_union(u_shape, g.rectangle(9, 2, center=(4.5, 10)))
        self.assertEqual([round(_area(r), 6) for r in rings], [99, 18])
        self.assertGreater(_signed(rings[0]), 0)
        self.assertLess(_signed(rings[1]), 0)

    def test_shared_arc_and_two_half_disks(self):
        disk = g.circle(2)
        notched = g.contour_minus(SQUARE, disk)[0]
        rings = g.contour_union(notched, disk)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 100 + 3 * math.pi, places=3)
        upper = [CircleSeg((0, 0), 5, 0, math.pi, True), LineSeg((-5, 0), (5, 0))]
        lower = [CircleSeg((0, 0), 5, math.pi, 2 * math.pi, True), LineSeg((5, 0), (-5, 0))]
        rings = g.contour_union(upper, lower)
        self.assertEqual(self._kinds(rings[0]), ["CircleSeg"])
        self.assertAlmostEqual(rings[0][0].radius, 5)

    def test_shared_spline_border(self):
        curve = BSplineSeg(degree=2, control_points=[(10, 0), (13, 5), (10, 10)],
                           knots=[0, 0, 0, 1, 1, 1])
        left = [LineSeg((0, 0), (10, 0)), curve, LineSeg((10, 10), (0, 10)), LineSeg((0, 10), (0, 0))]
        right = [LineSeg((10, 0), (20, 0)), LineSeg((20, 0), (20, 10)), LineSeg((20, 10), (10, 10)),
                 curve.reversed()]
        rings = g.contour_union(left, right)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(_area(rings[0]), 200, places=3)
        self.assertNotIn("BSplineSeg", self._kinds(rings[0]))

    def test_direction_of_the_contour_is_kept(self):
        backwards = [s.reversed() for s in reversed(SQUARE)]
        rings = g.contour_union(backwards, g.rectangle(10, 10, center=(15, 5)))
        self.assertLess(_signed(rings[0]), 0)
        self.assertAlmostEqual(_area(rings[0]), 200)

    def test_result_is_a_valid_contour(self):
        ring = g.contour_union(L_SHAPE, g.rectangle(5, 5, center=(7.5, 7.5)))[0]
        self.assertAlmostEqual(_area(ring), 100)
        contour = Contour.from_segments(ring, role="outer")
        self.assertTrue(to_shapely(contour).is_valid)

    def test_a_border_within_same_point_is_shared(self):
        # within SAME_POINT the two borders are the same border; beyond, two rings
        near = g.contour_union(SQUARE, g.rectangle(10, 10, center=(15 + topo.precision.SAME_POINT / 2, 5)))
        self.assertEqual(len(near), 1)
        self.assertAlmostEqual(_area(near[0]), 200, delta=0.01)
        apart = g.contour_union(SQUARE, g.rectangle(10, 10, center=(15 + 2 * topo.precision.SAME_POINT, 5)))
        self.assertEqual(len(apart), 2)


class TestTouchingRingsUnderMotion(unittest.TestCase):
    """(`min(nexts, key=wedge)` in `_chain`): where two rings of the union touch at a
    point two pieces restart, the narrowest wedge wins. Proof: corner against
    corner and a circle tangent to a side (the circle's wedge, tangent backwards,
    is the full turn) give two rings at every motion; with `max` in place of `min`
    a figure eight comes out (red). There is no tie to prove: two kept pieces do
    not start in the same direction, because with the region on the same side the
    one that curves more is inside the other ring and is already removed. It does
    not prove the readings: `contour_union` is called neither by `faces()` nor by `outlines()`."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (2.4, -0.37, 0.61), (math.pi / 2, 0.0, 0.0)]

    def test_two_rings_at_every_motion(self):
        from tests.invariants import rigid
        others = {"corner": g.rectangle(10, 10, center=(15, 15)), "circle": g.circle(5, center=(15, 5))}
        for name, other in others.items():
            for motion in self.MOTIONS:
                move_seg, _ = rigid(*motion)
                rings = g.contour_union([move_seg(s) for s in SQUARE], [move_seg(s) for s in other])
                with self.subTest(other=name, motion=motion):
                    self.assertEqual(sorted(round(_area(r), 4) for r in rings),
                                     sorted([100.0, round(_area(other), 4)]))


class TestContourFromSegments(unittest.TestCase):

    def test_ring_becomes_a_contour(self):
        contour = Contour.from_segments(SQUARE, role="outer")
        self.assertAlmostEqual(contour.area, 100)
        self.assertEqual(contour.segments, SQUARE)

    def test_open_chain_raises(self):
        with self.assertRaises(ValueError):
            Contour.from_segments(SQUARE[:3], role="outer")

    def test_segments_out_of_order_raise(self):
        with self.assertRaises(ValueError):
            Contour.from_segments([SQUARE[0], SQUARE[2], SQUARE[1], SQUARE[3]], role="outer")



class TestTangentOnTheTrueCurve(unittest.TestCase):
    """the direction at the end of splines and ellipses is the derivative of the
    true curve, not the last chord of the polygon. Proof: a quarter circle written
    as a rational NURBS has known exact tangents; a spline and an ellipse
    coincide with the finite difference on the curve."""

    def test_rational_quarter_circle(self):
        from topo.core.geometry.regions import end_tangent
        quarter = BSplineSeg(degree=2, control_points=[(1, 0), (1, 1), (0, 1)],
                             knots=[0, 0, 0, 1, 1, 1], weights=[1, 2 ** -0.5, 1])
        for at_end, expected in ((False, (0.0, 1.0)), (True, (-1.0, 0.0))):
            for got, want in zip(end_tangent(quarter, at_end), expected):
                self.assertAlmostEqual(got, want, places=12)

    def test_spline_and_ellipse_like_the_curve(self):
        from topo.core.geometry.regions import end_tangent
        from topo.core.primitives import EllipseSeg
        spline = BSplineSeg(degree=3, control_points=[(0, 0), (1, 2), (3, 3), (4, 1), (6, 0)],
                            knots=[0, 0, 0, 0, 0.4, 1, 1, 1, 1])
        ellipse = EllipseSeg(center=(0, 0), major_axis=(2, 0), ratio=0.5, start_param=1.2, end_param=0.3, ccw=False)
        h = 1e-7
        cases = [(spline, False, spline._evaluate(0.0), spline._evaluate(h)),
                 (spline, True, spline._evaluate(1.0 - h), spline._evaluate(1.0)),
                 (ellipse, False, ellipse._point_at(1.2), ellipse._point_at(1.2 - h)),
                 (ellipse, True, ellipse._point_at(0.3 + h), ellipse._point_at(0.3))]
        for seg, at_end, a, b in cases:
            n = math.dist(a, b)
            with self.subTest(seg=type(seg).__name__, at_end=at_end):
                for got, want in zip(end_tangent(seg, at_end), ((b[0] - a[0]) / n, (b[1] - a[1]) / n)):
                    self.assertAlmostEqual(got, want, places=6)


if __name__ == "__main__":
    unittest.main()
