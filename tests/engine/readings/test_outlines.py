# tests/engine/readings/test_outlines.py

import math
import unittest
import topo
from topo.model.document import Document
from topo.model.role import ContourRole
from topo.core.topology.edge import Edge
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from topo.core.base.refit import refit_tessellations
from topo.core.primitives.conics import CircleSeg
from topo import to_shapely
from topo.precision import SAME_POINT

# max_gap has no default; island_gap no longer exists
MAX_GAP = 0.5


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _doc(edges):
    return Document(edges=edges, texts=[], source_path="")


class TestOutlines(unittest.TestCase):

    def test_two_separate_views_two_clusters(self):
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + _poly((50, 0), (60, 0), (60, 5), (50, 5))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 2)
        self.assertEqual([round(to_shapely(c.outer).area) for c in result.clusters], [100, 50])

    def test_island_inside_another_goes_to_loose(self):
        # 100x100 frame and a view inside — the only contour is the frame, the view goes
        # to loose with the island that contains it; its sides close by themselves, so it
        # is a single closed piece
        edges = _poly((0, 0), (100, 0), (100, 100), (0, 100)) + _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 10000.0)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual([t.cluster_ref for t in result.loose], [0])
        self.assertAlmostEqual(to_shapely(result.loose[0]).area, 400.0)

    def test_two_very_near_contours_stay_two_islands(self):
        # no distance between the views — two contours 1 mm apart are two islands
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + _poly((11, 0), (21, 0), (21, 5), (11, 5))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 2)

    def test_open_line_inside_a_view_is_its_own(self):
        # an axis inside the view that does not touch the contour goes to trash with the
        # view's cluster_ref; a line outside every contour stays without an island
        view = _poly((0, 0), (100, 0), (100, 50), (0, 50))
        small = _poly((200, 0), (210, 0), (210, 10), (200, 10))
        axis, loose = _line((10, 25), (90, 25)), _line((300, 0), (320, 0))
        result = topo.heal(_doc(view + small + [axis, loose]), max_gap=MAX_GAP).outlines()
        refs = {round(t.segments[0].start[0]): t.cluster_ref for t in result.loose}
        self.assertEqual(refs, {10: 0, 300: None})

    def test_group_of_detached_circles_inside_a_view_in_loose(self):
        # three circles detached from the border inside the view go to loose, whole,
        # with the island that contains them
        edges = _poly((0, 0), (200, 0), (200, 100), (0, 100)) + [
            _circle((90, 50), 3), _circle((100, 50), 5.5), _circle((110, 50), 3)]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual(sorted(s.radius for t in result.loose for s in t.segments), [3, 3, 5.5])
        self.assertEqual({t.cluster_ref for t in result.loose}, {0})

    def test_circle_inside_a_view_in_loose(self):
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(result.clusters[0].outer.role, ContourRole.OUTER)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual([(type(s).__name__, s.radius, t.cluster_ref) for t in result.loose for s in t.segments],
                         [("CircleSeg", 3, 0)])

    def test_circle_cut_by_the_axes_comes_out_whole(self):
        # the axes cross the circle in the planar network: in loose the circle comes
        # out intact, not in the network's 4 arcs
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        edges += [_line((5, 10), (15, 10)), _line((10, 5), (10, 15))]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(sorted(type(s).__name__ for t in result.loose for s in t.segments),
                         ["CircleSeg", "LineSeg", "LineSeg"])

    def test_side_cut_by_an_axis_returns_a_segment(self):
        # an axis leaving the contour breaks it: the outer contour stays 4 sides
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_line((10, -5), (10, 25))]
        outer = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines().clusters[0].outer
        self.assertEqual(len(outer.segments), 4)

    def test_marked_frame_stays_out(self):
        # snapdraw marks the frame → outlines() does not read it, it stays in loose with
        # its role; closed by itself, it comes out as a closed curve
        frame = _poly((0, 0), (100, 0), (100, 100), (0, 100))
        for e in frame:
            e.role = "frame"
        view = _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = topo.heal(_doc(frame + view), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 400.0)
        framed = [t for t in result.loose if t.role == "frame"]
        self.assertEqual([(type(t).__name__, len(t.segments)) for t in framed], [("ClosedCurve", 4)])

    def test_near_concentric_circles_in_loose_at_every_max_gap(self):
        # two circles 0.4 apart inside the view both come out in loose, below and above
        # the contact (max_gap 0.5 and 0.2)
        edges = _poly((0, 0), (100, 0), (100, 100), (0, 100)) + [
            _circle((50, 50), 5), _circle((50, 50), 4.6)]
        for gap in (MAX_GAP, 0.2):
            with self.subTest(max_gap=gap):
                result = topo.heal(_doc(edges), max_gap=gap).outlines()
                self.assertEqual(result.clusters[0].inners, [])
                self.assertEqual(sorted(s.radius for t in result.loose for s in t.segments), [4.6, 5])
                self.assertEqual({t.cluster_ref for t in result.loose}, {0})

    def test_nothing_closed_invalid(self):
        result = topo.heal(_doc([_line((0, 0), (5, 0))]), max_gap=MAX_GAP).outlines()
        self.assertFalse(result.is_valid)

    def test_requires_a_document(self):
        with self.assertRaises(TypeError):
            topo.heal([_line((0, 0), (1, 0))], max_gap=MAX_GAP).outlines()


