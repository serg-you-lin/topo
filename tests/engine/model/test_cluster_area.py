"""
tests/engine/model/test_cluster_area.py
-------------------------------
`Cluster.area` on nested contours: odd depth is void, even depth is material,
the signs alternate with the level.
"""

import math
import unittest

import topo

# circles become polygons: ~1.3 mm² of difference at r=30
DELTA = 3.0


def _nested_circles(*radii):
    """100x100 square with concentric circles at the centre, from the largest."""
    square = [((0, 0), (100, 0)), ((100, 0), (100, 100)),
              ((100, 100), (0, 100)), ((0, 100), (0, 0))]
    entities = [{"type": "line", "start": a, "end": b} for a, b in square]
    entities += [{"type": "circle", "center": (50, 50), "radius": r} for r in radii]
    return topo.heal(topo.load_geometry(entities)).faces()


class TestClusterAreaNested(unittest.TestCase):

    def test_001_one_level_is_removed(self):
        # a single void: the area is outer minus the void
        cluster = _nested_circles(30).clusters[0]
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * 900, delta=DELTA)

    def test_002_island_in_a_void_is_added_back(self):
        # circle inside circle: the smaller is material in the void, not a second void
        # subtracted twice
        cluster = _nested_circles(30, 10).clusters[0]
        self.assertEqual(sorted(i.depth for i in cluster.inners), [1, 2])
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * (900 - 100), delta=DELTA)

    def test_003_signs_alternate_with_depth(self):
        cluster = _nested_circles(30, 10, 3).clusters[0]
        self.assertEqual(sorted(i.depth for i in cluster.inners), [1, 2, 3])
        self.assertAlmostEqual(cluster.area, 10000 - math.pi * (900 - 100 + 9), delta=DELTA)


if __name__ == "__main__":
    unittest.main()
