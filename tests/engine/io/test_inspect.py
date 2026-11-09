"""
tests/engine/io/test_inspect.py
--------------------------
Smoke test dei tre livelli di topo.inspect: non devono sollevare e devono
stampare qualcosa di sensato.
"""

import io
import unittest
from contextlib import redirect_stdout

import topo
import topo_dxf
from topo import geometry
from topo.model.document import Document


def _square(side: float = 100.0) -> Document:
    return topo.load_segments(geometry.rectangle(side, side), tolerance=0.5)


class TestInspectLevels(unittest.TestCase):

    def test_level2_document(self):
        doc = _square()
        buf = io.StringIO()
        with redirect_stdout(buf):
            topo.inspect_document(doc)
        out = buf.getvalue()
        self.assertIn("LEVEL 2", out)
        self.assertIn("edge: 4", out)
        self.assertIn("node graph", out)

    def test_level3_result(self):
        doc = _square()
        result = topo.heal(doc, tolerance=0.5).faces()
        buf = io.StringIO()
        with redirect_stdout(buf):
            topo.inspect_result(result)
        out = buf.getvalue()
        self.assertIn("LEVEL 3", out)
        self.assertIn("PART 0", out)
        self.assertIn("role=outer", out)

    def test_inspect_functions_exported(self):
        # i livelli di topo in topo, quello del file nell'adapter (D129)
        for module, names in ((topo, ("inspect_document", "inspect_result")),
                              (topo_dxf, ("inspect_dxf", "inspect_file"))):
            for name in names:
                self.assertIn(name, module.__all__)
                self.assertTrue(callable(getattr(module, name)))
        self.assertNotIn("inspect_dxf", topo.__all__)


if __name__ == "__main__":
    unittest.main()
