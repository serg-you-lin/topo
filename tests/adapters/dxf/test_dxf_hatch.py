"""
tests/adapters/dxf/test_dxf_hatch.py
-------------------------------------
A DXF HATCH arrives as the lines of its pattern, normal edges.

The fixture uses ezdxf because topo cannot write a HATCH: it is the input
format itself that is tested here.
"""

import math
import os
import tempfile
import unittest

import ezdxf

import topo_dxf


def _square_with_hatch(path: str) -> None:
    # 10x10 square of LINEs + ANSI31 (lines at 45°) on the same border
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
        # the 4 sides plus the hatching lines
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
        # ezdxf moves the pattern origin at random unless forbidden: two loads of the
        # same file must give the same lines
        again = topo_dxf.load_dxf(os.path.join(self.tmp.name, "hatch.dxf"))
        self.assertEqual([e.segment for e in again.edges],
                         [e.segment for e in self.doc.edges])

    def test_no_hatch_left_unread(self):
        lost = [w for w in self.doc.warnings if w.startswith("types not reported")]
        self.assertFalse(any("HATCH" in w for w in lost))


# the 3x18 rectangle of HATCH "B" of anch_01, cut out of the file: the CAD saves
# it in three open paths, an L (left + top) and two loose sides
_ANCH_01 = os.path.join(os.path.dirname(__file__), "..", "..", "data", "golden_anchoring", "anch_01.dxf")


def _hatch_rect(path: str, in_pieces: bool) -> None:
    doc = ezdxf.readfile(_ANCH_01)
    msp = doc.modelspace()
    hatch = next(h for h in msp.query("HATCH") if h.dxf.pattern_name == "B")
    for e in list(msp):
        if e is not hatch:
            msp.delete_entity(e)
    first = hatch.paths.paths[:3]  # the three pieces of the first rectangle
    if in_pieces:
        hatch.paths.paths = first
    else:
        # the same sides, saved as a single closed ring
        xs = [v for p in first for e in p.edges for v in (e.start.x, e.end.x)]
        ys = [v for p in first for e in p.edges for v in (e.start.y, e.end.y)]
        hatch.paths.clear()
        hatch.paths.add_polyline_path([(min(xs), min(ys)), (max(xs), min(ys)),
                                       (max(xs), max(ys)), (min(xs), max(ys))], is_closed=True)
    doc.saveas(path)


class TestHatchBoundaryInPieces(unittest.TestCase):
    # a border in pieces is put back into rings with the file's sides only

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        pieces = os.path.join(cls.tmp.name, "pieces.dxf")
        whole = os.path.join(cls.tmp.name, "whole.dxf")
        _hatch_rect(pieces, in_pieces=True)
        _hatch_rect(whole, in_pieces=False)
        cls.pieces = topo_dxf.load_dxf(pieces)
        cls.whole = topo_dxf.load_dxf(whole)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _lines(self, doc):
        return sorted(tuple(sorted((tuple(round(v, 6) for v in e.start),
                                    tuple(round(v, 6) for v in e.end))))
                      for e in doc.edges)

    def test_same_lines_as_one_closed_boundary(self):
        # today ezdxf closes every piece with its chord: lines in half a rectangle
        self.assertTrue(self.whole.edges)
        self.assertEqual(self._lines(self.pieces), self._lines(self.whole))

    def test_no_open_boundary_warning(self):
        self.assertFalse(any(w.code == "dxf-hatch-open-boundary" for w in self.pieces.warnings))

    def test_boundary_that_never_closes_is_warned(self):
        # only the file's L: no side closes it, ezdxf's chord stays and it is said
        path = os.path.join(self.tmp.name, "only_l.dxf")
        _hatch_rect(path, in_pieces=True)
        doc = ezdxf.readfile(path)
        hatch = doc.modelspace().query("HATCH")[0]
        hatch.paths.paths = hatch.paths.paths[:1]
        doc.saveas(path)
        read = topo_dxf.load_dxf(path)
        self.assertTrue(read.edges)
        [warning] = [w for w in read.warnings if w.code == "dxf-hatch-open-boundary"]
        self.assertEqual(warning.message,
                         "HATCH whose boundary does not close, each piece closed on its own chord: 1")
        self.assertEqual(warning.notes, ("pattern B",))


if __name__ == "__main__":
    unittest.main()
