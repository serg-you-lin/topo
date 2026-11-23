"""
tests/adapters/dxf/test_ensure_linetype.py
----------------------------------
`ensure_linetype`: a single rule to register a linetype in the output
document — already present, source pattern, standard table, otherwise None.
"""

import unittest

import ezdxf

from topo_dxf.exporter import ensure_linetype


class TestEnsureLinetype(unittest.TestCase):

    def setUp(self):
        self.doc = ezdxf.new("R2010")

    def test_001_continuous_needs_no_registration(self):
        self.assertEqual(ensure_linetype(self.doc, "Continuous"), "Continuous")

    def test_002_source_pattern_wins_over_standard(self):
        # same name as a standard one, but the source's shape is the truth of that file
        self.assertEqual(ensure_linetype(self.doc, "DASHED", (10.0, 7.0, -3.0), "from the source"), "DASHED")
        self.assertEqual(self.doc.linetypes.get("DASHED").dxf.description, "from the source")

    def test_003_standard_name_without_pattern_is_registered(self):
        # before, a DASHED line with no captured pattern became continuous
        self.assertEqual(ensure_linetype(self.doc, "DASHED"), "DASHED")
        self.assertIn("DASHED", self.doc.linetypes)

    def test_004_unknown_name_without_pattern_is_none(self):
        self.assertIsNone(ensure_linetype(self.doc, "DASHHED"))
        self.assertNotIn("DASHHED", self.doc.linetypes)

    def test_005_custom_name_with_pattern_is_registered(self):
        self.assertEqual(ensure_linetype(self.doc, "MIO_TRATTO", (5.0, 3.0, -2.0)), "MIO_TRATTO")
        self.assertIn("MIO_TRATTO", self.doc.linetypes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
