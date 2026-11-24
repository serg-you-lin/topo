
"""
Test suite for writeback.split() and the recipe heal → split → file.

Structure
---------
_Fixtures        — helpers that build geometry in memory and go through
                   the real heal() (no mock Result)

TestUnitSplitOutput        — unit: generated files, namer, min_area
TestUnitSplitFilters       — unit: include_texts, exclude_types, keep_trash
TestUnitSplitLayers        — unit: layers present and canonical colours in the children

TestIntegrationPipeline    — integration: heal→detect→split pipeline on examples/
TestIntegrationContours    — integration: closed LWPOLYLINEs, CIRCLE, SPLINE

Philosophy
----------
- The unit tests use _make_via_heal(): it builds an in-memory ezdxf msp, calls
  the real heal(), then calls split() directly. No fake Result — if heal() does
  not recognize the geometry the test fails with a clear message, not a false green.

- The integration tests use split_to_files() as a black box on files in
  examples/. They verify only invariants observable from outside (files on
  disk, layers, entities).

- exclude_types is a parameter split() must accept. If it does not exist yet,
  the tests in TestUnitSplitFilters fail with TypeError — a clear signal to add it.

- ALL_LAYERS must be exported from topo_dxf.rules.layers as:
      ALL_LAYERS = {LAYER_OUTER: 3, LAYER_INNER: 2, ...} (topo's palette in ACI)
  If it is missing, TestUnitSplitLayers.test_002 and TestIntegrationLayers.test_003
  fail with ImportError — a clear signal to add it.

Running
-------
    python -m unittest tests/adapters/dxf/test_splitter.py -v
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import ezdxf


import topo
import topo_dxf
from topo_dxf.text_extractor import TEXT_TYPES
from topo_dxf.layers import (
    LAYER_OUTER, LAYER_INNER, TRASH_LAYER,
    ALL_LAYERS,
)
from tests.paths import DATA, drawing
EXAMPLES_DIR = DATA


# --- Fixtures: in-memory geometry + real heal() ---

def _make_via_heal(points: list[tuple], extra_entities=None):
    """Create an in-memory ezdxf msp with a closed LWPOLYLINE defined by `points`,
    run the real heal() and return (msp, result).

    extra_entities: list of callables (msp) -> None to add extra entities (texts,
    circles, etc.) before heal().

    Used by the unit tests to have an authentic Result on controlled geometry,
    without files on disk and without depending on examples/."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "0"})
    if extra_entities:
        for fn in extra_entities:
            fn(msp)
    doc = topo_dxf.document_from_msp(msp)
    result = topo.heal(doc, label="fixture").faces()
    return doc, result


def _rect(w=200, h=100) -> list[tuple]:
    """Points of a rectangle with a corner at the origin."""
    return [(0, 0), (w, 0), (w, h), (0, h)]


def _read_children(out_dir: str) -> dict[str, object]:
    """Read all the .dxf files in out_dir and return {name: modelspace}."""
    return {
        f.name: ezdxf.readfile(str(f)).modelspace()
        for f in Path(out_dir).glob("*.dxf")
    }



