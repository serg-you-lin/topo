# tests/engine/topology/test_touching.py

import math
import unittest
from topo.core.topology.touching import touching_groups
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg
from topo.core.topology.edge import node_point
from topo.core.topology.noding import edge_geometry
from topo.precision import SAME_POINT


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _square(x, y, size=10):
    pts = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    return [_line(pts[i], pts[(i + 1) % 4]) for i in range(4)]


class TestTouchingGroups(unittest.TestCase):

    def test_two_far_squares_two_groups(self):
        groups = touching_groups(_square(0, 0) + _square(100, 0), gap_tolerance=5)
        self.assertEqual(len(groups), 2)
        self.assertEqual([len(i.edges) for i in groups], [4, 4])

    def test_gap_below_tolerance_joins(self):
        # 3mm apart, tolerance 5: same group even without touching
        groups = touching_groups(_square(0, 0) + _square(13, 0), gap_tolerance=5)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].bbox, (0.0, 0.0, 23.0, 10.0))

    def test_transitive_chain(self):
        # A near B, B near C, A far from C: a single group
        edges = _square(0, 0) + _square(12, 0) + _square(24, 0)
        self.assertEqual(len(touching_groups(edges, gap_tolerance=3)), 1)

    def test_near_in_x_far_in_y(self):
        groups = touching_groups(_square(0, 0) + _square(0, 50), gap_tolerance=5)
        self.assertEqual(len(groups), 2)

    def test_hole_near_the_side_same_group(self):
        hole = Edge(role="unknown", start=(3, 5), end=(3, 5),
                    segment=CircleSeg(center=(2, 5), radius=1))
        groups = touching_groups(_square(0, 0) + [hole], gap_tolerance=1.5)
        self.assertEqual(len(groups), 1)

    def test_hole_far_from_the_sides_a_group_of_its_own(self):
        # only nearness: that the hole is INSIDE is told by the outer contour, afterwards
        hole = Edge(role="unknown", start=(52, 50), end=(52, 50),
                    segment=CircleSeg(center=(50, 50), radius=2))
        groups = touching_groups(_square(0, 0, 100) + [hole], gap_tolerance=5)
        self.assertEqual(len(groups), 2)

    def test_long_diagonal_does_not_join_by_bbox(self):
        # the diagonal's bbox covers the square, the true distance does not
        diag = _line((0, 0), (100, 100))
        groups = touching_groups([diag] + _square(70, 5), gap_tolerance=2)
        self.assertEqual(len(groups), 2)

    def test_sorted_by_area(self):
        groups = touching_groups(_square(0, 0, 5) + _square(100, 0, 20), gap_tolerance=1)
        self.assertEqual(groups[0].width, 20)

    def test_list_void(self):
        self.assertEqual(touching_groups([], gap_tolerance=1), [])


class TestGapOnTrueCurvesUnderMotion(unittest.TestCase):
    """`dwithin` at `gap_tolerance` on the discretizations. A circle with sagitta
    just below `SAME_POINT` and a small square at 0.4996 from the true circle,
    threshold 0.5: on a vertex the measured distance is the true one, at mid-chord
    ~0.001 more; half a step of the angular grid took it beyond 0.5 and the group
    became two."""

    N = 64
    MOTIONS = [(0.0, 0.0, 0.0), (math.pi / 64, 0.0, 0.0), (math.pi / 128, 0.0, 0.0), (0.7, 0.0, 0.0),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def _pieces(self, distance, move):
        step = 2 * math.pi / self.N
        r = SAME_POINT * (1 - 1e-8) / (1 - math.cos(step / 2))
        y = r + distance
        pts = [(-0.2, y), (0.2, y), (0.2, y + 0.4), (-0.2, y + 0.4)]
        segments = [CircleSeg(center=(0.0, 0.0), radius=r)] + [
            LineSeg(start=pts[i], end=pts[(i + 1) % 4]) for i in range(4)]
        edges = []
        for seg in map(move, segments):
            start, end = segment_endpoints(seg)
            edges.append(Edge(role="unknown", start=node_point(start), end=node_point(end), segment=seg))
        return edges

    def test_the_true_distance_decides_at_every_motion(self):
        from tests.invariants import rigid
        for distance, expected in ((0.4996, 1), (0.5004, 2)):
            for motion in self.MOTIONS:
                move, _ = rigid(*motion)
                with self.subTest(distance=distance, motion=motion):
                    self.assertEqual(len(touching_groups(self._pieces(distance, move), gap_tolerance=0.5)), expected)

    def test_in_place_the_chord_is_beyond_the_threshold(self):
        # the proof is not empty: at half a step the discretization measures more than 0.5
        #
        from tests.invariants import rigid
        move, _ = rigid(math.pi / 64, 0.0, 0.0)
        edges = self._pieces(0.4996, move)
        geoms = [edge_geometry(e) for e in edges]
        self.assertGreater(min(geoms[0].distance(g) for g in geoms[1:]), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
