"""
tests/real/test_fidelity.py
---------------------------
La promessa "fedele" della 1.0 (D143), su ogni disegno tracciato: il
risultato scritto in DXF e riletto si sovrappone al sorgente.

1. Hausdorff nei due versi ≤ il limite della lettura: la tolleranza dei nodi
   per `heal()`, `max_gap` per `island()` (l'unica cosa che sposta geometria
   in una vista sono le chiusure dei gap).
2. Coefficienti identici (centro e raggio, ellisse, punti di controllo) per
   ogni curva che la lettura non ha toccato: entrambi i capi coincidono con
   quelli di un altro edge del sorgente e la curva non ha un doppione quasi
   coincidente. Un capo che non tocca niente può essere stato chiuso entro la
   tolleranza, e allora l'arco riletto da un bulge ha centro e raggio
   ricalcolati; un doppione viene fuso. Lì vale solo il punto 1.

Ogni disegno con la sua lettura (D152): quelli di `golden_islands/` e
`golden_anchoring/` sono fogli di viste e si leggono con `island()`, gli
altri con `heal()`. Le copie identiche si misurano una volta.
"""

import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np
from shapely import STRtree, points
from shapely.geometry import LineString

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo.core.primitives.segments import segment_endpoints
from tests.drawings import case_name, tracked_drawings
from tests.readings import island_reading

MAX_GAP = 0.5            # quello di snapdraw, come test_golden_islands
SAMPLE_TOL = 0.01        # passo della discretizzazione su cui si misura
COEFF_EPS = 1e-9         # "identico" in virgola mobile
DUPLICATE_EPS = 0.05     # due curve così vicine sono un doppione da fondere
CUT_EPS = 2e-6           # un pezzo tagliato sta sulla sua spline (taglio esatto)
CUT_SAMPLE = 1e-6        # errore di corda nel confronto, sotto CUT_EPS
CUT_GAP = 0.02           # un tratto più corto resta dentro la fascia del bordo (2·GRAPH_EPSILON)


def _lines_and_samples(edges):
    lines, samples = [], []
    for e in edges:
        pts = e.segment.discretize(SAMPLE_TOL) if e.segment is not None else [e.start, e.end]
        if len(pts) >= 2 and LineString(pts).length > 0:
            lines.append(LineString(pts))
        samples += pts
    return lines, samples


def _directed(samples, lines) -> float:
    """Massima distanza di un punto di `samples` dalle linee di `lines`."""
    if not samples:
        return 0.0
    if not lines:
        return float("inf")
    _, d = STRtree(lines).query_nearest(points(np.array(samples)), return_distance=True,
                                        all_matches=False)
    return float(d.max())


def _coefficients(seg):
    """Quello che nessun passo di una lettura cambia su una curva che non tocca."""
    if isinstance(seg, (topo.primitives.ArcSeg, topo.primitives.CircleSeg)):
        return ("circle", (seg.center[0], seg.center[1], seg.radius))
    if isinstance(seg, topo.primitives.EllipseSeg):
        return ("ellipse", (seg.center[0], seg.center[1], seg.major_axis[0],
                            seg.major_axis[1], seg.ratio))
    if isinstance(seg, topo.primitives.BSplineSeg):
        return ("spline", (seg.degree, tuple(map(tuple, seg.control_points))))
    return None


def _same(a, b, eps) -> bool:
    if a[0] != b[0]:
        return False
    if a[0] != "spline":
        return all(abs(x - y) <= eps for x, y in zip(a[1], b[1]))
    (deg_a, pts_a), (deg_b, pts_b) = a[1], b[1]
    close = lambda P, Q: len(P) == len(Q) and all(
        abs(p[0] - q[0]) <= eps and abs(p[1] - q[1]) <= eps for p, q in zip(P, Q))
    # una spline percorsa al contrario ha i punti di controllo invertiti
    return deg_a == deg_b and (close(pts_a, pts_b) or close(pts_a, pts_b[::-1]))


