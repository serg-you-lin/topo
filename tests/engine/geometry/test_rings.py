"""
tests/engine/geometry/test_rings.py

Facts of a loop on the primitives: exact bbox against the formulas, perimeter,
points, and `ring_contains` against shapely's fine polygon on a grid of points
far from the border — every primitive, both directions, a jump.
"""

import math

import pytest
import random

from shapely.geometry import LineString, Point as SPoint, Polygon
from shapely.ops import split

from topo.core.geometry.rings import (
    ring_bbox, ring_contains, ring_covers_chord, ring_perimeter, ring_points, ring_split_by_chord,
)
from topo.core.primitives.spline import BSplineSeg
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg, EllipseSeg

EPS = 1e-12


def _reversed(ring):
    return [s.reversed() for s in reversed(ring)]


def _rounded_rectangle(L=30.0, W=12.0, r=2.5):
    a, b, h = L / 2, W / 2, math.pi / 2
    return [
        LineSeg((-a + r, -b), (a - r, -b)), CircleSeg((a - r, -b + r), r, -h, 0.0),
        LineSeg((a, -b + r), (a, b - r)), CircleSeg((a - r, b - r), r, 0.0, h),
        LineSeg((a - r, b), (-a + r, b)), CircleSeg((-a + r, b - r), r, h, 2 * h),
        LineSeg((-a, b - r), (-a, -b + r)), CircleSeg((-a + r, -b + r), r, 2 * h, 3 * h),
    ]


def _concave_fillet():
    # 10×10 square with a concave r=3 fillet on the top-right corner
    return [LineSeg((0.0, 0.0), (10.0, 0.0)), LineSeg((10.0, 0.0), (10.0, 7.0)),
            CircleSeg((10.0, 10.0), 3.0, 1.5 * math.pi, math.pi, ccw=False),
            LineSeg((7.0, 10.0), (0.0, 10.0)), LineSeg((0.0, 10.0), (0.0, 0.0))]


def _big_arc():
    # 300° arc closed by its chord: the circle segment contains the centre
    t0, t1 = math.radians(30), math.radians(330)
    arc = CircleSeg((0.0, 0.0), 5.0, t0, t1)
    s, e = arc._point_at(t0), arc._point_at(t1)
    return [arc, LineSeg(e, s)]


def _half_ellipse():
    ell = EllipseSeg((2.0, 3.0), (5.0, 2.0), 0.5, 0.3, 0.3 + math.pi)
    return [ell, LineSeg(ell._point_at(0.3 + math.pi), ell._point_at(0.3))]


def _spline_cap():
    ctrl = [(0.0, 0.0), (1.0, 3.0), (3.0, 4.0), (5.0, 1.0), (6.0, 3.0), (8.0, 0.0)]
    return [BSplineSeg(3, ctrl, [0, 0, 0, 0, 0.3, 0.55, 1, 1, 1, 1]), LineSeg((8.0, 0.0), (0.0, 0.0))]


def _with_jump():
    return [LineSeg((0.0, 0.0), (2.0, 0.0)), LineSeg((2.0, 0.0), (2.0, 2.0)),
            LineSeg((2.0, 2.0), (0.0, 2.0)), LineSeg((0.0, 2.0), (0.0, 0.01))]


RINGS = {
    "rettangolo_raccordato": _rounded_rectangle(),
    "raccordo_concavo": _concave_fillet(),
    "arco_di_300": _big_arc(),
    "cerchio": [CircleSeg((1.0, -2.0), 4.0)],
    "ellisse_ruotata": [EllipseSeg((2.0, 3.0), (7 * math.cos(0.6), 7 * math.sin(0.6)), 0.4, 0.0, 2 * math.pi)],
    "mezza_ellisse": _half_ellipse(),
    "spline": _spline_cap(),
    "salto": _with_jump(),
}


@pytest.mark.parametrize("name", sorted(RINGS))
@pytest.mark.parametrize("reverse", [False, True])
def test_contains_like_the_fine_polygon_far_from_the_border(name, reverse):
    ring = _reversed(RINGS[name]) if reverse else RINGS[name]
    polygon = Polygon(ring_points(ring, 1e-5))
    xmin, ymin, xmax, ymax = ring_bbox(ring)
    n = 40
    checked = 0
    for i in range(n + 1):
        for j in range(n + 1):
            p = (xmin - 1 + (xmax - xmin + 2) * i / n, ymin - 1 + (ymax - ymin + 2) * j / n)
            if polygon.exterior.distance(SPoint(p)) < 1e-3:
                continue
            assert ring_contains(ring, p) == polygon.contains(SPoint(p)), p
            checked += 1
    assert checked > n * n // 2


