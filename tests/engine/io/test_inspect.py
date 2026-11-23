"""
tests/engine/io/test_inspect.py
--------------------------
Smoke test of the three levels of topo.inspect: they must not raise and must
print something sensible.
"""

import io
import unittest
from contextlib import redirect_stdout

import topo
import topo_dxf
from topo import geometry
from topo.model.document import Document


def _square(side: float = 100.0) -> Document:
    return topo.load_segments(geometry.rectangle(side, side))


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
        result = topo.heal(doc).faces()
        buf = io.StringIO()
        with redirect_stdout(buf):
            topo.inspect_result(result)
        out = buf.getvalue()
        self.assertIn("LEVEL 3", out)
        self.assertIn("PART 0", out)
        self.assertIn("role=outer", out)

    def test_inspect_functions_exported(self):
        # topo's levels in topo, the file's in the adapter
        for module, names in ((topo, ("inspect_document", "inspect_result")),
                              (topo_dxf, ("inspect_dxf", "inspect_file"))):
            for name in names:
                self.assertIn(name, module.__all__)
                self.assertTrue(callable(getattr(module, name)))
        self.assertNotIn("inspect_dxf", topo.__all__)


if __name__ == "__main__":
    unittest.main()
