"""
tests/engine/primitives/test_intersections.py
---------------------------------------
`intersections(a, b)` gives the same meetings before and after a rigid
motion. Far from the origin the double noise is ~1e-10 mm: a smaller absolute
threshold (1e-10, 1e-12 in mm² or mm⁴) lets it decide — parallels that
"meet", a lost or doubled touch. Every case is a `subTest` per motion.
"""

import math
import unittest

import topo
intersections = topo.geometry.intersections
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from tests.invariants import rigid

# precise motions (angle, dx, dy) for `rigid`: null, rotation only, far, far and
# rotated; some are those found red by the scan
RIGID = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.0, 3e6, -2.5e6), (0.031, 3e6, -2.5e6),
           (0.062, 3e6, -2.5e6), (0.093, 3e6, -2.5e6), (0.7, 3e6, -2.5e6),
           (2.294, 3e6, -2.5e6), (math.pi / 2, -7e5, 4e5), (0.13, 1e6, 1e6)]


class TestIntersectionsUnderMotion(unittest.TestCase):
    """The meetings of the moved piece are the moved meetings."""

    def _assert_same_meetings(self, a, b, expected):
        for motion in RIGID:
            with self.subTest(motion=motion):
                segment, point = rigid(*motion)
                got = intersections(segment(a), segment(b))
                want = [point(p) for p in expected]
                self.assertEqual(len(got), len(want), got)
                for p in want:
                    self.assertLess(min(math.dist(p, q) for q in got), 1e-6)

    def test_001_collinear_overlap_has_no_point(self):
        # a stretch inside the other, on the same line: the meeting is a stretch, no
        # point. Far away, the `denom` of the two directions is only noise (~1e-8 mm²)
        # and the "meeting" fell wherever, often inside both
        self._assert_same_meetings(LineSeg(start=(0.0, 0.0), end=(100.0, 0.0)),
                                   LineSeg(start=(30.0, 0.0), end=(70.0, 0.0)), [])

    def test_002_end_on_the_middle_of_a_line_is_one_point(self):
        # a short stretch starting from the middle of another (a T): its end is the
        # meeting. Far away the noise of `t` over 0.04 mm exceeds 1e-9 and the T was lost
        self._assert_same_meetings(LineSeg(start=(0.0, 0.0), end=(0.05, 0.0)),
                                   LineSeg(start=(0.02, 0.0), end=(0.02, 0.04)), [(0.02, 0.0)])

    def test_003_arc_end_on_a_line_end_is_one_point(self):
        # a small arc ending where a line begins, not tangent to it
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=0.05, start_angle=0.0,
                                          end_angle=math.pi / 2),
                                   LineSeg(start=(0.0, 0.05), end=(-0.05, 0.08)), [(0.0, 0.05)])

    def test_004_line_tangent_to_a_circle_is_one_point(self):
        # tangency decided on the discriminant (mm⁴, threshold 1e-10): far away the
        # noise makes it negative (no point) or positive (two points ~1e-4 mm apart)
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   LineSeg(start=(-8.0, 5.0), end=(8.0, 5.0)), [(0.0, 5.0)])

    def test_005_circles_tangent_outside_are_one_point(self):
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(8.0, 0.0), radius=3.0), [(5.0, 0.0)])

    def test_006_circles_tangent_inside_are_one_point(self):
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(2.0, 0.0), radius=3.0), [(5.0, 0.0)])

    def test_007_crossings_stay_two(self):
        # to be safe: a true crossing stays two points
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   LineSeg(start=(-8.0, 3.0), end=(8.0, 3.0)), [(-4.0, 3.0), (4.0, 3.0)])
        self._assert_same_meetings(CircleSeg(center=(0.0, 0.0), radius=5.0),
                                   CircleSeg(center=(6.0, 0.0), radius=5.0), [(3.0, 4.0), (3.0, -4.0)])
