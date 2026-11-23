# tests/engine/tools/test_non_contour_candidates.py

import unittest

import topo
from topo.model.document import Document
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg


def _make_edge(p1, p2):
    # Role irrelevant to the criterion (topology only: branching + outer face) —
    # same pattern as tests/engine/topology/test_non_contour_edges.py.
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


class TestNonContourCandidates(unittest.TestCase):

    def test_inner_diagonal_is_a_candidate(self):
        # rectangle with an inner diagonal — same scheme as
        # test_non_contour_edges.test_inner_line_confirmed, but through the public
        # API on a Document.
        rect = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
        ]
        diagonal = _make_edge((0.0, 0.0), (1.0, 2.0))
        doc = Document(edges=rect + [diagonal], source_meta={"tolerance": 0.01})

        candidates = topo.non_contour_candidates(doc)

        self.assertEqual([id(e) for e in candidates], [id(diagonal)])

    def test_simple_contour_no_candidate(self):
        # triangle — no branching node, nothing to report
        tri = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (0.5, 1.0)),
            _make_edge((0.5, 1.0), (0.0, 0.0)),
        ]
        doc = Document(edges=tri, source_meta={"tolerance": 0.01})

        self.assertEqual(topo.non_contour_candidates(doc), [])

    def test_concave_side_between_two_bends_is_not_a_candidate(self):
        # a U: the two bends go from (0,10)/(30,10) to the vertices of the notch's
        # bottom, (10,10)/(20,10); the bottom (10,10)-(20,10) lies inside the convex hull
        # but borders the outside: it is contour
        u = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (30.0, 0.0)), ((30.0, 0.0), (30.0, 20.0)), ((30.0, 20.0), (20.0, 20.0)),
            ((20.0, 20.0), (20.0, 10.0)), ((20.0, 10.0), (10.0, 10.0)), ((10.0, 10.0), (10.0, 20.0)),
            ((10.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]]
        bends = [_make_edge((0.0, 0.0), (10.0, 10.0)), _make_edge((30.0, 0.0), (20.0, 10.0))]
        doc = Document(edges=u + bends)

        self.assertEqual({id(e) for e in topo.non_contour_candidates(doc)}, {id(e) for e in bends})

    def test_returned_edges_are_mutable_in_place(self):
        # The point of the function: the caller must be able to set .role on the
        # returned objects and see it reflected on doc.edges, to pass them to heal()
        # already labelled.
        rect = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
        ]
        diagonal = _make_edge((0.0, 0.0), (1.0, 2.0))
        doc = Document(edges=rect + [diagonal], source_meta={"tolerance": 0.01})

        for edge in topo.non_contour_candidates(doc):
            edge.role = topo.normalize_role("flange_up")

        self.assertEqual(diagonal.role, "flange_up")


if __name__ == "__main__":
    unittest.main(verbosity=2)
