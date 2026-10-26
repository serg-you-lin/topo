"""
tests/unit/core/test_segment_motion.py
----------------------------------------
`.translated(dx, dy)`, `.mirrored(origin, angle)` e `.scaled(factor, origin)`
su ogni primitiva nativa: la curva trasformata è la curva di prima
trasformata. Si controlla sui punti di
`discretize()` — gli stessi che legge ogni lettura — su una griglia di casi:
coordinate negative, vicine a zero, lontane dall'origine, archi nei due versi
e a cavallo dell'angolo 0. Ogni caso è un `subTest` (MAP.md D158).
"""

import math
import unittest

from topo.core.primitives.segments import (
    LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg, segment_endpoints,
)

# spostamenti: nullo, quasi nullo, negativo, lontano dall'origine nei due sensi
OFFSETS = [(0.0, 0.0), (1e-9, -1e-9), (-37.25, 12.5), (1e5, -1e5), (-3e6, 2.5e6)]
# precisione relativa alla grandezza delle coordinate: un double ha ~16 cifre
RELATIVE = 1e-12


def _segments() -> list:
    """(nome, segmento): ogni primitiva, in posizioni e versi diversi."""
    return [
        ("line", LineSeg(start=(-3.0, 4.0), end=(7.5, -2.25))),
        ("line near zero", LineSeg(start=(1e-12, -1e-12), end=(0.5, 0.0))),
        ("arc ccw", ArcSeg(center=(10.0, -5.0), radius=3.0, start_angle=0.3, end_angle=2.1)),
        ("arc cw", ArcSeg(center=(-2.0, 1.0), radius=0.75, start_angle=2.1, end_angle=0.3, ccw=False)),
        ("arc over 0", ArcSeg(center=(0.0, 0.0), radius=50.0, start_angle=-0.4, end_angle=0.4)),
        ("arc negative angles", ArcSeg(center=(1.0, 1.0), radius=2.0, start_angle=-2.5, end_angle=-1.0)),
        ("circle", CircleSeg(center=(-4.0, -6.0), radius=12.5)),
        ("circle small", CircleSeg(center=(0.0, 0.0), radius=0.02)),
        ("spline", BSplineSeg(degree=3, control_points=[(0, 0), (2, 5), (6, -3), (9, 1)],
                              knots=[0, 0, 0, 0, 1, 1, 1, 1])),
        ("nurbs", BSplineSeg(degree=2, control_points=[(1, 0), (1, 1), (0, 1)],
                             knots=[0, 0, 0, 1, 1, 1], weights=[1, math.sqrt(0.5), 1])),
        ("ellipse", EllipseSeg(center=(3.0, -2.0), major_axis=(8.0, 3.0), ratio=0.4,
                               start_param=0.0, end_param=2 * math.pi)),
        ("ellipse arc cw", EllipseSeg(center=(-1.0, 2.0), major_axis=(-2.0, 5.0), ratio=0.7,
                                      start_param=2.0, end_param=-0.5, ccw=False)),
    ]


def _close(a, b, scale: float) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= RELATIVE * max(1.0, scale)


# assi di specchio (punto, angolo in radianti): obliquo, lontano, l'asse y, la bisettrice
AXES = [((3.0, -2.0), 0.7), ((-1e4, 5e3), -1.2), ((0.0, 0.0), math.pi / 2), ((5.0, 5.0), math.pi / 4)]
# fattori di scala (attorno a un centro): piccolo, grande, vicino a 1
FACTORS = [(0.5, (0.0, 0.0)), (2.0, (3.0, -1.0)), (1e-3, (-50.0, 20.0)), (1e3, (1e4, -1e4)),
           (1.25, (7.0, 7.0))]
# passo fine della curva di riferimento: un punto della curva vi dista al più la sua freccia
FINE = 1e-4


def _mirror(p, origin, angle):
    """`p` specchiato sulla retta per `origin` ad `angle`, scritto qui a parte."""
    d = (math.cos(angle), math.sin(angle))
    v = (p[0] - origin[0], p[1] - origin[1])
    along = v[0] * d[0] + v[1] * d[1]
    return (origin[0] + 2 * along * d[0] - v[0], origin[1] + 2 * along * d[1] - v[1])


def _scale(p, factor, origin):
    return (origin[0] + (p[0] - origin[0]) * factor, origin[1] + (p[1] - origin[1]) * factor)


def _distance_to_polyline(p, points) -> float:
    best = math.inf
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


class _OnCurve:
    """Ogni vertice del segmento trasformato, riportato indietro, sta sulla
    curva di partenza; gli estremi sono gli estremi trasformati (verso incluso)."""

    def assert_on_curve(self, seg, moved, back, scale: float):
        reference = seg.discretize(FINE)
        for q in moved.discretize(0.01):
            d = _distance_to_polyline(back(q), reference)
            self.assertLessEqual(d, 2 * FINE + RELATIVE * max(1.0, scale), f"{q} fuori di {d}")

    def assert_ends(self, seg, moved, forward, scale: float):
        if isinstance(seg, CircleSeg):
            # un cerchio non ha un punto di partenza suo: il suo "estremo" è
            # sempre il punto all'angolo 0, non l'immagine di quello di prima
            return
        for p, q in zip(segment_endpoints(seg), segment_endpoints(moved)):
            self.assertTrue(_close(forward(p), q, scale), f"{forward(p)} ≠ {q}")


