"""
tests/engine/readings/test_heal_steps.py
----------------------------------
The steps of heal() used on their own, as a consumer composing their own
recipe uses them — and the composition in heal()'s order that gives the same
result as heal().
"""

import math
import unittest
from dataclasses import replace


import topo
import topo_dxf
from topo.model.document import Document
from topo.model.curve import ClosedCurve, OpenCurve
from topo.model.role import ContourRole
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg, EllipseSeg
from topo import to_shapely
from topo.precision import SAME_POINT
from tests.paths import DATA, drawing

EXAMPLES = DATA


def _line(p1, p2, role=ContourRole.UNKNOWN, decimals=3):
    r = lambda p: (round(p[0], decimals), round(p[1], decimals))
    return Edge(role=role, start=r(p1), end=r(p2), segment=LineSeg(start=p1, end=p2))


def _square(x0, y0, side, role=ContourRole.UNKNOWN):
    pts = [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]
    return [_line(pts[i], pts[(i + 1) % 4], role) for i in range(4)]


def _circle(center, radius, role=ContourRole.UNKNOWN):
    pt = (center[0] + radius, center[1])
    return Edge(role=role, start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _broken_square(spur=False):
    # Broken bottom-right corner: 10.03 vs 10.14, nodes at 1 decimal 10.0 vs 10.1 — only the repair via clustering closes it.
    edges = [_line((0.0, 0.0), (10.03, 0.0), decimals=1),
             _line((10.14, 0.0), (10.14, 10.0), decimals=1),
             _line((10.14, 10.0), (0.0, 10.0), decimals=1),
             _line((0.0, 10.0), (0.0, 0.0), decimals=1)]
    if spur:
        # third end in the same cluster: pairwise repair not defined
        edges.append(_line((10.06, 0.0), (10.06, -5.0), decimals=1))
    return edges


class TestSplitLabeled(unittest.TestCase):

    def test_001_non_structural_role_set_aside(self):
        mark = _line((2, 2), (5, 5), role="engrave")
        kept, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [mark])
        self.assertEqual(len(kept), 4)
        self.assertEqual(labeled, [mark])

    def test_002_hole_stays_with_the_callers_predicate(self):
        # without a predicate a "hole" is not structural, with the caller's predicate
        # that recognizes it it is
        hole = _circle((5, 5), 1, role="hole")
        _, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [hole])
        self.assertEqual(labeled, [hole])
        is_structural = lambda role: topo.is_structural_role(role) or role == "hole"
        kept, labeled = topo.experimental.split_labeled(_square(0, 0, 10) + [hole], is_structural)
        self.assertEqual(labeled, [])
        self.assertIn(hole, kept)


class TestCloseFreeGaps(unittest.TestCase):

    def test_001_gap_below_tolerance_closed(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9.95, 0))
        # before no face, after one
        self.assertEqual(topo.experimental.face_loops(edges), [])
        self.assertEqual(len(topo.experimental.face_loops(topo.experimental.close_free_gaps(edges, 0.1))), 1)

    def test_002_gap_above_tolerance_intact(self):
        edges = _square(0, 0, 10)
        edges[0] = _line((0, 0), (9, 0))
        self.assertEqual(topo.experimental.close_free_gaps(edges, 0.1), edges)

    def test_004_end_of_an_ellipse_arc_closes_like_a_spline_end(self):
        # half ellipse closed by a line arriving 0.003 from its end (og_04 with the
        # ellipse refit): the ellipse's end is free like the others
        half = EllipseSeg(center=(0.0, 0.0), major_axis=(4.0, 0.0), ratio=0.5, start_param=0.0, end_param=math.pi)
        a, b = segment_endpoints(half)
        edges = [Edge(role=ContourRole.UNKNOWN, start=a, end=b, segment=half), _line((b[0], b[1]), (a[0] - 0.003, a[1]))]
        self.assertEqual(topo.experimental.face_loops(edges), [])
        self.assertEqual(len(topo.experimental.face_loops(topo.experimental.close_free_gaps(edges, 0.05))), 1)

    def test_003_parallels_close_with_the_segment_at_each_angle(self):
        # (drw_0015): two parallel lines with the ends at 0.004. Rotated, the exact
        # parallelism is lost in the last bit and the "meeting" fell at 1e10 mm; a
        # meeting beyond the tolerance is a segment. Far from the origin, as in the
        # drawing: there the rotation's error exceeds 1e-10
        for angle in (0.0, 0.7, 0.13, math.pi / 2):
            pieces = [LineSeg(start=(-71610.7, -3035.024), end=(-71537.6, -3035.024)),
                      LineSeg(start=(-71537.6, -3035.028), end=(-71513.2, -3035.028))]
            edges = [_line(s.start, s.end) for s in (p.rotated(angle) for p in pieces)]
            healed = topo.experimental.close_free_gaps(edges, 0.5)
            self.assertEqual(len(healed), 3, angle)
            for before, after in zip(edges, healed):
                self.assertLess(math.dist(before.segment.end, after.segment.end), 0.5, angle)
                self.assertLess(math.dist(before.segment.start, after.segment.start), 0.5, angle)


