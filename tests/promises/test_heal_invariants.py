# tests/promises/test_heal_invariants.py

"""Invariants of `heal()` that must always hold, for any drawing — like those of
`outlines()` (test_outlines_invariants.py): they do not compare against a
frozen value, they are either true or the engine has a defect. They are never
regenerated. Fixture: every tracked drawing read with `heal()`
(tests/drawings.py), read as `tests/golden/test_golden_faces.py` reads it; the
heal golden, `tests/data/golden_faces/`, with tolerance and roles from
`tests/data/config/`.

A golden freezes an output and also protects a defect that was there when it
was written; these do not."""

import json
import math
import unittest
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Optional

from shapely.geometry import LineString, MultiPoint, Point

import topo
import topo_dxf
from topo.core.primitives import LineSeg
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE
from topo.model.document import Document

from tests.drawings import case_name, drawing_key, drawings_for
from tests.invariants import (
    MOTIONS, along_contours, uncovered, known_defect, contours, message_problems, moved, orders, shape_differences,
)
from topo import to_shapely
from tests.paths import DATA

SOURCE_DIR = DATA / "golden_faces"
DEFAULT_HEAL_TOLERANCE = 0.5          # as tests/golden/test_golden_faces.py

GLOBAL_NAME_ROLES = {"MARK": "engrave", "Signature": "engrave"}
# drawings with a gap exactly as wide as the tolerance: a rotation by any angle
# changes the rounding coordinates (~1e-14), enough to bring that gap above or
# below the threshold. It is the edge of a yes/no rule: the same geometry moved
# is not promised (docs/LIMITS.md), not a defect. The exact motions (`exact` in
# MOTIONS) are checked anyway
GAP_AT_TOLERANCE = {"Multipolis"}
# true defects found by these invariants, open in TODO.md: when they are solved
# the list empties
KNOWN_ORDER_DEPENDENT: set = set()
# (drawing, tolerance) → gate entry: pieces that came out twice
KNOWN_TWICE: dict = {}
# drawing → gate entry: the chords change the outer (slots as wide as the
# tolerance, filled only when the chords are there)
KNOWN_CHORDS: dict = {}   # closed
# tolerances on which every piece is proved to come out once, besides the drawing's own
OUT_ONCE_TOLERANCES = (DEFAULT_TOLERANCE, 0.05)
CHORDS_PER_CLUSTER = 6
# two readings of the same contour may differ by the discretization's sagitta
# along the whole border: allowed difference area per mm of perimeter
SHAPE_BAND = 2 * DEFAULT_TOLERANCE


def _sources() -> list:
    return drawings_for("faces")


def _config(dxf: Path) -> dict:
    # tolerance and roles chosen for the heal golden (test_golden_faces.py); every
    # other drawing is read with the defaults
    path = DATA / "config" / f"{dxf.stem}.json"
    if dxf.parent != SOURCE_DIR:
        return {}
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _tolerance(dxf: Path) -> float:
    return _config(dxf).get("tolerance", DEFAULT_HEAL_TOLERANCE)


def _read(dxf: Path, tol: Optional[float] = None):
    """(document, heal result) as in test_golden, at the drawing's tolerance or at
    `tol`: the drawing's tolerance given by name is the same reading."""
    return _read_at(dxf, _tolerance(dxf) if tol is None else tol)


@lru_cache(maxsize=None)
def _read_at(dxf: Path, tol: float):
    rules = topo.name_rules({**GLOBAL_NAME_ROLES, **_config(dxf).get("name_roles", {})})
    doc = topo_dxf.load_dxf(str(dxf), upgrade=True, explode_inserts=True, flatten_z=True,
                          role_rules=rules)
    return doc, topo.heal(doc).faces()


def _shape_differences(before: list, after: list) -> list:
    return shape_differences(before, after, SHAPE_BAND)


def _outers(result) -> list:
    return [to_shapely(c.outer) for c in result.clusters]


def _register(cls, make, known: frozenset = frozenset()):
    for dxf in _sources():
        test = make(dxf)
        if dxf.stem in known:
            test = unittest.expectedFailure(test)
        setattr(cls, case_name(dxf), test)


# ---------------------------------------------------------------------------

class TestMessagesAreDiagnostics(unittest.TestCase):
    """Every message of faces() is a Diagnostic of its channel, with a known code."""


def _make_messages_test(dxf: Path):
    def test(self):
        self.assertEqual(message_problems(_read(dxf)[1]), [])
    return test


_register(TestMessagesAreDiagnostics, _make_messages_test)


class TestPolygonValidity(unittest.TestCase):
    """Every outer and every inner is a simple shape of positive area."""


def _make_validity_test(dxf: Path):
    def test(self):
        _, result = _read(dxf)
        for ci, cluster in enumerate(result.clusters):
            for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in
                                                               enumerate(cluster.inners)]:
                self.assertTrue(to_shapely(contour).is_valid, f"{dxf.stem}.cluster[{ci}].{name} is not simple")
                self.assertGreater(to_shapely(contour).area, 0, f"{dxf.stem}.cluster[{ci}].{name} has null area")
    return test


