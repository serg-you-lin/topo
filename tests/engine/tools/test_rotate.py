"""
test_rotate.py
---------------
Unit tests for topo.tools.rotate (experimental, not yet in __all__):
    structural_segments      Result -> list[segment], filtered by role
    longest_structural_segment  same, but only the longest + its angle
    rotate_cluster / rotate_result   rotate an ALREADY sound Cluster/Result —
                                      no heal() called again
    rotate_document           rotates a raw Document (pre-heal)
    rotate_to_longest         orchestrator: aligns the longest, a single
                               heal() (the one the caller already did)

It uses topo.load_geometry (pure Python dicts -> Document) instead of a DXF
file: same pattern as test_geometry_loader.py, no I/O.
"""

import math
import unittest

import topo
from topo.tools.rotate import (
    structural_segments, longest_structural_segment,
    rotate_cluster, rotate_result, rotate_document, rotate_to_longest,
)
from topo.model.text import Text
from topo import to_shapely


def _tall_rect_with_diagonal():
    """Rectangle 100x400 (vertical outer, long sides = 400) plus an inner diagonal
    line (shorter and not outer) — the same shape as tests/data/try_for_rotation.dxf,
    built in memory."""
    return topo.load_geometry([
        {"type": "polygon", "points": [(0, 0), (100, 0), (100, 400), (0, 400)]},
        {"type": "line", "start": (0.3, 50), "end": (99.7, 350)},
    ])


def _rect_with_hole():
    """Rectangle 100x50 with a hole (circle) — outer + an inner. No explicit `role`
    on the rectangle on purpose: heal() assigns `ContourRole.OUTER` to the true
    outer anyway, and leaving the input without a role avoids the inner hole
    inheriting "outer" from the parent (see the comment in topo/tools/rotate.py
    on `hierarchy._make_inner`)."""
    return topo.load_geometry([
        {"type": "polygon", "points": [(0, 0), (100, 0), (100, 50), (0, 50)]},
        {"type": "circle", "center": (50, 25), "radius": 5},
    ])


class TestStructuralSegments(unittest.TestCase):

    def test_001_longest_defaults_to_outer_only_ignores_diagonal(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        seg, length, angle_deg = longest_structural_segment(result)
        self.assertIsNotNone(seg)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 90.0, places=6)

    def test_002_include_inners_adds_the_hole(self):
        result = topo.heal(_rect_with_hole()).faces()
        with_inners = structural_segments(result, include_inners=True)
        outer_only = structural_segments(result, include_inners=False)
        self.assertGreater(len(with_inners), len(outer_only))

    def test_003_no_clusters_returns_none(self):
        doc = topo.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        result = topo.heal(doc).faces()
        seg, length, angle_deg = longest_structural_segment(result)
        self.assertIsNone(seg)
        self.assertEqual(length, 0.0)
        self.assertIsNone(angle_deg)


class TestRotateCluster(unittest.TestCase):

    def test_001_rotates_outer_and_inner_keeps_parent_link(self):
        result = topo.heal(_rect_with_hole()).faces()
        cluster = result.clusters[0]
        rotated = rotate_cluster(cluster, math.pi / 2, origin=(0, 0))

        self.assertAlmostEqual(to_shapely(rotated.outer).bounds[0], -50.0, places=3)
        # the rotated inner must still have the NEW outer as parent, not the old one
        self.assertIs(rotated.inners[0].parent, rotated.outer)
        self.assertIsNot(rotated.inners[0].parent, cluster.outer)

    def test_002_does_not_mutate_original(self):
        result = topo.heal(_rect_with_hole()).faces()
        cluster = result.clusters[0]
        original_bounds = to_shapely(cluster.outer).bounds
        rotate_cluster(cluster, math.pi / 2, origin=(0, 0))
        self.assertEqual(to_shapely(cluster.outer).bounds, original_bounds)


class TestRotateResult(unittest.TestCase):

    def test_001_single_heal_matches_longest_outer_after_rotation(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        rotated = rotate_result(result, math.radians(-90), origin=(50, 200))
        _, length, angle_deg = longest_structural_segment(rotated)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 0.0, places=6)

    def test_002_loose_rotates_too(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        trash_before = result.loose[0].segments[0]
        rotated = rotate_result(result, math.radians(-90), origin=(50, 200))
        trash_after = rotated.loose[0].segments[0]
        self.assertNotEqual(trash_before.start, trash_after.start)

    def test_003_warns_instead_of_silently_dropping_texts(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        result.texts.append(Text(position=(0, 0), text="X"))
        rotated = rotate_result(result, 0.1)
        [warning] = [w for w in rotated.warnings if w.code == "not-rotated"]
        self.assertEqual(warning.message, "rotate_result(): 1 text not rotated (not supported yet)")
        self.assertEqual(warning.points, ((0.0, 0.0),))

    def test_004_warns_when_overlay_present(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        result.clusters[0].overlay = {"bending_lines": []}
        rotated = rotate_result(result, 0.1)
        [warning] = [w for w in rotated.warnings if w.code == "not-rotated"]
        self.assertEqual(warning.message, "rotate_result(): cluster.overlay is not rotated")
        self.assertIn("run the consumer's reading again", warning.help)


class TestRotateDocument(unittest.TestCase):

    def test_001_rotates_every_edge_around_origin(self):
        doc = topo.load_geometry([{"type": "line", "start": (1, 0), "end": (2, 0)}])
        rotated = rotate_document(doc, math.pi / 2, origin=(0, 0))
        seg = rotated.edges[0].segment
        self.assertAlmostEqual(seg.start[0], 0.0, places=6)
        self.assertAlmostEqual(seg.start[1], 1.0, places=6)

    def test_002_warns_instead_of_silently_dropping_texts(self):
        doc = topo.load_geometry([{"type": "line", "start": (1, 0), "end": (2, 0)}])
        doc.texts.append(Text(position=(3, 4), text="X"))
        [warning] = [w for w in rotate_document(doc, 0.1).warnings if w.code == "not-rotated"]
        self.assertEqual(warning.message, "rotate_document(): 1 text not rotated (not supported yet)")
        self.assertEqual(warning.points, ((3.0, 4.0),))


class TestRotateToLongest(unittest.TestCase):

    def test_001_aligns_longest_outer_to_horizontal_one_heal_only(self):
        result = topo.heal(_tall_rect_with_diagonal()).faces()
        rotated_result, applied_deg = rotate_to_longest(result)
        self.assertAlmostEqual(applied_deg, -90.0, places=6)

        _, length, angle_deg = longest_structural_segment(rotated_result)
        self.assertAlmostEqual(length, 400.0, places=6)
        self.assertAlmostEqual(angle_deg, 0.0, places=6)

    def test_002_no_outer_returns_result_unchanged(self):
        doc = topo.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
        result = topo.heal(doc).faces()
        rotated_result, applied_deg = rotate_to_longest(result)
        self.assertIs(rotated_result, result)
        self.assertEqual(applied_deg, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
