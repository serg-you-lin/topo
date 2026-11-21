"""
tests/adapters/dxf/test_conic_roundtrip.py
------------------------------------------
D288: il DXF non ha parabole né iperboli. `to_dxf` le scrive come la loro
spline razionale quadratica, esatta: riletta, è la stessa curva (ogni suo
punto sta sull'equazione della conica) e chiude la stessa area. D289: una
formula non ha una spline esatta: riletta sta entro SAME_POINT dalla curva.
"""

import math
import unittest
import warnings

import topo
import topo_dxf
from topo.precision import SAME_POINT
from topo.primitives import BSplineSeg, FormulaSeg, HyperbolaSeg, LineSeg, ParabolaSeg

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

    def test_riletta_e_la_stessa_curva(self):
        for conic in CONICS:
            with self.subTest(conic=type(conic).__name__):
                _, back = _round_trip(conic)
                (spline,) = [e.segment for e in back.edges if isinstance(e.segment, BSplineSeg)]
                a, b, c, d, e, f = conic.equation
                for u in range(101):
                    x, y = spline.point_at(spline.t_range[0] + (spline.t_range[1] - spline.t_range[0]) * u / 100)
                    self.assertLess(abs(a * x * x + b * x * y + c * y * y + d * x + e * y + f), 1e-12)

    def test_riletta_chiude_la_stessa_area(self):
        for conic in CONICS:
            with self.subTest(conic=type(conic).__name__):
                result, back = _round_trip(conic)
                (before,), (after,) = result.clusters, topo.heal(back).faces().clusters
                self.assertAlmostEqual(after.area, before.area, delta=1e-9 * before.area)

    def test_formula_riletta_entro_same_point(self):
        involute = FormulaSeg("r*(cos(t) + t*sin(t))", "r*(sin(t) - t*cos(t))", 0.0, 1.2, params={"r": 10.0})
        _, back = _round_trip(involute)
        (spline,) = [e.segment for e in back.edges if isinstance(e.segment, BSplineSeg)]
        t0, t1 = spline.t_range
        worst = max(math.dist(q, topo.geometry.nearest_point([involute], q))
                    for q in (spline.point_at(t0 + (t1 - t0) * u / 200) for u in range(201)))
        self.assertLessEqual(worst, SAME_POINT)


if __name__ == "__main__":
    unittest.main()
