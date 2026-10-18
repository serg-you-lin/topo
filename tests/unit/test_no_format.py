"""
tests/unit/test_no_format.py
----------------------------
topo non ha un formato (MAP.md D123, D129): si importa e lavora senza ezdxf
né PyMuPDF, e `topo.split` divide un Result in un Result per parte senza
scrivere niente. Il confine sugli import lo controlla `test_index.py`; qui si
prova che regge anche a runtime.
"""

import subprocess
import sys
import textwrap
import unittest

import ezdxf

import topo
import topo_dxf

# Un processo nuovo in cui ezdxf, fitz e pymupdf non si possono importare
_BLOCKED = textwrap.dedent("""
    import sys

    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in ("ezdxf", "fitz", "pymupdf"):
                raise ImportError("bloccato: " + name)

    sys.meta_path.insert(0, _Block())
""")


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", _BLOCKED + textwrap.dedent(code)],
                          capture_output=True, text=True)


def _two_squares_doc():
    """Due quadrati 100×100 a 300 mm di distanza, un testo e un segmento
    sciolto vicino al secondo."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for x0 in (0, 300):
        msp.add_lwpolyline([(x0, 0), (x0 + 100, 0), (x0 + 100, 100), (x0, 100)], close=True)
    msp.add_text("A", dxfattribs={"insert": (50, 50), "height": 5})
    msp.add_text("B", dxfattribs={"insert": (420, 50), "height": 5})
    msp.add_line((410, 0), (410, 30))          # trash, vicino al secondo
    return topo_dxf.document_from_msp(msp)


class TestTopoWithoutFormats(unittest.TestCase):

    def test_import_and_heal_without_ezdxf(self):
        out = _run("""
            import topo
            doc = topo.load_segments([
                topo.primitives.LineSeg((0, 0), (10, 0)),
                topo.primitives.LineSeg((10, 0), (10, 10)),
                topo.primitives.LineSeg((10, 10), (0, 10)),
                topo.primitives.LineSeg((0, 10), (0, 0)),
            ])
            result = topo.heal(doc)
            parts = topo.split(result, min_area=0)
            print(len(parts), "ezdxf" in sys.modules)
        """)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.split(), ["1", "False"])

    def test_adapter_says_which_extra(self):
        out = _run("import topo_dxf")
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("g-topo[dxf]", out.stderr)


class TestSplitIsModel(unittest.TestCase):

    def setUp(self):
        self.doc = _two_squares_doc()
        self.result = topo.heal(self.doc)
        self.assertEqual(self.result.cluster_count, 2)

    def test_one_result_per_part(self):
        parts = topo.split(self.result, namer=lambda i, c: f"P{i}")
        self.assertEqual([p.clusters[0].label for p in parts], ["P0", "P1"])
        for part in parts:
            self.assertIsInstance(part, topo.Result)
            self.assertEqual(part.cluster_count, 1)

    def test_trash_and_annotations_go_to_one_part(self):
        # ogni testo alla parte che lo contiene o alla più vicina, il trash
        # alla più vicina: niente duplicato, niente perso
        parts = topo.split(self.result)
        texts = [[a.text for a in p.annotations] for p in parts]
        self.assertEqual(texts, [["A"], ["B"]])
        self.assertEqual([len(p.trash_entities) for p in parts],
                         [0, len(self.result.trash_entities)])

    def test_min_area_drops_with_warning(self):
        parts = topo.split(self.result, min_area=20000)
        self.assertEqual(parts, [])
        self.assertTrue(any("sotto soglia" in w for w in self.result.warnings))

    def test_each_part_writes_to_dxf(self):
        for part in topo.split(self.result):
            msp = topo_dxf.to_dxf(part, self.doc, exclude_types={"TEXT"}).modelspace()
            self.assertEqual(len(msp.query("TEXT")), 0)
            self.assertEqual(len(msp.query("LWPOLYLINE[layer=='OuterContour']")), 1)


if __name__ == "__main__":
    unittest.main()
