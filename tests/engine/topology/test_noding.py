# tests/engine/topology/test_noding.py

import math
from collections import Counter
import unittest
from topo.precision import SAME_POINT
from topo.core.topology.noding import split_at_crossings, renode
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


class TestSplitAtCrossings(unittest.TestCase):

    def test_x_crossing_becomes_a_node(self):
        a, b = _line((0, 0), (10, 10)), _line((0, 10), (10, 0))
        noded = split_at_crossings([a, b], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 4)
        # all four pieces meet at the same node (5, 5)
        ends = [p.end for p in noded.pieces if p.end == (5.0, 5.0)] + \
               [p.start for p in noded.pieces if p.start == (5.0, 5.0)]
        self.assertEqual(len(ends), 4)

    def test_t_contact_splits_only_the_touched(self):
        base, stem = _line((0, 0), (10, 0)), _line((5, 0), (5, 5))
        noded = split_at_crossings([base, stem], tolerance=0.05)
        self.assertEqual(len(noded.pieces), 3)
        self.assertIs(noded.parent_of(noded.pieces[-1]), stem)

    def test_original_ends_stay_the_edge_nodes(self):
        a, b = _line((0, 0), (10, 0)), _line((5, -1), (5, 1))
        noded = split_at_crossings([a, b], tolerance=0.05)
        first = [p for p in noded.pieces if noded.parent_of(p) is a]
        self.assertEqual(first[0].start, a.start)
        self.assertEqual(first[-1].end, a.end)

    def test_crossed_circle_becomes_arcs(self):
        # a circle crossed by a line: two arcs between the two cuts
        noded = split_at_crossings([_circle((0, 0), 5), _line((-10, 0), (10, 0))], tolerance=0.05)
        arcs = [p for p in noded.pieces if (isinstance(p.segment, CircleSeg) and not p.segment.full)]
        self.assertEqual(len(arcs), 2)
        total = sum(p.segment.radius * p.segment._sweep() for p in arcs)
        self.assertAlmostEqual(total, 2 * math.pi * 5, places=6)

    def test_untouched_circle_stays_whole(self):
        c = _circle((0, 0), 1)
        noded = split_at_crossings([c, _line((5, 0), (6, 0))], tolerance=0.05)
        self.assertIn(c, noded.pieces)

    def test_near_tangency_is_a_single_node_not_two(self):
        """A line nearly tangent to an arc crosses in two mathematically distinct but
        very close roots: within `tolerance` they are the same contact, not two nodes
        with a sliver between."""
        radius, tol, gap = 10.0, 0.05, 0.02   # gap chosen < tol, >> _MIN_PIECE
        sink = (gap / 2) ** 2 / (2 * radius)  # sinking that produces that gap
        x = radius - sink
        half = math.sqrt(2 * radius * sink - sink * sink)
        arc = Edge(role="unknown", start=(0, -radius), end=(0, radius),
                   segment=CircleSeg(center=(0, 0), radius=radius,
                                  start_angle=-math.pi / 2, end_angle=math.pi / 2, ccw=True))
        line = _line((x, -half - 1), (x, half + 1))
        noded = split_at_crossings([arc, line], tolerance=tol)
        pieces_of = lambda parent: [p for p in noded.pieces if noded.parent_of(p) is parent]
        self.assertEqual(len(pieces_of(arc)), 2)
        self.assertEqual(len(pieces_of(line)), 2)