class TestDanglingSplines(unittest.TestCase):

    def test_001_spline_with_free_end(self):
        spline = Edge(role=ContourRole.UNKNOWN, start=(0.0, 0.0), end=(5.0, 5.0),
                      segment=BSplineSeg(degree=1, control_points=[(0.0, 0.0), (5.0, 5.0)],
                                        knots=[0, 0, 1, 1]))
        self.assertEqual(topo.experimental.dangling_splines([spline]), [spline])
        self.assertEqual(topo.experimental.dangling_splines(_square(0, 0, 10)), [])


class TestFindNonContourEdges(unittest.TestCase):

    def test_001_diagonale_interna_esclusa(self):
        diagonal = _line((0.0, 0.0), (1.0, 2.0))
        edges = [_line((0.0, 0.0), (1.0, 0.0)), _line((1.0, 0.0), (1.0, 2.0)),
                 _line((1.0, 2.0), (0.0, 2.0)), _line((0.0, 2.0), (0.0, 0.0)), diagonal]
        self.assertEqual(topo.experimental.find_non_contour_edges(edges, 0.01), {id(diagonal)})

    def test_002_line_between_two_squares_excluded(self):
        # walked back and forth by the outer border: it is nobody's contour
        joint = _line((10.0, 10.0), (20.0, 20.0))
        edges = _square(0, 0, 10) + _square(20, 20, 10) + [joint]
        self.assertEqual(topo.experimental.find_non_contour_edges(edges, 0.01), {id(joint)})


class TestLooseEnds(unittest.TestCase):
    """Two squares joined by a line, plus a stub 3 mm from a vertex: the scheme of F6."""

    def setUp(self):
        self.joint = _line((10.0, 10.0), (20.0, 20.0))
        self.stub = _line((10.0, 0.0), (13.0, -4.0))
        self.chord = _line((0.0, 0.0), (10.0, 10.0))
        self.edges = _square(0, 0, 10) + _square(20, 20, 10) + [self.joint, self.stub]

    def test_001_line_joining_two_shapes(self):
        candidates = topo.experimental.find_non_contour_edges(self.edges + [self.chord], 0.01)
        self.assertEqual(topo.experimental.find_joining_edges(self.edges + [self.chord], candidates), [self.joint],
                         "the diagonal of a square is a chord, it joins nothing")

    def test_002_estremo_libero_e_distanza(self):
        ends = topo.experimental.free_ends(self.edges)
        self.assertEqual([p for p, _ in ends], [(13.0, -4.0)])
        self.assertAlmostEqual(ends[0][1], 5.0)

    def test_003_heal_says_them(self):
        result = topo.heal(Document(edges=self.edges, source_meta={"tolerance": 0.05})).faces()
        self.assertEqual(result.cluster_count, 2)
        self.assertIn("free-end", [n.code for n in result.notes])
        self.assertIn("joining-edge", [n.code for n in result.notes])

    def test_004_clean_piece_no_warning(self):
        result = topo.heal(Document(edges=_square(0, 0, 10), source_meta={"tolerance": 0.05})).faces()
        self.assertEqual(result.warnings, [])

    def test_005_end_merged_by_the_tolerant_graph_is_not_free(self):
        # the broken corner is closed only by the tolerant graph: on its nodes the two
        # ends of the corner are one, the stub stays free
        edges = _broken_square(spur=True)
        self.assertEqual([p for p, _ in topo.experimental.free_ends(edges)], [(10.0, 0.0), (10.1, -5.0)])
        self.assertEqual([p for p, _ in topo.experimental.free_ends(edges, epsilon=0.1)], [(10.1, -5.0)])


def _arc(radius, missing_deg, center=(0.0, 0.0)):
    half = math.radians(missing_deg) / 2
    return CircleSeg(center, radius, half, 2 * math.pi - half)


