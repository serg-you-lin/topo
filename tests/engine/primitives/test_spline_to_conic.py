"""
tests/engine/primitives/test_spline_to_conic.py
-----------------------------------------------
A spline within SAME_POINT of an arc or an ellipse is that arc or that
ellipse: same exact ends, same direction, walked once. Micro-cases: cubic
splines approximating known arcs and ellipses within 1e-5; a true spline (a
wave) and one deformed by 3e-3 stay splines.
"""

import math
import random
import unittest

from topo.core.base.refit import refit_native_curves
from topo.core.geometry.curve_tests import _ellipse_distance
from topo.core.geometry.spline_fit import approximate_bspline
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo.core.geometry.fitting import conic_of_spline
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.line import LineSeg
from topo.core.topology.edge import Edge
from topo.model.role import ContourRole
from topo.precision import FLOAT_NOISE, SAME_POINT


def _spline_of(seg, tolerance=1e-5) -> BSplineSeg:
    """The cubic spline within `tolerance` of the curve `seg`, with its ends."""
    t0, t1 = seg.t_range
    pts = [seg.point_at(t0 + (t1 - t0) * k / 400) for k in range(401)]
    control, knots = approximate_bspline(pts, 3, tolerance)
    return BSplineSeg(degree=3, control_points=control, knots=knots)


CASES = [
    ("arco ccw", CircleSeg(center=(1.0, 1.0), radius=5.0, start_angle=0.5, end_angle=2.0), CircleSeg),
    ("arco cw", CircleSeg(center=(1.0, 1.0), radius=5.0, start_angle=2.0, end_angle=0.5, ccw=False), CircleSeg),
    ("arco di 300°", CircleSeg(center=(0.0, 0.0), radius=3.0, start_angle=0.0, end_angle=5.3), CircleSeg),
    ("cerchio da 0,7 rad", CircleSeg(center=(1.0, 1.0), radius=5.0, start_angle=0.7, end_angle=0.7 + 2 * math.pi), CircleSeg),
    ("arco d'ellisse", EllipseSeg(center=(3.0, -2.0), major_axis=(8.0, 3.0), ratio=0.4, start_param=0.3, end_param=2.5),
     EllipseSeg),
    ("arco d'ellisse cw", EllipseSeg(center=(3.0, -2.0), major_axis=(8.0, 3.0), ratio=0.4, start_param=2.5,
                                     end_param=0.3, ccw=False), EllipseSeg),
    ("ellisse intera", EllipseSeg(center=(3.0, -2.0), major_axis=(8.0, 3.0), ratio=0.4, start_param=1.0,
                                  end_param=1.0 + 2 * math.pi), EllipseSeg),
]


class TestConicOfSpline(unittest.TestCase):

    def test_diventa_la_conica_coi_capi_della_spline(self):
        for name, seg, kind in CASES:
            with self.subTest(name):
                spline = _spline_of(seg)
                conic = conic_of_spline(spline, SAME_POINT)
                self.assertIs(type(conic), kind)
                for p, q in zip(conic.endpoints(), spline.endpoints()):
                    self.assertLessEqual(math.dist(p, q), FLOAT_NOISE)
                self.assertAlmostEqual(conic._sweep(), seg._sweep(), delta=1e-4)
                self.assertEqual(conic.ccw, seg.ccw)

    def test_ogni_punto_della_spline_entro_same_point(self):
        for name, seg, _ in CASES:
            with self.subTest(name):
                spline = _spline_of(seg)
                conic = conic_of_spline(spline, SAME_POINT)
                a = math.hypot(*conic.major_axis)
                axis = (conic.major_axis[0] / a, conic.major_axis[1] / a)
                for p in spline.discretize(tolerance=1e-5):
                    distance, _ = _ellipse_distance(p, conic.center, axis, a, a * conic.ratio)
                    self.assertLessEqual(distance, SAME_POINT)

    def test_una_spline_vera_resta(self):
        wave = BSplineSeg(degree=3, control_points=[(0, 0), (2, 5), (6, -3), (9, 1)], knots=[0, 0, 0, 0, 1, 1, 1, 1])
        self.assertIsNone(conic_of_spline(wave, SAME_POINT))

    def test_fuori_da_same_point_resta(self):
        # half ellipse, a control point moved by 3e-3: more than SAME_POINT from the conic
        spline = _spline_of(EllipseSeg(center=(0.0, 0.0), major_axis=(8.0, 0.0), ratio=0.4, start_param=0.0,
                                       end_param=math.pi))
        k = len(spline.control_points) // 2
        bumped = [(x, y + (3e-3 if i == k else 0.0)) for i, (x, y) in enumerate(spline.control_points)]
        self.assertIsNone(conic_of_spline(BSplineSeg(3, bumped, spline.knots), SAME_POINT))

    def test_mai_l_iperbole(self):
        from topo.core.primitives.conics import HyperbolaSeg
        hyp = HyperbolaSeg(center=(0.0, 0.0), major_axis=(2.0, 0.0), ratio=0.8, start_param=-1.0, end_param=1.2)
        self.assertIsNone(conic_of_spline(_spline_of(hyp), SAME_POINT))


