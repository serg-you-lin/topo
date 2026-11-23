"""
tests/engine/primitives/test_discretize_tolerance.py
--------------------------------------------
The geometric promise of 1.0 starts here: `discretize(tol)` of circle, arc and
ellipse stays within `tol` of the true curve at every scale. The sagitta is
absolute, so the sides must grow with the radius: a fixed cap on the number of
sides violates it beyond a certain size (the old 128-side cap of the circle
overshot from r ≈ 33 at tol 0.01).

Measure: the curve sampled densely, for each sample the distance from the
nearest stretch of the polyline; the vertices lie on the curve, so the maximum
is the true deviation.
"""

import math
import unittest

from topo.core.primitives.polyline import _point_to_segment_distance
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo.core.primitives.spline import BSplineSeg

TOL = 0.01
RADII = (0.005, 1.0, 10.0, 33.0, 100.0, 500.0, 2000.0)


def _deviation(poly, curve_pts) -> float:
    """Maximum deviation of the curve's samples from the polyline."""
    worst = 0.0
    for p in curve_pts:
        # nearest vertex, then the two stretches that touch it
        j = min(range(len(poly)), key=lambda i: (poly[i][0] - p[0]) ** 2 + (poly[i][1] - p[1]) ** 2)
        d = min(
            _point_to_segment_distance(p, poly[k], poly[k + 1])
            for k in (j - 1, j) if 0 <= k < len(poly) - 1
        )
        worst = max(worst, d)
    return worst


def _samples(f, t0: float, t1: float, n: int = 4000):
    return [f(t0 + (t1 - t0) * i / n) for i in range(n + 1)]


class TestDiscretizeWithinTolerance(unittest.TestCase):

    def test_circle_every_radius(self):
        for r in RADII:
            with self.subTest(r=r):
                poly = CircleSeg((0.0, 0.0), r).discretize(tolerance=TOL)
                curve = _samples(lambda t: (r * math.cos(t), r * math.sin(t)), 0.0, 2 * math.pi)
                self.assertLessEqual(_deviation(poly, curve), TOL)

    def test_circle_sides_grow_with_radius(self):
        # no cap: at r 2000 about π·√(r/2·tol) ≈ 994 sides are needed
        self.assertGreater(len(CircleSeg((0.0, 0.0), 2000.0).discretize(tolerance=TOL)) - 1, 900)

    def test_arc_every_radius(self):
        for r in RADII:
            with self.subTest(r=r):
                arc = CircleSeg((0.0, 0.0), r, 0.0, 1.5 * math.pi)
                curve = _samples(lambda t: (r * math.cos(t), r * math.sin(t)), 0.0, 1.5 * math.pi)
                self.assertLessEqual(_deviation(arc.discretize(tolerance=TOL), curve), TOL)

    def test_ellipse_every_scale_and_ratio(self):
        for a, ratio in ((10.0, 1.0), (100.0, 0.5), (500.0, 0.1), (2000.0, 0.02), (1.0, 0.05)):
            with self.subTest(a=a, ratio=ratio):
                e = EllipseSeg((0.0, 0.0), (a, 0.0), ratio, 0.0, 2 * math.pi)
                curve = _samples(e._point_at, 0.0, 2 * math.pi, 20000)
                self.assertLessEqual(_deviation(e.discretize(tolerance=TOL), curve), TOL)

    def test_flat_ellipse(self):
        # a subdivision looking only at the midpoint came out by 0.0113 (at 139, ratio
        # 0.0027), the sharp corner at the ends of the major axis
        e = EllipseSeg((0.0, 0.0), (139.0, 0.0), 0.0027, 0.0, 2 * math.pi)
        curve = _samples(e._point_at, 0.0, 2 * math.pi, 40000)
        self.assertLessEqual(_deviation(e.discretize(tolerance=TOL), curve), TOL)

    def test_rotated_partial_clockwise_ellipse(self):
        a = 300.0
        axis = (a * math.cos(0.7), a * math.sin(0.7))
        e = EllipseSeg((1e4, -3e4), axis, 0.05, 2.0, -1.5, ccw=False)
        curve = _samples(e._point_at, 2.0, -1.5, 20000)
        self.assertLessEqual(_deviation(e.discretize(tolerance=TOL), curve), TOL)