class TestShortElementsAndTolerance(unittest.TestCase):
    """the tolerance measures a gap, not the length of a side. 100 square with the
    top-right corner filleted/chamfered, detached by 0.3 at the two ends, tol 1:
    the neighbouring sides are within tol of each other, but each has the end of
    the short element nearer."""

    GAP = 0.3

    def _heal(self, corner, a, b):
        g = self.GAP
        segs = [LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, a - g)), corner,
                LineSeg((b - g, 100), (0, 100)), LineSeg((0, 100), (0, 0))]
        return topo.heal(topo.load_segments(segs), max_gap=1.0).faces()

    def test_001_fillet_remains(self):
        result = self._heal(CircleSeg((99.6, 99.6), 0.4, 0, math.pi / 2), 99.6, 99.6)
        self.assertEqual(result.cluster_count, 1)
        outer = result.clusters[0].outer
        self.assertIn("CircleSeg", [type(s).__name__ for s in outer.segments])
        self.assertAlmostEqual(outer.area, 10000 - (0.4 ** 2 - math.pi * 0.4 ** 2 / 4), places=3)

    def test_002_chamfer_remains(self):
        c = 0.5 / math.sqrt(2)
        result = self._heal(LineSeg((100, 100 - c), (100 - c, 100)), 100 - c, 100 - c)
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].outer.area, 10000 - c * c / 2, places=3)

    def test_003_every_end_closes_a_single_gap(self):
        # three ends within tol: the two nearest pair up, the third stays free
        edges = [_line((0, 0), (10, 0)), _line((10.2, 0), (20, 0)), _line((10.5, 0.6), (10.5, 10))]
        healed = topo.experimental.close_free_gaps(edges, 1.0)
        self.assertEqual(len(topo.experimental.free_ends(healed)), 4, "the two outer ends and the two of the stub")


class TestGapAtTolerance(unittest.TestCase):

    def test_gap_as_wide_as_the_tolerance_closes_at_every_motion(self):
        # (regr_03): a hole with a 0.5 wide slot, tolerance 0.5. The comparison
        # `d <= tol` was decided by the last bit, different at every motion; within the
        # tolerance it includes it up to the noise
        from tests.invariants import MOTIONS, moved
        hole = [LineSeg(start=(52.659, 60.616), end=(60.0, 60.616)),
                LineSeg(start=(60.0, 60.616), end=(60.0, 70.0)),
                LineSeg(start=(60.0, 70.0), end=(45.0, 70.0)),
                LineSeg(start=(45.0, 70.0), end=(45.0, 60.616)),
                LineSeg(start=(45.0, 60.616), end=(52.159, 60.616))]
        plate = topo.geometry.rectangle(100, 100, center=(50, 60))
        doc = topo.load_segments(plate + hole)
        for name, move, _, _ in [("in place", lambda s: s, None, None)] + MOTIONS:
            result = topo.heal(moved(doc, move), max_gap=0.5).faces()
            self.assertEqual([len(c.inners) for c in result.clusters], [1], name)


def _closed_reading(doc, back):
    """The edges after close_free_gaps, brought back to the starting frame."""
    from shapely.geometry import LineString
    healed = topo.experimental.close_free_gaps(list(doc.edges), 0.5)
    return sorted(tuple(c for p in back(LineString(e.segment.discretize())).coords for c in p)
                  for e in healed)


def _same_at_every_motion(test, doc):
    from tests.invariants import MOTIONS, moved
    def same(a, b):
        return len(a) == len(b) and max(abs(u - v) for u, v in zip(a, b)) < 1e-6

    base = _closed_reading(doc, lambda g: g)
    for name, move, back, _ in MOTIONS:
        again = _closed_reading(moved(doc, move), back)
        # sets compared by nearness: sorting coordinates with the noise of a motion
        # would again be an order decided by the last bit
        test.assertEqual(len(again), len(base), name)
        test.assertTrue(all(any(same(a, b) for b in base) for a in again), name)
        test.assertTrue(all(any(same(a, b) for a in again) for b in base), name)
    return base


class TestTiedGapPartners(unittest.TestCase):

    def test_end_with_two_ends_at_the_same_distance_does_not_choose(self):
        # an end pointing between two symmetric free ends, at 0.316 from both, with no
        # curve in its way: two equally good partners, none chosen, and heal() says so
        x, y = -71565.8225, -3048.0985
        pieces = [LineSeg(start=(x + 3, y + 0.3), end=(x, y + 0.3)),
                  LineSeg(start=(x - 0.1, y - 5), end=(x - 0.1, y)),
                  LineSeg(start=(x - 0.1, y + 5.6), end=(x - 0.1, y + 0.6))]
        doc = topo.load_segments(pieces)
        _same_at_every_motion(self, doc)
        self.assertIn("tie", [w.code for w in topo.heal(doc, max_gap=0.5).faces().warnings])


