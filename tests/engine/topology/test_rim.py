# tests/engine/topology/test_rim.py

"""The segments of a face read from its border (`face_segments`). The faces per
loop of `outlines()` are no longer there: outlines() builds no inner."""

import math
import unittest

from shapely.geometry import Point, Polygon, box

from topo.core.geometry.shapely_polygons import build_polygon
from topo.core.primitives.line import LineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg
from topo.core.topology.edge import Edge
from topo.core.topology import rim
from topo.core.topology.rim import face_segments, off_rim

BAND = 0.02


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


class TestFaceSegments(unittest.TestCase):

    def test_edge_sul_bordo_solo_in_parte_da_la_sua_parte(self):
        # the base and the right side overshoot the square: crossings the network did not cut
        edges = [_line((-5, 0), (15, 0)), _line((10, -3), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, styles, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)
        self.assertEqual(len(styles), 4)
        rebuilt = build_polygon(segments)
        self.assertLess(rebuilt.symmetric_difference(box(0, 0, 10, 10)).area, 1e-9)
        ends = {tuple(round(c, 9) for c in p) for s in segments for p in segment_endpoints(s)}
        self.assertEqual(ends, {(0, 0), (10, 0), (10, 10), (0, 10)})

    def test_il_resto_di_un_edge_solo_in_parte_sul_bordo(self):
        # the base overshoots by 5 left and right, the right side by 3 downwards; only
        # the overshoot comes out, never the whole edge
        edges = [_line((-5, 0), (15, 0)), _line((10, -3), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        square = box(0, 0, 10, 10)
        _, _, used = face_segments(edges, square, BAND)
        rest = off_rim(edges[0], used[0], square.exterior, BAND)
        ends = sorted(tuple(tuple(round(c, 9) for c in p) for p in segment_endpoints(e.segment)) for e in rest)
        self.assertEqual(ends, [((-5, 0), (0, 0)), ((10, 0), (15, 0))])
        self.assertEqual(rest[0].start, (-5, 0))   # the original end keeps its node
        self.assertEqual(off_rim(edges[2], used[2], square.exterior, BAND), [])

    def test_doppione_sovrapposto_non_spezzetta(self):
        edges = [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)),
                 _line((10, 10), (0, 10)), _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, _, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)

    def test_arco_tangente_a_una_retta_resta_un_arco(self):
        # half disc: diameter as a line, semicircle as an arc
        arc = CircleSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi, ccw=True)
        edges = [_line((-5, 0), (5, 0)),
                 Edge(role="unknown", start=(5, 0), end=(-5, 0), segment=arc)]
        polygon = Polygon(arc.discretize(tolerance=0.01))
        segments, _, _ = face_segments(edges, polygon, BAND)
        self.assertEqual(sorted(type(s).__name__ for s in segments), ["CircleSeg", "LineSeg"])

    def test_due_tratti_vicini_si_chiudono_con_una_retta(self):
        # the top side runs 0.01 above the ring, the vertical sides end on the ring.
        # Every stretch ends on its own curve: between the two near ends a new line, no curve moved
        edges = [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)),
                 _line((10, 10.01), (0, 10.01)), _line((0, 10), (0, 0))]
        segments, styles, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 6)
        self.assertEqual(len(styles), 6)
        for k, segment in enumerate(segments):
            following = segments[(k + 1) % len(segments)]
            self.assertEqual(segment_endpoints(segment)[1], segment_endpoints(following)[0])
        bridges = sorted(round(math.dist(*segment_endpoints(s)), 9) for s in segments)[:2]
        self.assertEqual(bridges, [0.01, 0.01])


