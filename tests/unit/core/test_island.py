# tests/unit/core/test_island.py

import math
import unittest
import topo
from topo.model.document import Document
from topo.model.role import ContourRole
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import LineSeg, CircleSeg
from topo.core.base.normalizer import refit_tessellations
from topo.core.primitives.segments import ArcSeg
from topo import to_shapely

# max_gap non ha default (D98); island_gap non esiste più (D99)
MAX_GAP = 0.5


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _circle(center, radius):
    pt = (center[0] + radius, center[1])
    return Edge(role="unknown", start=pt, end=pt, segment=CircleSeg(center=center, radius=radius))


def _doc(edges):
    return Document(edges=edges, texts=[], source_meta={"tolerance": 0.05}, source_path="")


class TestIsland(unittest.TestCase):

    def test_due_viste_separate_due_cluster(self):
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + _poly((50, 0), (60, 0), (60, 5), (50, 5))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 2)
        self.assertEqual([round(to_shapely(c.outer).area) for c in result.clusters], [100, 50])

    def test_isola_dentro_un_altra_va_in_loose(self):
        # D161: cornice 100x100 e una vista dentro — l'unico contorno è la
        # cornice, la vista va in loose con l'isola che la contiene; i suoi
        # lati chiudono da sé, quindi è un pezzo chiuso solo (D162)
        edges = _poly((0, 0), (100, 0), (100, 100), (0, 100)) + _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 10000.0)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual([t.cluster_ref for t in result.loose], [0])
        self.assertAlmostEqual(to_shapely(result.loose[0]).area, 400.0)

    def test_due_contorni_vicinissimi_restano_due_isole(self):
        # D99: nessuna distanza fra le viste — due contorni a 1 mm sono due isole
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + _poly((11, 0), (21, 0), (21, 5), (11, 5))
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 2)

    def test_linea_aperta_dentro_una_vista_e_sua(self):
        # D99: un asse dentro la vista che non tocca il contorno va in trash con cluster_ref della vista;
        # una linea fuori da ogni contorno resta senza isola
        view = _poly((0, 0), (100, 0), (100, 50), (0, 50))
        small = _poly((200, 0), (210, 0), (210, 10), (200, 10))
        axis, loose = _line((10, 25), (90, 25)), _line((300, 0), (320, 0))
        result = topo.heal(_doc(view + small + [axis, loose]), max_gap=MAX_GAP).outlines()
        refs = {round(t.segments[0].start[0]): t.cluster_ref for t in result.loose}
        self.assertEqual(refs, {10: 0, 300: None})

    def test_gruppo_di_cerchi_staccati_dentro_una_vista_in_loose(self):
        # D161: tre cerchi staccati dal bordo dentro la vista vanno in loose,
        # interi, con l'isola che li contiene
        edges = _poly((0, 0), (200, 0), (200, 100), (0, 100)) + [
            _circle((90, 50), 3), _circle((100, 50), 5.5), _circle((110, 50), 3)]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual(sorted(s.radius for t in result.loose for s in t.segments), [3, 3, 5.5])
        self.assertEqual({t.cluster_ref for t in result.loose}, {0})

    def test_cerchio_dentro_una_vista_in_loose(self):
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(result.clusters[0].outer.role, ContourRole.OUTER)
        self.assertEqual(result.clusters[0].inners, [])
        self.assertEqual([(type(s).__name__, s.radius, t.cluster_ref) for t in result.loose for s in t.segments],
                         [("CircleSeg", 3, 0)])

    def test_cerchio_tagliato_dagli_assi_esce_intero(self):
        # gli assi incrociano il cerchio nella rete piana: in loose il
        # cerchio esce intatto, non nei 4 archi della rete (D161)
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_circle((10, 10), 3)]
        edges += [_line((5, 10), (15, 10)), _line((10, 5), (10, 15))]
        result = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines()
        self.assertEqual(sorted(type(s).__name__ for t in result.loose for s in t.segments),
                         ["CircleSeg", "LineSeg", "LineSeg"])

    def test_lato_tagliato_da_un_asse_torna_un_segmento(self):
        # un asse che esce dal contorno lo spezza: il contorno esterno resta di 4 lati
        edges = _poly((0, 0), (20, 0), (20, 20), (0, 20)) + [_line((10, -5), (10, 25))]
        outer = topo.heal(_doc(edges), max_gap=MAX_GAP).outlines().clusters[0].outer
        self.assertEqual(len(outer.segments), 4)

    def test_cornice_marcata_resta_fuori(self):
        # D30: snapdraw marca la cornice → outlines() non la legge, resta in loose
        # col suo ruolo; chiusa da sé, esce come una curva chiusa (D162, D189)
        frame = _poly((0, 0), (100, 0), (100, 100), (0, 100))
        for e in frame:
            e.role = "frame"
        view = _poly((40, 40), (60, 40), (60, 60), (40, 60))
        result = topo.heal(_doc(frame + view), max_gap=MAX_GAP).outlines()
        self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 400.0)
        framed = [t for t in result.loose if t.role == "frame"]
        self.assertEqual([(type(t).__name__, len(t.segments)) for t in framed], [("ClosedCurve", 4)])

    def test_cerchi_concentrici_vicini_in_loose_a_ogni_max_gap(self):
        # D161: due cerchi a 0.4 l'uno dall'altro dentro la vista escono
        # entrambi in loose, sotto e sopra il contatto (max_gap 0.5 e 0.2)
        edges = _poly((0, 0), (100, 0), (100, 100), (0, 100)) + [
            _circle((50, 50), 5), _circle((50, 50), 4.6)]
        for gap in (MAX_GAP, 0.2):
            with self.subTest(max_gap=gap):
                result = topo.heal(_doc(edges), max_gap=gap).outlines()
                self.assertEqual(result.clusters[0].inners, [])
                self.assertEqual(sorted(s.radius for t in result.loose for s in t.segments), [4.6, 5])
                self.assertEqual({t.cluster_ref for t in result.loose}, {0})

    def test_niente_di_chiuso_invalido(self):
        result = topo.heal(_doc([_line((0, 0), (5, 0))]), max_gap=MAX_GAP).outlines()
        self.assertFalse(result.is_valid)

    def test_richiede_un_documento(self):
        with self.assertRaises(TypeError):
            topo.heal([_line((0, 0), (1, 0))], max_gap=MAX_GAP).outlines()


