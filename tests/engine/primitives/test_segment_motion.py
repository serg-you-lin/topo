"""
tests/engine/primitives/test_segment_motion.py
----------------------------------------
`.translated(dx, dy)`, `.mirrored(origin, angle)` and `.scaled(factor, origin)`
on every native primitive: the transformed curve is the previous curve
transformed. It is checked on the points of `discretize()` — the same ones
every reading reads — on a grid of cases: negative coordinates, near zero, far
from the origin, arcs both ways and straddling angle 0. Every case is a `subTest`.
"""

import math
import unittest

from topo.core.primitives.line import LineSeg
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.mathseg import segment_endpoints
from topo.core.primitives.conics import CircleSeg, EllipseSeg, HyperbolaSeg, ParabolaSeg
from topo.core.primitives.clothoid import ClothoidSeg
from topo.core.primitives.formula import FormulaSeg

# shifts: null, almost null, negative, far from the origin both ways
OFFSETS = [(0.0, 0.0), (1e-9, -1e-9), (-37.25, 12.5), (1e5, -1e5), (-3e6, 2.5e6)]
# precision relative to the size of the coordinates: a double has ~16 digits
RELATIVE = 1e-12


def _segments() -> list:
    """(name, segment): every primitive, in different positions and directions."""
    return [
        ("line", LineSeg(start=(-3.0, 4.0), end=(7.5, -2.25))),
        ("line near zero", LineSeg(start=(1e-12, -1e-12), end=(0.5, 0.0))),
        ("arc ccw", CircleSeg(center=(10.0, -5.0), radius=3.0, start_angle=0.3, end_angle=2.1)),
        ("arc cw", CircleSeg(center=(-2.0, 1.0), radius=0.75, start_angle=2.1, end_angle=0.3, ccw=False)),
        ("arc over 0", CircleSeg(center=(0.0, 0.0), radius=50.0, start_angle=-0.4, end_angle=0.4)),
        ("arc negative angles", CircleSeg(center=(1.0, 1.0), radius=2.0, start_angle=-2.5, end_angle=-1.0)),
        ("circle", CircleSeg(center=(-4.0, -6.0), radius=12.5)),
        ("circle small", CircleSeg(center=(0.0, 0.0), radius=0.02)),
        ("spline", BSplineSeg(degree=3, control_points=[(0, 0), (2, 5), (6, -3), (9, 1)],
                              knots=[0, 0, 0, 0, 1, 1, 1, 1])),
        ("nurbs", BSplineSeg(degree=2, control_points=[(1, 0), (1, 1), (0, 1)],
                             knots=[0, 0, 0, 1, 1, 1], weights=[1, math.sqrt(0.5), 1])),
        ("ellipse", EllipseSeg(center=(3.0, -2.0), major_axis=(8.0, 3.0), ratio=0.4,
                               start_param=0.0, end_param=2 * math.pi)),
        ("ellipse arc cw", EllipseSeg(center=(-1.0, 2.0), major_axis=(-2.0, 5.0), ratio=0.7,
                                      start_param=2.0, end_param=-0.5, ccw=False)),
        ("parabola", ParabolaSeg(vertex=(2.0, -1.0), focus=(2.6, -0.2), start_param=-3.0, end_param=4.5)),
        ("parabola backwards", ParabolaSeg(vertex=(-5.0, 3.0), focus=(-5.0, 2.5), start_param=2.0, end_param=-1.0)),
        ("hyperbola", HyperbolaSeg(center=(4.0, 4.0), major_axis=(1.5, -2.0), ratio=1.3, start_param=-1.1, end_param=0.9)),
        ("hyperbola backwards", HyperbolaSeg(center=(0.0, 0.0), major_axis=(-3.0, 0.5), ratio=0.4,
                                             start_param=1.4, end_param=0.2)),
        ("formula involute", FormulaSeg("r*(cos(t) + t*sin(t))", "r*(sin(t) - t*cos(t))", 0.2, 2.0, params={"r": 4.0})),
        ("formula backwards", FormulaSeg("t", "t**3 / 9 - exp(-t)", 2.5, -1.5)),
        ("clothoid", ClothoidSeg(origin=(1.0, -2.0), angle=0.4, a=5.0, start_param=-3.0, end_param=8.0)),
        ("clothoid right backwards", ClothoidSeg(origin=(-4.0, 6.0), angle=2.0, a=1.5, start_param=2.5,
                                                 end_param=0.5, left=False)),
    ]


