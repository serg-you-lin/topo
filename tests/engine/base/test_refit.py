# tests/engine/base/test_refit.py

import math
import unittest
import topo
from topo.core.primitives.line import LineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo.precision import FLOAT_NOISE, SAME_POINT


class TestRefitJointsUnderMotion(unittest.TestCase):
    """G6e, gruppo B: una curva scritta a punti (retta, quarto di cerchio,
    retta) rifittata in tre primitive resta una catena sola. Ogni giunzione
    si arrotondava due volte, dalla fine di un pezzo e dall'inizio del
    successivo: due copie a 1 ulp, e con un bordo di cella fra loro i due
    pezzi prendevano nodi diversi."""

    def _profile(self, angle, dx, dy):
        import topo
        from tests.invariants import rigid
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + 3 * math.sin(a / 100 * math.pi / 2), 3 - 3 * math.cos(a / 100 * math.pi / 2))
                for a in range(1, 101)]
        pts += [(5.0, 3.0 + y * 0.05) for y in range(1, 41)]
        segment, _ = rigid(angle, dx, dy)
        return topo.load_segments([segment(LineSeg(start=a, end=b)) for a, b in zip(pts, pts[1:])]).edges

    def test_una_giunzione_su_un_bordo_di_cella_resta_un_nodo(self):
        from collections import Counter
        from topo.core.base.refit import refit_tessellations
        # il moto mette la giunzione fra la retta e l'arco a metà fra due celle di 1e-3
        for motion in [(0.0, 0.0, 0.0), (1.209, 2999999.9996208353, -2499999.9996809117)]:
            with self.subTest(motion=motion):
                out = refit_tessellations(self._profile(*motion))
                ends = Counter(n for e in out for n in (e.start, e.end))
                self.assertEqual(len(out), 3)
                self.assertEqual(sorted(ends.values()), [1, 1, 2, 2])


