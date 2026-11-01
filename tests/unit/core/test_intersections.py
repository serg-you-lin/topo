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

