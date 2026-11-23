# tests/engine/readings/test_outer_scan.py

import math
import unittest
from topo.core.readings.outer_scan import outer_candidate_edges, AXIS_X, AXIS_Y
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


class TestOuterCandidateEdges(unittest.TestCase):

    def test_square_all_the_sides(self):
        # the horizontal sides are seen only by the vertical ray: both axes are needed
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        oc = outer_candidate_edges(edges)
        self.assertEqual(oc.ids, {id(e) for e in edges})
        top = edges[2]
        self.assertTrue(all(h.axis == AXIS_X for h in oc.hits_of(top)))

    def test_hole_is_not_a_candidate(self):
        outer = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        hole = Edge(role="unknown", start=(6, 5), end=(6, 5),
                    segment=CircleSeg(center=(5, 5), radius=1))
        oc = outer_candidate_edges(outer + [hole])
        self.assertNotIn(id(hole), oc.ids)
        self.assertEqual(len(oc.edges), 4)

    def test_l_recess_all_the_sides(self):
        # L: the two sides of the recess are outer, seen from one of the two axes
        edges = _poly((0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10))
        oc = outer_candidate_edges(edges)
        self.assertEqual(oc.ids, {id(e) for e in edges})

    def test_parallel_inner_track_discarded(self):
        # nearly coincident projection, but inside: never at the extreme
        outer = _poly((0, 0), (10, 0), (10, 10), (0, 10))
        ghost = _line((9.9, 1), (9.9, 9))
        oc = outer_candidate_edges(outer + [ghost])
        self.assertNotIn(id(ghost), oc.ids)

    def test_outer_arc(self):
        # semicircle on top of a rectangle: the arc is the top border
        base = [_line((10, 5), (10, 0)), _line((10, 0), (0, 0)), _line((0, 0), (0, 5))]
        arc = Edge(role="unknown", start=(10, 5), end=(0, 5),
                   segment=CircleSeg(center=(5, 5), radius=5, start_angle=0.0,
                                  end_angle=math.pi, ccw=True))
        oc = outer_candidate_edges(base + [arc])
        self.assertIn(id(arc), oc.ids)
        self.assertTrue(any(h.axis == AXIS_Y for h in oc.hits_of(arc)))

    def test_list_void(self):
        oc = outer_candidate_edges([])
        self.assertEqual(oc.edges, [])
        self.assertEqual(oc.n_rays, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
