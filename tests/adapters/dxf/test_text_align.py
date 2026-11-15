"""
tests/adapters/dxf/test_text_align.py
-------------------------------------
Ancora e allineamento dei testi (MAP.md D256): un testo scritto da topo e
riletto torna nello stesso punto con lo stesso allineamento, per ogni coppia
halign × valign; una stringa su più righe torna su più righe. Il tipo
d'entità della sorgente non è nel modello.
"""

import os
import tempfile
import unittest
from itertools import product

import topo
import topo_dxf
from topo.model import Edge
from topo.model.text import HALIGNS, VALIGNS
from topo.primitives import LineSeg


def _square_doc(texts) -> topo.Document:
    pts = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]
    edges = [Edge.of(LineSeg(pts[i], pts[(i + 1) % 4]), "unknown") for i in range(4)]
    return topo.Document(edges=edges, texts=texts)


class TestTextAlignRoundTrip(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        texts = [topo.Text(position=(10.0 + 7 * i, 50.0), text=f"T{i}", height=2.5,
                           halign=h, valign=v)
                 for i, (h, v) in enumerate(product(HALIGNS, VALIGNS))]
        texts.append(topo.Text(position=(50.0, 20.0), text="riga 1\nriga 2",
                               halign="center", valign="top"))
        doc = _square_doc(texts)
        path = os.path.join(cls.tmp.name, "align.dxf")
        topo_dxf.to_dxf(topo.heal(doc).faces(), doc).saveas(path)
        cls.sent = texts
        cls.back = {t.text: t for t in topo_dxf.load_dxf(path).texts}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_ogni_allineamento_torna_uguale(self):
        for t in self.sent[:-1]:
            with self.subTest(halign=t.halign, valign=t.valign):
                r = self.back[t.text]
                self.assertEqual((r.halign, r.valign), (t.halign, t.valign))
                self.assertAlmostEqual(r.position[0], t.position[0], places=6)
                self.assertAlmostEqual(r.position[1], t.position[1], places=6)

    def test_piu_righe_tornano_piu_righe(self):
        r = self.back["riga 1\nriga 2"]
        self.assertEqual((r.halign, r.valign), ("center", "top"))
        self.assertEqual(r.position, (50.0, 20.0))

    def test_allineamento_sconosciuto_rifiutato(self):
        with self.assertRaises(ValueError):
            topo.Text(position=(0, 0), text="x", halign="middle")
        with self.assertRaises(ValueError):
            topo.Text(position=(0, 0), text="x", valign="centre")


if __name__ == "__main__":
    unittest.main()