def _close(a, b, scale: float) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= RELATIVE * max(1.0, scale)


# mirror axes (point, angle in radians): oblique, far, the y axis, the bisector
AXES = [((3.0, -2.0), 0.7), ((-1e4, 5e3), -1.2), ((0.0, 0.0), math.pi / 2), ((5.0, 5.0), math.pi / 4)]
# scale factors (about a centre): small, large, near 1
FACTORS = [(0.5, (0.0, 0.0)), (2.0, (3.0, -1.0)), (1e-3, (-50.0, 20.0)), (1e3, (1e4, -1e4)),
           (1.25, (7.0, 7.0))]
# fine step of the reference curve: a point of the curve is at most its sagitta from it
FINE = 1e-4


def _mirror(p, origin, angle):
    """`p` mirrored on the line through `origin` at `angle`, written separately here."""
    d = (math.cos(angle), math.sin(angle))
    v = (p[0] - origin[0], p[1] - origin[1])
    along = v[0] * d[0] + v[1] * d[1]
    return (origin[0] + 2 * along * d[0] - v[0], origin[1] + 2 * along * d[1] - v[1])


def _scale(p, factor, origin):
    return (origin[0] + (p[0] - origin[0]) * factor, origin[1] + (p[1] - origin[1]) * factor)


def _distance_to_polyline(p, points) -> float:
    best = math.inf
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length2 = dx * dx + dy * dy
        t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


class _OnCurve:
    """Every vertex of the transformed segment, brought back, lies on the starting
    curve; the ends are the transformed ends (direction included)."""

    def assert_on_curve(self, seg, moved, back, scale: float):
        reference = seg.discretize(tolerance=FINE)
        for q in moved.discretize(tolerance=0.01):
            d = _distance_to_polyline(back(q), reference)
            self.assertLessEqual(d, 2 * FINE + RELATIVE * max(1.0, scale), f"{q} fuori di {d}")

    def assert_ends(self, seg, moved, forward, scale: float):
        if (isinstance(seg, CircleSeg) and seg.full):
            # a circle has no starting point of its own: its "end" is always the point at
            # angle 0, not the image of the previous one
            return
        for p, q in zip(segment_endpoints(seg), segment_endpoints(moved)):
            self.assertTrue(_close(forward(p), q, scale), f"{forward(p)} ≠ {q}")


class TestTranslated(unittest.TestCase):

    def test_points_moved_by_the_same_amount(self):
        for name, seg in _segments():
            for dx, dy in OFFSETS:
                with self.subTest(segment=name, offset=(dx, dy)):
                    before = seg.discretize(tolerance=0.01)
                    after = seg.translated(dx, dy).discretize(tolerance=0.01)
                    self.assertEqual(len(after), len(before))
                    scale = max(abs(dx), abs(dy), *(abs(c) for p in before for c in p))
                    for p, q in zip(before, after):
                        self.assertTrue(_close((p[0] + dx, p[1] + dy), q, scale), f"{p} → {q}")

    def test_there_and_back_returns_to_the_segment(self):
        for name, seg in _segments():
            for dx, dy in OFFSETS:
                with self.subTest(segment=name, offset=(dx, dy)):
                    back = seg.translated(dx, dy).translated(-dx, -dy)
                    scale = max(abs(dx), abs(dy))
                    for p, q in zip(segment_endpoints(seg), segment_endpoints(back)):
                        self.assertTrue(_close(p, q, scale), f"{p} → {q}")


