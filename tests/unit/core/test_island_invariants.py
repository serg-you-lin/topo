# tests/unit/core/test_island_invariants.py

"""
Invarianti di `island()` che devono valere sempre, per qualunque disegno —
non confrontano contro un valore congelato (un golden): o sono vere o il
motore ha un difetto. Non vanno mai rigenerate né guardate a occhio (a
differenza di `tests/real/test_golden_islands.py`). Fixture: gli stessi
disegni reali: ogni disegno tracciato che si legge con `island()`
(tests/drawings.py, D158).
"""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

import topo
import topo_dxf

from tests.drawings import case_name, drawing_key, drawings_for
from tests.invariants import MOTIONS, along_contours, known_defect, contours, moved, orders, shape_differences
from tests.readings import island_reading
from topo.core.island import GRAPH_EPSILON
from topo.core.primitives.segments import DEFAULT_TOLERANCE

MAX_GAP = 0.5
SOURCES = drawings_for("island")
# lo stesso contorno può dare un `.polygon` diverso di tanto così: la freccia
# della discretizzazione più la griglia dei nodi dell'unione di facce (D106)
BOUNDS_TOLERANCE = DEFAULT_TOLERANCE + GRAPH_EPSILON
# due letture dello stesso contorno, ognuna fuori di BOUNDS_TOLERANCE: area di
# scarto ammessa per mm di perimetro
SHAPE_BAND = 2 * BOUNDS_TOLERANCE


def _keys(text: str) -> frozenset:
    return frozenset(f"data/{k}" for k in text.split())


# difetti veri trovati da queste invarianti, aperti nel cancello (TODO.md):
# invariante → (voce, disegni). Ogni caso esce come skip con la sua voce; quando
# un caso passa il test fallisce finché non esce dalla lista (D158)
KNOWN = {
    # pezzi usciti due volte, in un contorno e in loose: il ripiego "unione
    # delle facce" (D100) segna presi gli edge del cammino, non del bordo
    "out once": ("G6b", _keys(
        "golden_islands/regr_01 golden_islands/anch_02 golden_islands/anch_04 golden_islands/anch_06 "
        "golden_islands/regr_04 golden_anchoring/anch_02 golden_anchoring/anch_02_noframe "
        "golden_anchoring/anch_04 golden_anchoring/anch_04_noframe golden_anchoring/anch_06 "
        "golden_anchoring/anch_06_noframe golden_anchoring/anch_08 golden_anchoring/anch_08_noframe")),
    # la lettura cambia con l'ordine delle entità o con un moto rigido
    "edge order": ("G6c", _keys(
        "golden_anchoring/anch_01 golden_anchoring/anch_01_noframe golden_anchoring/anch_02 "
        "golden_anchoring/anch_02_noframe golden_anchoring/anch_03 golden_anchoring/anch_03_noframe "
        "golden_anchoring/anch_04 golden_anchoring/anch_04_noframe golden_anchoring/anch_05 "
        "golden_anchoring/anch_05_noframe golden_anchoring/anch_06 golden_anchoring/anch_06_noframe "
        "golden_anchoring/anch_08 golden_anchoring/anch_08_noframe golden_islands/anch_02 "
        "golden_islands/anch_03 golden_islands/anch_05 golden_islands/anch_06 golden_islands/anch_08 "
        "golden_islands/regr_01 golden_islands/regr_02 golden_islands/regr_04")),
    "rigid motion": ("G6c", _keys(
        "golden_anchoring/anch_01 golden_anchoring/anch_01_noframe golden_anchoring/anch_02 "
        "golden_anchoring/anch_02_noframe golden_anchoring/anch_03 golden_anchoring/anch_03_noframe "
        "golden_anchoring/anch_04 golden_anchoring/anch_04_noframe golden_anchoring/anch_06 "
        "golden_anchoring/anch_06_noframe golden_anchoring/anch_07 golden_anchoring/anch_08 "
        "golden_anchoring/anch_08_noframe golden_islands/anch_01 golden_islands/anch_02 "
        "golden_islands/anch_04 golden_islands/anch_06 golden_islands/anch_08 golden_islands/regr_03 "
        "golden_islands/regr_04")),
    # inner sovrapposti in parte: cicli fra giri accettati che non sono facce
    # (D107), non giri di D103 (D157)
    "inners cross": ("G7", _keys(
        "golden_islands/anch_03 golden_islands/regr_02 golden_anchoring/anch_01 "
        "golden_anchoring/anch_01_noframe golden_anchoring/anch_02 golden_anchoring/anch_02_noframe "
        "golden_anchoring/anch_03 golden_anchoring/anch_03_noframe golden_anchoring/anch_04 "
        "golden_anchoring/anch_04_noframe golden_anchoring/anch_08 golden_anchoring/anch_08_noframe")),
    "roundtrip": ("G7", _keys(
        "golden_islands/anch_03 golden_islands/regr_02 golden_anchoring/anch_03 "
        "golden_anchoring/anch_03_noframe")),
}


