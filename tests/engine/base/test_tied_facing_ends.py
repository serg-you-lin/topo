# tests/engine/base/test_tied_facing_ends.py

"""
D272: due capi già legati che si guardano lungo il proprio prolungamento,
entro `max_gap`, si uniscono con un tratto nuovo. La vista di fianco di
drw_0031: i due lati spezzati con un buco di qualche millesimo.
"""

import unittest

import topo
from topo.primitives import LineSeg

STEP = 0.005   # il buco fra i due pezzi di ogni lato


def _line(a, b):
    return LineSeg(start=a, end=b)


def _side_view() -> list:
    """Striscia 100x2 sotto; sopra il corpo, coi lati che ripartono STEP più su
    e un risvolto largo 0,3 a ogni lato."""
    top = 2 + STEP
    return [_line((0, 0), (100, 0)), _line((100, 0), (100, 2)), _line((100, 2), (0, 2)), _line((0, 2), (0, 0)),
            _line((0, top), (0, 10)), _line((0, 10), (100, 10)), _line((100, 10), (100, top)),
            _line((0, top), (0.3, top)), _line((0.3, top), (0.3, 3)), _line((0.3, 3), (99.7, 3)),
            _line((99.7, 3), (99.7, top)), _line((99.7, top), (100, top))]


def _tied(net) -> list:
    return [d for d in net.notes if d.code == "tied-ends-joined"]


class TestLatoInDuePezzi(unittest.TestCase):

    def test_la_vista_e_un_pezzo_solo(self):
        net = topo.heal(topo.load_segments(_side_view()), max_gap=0.05)
        result = net.outlines()
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.clusters), 1)
        xmin, ymin, xmax, ymax = result.clusters[0].outer.bbox
        self.assertAlmostEqual(ymin, 0.0)
        self.assertAlmostEqual(ymax, 10.0)
        self.assertEqual(len(_tied(net)[0].points), 2)

    def test_oltre_max_gap_restano_due(self):
        net = topo.heal(topo.load_segments(_side_view()), max_gap=0.003)
        self.assertEqual(_tied(net), [])

    def test_senza_max_gap_niente_si_unisce(self):
        # D267: heal(doc) legge il disegno com'è
        self.assertEqual(_tied(topo.heal(topo.load_segments(_side_view()))), [])


if __name__ == "__main__":
    unittest.main()
