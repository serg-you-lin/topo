"""
tests/engine/readings/test_network.py

`heal()` restituisce la rete riparata e le letture sono suoi metodi (D202):
la superficie di `Network`, i due numeri, `source_file` e `label` portati su
ogni lettura, `island()` sparito. Geometria costruita coi numeri.
"""

import unittest

import topo
from topo.primitives import LineSeg


def _square(x0: float = 0.0, side: float = 10.0) -> list:
    a, b, c, d = (x0, 0.0), (x0 + side, 0.0), (x0 + side, side), (x0, side)
    return [LineSeg(a, b), LineSeg(b, c), LineSeg(c, d), LineSeg(d, a)]


def _doc(segments: list, source_path: str = "") -> topo.Document:
    doc = topo.load_segments(segments)
    doc.source_path = source_path
    return doc


class TestHealReturnsNetwork(unittest.TestCase):

    def test_heal_restituisce_la_rete_e_le_due_letture(self):
        net = topo.heal(_doc(_square()), tolerance=0.01)
        self.assertIsInstance(net, topo.Network)
        self.assertTrue(net.is_valid)
        for reading in (net.faces(), net.outlines()):
            self.assertIsInstance(reading, topo.Result)
            self.assertTrue(reading.is_valid)
            self.assertEqual(len(reading.clusters), 1)

    def test_la_stessa_rete_letta_due_volte_da_lo_stesso(self):
        # una lettura non sporca la rete per la successiva
        net = topo.heal(_doc(_square() + [LineSeg((2, 2), (4, 4))]), tolerance=0.01)
        first, again = net.faces(), (net.outlines(), net.faces())[1]
        self.assertEqual([c.outer.area for c in first.clusters], [c.outer.area for c in again.clusters])
        self.assertEqual(len(first.loose), len(again.loose))

    def test_superficie(self):
        net = topo.heal(_doc(_square()), tolerance=0.01)
        for name in ("edges", "crossings", "free_ends", "set_aside", "warnings", "errors",
                     "is_valid", "source_file", "label", "tolerance", "max_gap", "faces", "outlines"):
            self.assertTrue(hasattr(net, name), name)
        # la rete piana con gli incroci (NodedEdges) resta interna
        self.assertFalse(hasattr(net, "noded"))

    def test_island_non_esiste_piu(self):
        self.assertFalse(hasattr(topo, "island"))
        self.assertNotIn("island", topo.__all__)
        self.assertIn("Network", topo.__all__)


class TestTwoNumbers(unittest.TestCase):

    def test_max_gap_di_default_e_la_tolleranza(self):
        net = topo.heal(_doc(_square()), tolerance=0.05)
        self.assertEqual((net.tolerance, net.max_gap), (0.05, 0.05))

    def test_max_gap_mai_sotto_la_tolleranza(self):
        net = topo.heal(_doc(_square()), tolerance=0.05, max_gap=0.01)
        self.assertEqual(net.max_gap, 0.05)

    def test_un_gap_si_chiude_solo_entro_max_gap(self):
        # un lato interrotto di 0.3: chiuso con max_gap 0.5, aperto senza
        segs = [LineSeg((0.0, 0.0), (9.7, 0.0))] + _square()[1:]
        self.assertEqual(len(topo.heal(_doc(segs), tolerance=0.01).faces().clusters), 0)
        self.assertEqual(len(topo.heal(_doc(segs), tolerance=0.01, max_gap=0.5).faces().clusters), 1)


class TestProvenance(unittest.TestCase):

    def test_source_file_di_default_dal_documento(self):
        net = topo.heal(_doc(_square(), source_path="parte.dxf"), tolerance=0.01)
        self.assertEqual(net.source_file, "parte.dxf")
        for reading in (net.faces(), net.outlines()):
            self.assertEqual(reading.source_file, "parte.dxf")
            self.assertEqual([c.source_file for c in reading.clusters], ["parte.dxf"])

    def test_source_file_del_chiamante_vince(self):
        net = topo.heal(_doc(_square(), source_path="parte.dxf"), tolerance=0.01, source_file="altro.dxf")
        self.assertEqual(net.faces().source_file, "altro.dxf")
        self.assertEqual(net.outlines().source_file, "altro.dxf")

    def test_label_su_ogni_cluster_di_tutte_e_due_le_letture(self):
        net = topo.heal(_doc(_square() + _square(x0=20.0)), tolerance=0.01, label="p")
        for reading in (net.faces(), net.outlines()):
            self.assertEqual([c.label for c in reading.clusters], ["p", "p"])


class TestEmpty(unittest.TestCase):

    def test_documento_vuoto_rete_non_valida_e_letture_non_valide(self):
        net = topo.heal(_doc([]))
        self.assertFalse(net.is_valid)
        for reading in (net.faces(), net.outlines()):
            self.assertFalse(reading.is_valid)
            self.assertEqual(reading.errors, net.errors)


if __name__ == "__main__":
    unittest.main()
