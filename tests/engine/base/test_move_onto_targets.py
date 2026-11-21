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
from topo.primitives import BSplineSeg, CircleSeg, EllipseSeg, LineSeg

OFF = 0.004   # i raccordi disegnati qualche millesimo di fianco al lato


def _line(a, b):
    return LineSeg(start=a, end=b)


def _arc(center, radius, a0, a1):
    return CircleSeg(center=center, radius=radius, start_angle=math.radians(a0), end_angle=math.radians(a1), ccw=True)


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


def _png(off: float = 0.01) -> list:
    """Il caso del disegno di Federico, chiuso: verticale che finisce poco sotto
    il raccordo R2, raccordo `off` a destra della verticale, legato all'obliqua."""
    arc = _arc((2 + off, 10), 2, 45, 180)
    top = (2 + off + 2 * math.cos(math.radians(45)), 10 + 2 * math.sin(math.radians(45)))
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 9.99)), arc, _line(top, (20, 0))]


def _pinned(gap: float = 0.017) -> list:
    """drw_0007: un arco coi capi inchiodati; la verticale finisce `gap` di
    fianco alla sua pancia."""
    cx = gap + 1.0
    arc = _arc((cx, 5), 1.0, 90, 270)
    top, bottom = (cx, 6.0), (cx, 4.0)
    return [_line((0, 0), (10, 0)), _line((10, 0), (10, 10)), _line((10, 10), (cx, 10)), _line((cx, 10), top), arc,
            _line(bottom, (cx, 2)), _line((0, 0), (0, 5))]


class TestRaccordoLegatoAUnaRetta(unittest.TestCase):

    def test_l_arco_si_sposta_e_le_rette_si_allungano(self):
        net = topo.heal(topo.load_segments(_png()), max_gap=0.05)
        self.assertEqual(len(_moved(net)), 1)
        self.assertEqual([d for d in net.notes if d.code == "ends-joined"], [])
        faces, outlines = net.faces(), net.outlines()
        for result in (faces, outlines):
            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.clusters), 1)
            # nessun tratto nuovo: retta, verticale allungata, arco, obliqua
            self.assertEqual(sorted(type(s).__name__ for s in result.clusters[0].outer.segments),
                             ["CircleSeg", "LineSeg", "LineSeg", "LineSeg"])
        self.assertAlmostEqual(faces.clusters[0].outer.area, outlines.clusters[0].outer.area, places=9)
        vertical = [s for s in faces.clusters[0].outer.segments if isinstance(s, LineSeg) and abs(s.start[0]) < 1e-9 and abs(s.end[0]) < 1e-9]
        self.assertGreater(max(vertical[0].start[1], vertical[0].end[1]), 9.99)   # allungata, non spostata


def _png_with(curve, top) -> list:
    """Il caso del PNG con un'altra primitiva al posto dell'arco: `top` è il suo
    capo legato all'obliqua."""
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 9.99)), curve, _line(top, (20, 0))]


def _two_fillets(off: float = 0.01) -> list:
    """Una retta in alto con un raccordo R2 a ogni capo, tutti e due `off` dentro
    rispetto ai lati, che finiscono poco sotto."""
    left = _arc((2 + off, 8), 2, 90, 180)
    right = _arc((18 - off, 8), 2, 0, 90)
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 7.99)), left, _line((2 + off, 10), (18 - off, 10)), right,
            _line((20, 0), (20, 7.99))]


def _one_piece(test, net, sides: int):
    """faces() e outlines(): lo stesso pezzo chiuso, di `sides` lati, senza tratti nuovi."""
    test.assertEqual([d for d in net.notes if d.code == "ends-joined"], [])
    faces, outlines = net.faces(), net.outlines()
    for result in (faces, outlines):
        test.assertTrue(result.is_valid)
        test.assertEqual(len(result.clusters), 1)
        test.assertEqual(len(result.clusters[0].outer.segments), sides)
    test.assertAlmostEqual(faces.clusters[0].outer.area, outlines.clusters[0].outer.area, places=9)


class TestAltrePrimitive(unittest.TestCase):

    def test_arco_di_ellisse(self):
        ellipse = EllipseSeg(center=(3.01, 10), major_axis=(3, 0), ratio=2 / 3,
                             start_param=math.radians(45), end_param=math.radians(180), ccw=True)
        top = (3.01 + 3 * math.cos(math.radians(45)), 10 + 2 * math.sin(math.radians(45)))
        net = topo.heal(topo.load_segments(_png_with(ellipse, top)), max_gap=0.05)
        self.assertEqual(len(_moved(net)), 1)
        _one_piece(self, net, 4)

    def test_spline(self):
        spline = BSplineSeg(control_points=[(3.424, 11.414), (0.01, 12.5), (0.01, 10)], knots=[0, 0, 0, 1, 1, 1], degree=2)
        net = topo.heal(topo.load_segments(_png_with(spline, (3.424, 11.414))), max_gap=0.05)
        self.assertEqual(len(_moved(net)), 1)
        _one_piece(self, net, 4)

    def test_raccordo_a_ogni_capo_della_retta(self):
        # entro max_gap si sistemano tutti e due: la retta si allunga a un capo per uno
        net = topo.heal(topo.load_segments(_two_fillets()), max_gap=0.05)
        self.assertEqual(len(_moved(net)[0].points), 2)
        _one_piece(self, net, 6)


class TestArcoInchiodato(unittest.TestCase):

    def test_l_arco_passa_per_il_capo(self):
        net = topo.heal(topo.load_segments(_pinned()), max_gap=0.05)
        self.assertEqual(len([d for d in net.notes if d.code == "arc-bent"]), 1)
        faces, outlines = net.faces(), net.outlines()
        for result in (faces, outlines):
            self.assertTrue(result.is_valid)
            self.assertEqual(len(result.clusters), 1)
        self.assertAlmostEqual(faces.clusters[0].outer.area, outlines.clusters[0].outer.area, places=9)

    def test_oltre_max_gap_resta_aperto(self):
        net = topo.heal(topo.load_segments(_pinned()), max_gap=0.005)
        self.assertEqual([d for d in net.notes if d.code == "arc-bent"], [])


class TestNonSiSposta(unittest.TestCase):

    def test_una_retta_non_si_sposta_mai(self):
        # retta corta coi due capi liberi a 0,01 da due lati perpendicolari:
        # si allunga fino a loro, non trasla
        segs = [_line((0, 0), (10, 0)), _line((0, 0), (0, 10)), _line((2, 0.01), (0.01, 2))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.05)
        self.assertEqual(_moved(net), [])
        moved_line = [e.segment for e in net.edges if abs(e.segment.start[0] - e.segment.end[0]) > 1
                      and abs(e.segment.start[1] - e.segment.end[1]) > 1]
        for p in (moved_line[0].start, moved_line[0].end):
            self.assertAlmostEqual(p[0] + p[1], 2.01, places=9)   # sempre sulla stessa retta x + y = 2,01

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