def _check(test, invariant: str, dxf: Path, check) -> None:
    """`check()` per `dxf`, o come difetto noto se il disegno è in KNOWN[invariant]."""
    gate, keys = KNOWN.get(invariant, ("", frozenset()))
    if drawing_key(dxf) in keys:
        known_defect(test, f"{drawing_key(dxf)} ({invariant})", gate, check)
    check()


def _snapshot(result) -> list:
    return sorted([float(v) for v in c.outer.polygon.bounds] + [len(c.inners)]
                  for c in result.clusters)


def _unmatched(before: list, after: list) -> list:
    """Le isole di `before` senza una gemella in `after`: stesso numero di
    inner, riquadro entro BOUNDS_TOLERANCE (accoppiamento uno a uno)."""
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
    """Ogni poligono letto da `island()` — outer e inner — è una forma
    semplice (non autointersecante): un poligono autointersecante dà
    un'area calcolata per cancellazione di segno, non la forma vera."""

    def _assert_valid(self, contour, where):
        self.assertTrue(contour.polygon.is_valid, f"{where}: .polygon non è una forma semplice")
        self.assertGreater(contour.polygon.area, 0, f"{where}: .polygon ha area nulla")


def _make_validity_test(dxf: Path):
    def test(self):
        _, result = island_reading(dxf, MAX_GAP)
        for ci, cluster in enumerate(result.clusters):
            self._assert_valid(cluster.outer, f"{dxf.stem}.cluster[{ci}].outer")
            for ii, inner in enumerate(cluster.inners):
                self._assert_valid(inner, f"{dxf.stem}.cluster[{ci}].inner[{ii}]")
    return test


for _dxf in SOURCES:
    setattr(TestPolygonValidity, case_name(_dxf), _make_validity_test(_dxf))


class TestRoundtripStable(unittest.TestCase):
    """Esportare in DXF e rileggere con `island()` deve dare le stesse isole
    (stesso riquadro esterno entro BOUNDS_TOLERANCE, stesso numero di inner
    per isola) — se cambia, il motore ha scritto o letto qualcosa di diverso
    da quello che aveva trovato la prima volta. Trovato così il 12 ottobre su
    `regr_04` (due mezzelune in un giro solo, risolto in D106). Difetti noti
    in KNOWN."""


