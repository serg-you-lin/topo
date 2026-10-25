"""
tests/unit/core/test_rings.py

Fatti di un giro sulle primitive (D166): bbox esatto contro le formule,
perimetro, punti, e `ring_contains` contro il poligono fine di shapely su una
griglia di punti lontani dal bordo — ogni primitiva, i due versi, un salto.
"""

import math

import pytest
from shapely.geometry import Point as SPoint, Polygon

from topo.core.geometry.rings import ring_bbox, ring_contains, ring_perimeter, ring_points
from topo.core.primitives.segments import ArcSeg, BSplineSeg, CircleSeg, EllipseSeg, LineSeg

EPS = 1e-12


def _reversed(ring):
    return [s.reversed() for s in reversed(ring)]


def _rounded_rectangle(L=30.0, W=12.0, r=2.5):
    a, b, h = L / 2, W / 2, math.pi / 2
    return [
        LineSeg((-a + r, -b), (a - r, -b)), ArcSeg((a - r, -b + r), r, -h, 0.0),
        LineSeg((a, -b + r), (a, b - r)), ArcSeg((a - r, b - r), r, 0.0, h),
        LineSeg((a - r, b), (-a + r, b)), ArcSeg((-a + r, b - r), r, h, 2 * h),
        LineSeg((-a, b - r), (-a, -b + r)), ArcSeg((-a + r, -b + r), r, 2 * h, 3 * h),
    ]


def _concave_fillet():
    # quadrato 10×10 con un raccordo concavo r=3 sull'angolo in alto a destra
    return [LineSeg((0.0, 0.0), (10.0, 0.0)), LineSeg((10.0, 0.0), (10.0, 7.0)),
            ArcSeg((10.0, 10.0), 3.0, 1.5 * math.pi, math.pi, ccw=False),
            LineSeg((7.0, 10.0), (0.0, 10.0)), LineSeg((0.0, 10.0), (0.0, 0.0))]


def _big_arc():
    # arco di 300° chiuso dalla sua corda: il segmento di cerchio contiene il centro
    t0, t1 = math.radians(30), math.radians(330)
    arc = ArcSeg((0.0, 0.0), 5.0, t0, t1)
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
def test_contains_come_il_poligono_fine_lontano_dal_bordo(name, reverse):
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


@pytest.mark.parametrize("name", sorted(RINGS))
def test_un_punto_del_bordo_sta_dentro(name):
    ring = RINGS[name]
    for p in ring_points(ring, 0.5)[::3]:
        assert ring_contains(ring, p, tolerance=0.01)
        assert ring_contains(_reversed(ring), p, tolerance=0.01)


def test_sulla_corda_dentro_il_segmento_di_cerchio():
    # il punto sta sulla retta della corda di un arco, ma la corda non è bordo
    ring = [ArcSeg((0.0, 0.0), 5.0, 0.0, math.pi), LineSeg((-5.0, 0.0), (0.0, -5.0)),
            LineSeg((0.0, -5.0), (5.0, 0.0))]
    assert ring_contains(ring, (1.0, 0.0))
    assert ring_contains(ring, (0.0, 4.0))
    assert not ring_contains(ring, (6.0, 0.0))


def test_bbox_esatto_sugli_estremi_delle_curve():
    assert ring_bbox(_rounded_rectangle()) == pytest.approx((-15.0, -6.0, 15.0, 6.0), abs=EPS)
    assert ring_bbox([CircleSeg((1.0, -2.0), 4.0)]) == pytest.approx((-3.0, -6.0, 5.0, 2.0), abs=EPS)
    # arco di 300° da 30°: tocca x = -5, y = ±5, non x = +5
    xmin, ymin, xmax, ymax = ring_bbox(_big_arc())
    assert (xmin, ymin, ymax) == pytest.approx((-5.0, -5.0, 5.0), abs=EPS)
    assert xmax == pytest.approx(5 * math.cos(math.radians(30)), abs=EPS)
    # ellisse ruotata: semiampiezze sqrt(a²cos² + b²sin²), sqrt(a²sin² + b²cos²)
    a, b, t = 7.0, 2.8, 0.6
    hx = math.sqrt((a * math.cos(t)) ** 2 + (b * math.sin(t)) ** 2)
    hy = math.sqrt((a * math.sin(t)) ** 2 + (b * math.cos(t)) ** 2)
    assert ring_bbox(RINGS["ellisse_ruotata"]) == pytest.approx((2 - hx, 3 - hy, 2 + hx, 3 + hy), abs=1e-12)


def test_perimetro_con_le_corde_dei_salti():
    L, W, r = 30.0, 12.0, 2.5
    assert ring_perimeter(_rounded_rectangle(L, W, r)) == pytest.approx(
        2 * (L + W) - 8 * r + 2 * math.pi * r, rel=1e-14)
    assert ring_perimeter(_with_jump()) == pytest.approx(8.0, abs=EPS)


def test_punti_senza_ripetere_il_primo():
    pts = ring_points(_with_jump())
    assert pts[0] == (0.0, 0.0) and pts[-1] == (0.0, 0.01)
    assert len(pts) == len(set(pts)) == 5
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pts)
