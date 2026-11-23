# tests/engine/topology/test_non_contour_edges.py

import unittest
from topo.core.topology.graph import build_node_graph
from topo.core.topology.non_contour_edges import NonContourEdgeDetector
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg

def _make_edge(p1, p2):
    # The role here is irrelevant to NonContourEdgeDetector, which works by
    # topology only (branching + outer face), never by role — any non-structural
    # string is enough.
    return Edge(
        role="bending",
        start=p1,
        end=p2,
        segment=LineSeg(start=p1, end=p2),
    )


class TestNonContourEdgeDetector(unittest.TestCase):

    def test_inner_line_confirmed(self):
        # rectangle with an inner diagonal
        #
        #  (0,2)-----(1,2)
        #    |    /    |
        #  (0,0)-----(1,0)
        #
        # the diagonal (0,0)-(1,2) is a chain of one edge between two branching nodes
        # and the border of the outer face does not walk it → excluded from the contour graph

        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (1.0, 2.0)),
            _make_edge((1.0, 2.0), (0.0, 2.0)),
            _make_edge((0.0, 2.0), (0.0, 0.0)),
            _make_edge((0.0, 0.0), (1.0, 2.0)),  # non-contour edge
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        non_contour_edge = edges[-1]
        self.assertIn(id(non_contour_edge), result)

    def test_line_on_the_border_ignored(self):
        # simple triangle — no branching node → nothing to exclude
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (0.5, 1.0)),
            _make_edge((0.5, 1.0), (0.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)

    def test_no_branching_nothing_to_exclude(self):
        # open chain — no branching node
        edges = [
            _make_edge((0.0, 0.0), (1.0, 0.0)),
            _make_edge((1.0, 0.0), (2.0, 0.0)),
        ]
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)
        self.assertEqual(len(result), 0)

    def test_hull_per_component_not_for_the_whole_sheet(self):
        # Two shapes on the same sheet, not connected to each other (no edge in
        # common): a large rectangle "A" and, wholly inside its area, a small rectangle
        # "B" with a diagonal — the same scheme as the first test, in miniature. Real bug
        # found on a drawing with several views: a hull computed on ALL the sheet's nodes
        # is dominated by A, so even B's true contour sides (not only its diagonal) come
        # out "inside" that huge hull and end excluded by mistake. Today it holds for the
        # outer face: it is walked per connected component.
        a = [
            _make_edge((0.0, 0.0), (100.0, 0.0)),
            _make_edge((100.0, 0.0), (100.0, 50.0)),
            _make_edge((100.0, 50.0), (0.0, 50.0)),
            _make_edge((0.0, 50.0), (0.0, 0.0)),
        ]
        b = [
            _make_edge((40.0, 20.0), (41.0, 20.0)),
            _make_edge((41.0, 20.0), (41.0, 22.0)),
            _make_edge((41.0, 22.0), (40.0, 22.0)),
            _make_edge((40.0, 22.0), (40.0, 20.0)),
            _make_edge((40.0, 20.0), (41.0, 22.0)),  # B's diagonal, not contour
        ]
        edges = a + b
        g = build_node_graph(edges)
        result = NonContourEdgeDetector(tolerance=0.01).detect(g, edges)

        b_contour_ids = {id(e) for e in b[:4]}
        b_diagonal_id = id(b[-1])

        self.assertEqual(result & b_contour_ids, set(),
                          "B's true contour sides must not be excluded")
        self.assertIn(b_diagonal_id, result,
                       "B's diagonal stays a non-contour edge")

    def test_concave_side_between_two_chords_stays_contour(self):
        # an L: the side (10,10)-(10,30) of the concave part is inside the convex hull;
        # the two chords from (0,0) to its vertices make it a candidate (ends of degree
        # 3), but it borders the outside
        #
        #  (0,30)-(10,30)
        #    |      |
        #    |    (10,10)----(30,10)
        #    |                  |
        #  (0,0)--------------(30,0)
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (30.0, 0.0)), ((30.0, 0.0), (30.0, 10.0)), ((30.0, 10.0), (10.0, 10.0)),
            ((10.0, 10.0), (10.0, 30.0)), ((10.0, 30.0), (0.0, 30.0)), ((0.0, 30.0), (0.0, 0.0))]]
        chords = [_make_edge((0.0, 0.0), (10.0, 10.0)), _make_edge((0.0, 0.0), (10.0, 30.0))]
        edges = outline + chords
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chords})

    def test_notch_with_overlapping_flanks(self):
        # a notch from the bottom up to (30,20), with drawn flanks that cross just above
        # the bottom (the right flank returns to (27, 0.5), to the left of where the left
        # one starts): without a node at the crossing the outer-face walk passed over it
        # and took the bends for border. Three bends from the notch's vertex.
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (28.0, 0.0)), ((28.0, 0.0), (30.0, 20.0)), ((30.0, 20.0), (27.0, 0.5)),
            ((27.0, 0.5), (60.0, 0.0)), ((60.0, 0.0), (60.0, 40.0)), ((60.0, 40.0), (30.0, 40.0)),
            ((30.0, 40.0), (0.0, 40.0)), ((0.0, 40.0), (0.0, 0.0))]]
        bends = [_make_edge((30.0, 20.0), (0.0, 0.0)), _make_edge((30.0, 20.0), (60.0, 0.0)),
                 _make_edge((30.0, 20.0), (30.0, 40.0))]
        edges = outline + bends
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in bends})


