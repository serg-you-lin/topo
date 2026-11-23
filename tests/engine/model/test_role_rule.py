"""
test_role_rule.py
-----------------
Unit tests for topo.model.role_rule: the rules with which the caller assigns a
role at load, evaluated on neutral signals — source group name and EdgeStyle —
with no format in between.
"""

import unittest


import topo
from topo.model.role_rule import resolve_role
from topo.model.style import EdgeStyle

CONTINUA    = EdgeStyle()
TRATTEGGIATA = EdgeStyle(linetype="DASHED", dash=(0.5, -0.25))
PUNTINATA   = EdgeStyle(linetype="DOT", dash=(0.0, -4.0))
CIANO       = EdgeStyle(color=(0, 255, 255))
# chains: different marks alternating (long stroke + short stroke / dot)
TRATTO_PUNTO = EdgeStyle(linetype="AnyType", dash=(0.5, -0.25, 0.0, -0.25))
DUE_TRATTI   = EdgeStyle(linetype="AnyType", dash=(1.25, -0.25, 0.25, -0.25))


class TestIsDashed(unittest.TestCase):

    def test_pattern_with_gaps_is_dashed(self):
        self.assertTrue(TRATTEGGIATA.is_dashed)
        self.assertTrue(PUNTINATA.is_dashed)

    def test_without_pattern_or_without_gaps_is_continuous(self):
        self.assertFalse(CONTINUA.is_dashed)
        self.assertFalse(EdgeStyle(dash=(1.0, 0.0)).is_dashed)

    def test_the_pattern_counts_not_the_name(self):
        # "dashed" is a fact of the pattern; the name says nothing
        self.assertFalse(EdgeStyle(linetype="DASHED").is_dashed)
        self.assertTrue(EdgeStyle(linetype="AnyType",
                                  dash=(1.0, -1.0)).is_dashed)


class TestDashKind(unittest.TestCase):
    # the stroke shape is read from the pattern's marks, not from the name

    def test_unbroken(self):
        self.assertEqual(CONTINUA.dash_kind, "continuous")
        self.assertEqual(EdgeStyle(dash=(1.0, 0.0)).dash_kind, "continuous")

    def test_uniform_hatching(self):
        self.assertEqual(TRATTEGGIATA.dash_kind, "uniform")
        self.assertEqual(PUNTINATA.dash_kind, "uniform")      # dots only
        # the same stroke repeated several times in the pattern: it stays uniform
        self.assertEqual(EdgeStyle(dash=(0.5, -0.25, 0.5, -0.25)).dash_kind,
                         "uniform")

    def test_chain(self):
        self.assertEqual(TRATTO_PUNTO.dash_kind, "chain")
        self.assertEqual(DUE_TRATTI.dash_kind, "chain")
        # long stroke + two short
        self.assertEqual(EdgeStyle(dash=(0.45, -0.05, 0.1, -0.05, 0.1, -0.05))
                         .dash_kind, "chain")

    def test_tolerance_relative_to_the_scale(self):
        # same ratios at different scales → same shape
        for k in (0.01, 1.0, 100.0):
            dash = tuple(x * k for x in (1.25, -0.25, 0.25, -0.25))
            self.assertEqual(EdgeStyle(dash=dash).dash_kind, "chain", msg=k)
        # strokes that differ by a rounding do not make a chain
        self.assertEqual(EdgeStyle(dash=(0.5, -0.25, 0.501, -0.25)).dash_kind,
                         "uniform")



