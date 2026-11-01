# tests/unit/core/test_rim.py

"""
I segmenti di una faccia letti dal suo bordo (`face_segments`, D106). Le
facce per giro di `island()` non ci sono più: island non costruisce inner
(D161).
"""

import math
import unittest

from shapely.geometry import Point, Polygon, box

from topo.core.primitives.polygon_builder import build_polygon
from topo.core.primitives.segments import ArcSeg, LineSeg, segment_endpoints
from topo.core.topology.edge import Edge
from topo.core.topology import rim
from topo.core.topology.rim import face_segments, off_rim

BAND = 0.02


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


class TestFaceSegments(unittest.TestCase):

    def test_edge_sul_bordo_solo_in_parte_da_la_sua_parte(self):
        # la base e il lato destro sporgono oltre il quadrato: incroci che
        # la rete non ha tagliato
        edges = [_line((-5, 0), (15, 0)), _line((10, -3), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, styles, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)
        self.assertEqual(len(styles), 4)
        rebuilt = build_polygon(segments)
        self.assertLess(rebuilt.symmetric_difference(box(0, 0, 10, 10)).area, 1e-9)
        ends = {tuple(round(c, 9) for c in p) for s in segments for p in segment_endpoints(s)}
        self.assertEqual(ends, {(0, 0), (10, 0), (10, 10), (0, 10)})

    def test_il_resto_di_un_edge_solo_in_parte_sul_bordo(self):
        # G6b: la base sporge di 5 a sinistra e a destra, il lato destro di 3
        # in basso; esce solo la sporgenza, mai l'edge intero
        edges = [_line((-5, 0), (15, 0)), _line((10, -3), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        square = box(0, 0, 10, 10)
        _, _, used = face_segments(edges, square, BAND)
        rest = off_rim(edges[0], used[0], square.exterior, BAND)
        ends = sorted(tuple(tuple(round(c, 9) for c in p) for p in segment_endpoints(e.segment)) for e in rest)
        self.assertEqual(ends, [((-5, 0), (0, 0)), ((10, 0), (15, 0))])
        self.assertEqual(rest[0].start, (-5, 0))   # il capo originale tiene il suo nodo
        self.assertEqual(off_rim(edges[2], used[2], square.exterior, BAND), [])

    def test_doppione_sovrapposto_non_spezzetta(self):
        edges = [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)),
                 _line((10, 10), (0, 10)), _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, _, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)

    def test_arco_tangente_a_una_retta_resta_un_arco(self):
        # mezzo disco: diametro come retta, semicerchio come arco
        arc = ArcSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi, ccw=True)
        edges = [_line((-5, 0), (5, 0)),
                 Edge(role="unknown", start=(5, 0), end=(-5, 0), segment=arc)]
        polygon = Polygon(arc.discretize(tolerance=0.01))
        segments, _, _ = face_segments(edges, polygon, BAND)
        self.assertEqual(sorted(type(s).__name__ for s in segments), ["ArcSeg", "LineSeg"])


class TestOffRimCutsUnderMotion(unittest.TestCase):
    """G6e, gruppo B, `rim.py:80`: i tagli di `off_rim` erano le ascisse
    arrotondate a 1e-9. Due capi presi a 1e-10 l'uno dall'altro cadevano in
    una cella o in due secondo il moto, e il capo del resto si spostava fino a
    5e-10 dal nodo del contorno (qui l'edge parte a -5.00000000045: il taglio
    cade a 4.5e-10 da un multiplo di 1e-9). Prova: al posto e ai moti esce la
    sola sporgenza, con il capo interno sul capo preso (entro il rumore del moto).
    Non prova la riga dentro `island()`: sui disegni tracciati il ripiego
    `_faces_union_loop` non arriva mai a `off_rim`."""

    MOTIONS = [(0.0, 0.0, 0.0), (0.7, 0.0, 0.0), (0.13, 3.1, -7.9), (2.4, -0.37, 0.61)]

    def test_due_capi_quasi_uguali_un_resto_solo(self):
        from tests.invariants import rigid
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                move_seg, move_pt = rigid(*motion)
                edge = _line((-5.00000000045, 0.0), (15.0, 0.0))
                edge = Edge(role="unknown", start=move_pt(edge.start), end=move_pt(edge.end),
                            segment=move_seg(edge.segment))
                square = Polygon([move_pt(p) for p in [(0, 0), (10, 0), (10, 10), (0, 10)]])
                corner = move_pt((0.0, 0.0))
                twin = move_pt((1e-10, 0.0))
                taken = [(corner, move_pt((10.0, 0.0))), (twin, corner)]
                rest = off_rim(edge, taken, square.exterior, BAND)
                left = [e for e in rest if e.start == edge.start]
                self.assertEqual(len(rest), 2)
                self.assertEqual(len(left), 1)
                # il capo interno è sul nodo del contorno, non su una cella
                inner = segment_endpoints(left[0].segment)[1]
                self.assertLess(math.dist(inner, corner), 1e-12)


class TestSenseOfAPerpendicularSpur(unittest.TestCase):
    """G6e, gruppo C, `rim.py:152`: il verso di un edge rispetto a un lato è il
    segno di un prodotto scalare, `>= 0`. Una sporgenza perpendicolare che
    tocca il punto medio di un lato ha prodotto 0 a riposo e rumore (±4e-15)
    sotto moto: il suo verso cambia col moto. Prova: il verso cambia davvero
    (la riga è raggiunta col valore nullo) e l'uscita di `face_segments` no,
    perché il lato lo tiene il suo edge. Non prova la riga dentro `island()`:
    sui disegni tracciati `face_segments` non è mai chiamata. Non prova il caso
    in cui la sporgenza vince il lato (sporgenza prima nell'elenco): quella è
    la parità di `_rim_runs`, riga D dell'inventario."""

    MOTIONS = [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (-1e-12, 0.0, 0.0),
               (0.7, 3.1, -2.2), (math.pi / 2, 0.0, 0.0)]
    SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]

    def test_il_verso_cambia_l_uscita_no(self):
        from tests.invariants import rigid
        senses, outputs = set(), set()
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                move_seg, move_pt = rigid(*motion)
                edges = [_line(self.SQUARE[i], self.SQUARE[(i + 1) % 4]) for i in range(4)]
                edges.append(_line((5, 0), (5, -3)))
                edges = [Edge(role="unknown", start=move_pt(e.start), end=move_pt(e.end),
                              segment=move_seg(e.segment)) for e in edges]
                polygon = Polygon([move_pt(p) for p in self.SQUARE])
                # il verso della sporgenza sul lato di sotto, come lo calcola la riga
                p, q = move_pt((0, 0)), move_pt((10, 0))
                mid = Point((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                senses.add(rim._sense(rim.edge_geometry(edges[4]), mid, p, q, BAND))
                segments, _, used = face_segments(edges, polygon, BAND)
                self.assertEqual(sorted(used), [0, 1, 2, 3])
                outputs.add(tuple(sorted(round(math.dist(*segment_endpoints(s)), 9)
                                         for s in segments)))
        self.assertEqual(senses, {1, -1})
        self.assertEqual(outputs, {(10.0, 10.0, 10.0, 10.0)})


if __name__ == "__main__":
    unittest.main()
