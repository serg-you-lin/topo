"""
tests/unit/core/test_intersections.py
---------------------------------------
G6e, gruppo A: `intersections(a, b)` dà gli stessi incontri prima e dopo un
moto rigido. Lontano dall'origine il rumore dei double è ~1e-10 mm: una
soglia assoluta più piccola (1e-10, 1e-12 in mm² o in mm⁴) lo lascia
decidere — parallele che "si incontrano", un tocco perso o sdoppiato.
Ogni caso è un `subTest` per moto (MAP.md D158).
"""

import math
import unittest

import topo
intersections = topo.geometry.intersections
from topo.core.primitives.segments import LineSeg, ArcSeg, CircleSeg, _rotate_point

# moti rigidi (angolo, dx, dy): nullo, solo rotazione, lontano, lontano e ruotato
MOTIONS = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.0, 3e6, -2.5e6), (0.031, 3e6, -2.5e6),
           (0.062, 3e6, -2.5e6), (0.093, 3e6, -2.5e6), (0.7, 3e6, -2.5e6),
           (2.294, 3e6, -2.5e6), (math.pi / 2, -7e5, 4e5), (0.13, 1e6, 1e6)]


def _moved(seg, angle, dx, dy):
    return seg.rotated(angle).translated(dx, dy)


def _moved_point(p, angle, dx, dy):
    q = _rotate_point(p, angle, (0.0, 0.0))
    return (q[0] + dx, q[1] + dy)


class TestIntersectionsUnderMotion(unittest.TestCase):
    """Gli incontri del pezzo mosso sono gli incontri mossi."""

    def _assert_same_meetings(self, a, b, expected):
        for motion in MOTIONS:
            with self.subTest(motion=motion):
                got = intersections(_moved(a, *motion), _moved(b, *motion))
                want = [_moved_point(p, *motion) for p in expected]
                self.assertEqual(len(got), len(want), got)
                for p in want:
                    self.assertLess(min(math.dist(p, q) for q in got), 1e-6)

    def test_001_collinear_overlap_has_no_point(self):
        # un tratto dentro l'altro, sulla stessa retta: l'incontro è un tratto, nessun
        # punto. Lontano, il `denom` delle due direzioni è solo rumore (~1e-8 mm²)
        # e l'"incontro" cadeva dove capitava, spesso dentro tutti e due
        self._assert_same_meetings(LineSeg(start=(0.0, 0.0), end=(100.0, 0.0)),
                                   LineSeg(start=(30.0, 0.0), end=(70.0, 0.0)), [])

    def test_002_end_on_the_middle_of_a_line_is_one_point(self):
        # un tratto corto che parte dal mezzo di un altro (un T): il suo capo è
        # l'incontro. Lontano il rumore di `t` su 0.04 mm supera 1e-9 e il T si perdeva
        self._assert_same_meetings(LineSeg(start=(0.0, 0.0), end=(0.05, 0.0)),
                                   LineSeg(start=(0.02, 0.0), end=(0.02, 0.04)), [(0.02, 0.0)])

    def test_003_arc_end_on_a_line_end_is_one_point(self):
        # un arco piccolo che finisce dove comincia una retta, che non gli è tangente
        self._assert_same_meetings(ArcSeg(center=(0.0, 0.0), radius=0.05, start_angle=0.0,
                                          end_angle=math.pi / 2),
                                   LineSeg(start=(0.0, 0.05), end=(-0.05, 0.08)), [(0.0, 0.05)])

    def test_004_line_tangent_to_a_circle_is_one_point(self):
        # la tangenza decisa sul discriminante (mm⁴, soglia 1e-10): lontano il
        # rumore lo fa negativo (nessun punto) o positivo (due punti a ~1e-4 mm)
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   LineSeg(start=(-8.0, 5.0), end=(8.0, 5.0)), [(0.0, 5.0)])

    def test_005_circles_tangent_outside_are_one_point(self):
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(8.0, 0.0), radius=3.0), [(5.0, 0.0)])

    def test_006_circles_tangent_inside_are_one_point(self):
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(2.0, 0.0), radius=3.0), [(5.0, 0.0)])

    def test_007_crossings_stay_two(self):
        # a scanso di equivoci: un incrocio vero resta di due punti
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   LineSeg(start=(-8.0, 3.0), end=(8.0, 3.0)), [(-4.0, 3.0), (4.0, 3.0)])
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(6.0, 0.0), radius=5.0), [(3.0, 4.0), (3.0, -4.0)])