class TestMirrored(unittest.TestCase):

    def test_points_mirrored_on_the_x_axis(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                # also the full circle: a mirror reverses the direction
                before = seg.discretize(tolerance=0.01)
                after = seg.mirrored().discretize(tolerance=0.01)
                self.assertEqual(len(after), len(before))
                for p, q in zip(before, after):
                    self.assertTrue(_close((p[0], -p[1]), q, 100.0), f"{p} → {q}")

    def test_mirrored_ends_and_same_direction_of_travel(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                (s, e), (ms, me) = segment_endpoints(seg), segment_endpoints(seg.mirrored())
                self.assertTrue(_close((s[0], -s[1]), ms, 100.0))
                self.assertTrue(_close((e[0], -e[1]), me, 100.0))

    def test_twice_returns_to_the_segment(self):
        for name, seg in _segments():
            with self.subTest(segment=name):
                again = seg.mirrored().mirrored().discretize(tolerance=0.01)
                for p, q in zip(seg.discretize(tolerance=0.01), again):
                    self.assertTrue(_close(p, q, 100.0), f"{p} → {q}")



class TestMirroredOnAxis(unittest.TestCase, _OnCurve):

    def test_curve_mirrored_on_the_axis(self):
        for name, seg in _segments():
            for origin, angle in AXES:
                with self.subTest(segment=name, axis=(origin, angle)):
                    moved = seg.mirrored(origin=origin, angle=angle)
                    self.assertIs(type(moved), type(seg))
                    scale = max(1e2, *map(abs, origin))
                    self.assert_on_curve(seg, moved, lambda q: _mirror(q, origin, angle), scale)
                    self.assert_ends(seg, moved, lambda p: _mirror(p, origin, angle), scale)

    def test_twice_returns_to_the_segment(self):
        for name, seg in _segments():
            for origin, angle in AXES:
                with self.subTest(segment=name, axis=(origin, angle)):
                    again = seg.mirrored(origin=origin, angle=angle).mirrored(origin=origin, angle=angle)
                    scale = max(1e2, *map(abs, origin))
                    self.assert_ends(seg, again, lambda p: p, scale)
                    self.assert_on_curve(seg, again, lambda q: q, scale)

    def test_x_axis_by_default(self):
        # the default is the usual mirror, field by field
        for name, seg in _segments():
            with self.subTest(segment=name):
                self.assertEqual(seg.mirrored(), seg.mirrored(origin=(0.0, 0.0), angle=0.0))


class TestScaled(unittest.TestCase, _OnCurve):

    def test_scaled_curve(self):
        for name, seg in _segments():
            for factor, origin in FACTORS:
                with self.subTest(segment=name, factor=factor, origin=origin):
                    moved = seg.scaled(factor, origin=origin)
                    self.assertIs(type(moved), type(seg))
                    scale = max(1e2, *map(abs, origin)) * max(1.0, factor)
                    self.assert_on_curve(seg, moved, lambda q: _scale(q, 1 / factor, origin), scale)
                    self.assert_ends(seg, moved, lambda p: _scale(p, factor, origin), scale)

    def test_radius_and_axes_multiplied(self):
        arc = CircleSeg(center=(1.0, 2.0), radius=3.0, start_angle=0.3, end_angle=2.1, ccw=False)
        big = arc.scaled(2.5, origin=(1.0, 2.0))
        self.assertEqual((big.center, big.radius, big.start_angle, big.end_angle, big.ccw),
                         ((1.0, 2.0), 7.5, 0.3, 2.1, False))
        self.assertEqual(CircleSeg(center=(2.0, 0.0), radius=4.0).scaled(0.5),
                         CircleSeg(center=(1.0, 0.0), radius=2.0))
        ellipse = EllipseSeg(center=(0.0, 0.0), major_axis=(8.0, 3.0), ratio=0.4,
                             start_param=0.0, end_param=1.0).scaled(2.0)
        self.assertEqual((ellipse.major_axis, ellipse.ratio), ((16.0, 6.0), 0.4))

    def test_non_positive_factor_refused(self):
        line = LineSeg(start=(0.0, 0.0), end=(1.0, 0.0))
        for factor in (0.0, -1.0, math.nan, math.inf):
            with self.subTest(factor=factor):
                with self.assertRaises(ValueError):
                    line.scaled(factor)


if __name__ == "__main__":
    unittest.main()
