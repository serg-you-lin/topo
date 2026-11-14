"""
tests/adapters/dxf/test_nothing_readable.py
--------------------------------------------
Un file con entità ma nessuna che topo modella è un errore, non un foglio
vuoto (D252). Un file vuoto davvero resta un Document vuoto.

Il fixture usa ezdxf perché topo non sa scrivere un 3DFACE: è il formato di
ingresso stesso che si prova qui.
"""

import os
import tempfile
import unittest

import ezdxf

import topo_dxf


def _save(path: str, faces: bool = False, line: bool = False) -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    if faces:
        msp.add_3dface([(0, 0, 0), (10, 0, 0), (10, 10, 5), (0, 10, 5)])
    if line:
        msp.add_line((0, 0), (10, 0))
    doc.saveas(path)


class TestNothingReadable(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "sheet.dxf")

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_unmodeled_entities_raise(self):
        _save(self.path, faces=True)
        with self.assertRaises(ValueError) as ctx:
            topo_dxf.load_dxf(self.path)
        # il messaggio nomina il tipo che topo non legge
        self.assertIn("3DFACE", str(ctx.exception))

    def test_empty_file_is_an_empty_document(self):
        _save(self.path)
        doc = topo_dxf.load_dxf(self.path)
        self.assertEqual(len(doc.edges), 0)
        self.assertEqual(len(doc.texts), 0)

    def test_partly_readable_file_loads_with_warning(self):
        _save(self.path, faces=True, line=True)
        doc = topo_dxf.load_dxf(self.path)
        self.assertEqual(len(doc.edges), 1)
        self.assertTrue(any("3DFACE" in str(w) for w in doc.warnings))


if __name__ == "__main__":
    unittest.main()
