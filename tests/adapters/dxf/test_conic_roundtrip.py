"""
tests/adapters/dxf/test_conic_roundtrip.py
------------------------------------------
DXF has no parabolas or hyperbolas. `to_dxf` writes them as their exact
rational quadratic spline: re-read, it is the same curve (every point of it
lies on the conic's equation) and closes the same area. A formula has no exact
spline: re-read it is within SAME_POINT of the curve; the clothoid too, the same.
"""

import math
import unittest
import warnings

import topo
import topo_dxf
from topo.precision import SAME_POINT
from topo.primitives import BSplineSeg, ClothoidSeg, FormulaSeg, HyperbolaSeg, LineSeg, ParabolaSeg

CONICS = [
    ParabolaSeg(vertex=(0.0, 0.0), focus=(0.0, 1.0), start_param=-4.0, end_param=4.0),
    HyperbolaSeg(center=(30.0, 0.0), major_axis=(3.0, 0.0), ratio=1.0, start_param=-1.2, end_param=1.2),
    HyperbolaSeg(center=(-7.0, 5.0), major_axis=(1.0, 2.0), ratio=0.6, start_param=1.5, end_param=-0.4).rotated(0.3),
]


def _round_trip(conic):
    ring = [conic, LineSeg(*reversed(conic.endpoints()))]
    doc = topo.load_segments(ring)
    result = topo.heal(doc).faces()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        drawing = topo_dxf.to_dxf(result, doc, include_texts=False)
    back = topo_dxf.document_from_msp(drawing.modelspace())
    return result, back


class TestConicRoundTrip(unittest.TestCase):

    def test_re_read_is_the_same_curve(self):
        for conic in CONICS:
            with self.subTest(conic=type(conic).__name__):
                _, back = _round_trip(conic)
                (spline,) = [e.segment for e in back.edges if isinstance(e.segment, BSplineSeg)]
                a, b, c, d, e, f = conic.equation
                for u in range(101):
                    x, y = spline.point_at(spline.t_range[0] + (spline.t_range[1] - spline.t_range[0]) * u / 100)
                    self.assertLess(abs(a * x * x + b * x * y + c * y * y + d * x + e * y + f), 1e-12)

    def test_re_read_closes_the_same_area(self):
        for conic in CONICS:
            with self.subTest(conic=type(conic).__name__):
                result, back = _round_trip(conic)
                (before,), (after,) = result.clusters, topo.heal(back).faces().clusters
                self.assertAlmostEqual(after.area, before.area, delta=1e-9 * before.area)

    def test_formula_and_clothoid_read_back_within_same_point(self):
        curves = [FormulaSeg("r*(cos(t) + t*sin(t))", "r*(sin(t) - t*cos(t))", 0.0, 1.2, params={"r": 10.0}),
                  ClothoidSeg(origin=(0.0, 0.0), angle=0.0, a=4.0, start_param=0.0, end_param=7.0)]
        for curve in curves:
            with self.subTest(curve=type(curve).__name__):
                _, back = _round_trip(curve)
                (spline,) = [e.segment for e in back.edges if isinstance(e.segment, BSplineSeg)]
                t0, t1 = spline.t_range
                worst = max(math.dist(q, topo.geometry.nearest_point([curve], q))
                            for q in (spline.point_at(t0 + (t1 - t0) * u / 200) for u in range(201)))
                self.assertLessEqual(worst, SAME_POINT)


if __name__ == "__main__":
    unittest.main()
