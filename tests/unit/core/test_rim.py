# tests/unit/core/test_rim.py

"""
I segmenti di una faccia letti dal suo bordo (`face_segments`, D106). Le
facce per giro di `island()` non ci sono più: island non costruisce inner
(D161).
"""

import math
import unittest

from shapely.geometry import Polygon, box

from topo.core.primitives.polygon_builder import build_polygon
from topo.core.primitives.segments import ArcSeg, LineSeg, segment_endpoints
from topo.core.topology.edge import Edge
from topo.core.topology.rim import face_segments

BAND = 0.02


def _line(p1, p2):
    return Edge(role="unknown", start=p1, end=p2, segment=LineSeg(start=p1, end=p2))


class TestFaceSegments(unittest.TestCase):

    def test_edge_sul_bordo_solo_in_parte_da_la_sua_parte(self):
        # la base e il lato destro sporgono oltre il quadrato: incroci che
        # la rete non ha tagliato
        edges = [_line((-5, 0), (15, 0)), _line((10, -3), (10, 10)),
                 _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, styles = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)
        self.assertEqual(len(styles), 4)
        rebuilt = build_polygon(segments)
        self.assertLess(rebuilt.symmetric_difference(box(0, 0, 10, 10)).area, 1e-9)
        ends = {tuple(round(c, 9) for c in p) for s in segments for p in segment_endpoints(s)}
        self.assertEqual(ends, {(0, 0), (10, 0), (10, 10), (0, 10)})

    def test_doppione_sovrapposto_non_spezzetta(self):
        edges = [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)),
                 _line((10, 10), (0, 10)), _line((10, 10), (0, 10)), _line((0, 10), (0, 0))]
        segments, _ = face_segments(edges, box(0, 0, 10, 10), BAND)
        self.assertEqual(len(segments), 4)

    def test_arco_tangente_a_una_retta_resta_un_arco(self):
        # mezzo disco: diametro come retta, semicerchio come arco
        arc = ArcSeg(center=(0, 0), radius=5, start_angle=0, end_angle=math.pi, ccw=True)
        edges = [_line((-5, 0), (5, 0)),
                 Edge(role="unknown", start=(5, 0), end=(-5, 0), segment=arc)]
        polygon = Polygon(arc.discretize(0.01))
        segments, _ = face_segments(edges, polygon, BAND)
        self.assertEqual(sorted(type(s).__name__ for s in segments), ["ArcSeg", "LineSeg"])


if __name__ == "__main__":
    unittest.main()
