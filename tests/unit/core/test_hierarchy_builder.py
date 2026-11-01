"""
tests/unit/core/test_hierarchy_builder.py

Test per HierarchyBuilder.

D15: HierarchyBuilder costruisce SOLO l'albero di contenimento —
`Cluster(outer, inners=[Contour...])`, zero `Hole`. La classificazione
hole / countersink è di `detect_flat()` (vedi tests/unit/test_detect.py).

I proxy ClosedCurve/OpenCurve vengono costruiti direttamente con primitive
native — nessun adapter DXF, nessun file reale.
"""

import math
import unittest
from shapely.geometry import Polygon

from topo.core.primitives.segments import LineSeg
from topo.model.curve import ClosedCurve, OpenCurve
from topo.model.role import ContourRole
from topo.core.base.hierarchy import HierarchyBuilder
import topo
from topo import to_shapely


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_proxy(polygon, *, role=ContourRole.UNKNOWN):
    return ClosedCurve(role=role, segments=topo.geometry.polygon(polygon.exterior.coords))


def _make_open_proxy(pts, *, role=ContourRole.UNKNOWN):
    segments = [
        LineSeg(start=pts[i], end=pts[i + 1])
        for i in range(len(pts) - 1)
    ]
    return OpenCurve(role=role, segments=segments)


def _circle_proxy(cx, cy, r):
    poly = Polygon(
        [(cx + r * math.cos(a * math.pi / 180),
          cy + r * math.sin(a * math.pi / 180))
         for a in range(0, 360, 5)]
    )
    return _make_proxy(poly)


def _rect_proxy(x0, y0, x1, y1):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return _make_proxy(poly)


def _make_builder():
    return HierarchyBuilder(
        label="",
        source_file="",
    )


class TestVirtualModelRemoved(unittest.TestCase):
    def test_closed_shape_has_no_virtual_flag(self):
        proxy = _make_proxy(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]))
        self.assertFalse(hasattr(proxy, "is_virtual"))
        self.assertFalse(hasattr(proxy, "vs_id"))


# ---------------------------------------------------------------------------
# Test 1 — outer + contorno interno
# ---------------------------------------------------------------------------

class TestOuterConInner(unittest.TestCase):
    """
    - 1 proxy grande (100×100) → OUTER
    - 1 proxy circolare d=5 contenuto → inner (heal NON lo promuove a foro)

    Atteso: 1 Cluster, 0 holes, 1 inner, trash vuoto.
    """

    def setUp(self):
        self.outer = _rect_proxy(0, 0, 100, 100)
        self.inner = _circle_proxy(50, 50, 2.5)
        self.clusters, self.trash = _make_builder().build([self.outer, self.inner])

    def test_produce_una_part(self):
        self.assertEqual(len(self.clusters), 1)

    def test_outer_area(self):
        self.assertAlmostEqual(to_shapely(self.clusters[0].outer).area, 10000.0, delta=1.0)

    def test_zero_holes(self):
        self.assertEqual(len(self.clusters[0].features("holes")), 0)

    def test_un_inner(self):
        self.assertEqual(len(self.clusters[0].inners), 1)
        self.assertEqual(self.clusters[0].inners[0].role, ContourRole.INNER)

    def test_trash_vuoto(self):
        self.assertEqual(len(self.trash), 0)


# ---------------------------------------------------------------------------
# Test 2 — nesting a tre livelli (countersink): heal appiattisce tutto in inners
# ---------------------------------------------------------------------------

class TestNestingFlattened(unittest.TestCase):
    """
    - outer   : rettangolo 100×100
    - medio   : cerchio d=20 dentro outer
    - piccolo : cerchio d=8  dentro medio

    heal() non riconosce più il countersink dal nesting (D15): consegna
    entrambi i cerchi come inners piatti. Il riconoscimento è di detect_flat().
    """

    def setUp(self):
        outer   = _rect_proxy(0, 0, 100, 100)
        medio   = _circle_proxy(50, 50, 10)   # d=20
        piccolo = _circle_proxy(50, 50, 4)    # d=8
        self.clusters, self.trash = _make_builder().build([outer, medio, piccolo])

    def test_produce_una_part(self):
        self.assertEqual(len(self.clusters), 1)

    def test_zero_holes(self):
        self.assertEqual(len(self.clusters[0].features("holes")), 0)

    def test_due_inners(self):
        self.assertEqual(len(self.clusters[0].inners), 2)


