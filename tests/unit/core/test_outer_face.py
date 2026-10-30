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
