"""
tests/adapters/dxf/test_dxf_fills.py
------------------------------------
Filled areas and callouts without a string: a SOLID, a filled HATCH, a polyline
with width arrive as sides with `EdgeStyle.filled`; a LEADER with no string of
its own arrives as curves, not as `Text`; `to_dxf` rewrites a loop of filled
sides as a filled HATCH.

The fixture uses ezdxf because topo cannot write these entities: it is the
input format itself that is tested here.
"""

import math
import os
import tempfile
import unittest

import ezdxf

import topo
import topo_dxf
from topo.core.geometry.measure import segment_length


def _drawing(path: str) -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    # A: a SOLID triangle (arrowhead)
    msp.add_solid([(0, 0), (4, 0), (2, 3)])
    # B: a filled 3x18 HATCH with the border saved in pieces, as in anch_01: the
    #    four sides out of order
    hatch = msp.add_hatch(color=1)
    hatch.set_solid_fill()
    edges = hatch.paths.add_edge_path()
    edges.add_line((20, 0), (23, 0))
    edges.add_line((23, 0), (23, 18))
    edges.add_line((20, 18), (20, 0))
    edges.add_line((23, 18), (20, 18))
    # C: a polyline of width 1 from (40, 0) to (50, 0)
    msp.add_lwpolyline([(40, 0), (50, 0)], dxfattribs={"const_width": 1.0})
    # D: a LEADER with no note, filled arrow at (60, 10)
    msp.add_leader([(60, 10), (60, 0)])
    doc.saveas(path)


class TestFilledAreas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.tmp.name, "fills.dxf")
        _drawing(cls.path)
        cls.doc = topo_dxf.load_dxf(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _filled_in(self, x0, x1):
        return [e for e in self.doc.edges if e.style.filled
                and x0 <= min(e.start[0], e.end[0]) and max(e.start[0], e.end[0]) <= x1]

    def _length(self, edges) -> float:
        return sum(segment_length(e.segment) for e in edges)

    def test_solid_becomes_three_filled_sides(self):
        sides = self._filled_in(-1, 5)
        self.assertEqual(len(sides), 3)
        self.assertAlmostEqual(self._length(sides), 4 + 2 * math.hypot(2, 3), places=6)

    def test_solid_hatch_in_pieces_stays_a_rectangle(self):
        # the four sides of the file, no chord: perimeter 2 * (3 + 18)
        sides = self._filled_in(19, 24)
        self.assertEqual(len(sides), 4)
        self.assertAlmostEqual(self._length(sides), 42.0, places=6)

    def test_wide_polyline_becomes_its_outline(self):
        sides = self._filled_in(39, 51)
        xs = [p[0] for e in sides for p in (e.start, e.end)]
        ys = [p[1] for e in sides for p in (e.start, e.end)]
        self.assertEqual((min(xs), max(xs), min(ys), max(ys)), (40.0, 50.0, -0.5, 0.5))
        self.assertAlmostEqual(self._length(sides), 22.0, places=6)

    def test_no_areas_lost(self):
        lost = [d for d in self.doc.warnings if d.code == "dxf-not-modeled"]
        self.assertEqual(lost, [])

    def test_leader_without_string_is_geometry(self):
        self.assertEqual([t for t in self.doc.texts if not t.text], [])
        line = [e for e in self.doc.edges if not e.style.filled
                and e.start[0] == e.end[0] == 60.0]
        self.assertTrue(line)
        self.assertTrue(self._filled_in(55, 65))

    def test_rule_on_the_filled(self):
        doc = topo_dxf.load_dxf(self.path, role_rules=[topo.RoleRule("arrow", filled=True)])
        self.assertEqual({e.role for e in doc.edges if e.style.filled}, {"arrow"})
        self.assertNotIn("arrow", {e.role for e in doc.edges if not e.style.filled})

    def test_to_dxf_rewrites_the_filled_areas(self):
        result = topo.heal(self.doc).outlines()
        out = topo_dxf.to_dxf(result, self.doc)
        hatches = list(out.modelspace().query("HATCH"))
        # A, B, C and the leader's tip
        self.assertEqual(len(hatches), 4)
        self.assertTrue(all(h.dxf.solid_fill for h in hatches))


class TestDocumentFromMsp(unittest.TestCase):
    """`document_from_msp` explodes nothing: a LEADER with no string and an unread
    SOLID are told by a warning, not by silence."""

    def test_warning_for_what_it_does_not_read(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_leader([(0, 10), (0, 0)])
        msp.add_solid([(0, 0), (4, 0), (2, 3)])
        result = topo_dxf.document_from_msp(msp)
        lost = [d.message for d in result.warnings if d.code == "dxf-not-modeled"]
        self.assertTrue(any("LEADER" in m for m in lost))
        self.assertTrue(any("SOLID" in m for m in lost))


class TestRoleRuleFilled(unittest.TestCase):

    def test_single_valid_condition(self):
        rule = topo.RoleRule("arrow", filled=True)
        self.assertTrue(rule.matches("", style=topo.model.EdgeStyle(filled=True)))
        self.assertFalse(rule.matches("", style=topo.model.EdgeStyle()))

    def test_text_without_appearance_does_not_match(self):
        self.assertFalse(topo.RoleRule("arrow", filled=False).matches("x", style=None))


if __name__ == "__main__":
    unittest.main()
