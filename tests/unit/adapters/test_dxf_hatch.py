"""
tests/unit/adapters/test_dxf_hatch.py
-------------------------------------
Un HATCH del DXF arriva come righe del suo pattern, edge normali.

Il fixture usa ezdxf perché topo non sa scrivere un HATCH: è il formato di
ingresso stesso che si prova qui.
"""

import math
import os
import tempfile
import unittest

import ezdxf

import topo_dxf


def _square_with_hatch(path: str) -> None:
    # quadrato 10x10 di LINE + ANSI31 (righe a 45°) sullo stesso bordo
    doc = ezdxf.new()
    msp = doc.modelspace()
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        msp.add_line(a, b)
    hatch = msp.add_hatch()
    hatch.set_pattern_fill("ANSI31", scale=0.5)
    hatch.paths.add_polyline_path(pts, is_closed=True)
    doc.saveas(path)


class TestHatchExploded(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(cls.tmp.name, "hatch.dxf")
        _square_with_hatch(path)
        cls.doc = topo_dxf.load_dxf(path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pattern_lines_become_edges(self):
        # i 4 lati più le righe del tratteggio
        self.assertGreater(len(self.doc.edges), 4)

    def test_pattern_lines_are_at_45_degrees(self):
        diagonals = 0
        for e in self.doc.edges:
            (x0, y0), (x1, y1) = e.start, e.end
            if abs(x1 - x0) > 1e-9 and abs(y1 - y0) > 1e-9:
                angle = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180
                self.assertAlmostEqual(angle, 45.0, places=6)
                diagonals += 1
        self.assertGreater(diagonals, 0)

    def test_same_file_same_lines(self):
        # ezdxf sposta a caso l'origine del pattern se non glielo si vieta:
        # due caricamenti dello stesso file devono dare le stesse righe
        again = topo_dxf.load_dxf(os.path.join(self.tmp.name, "hatch.dxf"))
        self.assertEqual([e.segment for e in again.edges],
                         [e.segment for e in self.doc.edges])

    def test_no_hatch_left_unread(self):
        lost = [w for w in self.doc.warnings if w.startswith("tipi non riportati")]
        self.assertFalse(any("HATCH" in w for w in lost))


if __name__ == "__main__":
    unittest.main()
