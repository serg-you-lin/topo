"""
tests/package/test_no_format_words.py
-------------------------------------
The `topo` package is geometry and mathematics, no format. The name of a file
format does not appear in its code nor in its tests: whoever explains how to
open a file is the adapter, and the README.
"""

import re
import unittest

from tests.paths import PROJECT_ROOT

FORMAT_WORDS = re.compile(r"dxf|dwg", re.IGNORECASE)


class TestNoFormatWords(unittest.TestCase):

    def test_no_format_inside_topo(self):
        found = []
        for path in sorted((PROJECT_ROOT / "topo").rglob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FORMAT_WORDS.search(line):
                    found.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{n}: {line.strip()}")
        self.assertEqual(found, [], "the name of a format inside topo: it goes in the adapter")


if __name__ == "__main__":
    unittest.main()