def _split_files(result, out_dir, *, min_area=0.0,
                 namer=None, **write_kwargs):
    """Pure topo.split(), then to_dxf + saveas per part: the write options
    (`include_texts`, `exclude_types`, ...) go to to_dxf."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for part in topo.split(result, namer=namer, min_area=min_area):
        path = os.path.join(out_dir, f"{part.clusters[0].label}.dxf")
        topo_dxf.to_dxf(part, **write_kwargs).saveas(path)
        paths.append(path)
    return paths


def _split_to_files(doc, output_folder, label="", source_file="", tolerance=None,
                    namer=None, min_area=0.0, is_structural=None,
                    **write_kwargs):
    """heal → split → to_dxf + saveas per part: the recipe that was
    `topo_dxf.split_to_files`, removed from the surface and kept here as a black
    box of the integration tests."""
    result = topo.heal(doc,  label=label, source_file=source_file,
                       is_structural=is_structural).faces()
    if result.is_valid and result.clusters:
        _split_files(result, output_folder, min_area=min_area, namer=namer, **write_kwargs)
    return result


# --- UNIT TEST — writeback.split() ---

class TestUnitSplitOutput(unittest.TestCase):
    """Test the output invariants of split(): generated files, namer, min_area, output folder."""

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        self.doc, self.result = _make_via_heal(_rect())

    def _assert_heal_found_parts(self):
        self.assertGreater(
            len(self.result.clusters), 0,
            "heal() found no parts — check the fixture geometry"
        )

    def test_001_writes_a_file(self):
        """split() generates at least one .dxf file."""
        self._assert_heal_found_parts()
        generated = _split_files(self.result, self.out_dir)
        files = list(Path(self.out_dir).glob("*.dxf"))
        self.assertGreater(len(files), 0, "No .dxf file generated")
        self.assertEqual(len(generated), len(files),
                         "Returned list does not match the files on disk")

    def test_002_file_leggibile(self):
        """The generated files are valid DXFs readable by ezdxf."""
        self._assert_heal_found_parts()
        generated = _split_files(self.result, self.out_dir)
        for path in generated:
            try:
                ezdxf.readfile(path)
            except Exception as e:
                self.fail(f"File not readable: {path} — {e}")

    def test_003_namer_default_formato(self):
            """The default namer produces a name of the type 'label_P1'."""
            self._assert_heal_found_parts()
            generated = _split_files(self.result, self.out_dir)
            
            self.assertTrue(len(generated) > 0)
            nome = Path(generated[0]).stem
            
            self.assertRegex(nome, r".+_P\d+$",
                             f"Name '{nome}' does not follow the format 'label_P1'")

    def test_004_namer_custom(self):
        """A custom namer is respected."""
        self._assert_heal_found_parts()
        namer = lambda i, cluster: f"piece_{i + 1}"
        generated = _split_files(self.result, self.out_dir,
                          namer=namer)
        self.assertTrue(len(generated) > 0)
        self.assertEqual(Path(generated[0]).stem, "piece_1")

    def test_005_cluster_label_of_the_original_part_intact(self):
        """The part's label gives the file name; the original cluster does not change."""
        self._assert_heal_found_parts()
        before = self.result.clusters[0].label
        generated = _split_files(self.result, self.out_dir)
        self.assertEqual(Path(generated[0]).stem, f"{before}_P1")
        self.assertEqual(self.result.clusters[0].label, before)

    def test_006_min_area_discards_part_below_threshold(self):
        """Parts with area below min_area are discarded and produce a warning."""
        self._assert_heal_found_parts()
        # 200x100 = 20_000 mm²; very high threshold → discarded
        generated = _split_files(self.result, self.out_dir,
                          min_area=999_999)
        self.assertEqual(len(generated), 0, "Part below threshold not discarded")
        self.assertTrue(len(self.result.warnings) > 0,
                        "No warning emitted for a discarded cluster")

    def test_007_output_folder_creata_se_assente(self):
        """split() creates the output folder if it does not exist."""
        self._assert_heal_found_parts()
        new_dir = os.path.join(self.out_dir, "sub", "new")
        _split_files(self.result, new_dir)
        self.assertTrue(os.path.isdir(new_dir))