class TestContactDecidedOnce(unittest.TestCase):
    """every contact is decided once per pair, on the true curves, and gives a single
    node, the same tuple for every edge it touches."""

    def _pieces_of(self, noded, parent):
        return [p for p in noded.pieces if noded.parent_of(p) is parent]

    def test_t_within_the_threshold_shares_the_node(self):
        # the stem ends 0.0004 above the base, below SAME_POINT: the base is cut and
        # its node is the stem's end, not the rounded projection
        base, stem = _line((0, 0), (10, 0)), _line((5, 0.0004), (5, 5))
        noded = split_at_crossings([base, stem], tolerance=0.05)
        cuts = {p.end for p in self._pieces_of(noded, base)[:-1]}
        self.assertEqual(cuts, {stem.start})

    def test_t_on_a_spline_cuts_it(self):
        from topo.core.primitives.spline import BSplineSeg
        spline = BSplineSeg(degree=2, control_points=[(0, 0), (5, 2), (10, 0)],
                            knots=[0, 0, 0, 1, 1, 1])
        top = spline._evaluate(0.5)
        curve = Edge(role="unknown", start=(0.0, 0.0), end=(10.0, 0.0), segment=spline)
        stem = _line((round(top[0], 4), round(top[1] + 0.0002, 4)), (5, 8))
        noded = split_at_crossings([curve, stem], tolerance=0.05)
        halves = self._pieces_of(noded, curve)
        self.assertEqual(len(halves), 2)
        self.assertTrue(all(isinstance(p.segment, BSplineSeg) for p in halves))
        self.assertEqual(halves[0].end, stem.start)
        self.assertEqual(halves[1].start, stem.start)

    def test_missed_tangency_is_a_contact(self):
        # a line passes 0.0004 outside a circle (below SAME_POINT) without touching it:
        # a shared node, and the circle, touched once only, stays whole
        c, line = _circle((0, 0), 5), _line((-10, 5.0004), (10, 5.0004))
        noded = split_at_crossings([c, line], tolerance=0.05)
        self.assertEqual(len(self._pieces_of(noded, line)), 2)
        self.assertIn(c, noded.pieces)

    def test_two_near_t_stay_two_nodes_each_with_its_stem(self):
        # two stems 0.03 apart (< tolerance, > GRAPH_EPSILON): two contacts of different
        # pairs, two nodes, each equal to its stem
        base = _line((0, 0), (10, 0))
        a, b = _line((5, 0), (5, 5)), _line((5.03, 0), (5.03, -5))
        noded = split_at_crossings([base, a, b], tolerance=0.05)
        nodes = [p.end for p in self._pieces_of(noded, base)[:-1]]
        self.assertEqual(nodes, [a.start, b.start])

    def test_a_short_side_does_not_vanish(self):
        # a side of 0.008 between two lines: its two ends do not become a single node,
        # even if each is within GRAPH_EPSILON of the other
        left, short, right = _line((0, 0), (5, 0)), _line((5, 0), (5.008, 0)), _line((5.008, 0), (10, 3))
        noded = split_at_crossings([left, short, right], tolerance=0.05)
        piece = self._pieces_of(noded, short)
        self.assertEqual(len(piece), 1)
        self.assertNotEqual(piece[0].start, piece[0].end)


