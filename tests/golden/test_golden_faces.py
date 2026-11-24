"""
tests/golden/test_golden_faces.py
-------------------------
Geometric regression test against the golden files: only heal(), no process
reading — a hole is an inner contour, a bend a non-structural edge. Holes,
bends and engravings: test_golden_process.py.

Source DXF: tests/data/golden_faces/
Golden JSON:  tests/data/golden_faces/json/
"""

import unittest
import json

from shapely import wkt as shapely_wkt


import topo
import topo_dxf
from topo_dxf.layers import role_to_dxf_layer
from topo import to_shapely
from tests.paths import DATA


EXAMPLES_DIR = DATA
GOLDEN_DXF_DIR = EXAMPLES_DIR / "golden_faces"
GOLDEN_JSON_DIR = GOLDEN_DXF_DIR / "json"

MAX_GAP = 0.5    # the golden faces/split are read with this

TOL_AREA = 0.1
TOL_PERIMETER = 0.5
TOL_SHAPE = 1.0

# Only for TestGoldenFacesWriteBack: DXF write-back -> reload introduces
# sub-mm rounding noise independent of topo. TOL_AREA/TOL_SHAPE stay tight for
# TestGoldenFaces (live output vs saved golden) -- here the comparison is output
# vs itself after a write/read round, a different and more permissive noise by nature.
TOL_AREA_ROUNDTRIP = 20.0
TOL_SHAPE_ROUNDTRIP = 30.0


GLOBAL_NAME_ROLES = {
    "MARK": "engrave",
    "Signature": "engrave",
}

# The roles a golden assigns at load (MARK/Signature → engrave, plus those of
# its config): the round-trip re-reads them from the layer to_dxf wrote them on.
def _roundtrip_name_roles(name_roles: dict) -> dict:
    return {role_to_dxf_layer(role): role for role in set(name_roles.values())}

# Mixed BSplineSeg + lines/arcs contours: materialized as native SPLINEs + open
# LWPOLYLINEs with coincident endpoints (never discretized). The round-trip
# sews them via the graph — no known loss at the moment.
ROUNDTRIP_KNOWN_LOSSY = set()


def _load_config(dxf_path):
    path = EXAMPLES_DIR / "config" / f"{dxf_path.stem}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_golden_files():
    if not GOLDEN_JSON_DIR.exists():
        return []
    return sorted(GOLDEN_JSON_DIR.glob("*.json"))


