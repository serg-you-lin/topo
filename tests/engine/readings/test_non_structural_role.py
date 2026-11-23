"""
tests/engine/readings/test_non_structural_role.py
---------------------------------------------
The promise on which a consumer removes what is not contour: edges with a
non-structural role do not change the part. `faces()` and `outlines()` give the
same segments and the same area as the drawing without them, and those edges
are all in `loose`.

The case: a contour with re-entrant corners and a 0.3 mm narrowing, crossed by
parallel lines cut on the border (`cut_by`). The lines touch the sides and cut
the tip of the corners: the shape that broke a side into many pieces.
"""

import unittest

import topo
from topo.primitives import LineSeg

CONTOUR = [
    (40, 20), (90, 20), (140, 60), (250, 60), (250, 100), (170, 100),
    (170, 140), (210, 140), (210, 100.3), (264, 100.3), (264, 180),
    (40, 180),
]
STEP = 1.0
TOLERANCES = (0.05, 0.5)


def _lines_across(part: list) -> list:
    # lines at 45° every STEP, kept only inside the piece
    pieces = []
    for k in range(-200, 200):
        line = LineSeg(start=(k * STEP - 20, -20), end=(k * STEP + 300, 300))
        pieces += topo.geometry.cut_by(line, part, keep="inside")
    return pieces


def _ring_key(contour) -> list:
    # the segments of a ring as ordered ends: two equal rings, same list
    return sorted(
        tuple(round(v, 9) for v in (*s.start, *s.end))
        for s in contour.segments
    )


class TestNonStructuralRoleLeavesThePart(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.part = topo.geometry.polygon(CONTOUR)
        cls.lines = _lines_across(cls.part)

    def test_the_piece_stays_the_one_without_the_lines(self):
        for tolerance in TOLERANCES:
            alone = topo.heal(topo.load_segments(self.part))
            doc = topo.load_segments(self.part)
            doc.edges += topo.load_segments(self.lines, role="x").edges
            network = topo.heal(doc)
            for reading in ("faces", "outlines"):
                with self.subTest(tolerance=tolerance, reading=reading):
                    expected = getattr(alone, reading)().clusters[0].outer
                    result = getattr(network, reading)()
                    self.assertTrue(result.is_valid, result.errors)
                    self.assertEqual(len(result.clusters), 1)
                    outer = result.clusters[0].outer
                    self.assertEqual(_ring_key(outer), _ring_key(expected))
                    self.assertAlmostEqual(outer.area, expected.area,
                                           places=9)
                    self.assertEqual(result.clusters[0].inners, [])
                    self.assertEqual(len(result.loose), len(self.lines))


class TestOnlyNonStructuralEdges(unittest.TestCase):
    # no structural edge: no part, but the edges set aside do not vanish — they are
    # in `loose` in both readings, equal

    def test_the_edges_set_aside_stay_in_loose(self):
        shapes = {
            "ring": topo.geometry.rectangle(200, 100),
            "rows": [LineSeg(start=(0, 0), end=(50, 0)),
                      LineSeg(start=(0, 10), end=(50, 30))],
        }
        for name, segments in shapes.items():
            network = topo.heal(topo.load_segments(segments, role="x"))
            lengths = {}
            for reading in ("faces", "outlines"):
                with self.subTest(shape=name, reading=reading):
                    result = getattr(network, reading)()
                    self.assertFalse(result.is_valid)
                    self.assertEqual(result.clusters, [])
                    self.assertTrue(result.loose)
                    lengths[reading] = sorted(
                        round(sum(map(topo.geometry.segment_length, c.segments)), 9)
                        for c in result.loose)
            with self.subTest(shape=name):
                self.assertEqual(lengths["faces"], lengths["outlines"])


if __name__ == "__main__":
    unittest.main()
