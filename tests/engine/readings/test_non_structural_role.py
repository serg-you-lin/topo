"""
tests/engine/readings/test_non_structural_role.py
---------------------------------------------
La promessa su cui un consumer toglie ciò che non è contorno (D210): gli edge
con un ruolo non strutturale non cambiano il pezzo. `faces()` e `outlines()`
danno gli stessi segmenti e la stessa area del disegno senza di loro, e quegli
edge stanno tutti in `loose`.

Il caso: un contorno con angoli rientranti e un restringimento di 0,3 mm,
attraversato da righe parallele tagliate sul bordo (`cut_by`). Le righe toccano
i lati e tagliano la punta degli angoli: la forma che spezzava un lato in
tanti pezzi (G16).
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
    # righe a 45° ogni STEP, tenute solo dentro il pezzo
    pieces = []
    for k in range(-200, 200):
        line = LineSeg(start=(k * STEP - 20, -20), end=(k * STEP + 300, 300))
        pieces += topo.geometry.cut_by(line, part, keep="inside")
    return pieces


def _ring_key(contour) -> list:
    # i segmenti di un anello come capi ordinati: due anelli uguali, stesso elenco
    return sorted(
        tuple(round(v, 9) for v in (*s.start, *s.end))
        for s in contour.segments
    )


class TestNonStructuralRoleLeavesThePart(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.part = topo.geometry.polygon(CONTOUR)
        cls.lines = _lines_across(cls.part)

    def test_il_pezzo_resta_quello_senza_le_righe(self):
        for tolerance in TOLERANCES:
            alone = topo.heal(topo.load_segments(self.part),
                              tolerance=tolerance)
            doc = topo.load_segments(self.part)
            doc.edges += topo.load_segments(self.lines, role="x").edges
            network = topo.heal(doc, tolerance=tolerance)
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


if __name__ == "__main__":
    unittest.main()