def _deviation_along(poly, curve_pts, window: int = 64) -> float:
    """Like `_deviation`, but the samples and the polygon go the same way: every
    sample looks at the sides from that of the last sample onwards. A subset of
    the sides gives a distance never smaller: the test does not pass by mistake.
    It serves where the sides are long (spline)."""
    worst, j = 0.0, 0
    for p in curve_pts:
        ks = range(max(j - 1, 0), min(j + window, len(poly) - 1))
        d, j = min((_point_to_segment_distance(p, poly[k], poly[k + 1]), k) for k in ks)
        worst = max(worst, d)
    return worst


def _spline(degree, n, clamped, rational, seed):
    """A pseudo-random but fixed spline: locked knots or not, weights or not."""
    import random
    rnd = random.Random(seed)
    cps = [(rnd.uniform(-50, 50), rnd.uniform(-50, 50)) for _ in range(n)]
    if clamped:
        inner = sorted(rnd.uniform(0, 10) for _ in range(n - degree - 1))
        knots = [0.0] * (degree + 1) + inner + [10.0] * (degree + 1)
    else:
        knots = sorted(rnd.uniform(-3, 13) for _ in range(n + degree + 1))
    weights = [rnd.uniform(0.2, 5) for _ in range(n)] if rational else None
    return BSplineSeg(degree=degree, control_points=cps, knots=knots, weights=weights)


class TestSplinePolygon(unittest.TestCase):
    """The spline's polygon is within `tol` by proof: Bézier pieces, halved until the
    control points are within `tol` of the chord. The check on the midpoint alone
    came out by 2.5·tol on a short spline with many knot intervals (236 of the 9612
    splines of the 631 DXFs of tests/)."""

    def _check(self, s, tol, n=4000):
        lo, hi = s.knots[s.degree], s.knots[-(s.degree + 1)]
        poly = s.discretize(tolerance=tol)
        self.assertEqual((poly[0], poly[-1]), s.endpoints())
        self.assertLessEqual(_deviation_along(poly, _samples(s._evaluate, lo, hi, n)), tol)

    def test_many_intervals_on_a_short_spline(self):
        # 191 zig-zag control points over 4.75 mm, 188 intervals: the shape of the worst
        # of the 631 (before 0.0023 from the curve at tol 0.001)
        cps = [(0.025 * i, 0.003 * (-1) ** i) for i in range(191)]
        knots = [0.0] * 4 + [i / 188 for i in range(1, 188)] + [1.0] * 4
        self._check(BSplineSeg(degree=3, control_points=cps, knots=knots), 1e-3, 20000)

    def test_degrees_nodes_and_weights(self):
        for degree in (1, 2, 3, 5):
            for clamped in (True, False):
                for rational in (False, True):
                    with self.subTest(degree=degree, clamped=clamped, rational=rational):
                        s = _spline(degree, degree + 8, clamped, rational, seed=degree * 4 + clamped * 2 + rational)
                        self._check(s, 1e-3)

    def test_multiple_nodes(self):
        cps = [(0.0, 0.0), (10.0, 20.0), (20.0, -5.0), (30.0, 15.0), (40.0, 0.0), (50.0, 30.0), (60.0, 0.0)]
        knots = [0.0] * 4 + [0.5, 0.5, 0.5] + [1.0] * 4
        self._check(BSplineSeg(degree=3, control_points=cps, knots=knots), 1e-3)

    def test_a_non_positive_weight_is_refused(self):
        s = BSplineSeg(degree=2, control_points=[(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)],
                       knots=[0.0, 0.0, 0.0, 1.0, 1.0, 1.0], weights=[1.0, -0.5, 1.0])
        with self.assertRaises(ValueError):
            s.discretize(tolerance=1e-3)

class TestEllipseOnParameterGrid(unittest.TestCase):
    """an ellipse uses the grid of its parameter, so the same ellipse gives the same
    polygon however the file cut it."""

    def _ellipse(self, t0, t1, ccw=True):
        return EllipseSeg((3.0, -2.0), (40.0, 30.0), 0.4, t0, t1, ccw)

    def _same(self, pts_a, pts_b):
        self.assertEqual(len(pts_a), len(pts_b))
        for p, q in zip(pts_a, pts_b):
            self.assertAlmostEqual(p[0], q[0], places=9)
            self.assertAlmostEqual(p[1], q[1], places=9)

    def test_four_quarters_are_the_ellipse(self):
        whole = self._ellipse(0.0, 2 * math.pi).discretize(tolerance=TOL)
        joined = [whole[0]]
        for q in range(4):
            joined += self._ellipse(q * math.pi / 2, (q + 1) * math.pi / 2).discretize(tolerance=TOL)[1:]
        self._same(joined, whole)

    def test_reversed_ellipse_gives_the_same_points_backwards(self):
        fwd = self._ellipse(0.37, 2.9).discretize(tolerance=TOL)
        self._same(self._ellipse(0.37, 2.9).reversed().discretize(tolerance=TOL), fwd[::-1])


