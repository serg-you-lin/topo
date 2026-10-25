"""
tests/unit/core/test_integrals.py

Area e baricentro esatti (D165) contro formule note: ogni primitiva, i due
versi, un giro misto, e la discretizzazione fine come controprova.
"""

import math

import pytest

from topo.core.geometry.integrals import ring_area, ring_centroid, ring_moments, segment_moments
from topo.core.primitives.segments import ArcSeg, BSplineSeg, CircleSeg, EllipseSeg, LineSeg

EPS = 1e-12


def _square(side=2.0, at=(0.0, 0.0)):
    x, y = at
    pts = [(x, y), (x + side, y), (x + side, y + side), (x, y + side)]
    return [LineSeg(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]


def _reversed(ring):
    return [s.reversed() for s in reversed(ring)]


def _shoelace(points):
    a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, points[1:] + points[:1]))
    return a / 2


def _sampled(seg, n):
    """`n` corde uniformi nel parametro: una retta resta una corda."""
    if isinstance(seg, LineSeg):
        return [seg.start]
    if isinstance(seg, EllipseSeg):
        sign = 1 if seg.ccw else -1
        return [seg._point_at(seg.start_param + sign * seg._sweep() * k / n) for k in range(n)]
    t0, t1 = seg.knots[seg.degree], seg.knots[-(seg.degree + 1)]
    return [seg._evaluate(t0 + (t1 - t0) * k / n) for k in range(n)]


def _dense_area(ring, n=4000):
    """Controprova indipendente: poligono a n e 2n corde, estrapolato (errore O(1/n²))."""
    coarse = abs(_shoelace([p for seg in ring for p in _sampled(seg, n)]))
    fine = abs(_shoelace([p for seg in ring for p in _sampled(seg, 2 * n)]))
    return (4 * fine - coarse) / 3


def test_quadrato():
    ring = _square(2.0, at=(1.0, 3.0))
    assert ring_area(ring) == pytest.approx(4.0, abs=EPS)
    assert ring_centroid(ring) == pytest.approx((2.0, 4.0), abs=EPS)


def test_verso_orario_cambia_segno_non_baricentro():
    ring = _square(2.0, at=(1.0, 3.0))
    assert ring_moments(_reversed(ring)).area == pytest.approx(-4.0, abs=EPS)
    assert ring_centroid(_reversed(ring)) == pytest.approx((2.0, 4.0), abs=EPS)


def test_cerchio():
    ring = [CircleSeg((5.0, -2.0), 10.0)]
    assert ring_area(ring) == pytest.approx(math.pi * 100, rel=1e-14)
    assert ring_centroid(ring) == pytest.approx((5.0, -2.0), abs=1e-12)


def test_arco_intero_come_il_cerchio():
    arc = ArcSeg((1.0, 1.0), 3.0, 0.7, 0.7 + 2 * math.pi)
    assert segment_moments(arc).area == pytest.approx(math.pi * 9, rel=1e-14)


@pytest.mark.parametrize("ccw", [True, False])
def test_mezzo_disco(ccw):
    r = 4.0
    if ccw:
        ring = [ArcSeg((0.0, 0.0), r, 0.0, math.pi, ccw=True), LineSeg((-r, 0.0), (r, 0.0))]
    else:
        ring = [LineSeg((r, 0.0), (-r, 0.0)), ArcSeg((0.0, 0.0), r, math.pi, 0.0, ccw=False)]
    m = ring_moments(ring)
    assert m.area == pytest.approx((1 if ccw else -1) * math.pi * r * r / 2, rel=1e-14)
    assert ring_centroid(ring) == pytest.approx((0.0, 4 * r / (3 * math.pi)), abs=1e-12)


def test_rettangolo_raccordato():
    L, W, r = 30.0, 12.0, 2.5
    a, b = L / 2, W / 2
    h = math.pi / 2
    ring = [
        LineSeg((-a + r, -b), (a - r, -b)), ArcSeg((a - r, -b + r), r, -h, 0.0),
        LineSeg((a, -b + r), (a, b - r)), ArcSeg((a - r, b - r), r, 0.0, h),
        LineSeg((a - r, b), (-a + r, b)), ArcSeg((-a + r, b - r), r, h, 2 * h),
        LineSeg((-a, b - r), (-a, -b + r)), ArcSeg((-a + r, -b + r), r, 2 * h, 3 * h),
    ]
    assert ring_area(ring) == pytest.approx(L * W - (4 - math.pi) * r * r, rel=1e-14)
    assert ring_centroid(ring) == pytest.approx((0.0, 0.0), abs=1e-12)


