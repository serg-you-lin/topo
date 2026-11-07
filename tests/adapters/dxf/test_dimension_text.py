"""
tests/adapters/dxf/test_dimension_text.py
-----------------------------------------
La stringa che una quota DXF mostra, risolta in lettura (`<>` = la misura,
MAP.md D138).
"""

import unittest

from topo.model.text import RenderedGeometry, RenderedText
from topo_dxf.text_extractor import _shown_text


def _texts(*contents):
    return RenderedGeometry(texts=[RenderedText(content=c, position=(0, 0)) for c in contents])


class TestShownText(unittest.TestCase):
    """La stringa di una quota DXF, risolta in lettura (`<>` = la misura, D138)."""

    def test_override_con_la_misura_disegnata(self):
        # il simbolo arriva come frammento a sé ("n" in un font di simboli): vale l'override
        self.assertEqual(_shown_text("Ø<>", _texts("n", "6.5"), 6.5), "Ø6.5")

    def test_override_usa_la_precisione_del_disegno(self):
        self.assertEqual(_shown_text("M<>", _texts("M", "5"), 5.000000004), "M5")

    def test_override_senza_testo_disegnato(self):
        self.assertEqual(_shown_text("(<>)", RenderedGeometry(), 35.0), "(35)")

    def test_frammenti_uniti(self):
        self.assertEqual(_shown_text(None, _texts("∅5,3", "+0,05^-0"), 6.625), "∅5,3+0,05^-0")

    def test_solo_misura(self):
        self.assertEqual(_shown_text(None, RenderedGeometry(), 12.50), "12.5")


if __name__ == "__main__":
    unittest.main()