class TestRoleRule(unittest.TestCase):

    def test_name_ignores_case(self):
        rule = topo.RoleRule("bending", name="Bend")
        self.assertTrue(rule.matches("BEND", style=CONTINUA))
        self.assertFalse(rule.matches("Bends", style=CONTINUA))

    def test_name_contains(self):
        rule = topo.RoleRule("construction", name_contains="constr")
        self.assertTrue(rule.matches("Construction_lines", style=CONTINUA))
        self.assertFalse(rule.matches("Cut", style=CONTINUA))

    def test_conditions_all_true_together(self):
        # snapdraw's case: dashed AND name "construction"
        rule = topo.RoleRule("construction", name_contains="construction", dashed=True)
        self.assertTrue(rule.matches("construction", style=TRATTEGGIATA))
        self.assertFalse(rule.matches("construction", style=CONTINUA))
        self.assertFalse(rule.matches("0", style=TRATTEGGIATA))

    def test_only_continuous(self):
        rule = topo.RoleRule("outer", dashed=False)
        self.assertTrue(rule.matches("", style=CONTINUA))
        self.assertFalse(rule.matches("", style=TRATTEGGIATA))

    def test_stroke_shape(self):
        # snapdraw's ISO 128 rule: chain → construction, the dashing not
        rule = topo.RoleRule("construction", dash="chain")
        self.assertTrue(rule.matches("", style=TRATTO_PUNTO))
        self.assertTrue(rule.matches("", style=DUE_TRATTI))
        self.assertFalse(rule.matches("", style=TRATTEGGIATA))
        self.assertFalse(rule.matches("", style=CONTINUA))
        self.assertTrue(topo.RoleRule("x", dash="UNIFORM").matches("", style=PUNTINATA))

    def test_dashed_includes_the_chains(self):
        # dashed stays "has at least one gap": it holds for the two families
        self.assertTrue(topo.RoleRule("x", dashed=True).matches("", style=TRATTO_PUNTO))

    def test_unknown_dash_raises(self):
        with self.assertRaises(ValueError):
            topo.RoleRule("construction", dash="dashdot")

    def test_colour_by_name_rgb_or_hex(self):
        for key in ("cyan", "CYAN", (0, 255, 255), "#00ffff"):
            self.assertTrue(topo.RoleRule("engrave", color=key).matches("", style=CIANO), msg=repr(key))
        self.assertFalse(topo.RoleRule("engrave", color="red").matches("", style=CIANO))

    def test_unknown_colour_raises(self):
        with self.assertRaises(ValueError):
            topo.RoleRule("engrave", color="puce")
        with self.assertRaises(ValueError):
            topo.RoleRule("engrave", color=4)     # an ACI index belongs to DXF

    def test_rule_without_conditions_raises(self):
        with self.assertRaises(ValueError):
            topo.RoleRule("bending")

    def test_cleaned_role(self):
        self.assertEqual(topo.RoleRule("Title Block", name="x").role, "title_block")


class TestResolveRole(unittest.TestCase):

    def test_chain_bend_taken_first_by_name(self):
        # a bend drawn as a chain stays bending if the rule by name comes first
        rules = [
            topo.RoleRule("bending", name="bend"),
            topo.RoleRule("construction", dash="chain"),
        ]
        self.assertEqual(resolve_role(rules, "Bend", TRATTO_PUNTO), "bending")
        self.assertEqual(resolve_role(rules, "Axes", TRATTO_PUNTO), "construction")

    def test_the_first_in_order_wins(self):
        rules = [
            topo.RoleRule("bending", name="bend"),
            topo.RoleRule("engrave", color="cyan"),
        ]
        self.assertEqual(resolve_role(rules, "Bend", CIANO), "bending")
        self.assertEqual(resolve_role(rules[::-1], "Bend", CIANO), "engrave")

    def test_no_rule_is_unknown(self):
        self.assertEqual(resolve_role([], "Bend", CONTINUA), "unknown")
        self.assertEqual(resolve_role(topo.name_rules({"misc": "outer"}), "Dunno", CONTINUA),
                         "unknown")

    def test_name_rules(self):
        rules = topo.name_rules({"TitleBlock": "title_block", "MARK": "engrave"})
        self.assertEqual(resolve_role(rules, "titleblock", CONTINUA), "title_block")
        self.assertEqual(resolve_role(rules, "MARK", CONTINUA), "engrave")


class TestWithoutAppearance(unittest.TestCase):
    # an annotation has no appearance to compare (style=None)

    def test_rule_on_the_name_matches(self):
        self.assertTrue(topo.RoleRule("note", name="text").matches("TEXT"))

    def test_rule_on_the_appearance_does_not_match(self):
        for rule in (topo.RoleRule("x", dashed=False), topo.RoleRule("x", dash="continuous"),
                     topo.RoleRule("x", color="cyan"),
                     topo.RoleRule("x", name="text", dashed=False)):
            self.assertTrue(rule.reads_style)
            self.assertFalse(rule.matches("text"), msg=repr(rule))

    def test_resolve_without_style(self):
        rules = [topo.RoleRule("cut", dashed=False), topo.RoleRule("note", name="text")]
        self.assertEqual(resolve_role(rules, "TEXT"), "note")


if __name__ == "__main__":
    unittest.main()