def test_ellisse_intera_ruotata():
    a, ratio, angle = 7.0, 0.4, 0.6
    ell = EllipseSeg((2.0, 3.0), (a * math.cos(angle), a * math.sin(angle)), ratio, 0.0, 2 * math.pi)
    assert ring_area([ell]) == pytest.approx(math.pi * a * a * ratio, rel=1e-14)
    assert ring_centroid([ell]) == pytest.approx((2.0, 3.0), abs=1e-12)


def test_mezza_ellisse_ruotata_contro_la_discretizzazione_fine():
    ell = EllipseSeg((2.0, 3.0), (5.0, 2.0), 0.5, 0.3, 0.3 + math.pi)
    start, end = ell._point_at(0.3), ell._point_at(0.3 + math.pi)
    ring = [ell, LineSeg(end, start)]
    assert ring_area(ring) == pytest.approx(math.pi * math.hypot(5, 2) ** 2 * 0.5 / 2, rel=1e-13)
    assert ring_area(ring) == pytest.approx(_dense_area(ring), rel=1e-11)


def test_segmento_parabolico():
    # Bézier quadratica (0,0)-(1,2)-(2,0): 2/3 del triangolo di controllo,
    # baricentro a 2/5 della freccia (1) dalla corda
    spline = BSplineSeg(2, [(0.0, 0.0), (1.0, 2.0), (2.0, 0.0)], [0, 0, 0, 1, 1, 1])
    ring = [spline, LineSeg((2.0, 0.0), (0.0, 0.0))]
    assert ring_moments(ring).area == pytest.approx(-4 / 3, rel=1e-14)
    assert ring_centroid(ring) == pytest.approx((1.0, 0.4), abs=1e-13)


def test_quarto_di_disco_razionale():
    w = math.sqrt(2) / 2
    arc = BSplineSeg(2, [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], [0, 0, 0, 1, 1, 1], weights=[1.0, w, 1.0])
    ring = [arc, LineSeg((0.0, 1.0), (0.0, 0.0)), LineSeg((0.0, 0.0), (1.0, 0.0))]
    assert ring_area(ring) == pytest.approx(math.pi / 4, rel=1e-13)
    c = 4 / (3 * math.pi)
    assert ring_centroid(ring) == pytest.approx((c, c), abs=1e-13)


def test_spline_cubica_a_piu_intervalli_contro_la_discretizzazione_fine():
    ctrl = [(0.0, 0.0), (1.0, 3.0), (3.0, 4.0), (5.0, 1.0), (6.0, 3.0), (8.0, 0.0)]
    spline = BSplineSeg(3, ctrl, [0, 0, 0, 0, 0.3, 0.55, 1, 1, 1, 1])
    ring = [spline, LineSeg((8.0, 0.0), (0.0, 0.0))]
    assert ring_area(ring) == pytest.approx(_dense_area(ring), rel=1e-11)


def test_traslare_sposta_il_baricentro_non_l_area():
    ring = [ArcSeg((0.0, 0.0), 4.0, 0.0, math.pi), LineSeg((-4.0, 0.0), (4.0, 0.0))]
    moved = [s.translated(10.0, -3.0) for s in ring]
    assert ring_area(moved) == pytest.approx(ring_area(ring), rel=1e-13)
    cx, cy = ring_centroid(ring)
    assert ring_centroid(moved) == pytest.approx((cx + 10.0, cy - 3.0), abs=1e-12)


def test_giro_senza_area_non_ha_baricentro():
    with pytest.raises(ValueError):
        ring_centroid([LineSeg((0.0, 0.0), (1.0, 0.0)), LineSeg((1.0, 0.0), (0.0, 0.0))])


def test_spline_periodica_chiusa_da_sola():
    # cubica uniforme non clamped: i primi tre punti ripetuti in coda la chiudono
    base = [(0.0, 0.0), (4.0, -1.0), (7.0, 2.0), (5.0, 6.0), (1.0, 5.0)]
    ctrl = base + base[:3]
    spline = BSplineSeg(3, ctrl, [float(k) for k in range(len(ctrl) + 4)])
    assert spline.periodic
    assert ring_area([spline]) == pytest.approx(_dense_area([spline]), rel=1e-11)


def test_un_salto_fra_segmenti_conta_come_la_sua_corda():
    # quadrato con un gap di 0.01 chiuso entro tolleranza: l'area non
    # dipende da dove sta il pezzo
    far = (1e5, -3e5)
    ring = [LineSeg((0.0, 0.0), (2.0, 0.0)), LineSeg((2.0, 0.0), (2.0, 2.0)),
            LineSeg((2.0, 2.0), (0.0, 2.0)), LineSeg((0.0, 2.0), (0.0, 0.01))]
    moved = [s.translated(*far) for s in ring]
    assert ring_area(ring) == pytest.approx(4.0, abs=EPS)
    assert ring_area(moved) == pytest.approx(4.0, abs=1e-6)
