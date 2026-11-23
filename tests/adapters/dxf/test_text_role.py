"""
test_text_role.py
-----------------
The role of a text: the consumer writes it, or its RoleRules at load on the
source group's name; topo keeps it and a DXF puts the text on the layer of its
role, like an edge. One without a role goes on `text_layer`.
"""

import unittest

import ezdxf


import topo
import topo_dxf


def _drawing_with_text(layer: str):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], close=True)
    msp.add_text("CODICE", dxfattribs={"layer": layer, "insert": (50, 50), "height": 5})
    return msp


class TestTextRole(unittest.TestCase):

    def test_default_unknown_and_slug(self):
        self.assertEqual(topo.Text(position=(0, 0)).role, "unknown")
        self.assertEqual(topo.Text(position=(0, 0), role="Title Block").role, "title_block")

    def test_rule_on_the_name_at_load(self):
        msp = _drawing_with_text("Testi")
        doc = topo_dxf.document_from_msp(msp, role_rules=topo.name_rules({"testi": "part_code"}))
        self.assertEqual([a.role for a in doc.texts], ["part_code"])

    def test_rule_on_the_appearance_does_not_touch_the_texts(self):
        msp = _drawing_with_text("Testi")
        doc = topo_dxf.document_from_msp(msp, role_rules=[topo.RoleRule("cut", dashed=False)])
        self.assertEqual([a.role for a in doc.texts], ["unknown"])

    def _text_layers(self, doc, **kwargs) -> set:
        out = topo_dxf.to_dxf(topo.heal(doc).faces(), **kwargs)
        return {e.dxf.layer for e in out.modelspace().query("TEXT MTEXT")}

    def test_dxf_on_the_role_layer(self):
        msp = _drawing_with_text("Testi")
        doc = topo_dxf.document_from_msp(msp, role_rules=topo.name_rules({"testi": "part_code"}))
        self.assertEqual(self._text_layers(doc), {"part_code"})

    def test_dxf_on_the_layer_chosen_for_the_role(self):
        msp = _drawing_with_text("Testi")
        doc = topo_dxf.document_from_msp(msp, role_rules=topo.name_rules({"testi": "part_code"}))
        self.assertEqual(self._text_layers(doc, layers={"part_code": "Codice"}), {"Codice"})

    def test_dxf_without_role_on_the_texts_layer(self):
        doc = topo_dxf.document_from_msp(_drawing_with_text("Testi"))
        self.assertEqual(self._text_layers(doc), {"Annotation"})
        self.assertEqual(self._text_layers(doc, text_layer="Note"), {"Note"})


if __name__ == "__main__":
    unittest.main()