class TestOffRimCutsUnderMotion(unittest.TestCase):
    """the cuts of `off_rim` were the abscissae rounded to 1e-9. Two ends taken 1e-10
    apart fell in one cell or two depending on the motion, and the end of the
    remainder moved up to 5e-10 from the contour's node (here the edge starts at
    -5.00000000045: the cut falls 4.5e-10 from a multiple of 1e-9). Proof: in place
    and at the motions only the overshoot comes out, with the inner end on the end
    taken (within the motion's noise). It does not prove the line inside
    `outlines()`: on the traced drawings the fallback `_faces_union_loop` never reaches `off_rim`."""

    MOTIONS = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.13, 3.1, -7.9), (2.4, -0.37, 0.61)]

    def test_due_capi_quasi_uguali_un_resto_solo(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                move_seg, move_pt = rigid(*motion)
                edge = _line((-5.00000000045, 0.0), (15.0, 0.0))
                edge = Edge(role="unknown", start=move_pt(edge.start), end=move_pt(edge.end),
                            segment=move_seg(edge.segment))
                square = Polygon([move_pt(p) for p in [(0, 0), (10, 0), (10, 10), (0, 10)]])
                corner = move_pt((0.0, 0.0))
                twin = move_pt((1e-10, 0.0))
                taken = [(corner, move_pt((10.0, 0.0))), (twin, corner)]
                rest = off_rim(edge, taken, square.exterior, BAND)
                left = [e for e in rest if e.start == edge.start]
                self.assertEqual(len(rest), 2)
                self.assertEqual(len(left), 1)
                # the inner end is on the contour's node, not on a cell
                inner = segment_endpoints(left[0].segment)[1]
                self.assertLess(math.dist(inner, corner), 1e-12)


class TestSenseOfAPerpendicularSpur(unittest.TestCase):
    """the direction of an edge relative to a side is the sign of a dot product, `>=
    0`. A perpendicular protrusion touching the midpoint of a side has product 0 at
    rest and noise (±4e-15) under motion: its direction changes with the motion.
    Proof: the direction really changes (the line is reached with the null value)
    and the output of `face_segments` does not, because the side is held by its
    edge. It does not prove the line inside `outlines()`: on the traced drawings
    `face_segments` is never called. It does not prove the case where the
    protrusion wins the side (protrusion first in the list): that is the parity of `_rim_runs`."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (math.pi / 2, 0.0, 0.0)]
    SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]

    def test_il_verso_cambia_l_uscita_no(self):
        from tests.invariants import rigid
        senses, outputs = set(), set()
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                move_seg, move_pt = rigid(*motion)
                edges = [_line(self.SQUARE[i], self.SQUARE[(i + 1) % 4]) for i in range(4)]
                edges.append(_line((5, 0), (5, -3)))
                edges = [Edge(role="unknown", start=move_pt(e.start), end=move_pt(e.end),
                              segment=move_seg(e.segment)) for e in edges]
                polygon = Polygon([move_pt(p) for p in self.SQUARE])
                # the protrusion's direction on the lower side, as the line computes it
                p, q = move_pt((0, 0)), move_pt((10, 0))
                mid = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                senses.add(rim._sense(rim.edge_geometry(edges[4]), mid, p, q, BAND))
                segments, _, used = face_segments(edges, polygon, BAND)
                self.assertEqual(sorted(used), [0, 1, 2, 3])
                outputs.add(tuple(sorted(round(math.dist(*segment_endpoints(s)), 9)
                                         for s in segments)))
        self.assertEqual(senses, {1, -1})
        self.assertEqual(outputs, {(10.0, 10.0, 10.0, 10.0)})


class TestSpurDoesNotTakeTheSide(unittest.TestCase):
    """(`best`, `s` in `_rim_runs`): a side was covered by every edge within `band`
    of its midpoint. A protrusion starting from the midpoint of the lower side
    covered it like the side, with the same reach (1): first in the list, it won by
    index and the side came out of length zero, (5, 0)→(5, 0). Now only the edge
    running along it covers a side (also the two ends of the side within `band`).
    Proof: the protrusion really is within `band` of the midpoint (checked), and
    the four sides come out of 10 with their edges in both orders and at five
    motions. It does not prove the readings: `face_segments` is not called on the traced drawings."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (math.pi / 2, 0.0, 0.0)]
    SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]

    def test_il_lato_resta_al_suo_edge(self):
        from tests.invariants import rigid
        sides = [_line(self.SQUARE[i], self.SQUARE[(i + 1) % 4]) for i in range(4)]
        spur = _line((5, 0), (5, -3))
        for name, order in (("sporgenza ultima", sides + [spur]), ("sporgenza prima", [spur] + sides)):
            for motion in self.MOTIONS:
                move_seg, move_pt = rigid(*motion)
                edges = [Edge(role="unknown", start=move_pt(e.start), end=move_pt(e.end),
                              segment=move_seg(e.segment)) for e in order]
                polygon = Polygon([move_pt(p) for p in self.SQUARE])
                k = order.index(spur)
                mid = move_pt((5, 0))
                self.assertLessEqual(rim.edge_geometry(edges[k]).distance(Point(mid)), BAND)
                segments, _, used = face_segments(edges, polygon, BAND)
                with self.subTest(order=name, motion=motion):
                    self.assertNotIn(k, used)
                    self.assertEqual(sorted(round(math.dist(*segment_endpoints(s)), 9) for s in segments),
                                     [10.0] * 4)

    def test_il_lato_di_partenza_non_conta(self):
        # `rim.py:173`: the coverage starts from the side covered by fewer edges, on a
        # tie the first of the ring, and where the ring starts is decided by whoever
        # builds it. Two overlapping lines on the lower side (the coverage has a
        # choice): the same output from every starting vertex. It does not prove three
        # overlapping edges on the same stretch.
        edges = [_line((-1, 0), (6, 0)), _line((4, 0), (11, 0)), _line((10, -1), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, -1))]
        ring = [(0, 0), (4, 0), (5, 0), (6, 0), (10, 0), (10, 10), (0, 10)]
        outputs = set()
        for r in range(len(ring)):
            segments, _, used = face_segments(edges, Polygon(ring[r:] + ring[:r]), BAND)
            ends = tuple(sorted(tuple(sorted(tuple(round(c, 9) for c in p) for p in segment_endpoints(s)))
                                for s in segments))
            outputs.add((ends, tuple(sorted(used))))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(next(iter(outputs))[1], (0, 1, 2, 3, 4))


