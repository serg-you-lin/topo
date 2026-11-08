"""
tests/adapters/dxf/test_edge_cases.py
-------------------------------------
Test Suite per casi edge su DXF reali.
"""

import unittest


import topo
import topo_dxf
from tests.paths import DATA

EDGE_CASES_DIR = DATA / "edge_cases"


def _extract_pline_vertices(msp):
    points = []
    for entity in msp.query("LWPOLYLINE"):
        for pt in entity.get_points():
            points.append((pt[0], pt[1]))
    return points


def _load_edge_cases():
    if not EDGE_CASES_DIR.exists():
        return []
    return sorted(EDGE_CASES_DIR.glob("*.dxf")) + sorted(
        EDGE_CASES_DIR.glob("*.DXF")
    )


class TestEdgeCases(unittest.TestCase):
    pass


def _make_test(dxf_path):
    def test_method(self):
        topo_doc = topo_dxf.load_dxf(str(dxf_path))
        result = topo.heal(topo_doc).faces()
        doc_out = topo_dxf.to_dxf(result, topo_doc)

        # ogni disegno di edge_cases/ ha almeno una parte
        self.assertGreater(result.cluster_count, 0)

        healed_vertices = _extract_pline_vertices(doc_out.modelspace())
        self.assertGreater(len(healed_vertices), 0)

    test_method.__name__ = f"test_{dxf_path.stem}"
    test_method.__doc__ = f"Edge case: {dxf_path.name}"
    return test_method


for _dxf_path in _load_edge_cases():
    setattr(TestEdgeCases, f"test_{_dxf_path.stem}", _make_test(_dxf_path))


class TestEdgeCasesDirExists(unittest.TestCase):

    def test_001_dir_exists(self):
        self.assertTrue(EDGE_CASES_DIR.exists())

    def test_002_contains_dxf(self):
        files = _load_edge_cases()
        self.assertGreater(len(files), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)