class TestUnitSplitFilters(unittest.TestCase):
    """Test the filters on entity types in split().

    The fixture adds a TEXT and a CIRCLE inside the rectangle's area, so the
    filters have something to act on.

    `exclude_types` is an option of `topo_dxf.to_dxf`, propagated by `split_to_files()`."""

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()

        def _add_texts(msp):
            msp.add_text("NOTA", dxfattribs={
                "insert": (50, 50), "height": 5, "layer": "0"
            })
            msp.add_circle((100, 50), 10, dxfattribs={"layer": "0"})

        self.doc, self.result = _make_via_heal(
            _rect(), extra_entities=[_add_texts]
        )
        self.assertTrue(
            len(self.result.clusters) > 0,
            "heal() found no parts — check the fixture"
        )

    def _child_msp(self, **split_kwargs):
        """Run split() and return the modelspace of the first child."""
        out_dir = tempfile.mkdtemp()
        generated = _split_files(self.result, out_dir, **split_kwargs)
        self.assertTrue(len(generated) > 0, "No file generated")
        return ezdxf.readfile(generated[0]).modelspace()

    def test_001_default_includes_text_and_circle(self):
        """Default (include_texts=True): TEXT and CIRCLE copied into the child."""
        out_msp = self._child_msp()
        self.assertEqual(len(list(out_msp.query("TEXT"))), 1,
                         "TEXT should be present")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE should be present")

    def test_002_include_texts_false_esclude_text(self):
        """include_texts=False: TEXT absent, CIRCLE present."""
        out_msp = self._child_msp(include_texts=False)
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                         "TEXT should not be present")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE should be present")

    def test_003_include_texts_false_excludes_all_types(self):
        """include_texts=False excludes all the types in TEXT_TYPES."""
        def _add_mtext(msp):
            msp.add_mtext("mtext", dxfattribs={
                "insert": (30, 30), "char_height": 5, "layer": "0"
            })

        doc, result = _make_via_heal(
            _rect(), extra_entities=[_add_mtext]
        )
        out_dir = tempfile.mkdtemp()
        generated = _split_files(result, out_dir,
                                 include_texts=False)
        self.assertTrue(len(generated) > 0)
        out_msp = ezdxf.readfile(generated[0]).modelspace()
        for ann_type in TEXT_TYPES:
            found = list(out_msp.query(ann_type))
            self.assertEqual(len(found), 0,
                             f"{ann_type} should not be present")

    def test_004_exclude_types_singolo(self):
        """exclude_types={'TEXT'}: TEXT absent, CIRCLE present."""
        out_msp = self._child_msp(exclude_types={"TEXT"})
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                         "TEXT should not be present")
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 1,
                         "CIRCLE should be present")

    def test_005_exclude_types_multipli(self):
        """exclude_types={'TEXT', 'CIRCLE'}: both absent."""
        out_msp = self._child_msp(exclude_types={"TEXT", "CIRCLE"})
        self.assertEqual(len(list(out_msp.query("TEXT"))), 0)
        self.assertEqual(len(list(out_msp.query("CIRCLE"))), 0)

    def test_006_split_writes_every_part(self):
        """Every part of split() is written from the model alone."""
        drawings = [topo_dxf.to_dxf(part) for part in topo.split(self.result)]
        self.assertGreater(len(drawings), 0)


class TestUnitSplitLayers(unittest.TestCase):
    """Verify layers and canonical colours in the child documents produced by split().

    NOTE: ALL_LAYERS must exist in topo_dxf.rules.layers as:
        ALL_LAYERS = {LAYER_OUTER: 3, LAYER_INNER: 2, ...} (topo's palette in ACI)"""

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        self.doc, self.result = _make_via_heal(_rect())
        self.assertTrue(
            len(self.result.clusters) > 0,
            "heal() found no parts — check the fixture"
        )
        self.generated = _split_files(self.result,
                                      self.out_dir)
        self.assertTrue(len(self.generated) > 0,
                        "split() generated no file")

    def test_001_all_layers_present(self):
        """All the standard topo layers are present in the child document."""
        from topo_dxf.layers import LAYER_OUTER, LAYER_INNER, TRASH_LAYER
        expected = {LAYER_OUTER, LAYER_INNER, TRASH_LAYER}
        for path in self.generated:
            child_doc = ezdxf.readfile(path)
            present = {l.dxf.name for l in child_doc.layers}
            for name in expected:
                self.assertIn(name, present,
                              f"{Path(path).name}: layer '{name}' missing")

    def test_002_colori_canonici(self):
        """Every topo layer has the canonical colour defined in layers.py."""
        from topo_dxf.layers import ALL_LAYERS
        for path in self.generated:
            child_doc = ezdxf.readfile(path)
            for layer_name, expected_color in ALL_LAYERS.items():
                layer = child_doc.layers.get(layer_name)
                self.assertIsNotNone(
                    layer, f"{Path(path).name}: layer '{layer_name}' not found"
                )
                self.assertEqual(
                    layer.dxf.color, expected_color,
                    f"{Path(path).name}: '{layer_name}' has colour "
                    f"{layer.dxf.color}, expected {expected_color}"
                )