class TestGapOntoCurve(unittest.TestCase):

    def test_the_end_closes_on_the_nearest_curve(self):
        # (drw_0015): the low end of the vertical stretch is 0.125 from the horizontal
        # stretch and 0.28 from its two ends: it closes on the stretch, as a T, at
        # every motion
        x, y = -71565.8225, -3048.0985
        pieces = [LineSeg(start=(x - 0.25, y), end=(x + 0.25, y)),
                  LineSeg(start=(x - 0.25, y + 0.375), end=(x + 0.25, y + 0.375)),
                  LineSeg(start=(x, y + 0.125), end=(x, y + 0.625))]
        doc = topo.load_segments(pieces)
        base = _same_at_every_motion(self, doc)
        stem = next(e for e in base if abs(e[0] - x) < 1e-6 and abs(e[2] - x) < 1e-6)
        self.assertAlmostEqual(min(stem[1], stem[3]), y, places=6)

    def test_two_meetings_on_the_continuation_the_first_wins(self):
        # (`min` over the meetings): the continued line cuts the circle at 0.2 and 0.4,
        # the end goes to 0.2 at every motion. Proof: the line chooses between two
        # meetings (counted in place) and the choice does not change. There is no tie
        # between distinct points to prove: on the continuation (line, or arc up to a
        # quarter turn) the distance from the end grows along the curve, two meetings at
        # the same distance are the same point; the tangent gives a single point. On the
        # traced drawings the line never chooses (a single meeting, 14314 calls). The
        # line's end is compared: the circle's discretization rotates with its angular grid.
        from unittest import mock
        from shapely.geometry import Point
        from tests.invariants import MOTIONS, moved
        from topo.core.base import gaps
        x, y = -71565.8225, -3048.0985
        doc = topo.load_segments([LineSeg(start=(x - 5, y), end=(x, y)),
                                  CircleSeg(center=(x + 0.3, y), radius=0.1)])
        counts = []
        real = gaps.intersections

        def counted(a, b, *args, **kwargs):
            hits = real(a, b, *args, **kwargs)
            counts.append(len(hits))
            return hits

        for name, move, back, _ in [("in place", lambda d: d, lambda g: g, None)] + list(MOTIONS):
            counts.clear()
            with mock.patch.object(gaps, "intersections", counted):
                healed = topo.experimental.close_free_gaps(list(moved(doc, move).edges), 0.5)
            self.assertIn(2, counts, name)
            ends = [back(Point(e.segment.end)).coords[0] for e in healed if isinstance(e.segment, LineSeg)]
            self.assertEqual(len(ends), 1, name)
            self.assertAlmostEqual(ends[0][0], x + 0.2, places=6, msg=name)
            self.assertAlmostEqual(ends[0][1], y, places=6, msg=name)

    def test_a_broken_corner_closes_at_the_corner(self):
        # the two lines meet at the true corner: the one from before, which outlines()
        # did not close, now the same in both readings
        pieces = [LineSeg(start=(0, 0), end=(99.9, 0)), LineSeg(start=(100, 0.1), end=(100, 50)),
                  LineSeg(start=(100, 50), end=(0, 50)), LineSeg(start=(0, 50), end=(0, 0))]
        doc = topo.load_segments(pieces)
        for result in (topo.heal(doc, max_gap=0.5).faces(), topo.heal(doc, max_gap=0.5).outlines()):
            self.assertEqual([round(to_shapely(c.outer).area, 3) for c in result.clusters], [5000.0])


