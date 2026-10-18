"""
test_annotation_role.py
-----------------------
Il ruolo di un'annotazione (MAP.md D127): lo scrive il consumer, o le sue
RoleRule al load sul nome del gruppo sorgente; topo lo conserva e, in un DXF
scritto con `annotation_layer=None`, mette l'annotazione sul layer del ruolo.
"""

import sys
import unittest
from pathlib import Path

import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import topo


def _drawing_with_text(layer: str):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
    msp.add_text("CODICE", dxfattribs={"layer": layer, "insert": (50, 50), "height": 5})
    return msp


class TestAnnotationRole(unittest.TestCase):

    def test_default_unknown_e_slug(self):
        self.assertEqual(topo.Note(position=(0, 0)).role, "unknown")
        self.assertEqual(topo.Note(position=(0, 0), role="Title Block").role, "title_block")

    def test_regola_sul_nome_al_load(self):
        msp = _drawing_with_text("Testi")
        doc = topo.document_from_msp(msp, role_rules=topo.name_rules({"testi": "part_code"}))
        self.assertEqual([a.role for a in doc.annotations], ["part_code"])
        self.assertEqual(doc.annotations[0].group, "Testi")

    def test_regola_sull_aspetto_non_tocca_le_annotazioni(self):
        msp = _drawing_with_text("Testi")
        doc = topo.document_from_msp(msp, role_rules=[topo.RoleRule("cut", dashed=False)])
        self.assertEqual([a.role for a in doc.annotations], ["unknown"])

    def test_dxf_sul_layer_del_ruolo(self):
        msp = _drawing_with_text("Testi")
        doc = topo.document_from_msp(msp, role_rules=topo.name_rules({"testi": "part_code"}))
        out = topo.to_dxf(topo.heal(doc), annotation_layer=None)
        layers = {e.dxf.layer for e in out.modelspace().query("TEXT MTEXT")}
        self.assertEqual(layers, {"part_code"})

    def test_dxf_senza_ruolo_torna_al_layer_d_origine(self):
        doc = topo.document_from_msp(_drawing_with_text("Testi"))
        out = topo.to_dxf(topo.heal(doc), annotation_layer=None)
        layers = {e.dxf.layer for e in out.modelspace().query("TEXT MTEXT")}
        self.assertEqual(layers, {"Testi"})


if __name__ == "__main__":
    unittest.main()
