# tests/promises/test_outlines_invariants.py

"""Invariants of `outlines()` that must always hold, for any drawing — they do
not compare against a frozen value (a golden): they are either true or the
engine has a defect. They are never regenerated nor looked at by eye (unlike
`tests/golden/test_golden_outlines.py`). Fixture: the same real drawings:
every tracked drawing read with `outlines()` (tests/drawings.py)."""

import tempfile
import unittest
from pathlib import Path


import topo
import topo_dxf

from tests.drawings import case_name, drawing_key, drawings_for
from tests.invariants import (along_contours, uncovered, known_defect, contours, message_problems, scrambled,
                              shape_differences, unscrambled)
from tests.readings import geometry_key, outline_reading, outline_scrambled
from topo.core.topology.noding import GRAPH_EPSILON
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE
from topo.core.primitives.line import LineSeg
from topo.core.primitives.conics import CircleSeg
from topo import to_shapely

MAX_GAP = 0.5
SOURCES = drawings_for("outlines")
# the same contour may give a polygon differing by this much: the
# discretization's sagitta plus the node grid of the union of faces
BOUNDS_TOLERANCE = DEFAULT_TOLERANCE + GRAPH_EPSILON
# two readings of the same contour, each off by BOUNDS_TOLERANCE: allowed
# difference area per mm of perimeter
SHAPE_BAND = 2 * BOUNDS_TOLERANCE


def _keys(text: str) -> frozenset:
    return frozenset(f"data/{k}" for k in text.split())


# true defects found by these invariants, open in the gate:
# invariant → (entry, drawings). Every case comes out as a skip with its entry;
# when a case passes the test fails until it leaves the list
KNOWN: dict = {}


def _check(test, invariant: str, dxf: Path, check) -> None:
    """`check()` for `dxf`, or as a known defect if the drawing is in KNOWN[invariant]."""
    gate, keys = KNOWN.get(invariant, ("", frozenset()))
    if drawing_key(dxf) in keys:
        known_defect(test, f"{drawing_key(dxf)} ({invariant})", gate, check)
    check()


def _snapshot(result) -> list:
    return sorted([float(v) for v in to_shapely(c.outer).bounds] + [len(c.inners)]
                  for c in result.clusters)


def _unmatched(before: list, after: list) -> list:
    """The islands of `before` without a twin in `after`: same number of inners, box
    within BOUNDS_TOLERANCE (one-to-one pairing)."""
    free = list(after)
    missing = []
    for item in before:
        twin = next((other for other in free if other[4] == item[4]
                     and all(abs(x - y) <= BOUNDS_TOLERANCE for x, y in zip(item[:4], other[:4]))),
                    None)
        if twin is None:
            missing.append([round(v, 3) for v in item])
        else:
            free.remove(twin)
    return missing


class TestPolygonValidity(unittest.TestCase):
    """Every polygon read by `outlines()` — outer and inner — is a simple shape (not
    self-intersecting): a self-intersecting polygon gives an area computed by sign
    cancellation, not the true shape."""

    def _assert_valid(self, contour, where):
        self.assertTrue(to_shapely(contour).is_valid, f"{where}: the polygon is not a simple shape")
        self.assertGreater(to_shapely(contour).area, 0, f"{where}: the polygon has null area")


def _make_validity_test(dxf: Path):
    def test(self):
        _, result = outline_reading(dxf, MAX_GAP)
        for ci, cluster in enumerate(result.clusters):
            self._assert_valid(cluster.outer, f"{dxf.stem}.cluster[{ci}].outer")
            for ii, inner in enumerate(cluster.inners):
                self._assert_valid(inner, f"{dxf.stem}.cluster[{ci}].inner[{ii}]")
    return test


for _dxf in SOURCES:
    setattr(TestPolygonValidity, case_name(_dxf), _make_validity_test(_dxf))


class TestMessagesAreDiagnostics(unittest.TestCase):
    """Every message of outlines() is a Diagnostic of its channel, with a known code."""


def _make_messages_test(dxf: Path):
    def test(self):
        self.assertEqual(message_problems(outline_reading(dxf, MAX_GAP)[1]), [])
    return test


for _dxf in SOURCES:
    setattr(TestMessagesAreDiagnostics, case_name(_dxf), _make_messages_test(_dxf))


class TestRoundtripStable(unittest.TestCase):
    """Exporting to DXF and re-reading with `outlines()` must give the same islands
    (same outer box within BOUNDS_TOLERANCE, same number of inners per island) — if
    it changes, the engine wrote or read something different from what it found the
    first time. Found this way on `regr_04` (two crescents in a
    single loop, solved). Known defects in KNOWN."""