class TestArcLineMeetUnderMotion(unittest.TestCase):
    """`intersections.closest_to`: an arc ending at its apex and a line cutting the
    circle 0.05 below. The two meetings are at the same distance from the arc's
    end: before the last bit won (±0.312 depending on the motion). Now the
    distance from the line's end decides, and if that too is equal the gap closes
    with the bridge between the two ends. It proves the choice in place (two equal
    candidates on the arc's end, counted) and at six motions. On the traced
    drawings the minimum gap between the two candidates is 2.08 mm: nothing changes there."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (math.pi / 2, 0.0, 0.0), (2.1, -1e5, 3e4)]

    def _closed(self, motion, offset):
        from unittest import mock
        from tests.invariants import rigid
        from topo.core.base import gaps
        from topo.core.geometry.measure import FLOAT_NOISE
        from topo.core.primitives.mathseg import segment_endpoints
        x, y = -71565.8225, -3048.0985
        move_seg, move_pt = rigid(*motion)
        pieces = [CircleSeg(center=(x, y), radius=1.0, start_angle=0.0, end_angle=math.pi / 2, ccw=True),
                  LineSeg(start=(x - 5, y + 0.95), end=(x + offset, y + 0.95))]
        doc = topo.load_segments([move_seg(p) for p in pieces])
        tied = []
        real = gaps.closest_to

        def counted(candidates, ref, *rest):
            d = [math.dist(q, ref) for q in candidates]
            tied.append(len(d) == 2 and abs(d[0] - d[1]) <= FLOAT_NOISE)
            return real(candidates, ref, *rest)

        with mock.patch.object(gaps, "closest_to", counted):
            healed = topo.experimental.close_free_gaps(list(doc.edges), 0.5)
        self.assertEqual(tied, [True], motion)
        a, tx, ty = motion
        c, s = math.cos(-a), math.sin(-a)
        back = lambda p: (c * (p[0] - tx) - s * (p[1] - ty) - x, s * (p[0] - tx) + c * (p[1] - ty) - y)
        return [(type(e.segment).__name__, *(round(v, 6) + 0.0 for p in segment_endpoints(e.segment)
                                              for v in back(p))) for e in healed]

    def test_line_end_midway_bridge_at_every_motion(self):
        for motion in self.MOTIONS:
            closed = self._closed(motion, 0.0)
            self.assertEqual(len(closed), 3, motion)
            bridges = [{e[1:3], e[3:5]} for e in closed if e[0] == "LineSeg"]
            self.assertIn({(0.0, 0.95), (0.0, 1.0)}, bridges, motion)

    def test_line_end_aside_the_meeting_from_its_side(self):
        for motion in self.MOTIONS:
            closed = self._closed(motion, -0.1)
            self.assertEqual(len(closed), 2, motion)
            line = next(e for e in closed if e[0] == "LineSeg")
            self.assertEqual(line[3:], (-0.31225, 0.95), motion)


class TestCloseNearFullArcs(unittest.TestCase):
    """an arc becomes a circle only if the gap is within tolerance (it is a gap) AND
    the missing angle is within the threshold (it is a circle)."""

    def _close(self, seg, tolerance, **kw):
        doc = topo.load_segments([seg])
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), tolerance, **kw)
        return type(edges[0].segment).__name__, n

    def test_001_broken_export_becomes_circle(self):
        self.assertEqual(self._close(_arc(3.0, 0.4), 0.05), ("CircleSeg", 1))

    def test_002_gap_within_tol_but_not_a_circle(self):
        self.assertEqual(self._close(_arc(0.4, 90), 1.0), ("CircleSeg", 0), "a small three-quarter")
        self.assertEqual(self._close(_arc(10.0, 2.9), 1.0), ("CircleSeg", 0))

    def test_003_near_circle_but_gap_beyond_tol(self):
        self.assertEqual(self._close(_arc(500.0, 1.5), 0.1), ("CircleSeg", 0))

    def test_004_angle_only_at_the_callers_choice(self):
        self.assertEqual(self._close(_arc(500.0, 1.5), math.inf), ("CircleSeg", 1))

    def test_005_linked_end_does_not_close(self):
        arc = _arc(10.0, 1.0)
        end = arc._point_at(arc.end_angle)
        doc = topo.load_segments([arc, LineSeg(end, (end[0] + 5, end[1]))])
        _, n = topo.experimental.close_near_full_arcs(list(doc.edges), 1.0)
        self.assertEqual(n, 0)

    def _close_all(self, segs, tolerance):
        doc = topo.load_segments(segs)
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), tolerance)
        return [type(e.segment).__name__ for e in edges], n

    def test_008_two_arcs_with_holes_below_2_degrees_are_a_circle(self):
        # every hole (1.72°, chord 0.15) is within tolerance and below 2°
        arcs = [CircleSeg((0, 0), 5, 0.015, math.pi - 0.015), CircleSeg((0, 0), 5, math.pi + 0.015, 2 * math.pi - 0.015)]
        self.assertEqual(self._close_all(arcs, 0.5), (["CircleSeg"], 1))

    def test_009_hole_of_1_joins_the_one_of_3_stays_open(self):
        # the 1° hole closes, the arcs are a single arc open by 3°
        h = lambda deg: math.radians(deg) / 2
        arcs = [CircleSeg((0, 0), 5, h(1), math.pi - h(3)), CircleSeg((0, 0), 5, math.pi + h(3), 2 * math.pi - h(1))]
        doc = topo.load_segments(arcs)
        edges, n = topo.experimental.close_near_full_arcs(list(doc.edges), 0.5)
        self.assertEqual((len(edges), n), (1, 1))
        self.assertAlmostEqual(math.degrees(2 * math.pi - edges[0].segment._sweep()), 3.0)
        self.assertNotEqual(edges[0].start, edges[0].end)

    def test_010_two_arcs_beyond_tolerance_do_not_make_the_circle(self):
        arcs = [CircleSeg((0, 0), 5, 0.015, math.pi - 0.015), CircleSeg((0, 0), 5, math.pi + 0.015, 2 * math.pi - 0.015)]
        self.assertEqual(self._close_all(arcs, 0.1), (["CircleSeg", "CircleSeg"], 0))

    def test_007_corner_tip_with_merged_ends_does_not_close(self):
        # the two ends fall in the same node, but two sides arrive at that node
        arc = _arc(1.5, 0.01)
        a, b = arc._point_at(arc.start_angle), arc._point_at(arc.end_angle)
        # without a grid the ends at 0.00026 mm stay two points: the single node comes
        # from a union of nodes, written by hand here
        node = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        edges = [Edge.of(LineSeg((20, 0.3), a), ContourRole.UNKNOWN), Edge.of(arc, ContourRole.UNKNOWN),
                 Edge.of(LineSeg(b, (20, -0.3)), ContourRole.UNKNOWN)]
        edges = [replace(edges[0], end=node), replace(edges[1], start=node, end=node),
                 replace(edges[2], start=node)]
        _, n = topo.experimental.close_near_full_arcs(edges, 0.1)
        self.assertEqual(n, 0)

    # from a brute force (seed 1468): a circle r 1.95 in two arcs joined at one
    # end, a 3.5° hole (chord 0.12) on the other side: over the 2° that close,
    # within the 4° that warn
    _SPLIT = [CircleSeg((0, 0), 1.95, math.radians(31.64), math.radians(259.9)),
              CircleSeg((0, 0), 1.95, math.radians(263.4), math.radians(391.64))]

    def test_011_two_arcs_joined_at_one_end_close_by_themselves(self):
        # whoever calls it by itself must not first merge the arcs that touch
        edges, n = topo.experimental.close_near_full_arcs(list(topo.load_segments(self._SPLIT).edges), 0.5,
                                                          max_missing_angle=math.radians(6))
        self.assertEqual(([type(e.segment).__name__ for e in edges], n), (["CircleSeg"], 1))

    def test_012_heal_says_how_many_degrees_are_missing_and_the_help_closes_it(self):
        doc = topo.load_segments(self._SPLIT)
        [d] = [w for w in topo.heal(doc, max_gap=0.5).warnings if isinstance(w, topo.Diagnostic)]
        self.assertEqual((d.code, d.param, d.at), ("open-arc", "max_missing_angle", (0.0, 0.0)))
        self.assertAlmostEqual(math.degrees(d.value), 3.5, places=2)
        self.assertIn("math.radians(3.5)", d.help)
        doc.edges, _ = topo.experimental.close_near_full_arcs(doc.edges, 0.5, max_missing_angle=math.radians(5.7))
        net = topo.heal(doc, max_gap=0.5)
        self.assertFalse([w for w in net.warnings if isinstance(w, topo.Diagnostic)])
        self.assertEqual(sum(len(c.inners) for c in net.faces().clusters) + net.faces().cluster_count, 1)

    def test_014_a_gap_just_beyond_the_limit_warns_and_the_help_closes_it(self):
        # an open rectangle of 0.055 with tolerance 0.05
        sides = [LineSeg((0.055, 0), (10, 0)), LineSeg((10, 0), (10, 5)), LineSeg((10, 5), (0, 5)), LineSeg((0, 5), (0, 0))]
        doc = topo.load_segments(sides)
        net = topo.heal(doc, max_gap=0.05)
        [d] = [w for w in net.warnings if isinstance(w, topo.Diagnostic)]
        self.assertEqual((d.code, d.param, round(d.value, 4)), ("near-gap", "max_gap", 0.055))
        self.assertEqual(net.faces().cluster_count, 0)
        self.assertIn("max_gap=0.055)", d.help)
        net = topo.heal(doc, max_gap=0.055)
        self.assertEqual((net.faces().cluster_count, [w for w in net.warnings if isinstance(w, topo.Diagnostic)]), (1, []))

    def test_013_a_small_thread_does_not_warn(self):
        # a thread is missing ~90°; r 0.3, chord 0.42 within 0.5, open on purpose
        thread = CircleSeg((0, 0), 0.3, 0.0, math.radians(270))
        net = topo.heal(topo.load_segments([thread]), max_gap=0.5)
        self.assertFalse([w for w in net.warnings if isinstance(w, topo.Diagnostic)])

    def test_015_nearly_is_twice_the_angle_that_closes(self):
        # 3.9° missing warns, 4.1° does not: the same "nearly" as a gap
        for missing, warns in ((3.9, True), (4.1, False)):
            arc = CircleSeg((0, 0), 1.95, 0.0, math.radians(360 - missing))
            net = topo.heal(topo.load_segments([arc]), max_gap=0.5)
            codes = [w.code for w in net.warnings if isinstance(w, topo.Diagnostic)]
            self.assertEqual("open-arc" in codes, warns, missing)


class TestSingleNodeGrid(unittest.TestCase):
    """the tolerance closes gaps, it does not round nodes. Lollipop: a square with an
    r=1.5 arc of 359.4° at the tip of a very narrow wedge, the two attached sides
    exact at the arc's ends, ends 0.016 apart."""

    def _lollipop(self):
        arc = _arc(1.5, 0.6)
        a, b = arc._point_at(arc.start_angle), arc._point_at(arc.end_angle)
        return [LineSeg((20, 0.3), (20, 20)), LineSeg((20, 20), (60, 20)), LineSeg((60, 20), (60, -20)),
                LineSeg((60, -20), (20, -20)), LineSeg((20, -20), (20, -0.3)), LineSeg((20, -0.3), b),
                arc, LineSeg(a, (20, 0.3))]

    def test_001_tip_arc_stays_in_the_outer(self):
        for tol in (0.05, 0.5):
            with self.subTest(tolerance=tol):
                result = topo.heal(topo.load_segments(self._lollipop()), max_gap=tol).faces()
                self.assertEqual(result.cluster_count, 1)
                cluster = result.clusters[0]
                self.assertEqual(cluster.inners, [], "the arc is not a hole")
                arcs = [s for s in cluster.outer.segments if (isinstance(s, CircleSeg) and not s.full)]
                self.assertEqual(len(arcs), 1)
                self.assertGreater(math.degrees(arcs[0]._sweep()), 359)

    def test_002_nodes_do_not_depend_on_the_tolerance(self):
        nodes = lambda tol: [(e.start, e.end) for e in topo.load_segments(self._lollipop()).edges]
        self.assertEqual(nodes(0.005), nodes(0.5))

    def test_006_heal_does_not_close_an_arc_by_tolerance_alone(self):
        result = topo.heal(topo.load_segments([_arc(10.0, 2.9)]), max_gap=1.0).faces()
        self.assertEqual(result.cluster_count, 0)


