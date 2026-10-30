"""
test_simplify_points.py
------------------------
Test unitari per topo.core.primitives.fitting.simplify_points (MAP.md D141).

Le tre garanzie, su casi che vengono da un contorno tracciato (smoother D21):
  - ogni punto dato sta entro `tolerance` dalle primitive;
  - le primitive sono una catena testa-coda: un tratto aperto parte e
    finisce esattamente nei suoi estremi, un contorno chiuso si richiude;
  - linea dove è dritto, arco dove è a raggio costante, spigolo vivo dove
    svolta, anche se il campionamento ha smussato l'angolo.
"""

import math
import unittest

from shapely.geometry import LineString, Point as SPoint

from topo.core.primitives.segments import ArcSeg, CircleSeg, LineSeg, BSplineSeg, segment_endpoints
from topo.core.primitives.fitting import simplify_points


def _side(a, b, n):
    """`n` punti da `a` verso `b`, `b` escluso."""
    return [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n)]


def _rounded_square(size=10.0, n=20):
    """Quadrato campionato come da un raster: il vertice manca, l'angolo è smussato su due campioni."""
    corners = [(0, 0), (size, 0), (size, size), (0, size)]
    pts = []
    for k in range(4):
        pts += _side(corners[k], corners[(k + 1) % 4], n)[1:]
    return pts


def _max_distance(primitives, points):
    line = LineString([q for s in primitives for q in s.discretize(tolerance=1e-4)])
    return max(line.distance(SPoint(p)) for p in points)


def _is_chain(primitives, closed):
    ends = [segment_endpoints(s) for s in primitives]
    links = list(zip(ends, ends[1:] + (ends[:1] if closed else [])))
    return all(math.dist(a[1], b[0]) < 1e-9 for a, b in links)


class TestGuarantees(unittest.TestCase):

    def test_001_rounded_square_four_lines_sharp_corners(self):
        pts = _rounded_square()
        out = simplify_points(pts, tolerance=0.1, scale=2.0)
        self.assertEqual([type(s) for s in out], [LineSeg] * 4)
        self.assertTrue(_is_chain(out, closed=True))
        # lo spigolo torna vivo: nell'incrocio dei due lati, non sul campione
        vertices = sorted((round(s.start[0], 6), round(s.start[1], 6)) for s in out)
        self.assertEqual(vertices, [(0, 0), (0, 10), (10, 0), (10, 10)])

    def test_002_circle_is_one_circle(self):
        pts = [(5 + 10 * math.cos(2 * math.pi * i / 90), 10 * math.sin(2 * math.pi * i / 90)) for i in range(90)]
        out = simplify_points(pts, tolerance=0.01, scale=2.0)
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], CircleSeg)
        self.assertAlmostEqual(out[0].radius, 10.0, places=6)

    def test_003_stadium_lines_and_arcs_chained(self):
        # due lati dritti e due semicerchi, raccordati senza spigolo
        pts = _side((0, 0), (20, 0), 40)
        pts += [(20 + 5 * math.sin(math.pi * i / 30), 5 - 5 * math.cos(math.pi * i / 30)) for i in range(30)]
        pts += _side((20, 10), (0, 10), 40)
        pts += [(-5 * math.sin(math.pi * i / 30), 5 + 5 * math.cos(math.pi * i / 30)) for i in range(30)]
        out = simplify_points(pts, tolerance=0.01, scale=2.0)
        self.assertEqual(sorted(type(s).__name__ for s in out), ["ArcSeg", "ArcSeg", "LineSeg", "LineSeg"])
        self.assertTrue(_is_chain(out, closed=True))
        self.assertLessEqual(_max_distance(out, pts), 0.01 + 1e-6)

    def test_004_open_stretch_keeps_its_ends(self):
        # un tratto aperto fra due tagli: linea e poi quarto d'arco
        pts = _side((0, 0), (10, 0), 20) + [(10 + 5 * math.sin(a), 5 - 5 * math.cos(a))
                                           for a in (math.pi / 2 * i / 20 for i in range(21))]
        out = simplify_points(pts, tolerance=0.01, scale=2.0, closed=False)
        # un arco ricava i capi dagli angoli: esatti a meno della virgola mobile
        self.assertLess(math.dist(segment_endpoints(out[0])[0], pts[0]), 1e-9)
        self.assertLess(math.dist(segment_endpoints(out[-1])[1], pts[-1]), 1e-9)
        self.assertTrue(_is_chain(out, closed=False))
        self.assertEqual([type(s) for s in out], [LineSeg, ArcSeg])

    def test_005_noisy_free_curve_is_a_spline_within_tolerance(self):
        pts = [(x / 10, math.sin(x / 20) * 3 + 0.03 * math.sin(x * 1.7)) for x in range(200)]
        out = simplify_points(pts, tolerance=0.1, scale=2.0, closed=False, arcs=False)
        self.assertTrue(all(isinstance(s, (BSplineSeg, LineSeg)) for s in out))
        self.assertTrue(_is_chain(out, closed=False))
        self.assertLessEqual(_max_distance(out, pts), 0.1 + 1e-6)
        spline = next(s for s in out if isinstance(s, BSplineSeg))
        self.assertLess(len(spline.control_points), 40)   # non interpola tutti i 200 punti

    def test_006_without_arcs_no_arc(self):
        pts = [(10 * math.cos(2 * math.pi * i / 90), 10 * math.sin(2 * math.pi * i / 90)) for i in range(90)]
        out = simplify_points(pts, tolerance=0.01, scale=2.0, arcs=False)
        self.assertFalse(any(isinstance(s, (ArcSeg, CircleSeg)) for s in out))
        self.assertTrue(_is_chain(out, closed=True))

    def test_007_lower_turn_more_corners(self):
        # ottagono: svolta di 45° a ogni vertice
        pts = []
        verts = [(10 * math.cos(math.pi / 4 * k), 10 * math.sin(math.pi / 4 * k)) for k in range(8)]
        for k in range(8):
            pts += _side(verts[k], verts[(k + 1) % 8], 15)
        self.assertEqual(len(simplify_points(pts, tolerance=0.05, scale=1.0, corner_turn_deg=40)), 8)
        self.assertTrue(all(isinstance(s, LineSeg) for s in simplify_points(pts, tolerance=0.05, scale=1.0,
                                                                             corner_turn_deg=40)))

    def test_008_degenerate_inputs(self):
        self.assertEqual(simplify_points([], tolerance=0.1, scale=1.0), [])
        self.assertEqual(simplify_points([(0, 0), (0, 0)], tolerance=0.1, scale=1.0), [])
        out = simplify_points([(0, 0), (3, 4)], tolerance=0.1, scale=1.0, closed=False)
        self.assertEqual(out, [LineSeg(start=(0.0, 0.0), end=(3.0, 4.0))])


if __name__ == "__main__":
    unittest.main(verbosity=2)
