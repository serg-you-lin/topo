"""
tests/drawings.py
-----------------
The repo's drawings on which the 1.0 promises run: every DXF tracked by git,
with its reading — those of `golden_outlines/` and `golden_anchoring/` are
sheets of views and are read with `outlines()`, the others with `faces()`.
Identical copies count once. A new drawing entering the repo gets all the
invariants without writing anything.
"""

import hashlib
import re
import subprocess
from functools import lru_cache
from pathlib import Path

from tests.paths import PROJECT_ROOT

OUTLINE_DIRS = ("tests/data/golden_outlines/", "tests/data/golden_anchoring/")


@lru_cache(maxsize=None)
def tracked_drawings() -> tuple:
    """((relative path, "faces" | "outlines"), ...), in path order."""
    out = subprocess.run(["git", "ls-files", "tests/*.dxf", "tests/*.DXF"],
                         cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
    seen, drawings = set(), []
    for rel in out.splitlines():
        digest = hashlib.sha1((PROJECT_ROOT / rel).read_bytes()).hexdigest()
        reading = "outlines" if rel.startswith(OUTLINE_DIRS) else "faces"
        if (digest, reading) not in seen:
            seen.add((digest, reading))
            drawings.append((rel, reading))
    return tuple(drawings)


def drawings_for(reading: str) -> list:
    """The absolute paths of the drawings read with `reading`."""
    return [PROJECT_ROOT / rel for rel, r in tracked_drawings() if r == reading]


def case_name(path: Path) -> str:
    """Name of a test per `path`: the path under tests/, in identifier characters."""
    rel = Path(path).resolve().relative_to(PROJECT_ROOT / "tests").with_suffix("")
    return "test_" + re.sub(r"\W", "_", rel.as_posix())


def drawing_key(path: Path) -> str:
    """The path of `path` under tests/, without extension: the key of a drawing in
    the lists of known defects."""
    return Path(path).resolve().relative_to(PROJECT_ROOT / "tests").with_suffix("").as_posix()
