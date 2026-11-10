"""
tutorial/_paths.py — one way to handle paths in every lesson

First line of each lesson::

    import _paths  # noqa: F401

From then on the working directory is the repository root, wherever the lesson
was started from (VS Code's Run button, a terminal in another folder). So in the
CONFIG block you write the plain path:

    INPUT = r"tutorial/files/plate.dxf"      # relative -> from the repository
    INPUT = r"C:\\my_drawings\\part.dxf"       # absolute -> used as it is

`out(lesson)` is the folder a lesson writes into: tutorial_output/<lesson>/.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)


def out(lesson: str) -> Path:
    """The output folder of one lesson, created if missing."""
    folder = ROOT / "tutorial_output" / lesson
    folder.mkdir(parents=True, exist_ok=True)
    return folder
