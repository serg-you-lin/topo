"""
tests/adapters/dxf/test_diagnostic_codes.py
-------------------------------------------
The loader's own diagnostics that no other test makes fire: what each says,
where it points, and, when it carries a call as `help`, that the call makes it
go away.

The fixtures use ezdxf because topo cannot write an INSERT or a LEADER: it is the
input format itself that is tested here. The two conversions that need an
external program (DWG through ODA, the ezdxf audit) are stood in for, so only
the loader's own branch is exercised.
"""

import os
import tempfile
import unittest
from unittest import mock

import ezdxf
from ezdxf.addons import odafc
from ezdxf.entities import Insert

import topo_dxf
from topo_dxf import loader


def _codes(diagnostics) -> list:
    return [d.code for d in diagnostics]


class _TmpDir(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def save(self, doc, name: str = "drawing.dxf") -> str:
        path = os.path.join(self.dir, name)
        doc.saveas(path)
        return path


def _doc_with_insert(version: str = "R2010"):
    doc = ezdxf.new(version)
    block = doc.blocks.new("B")
    block.add_line((0, 0), (1, 1))
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0))
    msp.add_blockref("B", (5, 5))
    return doc


class TestInsertsIgnored(_TmpDir):

    def test_points_at_the_insert_and_the_help_reads_it(self):
        path = self.save(_doc_with_insert())
        doc = topo_dxf.load_dxf(path, explode_inserts=False)
        [warning] = [w for w in doc.warnings if w.code == "dxf-inserts-ignored"]
        self.assertEqual(warning.points, ((5.0, 5.0),))
        self.assertEqual(warning.message, "INSERT not exploded, its geometry ignored: 1")
        self.assertIn("explode_inserts=True", warning.help)
        read = topo_dxf.load_dxf(path, explode_inserts=True)
        self.assertEqual(_codes(read.warnings), [])
        self.assertEqual(_codes(read.notes), ["dxf-inserts-exploded"])
        self.assertEqual(len(read.edges), len(doc.edges) + 1)


class TestExplodeFailed(_TmpDir):

    def test_an_insert_that_does_not_explode_is_counted_with_its_reason(self):
        path = self.save(_doc_with_insert())
        with mock.patch.object(Insert, "explode", side_effect=RuntimeError("no block")):
            doc = topo_dxf.load_dxf(path)
        [warning] = [w for w in doc.warnings if w.code == "dxf-explode-failed"]
        self.assertEqual(warning.message, "INSERT that could not be exploded, left out: 1")
        self.assertEqual(warning.notes, ("no block",))
        self.assertEqual(len(doc.edges), 1)

    def test_the_upgrade_of_a_legacy_file_counts_what_it_could_not_explode(self):
        path = self.save(_doc_with_insert("R12"))
        with mock.patch.object(Insert, "explode", side_effect=RuntimeError("no block")):
            doc = topo_dxf.load_dxf(path)
        [warning] = [w for w in doc.warnings if w.code == "dxf-explode-failed"]
        self.assertEqual(warning.message, "entities that could not be exploded in the upgrade: 1")
        self.assertEqual(warning.notes, ("INSERT: no block",))
        self.assertEqual(_codes(doc.notes).count("dxf-upgraded"), 1)


class TestDwgConversion(_TmpDir):

    def _read_dwg(self, oda_path: str):
        path = os.path.join(self.dir, "drawing.dwg")
        with open(path, "wb") as f:
            f.write(b"AC1032" + bytes(20))
        converted = ezdxf.new("R2010")
        converted.modelspace().add_line((0, 0), (5, 5))
        with mock.patch.object(odafc, "readfile", return_value=converted), \
                mock.patch.object(loader, "ODA_PATH", oda_path), \
                mock.patch.object(loader.shutil, "which", return_value="ODAFileConverter"):
            return topo_dxf.load_dxf(path)

    def test_a_dwg_says_which_version_it_converted(self):
        doc = self._read_dwg(oda_path="")
        [note] = [n for n in doc.notes if n.code == "dxf-dwg-converted"]
        self.assertEqual((note.level, note.message), ("note", "DWG R2018+ (AC1032) converted through odafc"))
        self.assertEqual(len(doc.edges), 1)

    def test_an_oda_path_that_is_no_file_falls_back_to_the_path_variable(self):
        wrong = os.path.join(self.dir, "missing.exe")
        doc = self._read_dwg(oda_path=wrong)
        [warning] = [w for w in doc.warnings if w.code == "dxf-oda-path"]
        self.assertIn(repr(wrong), warning.message)
        self.assertIn("ODA_PATH", warning.help)
        self.assertEqual(len(doc.edges), 1)


class TestAudit(_TmpDir):

    def test_the_problems_of_the_audit_are_counted_with_the_first_five(self):
        path = self.save(_doc_with_insert())
        problems = [mock.Mock(__str__=lambda self, i=i: f"problem {i}") for i in range(7)]
        auditor = mock.Mock(errors=problems)
        with mock.patch("ezdxf.document.Drawing.audit", return_value=auditor):
            doc = topo_dxf.load_dxf(path)
        [warning] = [w for w in doc.warnings if w.code == "dxf-audit"]
        self.assertEqual(warning.message, "7 problems found by the ezdxf audit")
        self.assertEqual(warning.notes, tuple(f"problem {i}" for i in range(5)))


class TestLeaderWithNoString(unittest.TestCase):

    def test_the_help_reads_it_as_curves(self):
        doc = ezdxf.new("R2010")
        doc.modelspace().add_leader([(0, 0), (10, 5), (20, 5)])
        bare = topo_dxf.document_from_msp(doc.modelspace())
        [warning] = [w for w in bare.warnings if w.code == "dxf-not-modeled"]
        self.assertEqual(warning.message, "LEADER with no string of its own not read (not exploded here): 1")
        self.assertEqual(bare.edges, [])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "leader.dxf")
            doc.saveas(path)
            read = topo_dxf.load_dxf(path)
        self.assertEqual(_codes(read.warnings), [])
        self.assertGreater(len(read.edges), 0)


if __name__ == "__main__":
    unittest.main()
