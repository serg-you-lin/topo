"""
test_strips.py
--------------
Test unitari per topo.tools.strips e topo.core.geometry.strips (MAP.md D134,
D142): i bordi affacciati, la distanza fra due bordi, la striscia (anche fra
due regioni sorelle, rifiutata se attraversa qualcosa), le regioni non
collegate, i bordi aperti dove passano le strisce.
"""

import math
import unittest
from pathlib import Path

import topo
import topo_dxf
from topo.core.geometry import circle, rectangle
from topo.core.primitives.segments import ArcSeg, LineSeg
from topo.tools.strips import facing_boundaries, gap, link, open_boundaries, unconnected_regions
from topo import to_shapely

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "cerchi_concentrici_detect_is_counter_tabs_join.dxf"


def _cluster(*shapes):
    doc = topo.load_segments([s for shape in shapes for s in shape])
    return topo.heal(doc).clusters[0]


def _window_with_two_discs():
    """Riquadro 200×120 con una finestra 160×80; dentro, due dischi r=10 a 20 l'uno dall'altro."""
    cluster = _cluster(rectangle(200, 120, center=(100, 60)), rectangle(160, 80, center=(100, 60)),
                       circle(10, center=(60, 60)), circle(10, center=(100, 60)))
    facing = facing_boundaries(cluster)[0]
    left, right = sorted(facing.inside, key=lambda c: to_shapely(c).centroid.x)
    return cluster, facing, left, right


def _heal_opened(cluster, links):
    """Il cluster ricostruito coi bordi aperti e i fianchi: deve richiudersi."""
    opened = open_boundaries(links)
    touched = {id(c) for c, _ in opened.boundaries}
    segments = [s for c in (cluster.outer, *cluster.inners) if id(c) not in touched for s in c.segments]
    segments += [s for _, chains in opened.boundaries for chain in chains for s in chain] + opened.sides
    doc = topo.load_segments(segments)
    return topo.heal(doc)


class TestFacingBoundaries(unittest.TestCase):

    def test_001_window_faces_the_two_discs(self):
        cluster, facing, left, right = _window_with_two_discs()
        self.assertEqual(len(facing_boundaries(cluster)), 1)
        self.assertEqual(facing.region.depth, 1)
        self.assertEqual({c.depth for c in facing.inside}, {2})
        self.assertEqual(facing.boundaries, [facing.region, *facing.inside])

    def test_002_cousins_never_face_each_other(self):
        # due finestre, un disco in ognuna: due gruppi, ognuno col suo disco
        cluster = _cluster(rectangle(200, 100, center=(100, 50)),
                           rectangle(60, 60, center=(50, 50)), circle(10, center=(50, 50)),
                           rectangle(60, 60, center=(150, 50)), circle(10, center=(150, 50)))
        groups = facing_boundaries(cluster)
        self.assertEqual(len(groups), 2)
        for g in groups:
            self.assertEqual(len(g.inside), 1)
            self.assertTrue(to_shapely(g.region).contains(to_shapely(g.inside[0])))

    def test_003_nested_four_levels_pair_by_direct_parent(self):
        cluster = _cluster(circle(20), circle(15), circle(10), circle(6), circle(3))
        pairs = sorted((g.region.depth, [c.depth for c in g.inside]) for g in facing_boundaries(cluster))
        self.assertEqual(pairs, [(1, [2]), (3, [4])])


class TestGap(unittest.TestCase):

    def test_001_two_discs(self):
        _, _, left, right = _window_with_two_discs()
        g = gap(left, right)
        self.assertAlmostEqual(g.distance, 20.0, places=9)
        self.assertAlmostEqual(g.on_a[0], 70.0, places=6)
        self.assertAlmostEqual(g.on_b[0], 90.0, places=6)

    def test_002_disc_and_window(self):
        _, facing, left, _ = _window_with_two_discs()
        g = gap(facing.region, left)
        # finestra x 20..180, y 20..100; disco in (60, 60) r=10: 30 dal lato sinistro, da sopra e da sotto
        self.assertAlmostEqual(g.distance, 30.0, places=9)
        self.assertAlmostEqual(math.dist(g.on_b, (60, 60)), 10.0, places=9)


class TestLink(unittest.TestCase):

    def test_001_between_two_sisters(self):
        _, facing, left, right = _window_with_two_discs()
        s = link(facing, left, right, (80, 60), 4.0).strip
        for p in s.a_cuts:
            self.assertAlmostEqual(math.dist(p, (60, 60)), 10.0, places=9)
        for p in s.b_cuts:
            self.assertAlmostEqual(math.dist(p, (100, 60)), 10.0, places=9)
        self.assertEqual(sorted(round(p[1], 9) for p in s.a_cuts), [58.0, 62.0])
        for side in s.sides:
            self.assertAlmostEqual(side.start[1], side.end[1], places=9)   # orizzontali: perpendicolari ai due cerchi

    def test_002_from_a_straight_side_it_leaves_perpendicular(self):
        cluster = _cluster(rectangle(100, 100, center=(50, 50)), rectangle(80, 80, center=(50, 50)), rectangle(20, 40, center=(50, 50)))
        facing = facing_boundaries(cluster)[0]
        island = facing.inside[0]
        s = link(facing, facing.region, island, (60, 45), 2.0).strip   # sul lato destro dell'isola
        for side in s.sides:
            self.assertAlmostEqual(side.start[1], side.end[1], places=9)
        self.assertEqual(sorted(round(p[1], 9) for p in s.b_cuts), [44.0, 46.0])

    def test_003_refused_across_a_third_boundary(self):
        _, facing, left, _ = _window_with_two_discs()
        with self.assertRaisesRegex(ValueError, "attraversa"):
            link(facing, facing.region, left, (180, 60), 4.0)   # dalla destra, passa attraverso l'altro disco

    def test_004_refused_when_too_wide(self):
        _, facing, left, right = _window_with_two_discs()
        with self.assertRaisesRegex(ValueError, "non incontra"):
            link(facing, left, right, (80, 60), 30.0)

    def test_005_refused_over_a_placed_strip(self):
        _, facing, left, right = _window_with_two_discs()
        first = link(facing, left, right, (80, 60), 4.0)
        with self.assertRaises(ValueError):
            link(facing, left, right, (80, 61), 4.0, placed=[first])

    def test_006_boundaries_outside_the_facing_raise(self):
        cluster, facing, left, _ = _window_with_two_discs()
        with self.assertRaises(ValueError):
            link(facing, cluster.outer, left, (10, 60), 2.0)
        with self.assertRaises(ValueError):
            link(facing, left, left, (50, 60), 2.0)


