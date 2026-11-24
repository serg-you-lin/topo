"""
test_writeback.py
-----------------
Integration tests for topo_dxf.to_dxf().

After the refactoring `write` no longer modifies the source modelspace: it
produces a NEW Drawing. These tests verify the routing of the topo layers on
the materialized document (doc_out), no longer on the starting msp.

The old behaviour "move the entities on the msp / entities on layer Trash /
keep_trash" no longer exists — the related tests were rewritten to inspect the
model (`result.loose`) or the output of to_dxf().

Then run:
    python -m pytest tests/adapters/dxf/test_writeback.py -v
"""

import math
import unittest
from collections import Counter
import ezdxf


import topo
import topo_dxf
from topo_dxf.parser import DxfEntityDispatcher
from topo_dxf.layers import LAYER_OUTER, LAYER_INNER
from tests.paths import DATA, drawing

EXAMPLES_DIR = DATA


def _pipeline(name, *, name_roles=None):
    """heal → to_dxf. Ritorna (result, msp_out)."""
    doc = topo_dxf.load_dxf(drawing(name), role_rules=topo.name_rules(name_roles or {}))
    result = topo.heal(doc).faces()
    doc_out = topo_dxf.to_dxf(result, doc)
    return result, doc_out.modelspace()


def _layers_of(msp, dxftype):
    return {e.dxf.layer for e in msp.query(dxftype)}


# --- 4-LINE rectangle — outer routing ---

class TestWritebackRectLines(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_lines.dxf")

    def test_001_writes_lwpolyline(self):
        self.assertGreaterEqual(len(list(self.msp.query("LWPOLYLINE"))), 1)

    def test_002_outer_layer_assigned(self):
        self.assertIn(LAYER_OUTER, _layers_of(self.msp, "LWPOLYLINE"))

    def test_003_outer_color_bylayer(self):
        for e in self.msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, 256)


# --- Outer CIRCLE (round flange) ---

class TestWritebackCircleOuter(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("circle_outer_with_hole.dxf")

    def test_001_outer_layer(self):
        self.assertIn(LAYER_OUTER, _layers_of(self.msp, "CIRCLE"))


# --- Large CIRCLE → LAYER_INNER ---

class TestWritebackCircleInner(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_circle_inner.dxf")

    def test_001_circle_on_inner_layer(self):
        self.assertIn(LAYER_INNER, _layers_of(self.msp, "CIRCLE"))


# --- Outer LWPOLYLINE + inner LINE loop ---

class TestWritebackInnerLoop(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_with_inner_mark.dxf")

    def test_001_inner_layer_present(self):
        self.assertIn(LAYER_INNER, _layers_of(self.msp, "LWPOLYLINE"))

    def test_002_single_outer(self):
        outer = [e for e in self.msp.query("LWPOLYLINE")
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)


# --- Deduplication ---

class TestWritebackDeduplication(unittest.TestCase):

    def setUp(self):
        self.result, self.msp = _pipeline("rect_lines_duplicated.dxf")

    def test_001_single_outer_lwpolyline(self):
        outer = [e for e in self.msp.query("LWPOLYLINE")
                 if e.dxf.layer == LAYER_OUTER]
        self.assertEqual(len(outer), 1)

    def test_002_no_duplicate_lines_in_output(self):
        from topo_dxf.sanitize import deduplicate as _dedup
        self.assertEqual(_dedup(self.msp), 0)


# --- Trash — lives in the model AND is materialized on the Trash layer of doc_out ---

from topo_dxf.layers import TRASH_LAYER


class TestWritebackTrash(unittest.TestCase):

    def test_001_trash_entities_in_model(self):
        result, _ = _pipeline("rect_with_trash.dxf")
        self.assertGreater(len(result.loose), 0)

    def test_002_trash_materialized_on_trash_layer(self):
        # Regression: to_dxf() MUST bring every unclassified entity back on the Trash
        # layer — a CAM operator must see the whole starting drawing, not only the clean parts.
        result, msp = _pipeline("rect_with_trash.dxf")
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), len(result.loose))

    def test_003_include_trash_false_omits_trash(self):
        doc = topo_dxf.load_dxf(drawing("rect_with_trash.dxf"))
        result = topo.heal(doc).faces()
        msp = topo_dxf.to_dxf(result, doc, include_loose=False).modelspace()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), 0)

    def test_004_open_trash_not_closed(self):
        # Open traces must not be closed: a trash LWPOLYLINE with the closed flag would
        # falsify the shape. two_rects_with_bend has an inner bending line that the
        # detector does not promote (endpoint ~10 mm from the outer) → it ends in trash
        # as an open trace.
        result, msp = _pipeline("two_rects_with_bend.dxf")
        trash_pl = [e for e in msp.query("LWPOLYLINE")
                    if e.dxf.layer == TRASH_LAYER]
        self.assertGreater(len(trash_pl), 0)
        for e in trash_pl:
            self.assertFalse(e.closed)

    def test_005_invalid_result_written_unless_refused(self):
        # No closed outer contour (arc_open at default tolerance: arc/arc gap of ~0.26
        # mm > 0.05) → heal() invalidates the result. By default to_dxf() writes it
        # anyway (everything in trash); with allow_invalid=False it refuses, as whoever
        # delivers to a machine wants.
        doc = topo_dxf.load_dxf(drawing("arc_open.dxf"))
        result = topo.heal(doc).faces()
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.clusters), 0)
        self.assertTrue(result.errors)

        msp = topo_dxf.to_dxf(result, doc).modelspace()
        trash = [e for e in msp if e.dxf.layer == TRASH_LAYER]
        self.assertEqual(len(trash), len(result.loose))
        self.assertGreater(len(trash), 0)

        with self.assertRaises(ValueError):
            topo_dxf.to_dxf(result, doc, allow_invalid=False)
        with self.assertRaises(ValueError):
            topo.experimental.to_svg(result, allow_invalid=False)
        self.assertIn("<svg", topo.experimental.to_svg(result))


