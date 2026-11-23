# tests/engine/base/test_tied_facing_ends.py

"""Two already bound ends facing each other along their own extension, within
`max_gap`, are joined by a new stretch. The side view of drw_0031: the two
sides broken with a hole of a few thousandths."""

import unittest

import topo
from topo.primitives import LineSeg

STEP = 0.005   # the hole between the two pieces of each side


def _line(a, b):
    return LineSeg(start=a, end=b)


def _side_view() -> list:
    """Strip 100x2 below; above, the body, with the sides restarting STEP higher and
    a 0.3-wide return at each side."""
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
        # heal(doc) reads the drawing as it is
        self.assertEqual(_tied(topo.heal(topo.load_segments(_side_view()))), [])


if __name__ == "__main__":
    unittest.main()