class TestArcOnCircleGrid(unittest.TestCase):
    """an arc uses the grid of its circle (anchored at angle 0), so the same circle
    gives the same polygon however the file cut it."""

    R = 50.0

    def _circle(self):
        return CircleSeg((3.0, -2.0), self.R).discretize(tolerance=TOL)

    def _arc(self, a0, a1, ccw=True):
        return CircleSeg((3.0, -2.0), self.R, a0, a1, ccw).discretize(tolerance=TOL)

    def _same(self, pts_a, pts_b):
        self.assertEqual(len(pts_a), len(pts_b))
        for p, q in zip(pts_a, pts_b):
            self.assertAlmostEqual(p[0], q[0], places=9)
            self.assertAlmostEqual(p[1], q[1], places=9)

    def test_four_quarters_are_the_circle(self):
        circle = self._circle()
        n = len(circle) - 1
        self.assertEqual(n % 4, 0, "grid chosen to have the quarters on the vertices")
        joined = [circle[0]]
        for q in range(4):
            joined += self._arc(q * math.pi / 2, (q + 1) * math.pi / 2)[1:]
        self._same(joined, circle)

    def test_off_grid_arc_is_a_piece_of_the_circle(self):
        # ends off the grid: the interior vertices are those of the circle, the two
        # head stretches shorter than the step
        circle = self._circle()
        step = 2 * math.pi / (len(circle) - 1)
        a0, a1 = 0.3 * step, 10.7 * step
        arc = self._arc(a0, a1)
        self._same(arc[1:-1], circle[1:11])
        self.assertLess(math.dist(arc[0], arc[1]), math.dist(circle[0], circle[1]))
        self.assertLess(math.dist(arc[-2], arc[-1]), math.dist(circle[0], circle[1]))

    def test_reversed_arc_gives_the_same_points_backwards(self):
        fwd = self._arc(0.37, 2.9)
        back = CircleSeg((3.0, -2.0), self.R, 0.37, 2.9).reversed().discretize(tolerance=TOL)
        self._same(back, fwd[::-1])

    def test_arc_shorter_than_a_step_is_one_chord(self):
        step = 2 * math.pi / (len(self._circle()) - 1)
        self.assertEqual(len(self._arc(0.2 * step, 0.7 * step)), 2)

    def test_endpoint_on_a_grid_point_gives_no_degenerate_side(self):
        step = 2 * math.pi / (len(self._circle()) - 1)
        arc = self._arc(3 * step + 1e-13, 9 * step - 1e-13)
        for p, q in zip(arc, arc[1:]):
            self.assertGreater(math.dist(p, q), 1e-6)


if __name__ == "__main__":
    unittest.main()


class TestGridSnapUnderMotion(unittest.TestCase):
    """(`_GRID_SNAP`): a vertex of the circle's grid less than 1e-9 mm from an arc
    end is skipped. A circle cut at 5e-10 mm from a vertex: `heal()` gives the
    same reading in place, rotated and far (the grid stays anchored at angle 0)."""

    def test_circle_cut_near_a_grid_vertex(self):
        import topo
        from tests.invariants import rigid
        from topo.core.primitives.conics import _circle_sides
        from topo.core.primitives.mathseg import DEFAULT_TOLERANCE
        r = 10.0
        cut = 5 * 2 * math.pi / _circle_sides(r, DEFAULT_TOLERANCE) + 5e-10 / r
        arcs = [CircleSeg(center=(0.0, 0.0), radius=r, start_angle=cut, end_angle=cut + math.pi),
                CircleSeg(center=(0.0, 0.0), radius=r, start_angle=cut + math.pi, end_angle=cut + 2 * math.pi)]

        def reading(motion):
            segment, _ = rigid(*motion)
            res = topo.heal(topo.load_segments([segment(a) for a in arcs])).faces()
            return res.is_valid, len(res.clusters), len(res.loose), res.clusters[0].outer.area

        at_rest = reading((0.0, 0.0, 0.0))
        self.assertEqual(at_rest[:3], (True, 1, 0))
        for motion in ((0.031, 0.0, 0.0), (0.7, 3e6, -2.5e6), (2.294, 3e6, -2.5e6)):
            with self.subTest(motion=motion):
                moved = reading(motion)
                self.assertEqual(moved[:3], at_rest[:3])
                self.assertAlmostEqual(moved[3], at_rest[3], delta=1e-2)
