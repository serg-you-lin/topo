# tests/engine/base/test_merge.py

import math
import unittest
import topo
from topo import to_shapely
from topo.core.base.merge import (merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
                                  merge_near_copies)
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from topo.precision import SAME_POINT


def _line(p1, p2, role="unknown"):
    return Edge(role=role, start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _arc(center, radius, start_deg, end_deg, role="unknown"):
    seg = CircleSeg(center=center, radius=radius,
                 start_angle=math.radians(start_deg), end_angle=math.radians(end_deg), ccw=True)
    start = (center[0] + radius * math.cos(seg.start_angle), center[1] + radius * math.sin(seg.start_angle))
    end = (center[0] + radius * math.cos(seg.end_angle), center[1] + radius * math.sin(seg.end_angle))
    return Edge(role=role, start=(round(start[0], 3), round(start[1], 3)),
                end=(round(end[0], 3), round(end[1], 3)), segment=seg)


def _line_raw(rounded_p1, rounded_p2, raw_p1, raw_p2, role="unknown"):
    # As the real adapter: Edge.start/end are the ROUNDED point (node identity in
    # the graph), the segment's LineSeg carries the full-precision coordinate of the
    # source — the two may differ by a fraction of a mm on non-round coordinates.
    return Edge(role=role, start=rounded_p1, end=rounded_p2, segment=LineSeg(start=raw_p1, end=raw_p2))


class TestMergeCollinearOverlaps(unittest.TestCase):

    def test_chain_of_three_merges(self):
        # A-B overlap, B-C overlap, A-C do not directly — it must merge anyway into a
        # single segment (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((8.0, 0.0), (20.0, 0.0)),
            _line((18.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

    def test_chain_of_two_merges(self):
        # Two strokes only that overlap: the union of two 1D intervals is always well
        # defined (here: (0,15)), there is no way to "go wrong" merging only 2 collinear
        # pieces.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((5.0, 0.0), (15.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (15.0, 0.0)))

    def test_a_stretch_contained_in_the_other_merges_into_the_longer(self):
        # Real case (golden la_104): a short stretch (15.68-21.36) and a long one
        # (10.0-21.36) on the same line, the short one wholly inside the long one — two
        # characters of an engraving aligned by coincidence, not a drawing error. The
        # union is just the longer one anyway: merging them neither fabricates nor loses geometry.
        edges = [
            _line((73.297, 15.68), (73.297, 21.36)),
            _line((73.297, 21.36), (73.297, 10.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual({out[0].segment.start, out[0].segment.end}, {(73.297, 10.0), (73.297, 21.36)})

    def test_tip_to_tail_contact_merges(self):
        # Three segments touching exactly in succession (no overlap, only continuity)
        # are the same line traced in pieces as much as a true overlap — the union is
        # well defined anyway, (0,0)-(30,0).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((10.0, 0.0), (20.0, 0.0)),
            _line((20.0, 0.0), (30.0, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0].segment.start, out[0].segment.end), ((0.0, 0.0), (30.0, 0.0)))

    def test_parallel_straights_do_not_merge(self):
        # Same direction, different offset: NOT the same line.
        edges = [
            _line((0.0, 0.0), (10.0, 0.0)),
            _line((3.0, 0.0), (13.0, 0.0)),
            _line((6.0, 0.0), (16.0, 0.0)),
            _line((0.0, 5.0), (10.0, 5.0)),
            _line((3.0, 5.0), (13.0, 5.0)),
            _line((6.0, 5.0), (16.0, 5.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_assigned_role_is_not_a_candidate(self):
        # A role other than UNKNOWN (assigned by role_rules) never enters
        # graph-building: merging it does not help and may alter intentional domain
        # geometry (see golden la_104: stretches of an engraving that overlap by design,
        # not by error).
        edges = [
            _line((0.0, 0.0), (10.0, 0.0), role="engrave"),
            _line((5.0, 0.0), (15.0, 0.0), role="engrave"),
            _line((8.0, 0.0), (20.0, 0.0), role="engrave"),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 3)

    def test_order_preserved_for_all_the_rest(self):
        # A cleanup pre-pass must not reorder edges it does not touch — even with zero
        # merges (see golden staffa_scarto_doppia: the reordering alone, with no merge,
        # changed the loop-finder's result).
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(5)]
        chain = [
            _line((0.0, 50.0), (10.0, 50.0)),
            _line((8.0, 50.0), (20.0, 50.0)),
            _line((18.0, 50.0), (30.0, 50.0)),
        ]
        edges = [others[0], others[1], chain[0], others[2], chain[1], others[3], chain[2], others[4]]
        out = merge_collinear_overlaps(edges)

        self.assertEqual(len(out), 6)  # 5 "others" + 1 merge
        # The merge takes the position of the chain's first member in input order
        # (index 2 in `edges`), the rest did not move.
        self.assertIs(out[0], others[0])
        self.assertIs(out[1], others[1])
        self.assertEqual((out[2].segment.start, out[2].segment.end), ((0.0, 50.0), (30.0, 50.0)))
        self.assertIs(out[3], others[2])
        self.assertIs(out[4], others[3])
        self.assertIs(out[5], others[4])

    def test_list_void(self):
        self.assertEqual(merge_collinear_overlaps([]), [])

    def test_merged_ends_edge_rounded_segment_raw(self):
        # On non-round coordinates edge.start/end (rounded, node identity in the graph)
        # and segment.start/end (full precision) differ by a fraction of a mm — two
        # different purposes, never mixed:
        #   - Edge.start/end of the merge STAY rounded: they serve to reattach to the
        #     node of the real neighbour in the graph, otherwise a true piece can
        #     vanish entirely (bug found on fa_che_non_mi_incazzi.dxf).
        #   - the merged LineSeg (edge.segment) ALWAYS carries the raw full-precision
        #     point, never the rounded one: it is what the export reads to build the
        #     output geometry, and a merge whose segment carries the rounded point
        #     produces a visible step as soon as it sits beside a native side never
        #     touched by the merge in the same contour (bug found on a real sheet: a
        #     "vertical" side with dx=0.031 instead of 0, length 0.97 instead of 1).
        edges = [
            _line_raw((0.0, 0.0), (10.0, 0.0), (0.0000003, 0.0), (10.0000003, 0.0)),
            _line_raw((8.0, 0.0), (20.0, 0.0), (8.0000003, 0.0), (20.0000003, 0.0)),
            _line_raw((18.0, 0.0), (30.0, 0.0), (18.0000003, 0.0), (30.0000003, 0.0)),
        ]
        out = merge_collinear_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, (0.0, 0.0))
        self.assertEqual(out[0].end, (30.0, 0.0))
        self.assertEqual(out[0].segment.start, (0.0000003, 0.0))
        self.assertEqual(out[0].segment.end, (30.0000003, 0.0))

    def test_contact_on_a_corner_does_not_merge(self):
        # An inner trace starting from a corner of the outer, collinear with the side
        # arriving there: the vertical side also ends in (0,0), it is a true node.
        # Merging them would erase it. Without `keep_junctions` (`outlines()`, which
        # nodes by itself) they merge as before.
        edges = [
            _line((-40.0, 0.0), (0.0, 0.0)),
            _line((0.0, 0.0), (200.0, 0.0)),
            _line((0.0, 0.0), (0.0, -40.0)),
        ]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 3)
        self.assertEqual(len(merge_collinear_overlaps(edges)), 2)

    def test_contact_without_other_edges_merges(self):
        # Same contact, but nothing else arrives at the point: it is only the seam
        # between two pieces of the same line.
        edges = [_line((-40.0, 0.0), (0.0, 0.0)), _line((0.0, 0.0), (200.0, 0.0))]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 1)

    def test_overlap_on_a_corner_merges(self):
        # A true overlap merges even where another edge arrives.
        edges = [
            _line((-40.0, 0.0), (5.0, 0.0)),
            _line((0.0, 0.0), (200.0, 0.0)),
            _line((0.0, 0.0), (0.0, -40.0)),
        ]
        self.assertEqual(len(merge_collinear_overlaps(edges, keep_junctions=True)), 2)


class TestSameCarrierUnderMotion(unittest.TestCase):
    """the same line in two pieces merges at every motion. The rounded key (angle,
    offset) had a cell edge where the two fell on different sides, and a seam on the verticals."""

    def _merged_at_every_motion(self, pieces, merge, expected):
        import topo
        from tests.invariants import MOTIONS, moved
        doc = topo.load_segments(pieces)
        for name, move, _, _ in [("in place", lambda s: s, None, None)] + MOTIONS:
            self.assertEqual(len(merge(moved(doc, move).edges)), expected, name)

    def test_vertical_duplicate_astride_a_cell(self):
        # drw_0016: x = 578.1875 is midway between two 1e-3 cells, the duplicate at
        # 2.5e-5 falls in the other; rotated they merged, in place they did not
        self._merged_at_every_motion(
            [LineSeg(start=(578.1875, 17.0), end=(578.1875, 25.0)),
             LineSeg(start=(578.1874750603, 24.9999881745), end=(578.1874750603, 16.9999881745))],
            merge_collinear_overlaps, 1)

    def test_vertical_duplicate_on_the_seam(self):
        # drw_0015: 1e-11 of noise on x sends a vertical duplicate to the other side of
        # the seam at +-90 degrees of the key (angle, offset)
        self._merged_at_every_motion(
            [LineSeg(start=(-71582.466979507, -2985.743765108251),
                     end=(-71582.46697950704, -2991.205129665564)),
             LineSeg(start=(-71582.46697950701, -2985.823579579326),
                     end=(-71582.466979507, -2986.705129665514)),
             LineSeg(start=(-71582.46697950704, -2991.705129665551),
                     end=(-71582.46697950696, -2985.476083898161))],
            merge_collinear_overlaps, 1)

    def test_arcs_of_the_same_circle_astride_a_cell(self):
        # like drw_0016 for circles: centre midway between two cells, the other at 2.5e-5
        self._merged_at_every_motion(
            [CircleSeg(center=(578.1875, 20.0), radius=12.0, start_angle=0.1, end_angle=1.3, ccw=True),
             CircleSeg(center=(578.187475, 20.0), radius=12.0, start_angle=1.2, end_angle=2.9, ccw=True)],
            merge_cocircular_overlaps, 1)


    def test_the_merge_goes_the_way_of_the_first_piece(self):
        # `merge.py`: the common line took a canonical direction (x increasing, then y),
        # which depends on the frame: a vertical rotated by +1e-12 rad came out merged
        # downwards, and every line turned half a turn. Visible in the `loose` of `heal`.
        from tests.invariants import rigid
        for pieces in ([((0, 0), (0, 6)), ((0, 4), (0, 10))],
                       [((10, 0), (4, 0)), ((6, 0), (0, 0))]):
            for motion in [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
                           (math.pi, 0.0, 0.0), (0.7, 3.1, -2.2)]:
                with self.subTest(pieces=pieces, motion=motion):
                    move_pt = rigid(*motion)[1]
                    edges = [_line(move_pt(a), move_pt(b)) for a, b in pieces]
                    merged = merge_collinear_overlaps(edges)
                    self.assertEqual(len(merged), 1)
                    seg, first = merged[0].segment, edges[0].segment
                    self.assertGreater((seg.end[0] - seg.start[0]) * (first.end[0] - first.start[0])
                                       + (seg.end[1] - seg.start[1]) * (first.end[1] - first.start[1]), 0)


class TestMergeNearCopies(unittest.TestCase):
    """The line nearly on top of another, merged only by the caller."""

    _PIECES = [LineSeg(start=(100, 0), end=(0.099, -0.0001)), LineSeg(start=(0, 0), end=(0, 50)),
               LineSeg(start=(0, 50), end=(100, 50)), LineSeg(start=(100, 50), end=(100, 0)),
               LineSeg(start=(0, 0), end=(0.0005, 17.7))]

    def test_the_longest_remains(self):
        long, copy = _line((0, 0), (0, 50)), _line((0, 0), (0.0005, 17.7))
        self.assertEqual(merge_near_copies([copy, long], distance=0.001), [long])

    def test_a_stroke_drawn_twice_with_a_role_is_one(self):
        # merge_collinear_overlaps never takes an assigned role: the exact copy falls to this one
        for second in (_line((0, 0), (8.4, 0), "engrave"), _line((8.4, 0), (0, 0), "engrave")):
            first = _line((0, 0), (8.4, 0), "engrave")
            self.assertEqual(len(merge_near_copies([first, second], distance=0.001)), 1)

    def test_the_same_line_with_other_roles_stays_two(self):
        edges = [_line((0, 0), (8.4, 0), "engrave"), _line((0, 0), (8.4, 0), "cut")]
        self.assertEqual(merge_near_copies(edges, distance=0.001), edges)

    def test_at_equal_length_the_median(self):
        out = merge_near_copies([_line((0, 0), (50, 0)), _line((50, 0.004), (0, 0.002))], distance=0.01)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertEqual((seg.start, seg.end), ((0.0, 0.001), (50.0, 0.002)))

    def test_the_copy_goes_with_the_nearest_line(self):
        # seed 1468: a short stretch at 0.006 from one line and at 0.41 from another
        # (the two long lines cover each other only in part: they are not copies of each other)
        near, far, copy = _line((0, 0), (3, 0)), _line((2, 0.41), (5, 0.41)), _line((2.2, 0.006), (2.5, 0.006))
        out = merge_near_copies([far, near, copy], distance=0.5)
        self.assertEqual(out, [far, near])

    def test_the_continuing_piece_is_not_a_copy(self):
        # brute force (seed 834): the piece after the end, in a row or at an angle, has
        # both ends within the distance of the long one but does not lie on it: it
        # stays, and heal() does not warn
        long = _line((0, 0), (10, 0))
        for nxt in (_line((10, 0), (10.3, 0.001)), _line((10, 0), (10.2, 0.3))):
            self.assertEqual(merge_near_copies([long, nxt], distance=0.5), [long, nxt])
        net = topo.heal(topo.load_segments([long.segment, LineSeg(start=(10, 0), end=(10.2, 0.3))]), max_gap=0.5)
        self.assertNotIn("near-copy", [w.code for w in net.warnings if isinstance(w, topo.Diagnostic)])

    def test_beyond_the_distance_two_remain(self):
        edges = [_line((0, 0), (0, 50)), _line((0, 0), (0.05, 17.7))]
        self.assertEqual(merge_near_copies(edges, distance=0.01), edges)

    def test_the_damaged_closes_only_if_the_caller_merges(self):
        # brute force, seed 1775: the bottom side stops at 0.099 from the corner; a copy
        # of the left side starts from the corner and keeps it occupied, so the gap does
        # not close. heal() says so, it does not merge it
        doc = topo.load_segments(self._PIECES)
        net = topo.heal(doc, max_gap=0.5)
        [d] = [w for w in net.warnings if isinstance(w, topo.Diagnostic)]
        self.assertEqual((d.code, d.param, round(d.value, 4)), ("near-copy", "distance", 0.0005))
        self.assertIn("distance=0.0005)", d.help)
        self.assertEqual(len(net.faces().clusters), 0)
        doc.edges = merge_near_copies(doc.edges, distance=0.0005)
        result = topo.heal(doc, max_gap=0.5).faces()
        self.assertEqual([round(to_shapely(c.outer).area) for c in result.clusters], [5000])


class TestMergeCocircularOverlaps(unittest.TestCase):

    def test_chain_of_fragments_merges(self):
        # golden piega_cazzuta: an arc traced in 4 consecutive pieces touching exactly
        # -> a single CircleSeg from 0 to 200 degrees.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
            _arc((0.0, 0.0), 10.0, 120.0, 160.0),
            _arc((0.0, 0.0), 10.0, 160.0, 200.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg.start_angle), 0.0)
        self.assertAlmostEqual(math.degrees(seg.end_angle), 200.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_degenerate_sliver_absorbed(self):
        # golden piega_cazzuta: a piece of 0.008 degrees (noise) in the middle of the
        # chain vanishes in the merge instead of staying a spurious node.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 50.008),
            _arc((0.0, 0.0), 10.0, 50.008, 120.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)

    def test_two_semicircles_close_the_circle(self):
        # golden cerchi_ciambella: a hole drawn as 2 semicircles -> a full turn is a
        # circle (CircleSeg), not a 360-degree CircleSeg -- no trace of which fragment was first.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 180.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].start, out[0].end)
        self.assertIsInstance(out[0].segment, CircleSeg)
        self.assertEqual(out[0].segment.radius, 10.0)

    def test_true_gap_does_not_close_by_mistake(self):
        # arc_arc_gap: a real gap (deliberately large here, 10 degrees) on one side must
        # not vanish only because the other side touches exactly.
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 170.0),
            _arc((0.0, 0.0), 10.0, 180.0, 360.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        seg = out[0].segment
        self.assertAlmostEqual(math.degrees(seg._sweep()), 350.0)
        self.assertNotEqual(out[0].start, out[0].end)

    def test_assigned_role_is_not_a_candidate(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0, role="engrave"),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0, role="engrave"),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_different_circles_do_not_merge(self):
        edges = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 20.0, 0.0, 50.0),
        ]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 2)

    def test_order_preserved(self):
        others = [_line((i * 100.0, 0.0), (i * 100.0 + 1.0, 0.0)) for i in range(3)]
        chain = [
            _arc((0.0, 0.0), 10.0, 0.0, 50.0),
            _arc((0.0, 0.0), 10.0, 50.0, 120.0),
        ]
        edges = [others[0], chain[0], others[1], chain[1], others[2]]
        out = merge_cocircular_overlaps(edges)

        self.assertEqual(len(out), 4)  # 3 "others" + 1 merge
        self.assertIs(out[0], others[0])
        seg = out[1].segment
        self.assertAlmostEqual(math.degrees(seg.end_angle), 120.0)
        self.assertIs(out[2], others[1])
        self.assertIs(out[3], others[2])

    def test_list_void(self):
        self.assertEqual(merge_cocircular_overlaps([]), [])

    def test_circle_written_twice_is_one_circle(self):
        # found by brute force: two equal CircleSegs were two overlapping holes
        edges = [Edge.of(CircleSeg((0.0, 0.0), 5.0), "unknown") for _ in range(2)]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, CircleSeg)

    def test_arc_over_a_circle_vanishes_in_the_circle(self):
        edges = [Edge.of(CircleSeg((0.0, 0.0), 10.0), "unknown"), _arc((0.0, 0.0), 10.0, -30.0, 30.0)]
        out = merge_cocircular_overlaps(edges)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, CircleSeg)

    def test_heal_double_circle_a_single_hole(self):
        import topo
        square = [LineSeg((0, 0), (200, 0)), LineSeg((200, 0), (200, 100)),
                  LineSeg((200, 100), (0, 100)), LineSeg((0, 100), (0, 0))]
        result = topo.heal(topo.load_segments(square + [CircleSeg((50, 50), 5)] * 2)).faces()
        self.assertEqual([len(c.inners) for c in result.clusters], [1])

    def test_concentric_circles_stay_two(self):
        edges = [Edge.of(CircleSeg((0.0, 0.0), 5.0), "unknown"), Edge.of(CircleSeg((0.0, 0.0), 6.0), "unknown")]
        self.assertEqual(len(merge_cocircular_overlaps(edges)), 2)