class TestRefitTessellations(unittest.TestCase):

    def _tessellated_arc(self, n=40):
        pts = [(10 * math.cos(math.pi * i / (2 * n)), 10 * math.sin(math.pi * i / (2 * n))) for i in range(n + 1)]
        return [_line(pts[i], pts[i + 1]) for i in range(n)]

    def test_catena_corta_diventa_un_arco(self):
        # 40 segmenti da ~0.39mm: sotto max_segment=0.5 → un arco r=10
        out = refit_tessellations(self._tessellated_arc(), max_segment=0.5)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0].segment, ArcSeg)
        self.assertAlmostEqual(out[0].segment.radius, 10.0, places=3)

    def test_estremi_tengono_i_nodi(self):
        chain = self._tessellated_arc()
        out = refit_tessellations(chain, max_segment=0.5)
        self.assertEqual(out[0].start, chain[0].start)
        self.assertEqual(out[0].end, chain[-1].end)

    def test_catena_troppo_corta_non_si_tocca(self):
        chain = self._tessellated_arc(n=5)
        self.assertEqual(refit_tessellations(chain, max_segment=5.0), chain)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestNestedInUnderMotion(unittest.TestCase):
    """G6e, gruppo D, `island.py:148`: `read_outlines` sceglie l'ospite col
    `max` sull'area dell'outer. Un pari merito non c'è: due ospiti che
    contengono lo stesso pezzo sono isole distinte, quindi i loro bordi non si
    toccano e uno contiene l'altro; le aree differiscono almeno di distanza ×
    perimetro, ben oltre il rumore. Prova: tre cornici annidate e un tratto
    dentro la più piccola; a ogni moto il tratto e le due cornici interne
    puntano alla cornice più grande."""

    MOTIONS = [(a, dx, dy) for a in (0.0, 0.8127, math.pi / 2)
               for dx, dy in ((0.0, 0.0), (13.1, -9.3), (2.5e6, -1.5e6))]

    def test_il_piu_esterno_ospita_tutti(self):
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
    """G6e, D193 punto 2, `island.py:146`: l'ospite di un pezzo si chiedeva
    al poligono del suo outer allargato di `tolerance`. Un morso ad arco
    (freccia 0.0099) e dentro il morso un cerchietto di raggio 0.003 a 0.051
    dall'arco vero, soglia 0.05 (`max_gap` 0): due isole a ogni moto, ma la
    corda sporge nel morso fino a 0.0099 e a mezzo passo della griglia
    angolare (D145) il buffer copriva tutto il cerchietto, che finiva
    annidato. Da quando due isole distano più della soglia sulle curve vere
    (D200) un punto solo del pezzo dice se sta dentro, sulle primitive."""

    N = 64
    MOTIONS = [(0.0, 0.0, 0.0), (math.pi / 64, 0.0, 0.0), (math.pi / 128, 0.0, 0.0), (0.7, 0.0, 0.0),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def _segments(self):
        step = 2 * math.pi / self.N
        r = 0.01 * (1 - 1e-8) / (1 - math.cos(step / 2))
        a = math.pi / 4
        p1, p2 = (-r * math.cos(a), -r * math.sin(a)), (r * math.cos(a), -r * math.sin(a))
        return [ArcSeg(center=(0.0, 0.0), radius=r, start_angle=5 * a, end_angle=7 * a, ccw=True),
                LineSeg(start=p2, end=(p2[0], -r - 3)), LineSeg(start=(p2[0], -r - 3), end=(p1[0], -r - 3)),
                LineSeg(start=(p1[0], -r - 3), end=p1),
                CircleSeg(center=(0.0, -r + 0.054), radius=0.003)]

    def test_il_cerchietto_nel_morso_non_e_annidato_a_nessun_moto(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            move, _ = rigid(*motion)
            with self.subTest(motion=motion):
                result = topo.heal(topo.load_segments([move(s) for s in self._segments()]), max_gap=0.0).outlines()
                self.assertEqual(len(result.clusters), 2)

    def test_al_posto_il_buffer_copre_il_cerchietto(self):
        # la prova non è vuota: a mezzo passo il poligono allargato di 0.05 lo contiene
        from shapely import Polygon
        from tests.invariants import rigid
        from topo.core.readings.outline import read_outline
        move, _ = rigid(math.pi / 64, 0.0, 0.0)
        segments = [move(s) for s in self._segments()]
        host = read_outline(topo.load_segments(segments[:4]).edges, 0.05, max_gap=0.0)
        self.assertTrue(to_shapely(host.outer).buffer(0.05).contains(Polygon(segments[4].discretize())))