def _make_test(path):

    def _assert_shapes_match_unordered(self, actual_shapes, expected_wkts, label, kind):
        expected_polys = [shapely_wkt.loads(wkt) for wkt in expected_wkts]
        unmatched = list(range(len(expected_polys)))

        for idx, actual_shape in enumerate(actual_shapes):
            best_idx = None
            best_score = None
            for expected_idx in unmatched:
                score = to_shapely(actual_shape).symmetric_difference(
                    expected_polys[expected_idx]
                ).area
                if best_score is None or score < best_score:
                    best_idx = expected_idx
                    best_score = score

            self.assertIsNotNone(best_idx, msg=f"{label} {kind}[{idx}] match")
            self.assertLess(
                best_score,
                TOL_SHAPE,
                msg=f"{label} {kind}[{idx}] shape",
            )
            unmatched.remove(best_idx)

    def test(self):

        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = GOLDEN_DXF_DIR / golden["source_file"]

        if not dxf_path.exists():
            self.skipTest(str(dxf_path))

        config = _load_config(dxf_path)
        name_roles = {
            **GLOBAL_NAME_ROLES,
            **config.get("name_roles", {})
        }

        result = topo.heal(
            topo_dxf.load_dxf(
                str(dxf_path),
                upgrade=True,
                explode_inserts=True,
                flatten_z=True,
                role_rules=topo.name_rules(name_roles),
            ),
            max_gap=config.get("max_gap", MAX_GAP),
        ).faces()

        # --- cluster count ---
        self.assertEqual(
            len(result.clusters),
            golden["cluster_count"],
        )

        for idx, (cluster, expected) in enumerate(
            zip(result.clusters, golden["clusters"])
        ):
            label = f"{golden['source_file']} part {idx+1}"

            inners = sorted(cluster.inners, key=lambda x: x.area, reverse=True)

            # --- area ---
            self.assertAlmostEqual(
                round(cluster.area, 4),
                expected["area_mm2"],
                delta=TOL_AREA,
                msg=f"{label} area",
            )

            # --- outer perimeter ---
            self.assertAlmostEqual(
                round(to_shapely(cluster.outer).exterior.length, 4),
                expected["outer_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} outer perimeter",
            )

            # --- total inner perimeter ---
            actual_inner_p = round(
                sum(to_shapely(i).exterior.length for i in inners),
                4,
            )
            self.assertAlmostEqual(
                actual_inner_p,
                expected["inner_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} inner perimeter",
            )

            # --- total perimeter ---
            actual_total_p = round(
                to_shapely(cluster.outer).exterior.length +
                sum(to_shapely(i).exterior.length for i in inners),
                4,
            )
            self.assertAlmostEqual(
                actual_total_p,
                expected["total_perimeter_mm"],
                delta=TOL_PERIMETER,
                msg=f"{label} total perimeter",
            )

            # --- outer shape ---
            outer = shapely_wkt.loads(expected["outer_wkt"])
            self.assertLess(
                to_shapely(cluster.outer).symmetric_difference(outer).area,
                TOL_SHAPE,
                msg=f"{label} outer shape",
            )

            # --- inners ---
            self.assertEqual(
                len(inners),
                expected["inners_count"],
                msg=f"{label} inners count",
            )

            _assert_shapes_match_unordered(
                self,
                inners,
                expected["inners_wkt"],
                label,
                "inner",
            )

            # --- inners to_dict ---
            if "inners" in expected:
                remaining_expected = list(enumerate(expected["inners"]))
                for j, inner in enumerate(inners):
                    best_idx = None
                    best_score = None
                    actual_dict = inner.to_dict()
                    actual_area = actual_dict.get("area", 0)
                    for expected_idx, exp_inner_dict in remaining_expected:
                        score = abs(actual_area - exp_inner_dict.get("area", 0))
                        if best_score is None or score < best_score:
                            best_idx = expected_idx
                            best_score = score
                    exp_inner_dict = expected["inners"][best_idx]
                    remaining_expected = [
                        item for item in remaining_expected
                        if item[0] != best_idx
                    ]
                    self.assertEqual(
                        actual_dict["role"],
                        exp_inner_dict["role"],
                        msg=f"{label} inner[{j}].role",
                    )
                    self.assertAlmostEqual(
                        actual_dict["area"],
                        exp_inner_dict["area"],
                        delta=TOL_AREA,
                        msg=f"{label} inner[{j}].area",
                    )


    test.__name__ = f"test_{path.stem}"
    return test


class TestGoldenFaces(unittest.TestCase):
    pass


for golden in _load_golden_files():
    setattr(
        TestGoldenFaces,
        f"test_{golden.stem}",
        _make_test(golden),
    )


def _make_roundtrip_test(path):
    """Round-trip of the exporter: heal → to_dxf → reload → heal.

    The assertions of TestGoldenFaces stop at the in-memory model and NEVER see the
    geometry written by to_dxf(): an exporter bug (e.g. arcs materialized
    inverted, lost contours) goes unnoticed. Here the WRITTEN geometry is reloaded
    and re-processed: it must reproduce the same model that TestGoldenFaces already
    validated against the golden. So we compare rt_result with result, not with the
    JSON — so the matching of the parts is independent of the order."""

    def test(self):
        golden = json.loads(path.read_text(encoding="utf-8"))
        dxf_path = GOLDEN_DXF_DIR / golden["source_file"]

        if not dxf_path.exists():
            self.skipTest(str(dxf_path))
        if golden["source_file"] in ROUNDTRIP_KNOWN_LOSSY:
            self.skipTest(f"{golden['source_file']}: known lossy write-back (mixed splines)")

        config = _load_config(dxf_path)
        max_gap = config.get("max_gap", MAX_GAP)
        name_roles = {**GLOBAL_NAME_ROLES, **config.get("name_roles", {})}

        def _pipeline(doc):
            return topo.heal(doc, max_gap=max_gap).faces()

        result = _pipeline(
            topo_dxf.load_dxf(
                str(dxf_path), upgrade=True, explode_inserts=True,
                flatten_z=True, role_rules=topo.name_rules(name_roles),
            )
        )
        doc_out = topo_dxf.to_dxf(result)
        rt_result = _pipeline(
            topo_dxf.document_from_msp(
                doc_out.modelspace(), role_rules=topo.name_rules(_roundtrip_name_roles(name_roles)),
                skip_layers=topo_dxf.SKIP_LAYERS,  # re-reads topo's output without loose and texts
            )
        )

        src = golden["source_file"]
        self.assertEqual(
            len(rt_result.clusters), len(result.clusters),
            msg=f"{src} round-trip cluster_count "
                f"(the exporter lost or invented a part)",
        )

        unmatched = list(rt_result.clusters)
        for i, cluster in enumerate(result.clusters):
            match = min(
                unmatched,
                key=lambda p: to_shapely(p.outer).centroid.distance(
                    to_shapely(cluster.outer).centroid
                ),
                default=None,
            )
            self.assertIsNotNone(match, msg=f"{src} part {i+1} without a match")
            unmatched.remove(match)
            label = f"{src} round-trip part {i+1}"

            self.assertAlmostEqual(
                match.area, cluster.area, delta=TOL_AREA_ROUNDTRIP, msg=f"{label} area",
            )
            self.assertAlmostEqual(
                to_shapely(match.outer).exterior.length,
                to_shapely(cluster.outer).exterior.length,
                delta=TOL_PERIMETER, msg=f"{label} outer perimeter",
            )
            self.assertLess(
                to_shapely(match.outer).symmetric_difference(to_shapely(cluster.outer)).area,
                TOL_SHAPE_ROUNDTRIP, msg=f"{label} outer shape",
            )
            self.assertEqual(
                len(match.inners), len(cluster.inners), msg=f"{label} inners count",
            )

    test.__name__ = f"test_roundtrip_{path.stem}"
    return test


class TestGoldenFacesWriteBack(unittest.TestCase):
    pass


for golden in _load_golden_files():
    setattr(
        TestGoldenFacesWriteBack,
        f"test_roundtrip_{golden.stem}",
        _make_roundtrip_test(golden),
    )


class TestGoldenFacesSetup(unittest.TestCase):

    def test_directory_exists(self):
        self.assertTrue(GOLDEN_JSON_DIR.exists())

    def test_has_files(self):
        self.assertGreater(len(_load_golden_files()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)