class TestWritebackSourceLayerNotKept(unittest.TestCase):
    """The source layer "MARK" of la_104 is not a contour: its geometry stays in the
    model as loose, and the written DXF has no such layer."""

    def setUp(self):
        doc = topo_dxf.load_dxf(drawing("la_104.DXF"))
        self.result = topo.heal(doc).faces()
        self.msp = topo_dxf.to_dxf(self.result, doc).modelspace()

    def test_001_mark_goes_to_trash_without_detect(self):
        self.assertEqual(sum(1 for e in self.msp if e.dxf.layer == "MARK"), 0)

    def test_002_trash_has_entities(self):
        self.assertGreater(len(self.result.loose), 0)


# --- Cluster E — the source's linetype always restored on output. Dashed lines must not come out continuous. The colour is never touched instead: it stays that of the destination topo layer (semantic by role — green outer, red trash, ... — adapters/dxf/layers.py), never the source's. ---

class TestWritebackStyle(unittest.TestCase):

    def _multifeature(self):
        name = "Multifeature.dxf"
        if not (drawing(name)).exists():
            self.skipTest(name)
        return _pipeline(name, name_roles={"MARK": "engrave"})

    def test_001_trash_linetype_preserved(self):
        # 64+ LINEs on "02___PRT_ALL_AXES" (hole axes) are CENTER in the source and end
        # in trash: they must stay CENTER on output, not fall back to the continuous
        # BYLAYER of the Trash layer.
        _, msp = self._multifeature()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertTrue(any(e.dxf.linetype == "CENTER" for e in trash))

    def test_002_custom_linetype_registered_with_pattern(self):
        _, msp = self._multifeature()
        self.assertIn("CENTER", msp.doc.linetypes)
        lt = msp.doc.linetypes.get("CENTER")
        self.assertGreater(len(lt.simplified_line_pattern()), 1)

    def test_003_trash_color_stays_trash_layer_color(self):
        # The same axis lines carry an explicit colour in the source (ACI 4/7/1, some
        # also with true_color): the trash never restores the original colour, only the
        # dashing. The colour stays that of the Trash layer (BYLAYER).
        _, msp = self._multifeature()
        trash = [e for e in msp
                 if e.dxf.hasattr("layer") and e.dxf.layer == TRASH_LAYER]
        self.assertTrue(trash)
        for e in trash:
            self.assertEqual(e.dxf.color, 256)
            self.assertFalse(e.dxf.hasattr("true_color"))

    def test_004_structural_color_stays_bylayer_despite_source_color(self):
        # outer/inner stay BYLAYER even when the source had a different explicit
        # colour: the colour is a domain decision by role (adapters/dxf/layers.py), not
        # an attribute to carry faithfully.
        result, msp = _pipeline("rect_with_circle_hole.dxf")
        for e in msp.query("LWPOLYLINE"):
            if e.dxf.layer == LAYER_OUTER:
                self.assertEqual(e.dxf.color, 256)