class TestRenode(unittest.TestCase):

    def test_nodes_from_the_real_point(self):
        # node rounded to 1 decimal, real point at 3: the node follows the real point
        e = Edge(role="unknown", start=(0.0, 0.0), end=(1.0, 0.0),
                 segment=LineSeg(start=(0.0, 0.0), end=(1.034, 0.0)))
        self.assertEqual(renode([e])[0].end, (1.034, 0.0))

    # a closed spline that crosses itself (a square with a curl on the bottom side),
    # of degree 1 so that the computations can be read by hand
    _CURL = [(0, 0), (40, 0), (60, -20), (50, -30), (40, -20), (60, 0),
             (100, 0), (100, 100), (0, 100), (0, 0)]

    def _curl_edge(self, end_shift):
        from topo.core.primitives.spline import BSplineSeg
        n = len(self._CURL)
        knots = [0.0, 0.0] + [k / (n - 1) for k in range(1, n - 1)] + [1.0, 1.0]
        seg = BSplineSeg(degree=1, control_points=self._CURL, knots=knots)
        return Edge(role="unknown", start=(0.0, 0.0), end=(end_shift, 0.0), segment=seg)

    def test_closed_curve_a_single_node(self):
        # an Edge written by hand (or rotated) with the end at 1e-13 from the start: the
        # curve is closed, the node is a single one as in Edge.of
        e = renode([self._curl_edge(1e-13)])[0]
        self.assertEqual(e.start, e.end)

    def test_outlines_does_not_depend_on_how_the_end_is_written(self):
        # before: exact end → a contour of 9900; end at 1e-13 → no contour, the whole
        # spline in loose and is_valid False
        import topo
        from dataclasses import replace
        exact = topo.load_segments([self._curl_edge(0.0).segment])
        shifted = replace(exact, edges=[self._curl_edge(1e-13)])
        areas = [[round(c.outer.area, 6) for c in topo.heal(d, max_gap=0.5).outlines().clusters]
                 for d in (exact, shifted)]
        self.assertEqual(areas[0], [9900.0])
        self.assertEqual(areas[1], areas[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNodesUnderMotion(unittest.TestCase):
    """`renode` rounded every end by itself. Two arcs of a polyline with bulge (step
    0.004 mm) have the common vertex in two copies 1 ulp apart; with a cell edge
    between them they become two nodes, and `decide_nodes` does not reunite them in
    a group wider than `epsilon`: the chain broke."""

    def test_a_vertex_on_a_cell_edge_stays_a_node(self):
        from collections import Counter
        import topo
        from tests.invariants import rigid
        from topo.core.topology.noding import decide_nodes
        pts = [(k * 0.004, 0.002 * math.sin(k * 0.7)) for k in range(60)]
        arcs = [CircleSeg.from_ends(a, b, 4 * math.atan(0.02 if i % 2 else -0.02)) for i, (a, b) in enumerate(zip(pts, pts[1:]))]
        # in place; the vertices midway between two 1e-3 cells; and rotated
        for motion in [(0.0, 0.0, 0.0), (0.0, 3000000.0005, -2500000.000476336),
                       (0.1, 3000000.0001767986, -2500000.0004505813)]:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                out, _ = decide_nodes(topo.load_segments([segment(a) for a in arcs]).edges)
                ends = Counter(n for e in out for n in (e.start, e.end))
                self.assertEqual(sorted(ends.values()).count(1), 2)


class TestEndContactsUnderMotion(unittest.TestCase):
    """a contact less than 1e-9 from an end (`at_end`, `_EPS`) and two nearly
    concentric arcs (`d < _EPS`). The two thresholds are near the noise; these
    cases, meant to break them, give the same pieces and the same nodes in place,
    rotated and far."""

    MOTIONS = [(0.031, 0.0, 0.0), (0.7, 3e6, -2.5e6), (2.294, 3e6, -2.5e6), (math.pi / 2, -7e5, 4e5)]

    def _reading(self, segs, motion):
        from collections import Counter
        import topo
        from tests.invariants import rigid
        segment, _ = rigid(*motion)
        out = split_at_crossings(topo.load_segments([segment(s) for s in segs]).edges, 0.5)
        nodes = Counter(n for e in out.pieces for n in (e.start, e.end))
        return len(out.pieces), sorted(nodes.values())

    def _same_at_every_motion(self, segs, at_rest):
        self.assertEqual(self._reading(segs, (0.0, 0.0, 0.0)), at_rest)
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                self.assertEqual(self._reading(segs, motion), at_rest)

    def test_t_on_the_end_of_a_stretch_shorter_than_node(self):
        # 0.008 < node (0.01): the case in which `_union` may refuse
        self._same_at_every_motion(
            [LineSeg(start=(0.0, 0.0), end=(0.008, 0.0)), LineSeg(start=(0.008, 0.0), end=(0.008, 5.0)),
             LineSeg(start=(0.0, 0.0), end=(0.0, -5.0))], (3, [1, 1, 2, 2]))

    def test_straight_on_the_end_of_a_short_arc(self):
        end = (0.05 * math.cos(0.15), 0.05 * math.sin(0.15))
        self._same_at_every_motion(
            [CircleSeg(center=(0.0, 0.0), radius=0.05, start_angle=0.0, end_angle=0.15),
             LineSeg(start=end, end=(3.0, 3.0))], (2, [1, 1, 2]))

    def test_nearly_concentric_arcs_within_node(self):
        for offset in (0.0, 0.8e-9, 1.2e-9, 3e-9, 1e-7):
            with self.subTest(offset=offset):
                c = (offset * math.cos(0.7), offset * math.sin(0.7))
                self._same_at_every_motion(
                    [CircleSeg(center=(0.0, 0.0), radius=5.0, start_angle=0.2, end_angle=1.2),
                     CircleSeg(center=c, radius=5.005, start_angle=0.0, end_angle=1.4)], self._reading(
                        [CircleSeg(center=(0.0, 0.0), radius=5.0, start_angle=0.2, end_angle=1.2),
                         CircleSeg(center=c, radius=5.005, start_angle=0.0, end_angle=1.4)], (0.0, 0.0, 0.0)))


class TestEndNodeUnderMotion(unittest.TestCase):
    """a node with several distinct entry ends was the smallest in (x, y), which a
    motion changes. The end of a line at (0.009, 0.009) from the end (0, 0) of
    another: at 0.009 from the curve, within `node` of its long end along it, the
    two ends are a node. In place it was (0, 0), at half a turn and at a quarter
    turn (0.009, 0.009)."""

    SEGMENTS = [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)),
                LineSeg(start=(0.009, 0.009), end=(0.009, 5.0)),
                LineSeg(start=(0.0, 0.0), end=(0.0, -5.0))]

    def _node(self, motion):
        """(the node near the two ends, the point's motion)."""
        import topo
        from tests.invariants import rigid
        segment, point = rigid(*motion)
        out = split_at_crossings(topo.load_segments([segment(s) for s in self.SEGMENTS]).edges, 0.5)
        nodes = {n for e in out.pieces for n in (e.start, e.end)}
        return min(nodes, key=lambda n: math.dist(n, point((0.0, 0.0)))), point

    def test_the_node_of_the_two_ends_does_not_depend_on_the_motion(self):
        at_rest, _ = self._node((0.0, 0.0, 0.0))
        for motion in [(math.pi, 0.0, 0.0), (math.pi / 2, 0.0, 0.0), (0.7, 3e3, -2e3)]:
            with self.subTest(motion=motion):
                node, point = self._node(motion)
                # within two cells of the node grid (1e-3), not 0.0127
                self.assertLess(math.dist(node, point(at_rest)), 2e-3)


