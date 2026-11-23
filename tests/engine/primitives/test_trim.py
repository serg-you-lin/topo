# tests/engine/primitives/test_trim.py

"""`sub_segment`: the stretch of a primitive between two of its points is the
same curve shortened — same ends, every point on the original curve."""

import math
import unittest

from topo.core.primitives.line import LineSeg
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo.core.primitives.clothoid import ClothoidSeg
from topo.core.primitives.formula import FormulaSeg
from topo.core.primitives.trim import sub_segment
from topo.core.geometry.measure import Reach, segment_length


def _close(p, q, tol=1e-6):
    return math.dist(p, q) <= tol


class TestSubSegment(unittest.TestCase):

    def _assert_on(self, piece, curve_distance, tol=1e-6):
        # every point of the stretch lies on the original curve
        for pt in piece.discretize(tolerance=0.001):
            self.assertLess(curve_distance(pt), tol)

    def test_line_straight(self):
        piece = sub_segment(LineSeg(start=(0, 0), end=(10, 0)), (2, 0), (7, 0), (4, 0))
        self.assertEqual(segment_endpoints(piece), ((2, 0), (7, 0)))

    def test_line_reversed_straight(self):
        piece = sub_segment(LineSeg(start=(0, 0), end=(10, 0)), (7, 0), (2, 0), (4, 0))
        self.assertEqual(segment_endpoints(piece), ((7, 0), (2, 0)))

    def test_arc_in_both_directions(self):
        arc = CircleSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi, ccw=True)
        a, b = (5 * math.cos(0.5), 5 * math.sin(0.5)), (5 * math.cos(2.0), 5 * math.sin(2.0))
        for x, y in ((a, b), (b, a)):
            piece = sub_segment(arc, x, y, (0, 5))
            s, e = segment_endpoints(piece)
            self.assertTrue(_close(s, x) and _close(e, y))
            self.assertAlmostEqual(piece._sweep(), 1.5)
            self._assert_on(piece, lambda p: abs(math.dist(p, (0, 0)) - 5))

    def test_end_just_beyond_the_arc_end_lies_on_the_end(self):
        arc = CircleSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi / 2, ccw=True)
        beyond = (5 * math.cos(math.pi / 2 + 1e-4), 5 * math.sin(math.pi / 2 + 1e-4))
        piece = sub_segment(arc, (5, 0), beyond, (0, 5))
        self.assertAlmostEqual(piece._sweep(), math.pi / 2)

    def test_circle_turns_on_the_side_of_via(self):
        circle = CircleSeg(center=(0, 0), radius=5)
        top, bottom = (0, 5), (0, -5)
        left = sub_segment(circle, top, bottom, (-5, 0))
        right = sub_segment(circle, top, bottom, (5, 0))
        self.assertAlmostEqual(left._sweep(), math.pi)
        self.assertAlmostEqual(right._sweep(), math.pi)
        self.assertLess(min(p[0] for p in left.discretize(tolerance=0.01)), -4.9)
        self.assertGreater(max(p[0] for p in right.discretize(tolerance=0.01)), 4.9)

    def test_ellipse(self):
        ellipse = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                             start_param=0, end_param=2 * math.pi)
        a, b = ellipse._point_at(0.3), ellipse._point_at(1.2)
        piece = sub_segment(ellipse, a, b, ellipse._point_at(0.7))
        s, e = segment_endpoints(piece)
        self.assertTrue(_close(s, a) and _close(e, b))
        self._assert_on(piece, lambda p: abs((p[0] / 10) ** 2 + (p[1] / 5) ** 2 - 1), tol=1e-6)

    def test_spline_exact_stretch_in_both_directions(self):
        spline = BSplineSeg(degree=3,
                           control_points=[(0, 0), (2, 4), (5, -1), (8, 3), (10, 0), (13, 2)],
                           knots=[0, 0, 0, 0, 0.3, 0.6, 1, 1, 1, 1])
        a, b = spline._evaluate(0.2), spline._evaluate(0.75)
        for x, y in ((a, b), (b, a)):
            piece = sub_segment(spline, x, y, None)
            s, e = segment_endpoints(piece)
            self.assertTrue(_close(s, x, 1e-6) and _close(e, y, 1e-6))
        # same curve: every point of the stretch coincides with the original spline
        piece = sub_segment(spline, a, b, None)
        lo, hi = piece.knots[0], piece.knots[-1]
        for k in range(11):
            t = lo + (hi - lo) * k / 10
            self.assertTrue(_close(piece._evaluate(t), spline._evaluate(t), 1e-9))

    def test_rational_spline(self):
        spline = BSplineSeg(degree=2, control_points=[(0, 0), (5, 5), (10, 0)],
                           knots=[0, 0, 0, 1, 1, 1], weights=[1.0, 0.5, 1.0])
        a, b = spline._evaluate(0.25), spline._evaluate(0.8)
        piece = sub_segment(spline, a, b, None)
        for k in range(11):
            t = 0.25 + 0.55 * k / 10
            self.assertTrue(_close(piece._evaluate(t), spline._evaluate(t), 1e-9))

    def test_periodic_spline_is_not_cut(self):
        # uniform cubic with the first three points repeated at the end: it closes
        # without a control point on the joint (periodic is derived)
        cps = [(0, 0), (4, 0), (4, 4), (0, 4)]
        spline = BSplineSeg(degree=3, control_points=cps + cps[:3], knots=list(range(11)))
        self.assertTrue(spline.periodic)
        self.assertIsNone(sub_segment(spline, spline._evaluate(3.5), spline._evaluate(5.5), None))


