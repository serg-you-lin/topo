"""
test_mathseg.py
---------------
Ogni primitiva è una curva matematica (MAP.md D285): un punto e una derivata
per ogni parametro del suo dominio, e una conica dà la sua equazione.
Microcasi: le primitive di test_segment_motion più due spline a più tratti.
"""

import math
import unittest

from topo.core.primitives.segments import (
    BSplineSeg, CircleSeg, ConicSeg, EllipseSeg, MathSeg, segment_endpoints,
)
from topo.precision import FLOAT_NOISE
from tests.engine.primitives.test_segment_motion import _segments


def _all() -> list:
    return _segments() + [
        ("spline a tre tratti", BSplineSeg(degree=3, control_points=[(0, 0), (1, 3), (4, 4), (6, 1), (8, 2), (9, 0)],
                                           knots=[0, 0, 0, 0, 1, 2.5, 3, 3, 3, 3])),
        ("spline di grado 1", BSplineSeg(degree=1, control_points=[(0, 0), (2, 1), (3, -1)], knots=[0, 0, 1, 2, 2])),
    ]


def _samples(seg, n=7):
    t0, t1 = seg.t_range
    return [t0 + (t1 - t0) * k / n for k in range(n + 1)]


class TestMathSeg(unittest.TestCase):

    def test_ogni_primitiva_e_una_mathseg(self):
        for name, seg in _all():
            self.assertIsInstance(seg, MathSeg, name)

    def test_i_capi_del_dominio_sono_i_capi_della_curva(self):
        for name, seg in _all():
            start, end = segment_endpoints(seg)
            t0, t1 = seg.t_range
            self.assertLess(t0, t1, name)
            self.assertLessEqual(math.dist(seg.point_at(t0), start), FLOAT_NOISE, name)
            self.assertLessEqual(math.dist(seg.point_at(t1), end), FLOAT_NOISE, name)

    def test_la_derivata_e_quella_del_punto(self):
        # rapporto incrementale centrato: errore h² × la derivata terza, sotto 1e-6
        h = 1e-5
        for name, seg in _all():
            t0, t1 = seg.t_range
            for t in _samples(seg)[1:-1]:
                if isinstance(seg, BSplineSeg) and any(abs(t - k) < 2 * h for k in seg.knots):
                    continue    # sul nodo di una spline a tratti la derivata seconda salta
                (ax, ay), (bx, by) = seg.point_at(t - h), seg.point_at(t + h)
                dx, dy = seg.derivative_at(t)
                self.assertAlmostEqual(dx, (bx - ax) / (2 * h), delta=1e-6 * max(1.0, abs(dx)), msg=(name, t))
                self.assertAlmostEqual(dy, (by - ay) / (2 * h), delta=1e-6 * max(1.0, abs(dy)), msg=(name, t))

    def test_la_derivata_ai_capi_va_nel_verso_della_percorrenza(self):
        for name, seg in _all():
            t0, t1 = seg.t_range
            for t, toward in ((t0, t0 + (t1 - t0) * 1e-4), (t1 - (t1 - t0) * 1e-4, t1)):
                (ax, ay), (bx, by) = seg.point_at(t), seg.point_at(toward)
                dx, dy = seg.derivative_at(t)
                self.assertGreater(dx * (bx - ax) + dy * (by - ay), 0, (name, t))


class TestConicSeg(unittest.TestCase):

    def test_un_cerchio_e_un_ellisse_coi_semiassi_uguali(self):
        # D287: le formule dell'ellisse valgono sul cerchio, esatte
        for name, seg in _all():
            if isinstance(seg, CircleSeg):
                self.assertIsInstance(seg, EllipseSeg, name)
                self.assertEqual((seg.ratio, seg.major_axis), (1.0, (seg.radius, 0.0)), name)
                for t in _samples(seg):
                    u = seg.start_param + (t if seg.ccw else -t)
                    self.assertLessEqual(math.dist(seg.point_at(t), EllipseSeg._point_at(seg, u)), FLOAT_NOISE, (name, t))

    def test_arco_cerchio_ellisse_sono_coniche_le_altre_no(self):
        for name, seg in _all():
            self.assertEqual(isinstance(seg, ConicSeg), name.startswith(("arc", "circle", "ellipse")), name)

    def test_la_curva_sta_sulla_sua_equazione(self):
        for name, seg in _all():
            if not isinstance(seg, ConicSeg):
                continue
            a, b, c, d, e, f = seg.equation
            for t in _samples(seg, 24):
                x, y = seg.point_at(t)
                self.assertAlmostEqual(a * x * x + b * x * y + c * y * y + d * x + e * y + f, 0.0, delta=1e-9, msg=(name, t))

    def test_il_discriminante_dice_ellisse(self):
        for name, seg in _all():
            if isinstance(seg, ConicSeg):
                a, b, c, *_ = seg.equation
                self.assertLess(b * b - 4 * a * c, 0, name)

    def test_cerchio_ha_a_uguale_c_e_niente_xy(self):
        circles = [(name, seg) for name, seg in _all() if isinstance(seg, CircleSeg)]
        self.assertGreater(len(circles), 3)
        for name, seg in circles:
            a, b, c, *_ = seg.equation
            self.assertAlmostEqual(a, c, delta=FLOAT_NOISE * a, msg=name)
            self.assertAlmostEqual(b, 0.0, delta=FLOAT_NOISE * a, msg=name)


if __name__ == "__main__":
    unittest.main()