class TestRefitNativeSplines(unittest.TestCase):

    def test_la_spline_diventa_arco_e_tiene_i_nodi(self):
        spline = _spline_of(CircleSeg(center=(1.0, 1.0), radius=5.0, start_angle=0.5, end_angle=2.0))
        start, end = spline.endpoints()
        line = LineSeg(start=end, end=(-10.0, 0.0))
        edges = refit_native_curves([Edge(role=ContourRole.UNKNOWN, start=start, end=end, segment=spline),
                                      Edge(role=ContourRole.UNKNOWN, start=end, end=line.end, segment=line)])
        self.assertIsInstance(edges[0].segment, CircleSeg)
        self.assertEqual((edges[0].start, edges[0].end), (start, end))
        self.assertIs(edges[1].segment, line)


    def test_ellisse_coi_semiassi_uguali_diventa_il_suo_cerchio(self):
        for ellipse in (EllipseSeg(center=(2.0, 1.0), major_axis=(3.0, 4.0), ratio=1.0, start_param=0.4, end_param=2.0),
                        EllipseSeg(center=(2.0, 1.0), major_axis=(-3.0, 4.0), ratio=1.0, start_param=2.0, end_param=0.4,
                                   ccw=False),
                        EllipseSeg(center=(2.0, 1.0), major_axis=(3.0, -4.0), ratio=1.0, start_param=0.0,
                                   end_param=2 * math.pi)):
            start, end = ellipse.endpoints()
            [edge] = refit_native_curves([Edge(role=ContourRole.UNKNOWN, start=start, end=end, segment=ellipse)])
            circle = edge.segment
            self.assertIsInstance(circle, CircleSeg)
            self.assertEqual((circle.radius, circle.ccw), (5.0, ellipse.ccw))
            self.assertAlmostEqual(circle._sweep(), ellipse._sweep(), delta=FLOAT_NOISE)
            for k in range(9):
                t = circle.t_range[1] * k / 8
                self.assertLessEqual(math.dist(circle.point_at(t), ellipse.point_at(t)), FLOAT_NOISE)

    def test_ellisse_vera_resta(self):
        ellipse = EllipseSeg(center=(0.0, 0.0), major_axis=(3.0, 0.0), ratio=0.999, start_param=0.0, end_param=1.0)
        start, end = ellipse.endpoints()
        [edge] = refit_native_curves([Edge(role=ContourRole.UNKNOWN, start=start, end=end, segment=ellipse)])
        self.assertIs(edge.segment, ellipse)


class TestFullTurn(unittest.TestCase):
    """A full turn from any angle stays full: (a + 2π) − a lands one ulp from 2π."""

    def test_cerchio_da_ogni_angolo_e_intero(self):
        rng = random.Random(7)
        for _ in range(2000):
            a = rng.uniform(-9.0, 9.0)
            self.assertTrue(CircleSeg(center=(0.0, 0.0), radius=1.0, start_angle=a, end_angle=a + 2 * math.pi).full)
            self.assertTrue(CircleSeg(center=(0.0, 0.0), radius=1.0).rotated(a).full)


if __name__ == "__main__":
    unittest.main()