def _untouched_curves(edges) -> list:
    """Coefficienti delle curve che una lettura non ha motivo di toccare."""
    def ends(seg):
        try:
            p, q = segment_endpoints(seg)
        except (TypeError, ValueError):
            return None
        return None if p == q else (p, q)

    shared = Counter()
    for e in edges:
        p = ends(e.segment)
        for q in p or ():
            shared[(round(q[0], 9), round(q[1], 9))] += 1
    coeffs = [_coefficients(e.segment) for e in edges]
    out = []
    for e, c in zip(edges, coeffs):
        if c is None:
            continue
        p = ends(e.segment)
        if p and any(shared[(round(q[0], 9), round(q[1], 9))] < 2 for q in p):
            continue
        if c[0] != "spline" and sum(1 for o in coeffs if o and _same(o, c, DUPLICATE_EPS)) > 1:
            continue
        out.append(c)
    return out


def _cut_in_pieces(coeffs, source_edges, written_edges) -> bool:
    """Vero se la spline `coeffs` del sorgente esce tagliata, non rifittata:
    in pezzi che stanno su di lei entro CUT_EPS e la coprono tutta, a
    meno di CUT_GAP. Una
    lettura la taglia dove un bordo la lascia a metà (G6b: il resto va in
    `loose`, la parte sul bordo nel contorno)."""
    if coeffs[0] != "spline":
        return False
    source = next(e.segment for e in source_edges if _coefficients(e.segment) == coeffs)
    line = LineString(source.discretize(CUT_SAMPLE))
    zone = line.buffer(CUT_EPS)
    on = [LineString(pts) for e in written_edges
          if isinstance(e.segment, topo.primitives.BSplineSeg)
          and len(pts := e.segment.discretize(CUT_SAMPLE)) >= 2 and zone.covers(LineString(pts))]
    return len(on) >= 2 and line.length - sum(g.length for g in on) <= CUT_GAP


def _round_trip(rel: str, reading: str):
    path = project_root / rel
    if reading == "island":
        doc, result = island_reading(path, MAX_GAP)
        bound = MAX_GAP
    else:
        doc = topo_dxf.load_dxf(str(path))
        result = topo.heal(doc)
        bound = doc.node_tolerance()
    drawing = topo_dxf.to_dxf(result, doc, include_texts=False)
    # skip_layers=(): il layer di `loose` si rilegge, è parte del risultato
    back = topo_dxf.document_from_msp(drawing.modelspace(), skip_layers=())
    return doc, back, bound


class TestFidelity(unittest.TestCase):
    """Un test per disegno tracciato, così la suite li divide fra i core
    (D160): in un test solo, il ciclo su tutti i disegni era il più lento
    della suite e non si poteva dividere."""

    def test_il_confronto_dei_coefficienti_non_e_vuoto(self):
        # la regola "non toccata" non deve escludere quasi tutto
        compared = sum(len(_untouched_curves(topo_dxf.load_dxf(str(project_root / rel)).edges))
                       for rel, _ in tracked_drawings())
        self.assertGreater(compared, 1000)


def _make_fidelity_test(rel: str, reading: str):
    def test(self):
        doc, back, bound = _round_trip(rel, reading)
        src_lines, src_samples = _lines_and_samples(doc.edges)
        out_lines, out_samples = _lines_and_samples(back.edges)
        self.assertLessEqual(_directed(src_samples, out_lines), bound,
                             "un punto del sorgente non è nel risultato")
        self.assertLessEqual(_directed(out_samples, src_lines), bound,
                             "un punto del risultato non è nel sorgente")
        written = [c for c in map(_coefficients, (e.segment for e in back.edges)) if c]
        missing = [c for c in _untouched_curves(doc.edges)
                   if not any(_same(c, w, COEFF_EPS) for w in written)]
        missing = [c for c in missing if not _cut_in_pieces(c, doc.edges, back.edges)]
        self.assertEqual(missing, [], "curve non toccate riscritte con altri coefficienti")
    return test


for _rel, _reading in tracked_drawings():
    setattr(TestFidelity, f"{case_name(project_root / _rel)}_{_reading}", _make_fidelity_test(_rel, _reading))


if __name__ == "__main__":
    unittest.main()
