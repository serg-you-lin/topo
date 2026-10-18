"""
test_role_style.py
-------------------
Test per l'uscita per ruolo in to_dxf() (MAP.md D37, D128): il chiamante
sceglie il layer di un ruolo (`layers`, un nome o una funzione
dell'elemento) e il suo aspetto (`role_styles`). L'aspetto agisce sul layer,
non sull'entità — tutto ciò che si scrive è BYLAYER. Nessuno stato fra una
chiamata e l'altra.
"""

import unittest
from pathlib import Path
import sys

import ezdxf

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo import RoleStyle
from topo_dxf.layers import LAYER_OUTER, TRASH_LAYER, color_for_role


def _rect_with_hole_and_frame():
    """
    Rettangolo 100x50 con un cerchio dentro + due LINE su layer STAMP dentro
    (ruolo 'stamp_d90', una a sinistra e una a destra) + una LINE su layer
    FRAME fuori (ruolo consumatore 'frame', D31).
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    msp.add_line((0, 0), (100, 0))
    msp.add_line((100, 0), (100, 50))
    msp.add_line((100, 50), (0, 50))
    msp.add_line((0, 50), (0, 0))
    msp.add_circle((50, 25), 5)

    msp.add_line((10, 10), (30, 10), dxfattribs={'layer': 'STAMP'})
    msp.add_line((70, 40), (90, 40), dxfattribs={'layer': 'STAMP'})
    msp.add_line((200, 200), (220, 200), dxfattribs={'layer': 'FRAME'})

    doc_in = topo_dxf.document_from_msp(
        msp, role_rules=topo.name_rules({'FRAME': 'frame', 'STAMP': 'stamp_d90'}))
    result = topo.heal(doc_in, tolerance=0.05)
    return result, doc_in


def _entities_on(doc, layer: str) -> int:
    return len(doc.modelspace().query(f'*[layer=="{layer}"]'))


class TestLayerByName(unittest.TestCase):
    """
    `layers={ruolo: nome}` manda un ruolo di consumatore sul layer scelto, e
    il suo `RoleStyle` va su quel layer; un ruolo senza scelta (`frame`) va
    sul layer col nome dello slug, grigio, senza `true_color` (D31).
    """

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            layers={"stamp_d90": "StampD90"},
            role_styles={"stamp_d90": RoleStyle(color=(255, 0, 255))},
        )

    def test_001_chosen_layer_has_true_color(self):
        layer = self.doc_out.layers.get("StampD90")
        self.assertTrue(layer.dxf.hasattr("true_color"))
        self.assertEqual(layer.rgb, (255, 0, 255))

    def test_002_role_entities_on_chosen_layer(self):
        self.assertEqual(_entities_on(self.doc_out, "StampD90"), 2)
        self.assertNotIn("stamp_d90", self.doc_out.layers)

    def test_003_frame_layer_created_with_consumer_color(self):
        self.assertIn('frame', self.doc_out.layers)
        layer = self.doc_out.layers.get('frame')
        self.assertFalse(layer.dxf.hasattr("true_color"))


class TestLayerSplitByElement(unittest.TestCase):
    """
    Una funzione in `layers` divide le entità di un ruolo su due layer
    guardando l'elemento scritto (come una piega "up" e una "down"); lo
    stile del ruolo va su entrambi.
    """

    def setUp(self):
        def side(element) -> str:
            x = element.segments[0].start[0]
            return "StampLeft" if x < 50 else "StampRight"

        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            layers={"stamp_d90": side},
            role_styles={"stamp_d90": RoleStyle(color=(0, 0, 255))},
        )

    def test_001_one_line_per_layer(self):
        self.assertEqual(_entities_on(self.doc_out, "StampLeft"), 1)
        self.assertEqual(_entities_on(self.doc_out, "StampRight"), 1)

    def test_002_style_on_both_layers(self):
        for name in ("StampLeft", "StampRight"):
            self.assertEqual(self.doc_out.layers.get(name).rgb, (0, 0, 255))


class TestEngineRoleRemapped(unittest.TestCase):
    """Anche un ruolo del motore si sposta: outer su `Cut`, verde di default,
    e il layer di default non nasce."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(self.result, self.doc_in, layers={"outer": "Cut"})

    def test_001_outer_on_cut(self):
        self.assertGreater(len(self.doc_out.modelspace().query('*[layer=="Cut"]')), 0)
        self.assertEqual(self.doc_out.layers.get("Cut").color, color_for_role("outer"))

    def test_002_no_default_outer_layer(self):
        self.assertNotIn(LAYER_OUTER, self.doc_out.layers)


