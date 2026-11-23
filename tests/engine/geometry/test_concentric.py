# tests/engine/geometry/test_concentric.py
"""`concentric_groups` and `arcs_around`: geometric facts between several contours."""

import math
import unittest

import topo
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from topo.core.geometry.concentric import arcs_around, concentric_groups


def _circle(c, r):
    return [CircleSeg(center=c, radius=r)]


def _square(c, half):
    x, y = c
    pts = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
    return [LineSeg(start=pts[i], end=pts[(i + 1) % 4]) for i in range(4)]


class TestConcentricGroups(unittest.TestCase):

    def test_two_concentric_circles_and_an_isolated_one(self):
        small, big, alone = _circle((0, 0), 2), _circle((0.05, 0), 4), _circle((20, 0), 2)
        groups = concentric_groups([big, alone, small], tolerance=0.1)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].items, (small, big))
        self.assertEqual(groups[0].diameters, (4, 8))
        self.assertEqual(groups[0].center, (0, 0))
        self.assertEqual(groups[1].items, (alone,))

    def test_outside_tolerance_do_not_join(self):
        a, b = _circle((0, 0), 2), _circle((0.5, 0), 4)
        self.assertEqual(len(concentric_groups([a, b], tolerance=0.1)), 2)
        self.assertEqual(len(concentric_groups([a, b], tolerance=1.0)), 1)

    def test_non_circles_do_not_appear(self):
        groups = concentric_groups([_square((0, 0), 5), _circle((0, 0), 2)], tolerance=0.1)
        self.assertEqual([len(g.items) for g in groups], [1])

    def test_three_circles_from_the_smaller_to_the_larger(self):
        rings = [_circle((0, 0), r) for r in (6, 2, 4)]
        (group,) = concentric_groups(rings, tolerance=0.1)
        self.assertEqual(group.diameters, (4, 8, 12))

    def test_public_api(self):
        self.assertIs(topo.geometry.concentric_groups, concentric_groups)
        self.assertIs(topo.geometry.arcs_around, arcs_around)


def _moved(p, angle, shift):
    c, s = math.cos(angle), math.sin(angle)
    return (c * p[0] - s * p[1] + shift[0], s * p[0] + c * p[1] + shift[1])


MOTIONS = [(0.0, (0, 0)), (math.pi, (0, 0)), (2.0, (1e5, 3e4)), (0.5, (-7, 3)),
           (math.pi / 2, (0, 0)), (4.1, (-3e5, 2e5)), (1.0, (0.3, 0)), (3.0, (5e4, -5e4)), (5.5, (1, 1))]


class TestConcentricGroupsUnderMotion(unittest.TestCase):
    """the partition does not depend on the frame."""

    def test_the_large_circle_goes_with_the_nearest_centre(self):
        # A and B equal at 0.15 (two groups); C larger at 0.06 from A and 0.09 from B:
        # it enters A. Before, it entered the group born first, that is the centre with
        # the smaller x, and a 180° rotation sent it to B.
        spec = [((0, 0), 2), ((0.15, 0), 2), ((0.06, 0), 4)]
        for angle, shift in MOTIONS:
            with self.subTest(angle=angle, shift=shift):
                items = [_circle(_moved(c, angle, shift), r) for c, r in spec]
                parts = {tuple(items.index(list(i)) for i in g.items) for g in concentric_groups(items, tolerance=0.1)}
                self.assertEqual(parts, {(0, 2), (1,)})

    def test_at_equal_diameter_the_reference_is_the_first_given(self):
        # A and B equal at 0.05 (one group): the group's centre is A's, the first
        # given, in every frame; D at 0.09 from A and 0.14 from B enters it.
        spec = [((0, 0), 2), ((0.05, 0), 2), ((-0.09, 0), 4)]
        for angle, shift in MOTIONS:
            with self.subTest(angle=angle, shift=shift):
                items = [_circle(_moved(c, angle, shift), r) for c, r in spec]
                (group,) = concentric_groups(items, tolerance=0.1)
                self.assertEqual(group.items, (items[0], items[1], items[2]))
                self.assertEqual(group.center, items[0][0].center)

    def test_stacked_groups_stay_in_y_order(self):
        # Two holes one above the other, same x at rest: a translation moves the x's by
        # one ulp, the order stays that of the y's.
        for shift in [(0, 0), (0.1, 0), (1e5 + 0.3, 7), (-3e5 + 0.7, 0)]:
            with self.subTest(shift=shift):
                low = _circle((0.1 + shift[0], 0 + shift[1]), 2)
                high = _circle((0.3 - 0.2 + shift[0], 10 + shift[1]), 2)
                groups = concentric_groups([high, low], tolerance=0.1)
                self.assertEqual([g.items for g in groups], [(low,), (high,)])


class TestArcsAround(unittest.TestCase):

    def _arc(self, c, r, sweep_deg):
        return CircleSeg(center=c, radius=r, start_angle=0.0, end_angle=math.radians(sweep_deg))

    def test_three_quarter_arc(self):
        (found,) = arcs_around((0, 0), 2.5, [self._arc((0, 0), 3, 270)], tolerance=0.1)
        self.assertAlmostEqual(found.sweep, 270)
        self.assertAlmostEqual(found.radius_ratio, 1.2)

    def test_only_larger_and_concentric_arcs(self):
        arcs = [self._arc((0, 0), 2, 270),       # smaller
                self._arc((5, 0), 3, 270),       # other centre
                self._arc((0, 0), 10, 90),
                self._arc((0, 0.05), 3, 270)]
        found = arcs_around((0, 0), 2.5, arcs, tolerance=0.1)
        self.assertEqual([a.arc for a in found], [arcs[3], arcs[2]])

    def test_ignores_what_is_not_an_arc(self):
        self.assertEqual(arcs_around((0, 0), 1, [CircleSeg(center=(0, 0), radius=2)], tolerance=0.1), [])

    def test_clockwise_arc(self):
        arc = CircleSeg(center=(0, 0), radius=3, start_angle=0.0, end_angle=math.radians(90), ccw=False)
        (found,) = arcs_around((0, 0), 2, [arc], tolerance=0.1)
        self.assertAlmostEqual(found.sweep, 270)


if __name__ == "__main__":
    unittest.main()