class TestFaceLoops(unittest.TestCase):
    """The loops of the bounded faces: one per face, never chosen by an order."""

    def test_001_one_square_one_ambit(self):
        self.assertEqual(len(topo.experimental.face_loops(_square(0, 0, 10))), 1)

    def test_002_two_slots_touching_two_ambits(self):
        # two square holes touching at a corner: two loops, not the figure-eight loop
        loops = topo.experimental.face_loops(_square(0, 0, 100) + _square(20, 20, 20) + _square(40, 40, 20))
        self.assertEqual(sorted(round(to_shapely(c).area) for c in topo.experimental.loops_to_curves(loops)),
                         [400, 400, 10000])

    def test_003_no_facet(self):
        self.assertEqual(topo.experimental.face_loops([_line((0, 0), (10, 0)), _line((20, 0), (20, 10))]), [])

    def test_004_a_circle_alone_is_an_ambit(self):
        self.assertEqual(len(topo.experimental.face_loops([_circle((50, 5), 2)])), 1)

    def test_005_does_not_touch_the_input_edges(self):
        edges = _square(0, 0, 10)
        before = [e.segment for e in edges]
        topo.experimental.face_loops(edges)
        self.assertEqual([e.segment for e in edges], before)


class TestLoopsToCurves(unittest.TestCase):

    def test_001_loop_with_a_non_structural_edge_discarded(self):
        engraved = _square(20, 0, 5, role="engrave")
        loops = topo.experimental.face_loops(_square(0, 0, 10) + engraved)
        self.assertEqual(len(loops), 2)
        kept = topo.experimental.structural_loops(loops)
        self.assertEqual(len(kept), 1)
        curves = topo.experimental.loops_to_curves(kept)
        self.assertEqual([round(to_shapely(f).area) for f in curves], [100])

    @staticmethod
    def _arc_with_chords(center=(5.0, 5.0), radius=0.64, n=16):
        # A quarter circle drawn twice: the arc and its chord copy. They close a loop
        # whose average width is below SAME_POINT. n different from the quarter's 15
        # sides on the arc's grid: with equal n the chords are the arc's polygon and the
        # loop is not there.
        arc = CircleSeg(center=center, radius=radius, start_angle=0.0,
                     end_angle=math.pi / 2, ccw=True)
        pts = [arc._point_at(k * (math.pi / 2) / n) for k in range(n + 1)]
        return [arc] + [LineSeg(start=pts[i], end=pts[i + 1]) for i in range(n)]

    def test_002_ambit_without_area_returns_as_open_curves(self):
        doc = topo.load_segments(self._arc_with_chords())
        loops = topo.experimental.face_loops(doc.edges)
        self.assertEqual(len(loops), 1)
        curves = topo.experimental.loops_to_curves(loops)
        self.assertEqual(len(curves), 17)
        self.assertTrue(all(isinstance(c, OpenCurve) for c in curves))

    def test_003_micro_circle_returns_as_open_curve(self):
        # average width (2·area/perimeter = radius) below SAME_POINT: it is not a contour
        loops = topo.experimental.face_loops([_circle((0.0, 0.0), 0.9 * SAME_POINT)])
        curves = topo.experimental.loops_to_curves(loops)
        self.assertEqual(len(curves), 1)
        self.assertIsInstance(curves[0], OpenCurve)
        self.assertIsInstance(curves[0].segments[0], CircleSeg)

    def test_004_heal_keeps_the_ambit_without_area(self):
        # the arc and the chords are not contour, they are in loose. Eight chords: too
        # few to be a curve written as points, which heal would refit and merge with the
        # arc; the loop stays without area: sagitta of the chords 0.2·(1-cos(π/32)) < SAME_POINT
        square = [LineSeg(start=a, end=b) for a, b in
                  [((0, 0), (10, 0)), ((10, 0), (10, 10)), ((10, 10), (0, 10)), ((0, 10), (0, 0))]]
        result = topo.heal(topo.load_segments(square + self._arc_with_chords(radius=0.2, n=8))).faces()
        self.assertEqual(result.cluster_count, 1)
        loose = [s for curve in result.loose for s in curve.segments]
        self.assertEqual(sum((isinstance(s, CircleSeg) and not s.full) for s in loose), 1)
        self.assertEqual(sum(isinstance(s, LineSeg) for s in loose), 8)


