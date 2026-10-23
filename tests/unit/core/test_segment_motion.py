"""
tests/unit/core/test_segment_motion.py
----------------------------------------
`.translated(dx, dy)` e `.mirrored()` su ogni primitiva nativa: la curva
trasformata è la curva di prima trasformata. Si controlla sui punti di
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


if __name__ == "__main__":
    unittest.main()
