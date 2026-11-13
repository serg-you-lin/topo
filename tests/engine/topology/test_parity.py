# tests/engine/topology/test_parity.py

import random
import unittest

from topo.core.primitives.segments import LineSeg
from topo.core.topology.edge import Edge
from topo.core.topology.noding import split_at_crossings
from topo.core.topology.parity import parity_rings
from topo.model.role import ContourRole


def _line(a, b):
    return Edge(role=ContourRole.UNKNOWN, start=a, end=b, segment=LineSeg(start=a, end=b))


def _polygon(*pts):
    return [_line(pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]


def _read(edges):
    noded = split_at_crossings(edges, 0.01)
    found = parity_rings(noded.pieces)
    rings = sorted(sorted({p for e, _ in loop for p in (e.start, e.end)}) for loop in found.loops)
    dropped = {id(noded.parent_of(p)) for p in noded.pieces if id(p) in found.dropped}
    return rings, dropped, found


class TestEvenNetwork(unittest.TestCase):

    def test_every_side_is_a_contour(self):
        # un rombo dentro un quadrato che tocca il lato in un punto: nodo di grado 4
        outer = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        inner = _polygon((5, 0), (8, 3), (5, 6), (2, 3))
        rings, dropped, found = _read(outer + inner)
        self.assertEqual(len(rings), 2)
        self.assertFalse(dropped)
        self.assertFalse(found.conflicts)

    def test_separate_component_inside_is_a_hole(self):
        outer = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        inner = _polygon((3, 3), (6, 3), (6, 6), (3, 6))
        rings, dropped, _ = _read(outer + inner)
        self.assertEqual(len(rings), 2)
        self.assertFalse(dropped)


class TestOddNodes(unittest.TestCase):

    def test_chord_goes(self):
        square = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        chord = _line((5, 0), (5, 10))
        rings, dropped, _ = _read(square + [chord])
        self.assertEqual(rings, [[(0, 0), (0, 10), (5, 0), (5, 10), (10, 0), (10, 10)]])
        self.assertEqual(dropped, {id(chord)})

    def test_line_across_goes_with_its_tails(self):
        square = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        axis = _line((-5, 5), (15, 5))
        rings, dropped, _ = _read(square + [axis])
        self.assertEqual(len(rings), 1)
        self.assertEqual(dropped, {id(axis)})

    def test_each_chord_with_its_own_odd_nodes_goes(self):
        rect = _polygon((0, 0), (20, 0), (20, 10), (0, 10))
        short = _line((5, 0), (5, 10))
        slanted = _line((10, 0), (20, 10))
        rings, dropped, _ = _read(rect + [short, slanted])
        self.assertEqual(len(rings), 1)
        self.assertEqual(dropped, {id(short), id(slanted)})

    def test_bridge_goes(self):
        square = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        stem = _line((0, 5), (3, 5))
        box = _polygon((3, 4), (3, 6), (5, 6), (5, 4))
        rings, dropped, _ = _read(square + [stem] + box)
        self.assertEqual(dropped, {id(stem)})
        self.assertEqual(len(rings), 2)

    def test_the_lightest_set_goes(self):
        # p e q dispari, uniti da tre strade: la diretta (2) costa meno delle
        # due spezzate (~6.3); resta il rombo
        p, q = (4, 5), (6, 5)
        direct = _line(p, q)
        rhombus = [_line(p, (5, 8)), _line((5, 8), q), _line(q, (5, 2)), _line((5, 2), p)]
        square = _polygon((0, 0), (10, 0), (10, 10), (0, 10))
        rings, dropped, _ = _read(square + rhombus + [direct])
        self.assertEqual(dropped, {id(direct)})
        self.assertEqual(len(rings), 2)

    def test_order_does_not_matter(self):
        rect = _polygon((0, 0), (20, 0), (20, 10), (0, 10))
        extra = [_line((5, 0), (5, 10)), _line((15, 0), (15, 10)), _line((0, 5), (20, 5))]
        expected, _, _ = _read(rect + extra)
        rnd = random.Random(4)
        for _ in range(5):
            edges = rect + extra
            rnd.shuffle(edges)
            edges = [_line(e.end, e.start) if rnd.random() < 0.5 else e for e in edges]
            self.assertEqual(_read(edges)[0], expected)


if __name__ == "__main__":
    unittest.main()
