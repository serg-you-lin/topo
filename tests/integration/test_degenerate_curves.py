"""
tests/integration/test_degenerate_curves.py
-------------------------------------------
D154: una curva di misura nulla (ARC o CIRCLE di raggio 0, una corda nulla
con bulge in una polilinea) è un punto, non una curva. La primitiva la
rifiuta; il caricamento va avanti e la segnala in `doc.warnings`, invece di
fermarsi su tutto il disegno (CIRCLE) o crashare a valle in `discretize`
(ARC). ezdxf qui serve solo a scrivere l'entità degenere che il file porta:
le API di topo non la costruiscono, ed è proprio il punto.
"""

import math
import unittest

import ezdxf

import topo
import topo_dxf
from topo.primitives import ArcSeg, EllipseSeg


class TestDegeneratePrimitives(unittest.TestCase):

    def test_001_arco_di_raggio_0_rifiutato(self):
        with self.assertRaises(ValueError):
            ArcSeg((1.0, 2.0), 0.0, 0.0, 1.0)

    def test_002_corda_nulla_rifiutata(self):
        # numpy divide 0/0 senza errore: prima ne usciva un arco NaN di raggio 0
        import numpy as np
        p = (np.float64(2.0), np.float64(2.0))
        with self.assertRaises(ValueError):
            ArcSeg.from_chord(p, p, 0.5)

    def test_003_ellisse_degenere_rifiutata(self):
        with self.assertRaises(ValueError):
            EllipseSeg((0.0, 0.0), (0.0, 0.0), 0.5, 0.0, 2 * math.pi)
        with self.assertRaises(ValueError):
            EllipseSeg((0.0, 0.0), (10.0, 0.0), 0.0, 0.0, 2 * math.pi)


class TestDegenerateEntitiesInADrawing(unittest.TestCase):

    def setUp(self):
        msp = ezdxf.new().modelspace()
        msp.add_lwpolyline([(0, 0), (10, 0), (10, 10), (0, 10)], close=True)
        msp.add_arc((3, 3), 0, 0, 90)
        msp.add_circle((6, 6), 0)
        # vertice ripetuto col bulge: una corda nulla
        msp.add_lwpolyline([(2, 2, 0.5), (2, 2, 0), (4, 4, 0)], format="xyb")
        self.doc = topo_dxf.document_from_msp(msp)

    def test_001_il_disegno_si_carica_e_avvisa(self):
        text = " ".join(self.doc.warnings)
        self.assertIn("ARC", text)
        self.assertIn("CIRCLE", text)

    def test_002_resta_solo_la_geometria_vera(self):
        result = topo.heal(self.doc)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.clusters), 1)
        self.assertEqual(len(result.loose), 1)    # il tratto (2,2)-(4,4)
        for curve in result.loose:
            for seg in curve.segments:
                self.assertFalse(any(math.isnan(c) for p in seg.discretize() for c in p))


if __name__ == "__main__":
    unittest.main()
