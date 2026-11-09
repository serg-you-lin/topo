# tests/package/test_index.py
"""docs/INDEX.md aggiornato e regola di dipendenza rispettata (`scripts/gen_index.py --check`)."""

import subprocess
import sys
import unittest
from tests.paths import PROJECT_ROOT



class TestCodeIndex(unittest.TestCase):

    def test_indice_aggiornato_e_layer_puliti(self):
        # docs/INDEX.md non è in git: su un clone nuovo lo si genera prima del --check
        if not (PROJECT_ROOT / "docs" / "INDEX.md").exists():
            subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "gen_index.py")],
                           capture_output=True, text=True, encoding="utf-8", check=True)
        run = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "gen_index.py"), "--check"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr
                         + "\n→ python scripts/gen_index.py, poi guarda la sezione Dependency rule")


if __name__ == "__main__":
    unittest.main()