class TestCrossingNodesUnderMotion(unittest.TestCase):
    """a node with no ends is the mean of its contact points rounded to the grid.
    Three lines, the third cuts the first two near their crossing: a tiny triangle
    with two crossing-vertices at 0.01074, two nodes. Rounded, at the motion below
    they are <= GRAPH_EPSILON apart and the graph (`cluster_points`) merged them:
    outer of 2 sides, the third in loose."""

    SEGMENTS = [
        LineSeg(start=(-0.4038192179613853, -0.9069697819400884), end=(0.3999047733007083, 0.9244307056293919)),
        LineSeg(start=(0.949814645702292, -0.31496011887135034), end=(-0.9430275941383344, 0.33091003454582124)),
        LineSeg(start=(0.013853742779737218, -0.004663352290131094), end=(-0.9611844021439172, 0.2173740678530485)),
    ]

    def test_two_crossings_beyond_graph_epsilon_stay_two_nodes(self):
        import topo
        from tests.invariants import rigid
        for motion in [(0.0, 0.0, 0.0), (0.8126685826151423, -0.5047703326061714, -0.21810059373354584)]:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                net = topo.heal(topo.load_segments([segment(s) for s in self.SEGMENTS]), max_gap=0.0)
                ends = Counter(q for e in split_at_crossings(net.edges, SAME_POINT).pieces for q in (e.start, e.end))
                # the two crossings are two nodes, each with the four half-sides arriving there;
                # the third end, at 0.0086 from the second line, no longer touches it
                self.assertEqual(sorted(n for n in ends.values() if n >= 3), [4, 4])
