"""
tests/paths.py
--------------
The two folders the tests use, written once: the project root and the
drawings of `tests/data/`. A test does not compute paths from `__file__`, so
it can change folder without changing anything inside.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA = PROJECT_ROOT / "tests" / "data"


def drawing(name: str) -> Path:
    """The drawing `name` of `tests/data/`, in whatever folder it is: one name, one
    copy (proved by `tests/package/test_one_copy.py`). For the names still doubled
    with different content (`SAME_NAME_DIFFERENT_CONTENT` there) the root wins, as
    before; with no file, the path in the root (the test that looks for it skips by itself)."""
    found = sorted(p for p in DATA.rglob(name) if p.is_file())
    if len(found) == 1:
        return found[0]
    return DATA / name
