"""
test_mathseg.py
---------------
Every primitive is a mathematical curve: a point and a derivative for every
parameter of its domain, and a conic gives its equation. Micro-cases: the
primitives of test_segment_motion plus two multi-piece splines.
"""

import math
import unittest

import topo
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.mathseg import MathSeg, segment_endpoints
from topo.core.primitives.clothoid import ClothoidSeg
from topo.core.primitives.conics import CircleSeg, ConicSeg, EllipseSeg, HyperbolaSeg, ParabolaSeg
from topo.core.primitives.formula import FormulaSeg
from topo.core.primitives.line import LineSeg
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
        # centred incremental ratio: error h² × the third derivative, below 1e-6
        h = 1e-5
        for name, seg in _all():
            t0, t1 = seg.t_range
            for t in _samples(seg)[1:-1]:
                if isinstance(seg, BSplineSeg) and any(abs(t - k) < 2 * h for k in seg.knots):
                    continue    # at the knot of a piecewise spline the second derivative jumps
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
        # the ellipse's formulas hold on the circle, exact
        for name, seg in _all():
            if isinstance(seg, CircleSeg):
                self.assertIsInstance(seg, EllipseSeg, name)
                self.assertEqual((seg.ratio, seg.major_axis), (1.0, (seg.radius, 0.0)), name)
                for t in _samples(seg):
                    u = seg.start_param + (t if seg.ccw else -t)
                    self.assertLessEqual(math.dist(seg.point_at(t), EllipseSeg._point_at(seg, u)), FLOAT_NOISE, (name, t))

    def test_arco_cerchio_ellisse_sono_coniche_le_altre_no(self):
        for name, seg in _all():
            self.assertEqual(isinstance(seg, ConicSeg), name.startswith(("arc", "circle", "ellipse", "parabola", "hyperbola")), name)

    def test_la_curva_sta_sulla_sua_equazione(self):
        for name, seg in _all():
            if not isinstance(seg, ConicSeg):
                continue
            a, b, c, d, e, f = seg.equation
            for t in _samples(seg, 24):
                x, y = seg.point_at(t)
                self.assertAlmostEqual(a * x * x + b * x * y + c * y * y + d * x + e * y + f, 0.0, delta=1e-9, msg=(name, t))

    def test_il_discriminante_dice_quale_conica(self):
        # B² − 4AC: < 0 ellipse (and circle), = 0 parabola, > 0 hyperbola; up to the
        # common factor, compared against the square of the coefficients
        for name, seg in _all():
            if isinstance(seg, ConicSeg):
                a, b, c, *_ = seg.equation
                disc, size = b * b - 4 * a * c, max(a * a, b * b, c * c)
                if isinstance(seg, ParabolaSeg):
                    self.assertLessEqual(abs(disc), 1e-12 * size, name)
                elif isinstance(seg, HyperbolaSeg):
                    self.assertGreater(disc, 0, name)
                else:
                    self.assertLess(disc, 0, name)

    def test_cerchio_ha_a_uguale_c_e_niente_xy(self):
        circles = [(name, seg) for name, seg in _all() if isinstance(seg, CircleSeg)]
        self.assertGreater(len(circles), 3)
        for name, seg in circles:
            a, b, c, *_ = seg.equation
            self.assertAlmostEqual(a, c, delta=FLOAT_NOISE * a, msg=name)
            self.assertAlmostEqual(b, 0.0, delta=FLOAT_NOISE * a, msg=name)



def _ellipse_perimeter(a: float, b: float) -> float:
    """The exact perimeter with the arithmetic-geometric mean (Gauss, Ivory):
    P = 2π/M · (a² − Σ 2ⁿ⁻¹·cₙ²), c₀² = a² − b², cₙ₊₁ = (aₙ − bₙ)/2."""
    total, weight = (a * a - b * b) / 2, 0.5
    x, y = a, b
    while x - y > 1e-15 * x:
        c = (x - y) / 2
        x, y = (x + y) / 2, math.sqrt(x * y)
        weight *= 2
        total += weight * c * c
    return 2 * math.pi * (a * a - total) / x


