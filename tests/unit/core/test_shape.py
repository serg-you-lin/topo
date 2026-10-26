# tests/unit/core/test_shape.py
"""`contour_shape`: fatti di forma di un contorno chiuso (D68)."""

import math
import unittest

import topo
from topo.core.primitives.segments import ArcSeg, CircleSeg, EllipseSeg, LineSeg, BSplineSeg
from topo.core.geometry.shape import (
    CIRCLE, ELLIPSE, OTHER, POLYGON, RECTANGLE, STADIUM, ShapeKind, contour_shape, merge_runs,
)
from topo.core.topology.edge import Edge
from topo.model.document import Document

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5


def _ring(*pts):
    return [LineSeg(start=pts[i], end=pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _stadium(c1, c2, r):
    """Stadio orizzontale fra i centri c1 e c2 (stessa y), percorsa in senso antiorario."""
    (x1, y), (x2, _) = c1, c2
    return [
        LineSeg(start=(x1, y - r), end=(x2, y - r)),
        ArcSeg(center=c2, radius=r, start_angle=-math.pi / 2, end_angle=math.pi / 2, ccw=True),
        LineSeg(start=(x2, y + r), end=(x1, y + r)),
        ArcSeg(center=c1, radius=r, start_angle=math.pi / 2, end_angle=3 * math.pi / 2, ccw=True),
    ]


class TestContourShape(unittest.TestCase):

    def test_cerchio(self):
        s = contour_shape([CircleSeg(center=(10, 20), radius=3)])
        self.assertEqual(s.kind, CIRCLE)
        self.assertAlmostEqual(s.diameter, 6)
        self.assertEqual(s.center, (10, 20))
        self.assertIsNone(s.angle)

    def test_cerchio_in_quattro_archi(self):
        arcs = [ArcSeg(center=(0, 0), radius=5, start_angle=k * math.pi / 2,
                       end_angle=(k + 1) * math.pi / 2) for k in range(4)]
        s = contour_shape(arcs)
        self.assertEqual(s.kind, CIRCLE)
        self.assertAlmostEqual(s.diameter, 10)

    def test_stadio(self):
        s = contour_shape(_stadium((0, 0), (20, 0), 4))
        self.assertEqual(s.kind, STADIUM)
        self.assertAlmostEqual(s.length, 28)
        self.assertAlmostEqual(s.width, 8)
        self.assertAlmostEqual(s.angle, 0)
        self.assertEqual(s.center, (10, 0))

    def test_rettangolo_ruotato(self):
        c, a = math.cos(math.radians(30)), math.sin(math.radians(30))
        pts = [(0, 0), (40 * c, 40 * a), (40 * c - 10 * a, 40 * a + 10 * c), (-10 * a, 10 * c)]
        s = contour_shape(_ring(*pts))
        self.assertEqual(s.kind, RECTANGLE)
        self.assertAlmostEqual(s.length, 40)
        self.assertAlmostEqual(s.width, 10)
        self.assertAlmostEqual(s.angle, 30)

    def test_lato_spezzato_resta_rettangolo(self):
        s = contour_shape(_ring((0, 0), (50, 0), (100, 0), (100, 30), (0, 30)))
        self.assertEqual(s.kind, RECTANGLE)
        self.assertEqual(s.sides, 4)

    def test_poligono(self):
        s = contour_shape(_ring((0, 0), (10, 0), (5, 8)))
        self.assertEqual(s.kind, POLYGON)
        self.assertEqual(s.sides, 3)

    def test_altro(self):
        # rettangolo con un angolo raccordato
        segs = [LineSeg(start=(0, 0), end=(20, 0)),
                LineSeg(start=(20, 0), end=(20, 5)),
                ArcSeg(center=(15, 5), radius=5, start_angle=0, end_angle=math.pi / 2),
                LineSeg(start=(15, 10), end=(0, 10)),
                LineSeg(start=(0, 10), end=(0, 0))]
        self.assertEqual(contour_shape(segs).kind, OTHER)

    def test_vuoto(self):
        self.assertIsNone(contour_shape([]))


class TestShapeKindStabile(unittest.TestCase):
    """
    D136: l'elenco dei kind è chiuso e il kind di un contorno non cambia nella
    1.x. Un kind in più, o un contorno che cambia kind, deve rompere qui.
    """

    def test_elenco_chiuso(self):
        self.assertEqual({k.value for k in ShapeKind},
                         {"circle", "ellipse", "stadium", "rectangle", "polygon", "other"})

    def test_il_kind_si_confronta_e_si_stampa_come_stringa(self):
        s = contour_shape([CircleSeg(center=(0, 0), radius=1)])
        self.assertEqual(s.kind, "circle")
        self.assertEqual(f"{s.kind}", "circle")
        self.assertEqual(s.to_dict()["kind"], "circle")

    def test_quadrato_e_un_rettangolo(self):
        s = contour_shape(_ring((0, 0), (10, 0), (10, 10), (0, 10)))
        self.assertEqual(s.kind, RECTANGLE)
        self.assertAlmostEqual(s.length, s.width)

    def test_ellisse(self):
        s = contour_shape([EllipseSeg(center=(1, 2), major_axis=(10, 0), ratio=0.5,
                                      start_param=0, end_param=2 * math.pi)])
        self.assertEqual(s.kind, ELLIPSE)
        self.assertAlmostEqual(s.length, 20)
        self.assertAlmostEqual(s.width, 10)
        self.assertAlmostEqual(s.angle, 0)
        self.assertEqual(s.center, (1, 2))

    def test_ellisse_ad_assi_uguali_e_un_cerchio(self):
        # stessi punti di un cerchio, esattamente: non un'approssimazione
        s = contour_shape([EllipseSeg(center=(0, 0), major_axis=(0, 4), ratio=1.0,
                                      start_param=0, end_param=2 * math.pi)])
        self.assertEqual(s.kind, CIRCLE)
        self.assertAlmostEqual(s.diameter, 8)

    def test_foro_in_isometria_in_due_meta(self):
        # un cerchio visto in isometria, spezzato da due nodi: due metà della
        # stessa ellisse, la seconda con l'asse maggiore girato di 180°
        top = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5, start_param=0, end_param=math.pi)
        bottom = EllipseSeg(center=(0, 0), major_axis=(-10, 0), ratio=0.5, start_param=0, end_param=math.pi)
        s = contour_shape([top, bottom])
        self.assertEqual(s.kind, ELLIPSE)
        self.assertAlmostEqual(s.length, 20)
        self.assertAlmostEqual(s.width, 10)
        self.assertEqual(s.sides, 2)

    def test_mezza_ellisse_non_e_un_ellisse(self):
        half = EllipseSeg(center=(0, 0), major_axis=(10, 0), ratio=0.5, start_param=0, end_param=math.pi)
        self.assertEqual(contour_shape([half, LineSeg(start=(-10, 0), end=(10, 0))]).kind, OTHER)

    def test_cerchio_fatto_di_spline_resta_altro(self):
        # cerchio esatto come NURBS razionale quadratica: la regola legge le
        # primitive come sono, il riconoscimento è un passo del chiamante
        w = math.sqrt(2) / 2
        spline = BSplineSeg(
            degree=2,
            control_points=[(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0)],
            knots=[0, 0, 0, .25, .25, .5, .5, .75, .75, 1, 1, 1],
            weights=[1, w, 1, w, 1, w, 1, w, 1],
        )
        self.assertEqual(contour_shape([spline]).kind, OTHER)

    def test_rettangolo_raccordato_e_altro(self):
        # quattro spigoli a raggio 2: serve una misura in più del record
        r = 2
        segs = [LineSeg(start=(r, 0), end=(20 - r, 0)),
                ArcSeg(center=(20 - r, r), radius=r, start_angle=-math.pi / 2, end_angle=0),
                LineSeg(start=(20, r), end=(20, 10 - r)),
                ArcSeg(center=(20 - r, 10 - r), radius=r, start_angle=0, end_angle=math.pi / 2),
                LineSeg(start=(20 - r, 10), end=(r, 10)),
                ArcSeg(center=(r, 10 - r), radius=r, start_angle=math.pi / 2, end_angle=math.pi),
                LineSeg(start=(0, 10 - r), end=(0, r)),
                ArcSeg(center=(r, r), radius=r, start_angle=math.pi, end_angle=3 * math.pi / 2)]
        self.assertEqual(contour_shape(segs).kind, OTHER)


class TestMisureSullePrimitive(unittest.TestCase):
    """`length`/`width` di `other` misurati sulla curva, non sul poligono inscritto (D156)."""

    def test_d_ruotata(self):
        # semicerchio r 10 chiuso dal diametro, ruotato di 20°: 20 × 10 esatti,
        # mentre il poligono inscritto è più corto fino a 2·tol
        a = math.radians(20)
        arc = ArcSeg(center=(5, 7), radius=10, start_angle=a - math.pi / 2, end_angle=a + math.pi / 2)
        s = contour_shape([arc, LineSeg(start=arc._point_at(a + math.pi / 2),
                                        end=arc._point_at(a - math.pi / 2))])
        self.assertEqual(s.kind, OTHER)
        self.assertAlmostEqual(s.length, 20, places=9)
        self.assertAlmostEqual(s.width, 10, places=9)

    def test_d_grande_oltre_la_tolleranza(self):
        # la stessa D a r 500: la polilinea a tol 0.01 resta indietro di quasi
        # 0.01 sulla larghezza (sagitta), la misura no
        a = math.radians(20)
        arc = ArcSeg(center=(0, 0), radius=500, start_angle=a - math.pi / 2, end_angle=a + math.pi / 2)
        s = contour_shape([arc, LineSeg(start=arc._point_at(a + math.pi / 2),
                                        end=arc._point_at(a - math.pi / 2))])
        self.assertAlmostEqual(s.length, 1000, places=7)
        self.assertAlmostEqual(s.width, 500, places=7)

    def test_spline_misurata_sulla_curva(self):
        from topo.core.geometry.measure import segment_reach
        from topo.core.geometry.points import interpolate_bspline
        pts = [(50 * math.cos(t), 50 * math.sin(t)) for t in (i * 2 * math.pi / 12 for i in range(13))]
        cp, kn = interpolate_bspline(pts, 3)
        spline = BSplineSeg(degree=3, control_points=cp, knots=kn)
        dense = spline.discretize(1e-7)
        for d in ((1, 0), (0, 1), (1, 1), (-0.3, 1)):
            n = math.hypot(*d)
            proj = [(p[0] * d[0] + p[1] * d[1]) / n for p in dense]
            lo, hi = segment_reach(spline, d)
            # la curva vera arriva almeno dove arrivano i suoi punti, e non oltre la tolleranza densa
            self.assertLessEqual(lo, min(proj) + 1e-9)
            self.assertGreaterEqual(hi, max(proj) - 1e-9)
            self.assertAlmostEqual(lo, min(proj), delta=1e-6)
            self.assertAlmostEqual(hi, max(proj), delta=1e-6)

    def test_ellisse_ruotata(self):
        from topo.core.geometry.measure import segment_reach
        a = math.radians(20)
        e = EllipseSeg(center=(3, 4), major_axis=(10 * math.cos(a), 10 * math.sin(a)),
                       ratio=0.4, start_param=0, end_param=2 * math.pi)
        half = math.hypot(10 * math.cos(a), 4 * math.sin(a))
        lo, hi = segment_reach(e, (1, 0))
        self.assertAlmostEqual(lo, 3 - half, places=12)
        self.assertAlmostEqual(hi, 3 + half, places=12)

    def test_arco_che_non_passa_per_l_estremo(self):
        from topo.core.geometry.measure import segment_reach
        # quarto in alto a destra percorso al contrario: lungo x va da 0 a r, mai a −r
        arc = ArcSeg(center=(0, 0), radius=4, start_angle=math.pi / 2, end_angle=0, ccw=False)
        lo, hi = segment_reach(arc, (1, 0))
        self.assertAlmostEqual(lo, 0, places=12)
        self.assertAlmostEqual(hi, 4, places=12)


def _edge(seg):
    pts = seg.discretize()
    return Edge(role="unknown", start=pts[0], end=pts[-1], segment=seg)


class TestContourShapeSuIsole(unittest.TestCase):
    """Stesso fatto di forma dalle due letture."""

    def _doc(self):
        segs = (_ring((0, 0), (100, 0), (100, 50), (0, 50))
                + [CircleSeg(center=(15, 25), radius=4)]
                + _stadium((40, 25), (70, 25), 5))
        return Document(edges=[_edge(s) for s in segs], texts=[],
                             source_meta={"tolerance": 0.05}, source_path="")

    def _kinds(self, cluster):
        return sorted(contour_shape(c).kind for c in cluster.inners)

    def test_island(self):
        # D161: island() non fa inner; i pezzi che chiudono da sé sono in loose (D162)
        result = topo.island(self._doc(), max_gap=MAX_GAP)
        self.assertEqual(contour_shape(result.clusters[0].outer).kind, RECTANGLE)
        kinds = sorted(s.kind for s in map(contour_shape, result.loose) if s is not None)
        self.assertEqual(kinds, [CIRCLE, STADIUM])

    def test_heal(self):
        cluster = topo.heal(self._doc()).clusters[0]
        self.assertEqual(contour_shape(cluster.outer).kind, RECTANGLE)
        self.assertEqual(self._kinds(cluster), [CIRCLE, STADIUM])



class TestMergeRuns(unittest.TestCase):

    def test_arcs_across_angle_zero_add_their_sweeps(self):
        # da 3π/2 a 2π e da 0 a π/2: un arco solo di π, non uno di ampiezza nulla
        ring = [ArcSeg(center=(0, 0), radius=1, start_angle=3 * math.pi / 2, end_angle=2 * math.pi, ccw=True),
                ArcSeg(center=(0, 0), radius=1, start_angle=0.0, end_angle=math.pi / 2, ccw=True),
                LineSeg(start=(0, 1), end=(0, -1))]
        merged, _ = merge_runs(ring, [None] * 3)
        self.assertEqual(len(merged), 2)
        self.assertAlmostEqual(merged[0]._sweep(), math.pi)
        self.assertAlmostEqual(math.cos(merged[0].end_angle), 0)
        self.assertAlmostEqual(math.sin(merged[0].end_angle), 1)


if __name__ == "__main__":
    unittest.main()
