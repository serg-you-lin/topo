"""
tests/adapters/dxf/test_dimension_text.py
-----------------------------------------
La stringa che una quota DXF mostra, risolta in lettura (`<>` = la misura,
MAP.md D138).
"""

import unittest

from topo.model.text import RenderedGeometry, RenderedText
from types import SimpleNamespace

from topo_dxf.text_extractor import _shown_text, written_by_hand


def _texts(*contents):
    return RenderedGeometry(texts=[RenderedText(content=c, position=(0, 0)) for c in contents])


class TestShownText(unittest.TestCase):
    """La stringa di una quota DXF: il campo del file con `<>` sostituito dal
    numero che il file disegna; topo non calcola numeri (D263, D264)."""

    def test_override_con_la_misura_disegnata(self):
        # il simbolo arriva come frammento a sé ("n" in un font di simboli): vale l'override
        self.assertEqual(_shown_text("Ø<>", _texts("n", "6.5")), "Ø6.5")

    def test_override_usa_la_precisione_del_disegno(self):
        self.assertEqual(_shown_text("M<>", _texts("M", "5")), "M5")

    def test_numero_dentro_la_stringa_del_blocco(self):
        # il blocco scrive "R5", non un "5" isolato: il numero si prende da lì
        self.assertEqual(_shown_text("R<>", _texts("R5")), "R5")
        self.assertEqual(_shown_text("Ø<>", _texts("n4.2")), "Ø4.2")
        self.assertEqual(_shown_text("(<>)", _texts("41°")), "(41)")

    def test_numero_scritto_nell_override_saltato(self):
        # "0.2" lo scrive già l'override: la misura è l'altro numero
        self.assertEqual(_shown_text("<>±0.2", _texts("10±0.2")), "10±0.2")

    def test_nessun_numero_disegnato_lascia_il_segnaposto(self):
        # quota senza blocco (QCAD): il numero nel file non c'è
        self.assertEqual(_shown_text("R<>", RenderedGeometry()), "R<>")
        self.assertEqual(_shown_text("(<>)", RenderedGeometry()), "(<>)")
        self.assertEqual(_shown_text(None, RenderedGeometry()), "<>")

    def test_frammenti_uniti(self):
        self.assertEqual(_shown_text(None, _texts("∅5,3", "+0,05^-0")), "∅5,3+0,05^-0")


def _dimension(text):
    # solo il campo testo del file: la regola non guarda altro
    return SimpleNamespace(dxf={"text": text})


class TestWrittenByHand(unittest.TestCase):
    """Una quota col numero scritto a mano non ha decimali né fattore: il numero
    è il testo com'è scritto, topo non lo confronta coi punti (D265)."""

    def test_numero_scritto(self):
        self.assertTrue(written_by_hand(_dimension("2000.00")))
        self.assertTrue(written_by_hand(_dimension("R5")))

    def test_segnaposto_o_vuoto(self):
        for text in ("", "<>", "R<>", "<>±0.2", " "):
            self.assertFalse(written_by_hand(_dimension(text)), text)


if __name__ == "__main__":
    unittest.main()
