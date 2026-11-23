"""
test_golden_outlines.py
-----------------------
Regression on `outlines()`: for every sheet of views, the clusters — outer
contour box and number of inner contours — and the open lines outside every
cluster.

Drawings in `tests/data/golden_outlines/` (`anch_NN`, `regr_NN`): anonymized
copies of snapdraw's sheets with only the geometry `outlines()` reads in the
framer — frame, title block and construction lines removed by snapdraw, the
file written by topo (layer `geometry`). topo does not know what a frame is:
it receives the sheet already cleaned. Clusters judged right by Federico on
the islands-scale review page (5 October). Golden in `json/` alongside;
without the drawings the test skips.

Golden to be regenerated only after checking by eye that the clusters are
right, never to make a test pass:

    python -m tests.golden.test_golden_outlines --generate
"""

import json
import sys
import unittest
from pathlib import Path



from tests.readings import outline_reading
from topo import to_shapely
from tests.paths import DATA, PROJECT_ROOT

MAX_GAP = 0.5    # snapdraw's (SHEET_MAX_GAP)
TOL = 0.01       # mm

SOURCE_DIR = DATA / "golden_outlines"
GOLDEN_DIR = SOURCE_DIR / "json"


def snapshot(dxf_path: Path, max_gap: float = MAX_GAP, name: str = None, area: bool = False) -> dict:
    """The clusters in box order (two clusters of equal area do not swap the golden).
    `area`: also the exact area of each piece, which sees an outer changed inside the same box."""
    _, result = outline_reading(dxf_path, max_gap)
    clusters = sorted([round(float(v), 3) for v in to_shapely(c.outer).bounds] + [len(c.inners), round(c.area, 3)]
                      for c in result.clusters)
    return {"source_file": name or dxf_path.name,
            "clusters": [dict({"bbox": i[:4], "inners": i[4]}, **({"area": i[5]} if area else {}))
                         for i in clusters],
            "open_outside": sum(1 for t in result.loose if getattr(t, "cluster_ref", None) is None)}


# Sheets of views and multiple parts judged right by Federico on 20 November,
# read with max_gap 0.05 (the one that counts, not snapdraw's 0.5). The drawings
# are not anonymized: they stay in tests/examples (outside git) and the map
# og_NN -> path is there; in git only the golden, with the name og_NN. Without
# the map or the drawing the test skips.
MAX_GAP_SHEETS = 0.05
SHEETS_MAP = PROJECT_ROOT / "tests" / "examples" / "golden_outlines_max_gap.json"
SHEETS_GOLDEN_DIR = DATA / "golden_outlines_max_gap"


def _sheets() -> dict:
    """{og_NN: path of the drawing}; empty without the map."""
    if not SHEETS_MAP.exists():
        return {}
    return {k: PROJECT_ROOT / v for k, v in json.loads(SHEETS_MAP.read_text(encoding="utf-8")).items()}


class TestGoldenOutlines(unittest.TestCase):

    def _compare(self, expected, actual, where):
        if isinstance(expected, dict):
            self.assertEqual(sorted(expected), sorted(actual), where)
            for k in expected:
                self._compare(expected[k], actual[k], f"{where}.{k}")
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), f"{where}: different lengths")
            for i, (e, a) in enumerate(zip(expected, actual)):
                self._compare(e, a, f"{where}[{i}]")
        elif isinstance(expected, float):
            self.assertAlmostEqual(expected, actual, delta=TOL, msg=where)
        else:
            self.assertEqual(expected, actual, where)


def _make_test(dxf: Path, golden: Path):
    def test(self):
        self._compare(json.loads(golden.read_text(encoding="utf-8")), snapshot(dxf), dxf.stem)
    return test


# golden frozen on purpose: they were moved on purpose; the doubts are closed
# and they are regenerated all together, looking at the DXFs first; then this
# list empties
KNOWN_STALE: set = set()

for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    _golden = GOLDEN_DIR / f"{_dxf.stem}.json"
    if _golden.exists():
        _test = _make_test(_dxf, _golden)
        if _dxf.stem in KNOWN_STALE:
            _test = unittest.expectedFailure(_test)
        setattr(TestGoldenOutlines, f"test_{_dxf.stem}", _test)


def _make_sheet_test(name: str, golden: Path):
    def test(self):
        dxf = _sheets().get(name)
        if dxf is None or not dxf.exists():
            self.skipTest(f"{name}: drawing not present (map {SHEETS_MAP.name})")
        expected = json.loads(golden.read_text(encoding="utf-8"))
        self._compare(expected, snapshot(dxf, MAX_GAP_SHEETS, name, area=True), name)
    return test


for _golden in sorted(SHEETS_GOLDEN_DIR.glob("og_*.json")):
    setattr(TestGoldenOutlines, f"test_max_gap_{_golden.stem}", _make_sheet_test(_golden.stem, _golden))


def generate():
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for dxf in sorted(SOURCE_DIR.glob("*.dxf")):
        snap = snapshot(dxf)
        (GOLDEN_DIR / f"{dxf.stem}.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"  OK: {dxf.name} — {len(snap['clusters'])} cluster, {snap['open_outside']} open lines outside")


def generate_sheets():
    """The golden of the sheets with max_gap: only after Federico has looked at them."""
    SHEETS_GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, dxf in sorted(_sheets().items()):
        snap = snapshot(dxf, MAX_GAP_SHEETS, name, area=True)
        (SHEETS_GOLDEN_DIR / f"{name}.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"  OK: {name} — {len(snap['clusters'])} cluster, {snap['open_outside']} open lines outside")


if __name__ == "__main__":
    if "--generate-sheets" in sys.argv:
        generate_sheets()
    elif "--generate" in sys.argv:
        generate()
    else:
        unittest.main()
