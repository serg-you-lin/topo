"""
tests/engine/readings/test_network.py

`heal()` returns the repaired network and the readings are its methods: the
surface of `Network`, the two numbers, `source_file` and `label` carried onto
every reading, `island()` gone. Geometry built with the numbers.
"""

import unittest

import topo
from topo.primitives import LineSeg


def _square(x0: float = 0.0, side: float = 10.0) -> list:
    a, b, c, d = (x0, 0.0), (x0 + side, 0.0), (x0 + side, side), (x0, side)
    return [LineSeg(a, b), LineSeg(b, c), LineSeg(c, d), LineSeg(d, a)]


def _doc(segments: list, source_path: str = "") -> topo.Document:
    doc = topo.load_segments(segments)
    doc.source_path = source_path
    return doc


class TestHealReturnsNetwork(unittest.TestCase):

    def test_heal_returns_the_network_and_the_two_readings(self):
        net = topo.heal(_doc(_square()), max_gap=0.01)
        self.assertIsInstance(net, topo.Network)
        self.assertTrue(net.is_valid)
        for reading in (net.faces(), net.outlines()):
            self.assertIsInstance(reading, topo.Result)
            self.assertTrue(reading.is_valid)
            self.assertEqual(len(reading.clusters), 1)

    def test_the_same_network_read_twice_gives_the_same(self):
        # a reading does not dirty the network for the next
        net = topo.heal(_doc(_square() + [LineSeg((2, 2), (4, 4))]), max_gap=0.01)
        first, again = net.faces(), (net.outlines(), net.faces())[1]
        self.assertEqual([c.outer.area for c in first.clusters], [c.outer.area for c in again.clusters])
        self.assertEqual(len(first.loose), len(again.loose))

    def test_surface(self):
        net = topo.heal(_doc(_square()), max_gap=0.01)
        for name in ("edges", "crossings", "free_ends", "set_aside", "warnings", "errors",
                     "is_valid", "source_file", "label", "max_gap", "faces", "outlines"):
            self.assertTrue(hasattr(net, name), name)
        # the planar network with the crossings (NodedEdges) stays internal
        self.assertFalse(hasattr(net, "noded"))

    def test_island_no_longer_exists(self):
        self.assertFalse(hasattr(topo, "island"))
        self.assertNotIn("island", topo.__all__)
        self.assertIn("Network", topo.__all__)


class TestTwoNumbers(unittest.TestCase):

    def test_without_max_gap_no_gap_closes(self):
        # a side interrupted by 0.03, below the tolerance: without max_gap it stays open
        segs = [LineSeg((0.0, 0.0), (9.97, 0.0))] + _square()[1:]
        net = topo.heal(_doc(segs))
        self.assertEqual(net.max_gap, 0.0)
        self.assertFalse(hasattr(net, "tolerance"))
        self.assertEqual(len(net.faces().clusters), 0)

    def test_max_gap_below_the_tolerance_stays_its_own(self):
        segs = [LineSeg((0.0, 0.0), (9.97, 0.0))] + _square()[1:]
        net = topo.heal(_doc(segs), max_gap=0.01)
        self.assertEqual(net.max_gap, 0.01)
        self.assertEqual(len(net.faces().clusters), 0)

    def test_a_closed_gap_is_reported(self):
        # how many, how long and where: never a closure in silence
        segs = [LineSeg((0.0, 0.0), (9.97, 0.0))] + _square()[1:]
        net = topo.heal(_doc(segs), max_gap=0.05)
        joined = [n for n in net.notes if n.code == "ends-joined"]
        self.assertEqual(len(joined), 1)
        self.assertEqual(len(joined[0].points), 1)
        self.assertIn("0.0300 mm", joined[0].notes[0])

    def test_a_gap_closes_only_within_max_gap(self):
        # a side interrupted by 0.3: closed with max_gap 0.5, open without
        segs = [LineSeg((0.0, 0.0), (9.7, 0.0))] + _square()[1:]
        self.assertEqual(len(topo.heal(_doc(segs), max_gap=0.01).faces().clusters), 0)
        self.assertEqual(len(topo.heal(_doc(segs), max_gap=0.5).faces().clusters), 1)


class TestThresholdsChecked(unittest.TestCase):
    """`max_gap` is in mm: a value that is not stops at `heal()`."""

    def test_the_tolerance_is_not_a_parameter(self):
        # a single fixed threshold: topo.precision.SAME_POINT
        with self.assertRaises(TypeError):
            topo.heal(_doc(_square()), **{"tolerance": 0.05})

    def test_invalid_max_gap_refused(self):
        for bad in (-0.1, float("nan"), float("inf")):
            with self.subTest(max_gap=bad), self.assertRaises(ValueError):
                topo.heal(_doc(_square()), max_gap=bad)

    def test_max_gap_zero_accepted(self):
        self.assertTrue(topo.heal(_doc(_square()), max_gap=0.0).faces().is_valid)

    def test_non_numeric_threshold(self):
        for kw in ({"max_gap": "0.1"}, {"max_gap": True}):
            with self.subTest(**kw), self.assertRaises(TypeError):
                topo.heal(_doc(_square()), **kw)


class TestProvenance(unittest.TestCase):

    def test_default_source_file_from_the_document(self):
        net = topo.heal(_doc(_square(), source_path="parte.dxf"), max_gap=0.01)
        self.assertEqual(net.source_file, "parte.dxf")
        for reading in (net.faces(), net.outlines()):
            self.assertEqual(reading.source_file, "parte.dxf")
            self.assertEqual([c.source_file for c in reading.clusters], ["parte.dxf"])

    def test_callers_source_file_wins(self):
        net = topo.heal(_doc(_square(), source_path="parte.dxf"), source_file="altro.dxf", max_gap=0.01)
        self.assertEqual(net.faces().source_file, "altro.dxf")
        self.assertEqual(net.outlines().source_file, "altro.dxf")

    def test_label_on_every_cluster_of_both_readings(self):
        net = topo.heal(_doc(_square() + _square(x0=20.0)), label="p", max_gap=0.01)
        for reading in (net.faces(), net.outlines()):
            self.assertEqual([c.label for c in reading.clusters], ["p", "p"])


class TestEmpty(unittest.TestCase):

    def test_void_document_invalid_network_and_invalid_readings(self):
        net = topo.heal(_doc([]))
        self.assertFalse(net.is_valid)
        for reading in (net.faces(), net.outlines()):
            self.assertFalse(reading.is_valid)
            self.assertEqual(reading.errors, net.errors)


if __name__ == "__main__":
    unittest.main()
