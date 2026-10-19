"""
test_tabs.py
------------
Test unitari per topo.tools.tabs (MAP.md D40/D139): `bridge_tabs` (una coppia,
una posizione), `bridge_nested_tabs` (cammina la gerarchia, N linguette per
coppia, a qualunque profondità) e `bridge_parent_tabs` (linguette nei punti
scelti dal chiamante, il genitore spezzato una volta sola).
"""

import math
import unittest
from pathlib import Path
import sys

from shapely.geometry import Polygon

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo.core.primitives.segments import CircleSeg
from topo.model.contour import Contour
from topo.core.geometry.build import polygon as polygon_segments
from topo.tools.tabs import bridge_tabs, bridge_parent_tabs, bridge_nested_tabs, is_tab_island


def _circle_points(center, radius, n=200):
    cx, cy = center
    return [
        (cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


class TestBridgeTabs(unittest.TestCase):
    """Una coppia genitore/figlio, una sola posizione — la meccanica di base."""

    def setUp(self):
        self.center = (0.0, 0.0)
        self.parent_points = _circle_points(self.center, radius=9.0)
        self.child_points = _circle_points(self.center, radius=4.0)

    def test_001_tab_edges_span_the_radial_gap(self):
        # linguetta a destra (angolo 0): anchor esatti sui due cerchi
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        bridge = bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=1.0)
        self.assertEqual(len(bridge.tab_edges), 2)
        for edge in bridge.tab_edges:
            length = math.hypot(edge.end[0] - edge.start[0], edge.end[1] - edge.start[1])
            # il fianco e' leggermente piu' lungo del gap radiale puro (9-4=5)
            # perche' e' offsettato di tab_width/2 dal centro esatto — ma non di molto.
            self.assertAlmostEqual(length, 5.0, delta=0.05)

    def test_002_cuts_land_close_to_the_anchor(self):
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        bridge = bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=1.0)
        for cut_pt, _ in (bridge.child_cut_a, bridge.child_cut_b):
            self.assertAlmostEqual(math.hypot(*cut_pt), 4.0, delta=0.05)
        for cut_pt, _ in (bridge.parent_cut_a, bridge.parent_cut_b):
            self.assertAlmostEqual(math.hypot(*cut_pt), 9.0, delta=0.05)

    def test_003_too_wide_tab_raises(self):
        anchor_child = (4.0, 0.0)
        anchor_parent = (9.0, 0.0)
        with self.assertRaises(ValueError):
            bridge_tabs(self.parent_points, self.child_points, anchor_parent, anchor_child, tab_width=100.0)


def _make_contour(radius, depth, parent=None, center=(0.0, 0.0)):
    poly = Polygon(_circle_points(center, radius, n=64))
    return Contour(role="unknown", polygon=poly, segments=[CircleSeg(center=center, radius=radius)],
                         depth=depth, parent=parent)


class _FakeCluster:
    def __init__(self, outer, inners):
        self.outer = outer
        self.inners = inners


class TestBridgeNestedTabs(unittest.TestCase):
    """Cammina la gerarchia — a qualunque profondita', mai un livello saltato."""

    def test_001_single_pair_on_real_fixture(self):
        doc = topo_dxf.load_dxf(str(project_root / "tests/data/cerchi_concentrici_detect_is_counter_tabs_join.dxf"))
        result = topo.heal(doc)
        cluster = result.clusters[0]

        bridges = bridge_nested_tabs(cluster, tab_width=2.0, tab_count=4, discretize_tolerance=0.05)

        self.assertEqual(len(bridges), 1)
        bridge = bridges[0]
        self.assertEqual(bridge.child_contour.depth, 2)
        self.assertEqual(bridge.parent_contour.depth, 1)
        self.assertEqual(len(bridge.child_stretches), 4)
        self.assertEqual(len(bridge.parent_stretches), 4)
        self.assertEqual(len(bridge.tab_edges), 8)  # 2 fianchi x 4 linguette

    def test_002_four_level_chain_pairs_by_immediate_parent(self):
        # outer (depth0) -> figlio depth1 (vuoto) -> nipote depth2 (isola)
        # -> pronipote depth3 (vuoto) -> pro-pronipote depth4 (isola)
        outer = _make_contour(radius=20.0, depth=0)
        figlio = _make_contour(radius=15.0, depth=1, parent=outer)
        nipote = _make_contour(radius=10.0, depth=2, parent=figlio)
        pronipote = _make_contour(radius=6.0, depth=3, parent=nipote)
        pro_pronipote = _make_contour(radius=3.0, depth=4, parent=pronipote)

        cluster = _FakeCluster(outer=outer, inners=[figlio, nipote, pronipote, pro_pronipote])
        bridges = bridge_nested_tabs(cluster, tab_width=0.5, tab_count=4, discretize_tolerance=0.05)

        # solo le profondita' pari >= 2 generano un ponte, ognuna col SUO genitore diretto
        self.assertEqual(len(bridges), 2)
        pairs = {(b.child_contour.depth, b.parent_contour.depth) for b in bridges}
        self.assertEqual(pairs, {(2, 1), (4, 3)})


def _rect_contour(x0, y0, x1, y1, depth, parent=None):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return Contour(role="unknown", polygon=Polygon(pts), segments=polygon_segments(pts), depth=depth, parent=parent)