# ---------------------------------------------------------------------------
# Test 2bis — stessa gerarchia, ma depth/parent non vengono più persi
# ---------------------------------------------------------------------------

class TestNestingDepthAndParent(unittest.TestCase):
    """
    Stessa gerarchia a tre livelli di TestNestingFlattened: outer (100x100) →
    medio (d=20) → piccolo (d=8). heal() appiattisce comunque tutto in
    `cluster.inners`, ma ogni Contour porta con sé `depth`/`parent` — il
    dato che uno strumento di linguette (Smoother) legge per sapere chi è
    nipote di chi, invece di ricalcolare il contenimento da solo.
    """

    def setUp(self):
        self.outer_proxy   = _rect_proxy(0, 0, 100, 100)
        self.medio_proxy   = _circle_proxy(50, 50, 10)   # d=20, figlio diretto
        self.piccolo_proxy = _circle_proxy(50, 50, 4)    # d=8,  nipote
        self.clusters, _ = _make_builder().build(
            [self.outer_proxy, self.medio_proxy, self.piccolo_proxy]
        )
        self.cluster = self.clusters[0]
        # area decrescente: inners[0] è sempre il medio, inners[1] il piccolo
        # (_build_tree ordina i proxy per area prima di piazzarli).
        self.medio, self.piccolo = self.cluster.inners

    def test_outer_depth_zero_senza_genitore(self):
        self.assertEqual(self.cluster.outer.depth, 0)
        self.assertIsNone(self.cluster.outer.parent)

    def test_figlio_diretto_depth_uno_genitore_e_outer(self):
        self.assertEqual(self.medio.depth, 1)
        self.assertIs(self.medio.parent, self.cluster.outer)

    def test_nipote_depth_due_genitore_e_il_figlio_non_l_outer(self):
        self.assertEqual(self.piccolo.depth, 2)
        self.assertIs(self.piccolo.parent, self.medio)
        self.assertIsNot(self.piccolo.parent, self.cluster.outer)


# ---------------------------------------------------------------------------
# Test 3 — trash
# ---------------------------------------------------------------------------

class TestTrash(unittest.TestCase):
    """
    - 1 proxy outer (100×100)
    - 1 OpenCurve role=UNKNOWN fuori dall'outer

    Atteso: il proxy aperto flottante finisce in trash, l'outer produce 1 Cluster.
    """

    def setUp(self):
        self.outer    = _rect_proxy(0, 0, 100, 100)
        self.floating = _make_open_proxy([(200, 200), (210, 200)], role=ContourRole.UNKNOWN)
        self.clusters, self.trash = _make_builder().build([self.outer, self.floating])

    def test_una_part_prodotta(self):
        self.assertGreaterEqual(len(self.clusters), 1)

    def test_floating_in_trash(self):
        self.assertIn(self.floating, self.trash)

    def test_outer_non_in_trash(self):
        self.assertFalse(
            any(
                getattr(t, "polygon", None) is not None
                and to_shapely(t).equals(to_shapely(self.outer))
                for t in self.trash
            )
        )


# ---------------------------------------------------------------------------
# Test 4 — segments copiati dal proxy al model
# ---------------------------------------------------------------------------

