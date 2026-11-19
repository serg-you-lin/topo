# tests/engine/base/test_move_onto_targets.py

"""
D271: una curva aperta coi due capi entro `max_gap` da due curve diverse,
almeno uno staccato, si sposta intera su di loro. Non verso un filetto
(arco o cerchio con un altro concentrico), non una retta per il centro del
cerchio (un asse).
"""

import math
import unittest

import topo
from topo.primitives import ArcSeg, CircleSeg, LineSeg

OFF = 0.004   # i raccordi disegnati qualche millesimo di fianco al lato


def _line(a, b):
    return LineSeg(start=a, end=b)


def _arc(center, radius, a0, a1):
    return ArcSeg(center=center, radius=radius, start_angle=math.radians(a0), end_angle=math.radians(a1), ccw=True)


def _bridge(off: float) -> list:
    """Due blocchi 40x40 uniti in alto da un ponticello alto 10; sotto il
    ponticello due raccordi R3 spostati di `off` lungo x."""
    return [_line((0, 0), (40, 0)), _line((0, 0), (0, 40)), _line((40, 0), (40, 40)),
            _line((60, 0), (100, 0)), _line((100, 0), (100, 40)), _line((60, 0), (60, 40)),
            _line((0, 40), (100, 40)), _line((43, 30), (57, 30)),
            _arc((43 + off, 27), 3, 90, 180), _arc((57 - off, 27), 3, 0, 90)]


def _moved(net) -> list:
    return [d for d in net.notes if d.code == "curves-moved"]


class TestRaccordoDiFianco(unittest.TestCase):

    def test_il_ponticello_chiude_e_lo_dice(self):
        net = topo.heal(topo.load_segments(_bridge(OFF)), max_gap=0.05)
        result = net.outlines()
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.clusters), 1)
        exact = topo.heal(topo.load_segments(_bridge(0.0)), max_gap=0.05).outlines()
        self.assertAlmostEqual(result.clusters[0].outer.area, exact.clusters[0].outer.area, places=6)
        self.assertEqual(len(_moved(net)[0].points), 2)

    def test_senza_max_gap_niente_si_sposta(self):
        # D267: heal(doc) legge il disegno com'è
        net = topo.heal(topo.load_segments(_bridge(OFF)))
        self.assertEqual(_moved(net), [])

    def test_oltre_max_gap_niente_si_sposta(self):
        net = topo.heal(topo.load_segments(_bridge(OFF)), max_gap=0.003)
        self.assertEqual(_moved(net), [])


class TestNonSiSposta(unittest.TestCase):

    def test_braccio_d_asse_che_supera_il_foro(self):
        # croce d'asse di un foro R3: i bracci partono dal centro e superano il
        # cerchio di 0,3; un braccio tocca una retta col capo esterno
        segs = [CircleSeg(center=(0, 0), radius=3), _line((0, 0), (3.3, 0)), _line((3.3, -1), (3.3, 1))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.5)
        self.assertEqual(_moved(net), [])

    def test_riga_verso_un_filetto(self):
        # filetto: foro R3 e arco di cresta R3,5 concentrico; la riga finisce
        # 0,2 fuori dalla cresta e tocca una retta con l'altro capo
        segs = [CircleSeg(center=(0, 0), radius=3), _arc((0, 0), 3.5, 0, 270),
                _line((2.0, 4.0), (2.0, 2.9)), _line((1.0, 4.0), (3.0, 4.0))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.5)
        self.assertEqual(_moved(net), [])


if __name__ == "__main__":
    unittest.main()
