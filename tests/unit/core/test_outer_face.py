# tests/unit/core/test_outer_face.py

import math
import unittest
from shapely.ops import polygonize, unary_union
from topo.core.topology.outer_face import _network, outer_face
from topo.core.topology.noding import split_at_crossings
from topo.core.topology.edge import Edge
from topo.core.geometry.measure import round_point
from topo.core.primitives.segments import BSplineSeg, LineSeg, CircleSeg, segment_endpoints
from topo import to_shapely


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _poly(*pts):
    return [_line(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _face(edges):
    return outer_face(split_at_crossings(edges, tolerance=0.05).pieces, epsilon=0.01)


class TestOuterFace(unittest.TestCase):

    def test_quadrato_con_diagonale(self):
        # la diagonale divide il quadrato in due facce: il contorno esterno è il quadrato
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((0, 0), (10, 10))]
        face = _face(edges)
        self.assertAlmostEqual(to_shapely(face).area, 100.0)
        self.assertEqual(len(face.edges), 4)

    def test_asse_che_sporge_e_una_sporgenza(self):
        # un asse che attraversa il quadrato ed esce dai due lati
        edges = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((-3, 5), (13, 5))]
        face = _face(edges)
        self.assertAlmostEqual(to_shapely(face).area, 100.0)
        self.assertEqual(len(face.spurs), 2)

    def test_l_con_rientro(self):
        edges = _poly((0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10))
        self.assertAlmostEqual(to_shapely(_face(edges)).area, 64.0)

    def test_punto_piu_a_sinistra_a_meta_di_un_arco(self):
        # vista stretta dentro un cerchio che la attraversa: il nodo più a
        # sinistra è dentro il cerchio, il punto più a sinistra è sul cerchio
        view = _poly((-1, -3), (1, -3), (1, 20), (-1, 20))
        circle = Edge(role="unknown", start=(8, 0), end=(8, 0),
                      segment=CircleSeg(center=(0, 0), radius=8))
        face = _face(view + [circle])
        self.assertGreater(to_shapely(face).area, 3.14 * 64)
        # la parte di vista che esce sopra il cerchio è contorno
        self.assertGreater(to_shapely(face).bounds[3], 19.9)

    def test_nessun_giro(self):
        self.assertIsNone(_face([_line((0, 0), (5, 0))]))