def _chords(ring, polygon, n=150, seed=7):
    """Random chords in the enlarged bbox, away from a tangent touch: every meeting
    with the border is a clean crossing or there is none (the fine polygon and the
    primitives can differ only there)."""
    rnd = random.Random(seed)
    xmin, ymin, xmax, ymax = ring_bbox(ring)
    w, h = xmax - xmin, ymax - ymin
    out = []
    while len(out) < n:
        a = (xmin - w / 4 + rnd.random() * w * 1.5, ymin - h / 4 + rnd.random() * h * 1.5)
        b = (xmin - w / 4 + rnd.random() * w * 1.5, ymin - h / 4 + rnd.random() * h * 1.5)
        line = LineString([a, b])
        if line.length < 1e-3 or min(polygon.exterior.distance(SPoint(p)) for p in (a, b)) < 1e-2:
            continue
        # no tangencies: moved by ±1e-2 the chord meets the border the same number of times
        if len({_meets(line.offset_curve(d), polygon) for d in (-1e-2, 1e-2)}) != 1:
            continue
        out.append((a, b))
    return out


def _meets(line, polygon):
    hit = line.intersection(polygon.exterior)
    return len(getattr(hit, "geoms", [hit])) if not hit.is_empty else 0


@pytest.mark.parametrize("name", sorted(RINGS))
def test_dividing_chord_and_covered_chord_like_shapely(name):
    ring = RINGS[name]
    polygon = Polygon(ring_points(ring, 1e-5))
    for a, b in _chords(ring, polygon):
        line = LineString([a, b])
        assert ring_split_by_chord(ring, a, b) == (len(split(polygon, line).geoms) >= 2), (a, b)
        assert ring_split_by_chord(_reversed(ring), a, b) == ring_split_by_chord(ring, a, b)
        assert ring_covers_chord(ring, a, b) == polygon.buffer(1e-6).covers(line), (a, b)


def test_chord_on_the_border_is_a_touch():
    ring = _rounded_rectangle()              # 30×12, raccordi r=2.5
    assert not ring_split_by_chord(ring, (-10.0, -6.0), (10.0, -6.0))     # on the side
    assert ring_covers_chord(ring, (-10.0, -6.0), (10.0, -6.0))
    assert not ring_split_by_chord(ring, (-20.0, 6.0), (20.0, 6.0))       # along the top side
    assert ring_split_by_chord(ring, (0.0, -7.0), (0.0, 7.0))
    assert ring_split_by_chord(ring, (0.0, -6.0), (0.0, 6.0))             # from border to border, ends on the border
    assert not ring_split_by_chord(ring, (0.0, -6.0), (0.0, 0.0))         # entra e si ferma


@pytest.mark.parametrize("name", sorted(RINGS))
def test_a_border_point_is_inside(name):
    ring = RINGS[name]
    for p in ring_points(ring, 0.5)[::3]:
        assert ring_contains(ring, p, tolerance=0.01)
        assert ring_contains(_reversed(ring), p, tolerance=0.01)


def test_on_the_chord_inside_the_circle_segment():
    # the point lies on the line of an arc's chord, but the chord is not border
    ring = [CircleSeg((0.0, 0.0), 5.0, 0.0, math.pi), LineSeg((-5.0, 0.0), (0.0, -5.0)),
            LineSeg((0.0, -5.0), (5.0, 0.0))]
    assert ring_contains(ring, (1.0, 0.0))
    assert ring_contains(ring, (0.0, 4.0))
    assert not ring_contains(ring, (6.0, 0.0))


@pytest.mark.parametrize("motion", [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
                                    (0.7, 3.1, -2.2), (2.4, -0.37, 0.61)])
