"""
test_role.py
------------
Unit tests for topo.model.role: the open role vocabulary.

Covers:
  - normalize_role : known role → constant, unknown → slug kept,
                     dirty input → safe slug (no injection payloads)
  - role_str       : string value whether the role is enum or str
  - integration    : a custom role survives load_geometry → heal
"""

import unittest

import topo
import topo_dxf
from topo.model.role import (
    ContourRole, normalize_role, role_str,
    is_structural_role, STRUCTURAL_ROLES,
)
from topo import to_shapely


class TestNormalizeRole(unittest.TestCase):

    def test_known_role_becomes_constant(self):
        # Only outer/inner are engine vocabulary now (roles out of core) —
        # normalize_role() promotes them to ContourRole.
        self.assertIs(normalize_role("outer"), ContourRole.OUTER)
        self.assertIs(normalize_role("  INNER "), ContourRole.INNER)

    def test_manufacturing_role_is_any_slug_here(self):
        # "hole"/"bending" are no longer constants of model.role: they are process
        # vocabulary, snapbend's. Here they pass as any slug, not as a ContourRole.
        self.assertEqual(normalize_role("hole"), "hole")
        self.assertNotIsInstance(normalize_role("hole"), ContourRole)

    def test_unknown_role_kept_as_slug(self):
        self.assertEqual(normalize_role("title_block"), "title_block")
        self.assertEqual(normalize_role("Nesting Region"), "nesting_region")

    def test_dirty_input_neutralized(self):
        # characters outside [a-z0-9_-] collapsed: no injection in the sinks
        self.assertEqual(normalize_role("</cluster><x>"), "cluster_x")
        self.assertEqual(normalize_role("a\nb\tc"), "a_b_c")

    def test_truncation_at_64(self):
        self.assertEqual(len(normalize_role("x" * 200)), 64)

    def test_empty_or_non_string_becomes_unknown(self):
        self.assertEqual(normalize_role(""), "unknown")
        self.assertEqual(normalize_role("   "), "unknown")
        self.assertEqual(normalize_role(None), "unknown")
        self.assertEqual(normalize_role(123), "unknown")


class TestRoleStr(unittest.TestCase):

    def test_from_enum_and_from_string(self):
        self.assertEqual(role_str(ContourRole.OUTER), "outer")
        self.assertEqual(role_str("title_block"), "title_block")


class TestIsStructuralRole(unittest.TestCase):
    """Minimal predicate of the engine: only outer/inner. The extended process
    predicate (+ hole/countersink/threaded_hole) is snapbend's."""

    def test_contour_roles(self):
        for r in (ContourRole.OUTER, ContourRole.INNER):
            self.assertTrue(is_structural_role(r))

    def test_marking_and_furniture_are_not_structural(self):
        for r in ("engrave", "marking", "bending", "hole", ContourRole.UNKNOWN):
            self.assertFalse(is_structural_role(r))

    def test_consumer_slug_is_not_structural(self):
        # `frame` is no longer a topo constant: it is a slug like the others
        self.assertFalse(is_structural_role("frame"))
        self.assertFalse(is_structural_role("title_block"))
        self.assertFalse(is_structural_role("section"))

    def test_accepts_the_equivalent_string_slug(self):
        # ContourRole inherits from str: "outer" == ContourRole.OUTER
        self.assertTrue(is_structural_role("outer"))
        self.assertIn(ContourRole.INNER, STRUCTURAL_ROLES)


class TestCustomRoleSurvivesHeal(unittest.TestCase):

    def test_custom_role_kept_not_flattened_to_unknown(self):
        # an "outer" square with a small square inside marked with a role topo does not
        # know: heal keeps it as non-structural geometry (trash), but the role stays the
        # caller's, not "unknown"
        doc = topo.load_geometry([
            {"type": "polygon", "role": "outer",
             "points": [(0, 0), (100, 0), (100, 100), (0, 100)]},
            {"type": "polygon", "role": "title_block",
             "points": [(10, 10), (40, 10), (40, 30), (10, 30)]},
        ])
        result = topo.heal(doc).faces()

        all_roles = {result.clusters[0].outer.role}
        all_roles.update(i.role for i in result.clusters[0].inners)
        all_roles.update(role_str(getattr(t, "role", "")) for t in result.loose)

        self.assertIn("title_block", all_roles)
        self.assertEqual(result.clusters[0].outer.role, ContourRole.OUTER)


class TestConsumerRolesSurviveDetect(unittest.TestCase):
    """a role topo does not classify (frame, title block, a consumer's slug) survives
    the pipeline — load → heal — with geometry and role intact. The same after
    snapbend's detection: tests/flat/test_roles.py."""

    def _framed_doc(self):
        # large frame + two parts inside, all geometrically distinct
        return topo.load_geometry([
            {"type": "polygon", "role": "frame",
             "points": [(0, 0), (400, 0), (400, 300), (0, 300)]},
            {"type": "polygon", "role": "outer",
             "points": [(20, 20), (120, 20), (120, 120), (20, 120)]},
            {"type": "polygon", "role": "outer",
             "points": [(200, 20), (300, 20), (300, 120), (200, 120)]},
        ])

    def test_the_frame_is_not_a_cluster_nor_eats_the_pieces(self):
        result = topo.heal(self._framed_doc()).faces()
        self.assertEqual(len(result.clusters), 2)
        for c in result.clusters:
            self.assertEqual(c.outer.role, ContourRole.OUTER)
            self.assertLess(to_shapely(c.outer).area, 20000)  # it is not the frame

    def test_to_dxf_writes_the_consumer_role_on_a_layer_of_its_own(self):
        # the frame does not end on "Trash" together with the true garbage, but on a
        # "frame" layer with its colour. topo does not know what it is — it carries
        # faithfully the slug the consumer assigned.
        doc = self._framed_doc()
        result = topo.heal(doc).faces()
        out = topo_dxf.to_dxf(result, doc)

        layers = {e.dxf.layer for e in out.modelspace()}
        self.assertIn("frame", layers)

        frame_ents = [e for e in out.modelspace() if e.dxf.layer == "frame"]
        self.assertTrue(frame_ents)
        self.assertIn("frame", out.layers)


if __name__ == "__main__":
    unittest.main()
