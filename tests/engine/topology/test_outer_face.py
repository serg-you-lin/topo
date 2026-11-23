# tests/engine/topology/test_outer_face.py

import math
import unittest
from shapely.ops import polygonize, unary_union
from topo.core.topology.outer_face import _network, outer_face
from topo.core.topology.noding import split_at_crossings
from topo.core.topology.edge import Edge
from topo.core.topology.edge import node_point
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.line import LineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg
from topo import to_shapely


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _face(edges):
    return outer_face(split_at_crossings(edges, tolerance=0.05).pieces, epsilon=0.01)


class TestOuterFace(unittest.TestCase):

    def test_square_with_diagonal(self):
        # the diagonal divides the square into two faces: the outer contour is the square
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((0, 0), (10, 10))]
        face = _face(edges)
        self.assertAlmostEqual(to_shapely(face).area, 100.0)
        self.assertEqual(len(face.edges), 4)

    def test_axis_that_protrudes_is_a_protrusion(self):
        # an axis crossing the square and leaving by the two sides
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((-3, 5), (13, 5))]
        face = _face(edges)
        self.assertAlmostEqual(to_shapely(face).area, 100.0)
        self.assertEqual(len(face.spurs), 2)

    def test_l_with_recess(self):
        edges = _poly((0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10))
        self.assertAlmostEqual(to_shapely(_face(edges)).area, 64.0)

    def test_leftmost_point_mid_arc(self):
        # narrow view inside a circle that crosses it: the leftmost node is inside the
        # circle, the leftmost point is on the circle
        view = _poly((-1, -3), (1, -3), (1, 20), (-1, 20))
        circle = Edge(role="unknown", start=(8, 0), end=(8, 0),
                      segment=CircleSeg(center=(0, 0), radius=8))
        face = _face(view + [circle])
        self.assertGreater(to_shapely(face).area, 3.14 * 64)
        # the part of the view that leaves above the circle is contour
        self.assertGreater(to_shapely(face).bounds[3], 19.9)

    def test_no_ambit(self):
        self.assertIsNone(_face([_line((0, 0), (5, 0))]))


class TestContactsByDistance(unittest.TestCase):
    """A square with the base side made of a spline and the vertical sides ending
    0.0004 above it (below SAME_POINT): the noding does not split the spline, the
    face closes only in the union of the faces. The contact holds by distance,
    wherever the drawing sits: a grid fixed to the axes sewed it only if the two
    points fell in the same cell."""

    def _square(self, move):
        base = BSplineSeg(2, [(-5.0, 0.0), (5.0, 0.0), (15.0, 0.0)], [0, 0, 0, 1, 1, 1])
        sides = [LineSeg(start=(0.0, 0.0004), end=(0.0, 10.0)), LineSeg(start=(0.0, 10.0), end=(10.0, 10.0)),
                 LineSeg(start=(10.0, 10.0), end=(10.0, 0.0004))]
        edges = []
        for seg in [move(base)] + [move(s) for s in sides]:
            start, end = segment_endpoints(seg)
            edges.append(Edge(role="unknown", start=node_point(start), end=node_point(end), segment=seg))
        return _face(edges)

    def test_moved_by_fractions_of_a_cell(self):
        for dy in (0.0, 0.0002, 0.0004, 0.0006, 0.0008):
            with self.subTest(dy=dy):
                face = self._square(lambda s: s.translated(0.0, dy))
                self.assertAlmostEqual(to_shapely(face).area, 100.0, delta=0.1)

    def test_rotated(self):
        for angle in (0.3, 0.7, 1.1, 2.0):
            with self.subTest(angle=angle):
                face = self._square(lambda s: s.rotated(angle))
                self.assertAlmostEqual(to_shapely(face).area, 100.0, delta=0.1)

    def test_straight_grazing_a_circle(self):
        # a V with the inscribed circle, the sides miss it by 0.0004 (below SAME_POINT):
        # the tip between the V and the circle is a closed face of the network. The
        # network is looked at and not the contour: here no edge lies wholly on the
        # border of the union and the fallback makes no loop of it (TODO, 1.x)
        r, d = 1.0, 1.0 / math.sin(math.radians(20)) + 0.0004 / math.sin(math.radians(20))
        apex = (d, 0.0)
        ends = [(d - 6 * math.cos(math.radians(a)), -6 * math.sin(math.radians(a))) for a in (20, -20)]
        ends = [node_point(p) for p in ends]
        circle = Edge(role="unknown", start=(r, 0.0), end=(r, 0.0), segment=CircleSeg(center=(0.0, 0.0), radius=r))
        edges = [_line(ends[0], node_point(apex)), _line(node_point(apex), ends[1]), circle]
        for angle in (0.0, 0.7):
            with self.subTest(angle=angle):
                moved = []
                for e in edges:
                    seg = e.segment.rotated(angle)
                    start, end = segment_endpoints(seg)
                    moved.append(Edge(role="unknown", start=node_point(start), end=node_point(end), segment=seg))
                pieces = split_at_crossings(moved, tolerance=0.05).pieces
                area = unary_union(list(polygonize(_network(pieces, 0.01)))).area
                self.assertGreater(area, math.pi * r * r + 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestOverlapFromANodeUnderMotion(unittest.TestCase):
    """a ~0 turn (an edge that restarts along the one it arrived by) would be decided
    by the sign of the noise, and happens only with two edges overlapping from a
    node. Here they are: the two readings give the same answer in place, rotated
    and far. Measured on 1 November with a trace: the overlap is removed before the
    faces, and the line fires only on the arrival edge (36 times out of 36), never on another."""

    def test_faces_and_outlines_do_not_depend_on_the_motion(self):
        import topo
        from tests.invariants import rigid
        from topo.core.primitives.line import LineSeg
        # triangle with the base side doubled from the node (0, 0): 10 mm and 20 mm overlapping
        segs = [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)), LineSeg(start=(0.0, 0.0), end=(20.0, 0.0)),
                LineSeg(start=(20.0, 0.0), end=(10.0, 10.0)), LineSeg(start=(10.0, 10.0), end=(0.0, 0.0)),
                LineSeg(start=(10.0, 0.0), end=(10.0, 10.0))]
        readings = {"faces": lambda d: topo.heal(d).faces(),
                    "outlines": lambda d: topo.heal(d, max_gap=0.5).outlines()}

        def reading(read, motion):
            segment, _ = rigid(*motion)
            r = read(topo.load_segments([segment(s) for s in segs]))
            return r.is_valid, len(r.clusters), [len(c.inners) for c in r.clusters], len(r.loose), \
                sum(c.outer.area for c in r.clusters)

        for name, read in readings.items():
            at_rest = reading(read, (0.0, 0.0, 0.0))
            self.assertEqual(at_rest[:4], (True, 1, [0], 1), name)
            for motion in ((0.031, 0.0, 0.0), (0.7, 0.0, 0.0), (0.7, 3e6, -2.5e6), (2.294, 3e6, -2.5e6)):
                with self.subTest(reading=name, motion=motion):
                    moved = reading(read, motion)
                    self.assertEqual(moved[:4], at_rest[:4])
                    self.assertAlmostEqual(moved[4], at_rest[4], delta=1e-2)   # the node grid, far


