# tests/engine/readings/test_parity_faces.py

"""The parity reading, `topo.experimental.parity_faces`: what is guaranteed (all
nodes even: a single reading), what is chosen (odd nodes: the minimum), and the
declared limit (in ties it depends on the frame)."""

import unittest

import topo
import topo_dxf
from topo import to_shapely
from topo.core.primitives import LineSeg

from tests.invariants import MOTIONS, message_problems, moved, shape_differences
from tests.paths import DATA

TOL = 0.01


def _lines(*points, closed: bool = False) -> list:
    pts = list(points) + ([points[0]] if closed else [])
    return [LineSeg(start=a, end=b) for a, b in zip(pts, pts[1:])]


def _read(segments: list):
    return topo.experimental.parity_faces(topo.heal(topo.load_segments(segments)))


class TestEvenNodes(unittest.TestCase):
    """Every node even: every line is contour, and the reading is a single one."""

    def test_rectangle_touching_the_border_is_an_inner(self):
        # an inner rectangle with a side on the part's border, touched at a point
        result = _read(_lines((0, 0), (100, 0), (100, 60), (0, 60), closed=True)
                       + _lines((50, 0), (80, 20), (50, 40), (20, 20), closed=True))
        self.assertTrue(result.is_valid)
        self.assertEqual(result.reading, "parity")
        self.assertEqual([len(c.inners) for c in result.clusters], [1])
        self.assertEqual(result.loose, [])
        self.assertEqual(message_problems(result), [])


class TestOddNodes(unittest.TestCase):
    """Odd nodes: free ends and bridges away, then the least silhouette, then the shortest."""

    def test_diagonals_away_the_square_remains(self):
        # the 8 corners have degree 3; the rectangle's sides are silhouette: the
        # shortest set that makes every node even is the 4 diagonals
        result = _read(_lines((0, 0), (260, 0), (260, 150), (0, 150), closed=True)
                       + _lines((95, 47), (165, 47), (165, 103), (95, 103), closed=True)
                       + _lines((0, 0), (95, 47)) + _lines((260, 0), (165, 47))
                       + _lines((0, 150), (95, 103)) + _lines((260, 150), (165, 103)))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].area, 260 * 150 - 70 * 56)
        self.assertEqual(len(result.loose), 4)
        self.assertEqual(message_problems(result), [])

    def test_crossing_sides_it_cuts_them(self):
        # a side overshoots the corner: the crossing is cut and the tail is a free end
        result = _read([LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, 50.1)),
                        LineSeg((100.1, 50), (0, 50)), LineSeg((0, 50), (0, 0))])
        self.assertTrue(result.is_valid)
        self.assertAlmostEqual(to_shapely(result.clusters[0].outer).area, 100 * 50)
        self.assertIn("crossing", [w.code for w in result.warnings])

    def test_non_structural_role_does_not_enter(self):
        # a line with a decided non-structural role does not count in the degrees
        doc = topo.load_segments(_lines((0, 0), (100, 0), (100, 60), (0, 60), closed=True))
        doc.edges.append(doc.edges[0].__class__(role="engrave", start=(50, 0), end=(50, 60),
                                                segment=LineSeg((50, 0), (50, 60))))
        result = topo.experimental.parity_faces(topo.heal(doc))
        self.assertEqual(result.cluster_count, 1)
        self.assertAlmostEqual(result.clusters[0].area, 100 * 60)


class TestDeclaredLimit(unittest.TestCase):
    """The declared limit: where two sets to remove have the same length, which one
    is removed depends on the coordinates. The slot with the cross of Multifeature,
    mirrored, reads with the other two wedges. If one day the reading becomes
    invariant, this test falls: it is changed on purpose, with the decision that says so."""

    def test_multifeature_mirrored_changes_the_holes(self):
        doc = topo_dxf.load_dxf(str(DATA / "Multifeature.dxf"))
        name, move, back, _ = [m for m in MOTIONS if m[0] == "mirror"][0]
        inners = [to_shapely(i) for c in topo.experimental.parity_faces(topo.heal(doc)).clusters
                  for i in c.inners]
        again = [back(to_shapely(i)) for c in topo.experimental.parity_faces(topo.heal(moved(doc, move))).clusters
                 for i in c.inners]
        self.assertNotEqual(shape_differences(inners, again, 2 * TOL), [])


if __name__ == "__main__":
    unittest.main()
