"""
tests/adapters/dxf/test_text_align.py
-------------------------------------
Text anchor and alignment: a text written by topo and re-read comes back at the
same point with the same alignment, for every halign × valign pair; a
multi-line string comes back on several lines; edge spaces stay, because the
anchor counts them. The source's entity type is not in the model.
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
        texts.append(topo.Text(position=(60.0, 80.0), text="SECTION  ", halign="right"))
        texts.append(topo.Text(position=(60.0, 85.0), text="  Materiale"))
        doc = _square_doc(texts)
        path = os.path.join(cls.tmp.name, "align.dxf")
        topo_dxf.to_dxf(topo.heal(doc).faces()).saveas(path)
        cls.sent = texts
        cls.back = {t.text: t for t in topo_dxf.load_dxf(path).texts}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_alignment_comes_back_equal(self):
        for t in self.sent[:-3]:
            with self.subTest(halign=t.halign, valign=t.valign):
                r = self.back[t.text]
                self.assertEqual((r.halign, r.valign), (t.halign, t.valign))
                self.assertAlmostEqual(r.position[0], t.position[0], places=6)
                self.assertAlmostEqual(r.position[1], t.position[1], places=6)

    def test_more_lines_come_back_more_lines(self):
        r = self.back["riga 1\nriga 2"]
        self.assertEqual((r.halign, r.valign), ("center", "top"))
        self.assertEqual(r.position, (50.0, 20.0))

    def test_edge_spaces_remain(self):
        self.assertEqual(self.back["SECTION  "].position, (60.0, 80.0))
        self.assertIn("  Materiale", self.back)

    def test_unknown_alignment_refused(self):
        with self.assertRaises(ValueError):
            topo.Text(position=(0, 0), text="x", halign="middle")
        with self.assertRaises(ValueError):
            topo.Text(position=(0, 0), text="x", valign="centre")


if __name__ == "__main__":
    unittest.main()
