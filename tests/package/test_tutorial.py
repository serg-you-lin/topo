# tests/package/test_tutorial.py
"""Every lesson of tutorial/ runs from its CONFIG block and ends without errors."""

import subprocess
import sys
import unittest
from tests.paths import PROJECT_ROOT

TUTORIAL = PROJECT_ROOT / "tutorial"
LESSONS = sorted(p for p in TUTORIAL.glob("[0-9][0-9]_*.py"))


class TestTutorial(unittest.TestCase):

    def test_the_lessons_are_there(self):
        self.assertGreaterEqual(len(LESSONS), 13)

    def test_every_lesson_runs(self):
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.name):
                run = subprocess.run([sys.executable, str(lesson)], capture_output=True, text=True,
                                     encoding="utf-8", cwd=TUTORIAL, timeout=120)
                self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr[-3000:])

    def test_the_lessons_use_only_public_names(self):
        # a tester learns the public surface: no topo.core nor an import from an internal module
        for lesson in LESSONS:
            with self.subTest(lesson=lesson.name):
                source = lesson.read_text(encoding="utf-8")
                self.assertNotIn("topo.core", source)
                self.assertNotIn("from topo.", source.replace("from topo.primitives", ""))


if __name__ == "__main__":
    unittest.main()
