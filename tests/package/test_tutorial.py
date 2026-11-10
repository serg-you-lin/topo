# tests/package/test_tutorial.py
"""Ogni lezione di tutorial/ gira dal suo blocco CONFIG e finisce senza errori (D247)."""

import subprocess
import sys
import unittest
from tests.paths import PROJECT_ROOT

TUTORIAL = PROJECT_ROOT / "tutorial"
LESSONS = sorted(p for p in TUTORIAL.glob("[0-9][0-9]_*.py"))


class TestTutorial(unittest.TestCase):

    def test_ci_sono_le_lezioni(self):
        self.assertGreaterEqual(len(LESSONS), 13)

    def test_ogni_lezione_gira(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.name):
                run = subprocess.run([sys.executable, str(lesson)], capture_output=True, text=True,
                                     encoding="utf-8", cwd=TUTORIAL, timeout=120)
                self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-3000:])

    def test_le_lezioni_usano_solo_nomi_pubblici(self):
        # un tester impara la superficie pubblica: niente topo.core né import da un modulo interno
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.name):
                source = lesson.read_text(encoding="utf-8")
                self.assertNotIn("topo.core", source)
                self.assertNotIn("from topo.", source.replace("from topo.primitives", ""))


if __name__ == "__main__":
    unittest.main()