class TestContattiPerDistanza(unittest.TestCase):
    """Un quadrato col lato di base fatto da una spline e i lati verticali che
    finiscono 0.004 sopra di essa: il noding non spezza la spline, la faccia
    si chiude solo nell'unione delle facce (D100). Il contatto vale per
    distanza, dovunque stia il disegno: una griglia fissa agli assi lo
    cuciva solo se i due punti cadevano nella stessa cella (G6c)."""

    def _square(self, move):
        base = BSplineSeg(2, [(-5.0, 0.0), (5.0, 0.0), (15.0, 0.0)], [0, 0, 0, 1, 1, 1])
        sides = [LineSeg(start=(0.0, 0.004), end=(0.0, 10.0)), LineSeg(start=(0.0, 10.0), end=(10.0, 10.0)),
                 LineSeg(start=(10.0, 10.0), end=(10.0, 0.004))]
        edges = []
        for seg in [move(base)] + [move(s) for s in sides]:
            start, end = segment_endpoints(seg)
            edges.append(Edge(role="unknown", start=round_point(start), end=round_point(end), segment=seg))
        return _face(edges)

    def test_spostato_di_frazioni_di_cella(self):
        for dy in (0.0, 0.002, 0.004, 0.006, 0.008):
            with self.subTest(dy=dy):
                face = self._square(lambda s: s.translated(0.0, dy))
                self.assertAlmostEqual(to_shapely(face).area, 100.0, delta=0.1)

    def test_ruotato(self):
        for angle in (0.3, 0.7, 1.1, 2.0):
            with self.subTest(angle=angle):
                face = self._square(lambda s: s.rotated(angle))
                self.assertAlmostEqual(to_shapely(face).area, 100.0, delta=0.1)

    def test_retta_che_sfiora_un_cerchio(self):
        # una V col cerchio inscritto, i lati lo mancano di 0.004: la punta
        # fra la V e il cerchio è una faccia chiusa della rete. Si guarda la
        # rete e non il contorno: qui nessun edge sta per intero sul bordo
        # dell'unione e il ripiego D100 non ne fa un giro (TODO, 1.x)
        r, d = 1.0, 1.0 / math.sin(math.radians(20)) + 0.004 / math.sin(math.radians(20))
        apex = (d, 0.0)
        ends = [(d - 6 * math.cos(math.radians(a)), -6 * math.sin(math.radians(a))) for a in (20, -20)]
        ends = [round_point(p) for p in ends]
        circle = Edge(role="unknown", start=(r, 0.0), end=(r, 0.0), segment=CircleSeg(center=(0.0, 0.0), radius=r))
        edges = [_line(ends[0], round_point(apex)), _line(round_point(apex), ends[1]), circle]
        for angle in (0.0, 0.7):
            with self.subTest(angle=angle):
                moved = []
                for e in edges:
                    seg = e.segment.rotated(angle)
                    start, end = segment_endpoints(seg)
                    moved.append(Edge(role="unknown", start=round_point(start), end=round_point(end), segment=seg))
                pieces = split_at_crossings(moved, tolerance=0.05).pieces
                area = unary_union(list(polygonize(_network(pieces, 0.01)))).area
                self.assertGreater(area, math.pi * r * r + 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestOverlapFromANodeUnderMotion(unittest.TestCase):
    """G6e, `outer_face.py:218`: una svolta ~0 (un edge che riparte lungo
    quello da cui si arriva) la deciderebbe il segno del rumore, e arriva solo
    con due edge sovrapposti da un nodo. Qui ci sono: le due letture danno la
    stessa risposta al posto, ruotate e lontano. Misurato il 1 novembre con un
    tracciamento: la sovrapposizione è tolta prima delle facce, e la 218
    scatta solo sull'edge d'arrivo (36 volte su 36), mai su un altro."""

    def test_heal_e_island_non_dipendono_dal_moto(self):
        import topo
        from tests.invariants import rigid
        from topo.core.primitives.segments import LineSeg
        # triangolo con il lato di base doppio dal nodo (0, 0): 10 mm e 20 mm sovrapposti
        segs = [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)), LineSeg(start=(0.0, 0.0), end=(20.0, 0.0)),
                LineSeg(start=(20.0, 0.0), end=(10.0, 10.0)), LineSeg(start=(10.0, 10.0), end=(0.0, 0.0)),
                LineSeg(start=(10.0, 0.0), end=(10.0, 10.0))]
        readings = {"heal": lambda d: topo.heal(d, tolerance=0.05),
                    "island": lambda d: topo.island(d, tolerance=0.05, max_gap=0.5)}

        def reading(read, motion):
            segment, _ = rigid(*motion)
            r = read(topo.load_segments([segment(s) for s in segs]))
            return r.is_valid, len(r.clusters), [len(c.inners) for c in r.clusters], len(r.loose), \
                sum(c.outer.area for c in r.clusters)

        for name, read in readings.items():
            at_rest = reading(read, (0.0, 0.0, 0.0))
            self.assertEqual(at_rest[:4], (True, 1, [0], 1), name)
            for motion in ((0.031, 0.0, 0.0), (0.7, 0.0, 0.0), (0.7, 3e6, -2.5e6), (2.294, 3e6, -2.5e6)):
                with self.subTest(reading=name, motion=motion):
                    moved = reading(read, motion)
                    self.assertEqual(moved[:4], at_rest[:4])
                    self.assertAlmostEqual(moved[4], at_rest[4], delta=1e-2)   # la griglia dei nodi, lontano


