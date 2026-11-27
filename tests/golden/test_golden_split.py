

"""
tests/golden/test_golden_split.py
-------------------------------
Geometric regression test for the files produced by splitting.

For every golden in tests/data/golden_split/golden/:
  1. Reprocess the parent DXF (heal → split) in a temporary folder —
     no process reading: a hole is an inner contour.
  2. Compare area, perimeters, WKT geometry and layer of every part against
     the saved golden. Hole layers and summary: test_golden_process.py.

Tolerances:
    TOL_AREA      = 0.1  mm²
    TOL_PERIMETER = 0.5  mm
    TOL_SHAPE     = 1.0  mm²  (symmetric difference Shapely)

Generate the golden first with:
    python generate_golden_split.py

Run the tests with:
    python -m pytest tests/test_golden_split.py -v
    or
    python tests/test_golden_split.py
"""

import atexit
import json
import shutil
import tempfile
from collections import Counter
import unittest
from functools import lru_cache
from pathlib import Path

import ezdxf
from shapely import wkt as shapely_wkt


import topo
import topo_dxf
from topo_dxf.layers import role_to_dxf_layer
from topo import to_shapely
from tests.paths import DATA, drawing


MULTIPLI_DIR = DATA / "golden_split"
GOLDEN_DIR   = MULTIPLI_DIR / "golden"

TOL_AREA      = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE     = 1.0
MAX_GAP = 0.5    # the golden faces/split are read with this

_PARENT_PIPELINE_CACHE: dict[tuple[Path, float], dict] = {}


def _match_inner_polygons(actual_wkts: list[str], expected_wkts: list[str]) -> list[tuple[int, int, float]]:
    """Return a one-to-one (greedy) matching between current/expected inners
    minimizing the geometric diff (area symmetric_difference)."""
    if len(actual_wkts) != len(expected_wkts):
        raise ValueError(
            f"inner count mismatch: actual={len(actual_wkts)} expected={len(expected_wkts)}"
        )

    actual_polys = [shapely_wkt.loads(w) for w in actual_wkts]
    expected_polys = [shapely_wkt.loads(w) for w in expected_wkts]

    candidates = []
    for ai, a_poly in enumerate(actual_polys):
        for ei, e_poly in enumerate(expected_polys):
            diff = a_poly.symmetric_difference(e_poly).area
            candidates.append((diff, ai, ei))

    candidates.sort(key=lambda t: t[0])

    matched_actual = set()
    matched_expected = set()
    matches: list[tuple[int, int, float]] = []
    for diff, ai, ei in candidates:
        if ai in matched_actual or ei in matched_expected:
            continue
        matched_actual.add(ai)
        matched_expected.add(ei)
        matches.append((ai, ei, diff))
        if len(matches) == len(actual_wkts):
            break

    if len(matches) != len(actual_wkts):
        raise ValueError("cannot build a complete matching between inners")

    return matches


