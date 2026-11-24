"""
tests/promises/test_fidelity.py
---------------------------
The "faithful" promise of 1.0, on every tracked drawing: the result written to
DXF and re-read overlaps the source.

1. Hausdorff in both directions ≤ the reading's limit: the node tolerance for
   `heal()`, `max_gap` for `outlines()` (the only thing that moves geometry in
   a view is the gap closures).
2. Identical coefficients (centre and radius, ellipse, control points) for
   every curve the reading did not touch — taken after `refit_native_curves`:
   a spline that is an arc or an ellipse comes out as that: both ends coincide
   with those of another edge of the source and the curve has no nearly
   coincident duplicate. An end touching nothing may have been closed within the
   tolerance, and then the arc re-read from a bulge has centre and radius
   recomputed; a duplicate is merged. There only point 1 holds.

3. Exact closed contours: no jump between a segment and the next beyond
   FLOAT_NOISE, in any reading: a jump within the tolerance is closed by the
   engine with a new segment.

Each drawing with its reading: those of `golden_outlines/` and
`golden_anchoring/` are sheets of views and are read with `outlines()`, the
others with `heal()`. Identical copies are measured once.
"""

import unittest
from collections import Counter

import numpy as np
from shapely import STRtree, points
from shapely.geometry import LineString, box


import topo
import topo_dxf
from topo.core.base.refit import refit_native_curves
from topo.core.primitives.mathseg import segment_endpoints
from tests.drawings import case_name, tracked_drawings
from tests.invariants import contour_jumps
from tests.readings import outline_reading
from tests.paths import PROJECT_ROOT

MAX_GAP = 0.5            # snapdraw's, like test_golden_outlines
# step of the discretization on which it is measured, as a fraction of the
# limit: the measure is wrong by at most one step (a tenth of the limit) at every
# tolerance. The check stays `<= limit`: a closed gap exactly as wide as the
# tolerance moves an end by the whole limit, and it is not a defect
SAMPLE_RATIO = 0.1
SPLINE_BOX = 0.01        # margin of the rectangles of the written splines (_written_splines)
COEFF_EPS = 1e-9         # "identical" in floating point

DUPLICATE_EPS = 0.05     # two curves this close are a duplicate to merge
CUT_EPS = 2e-6           # a cut piece lies on its spline (exact cut)
CUT_SAMPLE = 1e-6        # chord error in the comparison, below CUT_EPS
CUT_GAP = 0.02           # a shorter stretch stays inside the border band (2·GRAPH_EPSILON)



def _lines_and_samples(edges, step: float):
    lines, samples = [], []
    for e in edges:
        pts = e.segment.discretize(tolerance=step) if e.segment is not None else [e.start, e.end]
        if len(pts) >= 2 and LineString(pts).length > 0:
            lines.append(LineString(pts))
        samples += pts
    return lines, samples


def _directed(samples, lines) -> float:
    """Maximum distance of a point of `samples` from the lines of `lines`."""
    if not samples:
        return 0.0
    if not lines:
        return float("inf")
    _, d = STRtree(lines).query_nearest(points(np.array(samples)), return_distance=True,
                                        all_matches=False)
    return float(d.max())


def _coefficients(seg):
    """What no step of a reading changes on a curve it does not touch."""
    if isinstance(seg, topo.primitives.CircleSeg):
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
    # a spline walked backwards has the control points reversed
    return deg_a == deg_b and (close(pts_a, pts_b) or close(pts_a, pts_b[::-1]))


def _untouched_curves(edges) -> list:
    """Coefficients of the curves a reading has no reason to touch."""
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


def _written_splines(written_edges):
    """(spline, index on their rectangles) of the written splines: the fine
    discretization is done only for those near a curve."""
    splines = [e.segment for e in written_edges if isinstance(e.segment, topo.primitives.BSplineSeg)]
    boxes = [box(*LineString(s.discretize(tolerance=SPLINE_BOX)).buffer(SPLINE_BOX).bounds) for s in splines]
    return splines, STRtree(boxes)


def _cut_in_pieces(coeffs, source_edges, written) -> bool:
    """True if the source's spline `coeffs` comes out cut, not refitted: in pieces
    lying on it within CUT_EPS and covering it all, up to CUT_GAP. A reading cuts
    it where a border leaves it in the middle (the rest goes in `loose`, the part
    on the border in the contour)."""
    if coeffs[0] != "spline":
        return False
    source = next(e.segment for e in source_edges if _coefficients(e.segment) == coeffs)
    line = LineString(source.discretize(tolerance=CUT_SAMPLE))
    zone = line.buffer(CUT_EPS)
    splines, tree = written
    near = (splines[k].discretize(tolerance=CUT_SAMPLE) for k in sorted(tree.query(zone)))
    on = [g for pts in near if len(pts) >= 2 and zone.covers(g := LineString(pts))]
    return len(on) >= 2 and line.length - sum(g.length for g in on) <= CUT_GAP


def _round_trip(rel: str, reading: str):
    path = PROJECT_ROOT / rel
    if reading == "outlines":
        doc, result = outline_reading(path, MAX_GAP)
        bound = MAX_GAP
    else:
        doc = topo_dxf.load_dxf(str(path))
        result = topo.heal(doc).faces()
        bound = topo.precision.SAME_POINT
    drawing = topo_dxf.to_dxf(result, include_texts=False)
    # the `loose` layer is re-read (default): it is part of the result
    back = topo_dxf.document_from_msp(drawing.modelspace())
    return doc, result, back, bound


class TestFidelity(unittest.TestCase):
    """One test per tracked drawing, so the suite divides them among the cores: in a
    single test, the loop over all the drawings was the slowest of the suite and
    could not be divided."""

    def test_the_coefficient_comparison_is_not_empty(self):
        # the "untouched" rule must not exclude almost everything
        compared = sum(len(_untouched_curves(topo_dxf.load_dxf(str(PROJECT_ROOT / rel)).edges))
                       for rel, _ in tracked_drawings())
        self.assertGreater(compared, 1000)


def _make_fidelity_test(rel: str, reading: str):
    def test(self):
        doc, result, back, bound = _round_trip(rel, reading)
        self.assertEqual(contour_jumps(result), [], "leaps in the delivered contours")
        step = SAMPLE_RATIO * bound
        src_lines, src_samples = _lines_and_samples(doc.edges, step)
        out_lines, out_samples = _lines_and_samples(back.edges, step)
        self.assertLessEqual(_directed(src_samples, out_lines), bound,
                             "a source point is not in the result")
        self.assertLessEqual(_directed(out_samples, src_lines), bound,
                             "a result point is not in the source")
        written = [c for c in map(_coefficients, (e.segment for e in back.edges)) if c]
        # a curve of the file that is a simpler primitive comes out as that
        source = refit_native_curves(doc.edges)
        missing = [c for c in _untouched_curves(source)
                   if not any(_same(c, w, COEFF_EPS) for w in written)]
        if missing:
            written_splines = _written_splines(back.edges)
            missing = [c for c in missing if not _cut_in_pieces(c, source, written_splines)]
        self.assertEqual(missing, [], "untouched curves rewritten with other coefficients")
    return test


for _rel, _reading in tracked_drawings():
    setattr(TestFidelity, f"{case_name(PROJECT_ROOT / _rel)}_{_reading}", _make_fidelity_test(_rel, _reading))


if __name__ == "__main__":
    unittest.main()
