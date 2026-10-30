"""
tests/unit/test_loose.py
------------------------
`result.loose` (MAP.md D137): ogni curva che non è contorno di nessun
cluster sa quale cluster la contiene (`cluster_ref`), un consumatore la
sposta in `cluster.detected` con `topo.promote`, `split` la manda alla parte
del suo `cluster_ref`.

Il disegno: una piastra 200×100 centrata nell'origine con un foro Ø20 in
(50, 0), una linea da lato a lato, una croce di centro dentro il foro, un
cerchietto marcato da un consumatore dentro la piastra, una linea fuori da
tutto; più in là una piastrina 50×50 con una linea dentro.
"""

import math
import unittest

import topo
from topo.primitives import LineSeg
from topo import to_shapely

fg = topo.geometry


def _drawing():
    doc = topo.load_segments([
        fg.rectangle(200, 100),
        fg.circle(10, center=(50, 0)),
        LineSeg(start=(0, -50), end=(0, 50)),          # da lato a lato
        LineSeg(start=(45, 0), end=(55, 0)),           # croce nel foro
        LineSeg(start=(50, -5), end=(50, 5)),
        LineSeg(start=(150, 0), end=(180, 0)),         # fuori da tutto
        fg.rectangle(50, 50, center=(400, 0)),
        LineSeg(start=(390, 0), end=(410, 0)),         # dentro la piastrina
    ])
    mark = topo.load_segments(fg.circle(5, center=(-50, 0)), role="mark")
    doc.edges += mark.edges
    return doc


def _at(result, x, y):
    """La curva sciolta che passa per (x, y)."""
    for curve in result.loose:
        pts = topo.geometry.track_points(curve.segments)
        if any(math.dist(p, (x, y)) < 1e-6 for p in pts):
            return curve
    raise AssertionError(f"nessuna curva sciolta per ({x}, {y})")


