# tests/engine/readings/test_non_contour_choices.py

"""The choices of heal()'s non-contour criterion, one class per choice. Every
test is the minimal drawing of the limit case and says what topo chooses by
default: if a default changes, it changes here, on purpose and by a written
decision, never to make another test pass.

  A  inner chain (0 passes)           → chord: the piece stays full
  B  bridge (2 passes)                → two pieces, with a warning
  C  on the border for less than half → chord
  D  sides that overlap               → judged on the planar network, and told in a warning
  E  chain closed on a single node    → never a candidate: today it stays a hole (open in TODO)
"""

import unittest

import topo
from topo.core.primitives import LineSeg
from topo.core.topology.noding import interior_crossings
from topo import to_shapely

TOL = 0.01


def _lines(*points, closed: bool = False) -> list:
    pts = list(points) + ([points[0]] if closed else [])
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]


def _heal(segments: list):
    return topo.heal(topo.load_segments(segments)).faces()


class TestA_InteriorChainIsChord(unittest.TestCase):
    """Rectangle, inner square, 4 corner-to-corner diagonals: the same graph as a
    panel with stiffening crosses and a hole held by 4 lines. Without other
    information the piece is full."""

    def test_full_panel_eight_lines_in_the_trash(self):
        result = _heal(_lines((0, 0), (260, 0), (260, 150), (0, 150), closed=True)
                       + _lines((95, 47), (165, 47), (165, 103), (95, 103), closed=True)
                       + _lines((0, 0), (95, 47)) + _lines((260, 0), (165, 47))
                       + _lines((0, 150), (95, 103)) + _lines((260, 150), (165, 103)))
        self.assertEqual(result.cluster_count, 1)
        self.assertEqual(len(result.clusters[0].inners), 0)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 260 * 150)
        self.assertEqual(len(result.loose), 8)


class TestB_BridgeSplitsParts(unittest.TestCase):
    """Two rectangles joined by a line: the outer border walks it back and forth. Two
    pieces, and heal() says so."""

    def test_two_pieces_and_warning(self):
        result = _heal(_lines((0, 0), (110, 0), (110, 50), (110, 100), (0, 100), closed=True)
                       + _lines((166, 0), (276, 0), (276, 100), (166, 100), (166, 50), closed=True)
                       + _lines((110, 50), (166, 50)))
        self.assertEqual(result.cluster_count, 2)
        self.assertEqual(len(result.loose), 1)
        self.assertIn("joining-edge", [n.code for n in result.notes], result.notes)


class TestC_GrazedChordIsChord(unittest.TestCase):
    """A chord at y=49 crosses a V notch 1.5 mm deep in the top side: for 1.33 mm
    out of 100 it borders the outside. Less than half: chord, and the notch stays
    in the contour."""

    def test_chord_in_the_trash_notch_in_the_contour(self):
        outline = _lines((0, 0), (100, 0), (100, 49), (100, 50), (51, 50), (50, 48.5), (49, 50),
                         (0, 50), (0, 49), closed=True)
        result = _heal(outline + _lines((0, 49), (100, 49)))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 100 * 50 - 1.5)
        self.assertEqual(len(result.loose), 1)


class TestD_CrossingSidesAreReported(unittest.TestCase):
    """A notch with overlapping flanks: the right flank returns to (27, 0.5), to the
    left of where the left one starts, and the following side crosses the left
    flank just above the bottom. heal() does not repair: it says so, with the point."""

    NOTCH = ((0, 0), (28, 0), (30, 20), (27, 0.5), (60, 0), (60, 40), (30, 40), (0, 40))

    def test_warning_with_the_point(self):
        result = _heal(_lines(*self.NOTCH, closed=True))
        crossing = [w for w in result.warnings if w.code == "crossing"]
        self.assertEqual(len(crossing), 1, result.warnings)
        self.assertAlmostEqual(crossing[0].at[0], 28.048, places=2)
        self.assertAlmostEqual(crossing[0].at[1], 0.484, places=2)

    def test_true_crossing_found(self):
        doc = topo.load_segments(_lines(*self.NOTCH, closed=True))
        points = interior_crossings(doc.edges, TOL)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0][0], 28.048, places=2)
        self.assertAlmostEqual(points[0][1], 0.484, places=2)

    def test_t_contact_is_not_a_crossing(self):
        # the end of a chord at mid top side: a contact, not an overlap
        doc = topo.load_segments(_lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True)
                                 + _lines((0, 0), (20, 20)))
        self.assertEqual(interior_crossings(doc.edges, TOL), [])

    def test_clean_drawing_no_warning(self):
        result = _heal(_lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True))
        self.assertFalse(any("crossing" in w for w in result.warnings), result.warnings)


class TestE_ClosedChainNeverCandidate(unittest.TestCase):
    """A triangular hole with a vertex in common with the outer contour: its chain
    starts and returns to the same node, so it is never a chord. Today it is a
    hole; whether it should go to the trash is open in TODO."""

    def test_today_it_stays_a_hole(self):
        result = _heal(_lines((0, 0), (260, 0), (260, 120), (0, 120), closed=True)
                       + _lines((0, 0), (90, 40), (50, 80), closed=True))
        self.assertEqual(result.cluster_count, 1)
        self.assertEqual(len(result.clusters[0].inners), 1)
        self.assertEqual(len(result.loose), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
