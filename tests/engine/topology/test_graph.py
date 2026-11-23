# tests/engine/topology/test_graph.py

import math
import unittest
from topo.core.topology.graph import Graph, build_node_graph, cluster_points
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from topo.model.role import ContourRole


def _make_edge(p1, p2):
    return Edge(
        role=ContourRole.UNKNOWN,
        start=p1,
        end=p2,
        segment=LineSeg(start=p1, end=p2),
    )


def _arc_edge(center, radius, start_deg, end_deg):
    seg = CircleSeg(center=center, radius=radius,
                 start_angle=math.radians(start_deg), end_angle=math.radians(end_deg), ccw=True)
    start = (center[0] + radius * math.cos(seg.start_angle), center[1] + radius * math.sin(seg.start_angle))
    end = (center[0] + radius * math.cos(seg.end_angle), center[1] + radius * math.sin(seg.end_angle))
    return Edge(role=ContourRole.UNKNOWN, start=start, end=end, segment=seg)

def _triangle_edges():
    a, b, c = (0.0, 0.0), (1.0, 0.0), (0.5, 1.0)
    return [_make_edge(a, b), _make_edge(b, c), _make_edge(c, a)]


class TestGraphDegree(unittest.TestCase):

    def test_degree_triangle(self):
        g = build_node_graph(_triangle_edges())
        for node in g.nodes:
            self.assertEqual(g.degree(node), 2)


class TestGraphBranchingNodes(unittest.TestCase):

    def test_node_with_three_connections(self):
        edges = _triangle_edges()
        edges.append(_make_edge((0.0, 0.0), (1.0, 1.0)))
        g = build_node_graph(edges)
        self.assertIn((0.0, 0.0), g.branching_nodes())


class TestGraphPruned(unittest.TestCase):

    def test_open_chain_removed(self):
        a, b, c = (0.0, 0.0), (1.0, 0.0), (2.0, 0.0)
        edges = [_make_edge(a, b), _make_edge(b, c)]
        g = build_node_graph(edges)
        self.assertEqual(len(g.pruned().nodes), 0)


class TestClusterPoints(unittest.TestCase):

    def test_epsilon_zero_is_identity(self):
        pts = [(0.0, 0.0), (0.02, 0.0), (5.0, 5.0)]
        m = cluster_points(pts, 0.0)
        self.assertEqual(m, {p: p for p in pts})

    def test_merges_points_within_epsilon(self):
        pts = [(0.0, 0.0), (0.02, 0.0), (5.0, 5.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(m[(0.0, 0.0)], m[(0.02, 0.0)])
        self.assertNotEqual(m[(0.0, 0.0)], m[(5.0, 5.0)])

    def test_representative_is_lexicographic_min(self):
        pts = [(1.0, 0.0), (0.98, 0.0), (1.02, 0.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(set(m.values()), {(0.98, 0.0)})

    def test_transitive_chaining(self):
        # documented caveat: chained points within epsilon all collapse
        pts = [(0.0, 0.0), (0.08, 0.0), (0.16, 0.0)]
        m = cluster_points(pts, 0.1)
        self.assertEqual(len(set(m.values())), 1)


class TestBuildNodeGraphClustering(unittest.TestCase):

    def _open_square_split_corner(self):
        # closed square, but a corner is split into two nodes 0.06 apart — like a
        # rounding at a cell boundary
        a, b = (0.0, 0.0), (10.0, 0.0)
        c1, c2 = (10.0, 10.0), (10.06, 10.0)
        d = (0.0, 10.0)
        return [
            _make_edge(a, b),
            _make_edge(b, c1),
            _make_edge(c2, d),
            _make_edge(d, a),
        ]

    def test_exact_graph_leaves_corner_open(self):
        g = build_node_graph(self._open_square_split_corner())
        self.assertEqual(len(g.open_nodes()), 2)
        self.assertEqual(len(g.pruned().nodes), 0)

    def test_clustered_graph_closes_corner(self):
        g = build_node_graph(self._open_square_split_corner(), epsilon=0.1)
        self.assertEqual(g.open_nodes(), [])
        for node in g.pruned().nodes:
            self.assertEqual(g.degree(node), 2)

    def test_clustering_preserves_edge_objects(self):
        edges = self._open_square_split_corner()
        g = build_node_graph(edges, epsilon=0.1)
        seen = {id(e) for conn in g.nodes.values() for e, _ in conn}
        self.assertEqual(seen, {id(e) for e in edges})


class TestCloseSelfLoop(unittest.TestCase):

    def test_nearly_closed_arc_becomes_degenerate_loop(self):
        # arc_arc_gap: a 359.9-degree arc, its two ends end in the same epsilon
        # cluster -- but the real development (radius*sweep) is huge, it is not noise:
        # it must close, not vanish.
        #
        edge = _arc_edge((0.0, 0.0), 50.0, 0.0, 359.9)
        g = build_node_graph([edge], epsilon=0.5)
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(len(g.degenerate_loops), 1)
        closed = g.degenerate_loops[0]
        self.assertEqual(closed.start, closed.end)

    def test_short_arc_stays_discarded(self):
        # Small real development (radius 0.5, sweep 5 degrees): it really is a sliver,
        # the behaviour as always (discarded, not a loop) must not change.
        edge = _arc_edge((0.0, 0.0), 0.5, 0.0, 5.0)
        g = build_node_graph([edge], epsilon=0.5)
        self.assertEqual(len(g.nodes), 0)
        self.assertEqual(len(g.degenerate_loops), 0)

    def test_epsilon_zero_leaves_the_nearly_closed_arc(self):
        # Without clustering (epsilon=0, historical behaviour) the two ends stay
        # distinct nodes: the arc is a normal edge, not a loop.
        edge = _arc_edge((0.0, 0.0), 50.0, 0.0, 359.9)
        g = build_node_graph([edge], epsilon=0.0)
        self.assertEqual(len(g.degenerate_loops), 0)
        self.assertEqual(len(g.nodes), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)