class TestWeldUnderMotion(unittest.TestCase):

    def test_arc_of_equal_chords_welded_the_same_at_every_motion(self):
        # (from a real drawing): a fillet written in 0.04 chords between two sides. With
        # all chords equal the welding order was decided by the last bit, and the 0.05
        # cap left a different alternation at every motion. Now the whole group is
        # judged: wider than 0.05, none
        import topo
        from tests.invariants import MOTIONS, moved
        center, r, n = (251.0, 21.0), 1.25, 12
        step = 2 * math.asin(0.02 / r)
        pts = [(center[0] + r * math.cos(k * step), center[1] + r * math.sin(k * step)) for k in range(n + 1)]
        pieces = [LineSeg(start=(pts[0][0], pts[0][1] - 10), end=pts[0])]
        pieces += [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]
        pieces.append(LineSeg(start=pts[-1], end=(pts[-1][0] - 10, pts[-1][1])))
        doc = topo.load_segments(pieces)
        base = len(weld_degenerate_linesegs(doc.edges))
        for name, move, _, _ in MOTIONS:
            self.assertEqual(len(weld_degenerate_linesegs(moved(doc, move).edges)), base, name)
        self.assertEqual(base, n + 2)


class TestWeldDegenerateLinesegs(unittest.TestCase):

    def _chain(self):
        return [
            _line_raw((0.0, 0.0), (10.0, 0.0), (0.0, 0.0), (10.0, 0.0)),
            _line_raw((10.0, 0.0), (10.0002, 0.0), (10.0, 0.0), (10.0002, 0.0)),
            _line_raw((10.0002, 0.0), (20.0, 0.0), (10.0002, 0.0), (20.0, 0.0)),
        ]

    def test_chain_stays_connected(self):
        # the 0.0002 mm LineSeg (below SAME_POINT) vanishes, but the two neighbours must
        # find themselves on the same node — just deleting it would detach the chain.
        out = weld_degenerate_linesegs(self._chain())
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].end, out[1].start)

    def test_segment_keeps_the_real_point(self):
        # only the node moves, the segment stays at full precision
        out = weld_degenerate_linesegs(self._chain())
        self.assertEqual(out[1].segment.start, (10.0002, 0.0))

    def test_assigned_role_is_not_welded(self):
        edges = [_line((0.0, 0.0), (0.02, 0.0), role="engrave")]
        self.assertEqual(weld_degenerate_linesegs(edges), edges)

    def test_above_threshold_is_not_welded(self):
        edges = [_line((0.0, 0.0), (0.06, 0.0)), _line((0.06, 0.0), (5.0, 0.0))]
        out = weld_degenerate_linesegs(edges)
        self.assertEqual(len(out), 2)
        self.assertIs(out[0], edges[0])
        self.assertIs(out[1], edges[1])

    def test_free_tip_is_not_welded(self):
        # a short stretch with an end touching nobody is a tip, not a double node:
        # welding it would move the free end by 0.03 and the 0.004 gap towards the
        # adjacent arc would no longer close
        edges = [_line((10.0, 0.0), (20.0, 0.0)), _line((10.03, 0.0), (10.0, 0.0))]
        self.assertEqual(weld_degenerate_linesegs(edges), edges)

    def test_list_void(self):
        self.assertEqual(weld_degenerate_linesegs([]), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