def _roundtrip(self, dxf: Path):
    doc, before = outline_reading(dxf, MAX_GAP)
    exported = topo_dxf.to_dxf(before, source_doc=doc, allow_invalid=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / f"{dxf.stem}.dxf"
        exported.saveas(str(tmp_path))
        # re-reads topo's output without its loose and text layers
        after = topo.heal(topo_dxf.load_dxf(str(tmp_path), skip_layers=topo_dxf.SKIP_LAYERS),
                          max_gap=MAX_GAP).outlines()
    snap_before, snap_after = _snapshot(before), _snapshot(after)
    self.assertEqual(len(snap_before), len(snap_after),
                     f"{dxf.stem}: the number of islands changes after export+reload")
    self.assertEqual(_unmatched(snap_before, snap_after), [],
                     f"{dxf.stem}: the islands change after export+reload "
                     f"(after: {[[round(v, 3) for v in s] for s in snap_after]})")


def _make_roundtrip_test(dxf: Path):
    def test(self):
        _check(self, "roundtrip", dxf, lambda: _roundtrip(self, dxf))
    return test


for _dxf in SOURCES:
    setattr(TestRoundtripStable, case_name(_dxf), _make_roundtrip_test(_dxf))


class TestNothingDropped(unittest.TestCase):
    """Every piece of input geometry ends in the output — in the segments of a
    contour or in the trash — within `max_gap`: the gap-fix may move an end up to
    there, not beyond. Found this way the stretch of two tangent arcs that, with a
    loop divided into lobes, was in no lobe."""


def _make_dropped_test(dxf: Path):
    def test(self):
        doc, result = outline_reading(dxf, MAX_GAP)
        lost = uncovered(doc, result, MAX_GAP)
        self.assertLessEqual(lost.length, GRAPH_EPSILON,
                             f"{dxf.stem}: {lost.length:.3f} mm of input geometry "
                             f"are in no output (near {lost.representative_point()})")
    return test


for _dxf in SOURCES:
    setattr(TestNothingDropped, case_name(_dxf), _make_dropped_test(_dxf))


class TestOutOnce(unittest.TestCase):
    """Every input piece comes out once, either in a contour or in `loose`: no
    `loose` stretch runs along a contour."""


def _make_out_once_test(dxf: Path):
    def test(self):
        doc, result = outline_reading(dxf, MAX_GAP)
        _check(self, "out once", dxf, lambda: self.assertEqual(
            along_contours(result, doc), [], f"{dxf.stem}: loose stretches along a contour"))
    return test


for _dxf in SOURCES:
    setattr(TestOutOnce, case_name(_dxf), _make_out_once_test(_dxf))


def _differences(result, again, back=lambda p: p) -> list:
    """What changes between the islands of `result` and those of `again` (brought
    back with `back`): number, outer, inner."""
    outers, inners = contours(result)
    outers_again, inners_again = ([back(p) for p in ps] for ps in contours(again))
    found = []
    if len(again.clusters) != len(result.clusters):
        found.append(f"isole {len(result.clusters)} → {len(again.clusters)}")
    for what, before, after in (("outer", outers, outers_again), ("inner", inners, inners_again)):
        lost = shape_differences(before, after, SHAPE_BAND)
        if lost:
            found.append(f"{what} {len(before)} → {len(after)}, change {lost[:3]}")
    return found


_SCRAMBLED: dict = {}   # fingerprint of the geometry -> differences: twins are read once


class TestScrambled(unittest.TestCase):
    """The same drawing written another way — entities in another order, rotated,
    far from the origin, mirrored — gives the same islands: the reading depends
    neither on the file's order nor on the frame. One reading, all at once, once
    per geometry; the other angles are tried by the micro-cases (TestScrambledMicro)."""


def _scrambled_differences(dxf: Path) -> list:
    doc, result = outline_reading(dxf, MAX_GAP)
    key = geometry_key(doc)
    if key not in _SCRAMBLED:
        _SCRAMBLED[key] = _differences(result, outline_scrambled(dxf, MAX_GAP), unscrambled)
    return _SCRAMBLED[key]


def _make_scrambled_test(dxf: Path):
    def test(self):
        found = _scrambled_differences(dxf)
        _check(self, "scrambled", dxf,
               lambda: self.assertEqual(found, [], f"{dxf.stem}: written another way changes the islands"))
    return test


for _dxf in SOURCES:
    setattr(TestScrambled, case_name(_dxf), _make_scrambled_test(_dxf))


# eight arbitrary angles: on whole drawings each cost a reading per drawing
# (~25 s of suite), on micro-cases a few milliseconds
ANGLES = (0.13, 0.41, 0.97, 1.33, 1.9, 2.47, 3.01, 4.4)
# minimal cuts of the repo's drawings that, before the change, changed reading
# with the angle, and not at ROTATION: each was unstable on the old code and is stable since
MICRO_CASES = {
    # anch_03, anch_03_noframe, regr_02: a 60° V with the inscribed circle cutting
    # every side by 0.004; before unstable at 6 angles out of 8
    "v_with_circle": [
        LineSeg(start=(746.518400822, 390.9160859284), end=(754.018400822, 395.2910859284)),
        LineSeg(start=(754.018400822, 395.2910859284), end=(739.018400822, 403.8625144998001)),
        CircleSeg(center=(748.5175721479, 395.281296222), radius=2.7545675962),
    ],
    # regr_04 reduced to blocks: two nearly aligned lines, offset by 0.04, starts at
    # 0.042; before they gave a degenerate contour at 4 angles out of 8
    "offset_lines": [
        LineSeg(start=(1068.899871006625, 584.2766554286404), end=(1063.209502662657, 586.5054223191735)),
        LineSeg(start=(1068.884100771032, 584.2375217405909), end=(1069.529957804885, 583.9735163747837)),
    ],
}


class TestScrambledMicro(unittest.TestCase):
    """Like TestScrambled, at eight angles, on the contacts a single angle does not
    see: a wrongly decided contact changes the reading only at some angles. A new
    case enters here as a minimal cut, not as an extra angle on whole drawings."""


def _make_micro_test(segments: list):
    def test(self):
        doc = topo.load_segments(segments)
        result = topo.heal(doc, max_gap=MAX_GAP).outlines()
        for seed, angle in enumerate(ANGLES):
            again = topo.heal(scrambled(doc, angle, seed), max_gap=MAX_GAP).outlines()
            self.assertEqual(_differences(result, again, lambda p: unscrambled(p, angle)), [],
                             f"{angle} rad: written another way changes the islands")
    return test


for _name, _segments in MICRO_CASES.items():
    setattr(TestScrambledMicro, f"test_{_name}", _make_micro_test(_segments))


if __name__ == "__main__":
    unittest.main()
