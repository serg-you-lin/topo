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


def drawing(name: str) -> Path:
    """Il disegno `name` di `tests/data/`, in qualunque cartella stia: un nome,
    una copia (lo prova `tests/package/test_one_copy.py`). Per i nomi ancora
    doppi con contenuti diversi (`SAME_NAME_DIFFERENT_CONTENT` lì) vince la
    radice, come prima; senza nessun file, il percorso nella radice (il test
    che lo cerca si salta da sé)."""
    found = sorted(p for p in DATA.rglob(name) if p.is_file())
    if len(found) == 1:
        return found[0]
    return DATA / name
