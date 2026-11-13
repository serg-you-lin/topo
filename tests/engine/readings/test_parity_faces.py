# tests/engine/readings/test_parity_faces.py

"""
La lettura per parità, `topo.experimental.parity_faces` (D250): cosa è
garantito (nodi tutti pari: una lettura sola), cosa è scelto (nodi dispari:
il minimo), e il limite dichiarato (nei pareggi dipende dal riferimento).
"""

import unittest

import topo
import topo_dxf
from topo import to_shapely
from topo.core.primitives import LineSeg

from tests.invariants import MOTIONS, message_problems, moved, shape_differences
from tests.paths import DATA

TOL = 0.01


def _lines(*points, closed: bool = False) -> list:
    pts = list(points) + ([points[0]] if closed else [])
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]


def _read(segments: list):
    return topo.experimental.parity_faces(topo.heal(topo.load_segments(segments), tolerance=TOL))


class TestEvenNodes(unittest.TestCase):
    """Ogni nodo pari: ogni linea è contorno, e la lettura è una sola."""

    def test_rettangolo_che_tocca_il_bordo_e_un_inner(self):
        # un rettangolo interno con un lato sul bordo del pezzo, toccato in un punto
        result = _read(_lines((0, 0), (100, 0), (100, 60), (0, 60), closed=True)
                       + _lines((50, 0), (80, 20), (50, 40), (20, 20), closed=True))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.reading, "parity")
        self.assertEqual([len(c.inners) for c in result.clusters], [1])
        self.assertEqual(result.loose, [])
        self.assertEqual(message_problems(result), [])


class TestOddNodes(unittest.TestCase):
    """Nodi dispari: via capi liberi e ponti, poi il meno di sagoma, poi il più corto."""

    def test_diagonali_via_il_quadrato_resta(self):
        # gli 8 angoli hanno grado 3; i lati del rettangolo sono sagoma:
        # l'insieme più corto che rende pari ogni nodo sono le 4 diagonali
        result = _read(_lines((0, 0), (260, 0), (260, 150), (0, 150), closed=True)
                       + _lines((95, 47), (165, 47), (165, 103), (95, 103), closed=True)
                       + _lines((0, 0), (95, 47)) + _lines((260, 0), (165, 47))
                       + _lines((0, 150), (95, 103)) + _lines((260, 150), (165, 103)))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].area, 260 * 150 - 70 * 56)
        self.assertEqual(len(result.loose), 4)
        self.assertEqual(message_problems(result), [])

    def test_lati_che_si_incrociano_li_taglia(self):
        # un lato sfora l'angolo: l'incrocio si taglia e la coda è un capo libero
        result = _read([LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, 50.1)),
                        LineSeg((100.1, 50), (0, 50)), LineSeg((0, 50), (0, 0))])
        self.assertTrue(result.is_valid)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 100 * 50)
        self.assertIn("crossing", [w.code for w in result.warnings])

    def test_ruolo_non_strutturale_non_entra(self):
        # una linea con un ruolo deciso non strutturale non conta nei gradi
        doc = topo.load_segments(_lines((0, 0), (100, 0), (100, 60), (0, 60), closed=True))
        doc.edges.append(doc.edges[0].__class__(role="engrave", start=(50, 0), end=(50, 60),
                                                segment=LineSeg((50, 0), (50, 60))))
        result = topo.experimental.parity_faces(topo.heal(doc, tolerance=TOL))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].area, 100 * 60)


class TestDeclaredLimit(unittest.TestCase):
    """Il limite dichiarato: dove due insiemi da togliere hanno la stessa
    lunghezza, quale si toglie dipende dalle coordinate. L'asola con la
    croce di Multifeature, specchiata, si legge con gli altri due spicchi.
    Se un giorno la lettura diventa invariante, questo test cade: si cambia
    apposta, con la decisione che lo dice."""

    def test_multifeature_specchiato_cambia_i_fori(self):
        doc = topo_dxf.load_dxf(str(DATA / "Multifeature.dxf"))
        name, move, back, _ = [m for m in MOTIONS if m[0] == "mirror"][0]
        inners = [to_shapely(i) for c in topo.experimental.parity_faces(topo.heal(doc)).clusters
                  for i in c.inners]
        again = [back(to_shapely(i)) for c in topo.experimental.parity_faces(topo.heal(moved(doc, move))).clusters
                 for i in c.inners]
        self.assertNotEqual(shape_differences(inners, again, 2 * TOL), [])


if __name__ == "__main__":
    unittest.main()
