"""
tests/paths.py
--------------
Le due cartelle che i test usano, scritte una volta: la radice del progetto e
i disegni di `tests/data/`. Un test non calcola percorsi da `__file__`, così
può cambiare cartella senza cambiare niente dentro.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "tests" / "data"