# a 40 × 20 rectangle with the bottom and top sides not split
_RECT = [((0.0, 0.0), (40.0, 0.0)), ((40.0, 0.0), (40.0, 20.0)),
         ((40.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]


class TestChainCandidates(unittest.TestCase):
    """The chain between two branching nodes is judged, not the edge: nodes of degree 2 are not forks."""

    def test_chain_at_t_on_the_sides(self):
        # bends from vertex to vertex for two mid-side points, which the heal graph does
        # not split: (10,0) and (30,20) have degree 2 there
        #
        #  (0,20)-----(30,20)--(40,20)
        #    |       /             |
        #  (0,0)--(10,0)--------(40,0)
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 20.0), (10.0, 0.0)), _make_edge((10.0, 0.0), (30.0, 20.0)),
                 _make_edge((30.0, 20.0), (40.0, 0.0))]
        edges = outline + chain
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chain})

    def test_chain_with_interior_vertex(self):
        # a chord broken at (20,10), a free point inside the piece
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 0.0), (20.0, 10.0)), _make_edge((20.0, 10.0), (40.0, 20.0))]
        edges = outline + chain
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(e) for e in chain})

    def test_broken_side_stays_contour(self):
        # the bottom side in two stretches, a diagonal from its two ends: the two
        # stretches are a candidate chain, but on the outer border
        outline = [_make_edge(a, b) for a, b in [
            ((0.0, 0.0), (20.0, 0.0)), ((20.0, 0.0), (40.0, 0.0)), ((40.0, 0.0), (40.0, 20.0)),
            ((40.0, 20.0), (0.0, 20.0)), ((0.0, 20.0), (0.0, 0.0))]]
        chord = _make_edge((0.0, 0.0), (40.0, 20.0))
        edges = outline + [chord]
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, {id(chord)})

    def test_hole_touching_the_contour_remains(self):
        # a closed loop attached to the contour at a single node (0,0): a chain with
        # equal ends is already a loop, never a chord
        outline = [_make_edge(a, b) for a, b in _RECT]
        lobe = [_make_edge((0.0, 0.0), (10.0, 5.0)), _make_edge((10.0, 5.0), (5.0, 10.0)),
                _make_edge((5.0, 10.0), (0.0, 0.0))]
        edges = outline + lobe
        result = NonContourEdgeDetector(tolerance=0.01).detect(build_node_graph(edges), edges)
        self.assertEqual(result, set())


class TestGraphChains(unittest.TestCase):

    def test_every_edge_in_a_single_chain(self):
        outline = [_make_edge(a, b) for a, b in _RECT]
        chain = [_make_edge((0.0, 20.0), (10.0, 0.0)), _make_edge((10.0, 0.0), (30.0, 20.0)),
                 _make_edge((30.0, 20.0), (40.0, 0.0))]
        chains = build_node_graph(outline + chain).chains()
        # theta: three chains between (0,20) and (40,0)
        self.assertEqual(len(chains), 3)
        self.assertEqual(sorted(len(run) for run, _, _ in chains), [2, 2, 3])
        for _, a, b in chains:
            self.assertEqual({a, b}, {(0.0, 20.0), (40.0, 0.0)})
        ids = [id(e) for run, _, _ in chains for e in run]
        self.assertEqual(sorted(ids), sorted(id(e) for e in outline + chain))

    def test_ring_without_branches(self):
        chains = build_node_graph([_make_edge(a, b) for a, b in _RECT]).chains()
        self.assertEqual(len(chains), 1)
        run, a, b = chains[0]
        self.assertEqual((len(run), a), (4, b))


if __name__ == "__main__":
    unittest.main(verbosity=2)