def _roundtrip(self, dxf: Path):
    doc, before = island_reading(dxf, MAX_GAP)
    exported = topo_dxf.to_dxf(before, source_doc=doc, allow_invalid=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / f"{dxf.stem}.dxf"
        exported.saveas(str(tmp_path))
        after = topo.island(topo_dxf.load_dxf(str(tmp_path)), max_gap=MAX_GAP)
    snap_before, snap_after = _snapshot(before), _snapshot(after)
    self.assertEqual(len(snap_before), len(snap_after),
                     f"{dxf.stem}: il numero di isole cambia dopo export+reload")
    self.assertEqual(_unmatched(snap_before, snap_after), [],
                     f"{dxf.stem}: le isole cambiano dopo export+reload "
                     f"(dopo: {[[round(v, 3) for v in s] for s in snap_after]})")


def _make_roundtrip_test(dxf: Path):
    def test(self):
        _check(self, "roundtrip", dxf, lambda: _roundtrip(self, dxf))
    return test


for _dxf in SOURCES:
    setattr(TestRoundtripStable, case_name(_dxf), _make_roundtrip_test(_dxf))


def _geometry(segment):
    pts = segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


class TestNothingDropped(unittest.TestCase):
    """Ogni pezzo di geometria in ingresso finisce in uscita — nei segmenti
    di un contorno o nel trash — entro `max_gap`: il gap-fix può spostare un
    estremo fino a lì, non oltre (D98). Trovato così (D106) il tratto di due
    archi tangenti che, diviso un giro in lobi, non stava in nessun lobo."""


def _make_dropped_test(dxf: Path):
    def test(self):
        doc, result = island_reading(dxf, MAX_GAP)
        out = [_geometry(s) for c in result.clusters for ct in [c.outer] + c.inners
               for s in ct.segments]
        out += [_geometry(s) for f in result.loose for s in f.segments]
        covered = unary_union(out).buffer(MAX_GAP)
        lost = unary_union([_geometry(e.segment) for e in doc.edges]).difference(covered)
        self.assertLessEqual(lost.length, GRAPH_EPSILON,
                             f"{dxf.stem}: {lost.length:.3f} mm di geometria in ingresso "
                             f"non stanno in nessuna uscita (vicino a {lost.representative_point()})")
    return test


for _dxf in SOURCES:
    setattr(TestNothingDropped, case_name(_dxf), _make_dropped_test(_dxf))


class TestOutOnce(unittest.TestCase):
    """Ogni pezzo d'ingresso esce una volta, o in un contorno o in `loose`
    (D137, D158): nessun tratto di `loose` corre lungo un contorno."""


def _make_out_once_test(dxf: Path):
    def test(self):
        _, result = island_reading(dxf, MAX_GAP)
        _check(self, "out once", dxf, lambda: self.assertEqual(
            along_contours(result), [], f"{dxf.stem}: tratti di loose lungo un contorno"))
    return test


for _dxf in SOURCES:
    setattr(TestOutOnce, case_name(_dxf), _make_out_once_test(_dxf))


class TestInnersDontCross(unittest.TestCase):
    """Due inner della stessa isola o sono disgiunti o uno contiene l'altro
    (un foro dentro un foro): sovrapposti in parte sono due cicli che non
    sono facce. Margine: una fascia larga BOUNDS_TOLERANCE lungo il bordo
    del più piccolo. Difetti noti in KNOWN."""


def _make_cross_test(dxf: Path):
    def test(self):
        _, result = island_reading(dxf, MAX_GAP)
        crossing = []
        for ci, cluster in enumerate(result.clusters):
            polygons = [inner.polygon for inner in cluster.inners]
            for i in range(len(polygons)):
                for j in range(i + 1, len(polygons)):
                    small = min(polygons[i], polygons[j], key=lambda p: p.area)
                    band = small.length * BOUNDS_TOLERANCE
                    shared = polygons[i].intersection(polygons[j]).area
                    if shared > band and small.area - shared > band:
                        crossing.append(f"cluster[{ci}].inner[{i}]/inner[{j}]")
        _check(self, "inners cross", dxf,
               lambda: self.assertEqual(crossing, [], f"{dxf.stem}: inner sovrapposti in parte"))
    return test


for _dxf in SOURCES:
    setattr(TestInnersDontCross, case_name(_dxf), _make_cross_test(_dxf))


def _differences(result, again, back=lambda p: p) -> list:
    """Cosa cambia fra le isole di `result` e quelle di `again` (riportate
    indietro con `back`): numero, outer, inner."""
    outers, inners = contours(result)
    outers_again, inners_again = ([back(p) for p in ps] for ps in contours(again))
    found = []
    if len(again.clusters) != len(result.clusters):
        found.append(f"isole {len(result.clusters)} → {len(again.clusters)}")
    for what, before, after in (("outer", outers, outers_again), ("inner", inners, inners_again)):
        lost = shape_differences(before, after, SHAPE_BAND)
        if lost:
            found.append(f"{what} {len(before)} → {len(after)}, cambiano {lost[:3]}")
    return found


class TestRigidMotion(unittest.TestCase):
    """Ruotare, spostare lontano dall'origine o specchiare il disegno prima
    di `island()` dà le stesse isole mosse, outer e inner: la lettura non
    dipende dal sistema di riferimento né dalla grandezza delle coordinate
    (D143, D158)."""


def _make_motion_test(dxf: Path):
    def test(self):
        doc, result = island_reading(dxf, MAX_GAP)
        found = {name: _differences(result, topo.island(moved(doc, move), max_gap=MAX_GAP), back)
                 for name, move, back, _ in MOTIONS}
        found = {name: diff for name, diff in found.items() if diff}
        _check(self, "rigid motion", dxf,
               lambda: self.assertEqual(found, {}, f"{dxf.stem}: un moto cambia le isole"))
    return test


for _dxf in SOURCES:
    setattr(TestRigidMotion, case_name(_dxf), _make_motion_test(_dxf))


class TestEdgeOrder(unittest.TestCase):
    """L'ordine in cui il file elenca le entità non conta: gli edge al
    contrario, e rimescolati con seed fissi, danno le stesse isole."""


def _make_order_test(dxf: Path):
    def test(self):
        doc, result = island_reading(dxf, MAX_GAP)
        found = {name: _differences(result, topo.island(replace(doc, edges=edges), max_gap=MAX_GAP))
                 for name, edges in orders(doc.edges)}
        found = {name: diff for name, diff in found.items() if diff}
        _check(self, "edge order", dxf,
               lambda: self.assertEqual(found, {}, f"{dxf.stem}: l'ordine cambia le isole"))
    return test


for _dxf in SOURCES:
    setattr(TestEdgeOrder, case_name(_dxf), _make_order_test(_dxf))


if __name__ == "__main__":
    unittest.main()
