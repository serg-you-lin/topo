# tests/unit/core/test_non_contour_choices.py

"""
Le scelte del criterio non-contorno di heal(), una classe per scelta (MAP.md
D131, D132). Ogni test è il disegno minimo del caso limite e dice cosa topo
sceglie per default: se un default cambia, cambia qui, apposta e per una
decisione scritta, mai per far passare un altro test.

  A  catena interna (0 passaggi)      → corda: il pezzo resta pieno
  B  ponte (2 passaggi)               → due pezzi, con un warning
  C  sul bordo per meno di metà       → corda
  D  lati che si accavallano          → giudicati sulla rete piana, e detti in un warning
  E  catena chiusa su un nodo solo    → mai candidata: oggi resta un foro (aperto in TODO)
"""

import unittest

import topo
from topo.core.primitives import LineSeg
from topo.core.topology.noding import interior_crossings

TOL = 0.01


def _lines(*points, closed: bool = False) -> list:
    pts = list(points) + ([points[0]] if closed else [])
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]


def _heal(segments: list):
    return topo.heal(topo.load_segments(segments), tolerance=TOL)


class TestA_InteriorChainIsChord(unittest.TestCase):
    """Rettangolo, quadrato interno, 4 diagonali angolo-angolo: lo stesso
    grafo di un pannello con le crocette di irrigidimento e di un foro tenuto
    da 4 linee. Senza altre informazioni il pezzo è pieno."""

    def test_pannello_pieno_otto_linee_nel_trash(self):
        result = _heal(_lines((0, 0), (260, 0), (260, 150), (0, 150), closed=True)
                       + _lines((95, 47), (165, 47), (165, 103), (95, 103), closed=True)
                       + _lines((0, 0), (95, 47)) + _lines((260, 0), (165, 47))
                       + _lines((0, 150), (95, 103)) + _lines((260, 150), (165, 103)))
        self.assertEqual(result.cluster_count, 1)
        self.assertEqual(len(result.clusters[0].inners), 0)
        self.assertAlmostEqual(result.clusters[0].outer.polygon.area, 260 * 150)
        self.assertEqual(len(result.loose), 8)


class TestB_BridgeSplitsParts(unittest.TestCase):
    """Due rettangoli uniti da una linea: il bordo esterno la percorre andata
    e ritorno. Due pezzi, e heal() lo dice."""

    def test_due_pezzi_e_warning(self):
        result = _heal(_lines((0, 0), (110, 0), (110, 50), (110, 100), (0, 100), closed=True)
                       + _lines((166, 0), (276, 0), (276, 100), (166, 100), (166, 50), closed=True)
                       + _lines((110, 50), (166, 50)))
        self.assertEqual(result.cluster_count, 2)
        self.assertEqual(len(result.loose), 1)
        self.assertTrue(any("uniscono due forme" in w for w in result.warnings), result.warnings)


class TestC_GrazedChordIsChord(unittest.TestCase):
    """Una corda a y=49 attraversa una tacca a V profonda 1,5 mm nel lato
    alto: per 1,33 mm su 100 confina con l'esterno. Meno di metà: corda, e la
    tacca resta nel contorno."""

    def test_corda_nel_trash_tacca_nel_contorno(self):
        outline = _lines((0, 0), (100, 0), (100, 49), (100, 50), (51, 50), (50, 48.5), (49, 50),
                         (0, 50), (0, 49), closed=True)
        result = _heal(outline + _lines((0, 49), (100, 49)))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].outer.polygon.area, 100 * 50 - 1.5)
        self.assertEqual(len(result.loose), 1)


class TestD_CrossingSidesAreReported(unittest.TestCase):
    """Una tacca coi fianchi accavallati: il fianco destro torna a (27, 0.5),
    a sinistra di dove parte il sinistro, e il lato che segue incrocia il
    fianco sinistro poco sopra il fondo. heal() non ripara: lo dice, con il
    punto."""

    NOTCH = ((0, 0), (28, 0), (30, 20), (27, 0.5), (60, 0), (60, 40), (30, 40), (0, 40))

    def test_warning_con_il_punto(self):
        result = _heal(_lines(*self.NOTCH, closed=True))
        crossing = [w for w in result.warnings if "incroci fra lati di contorno" in w]
        self.assertEqual(len(crossing), 1, result.warnings)
        self.assertIn("(28.05, 0.48)", crossing[0])

    def test_incrocio_vero_trovato(self):
        doc = topo.load_segments(_lines(*self.NOTCH, closed=True))
        points = interior_crossings(doc.edges, TOL)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0][0], 28.048, places=2)
        self.assertAlmostEqual(points[0][1], 0.484, places=2)

    def test_contatto_a_t_non_e_un_incrocio(self):
        # il capo di una corda a metà del lato alto: un contatto, non un
        # accavallamento
        doc = topo.load_segments(_lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True)
                                 + _lines((0, 0), (20, 20)))
        self.assertEqual(interior_crossings(doc.edges, TOL), [])

    def test_disegno_pulito_nessun_warning(self):
        result = _heal(_lines((0, 0), (40, 0), (40, 20), (0, 20), closed=True))
        self.assertFalse(any("incroci" in w for w in result.warnings), result.warnings)


class TestE_ClosedChainNeverCandidate(unittest.TestCase):
    """Un foro triangolare con un vertice in comune col contorno esterno: la
    sua catena parte e torna allo stesso nodo, quindi non è mai una corda.
    Oggi è un foro; se debba andare nel trash è aperto in TODO (D132)."""

    def test_oggi_resta_un_foro(self):
        result = _heal(_lines((0, 0), (260, 0), (260, 120), (0, 120), closed=True)
                       + _lines((0, 0), (90, 40), (50, 80), closed=True))
        self.assertEqual(result.cluster_count, 1)
        self.assertEqual(len(result.clusters[0].inners), 1)
        self.assertEqual(len(result.loose), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
