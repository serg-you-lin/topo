# tests/engine/base/test_move_onto_targets.py

"""An open curve with both ends within `max_gap` of two different curves, at
least one detached, moves whole onto them. Not towards a thread (arc or circle
with another concentric one), not a line through the circle's centre (an axis)."""

import math
import unittest

import topo
from topo.primitives import BSplineSeg, CircleSeg, EllipseSeg, LineSeg

OFF = 0.004   # fillets drawn a few thousandths beside the side


def _line(a, b):
    return LineSeg(start=a, end=b)


def _arc(center, radius, a0, a1):
    return CircleSeg(center=center, radius=radius, start_angle=math.radians(a0), end_angle=math.radians(a1), ccw=True)


def _bridge(off: float) -> list:
    """Two 40x40 blocks joined at the top by a bridge 10 high; under the bridge two
    R3 fillets moved by `off` along x."""
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
        # heal(doc) reads the drawing as it is
        net = topo.heal(topo.load_segments(_bridge(OFF)))
        self.assertEqual(_moved(net), [])

    def test_oltre_max_gap_niente_si_sposta(self):
        net = topo.heal(topo.load_segments(_bridge(OFF)), max_gap=0.003)
        self.assertEqual(_moved(net), [])


def _png(off: float = 0.01) -> list:
    """The case of Federico's drawing, closed: a vertical ending just below the R2
    fillet, fillet `off` to the right of the vertical, bound to the oblique."""
    arc = _arc((2 + off, 10), 2, 45, 180)
    top = (2 + off + 2 * math.cos(math.radians(45)), 10 + 2 * math.sin(math.radians(45)))
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 9.99)), arc, _line(top, (20, 0))]


def _pinned(gap: float = 0.017) -> list:
    """drw_0007: an arc with nailed ends; the vertical ends `gap` beside its belly."""
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
            # no new stretch: line, lengthened vertical, arc, oblique
            self.assertEqual(sorted(type(s).__name__ for s in result.clusters[0].outer.segments),
                             ["CircleSeg", "LineSeg", "LineSeg", "LineSeg"])
        self.assertAlmostEqual(faces.clusters[0].outer.area, outlines.clusters[0].outer.area, places=9)
        vertical = [s for s in faces.clusters[0].outer.segments if isinstance(s, LineSeg) and abs(s.start[0]) < 1e-9 and abs(s.end[0]) < 1e-9]
        self.assertGreater(max(vertical[0].start[1], vertical[0].end[1]), 9.99)   # lengthened, not moved


def _png_with(curve, top) -> list:
    """The PNG case with another primitive in place of the arc: `top` is its end bound to the oblique."""
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 9.99)), curve, _line(top, (20, 0))]


def _two_fillets(off: float = 0.01) -> list:
    """A line at the top with an R2 fillet at each end, both `off` inside with
    respect to the sides, which end just below."""
    left = _arc((2 + off, 8), 2, 90, 180)
    right = _arc((18 - off, 8), 2, 0, 90)
    return [_line((0, 0), (20, 0)), _line((0, 0), (0, 7.99)), left, _line((2 + off, 10), (18 - off, 10)), right,
            _line((20, 0), (20, 7.99))]


def _one_piece(test, net, sides: int):
    """faces() and outlines(): the same closed piece, of `sides` sides, with no new stretches."""
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
        # within max_gap both are fixed: the line lengthens at one end for one
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
        # short line with both free ends at 0.01 from two perpendicular sides: it
        # lengthens up to them, does not translate
        segs = [_line((0, 0), (10, 0)), _line((0, 0), (0, 10)), _line((2, 0.01), (0.01, 2))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.05)
        self.assertEqual(_moved(net), [])
        moved_line = [e.segment for e in net.edges if abs(e.segment.start[0] - e.segment.end[0]) > 1
                      and abs(e.segment.start[1] - e.segment.end[1]) > 1]
        for p in (moved_line[0].start, moved_line[0].end):
            self.assertAlmostEqual(p[0] + p[1], 2.01, places=9)   # always on the same line x + y = 2.01

    def test_braccio_d_asse_che_supera_il_foro(self):
        # axis cross of an R3 hole: the arms start from the centre and exceed the
        # circle by 0.3; one arm touches a line with its outer end
        segs = [CircleSeg(center=(0, 0), radius=3), _line((0, 0), (3.3, 0)), _line((3.3, -1), (3.3, 1))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.5)
        self.assertEqual(_moved(net), [])

    def test_riga_verso_un_filetto(self):
        # thread: R3 hole and concentric R3.5 crest arc; the line ends 0.2 outside the
        # crest and touches a line with the other end
        segs = [CircleSeg(center=(0, 0), radius=3), _arc((0, 0), 3.5, 0, 270),
                _line((2.0, 4.0), (2.0, 2.9)), _line((1.0, 4.0), (3.0, 4.0))]
        net = topo.heal(topo.load_segments(segs), max_gap=0.5)
        self.assertEqual(_moved(net), [])


if __name__ == "__main__":
    unittest.main()