class TestFirstStepUnderMotion(unittest.TestCase):
    """on a vertical left side the leftmost points tie and the last bit chooses the
    first; on the traced drawings it happens 938 times out of 2964
    (`probe_first_step.py`). `going_down` instead does not reach the noise (minimum
    |dy| 0.004 mm, 461 interior branches). Proof: the loop starts from different
    nodes depending on the motion (checked) and the passes per piece are the same —
    whoever consumes them (`outer_face`, `non_contour_edges`) counts, does not look
    at where it starts. It does not prove a tie between points of two different components."""

    # rotations of 1e-12: the left side leans one way or the other, within the noise
    MOTIONS = [(1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0), (1e-12, 0.3, -0.2), (-1e-12, 0.3, -0.2)]

    def test_different_starts_same_passes(self):
        from tests.invariants import rigid
        from topo.core.topology.graph import build_node_graph
        from topo.core.topology.outer_face import _first_step, outer_face_passes
        # square with a chord from (0, 5) and a protrusion beyond the right side
        base = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((0, 5), (13, 5))]
        starts, readings = set(), []
        for motion in self.MOTIONS:
            move_seg, move_pt = rigid(*motion)
            edges = [Edge(role="unknown", start=move_pt(e.start), end=move_pt(e.end),
                          segment=move_seg(e.segment)) for e in base]
            pieces = split_at_crossings(edges, tolerance=0.05).pieces
            graph = build_node_graph(pieces, sliver=0.01)
            (component,) = graph.connected_components()
            starts.add(tuple(round(c - d, 6) for c, d in zip(_first_step(graph, component)[1], motion[1:])))
            passes = outer_face_passes(graph, component, len(pieces))
            readings.append(sorted(
                (tuple(round((a + b) / 2 - d, 6) for a, b, d in zip(p.start, p.end, motion[1:])),
                 passes.get(id(p), 0)) for p in pieces))
        self.assertGreater(len(starts), 1)            # the tie is really there
        for r in readings[1:]:
            self.assertEqual(r, readings[0])
        self.assertIn(2, [n for _, n in readings[0]])  # la sporgenza, due volte
        self.assertIn(0, [n for _, n in readings[0]])  # la corda, mai