class TestClosedSplineSeamUnderMotion(unittest.TestCase):
    """(`_spline_param`, the nearest sample): on a closed spline the end lying on the
    seam has two parameters, lo and hi, at the same distance; hi always won (the
    `<=` on the ends) and the stretch came out reversed, the complement. Now `via`
    decides, like on the circle. Proof: the tie is there in place (the two
    distances, checked), the stretch is the right one in both directions and at
    seven motions; inside `outlines()` a line cutting the closed spline gives the
    same outer as the open spline to 1e-9 (before, half shape). It does not prove
    a spline crossing itself (two parameters there too, `via` does not always
    separate them: later)."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0), (0.7, 3.1, -2.2),
               (math.pi / 2, 0.0, 0.0), (2.1, -1e5, 3e4), (2.4, -0.37, 0.61)]
    X, Y = -71565.8225, -3048.0985
    LOOP = [(0, 0), (10, -3), (20, 0), (23, 10), (20, 20), (10, 23), (0, 20), (-3, 10)]

    def _spline(self, gap=0.0):
        cps = [(self.X + a, self.Y + b) for a, b in self.LOOP + [(0, gap)]]
        n, p = len(cps), 3
        knots = [0.0] * (p + 1) + [i / (n - p) for i in range(1, n - p)] + [1.0] * (p + 1)
        return BSplineSeg(degree=p, control_points=cps, knots=knots)

    @staticmethod
    def _length(seg):
        pts = seg.discretize(tolerance=0.001)
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

    def test_the_stretch_from_the_junction_is_via_s(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            move_seg, _ = rigid(*motion)
            spline = move_seg(self._spline())
            seam, b = spline._evaluate(0.0), spline._evaluate(0.3)
            self.assertEqual(math.dist(seam, spline._evaluate(1.0)), 0.0)
            short = sub_segment(spline, seam, b, spline._evaluate(0.15))
            long = sub_segment(spline, b, seam, spline._evaluate(0.6))
            whole = self._length(spline)
            with self.subTest(motion=motion):
                self.assertAlmostEqual(self._length(short), 27.034, places=2)
                self.assertAlmostEqual(self._length(short) + self._length(long), whole, places=3)
                self.assertTrue(_close(segment_endpoints(short)[0], seam))
                self.assertTrue(_close(segment_endpoints(long)[1], seam))

    def test_outlines_the_cut_closed_spline_stays_whole(self):
        import topo
        from tests.invariants import rigid
        X, Y = self.X, self.Y
        for gap in (0.0, 1e-9):
            for motion in self.MOTIONS:
                move_seg, _ = rigid(*motion)
                pieces = [self._spline(gap), LineSeg(start=(X - 10, Y + 10), end=(X + 30, Y + 10))]
                doc = topo.load_segments([move_seg(s) for s in pieces])
                result = topo.heal(doc, max_gap=0.5).outlines()
                with self.subTest(gap=gap, motion=motion):
                    self.assertEqual([round(c.area, 3) for c in result.clusters],
                                     [465.317])


if __name__ == "__main__":
    unittest.main()


class TestHairpinBranch(unittest.TestCase):
    """A hairpin: out and back 0.01 apart, non-uniform knots. The cut's branch is
    chosen by certificate on the Bézier pieces: with 64 samples half the cuts
    ended on the other branch."""

    SPLINE = BSplineSeg(degree=3,
                        control_points=[(0, 0), (25, 0), (50, 0), (50.5, 0.005), (50, 0.01), (25, 0.01), (0, 0.01)],
                        knots=[0.0] * 4 + [0.3, 0.5, 0.6] + [1.0] * 4)

    def test_the_cut_stays_on_its_branch(self):
        s = self.SPLINE
        for k in range(1, 40):
            t0, t1 = k / 41, (k + 1) / 41
            with self.subTest(t0=t0):
                a, b, via = s._evaluate(t0), s._evaluate(t1), s._evaluate((t0 + t1) / 2)
                piece = sub_segment(s, a, b, via)
                pa, pb = segment_endpoints(piece)
                self.assertTrue(_close(pa, a) and _close(pb, b))
                # the stretch is as short as the curve between the two points, not the hairpin's loop
                self.assertLess(segment_length(piece), 1.5 * math.dist(a, b) + 1e-6)

    def test_reach_sees_the_tip(self):
        # the hairpin's tip lies beyond x = 50: the extent finds it, exact
        lo, hi = Reach(self.SPLINE)((1.0, 0.0))
        tip = max(self.SPLINE._evaluate(i / 20000)[0] for i in range(20001))
        self.assertEqual(lo, 0.0)
        self.assertGreaterEqual(hi, tip)
        self.assertLess(hi - tip, 1e-6)


class TestCurveBranch(unittest.TestCase):
    """Clothoid and formula have no control points: the cut's branch is chosen by
    certificate (unit speed of the clothoid, interval arithmetic of the formula).
    With 64 samples the spiral ended on another turn in 180 cuts out of 199, the
    involute up to 144 mm away."""

    CURVES = {
        "spiral clothoid": ClothoidSeg(origin=(0, 0), angle=0, a=1.0, start_param=0, end_param=30),
        "long involute": FormulaSeg(x="cos(t) + t*sin(t)", y="sin(t) - t*cos(t)", start_param=0, end_param=200),
        "non-uniform hairpin": FormulaSeg(x="50 * sin(pi * t**3)", y="0.01 * t", start_param=0, end_param=1),
    }

    def test_the_cut_ends_are_those_asked_for(self):
        for name, seg in self.CURVES.items():
            total = seg.t_range[1]
            for k in range(1, 60):
                ta, tb = total * k / 61, total * (k + 1) / 61
                a, b = seg.point_at(ta), seg.point_at(tb)
                with self.subTest(curve=name, k=k):
                    pa, pb = segment_endpoints(sub_segment(seg, a, b, seg.point_at((ta + tb) / 2)))
                    self.assertTrue(_close(pa, a) and _close(pb, b))