_register(TestPolygonValidity, _make_validity_test)


class TestContoursAreRings(unittest.TestCase):
    """The segments of every outer and every inner are a head-to-tail ring: each
    starts where the previous ends, the last closes on the first. It is what a
    caller finds in `contour.segments` and passes to the primitives of
    `topo.geometry.regions` without reordering."""


def _make_ring_test(dxf: Path):
    def test(self):
        from topo.core.primitives.mathseg import segment_endpoints
        _, result = _read(dxf)
        for ci, cluster in enumerate(result.clusters):
            for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in
                                                               enumerate(cluster.inners)]:
                segs = contour.segments
                for k, seg in enumerate(segs):
                    end = segment_endpoints(seg)[1]
                    start = segment_endpoints(segs[(k + 1) % len(segs)])[0]
                    self.assertLessEqual(math.dist(end, start), DEFAULT_TOLERANCE,
                                         f"{dxf.stem}.cluster[{ci}].{name}: the segment {k} "
                                         f"finisce a {end}, the next starts at {start}")
    return test


_register(TestContoursAreRings, _make_ring_test)


class TestNothingDropped(unittest.TestCase):
    """Every piece of input geometry ends in the output — in the segments of a
    contour or in the trash — within heal's tolerance: closing a gap or repairing
    a corner moves an end up to there, not beyond."""


def _make_dropped_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        lost = uncovered(doc, result, tol)
        self.assertLessEqual(lost.length, DEFAULT_TOLERANCE,
                             f"{dxf.stem}: {lost.length:.3f} mm of input geometry are not "
                             f"in any output (near {lost.representative_point()})")
    return test


_register(TestNothingDropped, _make_dropped_test)


class TestOutOnce(unittest.TestCase):
    """Every input piece comes out once, either in a contour or in `loose`: no
    `loose` stretch runs along a contour. At the drawing's tolerance and on
    OUT_ONCE_TOLERANCES (another tolerance changes which gaps it closes and which
    corners it repairs)."""


def _make_out_once_test(dxf: Path):
    def test(self):
        for tol in sorted({_tolerance(dxf), *OUT_ONCE_TOLERANCES}):
            with self.subTest(tolerance=tol):
                doc, result = _read(dxf, tol)
                check = lambda: self.assertEqual(along_contours(result, doc), [],
                                                 f"{dxf.stem} at tol {tol}: loose stretches along a contour")
                gate = KNOWN_TWICE.get((drawing_key(dxf), tol))
                if gate:
                    known_defect(self, f"{drawing_key(dxf)} at tol {tol}", gate, check)
                check()
    return test


_register(TestOutOnce, _make_out_once_test)


def _vertices(contour) -> list:
    pts = []
    for seg in contour.segments:
        for p in (seg.discretize(tolerance=DEFAULT_TOLERANCE)[0], seg.discretize(tolerance=DEFAULT_TOLERANCE)[-1]):
            p = (float(p[0]), float(p[1]))
            if all(math.dist(p, q) > 1e-6 for q in pts):
                pts.append(p)
    return pts


def _is_chord(polygon, a, b, margin: float) -> bool:
    """`a`–`b` crosses the material: inside the polygon, touching the border only at
    the two ends, and not running near it."""
    if math.dist(a, b) < 4 * margin:
        return False
    line = LineString([a, b])
    if not polygon.contains(line):
        return False
    touch = polygon.exterior.intersection(line)
    if not isinstance(touch, MultiPoint) or len(touch.geoms) != 2:
        return False
    return polygon.exterior.distance(line.interpolate(0.5, normalized=True)) > margin


def _chords(cluster, margin: float) -> list:
    """Pairs of chords from a common vertex to the two ends of a straight side: so
    the two ends of the side become branching nodes. First the sides outside the
    convex hull (the concave part), then the others."""
    polygon = to_shapely(cluster.outer)
    hull = polygon.convex_hull.exterior
    vertices = _vertices(cluster.outer)
    sides = [s for s in cluster.outer.segments if isinstance(s, LineSeg)]
    sides.sort(key=lambda s: -hull.distance(Point((s.start[0] + s.end[0]) / 2, (s.start[1] + s.end[1]) / 2)))
    chords = []
    for side in sides:
        if len(chords) >= 2 * CHORDS_PER_CLUSTER:
            break
        a, b = tuple(side.start[:2]), tuple(side.end[:2])
        for v in sorted(vertices, key=lambda q: math.dist(q, a) + math.dist(q, b)):
            if min(math.dist(v, a), math.dist(v, b)) < 1e-6:
                continue
            if _is_chord(polygon, v, a, margin) and _is_chord(polygon, v, b, margin):
                chords += [LineSeg(start=v, end=a), LineSeg(start=v, end=b)]
                break
    return chords


