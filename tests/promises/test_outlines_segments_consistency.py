# tests/promises/test_outlines_segments_consistency.py

"""For every contour read by `outlines()`, the polygon (`to_shapely`, the finite
geometric shape that SVG/view_model draw) and `.segments` (the raw pieces
`to_dxf` writes) must describe the same shape: they are two representations of
the same contour, not two independent readings. Found on 12 October: on
`regr_04.dxf`, an isometric view's outer contour (the union of several faces)
had disconnected `.segments` (26 broken junctions out of 84) covering a third
of the true area — invisible both to `test_golden_outlines.py` (it compares
only bbox + count) and to SVG/view_model (they read only the polygon).
It is not a golden: it does not compare against a frozen value, it is an
invariant always true by definition — it is never regenerated, only made to pass."""

import unittest
from pathlib import Path

import topo

from tests.readings import outline_reading
from topo.core.topology.noding import GRAPH_EPSILON
from topo.core.geometry.shapely_polygons import build_polygon
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE
from topo import to_shapely
from tests.paths import DATA

SOURCE_DIR = DATA / "golden_outlines"
MAX_GAP = 0.5
# how much the border of the same shape may move between the two readings: the
# discretization's sagitta plus the node grid of the union of faces — along the
# whole perimeter, the area of a band that wide
OUTLINE_BAND = DEFAULT_TOLERANCE + GRAPH_EPSILON


class TestOutlinesSegmentsConsistency(unittest.TestCase):

    def _assert_same_shape(self, contour, where):
        poly = to_shapely(contour)
        rebuilt = build_polygon(contour.segments)
        self.assertIsNotNone(rebuilt, f"{where}: .segments do not form a valid polygon")
        sym = poly.symmetric_difference(rebuilt).area
        tol = max(poly.area * 0.01, poly.length * OUTLINE_BAND)
        self.assertLess(sym, tol,
                         f"{where}: the polygon (area={poly.area:.4f}) e .segments "
                         f"(area={rebuilt.area:.4f}) descrivono forme diverse "
                         f"(differenza simmetrica={sym:.4f})")


def _make_test(dxf: Path):
    def test(self):
        _, result = outline_reading(dxf, MAX_GAP)
        for ci, cluster in enumerate(result.clusters):
            self._assert_same_shape(cluster.outer, f"{dxf.stem}.cluster[{ci}].outer")
            for ii, inner in enumerate(cluster.inners):
                self._assert_same_shape(inner, f"{dxf.stem}.cluster[{ci}].inner[{ii}]")
    return test


for _dxf in sorted(SOURCE_DIR.glob("*.dxf")):
    setattr(TestOutlinesSegmentsConsistency, f"test_{_dxf.stem}", _make_test(_dxf))


if __name__ == "__main__":
    unittest.main()