class TestClusterRef(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = topo.heal(_drawing())

    def test_due_parti_la_piastra_e_la_piu_grande(self):
        self.assertEqual(len(self.result.clusters), 2)
        self.assertAlmostEqual(to_shapely(self.result.clusters[0].outer).area, 20000, delta=1)

    def test_linea_da_lato_a_lato_sta_nella_piastra(self):
        self.assertEqual(_at(self.result, 0, -50).cluster_ref, 0)

    def test_croce_nel_foro_sta_nella_piastra(self):
        self.assertEqual(_at(self.result, 45, 0).cluster_ref, 0)
        self.assertEqual(_at(self.result, 50, 5).cluster_ref, 0)

    def test_curva_chiusa_marcata_sta_nella_piastra(self):
        mark = next(c for c in self.result.loose if c.role == "mark")
        self.assertIsNotNone(to_shapely(mark))
        self.assertEqual(mark.cluster_ref, 0)

    def test_linea_fuori_da_tutto_non_ha_cluster(self):
        self.assertIsNone(_at(self.result, 150, 0).cluster_ref)

    def test_linea_nella_piastrina(self):
        self.assertEqual(_at(self.result, 390, 0).cluster_ref, 1)


class TestPromote(unittest.TestCase):

    def setUp(self):
        self.result = topo.heal(_drawing())

    def test_sposta_da_loose_a_detected(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        topo.promote(self.result, line, plate, "lines")
        self.assertFalse(any(c is line for c in self.result.loose))
        self.assertIs(plate.detected.get("lines")[0], line)

    def test_il_chiamante_attacca_quello_che_ne_ha_fatto(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        topo.promote(self.result, line, plate, "axes", item=("asse", line))
        self.assertEqual(plate.detected.get("axes"), [("asse", line)])

    def test_anche_una_curva_fuori_da_ogni_cluster(self):
        guide = _at(self.result, 150, 0)
        topo.promote(self.result, guide, self.result.clusters[1], "guides")
        self.assertIs(self.result.clusters[1].detected.get("guides")[0], guide)

    def test_due_volte_solleva(self):
        line = _at(self.result, 0, -50)
        plate = self.result.clusters[0]
        topo.promote(self.result, line, plate, "lines")
        with self.assertRaises(ValueError):
            topo.promote(self.result, line, plate, "lines")
        self.assertEqual(len(plate.detected.get("lines")), 1)

    def test_cluster_di_un_altro_result_solleva(self):
        other = topo.heal(_drawing()).clusters[0]
        line = _at(self.result, 0, -50)
        with self.assertRaises(ValueError):
            topo.promote(self.result, line, other, "lines")
        self.assertTrue(any(c is line for c in self.result.loose))


class TestPromoteGroup(unittest.TestCase):
    """Più curve, un solo item (D172): un foro e la sua sede."""

    def setUp(self):
        self.result = topo.heal(_drawing())
        self.line = _at(self.result, 0, -50)
        self.guide = _at(self.result, 150, 0)
        self.plate = self.result.clusters[0]
        self.before = len(self.result.loose)

    def test_due_curve_un_item(self):
        topo.promote(self.result, [self.line, self.guide], self.plate, "pairs", item="coppia")
        self.assertEqual(self.plate.detected.get("pairs"), ["coppia"])
        self.assertEqual(len(self.result.loose), self.before - 2)
        self.assertFalse(any(c is self.line or c is self.guide for c in self.result.loose))

    def test_una_curva_in_lista_e_la_curva_stessa(self):
        topo.promote(self.result, [self.line], self.plate, "lines")
        self.assertIs(self.plate.detected.get("lines")[0], self.line)

    def test_senza_item_solleva_e_non_tocca(self):
        with self.assertRaises(ValueError):
            topo.promote(self.result, [self.line, self.guide], self.plate, "pairs")
        self.assertEqual(len(self.result.loose), self.before)
        self.assertIsNone(self.plate.detected)

    def test_una_curva_assente_non_sposta_le_altre(self):
        topo.promote(self.result, self.guide, self.plate, "guides")
        with self.assertRaises(ValueError):
            topo.promote(self.result, [self.line, self.guide], self.plate, "pairs", item="coppia")
        self.assertTrue(any(c is self.line for c in self.result.loose))
        self.assertEqual(self.plate.detected.get("pairs"), [])

    def test_doppione_solleva(self):
        with self.assertRaises(ValueError):
            topo.promote(self.result, [self.line, self.line], self.plate, "pairs", item="coppia")
        self.assertEqual(len(self.result.loose), self.before)

    def test_vuoto_solleva(self):
        with self.assertRaises(ValueError):
            topo.promote(self.result, [], self.plate, "pairs", item="niente")


class TestSplit(unittest.TestCase):

    def setUp(self):
        self.result = topo.heal(_drawing())
        self.plate, self.small = topo.split(self.result, min_area=0)

    def test_ogni_curva_va_al_suo_cluster(self):
        self.assertEqual(len(self.plate.loose) + len(self.small.loose), len(self.result.loose))
        refs = [c.cluster_ref for c in self.plate.loose]
        self.assertIn(0, refs)
        self.assertEqual([c.cluster_ref for c in self.small.loose], [0])

    def test_quella_fuori_va_alla_parte_piu_vicina_senza_cluster_ref(self):
        outside = _at(self.plate, 150, 0)
        self.assertIsNone(outside.cluster_ref)

    def test_l_originale_non_cambia(self):
        self.assertEqual(_at(self.result, 390, 0).cluster_ref, 1)

    def test_una_curva_promossa_viaggia_col_suo_cluster(self):
        result = topo.heal(_drawing())
        guide = _at(result, 150, 0)
        topo.promote(result, guide, result.clusters[1], "guides")
        plate, small = topo.split(result, min_area=0)
        self.assertEqual(small.clusters[0].detected.get("guides"), [guide])
        self.assertFalse(any(c.cluster_ref is None for c in plate.loose))


class TestRotate(unittest.TestCase):

    def test_curva_chiusa_sciolta_ruota_col_resto(self):
        result = topo.heal(_drawing())
        rotated = topo.rotate_result(result, math.pi / 2)
        mark = next(c for c in rotated.loose if c.role == "mark")
        c = to_shapely(mark).centroid
        self.assertAlmostEqual(c.x, 0, places=3)
        self.assertAlmostEqual(c.y, -50, places=3)


if __name__ == "__main__":
    unittest.main()