class TestSegmentsCopiati(unittest.TestCase):
    """
    HierarchyBuilder copia proxy.segments su outer e inner.

    I segments sono stub — l'importante è che arrivino intatti.
    """

    def setUp(self):
        from topo.core.primitives import LineSeg, ArcSeg

        self.seg_outer = [
            LineSeg(start=(0, 0),   end=(100, 0)),
            LineSeg(start=(100, 0), end=(100, 100)),
            LineSeg(start=(100, 100), end=(0, 100)),
            LineSeg(start=(0, 100), end=(0, 0)),
        ]
        self.seg_inner = [
            ArcSeg(center=(50, 50), radius=2.5,
                   start_angle=0.0, end_angle=6.2831, ccw=True),
        ]

        outer = _rect_proxy(0, 0, 100, 100)
        outer.segments = list(self.seg_outer)

        inner = _circle_proxy(50, 50, 2.5)
        inner.segments = list(self.seg_inner)

        self.clusters, _ = _make_builder().build([outer, inner])

    def test_outer_segments_copiati(self):
        self.assertEqual(self.clusters[0].outer.segments, self.seg_outer)

    def test_inner_segments_copiati(self):
        self.assertEqual(self.clusters[0].inners[0].segments, self.seg_inner)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCopiesOrderUnderMotion(unittest.TestCase):
    """G6e, gruppo B, `hierarchy.py:82`: due copie congruenti si ordinano per
    l'angolo del bbox (D166). L'area arrotondata a 1e-6 le diceva pari solo se
    cadevano nella stessa cella: con l'area a metà cella (10.0000005) l'ultimo
    bit, che il moto cambia, decideva l'ordine. Prova: a ogni traslazione la
    copia a sinistra (o in basso) viene prima. Le rotazioni non sono provate:
    lì cambia davvero quale copia è a sinistra."""

    W, H = 10.0, 1.00000005
    MOTIONS = [(0.0, dx, dy) for dx in (0.0, 0.3, 1.7, 13.1, 250.0, 2.5e6) for dy in (0.0, 0.7, -9.3, -1.5e6)]

    @staticmethod
    def _rectangle(x0, y0, w, h):
        p = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        return [LineSeg(start=p[i], end=p[(i + 1) % 4]) for i in range(4)]

    def _first_corner(self, offset, motion):
        from tests.invariants import rigid
        segment, point = rigid(*motion)
        segs = self._rectangle(0, 0, self.W, self.H) + self._rectangle(*offset, self.W, self.H)
        result = topo.heal(topo.load_segments([segment(s) for s in segs])).faces()
        self.assertEqual(len(result.clusters), 2)
        return result.clusters[0].bbox[:2], point((0.0, 0.0))

    def test_copie_affiancate_la_sinistra_prima(self):
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                corner, origin = self._first_corner((20, 0), motion)
                self.assertAlmostEqual(corner[0], origin[0], delta=1e-3)

    def test_copie_impilate_la_bassa_prima(self):
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                corner, origin = self._first_corner((0, 5), motion)
                self.assertAlmostEqual(corner[1], origin[1], delta=1e-3)


class TestTreeOrderUnderMotion(unittest.TestCase):
    """G6e, gruppo B, `hierarchy.py:86`: `_build_tree` piazza i contorni dal
    più grande per `round(area, 6)`. L'ordine decide la forma dell'albero solo
    fra due contorni di cui uno contiene l'altro, e lì le aree differiscono
    ben oltre 1e-6 (sui disegni: 344 coppie entro 1e-5, nessuna annidata).
    Prova: una piastra con due fori congruenti con l'area a metà cella dà a
    ogni traslazione un cluster con due inner di profondità 1. Non prova
    l'ordine dei due inner fra loro, che non è un contratto."""

    MOTIONS = [(0.0, dx, dy) for dx in (0.0, 0.3, 13.1, 250.0, 2.5e6) for dy in (0.0, -9.3, -1.5e6)]

    def test_due_fori_congruenti_restano_figli_della_piastra(self):
        from tests.invariants import rigid
        rect = TestCopiesOrderUnderMotion._rectangle
        segs = rect(0, 0, 40, 10) + rect(2, 2, 10, 1.00000005) + rect(22, 2, 10, 1.00000005)
        for motion in self.MOTIONS:
            with self.subTest(motion=motion):
                segment, _ = rigid(*motion)
                result = topo.heal(topo.load_segments([segment(s) for s in segs])).faces()
                self.assertEqual(len(result.clusters), 1)
                self.assertEqual([c.depth for c in result.clusters[0].inners], [1, 1])