@lru_cache(maxsize=None)
def _load_golden_entries() -> tuple[tuple[tuple[str, dict], ...], ...]:
    if not GOLDEN_DIR.exists():
        return ()
    entries = []
    for golden_path in sorted(GOLDEN_DIR.glob("*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        entries.append((golden_path.stem, golden))
    return tuple(entries)


def _load_config(dxf_path: Path) -> dict:
    config_path = MULTIPLI_DIR / "config" / f"{dxf_path.stem}.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def _get_parent_split_cache(parent_path: Path, max_gap: float) -> dict:
    cache_key = (parent_path.resolve(), float(max_gap))
    cached = _PARENT_PIPELINE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    output_folder = Path(tempfile.mkdtemp(prefix=f"golden_split_{parent_path.stem}_"))
    atexit.register(shutil.rmtree, output_folder, ignore_errors=True)

    doc = topo_dxf.load_dxf(parent_path, explode_inserts=True)
    result = topo.heal(doc, max_gap=max_gap).faces()

    if result.is_valid and result.clusters:
        output_folder.mkdir(parents=True, exist_ok=True)
        for i, part in enumerate(topo.split(result).pieces):
            topo_dxf.to_dxf(part).saveas(str(output_folder / f"{i:03d}.dxf"))

    part_payloads = []
    for cluster in result.clusters if result.is_valid and result.clusters else []:
        inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)
        part_payloads.append({
            "area": cluster.area,
            "inners_count": len(inners),
            "outer_perimeter": to_shapely(cluster.outer).exterior.length,
            "inner_perimeter": sum(to_shapely(i).exterior.length for i in inners),
            "outer_wkt": to_shapely(cluster.outer).wkt,
            "inners_wkt": [to_shapely(i).wkt for i in inners],
            "outer_role": cluster.outer.role,
            "inner_roles": [i.role for i in inners],
        })

    cached_entry = {
        "output_folder": output_folder,
        "children": sorted(output_folder.glob("*.dxf")),
        "clusters": part_payloads,
    }
    _PARENT_PIPELINE_CACHE[cache_key] = cached_entry
    return cached_entry


class _SplitContext:
    """Context manager that runs the pipeline on the parent once per parent+max_gap
    and makes the output folder available for the whole `with` block."""

    def __init__(self, parent_path: Path, max_gap: float):
        self._parent_path = parent_path
        self._max_gap = max_gap
        self._cache_entry = None

    def __enter__(self) -> Path:
        self._cache_entry = _get_parent_split_cache(self._parent_path, self._max_gap)
        return self._cache_entry["output_folder"]

    def __exit__(self, *_):
        return False


def _load_golden_files():
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


class TestGoldenSplit(unittest.TestCase):
    pass


def _make_split_test(golden_path: Path):
    def test_method(self):
        golden      = json.loads(golden_path.read_text(encoding="utf-8"))
        child_name = golden.get("source_file", f"{golden['parent_file']}__part{golden['part_index']}")
        parent_name = golden["parent_file"]
        parent_path = drawing(parent_name)

        if not parent_path.exists():
            self.skipTest(f"Parent DXF not found: {parent_path}")

        config    = _load_config(parent_path)
        max_gap = config.get("max_gap", MAX_GAP)

        part_index = golden["part_index"]

        # Find the child by index, not by name: different parents produce children
        # with identical names (000_.dxf, 001_.dxf...), so the name is not a reliable
        # key. The index is the source of truth.
        with _SplitContext(parent_path, max_gap) as output_folder:
            children = sorted(output_folder.glob("*.dxf"))

            if part_index >= len(children):
                self.fail(
                    f"part_index={part_index} out of range: "
                    f"the split produced only {len(children)} children.\n"
                    f"Generated children: {[f.name for f in children]}"
                )

            part_payload = _PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(max_gap))]["clusters"][part_index]

        self.assertIsNotNone(
            part_payload,
            f"{child_name}: no part available for the requested child"
        )

        self.assertEqual(
            len(_PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(max_gap))]["clusters"]),
            len(children),
            f"{child_name}: the number of parts in cache ({len(_PARENT_PIPELINE_CACHE[(parent_path.resolve(), float(max_gap))]['clusters'])}) does not match the generated children ({len(children)})"
        )

        label = child_name

        # --- Area ---
        actual_area = round(part_payload["area"], 4)
        self.assertAlmostEqual(
            actual_area,
            golden["area_mm2"],
            delta=TOL_AREA,
            msg=f"{label}: area {actual_area} != attesa {golden['area_mm2']} (tol={TOL_AREA})",
        )

        # --- Inner contours ---
        self.assertEqual(
            part_payload["inners_count"],
            golden["inners_count"],
            msg=f"{label}: inners_count {part_payload['inners_count']} != atteso {golden['inners_count']}",
        )

        # --- Outer perimeter ---
        actual_outer_p = round(part_payload["outer_perimeter"], 4)
        self.assertAlmostEqual(
            actual_outer_p,
            golden["outer_perimeter_mm"],
            delta=TOL_PERIMETER,
            msg=f"{label}: outer_perimeter {actual_outer_p} != atteso {golden['outer_perimeter_mm']}",
        )

        # --- Inner perimeter ---
        actual_inner_p = round(
            part_payload["inner_perimeter"],
            4,
        )
        self.assertAlmostEqual(
            actual_inner_p,
            golden["inner_perimeter_mm"],
            delta=TOL_PERIMETER,
            msg=f"{label}: inner_perimeter {actual_inner_p} != atteso {golden['inner_perimeter_mm']}",
        )

        # --- Outer geometry (WKT) ---
        expected_outer = shapely_wkt.loads(golden["outer_wkt"])
        diff = shapely_wkt.loads(part_payload["outer_wkt"]).symmetric_difference(expected_outer).area
        self.assertLess(
            diff, TOL_SHAPE,
            msg=f"{label}: geometria outer cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})",
        )

        # --- Inners geometry (WKT) ---
        self.assertEqual(
            len(part_payload["inners_wkt"]),
            len(golden["inners_wkt"]),
            msg=(
                f"{label}: numero inner diverso "
                f"(actual={len(part_payload['inners_wkt'])}, expected={len(golden['inners_wkt'])})"
            ),
        )

        inner_matches = _match_inner_polygons(part_payload["inners_wkt"], golden["inners_wkt"])
        for actual_idx, expected_idx, diff in inner_matches:
            self.assertLess(
                diff, TOL_SHAPE,
                msg=(
                    f"{label} inner(actual={actual_idx}, expected={expected_idx}): "
                    f"geometria cambiata (diff={diff:.4f} mm², tol={TOL_SHAPE})"
                ),
            )

        # --- Layers ---
        if "outer_layer" in golden:
            self.assertEqual(
                role_to_dxf_layer(part_payload["outer_role"]),
                golden["outer_layer"],
                msg=f"{label}: outer_layer '{role_to_dxf_layer(part_payload['outer_role'])}' != atteso '{golden['outer_layer']}'",
            )

        if "inners_layers" in golden:
            actual_layers = [role_to_dxf_layer(h_role) for h_role in part_payload["inner_roles"]]
            self.assertEqual(
                Counter(actual_layers),
                Counter(golden["inners_layers"]),
                msg=f"{label}: inners_layers multiset {actual_layers} != attesi {golden['inners_layers']}",
            )

    test_method.__name__ = f"test_{golden_path.stem}"
    test_method.__doc__  = f"Split golden: {golden_path.name}"
    return test_method


# Dynamically generate a test for every golden file
for _golden_path in _load_golden_files():
    setattr(TestGoldenSplit, f"test_{_golden_path.stem}", _make_split_test(_golden_path))


class TestGoldenSplitSetup(unittest.TestCase):

    def test_001_golden_dir_exists(self):
        """The golden_split/golden/ folder exists."""
        self.assertTrue(
            GOLDEN_DIR.exists(),
            f"Golden folder not found: {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden_split.py"
        )

    def test_002_golden_not_empty(self):
        """The golden_split/golden/ folder contains at least 1 golden file."""
        files = list(GOLDEN_DIR.glob("*.json")) if GOLDEN_DIR.exists() else []
        self.assertGreater(
            len(files), 0,
            f"No golden file found in {GOLDEN_DIR}\n"
            f"Genera i golden file con: python generate_golden_split.py"
        )
        print(f"\n  Golden split trovati: {len(files)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)