# --- INTEGRATION TEST — full split_to_files() pipeline ---

class TestIntegrationPipeline(unittest.TestCase):
    """Test split_to_files() as a black box on files in examples/. It verifies
    observable invariants: files on disk, cluster count, layers. It does not go
    into the details of split() — those are in the unit tests."""

    def _run(self, dxf_name, label, **kwargs):
        out_dir = tempfile.mkdtemp()
        result = _split_to_files(
            topo_dxf.load_dxf(str(drawing(dxf_name))),
            output_folder=out_dir, label=label, **kwargs
        )
        return result, out_dir

    def test_001_two_parts_generates_two_files(self):
        """two_parts.dxf → the pipeline writes 2 child files."""
        _, out_dir = self._run("two_parts.dxf", "two_parts")
        files = list(Path(out_dir).glob("*.dxf"))
        self.assertEqual(len(files), 2,
                         f"Attesi 2 file, found {len(files)}: "
                         f"{[f.name for f in files]}")

    def test_002_child_files_readable(self):
        """The child files are valid DXFs."""
        _, out_dir = self._run("two_parts.dxf", "two_parts")
        for f in Path(out_dir).glob("*.dxf"):
            try:
                ezdxf.readfile(str(f))
            except Exception as e:
                self.fail(f"Child file not readable: {f.name} — {e}")

    def test_003_result_ha_parts(self):
        """split_to_files() returns a Result with clusters filled."""
        result, _ = self._run("two_parts.dxf", "two_parts")
        self.assertGreater(len(result.clusters), 0)

    def test_004_part_with_aperture(self):
        """pline_with_hole.dxf → the cluster has at least one inner/hole."""
        result, _ = self._run("pline_with_hole.dxf", "pline_with_hole")
        self.assertEqual(len(result.clusters), 1)
        self.assertGreater(len(result.clusters[0].inners), 0,
                           "No inner/hole found")

    def test_005_include_texts_false_propagato(self):
        """include_texts=False correctly propagated by the wrapper."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        msp.add_lwpolyline(_rect(), close=True, dxfattribs={"layer": "0"})
        msp.add_text("NOTA", dxfattribs={
            "insert": (50, 50), "height": 5, "layer": "0"
        })
        _split_to_files(topo_dxf.document_from_msp(msp), output_folder=out_dir, label="test",
                             include_texts=False)
        for f in Path(out_dir).glob("*.dxf"):
            out_msp = ezdxf.readfile(str(f)).modelspace()
            self.assertEqual(len(list(out_msp.query("TEXT"))), 0,
                             f"{f.name}: TEXT present with include_texts=False")

    def test_006_namer_custom_propagato(self):
        """A custom namer passed to split_to_files() is used."""
        out_dir = tempfile.mkdtemp()
        namer = lambda i, cluster: f"custom_{i + 1:02d}"
        _split_to_files(topo_dxf.load_dxf(str(drawing("two_parts.dxf"))), output_folder=out_dir,
                             label="two_parts", namer=namer)
        names = {f.stem for f in Path(out_dir).glob("*.dxf")}
        self.assertIn("custom_01", names,
                      f"Custom name not found among: {names}")

    def test_007_empty_msp_generates_no_file(self):
        """empty msp → no file generated."""
        out_dir = tempfile.mkdtemp()
        doc = ezdxf.new("R2010")
        _split_to_files(topo_dxf.document_from_msp(doc.modelspace()), output_folder=out_dir,
                             label="empty")
        files = list(Path(out_dir).glob("*.dxf"))
        self.assertEqual(len(files), 0,
                         f"Files generated from empty msp: {[f.name for f in files]}")


class TestIntegrationContours(unittest.TestCase):
    """Verify that the structural contours in the child files are correct: closed
    LWPOLYLINEs, CIRCLE and SPLINE exported correctly."""

    def _children(self, dxf_name, label, **kwargs):
        out_dir = tempfile.mkdtemp()
        _split_to_files(topo_dxf.load_dxf(str(drawing(dxf_name))), output_folder=out_dir,
                             label=label, **kwargs)
        return _read_children(out_dir)

    def _spline_signature(self, spline):
        # geometry only: flags, tolerances, fit points and tangents of the source file
        # are not part of the curve
        cps = tuple((round(float(p[0]), 6), round(float(p[1]), 6), round(float(p[2]), 6))
                    for p in spline.control_points)
        knots = tuple(round(float(k), 9) for k in spline.knots)
        weights = tuple(round(float(w), 9) for w in spline.weights)
        return (int(spline.dxf.degree), cps, knots, weights)

    def test_001_lwpolyline_outer_closed(self):
        """LWPOLYLINE on OuterContour in the children is closed=True."""
        from topo_dxf.layers import LAYER_OUTER
        children = self._children("two_parts.dxf", "two_parts")
        self.assertGreater(len(children), 0)
        for fname, msp in children.items():
            for e in msp.query("LWPOLYLINE"):
                if e.dxf.layer == LAYER_OUTER:
                    self.assertTrue(e.closed,
                                    f"{fname}: LWPOLYLINE su {LAYER_OUTER} "
                                    f"is not closed")

    def test_002_lwpolyline_inner_closed(self):
        """LWPOLYLINE on InnerContour/Hole in the children is closed=True."""
        from topo_dxf.layers import LAYER_INNER
        children = self._children("pline_with_hole.dxf", "pline_with_hole")
        for fname, msp in children.items():
            for e in msp.query("LWPOLYLINE"):
                if e.dxf.layer in (LAYER_INNER,):
                    self.assertTrue(e.closed,
                                    f"{fname}: LWPOLYLINE su {e.dxf.layer} "
                                    f"is not closed")

    def test_003_circle_outer_esportato(self):
        """CIRCLE on OuterContour is exported to the child file."""
        from topo_dxf.layers import LAYER_OUTER
        children = self._children("cerchi_ciambella.dxf", "cerchi_ciambella")
        self.assertGreater(len(children), 0,
                           "No child file from cerchi_ciambella.dxf")
        for fname, msp in children.items():
            outer_circles = [e for e in msp.query("CIRCLE")
                             if e.dxf.layer == LAYER_OUTER]
            self.assertEqual(len(outer_circles), 1,
                             f"{fname}: expected 1 CIRCLE on {LAYER_OUTER}, "
                             f"trovati {len(outer_circles)}")

    def test_004_spline_outer_esportato(self):
        """File with SPLINE: at least one child contains a structural SPLINE on OuterContour."""
        from topo_dxf.layers import LAYER_OUTER
        children = self._children("intricato_doppio.dxf", "intricato_doppio")
        figli_con_outer = [
            fname for fname, msp in children.items()
            if any(e.dxf.layer == LAYER_OUTER
                   for e in msp.query("SPLINE LINE ARC"))
        ]
        self.assertGreater(len(figli_con_outer), 0,
                           "No child has entities on OuterContour "
                           "for a file with SPLINE")

    def test_006_spline_parametri_preservati(self):
        """The SPLINEs written in the children preserve the source's key parameters."""
        from topo_dxf.layers import LAYER_OUTER
        src_doc = ezdxf.readfile(str(drawing("intricato_doppio.dxf")))
        src_splines = list(src_doc.modelspace().query("SPLINE"))
        self.assertGreater(len(src_splines), 0, "The source fixture contains no SPLINE")

        src_signatures = {self._spline_signature(s) for s in src_splines}

        children = self._children("intricato_doppio.dxf", "intricato_doppio")
        out_outer_splines = []
        for _, msp in children.items():
            out_outer_splines.extend([e for e in msp.query("SPLINE") if e.dxf.layer == LAYER_OUTER])

        self.assertGreater(len(out_outer_splines), 0,
                           "No SPLINE on OuterContour found in the children")

        for out_spline in out_outer_splines:
            sig = self._spline_signature(out_spline)
            self.assertIn(sig, src_signatures,
                          "Child SPLINE does not match the source's parameters")

    def test_005_regression_closed_lwpolyline_all_the_examples(self):
        """Regression: for every file in tests/data/, every structural LWPOLYLINE in the
        children is closed=True, on the layers without SPLINE/ELLIPSE: a mixed contour
        is written in open pieces that close together (`write_segments`)."""
        from topo_dxf.layers import LAYER_OUTER, LAYER_INNER
        structural = {LAYER_OUTER, LAYER_INNER}
        # the drawings that were in the root are now in golden_faces/ (one name, one copy)
        sources = {p.name: p for d in (EXAMPLES_DIR / "golden_faces", EXAMPLES_DIR) for p in Path(d).glob("*.dxf")}
        for src in sorted(sources.values()):
            if src.stem.endswith("_healed"):
                continue
            out_dir = tempfile.mkdtemp()
            with self.subTest(src=src.name):
                _split_to_files(topo_dxf.load_dxf(str(src)), output_folder=out_dir, label=src.stem)
                for child in Path(out_dir).glob("*.dxf"):
                    msp = ezdxf.readfile(str(child)).modelspace()
                    mixed = {e.dxf.layer for e in msp.query("SPLINE ELLIPSE")}
                    for e in msp.query("LWPOLYLINE"):
                        if e.dxf.layer in structural - mixed:
                            self.assertTrue(
                                e.closed,
                                f"{child.name}: LWPOLYLINE su {e.dxf.layer} "
                                f"not closed (source: {src.name})"
                            )


