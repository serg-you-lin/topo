"""
tests/engine/primitives/test_conics.py
--------------------------------------
Parabola e iperbole (MAP.md D288): la discretizzazione sta entro la
tolleranza per dimostrazione, la spline razionale quadratica è la stessa
curva, e il motore le legge come le altre primitive. Microcasi con la
risposta in forma chiusa.
"""

import math
import unittest

import topo
from topo.core.primitives.segments import LineSeg
from topo.core.primitives.conics import HyperbolaSeg, ParabolaSeg
from topo.precision import FLOAT_NOISE

PARABOLA = ParabolaSeg(vertex=(0.0, 0.0), focus=(0.0, 1.0), start_param=-4.0, end_param=4.0)   # y = x²/4
HYPERBOLA = HyperbolaSeg(center=(30.0, 0.0), major_axis=(3.0, 0.0), ratio=1.0, start_param=-1.2, end_param=1.2)


def _on_equation(seg, p) -> float:
    a, b, c, d, e, f = seg.equation
    x, y = p
    return a * x * x + b * x * y + c * y * y + d * x + e * y + f


def _chord_gap(seg, pts) -> float:
    """Lo scarto più grande fra la curva vera e il poligono: fra due vertici
    consecutivi, la curva campionata fitta sul suo parametro."""
    worst = 0.0
    t0, t1 = seg.t_range
    n = 4000
    ts = [t0 + (t1 - t0) * k / n for k in range(n + 1)]
    for t in ts:
        q = seg.point_at(t)
        worst = max(worst, min(abs((b[0] - a[0]) * (a[1] - q[1]) - (a[0] - q[0]) * (b[1] - a[1])) / math.dist(a, b)
                               for a, b in zip(pts, pts[1:])
                               if min(math.dist(q, a), math.dist(q, b)) <= math.dist(a, b)))
    return worst


class TestDiscretize(unittest.TestCase):

    def test_ogni_corda_entro_la_tolleranza(self):
        for seg in (PARABOLA, HYPERBOLA, PARABOLA.rotated(0.7).translated(1e4, -3e3), HYPERBOLA.reversed()):
            for tol in (0.01, 0.001):
                pts = seg.discretize(tolerance=tol)
                self.assertLessEqual(_chord_gap(seg, pts), tol * (1 + 1e-6), (seg, tol))

    def test_i_vertici_stanno_sulla_curva_e_ai_capi(self):
        for seg in (PARABOLA, HYPERBOLA):
            pts = seg.discretize(tolerance=0.001)
            self.assertEqual((pts[0], pts[-1]), seg.endpoints())
            self.assertLess(max(abs(_on_equation(seg, p)) for p in pts), 1e-12)

    def test_un_pezzo_ha_i_vertici_della_curva_intera(self):
        # griglia ancorata al parametro 0: i vertici interni di un pezzo sono vertici dell'intera
        whole = PARABOLA.discretize(tolerance=0.001)
        piece = ParabolaSeg(PARABOLA.vertex, PARABOLA.focus, -1.3, 2.7).discretize(tolerance=0.001)
        self.assertTrue(set(piece[1:-1]) <= set(whole))


class TestToBspline(unittest.TestCase):

    def test_la_spline_e_la_stessa_curva(self):
        for seg in (PARABOLA, HYPERBOLA, HYPERBOLA.rotated(1.1).scaled(3.0)):
            spline = seg.to_bspline()
            self.assertEqual(spline.degree, 2)
            for u in range(201):
                self.assertLess(abs(_on_equation(seg, spline._evaluate(u / 200))), 1e-12, (seg, u))
            for p, q in zip(spline.endpoints(), seg.endpoints()):
                self.assertLess(math.dist(p, q), 1e-12)


class TestInTheEngine(unittest.TestCase):

    def test_area_chiusa_da_una_corda(self):
        # parabola y = x²/4 fra x = −4 e 4 e la corda y = 4: 2·(16 − 64/12) = 64/3
        # iperbole x² − y² = 9 fino a x = 3·cosh(1.2): a·b·(sinh T·cosh T − T)
        cases = [(PARABOLA, 64 / 3), (HYPERBOLA, 9 * (math.sinh(1.2) * math.cosh(1.2) - 1.2))]
        for seg, area in cases:
            # lontano dall'origine Green moltiplica coordinate di 1e5: restano ~1e-8 mm²
            for moved, delta in ((seg, 1e-9 * area), (seg.rotated(0.7).translated(1e5, -3e4), FLOAT_NOISE)):
                ring = [moved, LineSeg(*reversed(moved.endpoints()))]
                (cluster,) = topo.heal(topo.load_segments(ring)).faces().clusters
                self.assertAlmostEqual(cluster.area, area, delta=delta, msg=type(seg).__name__)

    def test_retta_incrocia_esatta(self):
        line = LineSeg((-10.0, 1.0), (40.0, 1.0))
        got = sorted(topo.geometry.intersections(PARABOLA, line))
        self.assertEqual(got, [(-2.0, 1.0), (2.0, 1.0)])
        (p,) = topo.geometry.intersections(HYPERBOLA, line)
        self.assertAlmostEqual(p[0], 30 + 3 * math.sqrt(1 + 1 / 9), delta=1e-12)

    def test_retta_tangente_al_vertice_un_punto(self):
        self.assertEqual(topo.geometry.intersections(PARABOLA, LineSeg((-3.0, 0.0), (3.0, 0.0))), [(0.0, 0.0)])

    def test_tratto_fra_due_punti_esatto(self):
        for seg in (PARABOLA, HYPERBOLA.reversed()):
            t1 = seg.t_range[1]
            a, b = seg.point_at(0.3 * t1), seg.point_at(0.8 * t1)
            piece = topo.primitives.sub_segment(seg, a, b, seg.point_at(0.5 * t1))
            self.assertIs(type(piece), type(seg))
            for p, q in zip(piece.endpoints(), (a, b)):
                self.assertLess(math.dist(p, q), 1e-12)


if __name__ == "__main__":
    unittest.main()