class TestFirstStepUnderMotion(unittest.TestCase):
    """G6e, gruppo C, `_first_step`: su un lato sinistro verticale i punti più
    a sinistra sono pari merito e il primo lo sceglie l'ultimo bit; sui
    disegni tracciati succede 938 volte su 2964 (`probe_first_step.py`).
    `going_down` invece non arriva al rumore (|dy| minimo 0.004 mm, 461
    rami interni). Prova: il giro parte da nodi diversi secondo il moto
    (controllato) e i passaggi per pezzo sono gli stessi — chi li consuma
    (`outer_face`, `non_contour_edges`) conta, non guarda da dove si parte.
    Non prova un pari merito fra punti di due componenti diversi."""

    # rotazioni di 1e-12: il lato sinistro pende di qua o di là, entro il rumore
    MOTIONS = [(1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0), (1e-12, 0.3, -0.2), (-1e-12, 0.3, -0.2)]

    def test_partenze_diverse_stessi_passaggi(self):
        from tests.invariants import rigid
        from topo.core.topology.graph import build_node_graph
        from topo.core.topology.outer_face import _first_step, outer_face_passes
        # quadrato con una corda da (0, 5) e una sporgenza oltre il lato destro
        base = _poly((0, 0), (10, 0), (10, 10), (0, 10)) + [_line((0, 5), (13, 5))]
        starts, readings = set(), []
        for motion in self.MOTIONS:
            move_seg, move_pt = rigid(*motion)
            edges = [Edge(role="unknown", start=move_pt(e.start), end=move_pt(e.end),
                          segment=move_seg(e.segment)) for e in base]
            pieces = split_at_crossings(edges, tolerance=0.05).pieces
            graph = build_node_graph(pieces, sliver=0.01)
            (component,) = graph.connected_components()
            starts.add(tuple(round(c - d, 6) for c, d in zip(_first_step(graph, component)[1], motion[1:])))
            passes = outer_face_passes(graph, component, len(pieces))
            readings.append(sorted(
                (tuple(round((a + b) / 2 - d, 6) for a, b, d in zip(p.start, p.end, motion[1:])),
                 passes.get(id(p), 0)) for p in pieces))
        self.assertGreater(len(starts), 1)            # il pari merito c'è davvero
        for r in readings[1:]:
            self.assertEqual(r, readings[0])
        self.assertIn(2, [n for _, n in readings[0]])  # la sporgenza, due volte
        self.assertIn(0, [n for _, n in readings[0]])  # la corda, mai


class TestUnionGridUnderMotion(unittest.TestCase):
    """G6e, gruppo B, `outer_face.py:41` (`UNION_GRID`): la griglia della rete
    del ripiego (D100, D179). Sui 31 disegni di `island()` lavora solo sui
    doppioni a 1e-12 (qui i due cerchi di un disegno ancorato): con la griglia
    coincidono, senza si incrociano dove dice l'ultimo bit. Prova: la griglia
    cambia davvero la rete (valore controllato al posto), e la lettura è la
    stessa a ogni moto e senza griglia. Non prova la finestra di 1e-6 fra due
    curve distinte: lì decide prima `_network` coi capi sulle tuple (voce a sé
    dell'inventario G6e)."""

    CIRCLES = [CircleSeg(center=(67.6769804197, 260.3946312001), radius=0.5325),
               CircleSeg(center=(67.67698041971678, 260.3946312001228), radius=0.5325000000015537)]
    MOTIONS = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.13, 3.1, -7.9), (2.4, -0.37, 0.61),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def test_la_griglia_lavora_sui_doppioni(self):
        import shapely
        from topo.core.topology.graph import build_node_graph
        from topo.core.topology.outer_face import UNION_GRID, _on_nodes
        edges = [Edge(role="unknown", start=round_point(segment_endpoints(s)[0]),
                      end=round_point(segment_endpoints(s)[1]), segment=s)
                 for s in self.CIRCLES]
        lines = _on_nodes(edges, build_node_graph(edges, sliver=0.01))
        on_grid = len(shapely.unary_union(lines, grid_size=UNION_GRID).geoms)
        exact = len(shapely.unary_union(lines).geoms)
        self.assertEqual(on_grid, 64)   # i due poligoni coincidono vertice per vertice
        self.assertLess(exact, 10)      # senza griglia: pochi incroci all'ultimo bit

    def test_la_lettura_non_dipende_dalla_griglia_ne_dal_moto(self):
        from unittest import mock
        import topo
        from topo.core.topology import outer_face as module
        from tests.invariants import rigid
        areas = set()
        for motion in self.MOTIONS:
            segment, _ = rigid(*motion)
            for grid in (module.UNION_GRID, None):
                with self.subTest(motion=motion, grid=grid), mock.patch.object(module, "UNION_GRID", grid):
                    result = topo.island(topo.load_segments([segment(s) for s in self.CIRCLES]), max_gap=0.0)
                    self.assertEqual(len(result.clusters), 1)
                    self.assertEqual(len(result.loose), 1)
                    areas.add(round(to_shapely(result.clusters[0].outer).area, 9))
        self.assertEqual(len(areas), 1)   # lo stesso cerchio in ogni moto, con e senza griglia
