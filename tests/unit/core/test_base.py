# tests/unit/core/test_base.py
# Le basi comuni a ogni lettura (D187): i nodi si decidono una volta, per
# vicinanza, prima di heal() e di outlines(); le due letture partono dagli stessi.

import unittest

import topo
from topo.core.primitives.segments import LineSeg
from topo.core.topology.noding import decide_nodes
from tests.invariants import MOTIONS, contours, moved, shape_differences
from topo.core.primitives.segments import DEFAULT_TOLERANCE


def _square_with_split_corner():
    # l'angolo in alto a destra disegnato con due estremi a 0.0002: 10.0004 e
    # 10.0006 cadono in due celle diverse della griglia da 1e-3
    return [LineSeg(start=(0.0, 0.0), end=(10.0, 0.0)),
            LineSeg(start=(10.0, 0.0), end=(10.0004, 10.0)),
            LineSeg(start=(10.0006, 10.0), end=(0.0, 10.0)),
            LineSeg(start=(0.0, 10.0), end=(0.0, 0.0))]


class TestDecideNodes(unittest.TestCase):

    def test_estremi_a_cavallo_di_una_cella_sono_un_nodo(self):
        doc = topo.load_segments(_square_with_split_corner())
        self.assertNotEqual(doc.edges[1].end, doc.edges[2].start)   # la tupla della griglia
        edges, welded = decide_nodes(doc.edges)
        self.assertEqual(edges[1].end, edges[2].start)
        self.assertEqual(welded, 0)

    def test_punti_fitti_piu_larghi_di_epsilon_restano_distinti(self):
        # una curva scritta a passi da 0.004: il gruppo supera 0.01, nessun nodo fuso
        pts = [(5.0 + 0.004 * k, 1.0) for k in range(6)]
        doc = topo.load_segments([LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])])
        edges, welded = decide_nodes(doc.edges)
        self.assertEqual(len(edges), 5)
        self.assertEqual(welded, 0)
        self.assertEqual(len({p for e in edges for p in (e.start, e.end)}), 6)


class TestSameBaseForEveryReading(unittest.TestCase):

    def test_heal_e_island_leggono_lo_stesso_contorno_a_ogni_moto(self):
        doc = topo.load_segments(_square_with_split_corner())
        band = 2 * DEFAULT_TOLERANCE
        for name, move, back, _ in [("al posto", lambda s: s, lambda p: p, None)] + MOTIONS:
            moved_doc = moved(doc, move)
            healed = [back(p) for p in contours(topo.heal(moved_doc, tolerance=0.05).faces())[0]]
            read = [back(p) for p in contours(topo.heal(moved_doc, max_gap=0.5).outlines())[0]]
            self.assertEqual((len(healed), len(read)), (1, 1), name)
            self.assertEqual(shape_differences(healed, read, band) + shape_differences(read, healed, band),
                             [], name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