class TestLabeledAndHierarchy(unittest.TestCase):

    def test_001_loose_curves_closed_and_open(self):
        # a single rule for loose: closed by itself comes out closed, role intact
        curves = topo.experimental.loose_curves([_circle((5, 5), 1, role="engrave"),
                                                 _line((0, 0), (3, 0), role="engrave")])
        self.assertEqual(sorted(type(f).__name__ for f in curves), ["ClosedCurve", "OpenCurve"])
        self.assertTrue(all(f.role == "engrave" for f in curves))

    def test_002_square_within_square(self):
        loops = topo.experimental.face_loops(_square(0, 0, 10) + _square(3, 3, 4))
        clusters, trash = topo.experimental.build_hierarchy(topo.experimental.loops_to_curves(loops), label="p")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].inners), 1)
        self.assertEqual(clusters[0].inners[0].depth, 1)
        self.assertEqual(clusters[0].label, "p")
        self.assertEqual(trash, [])


class TestComposition(unittest.TestCase):
    """The steps composed by hand in heal()'s order give heal()'s clusters."""

    def _compose(self, doc, tol):
        prepared = topo.experimental.prepare(doc.edges)
        edges = topo.experimental.normalize(prepared.edges, tol + 1e-6, keep_junctions=True).edges
        noded = topo.experimental.split_at_crossings(edges, tol)
        non_contour = topo.experimental.non_contour_pieces(noded, tol)
        loops = [noded.whole(loop) for loop in topo.experimental.face_loops(
            [p for p in noded.pieces if id(p) not in non_contour])]
        kept = topo.experimental.structural_loops(loops)
        clusters, _ = topo.experimental.build_hierarchy(topo.experimental.loops_to_curves(kept))
        return clusters

    def test_001_same_clusters_as_heal(self):
        for name in ("rect_with_circle_hole.dxf", "flangia con fori.DXF", "two_parts.dxf"):
            with self.subTest(name=name):
                doc = topo_dxf.load_dxf(str(drawing(name)))
                expected = topo.heal(doc).faces().clusters
                got = self._compose(doc, doc.source_meta.get("tolerance", 0.05))
                self.assertEqual([to_shapely(c.outer).wkt for c in got],
                                 [to_shapely(c.outer).wkt for c in expected])
                self.assertEqual([len(c.inners) for c in got], [len(c.inners) for c in expected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
