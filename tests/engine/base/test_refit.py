# tests/engine/base/test_refit.py

import math
import unittest
import topo
from topo.core.primitives.line import LineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo.precision import FLOAT_NOISE, SAME_POINT


class TestRefitJointsUnderMotion(unittest.TestCase):
    """a curve written as points (line, quarter circle, line) refitted into three
    primitives stays a single chain. Every junction was rounded twice, from the
    end of a piece and from the start of the next: two copies 1 ulp apart, and
    with a cell edge between them the two pieces took different nodes."""

    def _profile(self, angle, dx, dy):
        import topo
        from tests.invariants import rigid
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + 3 * math.sin(a / 100 * math.pi / 2), 3 - 3 * math.cos(a / 100 * math.pi / 2))
                for a in range(1, 101)]
        pts += [(5.0, 3.0 + y * 0.05) for y in range(1, 41)]
        segment, _ = rigid(angle, dx, dy)
        return topo.load_segments([segment(LineSeg(start=a, end=b)) for a, b in zip(pts, pts[1:])]).edges

    def test_a_junction_on_a_cell_edge_stays_a_node(self):
        from collections import Counter
        from topo.core.base.refit import refit_tessellations
        # the motion puts the junction between the line and the arc midway between two 1e-3 cells
        for motion in [(0.0, 0.0, 0.0), (1.209, 2999999.9996208353, -2499999.9996809117)]:
            with self.subTest(motion=motion):
                out = refit_tessellations(self._profile(*motion))
                ends = Counter(n for e in out for n in (e.start, e.end))
                self.assertEqual(len(out), 3)
                self.assertEqual(sorted(ends.values()), [1, 1, 2, 2])


class TestRefitCornerFromTolerance(unittest.TestCase):
    """in the refit a corner is where no smooth curve passes within the tolerance,
    not a turn above 35° (a smoother number). Micro-cases."""

    def test_corner_of_20_degrees_written_as_points_stays_two_lines(self):
        t = math.radians(20)
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + k * 0.05 * math.cos(t), k * 0.05 * math.sin(t)) for k in range(1, 41)]
        self.assertEqual(self._refit(pts), ["LineSeg", "LineSeg"])

    def test_smooth_curve_that_is_not_an_arc_stays_a_curve(self):
        # a bump of 0.04 mm over 3 mm, the curvature changes (regr_01 at y 686): no corner
        pts = [(x * 0.02, 0.04 * math.sin(math.pi * x / 150) - 0.3 * (x / 150) ** 3) for x in range(151)]
        (kind,) = self._refit(pts)     # a single piece; arc or spline, within 0.02 both are fine
        self.assertNotEqual(kind, "LineSeg")

    def test_straight_and_tangent_fillet_without_fake_corners(self):
        # 2 mm of line, then a tangent quarter circle of radius 1: line + arc, no extra piece
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + math.sin(a / 40 * math.pi / 2), 1 - math.cos(a / 40 * math.pi / 2)) for a in range(1, 41)]
        self.assertEqual(self._refit(pts), ["LineSeg", "CircleSeg"])

    def _refit(self, pts):
        return [type(s).__name__ for s in _refit_segments(pts)]


def _refit_segments(pts):
    import topo
    from topo.core.base.refit import refit_tessellations
    out = refit_tessellations(topo.load_segments([LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]).edges)
    return [e.segment for e in out]