class TestAlgebra(unittest.TestCase):
    """`algebra` says what mathematics writes the curve exactly, read from the curve."""

    def test_ogni_primitiva_ha_il_suo_gruppo(self):
        expected = {LineSeg: "polynomial", ParabolaSeg: "polynomial", CircleSeg: "rational", EllipseSeg: "rational",
                    HyperbolaSeg: "rational", ClothoidSeg: "transcendental"}
        for name, seg in _all():
            if type(seg) in expected:
                self.assertEqual(seg.algebra, expected[type(seg)], name)

    def test_spline_polinomiale_senza_pesi_o_coi_pesi_uguali(self):
        cp, knots = [(0, 0), (1, 2), (3, 1)], [0, 0, 0, 1, 1, 1]
        self.assertEqual(BSplineSeg(2, cp, knots).algebra, "polynomial")
        self.assertEqual(BSplineSeg(2, cp, knots, weights=[2.5, 2.5, 2.5]).algebra, "polynomial")
        self.assertEqual(BSplineSeg(2, cp, knots, weights=[1, math.sqrt(0.5), 1]).algebra, "rational")

    def test_spline_coi_pesi_uguali_e_la_stessa_curva_senza_pesi(self):
        # the common factor cancels: it really is a polynomial
        cp, knots = [(0, 0), (1, 2), (3, 1)], [0, 0, 0, 1, 1, 1]
        a, b = BSplineSeg(2, cp, knots), BSplineSeg(2, cp, knots, weights=[2.5, 2.5, 2.5])
        for t in (0.0, 0.3, 0.71, 1.0):
            self.assertAlmostEqual(math.dist(a.point_at(t), b.point_at(t)), 0.0, delta=FLOAT_NOISE)

    def test_la_formula_dal_suo_albero(self):
        cases = [("t", "t**2", "polynomial"), ("t", "t / 2 + sqrt(2) * t", "polynomial"),
                 ("t", "t**n", "polynomial"), ("t", "1 / (1 + t**2)", "rational"), ("t", "t**-2", "rational"),
                 ("t", "t**0.5", "transcendental"), ("t", "2**t", "transcendental"),
                 ("r*cos(t)", "r*sin(t)", "transcendental")]   # a circle, but the tree does not prove it
        for x, y, algebra in cases:
            with self.subTest(x=x, y=y):
                self.assertEqual(FormulaSeg(x, y, 1.0, 2.0, params={"n": 3.0, "r": 2.0}).algebra, algebra)

    def test_il_moto_non_cambia_il_gruppo(self):
        for name, seg in _all():
            for moved in (seg.reversed(), seg.rotated(0.7), seg.mirrored(angle=0.3), seg.scaled(2.0)):
                self.assertEqual(moved.algebra, seg.algebra, name)


class TestExactLength(unittest.TestCase):
    """every curve measures its length as ∫|P'|, not the sum of the chords."""

    def test_perimetro_dell_ellisse(self):
        ellipse = EllipseSeg(center=(0.0, 0.0), major_axis=(5.0, 0.0), ratio=0.6, start_param=0.0, end_param=2 * math.pi)
        self.assertAlmostEqual(topo.geometry.segment_length(ellipse), _ellipse_perimeter(5.0, 3.0), delta=1e-10)

    def test_quarto_di_cerchio_razionale(self):
        quarter = BSplineSeg(degree=2, control_points=[(1, 0), (1, 1), (0, 1)], knots=[0, 0, 0, 1, 1, 1],
                             weights=[1, math.sqrt(0.5), 1])
        self.assertAlmostEqual(topo.geometry.segment_length(quarter), math.pi / 2, delta=1e-14)


if __name__ == "__main__":
    unittest.main()