class TestTranslated(unittest.TestCase):

    def test_punti_spostati_della_stessa_quantita(self):
        for name, seg in _segments():
            for dx, dy in OFFSETS:
                with self.subTest(segment=name, offset=(dx, dy)):
                    before = seg.discretize(0.01)
                    after = seg.translated(dx, dy).discretize(0.01)
                    self.assertEqual(len(after), len(before))
                    scale = max(abs(dx), abs(dy), *(abs(c) for p in before for c in p))
                    for p, q in zip(before, after):
                        self.assertTrue(_close((p[0] + dx, p[1] + dy), q, scale), f"{p} → {q}")

    def test_andata_e_ritorno_torna_al_segmento(self):
        for name, seg in _segments():
            for dx, dy in OFFSETS:
                with self.subTest(segment=name, offset=(dx, dy)):
                    back = seg.translated(dx, dy).translated(-dx, -dy)
                    scale = max(abs(dx), abs(dy))
                    for p, q in zip(segment_endpoints(seg), segment_endpoints(back)):
                        self.assertTrue(_close(p, q, scale), f"{p} → {q}")


class TestMirrored(unittest.TestCase):

    def test_punti_specchiati_sull_asse_x(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                before = seg.discretize(0.01)
                if isinstance(seg, CircleSeg):
                    # un cerchio non ha verso: specchiato è percorso ancora
                    # CCW, gli stessi vertici in ordine inverso
                    before = before[::-1]
                after = seg.mirrored().discretize(0.01)
                self.assertEqual(len(after), len(before))
                for p, q in zip(before, after):
                    self.assertTrue(_close((p[0], -p[1]), q, 100.0), f"{p} → {q}")

    def test_estremi_specchiati_e_stesso_verso_di_percorrenza(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                (s, e), (ms, me) = segment_endpoints(seg), segment_endpoints(seg.mirrored())
                self.assertTrue(_close((s[0], -s[1]), ms, 100.0))
                self.assertTrue(_close((e[0], -e[1]), me, 100.0))

    def test_due_volte_torna_al_segmento(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                again = seg.mirrored().mirrored().discretize(0.01)
                for p, q in zip(seg.discretize(0.01), again):
                    self.assertTrue(_close(p, q, 100.0), f"{p} → {q}")



class TestMirroredOnAxis(unittest.TestCase, _OnCurve):

    def test_curva_specchiata_sull_asse(self):
        for name, seg in _segments():
            for origin, angle in AXES:
                with self.subTest(segment=name, axis=(origin, angle)):
                    moved = seg.mirrored(origin, angle)
                    self.assertIs(type(moved), type(seg))
                    scale = max(1e2, *map(abs, origin))
                    self.assert_on_curve(seg, moved, lambda q: _mirror(q, origin, angle), scale)
                    self.assert_ends(seg, moved, lambda p: _mirror(p, origin, angle), scale)

    def test_due_volte_torna_al_segmento(self):
        for name, seg in _segments():
            for origin, angle in AXES:
                with self.subTest(segment=name, axis=(origin, angle)):
                    again = seg.mirrored(origin, angle).mirrored(origin, angle)
                    scale = max(1e2, *map(abs, origin))
                    self.assert_ends(seg, again, lambda p: p, scale)
                    self.assert_on_curve(seg, again, lambda q: q, scale)

    def test_asse_x_di_default(self):
        # il default è lo specchio di sempre, campo per campo
        for name, seg in _segments():
            with self.subTest(segment=name):
                self.assertEqual(seg.mirrored(), seg.mirrored((0.0, 0.0), 0.0))


class TestScaled(unittest.TestCase, _OnCurve):

    def test_curva_scalata(self):
        for name, seg in _segments():
            for factor, origin in FACTORS:
                with self.subTest(segment=name, factor=factor, origin=origin):
                    moved = seg.scaled(factor, origin)
                    self.assertIs(type(moved), type(seg))
                    scale = max(1e2, *map(abs, origin)) * max(1.0, factor)
                    self.assert_on_curve(seg, moved, lambda q: _scale(q, 1 / factor, origin), scale)
                    self.assert_ends(seg, moved, lambda p: _scale(p, factor, origin), scale)

    def test_raggio_e_assi_moltiplicati(self):
        arc = ArcSeg(center=(1.0, 2.0), radius=3.0, start_angle=0.3, end_angle=2.1, ccw=False)
        big = arc.scaled(2.5, (1.0, 2.0))
        self.assertEqual((big.center, big.radius, big.start_angle, big.end_angle, big.ccw),
                         ((1.0, 2.0), 7.5, 0.3, 2.1, False))
        self.assertEqual(CircleSeg(center=(2.0, 0.0), radius=4.0).scaled(0.5),
                         CircleSeg(center=(1.0, 0.0), radius=2.0))
        ellipse = EllipseSeg(center=(0.0, 0.0), major_axis=(8.0, 3.0), ratio=0.4,
                             start_param=0.0, end_param=1.0).scaled(2.0)
        self.assertEqual((ellipse.major_axis, ellipse.ratio), ((16.0, 6.0), 0.4))

    def test_fattore_non_positivo_rifiutato(self):
        line = LineSeg(start=(0.0, 0.0), end=(1.0, 0.0))
        for factor in (0.0, -1.0, math.nan, math.inf):
            with self.subTest(factor=factor):
                with self.assertRaises(ValueError):
                    line.scaled(factor)


if __name__ == "__main__":
    unittest.main()