class TestRefitEllipse(unittest.TestCase):
    """The refit tries the ellipse before the spline: the simplest family within the
    tolerance (5 numbers against the control points). Micro-cases."""

    @staticmethod
    def _ellipse(t, angle=math.radians(30), a=4.0, b=1.6, center=(1000.0, 500.0)):
        c, s = math.cos(angle), math.sin(angle)
        return (center[0] + a * math.cos(t) * c - b * math.sin(t) * s,
                center[1] + a * math.cos(t) * s + b * math.sin(t) * c)

    def test_whole_ellipse_written_as_points_becomes_an_ellipse(self):
        pts = [self._ellipse(2 * math.pi * k / 300) for k in range(301)]   # sides below 0.1 mm
        (seg,) = _refit_segments(pts)
        self.assertIsInstance(seg, EllipseSeg)
        self.assertAlmostEqual(math.hypot(*seg.major_axis), 4.0, delta=SAME_POINT)
        self.assertAlmostEqual(seg.ratio, 0.4, delta=SAME_POINT)

    def test_ellipse_arc_keeps_the_ends_in_both_directions(self):
        for sweep in (2.0, -2.0):
            pts = [self._ellipse(0.3 + sweep * k / 100) for k in range(101)]
            (seg,) = _refit_segments(pts)
            self.assertIsInstance(seg, EllipseSeg)
            start, end = segment_endpoints(seg)
            self.assertLessEqual(math.dist(start, pts[0]), FLOAT_NOISE, sweep)
            self.assertLessEqual(math.dist(end, pts[-1]), FLOAT_NOISE, sweep)
            self.assertAlmostEqual(seg._sweep(), 2.0, delta=SAME_POINT, msg=sweep)

    def test_hyperbola_branch_written_as_points_becomes_a_hyperbola(self):
        # the conic the fit finds says which; sides below 0.1 mm like a real refit
        from topo.primitives import HyperbolaSeg
        hyp = HyperbolaSeg(center=(1000.0, 500.0), major_axis=(3.0, 1.0), ratio=0.6, start_param=-0.9, end_param=1.1)
        pts = [hyp.point_at(hyp.t_range[1] * k / 120) for k in range(121)]
        (seg,) = _refit_segments(pts)
        self.assertIsInstance(seg, HyperbolaSeg)
        start, end = segment_endpoints(seg)
        self.assertLessEqual(math.dist(start, pts[0]), FLOAT_NOISE)
        self.assertLessEqual(math.dist(end, pts[-1]), FLOAT_NOISE)

    def test_curve_that_is_not_a_conic_does_not_become_an_ellipse(self):
        pts = [(x * 0.05, math.sin(x / 80) + 0.12 * math.sin(x / 20)) for x in range(300)]
        self.assertFalse(any(isinstance(s, EllipseSeg) and not isinstance(s, CircleSeg) for s in _refit_segments(pts)))


def _polygon(center, radius, sides, start=0.3):
    pts = [(center[0] + radius * math.cos(start + 2 * math.pi * k / sides),
            center[1] + radius * math.sin(start + 2 * math.pi * k / sides)) for k in range(sides)]
    return [LineSeg(start=pts[k], end=pts[(k + 1) % sides]) for k in range(sides)]


def _circles(segments):
    faces = topo.heal(topo.load_segments(segments), max_gap=0.1).faces()
    return [s for cl in faces.clusters for ct in [cl.outer, *cl.inners] for s in ct.segments if (isinstance(s, CircleSeg) and s.full)]


class TestRefitCircleRings(unittest.TestCase):
    """a ring lying wholly within 0.02 mm of a circle and going round it is that circle."""

    def test_hole_with_long_sides_becomes_circle(self):
        # brute force (seed 42): r 1.424 in 71 sides of 0.14 mm, beyond the short side
        (c,) = _circles(_polygon((5, 5), 1.424, 64))
        self.assertAlmostEqual(c.radius, 1.424, delta=0.002)

    def test_hole_with_a_gap_and_a_protruding_piece(self):
        ring = _polygon((5, 5), 1.0, 60)
        a = ring[7]
        ring[7] = LineSeg(start=a.start, end=(a.start[0] + 0.9 * (a.end[0] - a.start[0]), a.start[1] + 0.9 * (a.end[1] - a.start[1])))
        ring.append(LineSeg(start=ring[20].start, end=(ring[20].start[0] + 0.05, ring[20].start[1])))
        self.assertEqual(len(_circles(ring)), 1)

    def test_double_piece_running_on_the_circle_goes_with_the_circle(self):
        # seed 42: a double stretch along the loop, left aside, broke the circle into arc + line
        ring = _polygon((5, 5), 1.0, 60)
        a, b = ring[10].start, ring[10].end
        for extra in (LineSeg(start=a, end=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)),          # from the vertex, free end
                      LineSeg(start=((2 * a[0] + b[0]) / 3, (2 * a[1] + b[1]) / 3), end=b)):  # starts at mid-side
            faces = topo.heal(topo.load_segments(ring + [extra]), max_gap=0.1).faces()
            self.assertEqual([[type(s) for s in ct.segments] for cl in faces.clusters for ct in [cl.outer, *cl.inners]],
                             [[CircleSeg]])

    def test_true_polygon_remains(self):
        # hexagon of r 5: at mid-side it departs 0.67 mm from the circle
        self.assertEqual(_circles(_polygon((0, 0), 5.0, 6)), [])

    def test_half_turn_does_not_become_a_circle(self):
        half = _polygon((0, 0), 1.0, 60)[:30]
        net = topo.heal(topo.load_segments(half + [LineSeg(start=half[-1].end, end=half[0].start)]), max_gap=0.1)
        self.assertEqual([s for cl in net.faces().clusters for s in cl.outer.segments if (isinstance(s, CircleSeg) and s.full)], [])
