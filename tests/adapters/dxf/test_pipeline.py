"""
tests/adapters/dxf/test_pipeline.py
----------------------------------

Test semantic pipeline integrity.

Usa solo file generati in:
tests/data/
"""

import unittest

from tests.adapters.dxf.pipeline_check import (
    run_pipeline,
    count_entities_on_layer,
)

from tests.paths import DATA

EXAMPLES_DIR = DATA



def ex(name: str) -> str:
    """
    Resolve path to example DXF.
    """
    path = EXAMPLES_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing example file: {path}."
        )
    return str(path)


class TestSpecialLayersWithoutDetect(unittest.TestCase):
    """
    Senza detect_flat(), le entità su layer non-strutturale vanno in Trash.
    """

    def setUp(self):
        self.pipeline = run_pipeline(
            ex("la_104.dxf"),
            do_write=True,
        )

    def test_001_mark_goes_to_trash_without_detect(self):
        # Il layer sorgente "MARK" non compare mai nel documento materializzato.
        msp = self.pipeline["msp"]
        mark_count = count_entities_on_layer(msp, "MARK")
        self.assertEqual(mark_count, 0)

    def test_002_trash_has_entities(self):
        # Senza detect_flat(), la geometria non strutturale resta nel modello
        # come loose (non più spostata su un layer "Trash" del msp).
        result = self.pipeline["result"]
        self.assertGreater(len(result.loose), 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)