class TestRefitTessellations(unittest.TestCase):

    def _tessellated_arc(self, n=40):
        pts = [(10 * math.cos(math.pi * i / (2 * n)), 10 * math.sin(math.pi * i / (2 * n))) for i in range(n + 1)]
        return [_line(pts[i], pts[i + 1]) for i in range(n)]

    def test_short_chain_becomes_an_arc(self):
        # 40 segments of ~0.39 mm: below max_segment=0.5 → an r=10 arc
        out = refit_tessellations(self._tessellated_arc(), max_segment=0.5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, CircleSeg)
        self.assertAlmostEqual(out[0].segment.radius, 10.0, places=3)

    def test_ends_keep_the_nodes(self):
        chain = self._tessellated_arc()
        out = refit_tessellations(chain, max_segment=0.5)
        self.assertEqual(out[0].start, chain[0].start)
        self.assertEqual(out[0].end, chain[-1].end)

    def test_chain_too_short_is_left_alone(self):
        chain = self._tessellated_arc(n=5)
        self.assertEqual(refit_tessellations(chain, max_segment=5.0), chain)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNestedInUnderMotion(unittest.TestCase):
    """`read_outlines` chooses the host with `max` on the outer's area. There is no
    tie: two hosts containing the same piece are distinct islands, so their
    borders do not touch and one contains the other; the areas differ by at least
    distance × perimeter, well beyond the noise. Proof: three nested frames and a
    stretch inside the smallest; at every motion the stretch and the two inner
    frames point to the largest frame."""

    MOTIONS = [(a, dx, dy) for a in (0.0, 0.8127, math.pi / 2)
               for dx, dy in ((0.0, 0.0), (13.1, -9.3), (2.5e6, -1.5e6))]

    def test_the_outermost_hosts_all(self):
        from tests.invariants import rigid
        from topo import experimental
        rectangle = topo.geometry.rectangle
        segs = (rectangle(100, 100) + rectangle(60, 60) + rectangle(20, 20)
                + [LineSeg(start=(-3.0, 0.0), end=(3.0, 0.0))])
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                doc = topo.load_segments([segment(s) for s in segs])
                readings = experimental.read_outlines(doc.edges, 0.05, MAX_GAP)
                self.assertEqual(len(readings), 4)
                tops = [i for i, r in enumerate(readings) if r.nested_in is None]
                self.assertEqual(len(tops), 1)
                outer = to_shapely(readings[tops[0]].outer)
                self.assertAlmostEqual(outer.area, 100.0 ** 2, places=3)
                self.assertTrue(all(r.nested_in == tops[0] for i, r in enumerate(readings) if i != tops[0]))


class TestHostOfATinyPieceUnderMotion(unittest.TestCase):
    """the host of a piece was asked of the polygon of its outer widened by
    `tolerance`. An arc bite (sagitta just below `SAME_POINT`) and inside the bite
    a small circle of radius 0.0002 at 0.0502 from the true arc, threshold 0.05
    (`max_gap` 0): two islands at every motion, but the chord protrudes into the
    bite by nearly `SAME_POINT` and at half a step of the angular grid the buffer
    covered the whole small circle, which ended nested. Since two islands are
    farther apart than the threshold on the true curves, a single point of the
    piece says whether it is inside, on the primitives."""

    N = 64
    MOTIONS = [(0.0, 0.0, 0.0), (math.pi / 64, 0.0, 0.0), (math.pi / 128, 0.0, 0.0), (0.7, 0.0, 0.0),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def _segments(self):
        step = 2 * math.pi / self.N
        r = SAME_POINT * (1 - 1e-8) / (1 - math.cos(step / 2))
        a = math.pi / 4
        p1, p2 = (-r * math.cos(a), -r * math.sin(a)), (r * math.cos(a), -r * math.sin(a))
        return [CircleSeg(center=(0.0, 0.0), radius=r, start_angle=5 * a, end_angle=7 * a, ccw=True),
                LineSeg(start=p2, end=(p2[0], -r - 3)), LineSeg(start=(p2[0], -r - 3), end=(p1[0], -r - 3)),
                LineSeg(start=(p1[0], -r - 3), end=p1),
                CircleSeg(center=(0.0, -r + 0.0504), radius=0.0002)]

    def test_the_small_circle_in_the_bite_is_not_nested_at_any_motion(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            move, _ = rigid(*motion)
            with self.subTest(motion=motion):
                result = topo.heal(topo.load_segments([move(s) for s in self._segments()]), max_gap=0.0).outlines()
                self.assertEqual(len(result.clusters), 2)

    def test_in_place_the_buffer_covers_the_small_circle(self):
        # the proof is not empty: at half a step the polygon widened by 0.05 contains it
        from shapely import Polygon
        from tests.invariants import rigid
        from topo.core.readings.outline import read_outline
        move, _ = rigid(math.pi / 64, 0.0, 0.0)
        segments = [move(s) for s in self._segments()]
        host = read_outline(topo.load_segments(segments[:4]).edges, 0.05, max_gap=0.0)
        self.assertTrue(to_shapely(host.outer).buffer(0.05).contains(Polygon(segments[4].discretize())))