class TestChordsKeepTheOuter(unittest.TestCase):
    """A chord between two vertices of an outer, inside the material, divides the
    piece into two faces but does not change its border: with heal redone on the
    outer plus the chords, the same outer comes out and the chords go to the
    trash. It is the case of a bend line with no role. It skips the drawings
    without chords."""


def _make_chords_test(dxf: Path):
    def test(self):
        _, result = _read(dxf)
        tol = _tolerance(dxf)
        broken, tried = [], 0
        for ci, cluster in enumerate(result.clusters):
            chords = _chords(cluster, tol)
            if not chords:
                continue
            tried += 1
            again = topo.heal(topo.load_segments(list(cluster.outer.segments) + chords)).faces()
            if again.cluster_count != 1 or _shape_differences([to_shapely(cluster.outer)], _outers(again)):
                broken.append(f"cluster[{ci}] (+{len(chords)} chords): {again.cluster_count} cluster")
        if not tried:
            self.skipTest("no chord between two vertices of an outer")
        check = lambda: self.assertEqual(broken, [], f"{dxf.stem}: the chords change the outer")
        if drawing_key(dxf) in KNOWN_CHORDS:
            known_defect(self, drawing_key(dxf), KNOWN_CHORDS[drawing_key(dxf)], check)
        check()
    return test


_register(TestChordsKeepTheOuter, _make_chords_test)


class TestRolesOfChordsDontMatter(unittest.TestCase):
    """The non-structural edges of a file (bends from the layer) that cross an outer
    from border to border, read instead with no role, do not change the outers:
    the geometry alone says they are chords. It skips the drawings without such edges."""


def _crossing_edges(doc, result, tol: float) -> set:
    ids = set()
    for edge in doc.edges:
        if edge.role == "unknown" or not isinstance(edge.segment, LineSeg):
            continue
        a, b = Point(edge.start[:2]), Point(edge.end[:2])
        for cluster in result.clusters:
            ring = to_shapely(cluster.outer).exterior
            if ring.distance(a) <= tol and ring.distance(b) <= tol and \
                    to_shapely(cluster.outer).contains(LineString([edge.start[:2], edge.end[:2]]).interpolate(0.5, True)):
                ids.add(id(edge))
                break
    return ids


def _make_roles_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        ids = _crossing_edges(doc, result, tol)
        if not ids:
            self.skipTest("no non-structural edge from border to border")
        blind = Document(edges=[replace(e, role="unknown") if id(e) in ids else e for e in doc.edges],
                              source_path=doc.source_path, source_meta=doc.source_meta)
        again = topo.heal(blind).faces()
        self.assertEqual(again.cluster_count, result.cluster_count,
                         f"{dxf.stem}: {len(ids)} edges without role change the number of pieces")
        self.assertEqual(_shape_differences(_outers(result), _outers(again)), [],
                         f"{dxf.stem}: {len(ids)} edges without role change the outers")
    return test


_register(TestRolesOfChordsDontMatter, _make_roles_test)


class TestRigidMotion(unittest.TestCase):
    """Rotating, moving far from the origin or mirroring the drawing before heal
    gives the same pieces moved, outer and inner: heal does not depend on the frame
    (nor on "the leftmost point", nor on a grid aligned to the axes, nor on the
    direction a contour turns, nor on the size of the coordinates)."""


def _make_motion_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        outers, inners = contours(result)
        for name, move, back, exact in MOTIONS:
            with self.subTest(motion=name):
                if not exact and dxf.stem in GAP_AT_TOLERANCE:
                    self.skipTest("gap exactly as wide as the tolerance: on the threshold edge")
                again = topo.heal(moved(doc, move)).faces()
                outers_again, inners_again = ([back(p) for p in ps] for ps in contours(again))
                self.assertEqual(again.cluster_count, result.cluster_count, f"{dxf.stem}, {name}: changes the pieces")
                self.assertEqual(_shape_differences(outers, outers_again), [], f"{dxf.stem}, {name}: changes the outers")
                self.assertEqual(_shape_differences(inners, inners_again), [], f"{dxf.stem}, {name}: changes the holes")
    return test


_register(TestRigidMotion, _make_motion_test)


class TestEdgeOrder(unittest.TestCase):
    """The order in which the file lists the entities does not matter: the edges
    reversed, and shuffled with fixed seeds, give the same pieces."""


def _make_order_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        for name, edges in orders(doc.edges):
            with self.subTest(order=name):
                again = topo.heal(Document(edges=edges, source_path=doc.source_path,
                                           source_meta=doc.source_meta)).faces()
                self.assertEqual(again.cluster_count, result.cluster_count,
                                 f"{dxf.stem}, {name}: the order changes the pieces")
                self.assertEqual(_shape_differences(_outers(result), _outers(again)), [],
                                 f"{dxf.stem}, {name}: the order changes the outers")
    return test


_register(TestEdgeOrder, _make_order_test, known=frozenset(KNOWN_ORDER_DEPENDENT))


if __name__ == "__main__":
    unittest.main()