class TestNoStateBetweenCalls(unittest.TestCase):
    """La mappa vale per la sua chiamata: la successiva, senza, torna al
    default (D128 — niente registro globale)."""

    def test_001_second_call_is_default(self):
        result, doc_in = _rect_with_hole_and_frame()
        topo_dxf.to_dxf(result, doc_in, role_styles={"outer": RoleStyle(color=(0, 0, 0))})
        doc_out = topo_dxf.to_dxf(result, doc_in)
        self.assertFalse(doc_out.layers.get(LAYER_OUTER).dxf.hasattr("true_color"))


class TestRoleStyleConsumerRole(unittest.TestCase):
    """role_styles funziona anche su uno slug di consumatore (frame, D31)."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            role_styles={"frame": RoleStyle(color=(0, 0, 0), lineweight=0.05)},
        )

    def test_001_frame_layer_is_black(self):
        layer = self.doc_out.layers.get('frame')
        self.assertEqual(layer.rgb, (0, 0, 0))

    def test_002_frame_layer_lineweight_in_hundredths_mm(self):
        layer = self.doc_out.layers.get('frame')
        self.assertEqual(layer.dxf.lineweight, 5)  # 0.05 mm * 100


class TestRoleStyleLinetypeOverride(unittest.TestCase):
    """role_styles registra e applica un linetype standard ezdxf."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            role_styles={"unknown": RoleStyle(linetype="DASHED")},
        )

    def test_001_dashed_linetype_registered(self):
        self.assertIn("DASHED", self.doc_out.linetypes)

    def test_002_trash_layer_uses_dashed(self):
        layer = self.doc_out.layers.get(TRASH_LAYER)
        self.assertEqual(layer.dxf.linetype, "DASHED")


class TestRoleStyleDash(unittest.TestCase):
    """Un tratto senza nome (`dash`, D126) si registra col nome del ruolo e
    il pattern DXF che apre con la lunghezza totale."""

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            role_styles={"unknown": RoleStyle(dash=(5.0, -2.0))},
        )

    def test_001_trash_layer_uses_role_dash(self):
        self.assertEqual(self.doc_out.layers.get(TRASH_LAYER).dxf.linetype, "UNKNOWN_DASH")

    def test_002_pattern_has_total_length(self):
        pattern = self.doc_out.linetypes.get("UNKNOWN_DASH").pattern_tags.tags
        self.assertEqual([t.value for t in pattern if t.code == 40], [7.0])


class TestRoleStyleUnknownLinetypeRaises(unittest.TestCase):
    """
    Un linetype che né il documento né la tabella standard sanno definire è
    un errore di configurazione del consumatore: solleva, mai un DXF con un
    riferimento pendente (MAP.md D85).
    """

    def test_001_unknown_name_raises(self):
        result, doc_in = _rect_with_hole_and_frame()
        with self.assertRaises(ValueError):
            topo_dxf.to_dxf(result, doc_in, role_styles={"unknown": RoleStyle(linetype="DASHHED")})


class TestRoleStyleUnknownRoleCreatesLayerEvenWithoutEntities(unittest.TestCase):
    """
    Un override per un ruolo che non compare in nessuna entità di questo
    documento non deve sollevare — il layer viene comunque creato e stilato.
    """

    def setUp(self):
        self.result, self.doc_in = _rect_with_hole_and_frame()
        self.doc_out = topo_dxf.to_dxf(
            self.result, self.doc_in,
            role_styles={"title_block": RoleStyle(color=(10, 20, 30))},
        )

    def test_001_layer_exists(self):
        self.assertIn("title_block", self.doc_out.layers)

    def test_002_layer_has_override_color(self):
        layer = self.doc_out.layers.get("title_block")
        self.assertEqual(layer.rgb, (10, 20, 30))


if __name__ == "__main__":
    unittest.main(verbosity=2)