class TestBridgeParentTabs(unittest.TestCase):
    """Le isole di un genitore, linguette nei punti scelti dal chiamante (es. click a snap in una UI)."""

    def setUp(self):
        self.outer = _make_contour(radius=20.0, depth=0)
        self.parent = _make_contour(radius=9.0, depth=1, parent=self.outer)
        self.island = _make_contour(radius=4.0, depth=2, parent=self.parent)

    def test_001_one_tab_per_anchor(self):
        result = bridge_parent_tabs(self.parent, [(self.island, [(4.0, 0.0), (0.0, 4.0), (-4.0, 0.0)])], tab_width=1.0)
        self.assertIs(result.parent_contour, self.parent)
        self.assertEqual(len(result.islands), 1)
        self.assertIs(result.islands[0].contour, self.island)
        self.assertEqual(len(result.tab_edges), 6)  # 2 fianchi x 3 linguette
        self.assertEqual(len(result.islands[0].stretches), 3)
        self.assertEqual(len(result.parent_stretches), 3)
        self.assertEqual(result.failed, [])

    def test_002_anchor_on_parent_bridges_straight_to_the_island(self):
        # punto sul genitore, in alto: la linguetta scende radiale fino all'isola
        result = bridge_parent_tabs(self.parent, [(self.island, [(0.0, 9.0)])], tab_width=1.0)
        for edge in result.tab_edges:
            self.assertAlmostEqual(math.hypot(*edge.start), 4.0, delta=0.05)
            self.assertAlmostEqual(math.hypot(*edge.end), 9.0, delta=0.05)
            self.assertGreater(edge.start[1], 3.5)

    def test_003_not_an_island_of_parent_raises(self):
        self.assertFalse(is_tab_island(self.parent))
        with self.assertRaises(ValueError):
            bridge_parent_tabs(self.outer, [(self.parent, [(9.0, 0.0)])], tab_width=1.0)

    def test_004_no_anchor_raises(self):
        with self.assertRaises(ValueError):
            bridge_parent_tabs(self.parent, [(self.island, [])], tab_width=1.0)

    def test_005_anchor_on_a_straight_side_leaves_it_perpendicular(self):
        # isola quadrata in un genitore rettangolare largo: dal lato destro il
        # punto piu' vicino del genitore e' sopra/sotto, ma la linguetta deve
        # uscire a destra, perpendicolare al lato cliccato
        outer = _rect_contour(-10, -10, 210, 110, 0)
        parent = _rect_contour(10, 10, 190, 90, 1, outer)
        island = _rect_contour(30, 30, 70, 70, 2, parent)
        result = bridge_parent_tabs(parent, [(island, [(70.0, 50.0)])], tab_width=2.0)
        for edge in result.tab_edges:
            self.assertAlmostEqual(edge.start[0], 70.0, delta=1e-6)
            self.assertAlmostEqual(edge.end[0], 190.0, delta=1e-6)
            self.assertAlmostEqual(edge.start[1], edge.end[1], delta=1e-6)

    def test_006_two_islands_split_the_parent_once(self):
        # due isole sotto lo stesso genitore, una linguetta ciascuna verso il
        # basso: il genitore esce in 2 tratti (fra le due linguette), mai due
        # copie di se stesso spezzate ognuna per un'isola sola
        outer = _rect_contour(-10, -10, 210, 110, 0)
        parent = _rect_contour(10, 10, 190, 90, 1, outer)
        left = _rect_contour(30, 30, 70, 70, 2, parent)
        right = _rect_contour(120, 30, 160, 70, 2, parent)
        result = bridge_parent_tabs(parent, [(left, [(50.0, 30.0)]), (right, [(140.0, 30.0)])], tab_width=2.0)
        self.assertEqual(len(result.islands), 2)
        self.assertEqual(len(result.parent_stretches), 2)
        self.assertEqual(len(result.tab_edges), 4)
        self.assertEqual(result.failed, [])

    def test_007_island_that_cannot_be_bridged_goes_to_failed(self):
        # linguetta piu' larga dell'isola: quella non si collega, l'altra si'
        outer = _rect_contour(-10, -10, 210, 110, 0)
        parent = _rect_contour(10, 10, 190, 90, 1, outer)
        tiny = _rect_contour(30, 30, 31, 31, 2, parent)
        big = _rect_contour(120, 30, 160, 70, 2, parent)
        result = bridge_parent_tabs(parent, [(tiny, [(30.5, 30.0)]), (big, [(140.0, 30.0)])], tab_width=4.0)
        self.assertEqual([i.contour for i in result.islands], [big])
        self.assertEqual([c for c, _ in result.failed], [tiny])
        self.assertEqual(len(result.parent_stretches), 1)

    def test_008_single_tab_keeps_the_rest_of_both_contours(self):
        # una linguetta sola: isola e genitore escono in UN tratto ciascuno,
        # tutto il contorno tranne il pezzo sotto la linguetta
        result = bridge_parent_tabs(self.parent, [(self.island, [(4.0, 0.0)])], tab_width=1.0)
        self.assertEqual(len(result.islands[0].stretches), 1)
        self.assertEqual(len(result.parent_stretches), 1)
        island_len = sum(math.dist(a, b) for a, b in zip(result.islands[0].stretches[0], result.islands[0].stretches[0][1:]))
        self.assertAlmostEqual(island_len, 2 * math.pi * 4.0 - 1.0, delta=0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