class TestIntegrationLayers(unittest.TestCase):
    """Verify layers and canonical colours in the files produced by the full
    pipeline. Separate from TestUnitSplitLayers because here it goes through
    heal() on a real file."""

    def setUp(self):
        self.out_dir = tempfile.mkdtemp()
        _split_to_files(topo_dxf.load_dxf(str(drawing("two_parts.dxf"))),
                             output_folder=self.out_dir, label="test")
        self.files = list(Path(self.out_dir).glob("*.dxf"))
        self.assertTrue(len(self.files) > 0,
                        "setUp: no file generated from two_parts.dxf")

    def test_001_outer_layer_colore_canonico(self):
        """LAYER_OUTER has topo's palette green in every child file."""
        from topo_dxf.layers import LAYER_OUTER
        from topo_dxf.layers import color_for_role
        COLOR_OUTER = color_for_role("outer")
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            layer = child_doc.layers.get(LAYER_OUTER)
            self.assertIsNotNone(layer, f"{f.name}: LAYER_OUTER missing")
            self.assertEqual(layer.dxf.color, COLOR_OUTER,
                             f"{f.name}: LAYER_OUTER has colour "
                             f"{layer.dxf.color}, expected {COLOR_OUTER}")

    def test_002_all_topo_layers_present(self):
        """All the standard topo layers are present in every child file."""
        from topo_dxf.layers import LAYER_OUTER, LAYER_INNER, TRASH_LAYER
        expected = {LAYER_OUTER, LAYER_INNER, TRASH_LAYER}
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            present = {l.dxf.name for l in child_doc.layers}
            for name in expected:
                self.assertIn(name, present,
                              f"{f.name}: layer '{name}' missing")

    def test_003_all_canonical_colours(self):
        """Every topo layer has the canonical colour defined in layers.py."""
        from topo_dxf.layers import ALL_LAYERS
        for f in self.files:
            child_doc = ezdxf.readfile(str(f))
            for layer_name, expected_color in ALL_LAYERS.items():
                layer = child_doc.layers.get(layer_name)
                self.assertIsNotNone(
                    layer, f"{f.name}: layer '{layer_name}' not found"
                )
                self.assertEqual(
                    layer.dxf.color, expected_color,
                    f"{f.name}: '{layer_name}' has colour "
                    f"{layer.dxf.color}, expected {expected_color}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)