# tests/unit/core/test_islands.py

import math
import unittest
from topo.core.readings.islands import spatial_islands
from topo.core.topology.edge import Edge
from topo.core.primitives.segments import LineSeg, CircleSeg, segment_endpoints
from topo.core.geometry.measure import round_point
from topo.core.topology.noding import edge_geometry


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


def _square(x, y, size=10):
    pts = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    return [_line(pts[i], pts[(i + 1) % 4]) for i in range(4)]


class TestSpatialIslands(unittest.TestCase):

    def test_due_quadrati_lontani_due_isole(self):
        islands = spatial_islands(_square(0, 0) + _square(100, 0), gap_tolerance=5)
        self.assertEqual(len(islands), 2)
        self.assertEqual([len(i.edges) for i in islands], [4, 4])

    def test_gap_sotto_tolleranza_unisce(self):
        # 3mm di distanza, tolleranza 5: stessa isola anche senza toccarsi
        islands = spatial_islands(_square(0, 0) + _square(13, 0), gap_tolerance=5)
        self.assertEqual(len(islands), 1)
        self.assertEqual(islands[0].bbox, (0.0, 0.0, 23.0, 10.0))

    def test_catena_transitiva(self):
        # A vicino a B, B vicino a C, A lontano da C: una sola isola
        edges = _square(0, 0) + _square(12, 0) + _square(24, 0)
        self.assertEqual(len(spatial_islands(edges, gap_tolerance=3)), 1)

    def test_vicino_in_x_lontano_in_y(self):
        islands = spatial_islands(_square(0, 0) + _square(0, 50), gap_tolerance=5)
        self.assertEqual(len(islands), 2)

    def test_foro_vicino_al_lato_stessa_isola(self):
        hole = Edge(role="unknown", start=(3, 5), end=(3, 5),
                    segment=CircleSeg(center=(2, 5), radius=1))
        islands = spatial_islands(_square(0, 0) + [hole], gap_tolerance=1.5)
        self.assertEqual(len(islands), 1)

    def test_foro_lontano_dai_lati_isola_a_se(self):
        # solo vicinanza: che il foro stia DENTRO lo dice il contorno esterno, dopo
        hole = Edge(role="unknown", start=(52, 50), end=(52, 50),
                    segment=CircleSeg(center=(50, 50), radius=2))
        islands = spatial_islands(_square(0, 0, 100) + [hole], gap_tolerance=5)
        self.assertEqual(len(islands), 2)

    def test_diagonale_lunga_non_unisce_per_bbox(self):
        # la bbox della diagonale copre il quadrato, la distanza vera no
        diag = _line((0, 0), (100, 100))
        islands = spatial_islands([diag] + _square(70, 5), gap_tolerance=2)
        self.assertEqual(len(islands), 2)

    def test_ordinate_per_area(self):
        islands = spatial_islands(_square(0, 0, 5) + _square(100, 0, 20), gap_tolerance=1)
        self.assertEqual(islands[0].width, 20)

    def test_lista_vuota(self):
        self.assertEqual(spatial_islands([], gap_tolerance=1), [])


class TestGapOnTrueCurvesUnderMotion(unittest.TestCase):
    """G6e, D193 punto 2, `islands.py:66`: `dwithin` a `gap_tolerance` sulle
    discretizzazioni. Un cerchio con freccia 0.0099 e un quadratino a 0.496
    dal cerchio vero, soglia 0.5: su un vertice la distanza misurata è
    quella vera, a metà corda ~0.01 di più; mezzo passo della griglia
    angolare (D145) la portava oltre 0.5 e l'isola diventava due."""

    N = 64
    MOTIONS = [(0.0, 0.0, 0.0), (math.pi / 64, 0.0, 0.0), (math.pi / 128, 0.0, 0.0), (0.7, 0.0, 0.0),
               (math.pi / 2, 0.0, 0.0), (0.0, 2.5e6, -1.5e6)]

    def _pieces(self, distance, move):
        step = 2 * math.pi / self.N
        r = 0.01 * (1 - 1e-8) / (1 - math.cos(step / 2))
        y = r + distance
        pts = [(-0.2, y), (0.2, y), (0.2, y + 0.4), (-0.2, y + 0.4)]
        segments = [CircleSeg(center=(0.0, 0.0), radius=r)] + [
            LineSeg(start=pts[i], end=pts[(i + 1) % 4]) for i in range(4)]
        edges = []
        for seg in map(move, segments):
            start, end = segment_endpoints(seg)
            edges.append(Edge(role="unknown", start=round_point(start), end=round_point(end), segment=seg))
        return edges

    def test_la_distanza_vera_decide_a_ogni_moto(self):
        from tests.invariants import rigid
        for distance, expected in ((0.496, 1), (0.504, 2)):
            for motion in self.MOTIONS:
                move, _ = rigid(*motion)
                with self.subTest(distance=distance, motion=motion):
                    self.assertEqual(len(spatial_islands(self._pieces(distance, move), gap_tolerance=0.5)), expected)

    def test_al_posto_la_corda_sta_oltre_la_soglia(self):
        # la prova non è vuota: a mezzo passo la discretizzazione misura più di 0.5
        from tests.invariants import rigid
        move, _ = rigid(math.pi / 64, 0.0, 0.0)
        edges = self._pieces(0.496, move)
        geoms = [edge_geometry(e) for e in edges]
        self.assertGreater(min(geoms[0].distance(g) for g in geoms[1:]), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