class TestRefitCornerFromTolerance(unittest.TestCase):
    """D283: nel rifit lo spigolo è dove nessuna curva liscia passa entro la
    tolleranza, non una svolta sopra 35° (un numero di smoother). Microcasi."""

    def test_spigolo_di_20_gradi_scritto_a_punti_resta_due_rette(self):
        t = math.radians(20)
        pts = [(x * 0.05, 0.0) for x in range(41)]
        pts += [(2.0 + k * 0.05 * math.cos(t), k * 0.05 * math.sin(t)) for k in range(1, 41)]
        self.assertEqual(self._refit(pts), ["LineSeg", "LineSeg"])

    def test_curva_liscia_che_non_e_un_arco_resta_una_curva(self):
        # una gobba di 0,04 mm su 3 mm, la curvatura cambia (regr_01 a y 686): nessuno spigolo
        pts = [(x * 0.02, 0.04 * math.sin(math.pi * x / 150) - 0.3 * (x / 150) ** 3) for x in range(151)]
        (kind,) = self._refit(pts)     # un pezzo solo; arco o spline, entro 0,02 vanno bene tutti e due
        self.assertNotEqual(kind, "LineSeg")

    def test_retta_e_raccordo_tangente_senza_spigoli_finti(self):
        # 2 mm di retta, poi un quarto di cerchio di raggio 1 tangente: retta + arco, nessun pezzo in più
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
    """Il rifit prova l'ellisse prima della spline: la famiglia più semplice
    entro la tolleranza (5 numeri contro i punti di controllo). Microcasi."""

    @staticmethod
    def _ellipse(t, angle=math.radians(30), a=4.0, b=1.6, center=(1000.0, 500.0)):
        c, s = math.cos(angle), math.sin(angle)
        return (center[0] + a * math.cos(t) * c - b * math.sin(t) * s,
                center[1] + a * math.cos(t) * s + b * math.sin(t) * c)

    def test_ellisse_intera_scritta_a_punti_diventa_una_ellisse(self):
        pts = [self._ellipse(2 * math.pi * k / 300) for k in range(301)]   # lati sotto 0,1 mm
        (seg,) = _refit_segments(pts)
        self.assertIsInstance(seg, EllipseSeg)
        self.assertAlmostEqual(math.hypot(*seg.major_axis), 4.0, delta=SAME_POINT)
        self.assertAlmostEqual(seg.ratio, 0.4, delta=SAME_POINT)

    def test_arco_d_ellisse_tiene_i_capi_nei_due_versi(self):
        for sweep in (2.0, -2.0):
            pts = [self._ellipse(0.3 + sweep * k / 100) for k in range(101)]
            (seg,) = _refit_segments(pts)
            self.assertIsInstance(seg, EllipseSeg)
            start, end = segment_endpoints(seg)
            self.assertLessEqual(math.dist(start, pts[0]), FLOAT_NOISE, sweep)
            self.assertLessEqual(math.dist(end, pts[-1]), FLOAT_NOISE, sweep)
            self.assertAlmostEqual(seg._sweep(), 2.0, delta=SAME_POINT, msg=sweep)

    def test_ramo_d_iperbole_scritto_a_punti_diventa_un_iperbole(self):
        # D294: la conica che il fit trova dice quale; lati sotto 0,1 mm come un rifit vero
        from topo.primitives import HyperbolaSeg
        hyp = HyperbolaSeg(center=(1000.0, 500.0), major_axis=(3.0, 1.0), ratio=0.6, start_param=-0.9, end_param=1.1)
        pts = [hyp.point_at(hyp.t_range[1] * k / 120) for k in range(121)]
        (seg,) = _refit_segments(pts)
        self.assertIsInstance(seg, HyperbolaSeg)
        start, end = segment_endpoints(seg)
        self.assertLessEqual(math.dist(start, pts[0]), FLOAT_NOISE)
        self.assertLessEqual(math.dist(end, pts[-1]), FLOAT_NOISE)

    def test_curva_che_non_e_una_conica_non_diventa_ellisse(self):
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
    """D236: un anello che sta tutto entro 0,02 mm da un cerchio e gli fa il giro è quel cerchio."""

    def test_foro_a_lati_lunghi_diventa_cerchio(self):
        # forza bruta (seme 42): r 1,424 in 71 lati da 0,14 mm, oltre il lato corto di D60
        (c,) = _circles(_polygon((5, 5), 1.424, 64))
        self.assertAlmostEqual(c.radius, 1.424, delta=0.002)

    def test_foro_con_un_buco_e_un_pezzo_che_sporge(self):
        ring = _polygon((5, 5), 1.0, 60)
        a = ring[7]
        ring[7] = LineSeg(start=a.start, end=(a.start[0] + 0.9 * (a.end[0] - a.start[0]), a.start[1] + 0.9 * (a.end[1] - a.start[1])))
        ring.append(LineSeg(start=ring[20].start, end=(ring[20].start[0] + 0.05, ring[20].start[1])))
        self.assertEqual(len(_circles(ring)), 1)

    def test_pezzo_doppio_che_corre_sul_cerchio_va_col_cerchio(self):
        # seme 42: un tratto doppio lungo il giro, lasciato da parte, spezzava il cerchio in arco + linea
        ring = _polygon((5, 5), 1.0, 60)
        a, b = ring[10].start, ring[10].end
        for extra in (LineSeg(start=a, end=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)),          # dal vertice, capo libero
                      LineSeg(start=((2 * a[0] + b[0]) / 3, (2 * a[1] + b[1]) / 3), end=b)):  # parte a metà lato
            faces = topo.heal(topo.load_segments(ring + [extra]), max_gap=0.1).faces()
            self.assertEqual([[type(s) for s in ct.segments] for cl in faces.clusters for ct in [cl.outer, *cl.inners]],
                             [[CircleSeg]])

    def test_poligono_vero_resta(self):
        # esagono di r 5: a metà lato si stacca di 0,67 mm dal cerchio
        self.assertEqual(_circles(_polygon((0, 0), 5.0, 6)), [])

    def test_mezzo_giro_non_diventa_cerchio(self):
        half = _polygon((0, 0), 1.0, 60)[:30]
        net = topo.heal(topo.load_segments(half + [LineSeg(start=half[-1].end, end=half[0].start)]), max_gap=0.1)
        self.assertEqual([s for cl in net.faces().clusters for s in cl.outer.segments if (isinstance(s, CircleSeg) and s.full)], [])
