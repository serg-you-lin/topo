"""
tests/package/test_diagnostic_codes.py
--------------------------------------
The list of diagnostic codes in `tests/invariants.py` is the list of the sources:
a code written in the code and missing from the list, or listed and no longer
written, fails here. That every code fires in the suite is checked by the
`conftest.py` at the root.
"""

import unittest
from pathlib import Path

from tests.invariants import DYNAMIC_CODES, UNREACHED_CODES, all_codes, source_codes

ROOT = Path(__file__).resolve().parents[2]


class TestCodeList(unittest.TestCase):

    def test_every_code_in_the_sources_is_listed(self):
        self.assertEqual(sorted(source_codes(ROOT) - all_codes()), [])

    def test_every_listed_code_is_in_the_sources(self):
        self.assertEqual(sorted(all_codes() - source_codes(ROOT) - DYNAMIC_CODES), [])

    def test_the_unreached_are_listed_codes(self):
        self.assertEqual(sorted(UNREACHED_CODES - all_codes()), [])