class TestOverlapCutUnderMotion(unittest.TestCase):
    """(the cut between two edges that both cover): the cut goes where `gap` is
    minimal, on a tie near where the coverage changes. Two overlapping lines on
    (4, 6): `gap` is 0 at three vertices at rest and noise under motion, and the cut
    fell at 4, 5 or 6 depending on the motion. Now `gap` equal within FLOAT_NOISE.
    Proof: the tie in place (three vertices at gap < 1e-9, checked) and the cut at 6
    at seven rigid motions. It does not prove the mirror: it reverses the ring's
    direction and the cut goes to 4 (later). It does not prove the readings:
    `face_segments` is not called on the traced drawings."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0), (0.7, 3.1, -2.2),
               (math.pi / 2, 0.0, 0.0), (2.4, -0.37, 0.61), (2.1, -1e5, 3e4)]
    EDGES = [((-1, 0), (6, 0)), ((4, 0), (11, 0)), ((10, -1), (10, 10)), ((10, 10), (0, 10)), ((0, 10), (0, -1))]
    RING = [(0, 0), (4, 0), (5, 0), (6, 0), (10, 0), (10, 10), (0, 10)]

    def test_il_taglio_non_dipende_dal_moto(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            move_seg, move_pt = rigid(*motion)
            edges = [Edge(role="unknown", start=move_pt(a), end=move_pt(b),
                          segment=move_seg(LineSeg(start=a, end=b))) for a, b in self.EDGES]
            tied = [p for p in self.RING
                    if sum(rim.edge_geometry(edges[j]).distance(Point(move_pt(p))) for j in (0, 1)) < 1e-9]
            self.assertEqual(len(tied), 3, motion)
            _, _, used = face_segments(edges, Polygon([move_pt(p) for p in self.RING]), BAND)
            (a, b), = used[0]
            cut = move_pt((6, 0))
            with self.subTest(motion=motion):
                self.assertLess(min(math.dist(a, cut), math.dist(b, cut)), 1e-9)


class TestTrimmedAtTheMiddleUnderMotion(unittest.TestCase):
    """(`_trimmed`, the end nearest an end): on a segment 0.03 long (between `band`
    and 2·`band`) the midpoint is within `band` of both ends, at the same distance;
    the last bit won and the stretch came out 0 or 0.03 long. Now an end
    equidistant within FLOAT_NOISE stays where it is. Proof: the tie in place (the
    two distances, checked) and the stretch 0.015 long at nine motions. It does not
    prove the readings: `face_segments` is not called on the traced drawings."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0), (0.7, 3.1, -2.2),
               (math.pi / 2, 0.0, 0.0), (2.4, -0.37, 0.61), (2.1, -1e5, 3e4), (0.3, 0.0, 0.0), (1.1, 0.0, 0.0)]

    def test_il_mezzo_non_si_aggancia(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            move_seg, move_pt = rigid(*motion)
            seg = move_seg(LineSeg(start=(0, 0), end=(0.03, 0)))
            s0, s1 = segment_endpoints(seg)
            mid = move_pt((0.015, 0))
            self.assertLess(abs(math.dist(mid, s0) - math.dist(mid, s1)), 1e-9)
            piece = rim._trimmed(seg, move_pt((0, 0)), mid, move_pt((0.0075, 0)), BAND)
            with self.subTest(motion=motion):
                self.assertAlmostEqual(math.dist(*segment_endpoints(piece)), 0.015, places=9)


if __name__ == "__main__":
    unittest.main()