class TestUnionGridUnderMotion(unittest.TestCase):
    """(`UNION_GRID`): the fallback's network grid. On the 31 `outlines()` drawings
    it works only on the duplicates at 1e-12 (here the two circles of an anchored
    drawing): with the grid they coincide, without they cross where the last bit
    says. Proof: the grid really changes the network (value checked in place), and
    the reading is the same at every motion and without the grid. It does not prove
    the 1e-6 window between two distinct curves: there `_network` decides first
    with the ends on the tuples (an item of its own)."""

    CIRCLES = [CircleSeg(center=(67.6769804197, 260.3946312001), radius=0.5325),
               CircleSeg(center=(67.67698041971678, 260.3946312001228), radius=0.5325000000015537)]
    MOTIONS = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.13, 3.1, -7.9), (2.4, -0.37, 0.61),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def test_the_grid_works_on_the_duplicates(self):
        import shapely
        from topo.core.topology.graph import build_node_graph
        from topo.core.topology.outer_face import UNION_GRID, _on_nodes
        edges = [Edge(role="unknown", start=node_point(segment_endpoints(s)[0]),
                      end=node_point(segment_endpoints(s)[1]), segment=s)
                 for s in self.CIRCLES]
        lines = _on_nodes(edges, build_node_graph(edges, sliver=0.01))
        on_grid = len(shapely.unary_union(lines, grid_size=UNION_GRID).geoms)
        exact = len(shapely.unary_union(lines).geoms)
        self.assertEqual(on_grid, len(lines[0].coords) - 1)   # i due poligoni coincidono vertice per vertice
        self.assertLess(exact, 10)      # without a grid: few crossings at the last bit

    def test_the_reading_depends_neither_on_the_grid_nor_on_the_motion(self):
        from unittest import mock
        import topo
        from topo.core.topology import outer_face as module
        from tests.invariants import rigid
        areas = set()
        for motion in self.MOTIONS:
            segment, _ = rigid(*motion)
            for grid in (module.UNION_GRID, None):
                with self.subTest(motion=motion, grid=grid), mock.patch.object(module, "UNION_GRID", grid):
                    result = topo.heal(topo.load_segments([segment(s) for s in self.CIRCLES]), max_gap=0.0).outlines()
                    self.assertEqual(len(result.clusters), 1)
                    self.assertEqual(len(result.loose), 0)   # the duplicates are a single circle
                    areas.add(round(to_shapely(result.clusters[0].outer).area, 9))
        self.assertEqual(len(areas), 1)   # the same circle in every motion, with and without the grid


class TestChordContactUnderMotion(unittest.TestCase):
    """`outer_face._network`: the fallback redoes the noding on the discretizations
    with the ends on the tuples. F1 has an arc bite with sagitta just below
    `SAME_POINT`; the corner of triangle F2 is `SAME_POINT` + 2e-6 from the true
    arc, above `GRAPH_EPSILON` and beyond the 2e-6 chord: the noding does not touch
    them, but in place the corner's tuple went past the chord and the union welded
    F1 and F2 only with the node grid; without it F2 stays in loose at every motion."""

    N = 64
    MOTIONS = [(0.0, 0.0, 0.0), (0.0, 3e-7, 0.0), (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6), (0.7, 0.0, 0.0)]

    def _segments(self):
        from topo.core.primitives.conics import CircleSeg
        step = 2 * math.pi / self.N
        from topo.precision import FLOAT_NOISE, SAME_POINT
        r = SAME_POINT * (1 - 1e-8) / (1 - math.cos(step / 2))
        a = math.pi / 4
        p1, p2 = (-r * math.cos(a), -r * math.sin(a)), (r * math.cos(a), -r * math.sin(a))
        alpha = 48.5 * step
        d = SAME_POINT + 2 * FLOAT_NOISE
        q = ((r - d) * math.cos(alpha), (r - d) * math.sin(alpha))
        return [CircleSeg(center=(0.0, 0.0), radius=r, start_angle=5 * a, end_angle=7 * a, ccw=True),
                LineSeg(start=p2, end=(p2[0], -r - 3)), LineSeg(start=(p2[0], -r - 3), end=(p1[0], -r - 3)),
                LineSeg(start=(p1[0], -r - 3), end=p1),
                LineSeg(start=q, end=(q[0] + 1, q[1] + 2)), LineSeg(start=(q[0] + 1, q[1] + 2), end=(q[0] - 1, q[1] + 2)),
                LineSeg(start=(q[0] - 1, q[1] + 2), end=q)]

    def test_the_contact_on_the_chord_does_not_depend_on_the_motion(self):
        import topo
        from tests.invariants import rigid
        readings = []
        for motion in self.MOTIONS:
            segment, _ = rigid(*motion)
            result = topo.heal(topo.load_segments([segment(s) for s in self._segments()]), max_gap=0.05).outlines()   # the threshold from before the single-threshold change
            readings.append((len(result.clusters), len(result.loose),
                             round(to_shapely(result.clusters[0].outer).area, 1)))
        self.assertEqual(set(readings), {(1, 1, 3.6)}, readings)
