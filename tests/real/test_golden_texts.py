"""
test_golden_texts.py
--------------------
Regressione sulla lettura dei testi: confronta `topo_dxf.load_dxf(...).texts`
(`Text`, D138) con i golden in tests/data/golden/texts/.

Golden generati da tests/generate_golden_texts.py — da rigenerare solo
dopo aver verificato a mano che la lettura è giusta, mai per far passare un
test. I golden di prima di D138 (Note/Dimension/Leader) sono stati convertiti
chiave per chiave, stessi valori: `dim_type` → `measure_is_angle`,
`measured_value` → `measure`, `display_text` → `text`, `vertices` → `pointer`.

Un test per fixture, generato dalla fabbrica in fondo al file.
"""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo.tools.anchor import anchor_texts

EXAMPLES_DIR = project_root / "tests" / "data"
GOLDEN_DIR = EXAMPLES_DIR / "golden" / "texts"
_SOURCE_DIRS = [EXAMPLES_DIR, EXAMPLES_DIR / "golden"]


def _find_source(name: str):
    for d in _SOURCE_DIRS:
        p = d / name
        if p.exists():
            return p
    return None


TOL_POS = 0.05      # mm — tolleranza sulla posizione d'ancoraggio
TOL_VALUE = 0.01    # mm — tolleranza sul valore misurato


def _golden_files():
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


def _rendered_counts(r) -> dict:
    return {"strokes": len(r.strokes), "fills": len(r.fills), "texts": len(r.texts)}


def text_dict(t) -> dict:
    """Il golden di un `Text`: altezza e rotazione solo per una stringa senza
    immagine (con un'immagine il writer riscrive quella)."""
    d = {
        "source_kind": t.source_kind,
        "position": [round(t.position[0], 3), round(t.position[1], 3)],
        "text": t.text,
        "cluster_ref": t.cluster_ref,
    }
    if t.rendered.is_empty():
        d["height"] = round(t.height, 3)
        d["rotation"] = round(t.rotation, 3)
    d["measure"] = None if t.measure is None else round(t.measure, 4)
    d["measure_is_angle"] = t.measure_is_angle
    d["pointer"] = len(t.pointer)
    d["rendered"] = _rendered_counts(t.rendered)
    return d


def sort_key(entry: dict):
    return (entry["position"][0], entry["position"][1], entry["source_kind"], entry["text"])


def _make_test(path: Path):
    def test(self):
        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = _find_source(golden["source_file"])
        if dxf_path is None:
            self.skipTest(golden["source_file"])
        doc = topo_dxf.load_dxf(
            dxf_path, explode_inserts=True, flatten_z=True, verbose=False
        )
        result = topo.heal(doc)
        anchor_texts(result)
        texts = result.texts if result.texts else doc.texts
        actual = sorted((text_dict(t) for t in texts), key=sort_key)
        expected = golden["texts"]

        if "cluster_count" in golden:
            self.assertEqual(
                result.cluster_count, golden["cluster_count"],
                msg=f"{golden['source_file']}: numero parti",
            )
        self.assertEqual(len(actual), golden["text_count"],
                         msg=f"{golden['source_file']}: numero testi")
        self.assertEqual(
            dict(Counter(e["source_kind"] for e in actual)), golden["by_source_kind"],
            msg=f"{golden['source_file']}: conteggio per source_kind",
        )
        for i, (act, exp) in enumerate(zip(actual, expected)):
            ctx = f"{golden['source_file']} testo[{i}]"
            self.assertEqual(act.keys(), exp.keys(), msg=f"{ctx}: campi")
            for key in ("source_kind", "text", "cluster_ref", "measure_is_angle", "pointer", "rendered"):
                self.assertEqual(act[key], exp[key], msg=f"{ctx}: {key}")
            for key in ("height", "rotation"):
                if key in exp:
                    self.assertAlmostEqual(act[key], exp[key], delta=TOL_VALUE, msg=f"{ctx}: {key}")
            self.assertAlmostEqual(act["position"][0], exp["position"][0], delta=TOL_POS, msg=f"{ctx}: x")
            self.assertAlmostEqual(act["position"][1], exp["position"][1], delta=TOL_POS, msg=f"{ctx}: y")
            if exp["measure"] is None:
                self.assertIsNone(act["measure"], msg=f"{ctx}: measure")
            else:
                self.assertAlmostEqual(act["measure"], exp["measure"], delta=TOL_VALUE, msg=f"{ctx}: measure")

    return test


class TestGoldenTexts(unittest.TestCase):
    pass


for _golden in _golden_files():
    setattr(TestGoldenTexts, f"test_{_golden.stem}", _make_test(_golden))


class TestGoldenTextsSetup(unittest.TestCase):
    def test_golden_dir_populated(self):
        self.assertGreater(len(_golden_files()), 0, "nessun golden dei testi")


if __name__ == "__main__":
    unittest.main()