class TestUnconnectedRegions(unittest.TestCase):

    def test_001_a_chain_through_a_sister_connects_both(self):
        cluster, facing, left, right = _window_with_two_discs()
        self.assertEqual(len(unconnected_regions(cluster, [])), 2)
        sisters = link(facing, left, right, (80, 60), 4.0)
        self.assertEqual(len(unconnected_regions(cluster, [sisters])), 2)   # unite fra loro, non al bordo
        edge = link(facing, facing.region, left, (20, 60), 4.0, placed=[sisters])
        self.assertEqual(unconnected_regions(cluster, [sisters, edge]), [])

    def test_002_nested_regions_through_each_level(self):
        cluster = _cluster(circle(20), circle(15), circle(10), circle(6), circle(3))
        groups = sorted(facing_boundaries(cluster), key=lambda g: g.region.depth)
        inner = link(groups[1], groups[1].region, groups[1].inside[0], (3, 0), 1.0)
        self.assertEqual(len(unconnected_regions(cluster, [inner])), 2)   # il 4 è unito al 2, il 2 a niente
        outer = link(groups[0], groups[0].region, groups[0].inside[0], (0, 10), 1.0)
        self.assertEqual(unconnected_regions(cluster, [inner, outer]), [])


class TestOpenBoundaries(unittest.TestCase):

    def test_001_one_strip_keeps_the_rest_of_both_boundaries(self):
        cluster, facing, left, right = _window_with_two_discs()
        opened = open_boundaries([link(facing, left, right, (80, 60), 4.0)])
        self.assertEqual(len(opened.sides), 2)
        for contour, chains in opened.boundaries:
            self.assertEqual(len(chains), 1)
            self.assertEqual([type(s) for s in chains[0]], [ArcSeg])   # un cerchio tagliato è un arco
            self.assertGreater(chains[0][0]._sweep(), math.pi)          # il tratto lungo, non quello sotto

    def test_002_reclosed_on_the_fixture(self):
        cluster = topo.heal(topo_dxf.load_dxf(str(FIXTURE))).clusters[0]
        facing = facing_boundaries(cluster)[0]
        disc = facing.inside[0]
        c, r = to_shapely(disc).centroid, math.sqrt(to_shapely(disc).area / math.pi)
        links = []
        for k in range(4):
            at = (c.x + r * math.cos(k * math.pi / 2), c.y + r * math.sin(k * math.pi / 2))
            links.append(link(facing, facing.region, disc, at, 2.0, placed=links))
        opened = open_boundaries(links)
        self.assertEqual(sorted(len(chains) for _, chains in opened.boundaries), [4, 4])
        self.assertEqual(len(opened.sides), 8)
        healed = _heal_opened(cluster, links)
        self.assertTrue(healed.is_valid)
        self.assertEqual(len(healed.clusters), 1)
        self.assertEqual(len(healed.clusters[0].inners), 4)   # quattro spicchi vuoti, il disco è unito al resto

    def test_003_sisters_and_window_reclose(self):
        cluster, facing, left, right = _window_with_two_discs()
        sisters = link(facing, left, right, (80, 60), 4.0)
        edge = link(facing, facing.region, left, (20, 60), 4.0, placed=[sisters])
        healed = _heal_opened(cluster, [sisters, edge])
        self.assertTrue(healed.is_valid)
        self.assertEqual([c.depth for c in healed.clusters[0].inners], [1])

    def test_004_overlapping_strips_on_a_boundary_raise(self):
        _, facing, left, right = _window_with_two_discs()
        a = link(facing, left, right, (80, 60), 4.0)
        b = link(facing, left, right, (80, 61), 4.0)   # senza `placed`: nessuno l'ha rifiutata
        with self.assertRaises(ValueError):
            open_boundaries([a, b])

    def test_005_untouched_boundaries_are_absent(self):
        _, facing, left, right = _window_with_two_discs()
        opened = open_boundaries([link(facing, left, right, (80, 60), 4.0)])
        self.assertEqual({id(c) for c, _ in opened.boundaries}, {id(left), id(right)})
        self.assertTrue(all(isinstance(s, LineSeg) for s in opened.sides))


if __name__ == "__main__":
    unittest.main(verbosity=2)