# --- Annotations — texts and dimensions never discarded, routing to a dedicated layer ---

from topo_dxf.layers import LAYER_ANNOTATION


class TestWritebackTexts(unittest.TestCase):

    def _texts(self, msp):
        return list(msp.query("TEXT")) + list(msp.query("MTEXT"))

    def test_001_dimensions_and_text_materialized(self):
        # gamba_tavolo: 7 DIMENSIONs + 1 MTEXT in the source. No part covers them →
        # before they all vanished. Now each is a written TEXT/MTEXT.
        result, msp = _pipeline("gamba_tavolo.dxf")
        texts = self._texts(msp)
        self.assertEqual(len(texts), 8)

    def test_002_texts_on_dedicated_layer_by_default(self):
        result, msp = _pipeline("gamba_tavolo.dxf")
        for e in self._texts(msp):
            self.assertEqual(e.dxf.layer, LAYER_ANNOTATION)

    def test_003_dimension_carries_measured_value(self):
        # The dimension carries no geometry in the model: we materialize its value.
        result, msp = _pipeline("gamba_tavolo.dxf")
        values = {e.dxf.text for e in msp.query("TEXT")}
        self.assertIn("50", values)

    def test_003b_dimension_geometry_rendered_not_just_number(self):
        # Regression: the dimension must come out with its lines (leaders, measure
        # line, arrows), not just a number placed at random.
        result, msp = _pipeline("gamba_tavolo.dxf")
        dim_geom = [e for e in msp.query("LWPOLYLINE")
                    if e.dxf.layer == LAYER_ANNOTATION]
        # 7 dimensions → several polylines (≈ 2 leaders + measure line + arrows)
        self.assertGreater(len(dim_geom), 7 * 3)

    def test_004_text_covered_by_part_also_routed_to_annotation(self):
        # rect_with_trash: the TEXT is inside the outer, before it stayed on the source
        # layer "TESTO". By default it goes on the Annotation layer anyway.
        result, msp = _pipeline("rect_with_trash.dxf")
        texts = self._texts(msp)
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].dxf.layer, LAYER_ANNOTATION)

    def test_005_text_with_role_goes_on_its_role_layer(self):
        # The source layer does not stay in the model: a text the caller wants distinct
        # gives it a role, and it goes on the role's layer.
        doc = topo_dxf.load_dxf(drawing("rect_with_trash.dxf"),
                            role_rules=topo.name_rules({"TESTO": "note"}))
        result = topo.heal(doc).faces()
        msp = topo_dxf.to_dxf(result, doc).modelspace()
        texts = list(msp.query("TEXT"))
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0].dxf.layer, "note")

    def test_006_text_layer_custom_routes_there(self):
        doc = topo_dxf.load_dxf(drawing("rect_with_trash.dxf"))
        result = topo.heal(doc).faces()
        msp = topo_dxf.to_dxf(result, doc, text_layer=TRASH_LAYER).modelspace()
        texts = list(msp.query("TEXT"))
        self.assertEqual(texts[0].dxf.layer, TRASH_LAYER)

    def test_007_dims_and_leaders_survive_audit(self):
        # Multifeature: 16 DIMENSIONs (no geometry block → ezdxf's auditor deleted them)
        # + 4 LEADERs (section arrows, no repr point). They must all arrive in the output.
        name = "Multifeature.dxf"
        if not (drawing(name)).exists():
            self.skipTest(name)
        doc = topo_dxf.load_dxf(drawing(name))
        # the 16 dimensions have no block: only their string, centred on the text
        # midpoint, topo_dxf does not draw them; the 4 LEADERs have no string of their
        # own and are curves, the filled tip included
        dims = [a for a in doc.texts if a.rendered.is_empty()
                and (a.halign, a.valign) == ("center", "center")]
        self.assertEqual(len(dims), 16)
        # and a warning counts them: their drawing is not in the file
        self.assertEqual([str(w).split(":")[1].split()[0] for w in doc.warnings
                          if w.code == "dxf-dimension-no-block"], ["16"])
        self.assertEqual([a for a in doc.texts if not a.text], [])
        # what they measure, with the file's points, the number not: open `<>`
        self.assertTrue(all(a.measures is not None for a in dims))
        radius = [a for a in dims if isinstance(a.measures, topo.MeasuredRadius)]
        self.assertEqual([a.text for a in radius], ["R<>"])
        m = radius[0].measures
        self.assertAlmostEqual(math.dist(m.center, m.on_circle), 6.0, places=6)
        self.assertEqual(sum(1 for e in doc.edges if e.style.filled), 12)
        result = topo.heal(doc).faces()
        msp = topo_dxf.to_dxf(result, doc).modelspace()
        ann = Counter(e.dxftype() for e in msp if e.dxf.layer == LAYER_ANNOTATION)
        self.assertEqual(ann, Counter({"TEXT": len(doc.texts)}))

    def test_008_every_layer_read_by_default(self):
        # By default every layer is read; whoever re-reads a topo file skips the
        # Annotation and Trash layers with `skip_layers=SKIP_LAYERS`, by exact name,
        # case-insensitive.
        self.assertEqual(set(topo_dxf.SKIP_LAYERS), {LAYER_ANNOTATION, TRASH_LAYER})
        src = ezdxf.new("R2010")
        msp = src.modelspace()
        for i, layer in enumerate((LAYER_ANNOTATION, TRASH_LAYER.lower(), "Trash_old", "0")):
            msp.add_line((0, 10 * i), (50, 10 * i), dxfattribs={"layer": layer})
        doc = topo_dxf.document_from_msp(msp, skip_layers=topo_dxf.SKIP_LAYERS)
        self.assertEqual(len(doc.edges), 2)
        # nothing vanishes in silence: a warning counts the curves per layer
        skipped = [w for w in doc.warnings if w.code == "dxf-layer-skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertIn("2 curves", skipped[0].message)
        self.assertEqual(len(skipped[0].notes), 2)
        full = topo_dxf.document_from_msp(msp)
        self.assertEqual(len(full.edges), 4)
        self.assertFalse([w for w in full.warnings if w.code == "dxf-layer-skipped"])
        # a function decides by itself: here part of the name
        skip = lambda name: "trash" in name.lower()
        self.assertEqual(len(topo_dxf.document_from_msp(msp, skip_layers=skip).edges), 2)


# --- INSERT — exploded by default: a block must not make the geometry vanish ---

class TestWritebackInsertExplodedByDefault(unittest.TestCase):

    def test_001_block_geometry_survives_without_flag(self):
        # scritta.dxf is a single INSERT wrapping 93 LINEs + 23 SPLINEs (letters).
        # Without exploding, load_dxf discarded everything. Now it is the default.
        doc = topo_dxf.load_dxf(drawing("scritta.dxf"))
        self.assertGreater(len(doc.edges), 50)
        result = topo.heal(doc).faces()
        self.assertEqual(len(result.clusters), 1)
        self.assertGreater(len(result.clusters[0].inners), 6)


# --- Geometric round-trip — the WRITTEN geometry must coincide with the model ---

class TestWritebackArcRoundTrip(unittest.TestCase):
    """Arc regression: to_dxf() must materialize the outer with the same area as the
    model. Before the arc_seg_to_bulge fix the inverted arcs (loop oriented CCW →
    ccw=False) were written with the bulge of the complementary arc, that is
    "upside down", falsifying the area by thousands of mm²."""

    ARC_EXAMPLES = [
        "archi_bastardi.dxf",
        "arco convesso.dxf",
        "maniglia.dxf",
        "flangia_scantonata.dxf",
        "rettangolo_raggiato.dxf",
    ]

    def _written_outer_area(self, msp):
        area = 0.0
        for e in msp:
            if not e.dxf.hasattr("layer") or e.dxf.layer != LAYER_OUTER:
                continue
            if e.dxftype() not in ("LWPOLYLINE", "POLYLINE", "CIRCLE"):
                continue
            prim = DxfEntityDispatcher(e).parse()
            if prim is None:
                continue
            try:
                ring = prim if isinstance(prim, list) else [prim]
                area += topo.Contour.from_segments(ring, role="outer").area
            except ValueError:
                continue
        return area

    def test_outer_area_matches_model(self):
        for name in self.ARC_EXAMPLES:
            path = drawing(name)
            if not path.exists():
                continue
            with self.subTest(example=name):
                result, msp = _pipeline(name)
                model_area = sum(p.outer.area for p in result.clusters)
                written_area = self._written_outer_area(msp)
                self.assertAlmostEqual(
                    written_area, model_area, delta=max(1.0, model_area * 1e-4),
                    msg=f"{name}: outer written {written_area:.3f} vs "
                        f"modello {model_area:.3f}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
