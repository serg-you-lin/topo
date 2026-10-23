"""
tests/drawings.py
-----------------
I disegni del repo su cui girano le promesse della 1.0 (D143, D158): ogni DXF
tracciato da git, con la sua lettura (D152) — quelli di `golden_islands/` e
`golden_anchoring/` sono fogli di viste e si leggono con `island()`, gli altri
con `heal()`. Le copie identiche contano una volta. Un disegno nuovo che entra
nel repo ha tutte le invarianti senza scrivere niente.
"""

import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ISLAND_DIRS = ("tests/data/golden_islands/", "tests/data/golden_anchoring/")


@lru_cache(maxsize=None)
def tracked_drawings() -> tuple:
    """((percorso relativo, "heal" | "island"), ...), in ordine di percorso."""
    out = subprocess.run(["git", "ls-files", "tests/*.dxf", "tests/*.DXF"],
                         cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
    seen, drawings = set(), []
    for rel in out.splitlines():
        digest = hashlib.sha1((PROJECT_ROOT / rel).read_bytes()).hexdigest()
        reading = "island" if rel.startswith(ISLAND_DIRS) else "heal"
        if (digest, reading) not in seen:
            seen.add((digest, reading))
            drawings.append((rel, reading))
    return tuple(drawings)


def drawings_for(reading: str) -> list:
    """I percorsi assoluti dei disegni che si leggono con `reading`."""
    return [PROJECT_ROOT / rel for rel, r in tracked_drawings() if r == reading]


def case_name(path: Path) -> str:
    """Nome di un test per `path`: il percorso sotto tests/, in caratteri da identificatore."""
    rel = Path(path).resolve().relative_to(PROJECT_ROOT / "tests").with_suffix("")
    return "test_" + re.sub(r"\W", "_", rel.as_posix())


def drawing_key(path: Path) -> str:
    """Il percorso di `path` sotto tests/, senza estensione: la chiave di un
    disegno nelle liste dei difetti noti."""
    return Path(path).resolve().relative_to(PROJECT_ROOT / "tests").with_suffix("").as_posix()
