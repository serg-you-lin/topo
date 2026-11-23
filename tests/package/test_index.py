# tests/package/test_index.py
"""docs/INDEX.md up to date and the dependency rule respected (`scripts/gen_index.py --check`)."""

import subprocess
import sys
import unittest
from tests.paths import PROJECT_ROOT



class TestCodeIndex(unittest.TestCase):

    def test_index_updated_and_layers_clean(self):
        # docs/INDEX.md is not in git: on a fresh clone it is generated before the --check
        if not (PROJECT_ROOT / "docs" / "INDEX.md").exists():
            subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "gen_index.py")],
                           capture_output=True, text=True, encoding="utf-8", check=True)
        run = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "gen_index.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr
                         + "\n→ python scripts/gen_index.py, poi guarda la sezione Dependency rule")


if __name__ == "__main__":
    unittest.main()
