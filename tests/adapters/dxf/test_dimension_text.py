"""
tests/adapters/dxf/test_dimension_text.py
-----------------------------------------
The string a DXF dimension shows, resolved at reading (`<>` = the measure).
"""

import unittest

from topo.model.text import RenderedGeometry, RenderedText
from types import SimpleNamespace

from topo_dxf.text_extractor import _shown_text, written_by_hand


def _texts(*contents):
    return RenderedGeometry(texts=[RenderedText(content=c, position=(0, 0)) for c in contents])


class TestShownText(unittest.TestCase):
    """The string of a DXF dimension: the file's field with `<>` replaced by the
    number the file draws; topo does not compute numbers."""

    def test_override_with_the_drawn_measure(self):
        # the symbol arrives as a fragment of its own ("n" in a symbol font): the override holds
        self.assertEqual(_shown_text("Ø<>", _texts("n", "6.5")), "Ø6.5")

    def test_override_uses_the_drawings_precision(self):
        self.assertEqual(_shown_text("M<>", _texts("M", "5")), "M5")

    def test_number_inside_the_block_string(self):
        # the block writes "R5", not an isolated "5": the number is taken from there
        self.assertEqual(_shown_text("R<>", _texts("R5")), "R5")
        self.assertEqual(_shown_text("Ø<>", _texts("n4.2")), "Ø4.2")
        self.assertEqual(_shown_text("(<>)", _texts("41°")), "(41)")

    def test_number_written_in_the_override_skipped(self):
        # "0.2" is already written by the override: the measure is the other number
        self.assertEqual(_shown_text("<>±0.2", _texts("10±0.2")), "10±0.2")

    def test_no_drawn_number_leaves_the_placeholder(self):
        # dimension with no block (QCAD): the number is not in the file
        self.assertEqual(_shown_text("R<>", RenderedGeometry()), "R<>")
        self.assertEqual(_shown_text("(<>)", RenderedGeometry()), "(<>)")
        self.assertEqual(_shown_text(None, RenderedGeometry()), "<>")

    def test_fragments_joined(self):
        self.assertEqual(_shown_text(None, _texts("∅5,3", "+0,05^-0")), "∅5,3+0,05^-0")


def _dimension(text):
    # only the file's text field: the rule looks at nothing else
    return SimpleNamespace(dxf={"text": text})


class TestWrittenByHand(unittest.TestCase):
    """A dimension with the number written by hand has no decimals or factor: the
    number is the text as written, topo does not compare it with the points."""

    def test_written_number(self):
        self.assertTrue(written_by_hand(_dimension("2000.00")))
        self.assertTrue(written_by_hand(_dimension("R5")))

    def test_placeholder_or_empty(self):
        for text in ("", "<>", "R<>", "<>±0.2", " "):
            self.assertFalse(written_by_hand(_dimension(text)), text)


if __name__ == "__main__":
    unittest.main()
