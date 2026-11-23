"""
tests/engine/primitives/test_ellipse_seg.py
------------------------------------
`EllipseSeg` (core/primitives/conics.py): parametrization, closure,
`.reversed()`, adaptive discretization. Same parametrization as the DXF
ELLIPSE group, verified against `ezdxf.math.ellipse` (see the class docstring)
— these tests verify only topo's pure maths, no ezdxf.
"""

import math
import unittest

from topo.core.primitives.mathseg import segment_is_closed, segment_endpoints
from topo.core.primitives.conics import EllipseSeg, CircleSeg


def _max_deviation_from_ellipse(seg: EllipseSeg, pts) -> float:
    """Maximum deviation of the discretized points from the true curve — the curve
    is known in closed form (parametric), so for each point it is enough to check
    that it satisfies the equation of the rotated/translated ellipse."""
    mx, my = seg.major_axis
    a = math.hypot(mx, my)
    b = a * seg.ratio
    ux, uy = mx / a, my / a  # asse maggiore, versore
    max_dev = 0.0
    for x, y in pts:
        dx, dy = x - seg.center[0], y - seg.center[1]
        # coordinates in the ellipse's local frame (major axis = u)
        u = dx * ux + dy * uy
        v = -dx * uy + dy * ux
        val = (u / a) ** 2 + (v / b) ** 2
        # val == 1 exact on the curve; the approximated radial deviation
        max_dev = max(max_dev, abs(math.sqrt(val) - 1.0) * a)
    return max_dev


class TestEllipseSegClosed(unittest.TestCase):

    def test_full_ellipse_is_closed(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=2 * math.pi)
        self.assertTrue(segment_is_closed(seg))

    def test_full_ellipse_discretize_closes_polyline(self):
        seg = EllipseSeg(center=(3, -2), major_axis=(10, 0), ratio=0.4,
                          start_param=0.0, end_param=2 * math.pi)
        pts = seg.discretize(tolerance=0.01)
        self.assertAlmostEqual(pts[0][0], pts[-1][0], places=6)
        self.assertAlmostEqual(pts[0][1], pts[-1][1], places=6)

    def test_open_arc_is_not_closed(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        self.assertFalse(segment_is_closed(seg))


class TestEllipseSegPointAt(unittest.TestCase):

    def test_axis_aligned_endpoints(self):
        """major_axis=(10,0), ratio=0.5: at t=0 end of the major axis, at t=pi/2 end of
        the minor axis (rotate90 CCW of the major)."""
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        start, end = segment_endpoints(seg)
        self.assertAlmostEqual(start[0], 10.0, places=6)
        self.assertAlmostEqual(start[1], 0.0, places=6)
        self.assertAlmostEqual(end[0], 0.0, places=6)
        self.assertAlmostEqual(end[1], 5.0, places=6)

    def test_rotated_major_axis(self):
        """major_axis=(0,10) (rotated 90°), ratio=0.5: the minor axis rotates with it —
        rotate90((0,10)) = (-10,0) scaled by ratio = (-5,0)."""
        seg = EllipseSeg(center=(1, 1), major_axis=(0, 10), ratio=0.5,
                          start_param=0.0, end_param=math.pi / 2)
        start, end = segment_endpoints(seg)
        self.assertAlmostEqual(start[0], 1.0, places=6)
        self.assertAlmostEqual(start[1], 11.0, places=6)
        self.assertAlmostEqual(end[0], -4.0, places=6)
        self.assertAlmostEqual(end[1], 1.0, places=6)

    def test_degenerates_to_circle_when_ratio_one(self):
        """ratio=1.0: every point of the discretized ellipse lies on the circle of the
        same radius — the general formula must reduce to a circle."""
        radius = 7.0
        ellipse = EllipseSeg(center=(2, -3), major_axis=(radius, 0), ratio=1.0,
                              start_param=0.0, end_param=2 * math.pi)
        pts = ellipse.discretize(tolerance=0.01)
        for x, y in pts:
            d = math.hypot(x - 2, y - (-3))
            self.assertAlmostEqual(d, radius, places=4)


class TestEllipseSegDiscretize(unittest.TestCase):

    def test_deviation_within_tolerance_eccentric(self):
        """Eccentric ellipse (low ratio, strongly varying curvature): every sampled
        point must lie on the true curve within a reasonable tolerance relative to the requested one."""
        seg = EllipseSeg(center=(0, 0), major_axis=(50, 0), ratio=0.1,
                          start_param=0.0, end_param=2 * math.pi)
        tolerance = 0.05
        pts = seg.discretize(tolerance=tolerance)
        max_dev = _max_deviation_from_ellipse(seg, pts)
        self.assertLess(max_dev, tolerance * 5)  # the EVALUATED points lie on the curve

    def test_zero_sweep_returns_degenerate_point(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=1.0, end_param=1.0, ccw=True)
        pts = seg.discretize(tolerance=0.01)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0], pts[1])


class TestEllipseSegReversed(unittest.TestCase):

    def test_reversed_swaps_params_and_ccw(self):
        seg = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5,
                          start_param=0.2, end_param=1.5, ccw=True)
        rev = seg.reversed()
        self.assertEqual(rev.start_param, seg.end_param)
        self.assertEqual(rev.end_param, seg.start_param)
        self.assertFalse(rev.ccw)

    def test_reversed_same_locus_opposite_order(self):
        seg = EllipseSeg(center=(3, -2), major_axis=(12, 4), ratio=0.6,
                          start_param=math.radians(20), end_param=math.radians(140),
                          ccw=True)
        rev = seg.reversed()
        fwd_pts = seg.discretize(tolerance=0.01)
        rev_pts = rev.discretize(tolerance=0.01)
        self.assertEqual(len(fwd_pts), len(rev_pts))
        for (xf, yf), (xr, yr) in zip(fwd_pts, reversed(rev_pts)):
            self.assertAlmostEqual(xf, xr, places=6)
            self.assertAlmostEqual(yf, yr, places=6)


if __name__ == "__main__":
    unittest.main()