def test_on_the_chord_and_beside_it_under_motion(motion):
    # which side of the chord the point is on is the sign of `cross_pt`, zero on the
    # chord. Proof: on the chord (where the guard decides in place of the sign) and
    # at 1e-7 / 5e-9 to the side (where the sign decides, which is geometry) the
    # answer does not change with the motion. Without the guard (4.9, 0) comes out
    # at (2.4, -0.37, 0.61). It does not prove the line inside the readings: it is
    # reached by snapbend (`splits_contour`, `bridged_runs`), not `faces()` nor `outlines()`.
    from tests.invariants import rigid
    move_seg, move_pt = rigid(*motion)
    ring = [CircleSeg((0.0, 0.0), 5.0, 0.0, math.pi), LineSeg((-5.0, 0.0), (0.0, -5.0)),
            LineSeg((0.0, -5.0), (5.0, 0.0))]
    ring = [move_seg(s) for s in ring]
    points = [(1, 0), (4.9, 0), (-4.99, 0), (1, 1e-7), (1, -1e-7), (4.9, -1e-7), (0, 5e-9), (0, -5e-9)]
    assert all(ring_contains(ring, move_pt(p), 1e-12) for p in points)


@pytest.mark.parametrize("motion", [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
                                    (0.7, 3.1, -2.2), (2.4, -0.37, 0.61)])
def test_astride_the_guard_on_the_chord(motion):
    # within 1e-9 rad of the chord the point is given inside the circle segment.
    # Proof: across the threshold (points at 1e-9, 2.5e-9, 3e-9, 1e-6 from the
    # chord, on both sides), with the chord inside the loop (convex arc) and outside
    # (biting arc), the answer is the same at every motion. The threshold's value
    # matters little: taking the wrong branch changes the arc's angle by the
    # threshold itself, and the loop is rounded; with 0.5 rad or 1e-17 these points
    # come out equal. It does not prove the line inside the readings (reached by
    # snapbend, not `faces()` nor `outlines()`).
    from tests.invariants import rigid
    move_seg, move_pt = rigid(*motion)
    convex = [CircleSeg((0.0, 0.0), 5.0, 0.0, math.pi), LineSeg((-5.0, 0.0), (0.0, -5.0)),
              LineSeg((0.0, -5.0), (5.0, 0.0))]
    bite = [LineSeg((-5.0, -10.0), (5.0, -10.0)), LineSeg((5.0, -10.0), (5.0, 0.0)),
            CircleSeg((0.0, 0.0), 5.0, 0.0, math.pi, ccw=False), LineSeg((-5.0, 0.0), (-5.0, -10.0))]
    points = [(x, d) for x in (0.0, 3.0, -4.5)
              for d in (0.0, 1e-9, -1e-9, 2.5e-9, -2.5e-9, 3e-9, -3e-9, 1e-6, -1e-6)]
    for ring, expected in ((convex, True), (bite, False)):
        ring = [move_seg(s) for s in ring]
        assert [ring_contains(ring, move_pt(p), 1e-12) for p in points] == [expected] * len(points)


def test_exact_bbox_on_the_curve_extremes():
    assert ring_bbox(_rounded_rectangle()) == pytest.approx((-15.0, -6.0, 15.0, 6.0), abs=EPS)
    assert ring_bbox([CircleSeg((1.0, -2.0), 4.0)]) == pytest.approx((-3.0, -6.0, 5.0, 2.0), abs=EPS)
    # 300° arc from 30°: touches x = -5, y = ±5, not x = +5
    xmin, ymin, xmax, ymax = ring_bbox(_big_arc())
    assert (xmin, ymin, ymax) == pytest.approx((-5.0, -5.0, 5.0), abs=EPS)
    assert xmax == pytest.approx(5 * math.cos(math.radians(30)), abs=EPS)
    # ellisse ruotata: semiampiezze sqrt(a²cos² + b²sin²), sqrt(a²sin² + b²cos²)
    a, b, t = 7.0, 2.8, 0.6
    hx = math.sqrt((a * math.cos(t)) ** 2 + (b * math.sin(t)) ** 2)
    hy = math.sqrt((a * math.sin(t)) ** 2 + (b * math.cos(t)) ** 2)
    assert ring_bbox(RINGS["ellisse_ruotata"]) == pytest.approx((2 - hx, 3 - hy, 2 + hx, 3 + hy), abs=1e-12)


def test_perimeter_with_the_chords_of_the_leaps():
    L, W, r = 30.0, 12.0, 2.5
    assert ring_perimeter(_rounded_rectangle(L, W, r)) == pytest.approx(
        2 * (L + W) - 8 * r + 2 * math.pi * r, rel=1e-14)
    assert ring_perimeter(_with_jump()) == pytest.approx(8.0, abs=EPS)


def test_points_without_repeating_the_first():
    pts = ring_points(_with_jump())
    assert pts[0] == (0.0, 0.0) and pts[-1] == (0.0, 0.01)
    assert len(pts) == len(set(pts)) == 5
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pts)
