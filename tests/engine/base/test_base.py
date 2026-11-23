# tests/engine/base/test_base.py
# The foundations common to every reading: the nodes are decided once, by
# nearness, before heal() and outlines(); the two readings start from the same ones.

import unittest

import topo
from topo.core.primitives.line import LineSeg
from topo.core.topology.noding import decide_nodes
from tests.invariants import MOTIONS, contours, moved, shape_differences
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE


def _square_with_split_corner():
    # the top-right corner drawn with two ends at 0.0002: 10.0004 and 10.0006 fall
    # in two different cells of the 1e-3 grid
    return [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)),
            LineSeg(start=(10.0, 0.0), end=(10.0004, 10.0)),
            LineSeg(start=(10.0006, 10.0), end=(0.0, 10.0)),
            LineSeg(start=(0.0, 10.0), end=(0.0, 0.0))]


class TestDecideNodes(unittest.TestCase):

    def test_ends_astride_a_cell_are_a_node(self):
        doc = topo.load_segments(_square_with_split_corner())
        self.assertNotEqual(doc.edges[1].end, doc.edges[2].start)   # the grid tuple
        edges, welded = decide_nodes(doc.edges)
        self.assertEqual(edges[1].end, edges[2].start)
        self.assertEqual(welded, 0)

    def test_dense_points_wider_than_epsilon_stay_distinct(self):
        # a curve written in steps of 0.004: the group exceeds 0.01, no node merged
        pts = [(5.0 + 0.004 * k, 1.0) for k in range(6)]
        doc = topo.load_segments([LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])])
        edges, welded = decide_nodes(doc.edges)
        self.assertEqual(len(edges), 5)
        self.assertEqual(welded, 0)
        self.assertEqual(len({p for e in edges for p in (e.start, e.end)}), 6)


class TestSameBaseForEveryReading(unittest.TestCase):

    def test_faces_and_outlines_read_the_same_contour_at_every_motion(self):
        doc = topo.load_segments(_square_with_split_corner())
        band = 2 * DEFAULT_TOLERANCE
        for name, move, back, _ in [("in place", lambda s: s, lambda p: p, None)] + MOTIONS:
            moved_doc = moved(doc, move)
            healed = [back(p) for p in contours(topo.heal(moved_doc).faces())[0]]
            read = [back(p) for p in contours(topo.heal(moved_doc, max_gap=0.5).outlines())[0]]
            self.assertEqual((len(healed), len(read)), (1, 1), name)
            self.assertEqual(shape_differences(healed, read, band) + shape_differences(read, healed, band),
                             [], name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
