"""
tests/package/test_no_format_words.py
-------------------------------------
D292: il pacchetto `topo` è geometria e matematica, nessun formato (D123).
Il nome di un formato di file non compare nel suo codice né nei suoi testi:
chi spiega come si apre un file è l'adapter, e il README.
"""

import re
import unittest

from tests.paths import PROJECT_ROOT

FORMAT_WORDS = re.compile(r"dxf|dwg", re.IGNORECASE)


class TestNoFormatWords(unittest.TestCase):

    def test_nessun_formato_dentro_topo(self):
        found = []
        for path in sorted((PROJECT_ROOT / "topo").rglob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if FORMAT_WORDS.search(line):
                    found.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{n}: {line.strip()}")
        self.assertEqual(found, [], "il nome di un formato dentro topo: va nell'adapter (D292)")


if __name__ == "__main__":
    unittest.main()
