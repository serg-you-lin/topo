# tests/promises/test_outlines_invariants.py

"""
Invarianti di `outlines()` che devono valere sempre, per qualunque disegno —
non confrontano contro un valore congelato (un golden): o sono vere o il
motore ha un difetto. Non vanno mai rigenerate né guardate a occhio (a
differenza di `tests/golden/test_golden_outlines.py`). Fixture: gli stessi
disegni reali: ogni disegno tracciato che si legge con `outlines()`
(tests/drawings.py, D158).
"""

import tempfile
import unittest
from pathlib import Path


import topo
import topo_dxf

from tests.drawings import case_name, drawing_key, drawings_for
from tests.invariants import along_contours, uncovered, known_defect, contours, scrambled, shape_differences, unscrambled
from tests.readings import geometry_key, outline_reading, outline_scrambled
from topo.core.topology.noding import GRAPH_EPSILON
from topo.core.primitives.segments import DEFAULT_TOLERANCE, CircleSeg, LineSeg
from topo import to_shapely

MAX_GAP = 0.5
SOURCES = drawings_for("outlines")
# lo stesso contorno può dare un poligono diverso di tanto così: la freccia
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
KNOWN: dict = {}


def _check(test, invariant: str, dxf: Path, check) -> None:
    """`check()` per `dxf`, o come difetto noto se il disegno è in KNOWN[invariant]."""
    gate, keys = KNOWN.get(invariant, ("", frozenset()))
    if drawing_key(dxf) in keys:
        known_defect(test, f"{drawing_key(dxf)} ({invariant})", gate, check)
    check()


def _snapshot(result) -> list:
    return sorted([float(v) for v in to_shapely(c.outer).bounds] + [len(c.inners)]
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
    """Ogni poligono letto da `outlines()` — outer e inner — è una forma
    semplice (non autointersecante): un poligono autointersecante dà
    un'area calcolata per cancellazione di segno, non la forma vera."""

    def _assert_valid(self, contour, where):
        self.assertTrue(to_shapely(contour).is_valid, f"{where}: il poligono non è una forma semplice")
        self.assertGreater(to_shapely(contour).area, 0, f"{where}: il poligono ha area nulla")


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


class TestRoundtripStable(unittest.TestCase):
    """Esportare in DXF e rileggere con `outlines()` deve dare le stesse isole
    (stesso riquadro esterno entro BOUNDS_TOLERANCE, stesso numero di inner
    per isola) — se cambia, il motore ha scritto o letto qualcosa di diverso
    da quello che aveva trovato la prima volta. Trovato così il 12 ottobre su
    `regr_04` (due mezzelune in un giro solo, risolto in D106). Difetti noti
    in KNOWN."""


def _roundtrip(self, dxf: Path):
    doc, before = outline_reading(dxf, MAX_GAP)
    exported = topo_dxf.to_dxf(before, source_doc=doc, allow_invalid=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / f"{dxf.stem}.dxf"
        exported.saveas(str(tmp_path))
        after = topo.heal(topo_dxf.load_dxf(str(tmp_path)), max_gap=MAX_GAP).outlines()
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


class TestNothingDropped(unittest.TestCase):
    """Ogni pezzo di geometria in ingresso finisce in uscita — nei segmenti
    di un contorno o nel trash — entro `max_gap`: il gap-fix può spostare un
    estremo fino a lì, non oltre (D98). Trovato così (D106) il tratto di due
    archi tangenti che, diviso un giro in lobi, non stava in nessun lobo."""


def _make_dropped_test(dxf: Path):
    def test(self):
        doc, result = outline_reading(dxf, MAX_GAP)
        lost = uncovered(doc, result, MAX_GAP)
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
        doc, result = outline_reading(dxf, MAX_GAP)
        _check(self, "out once", dxf, lambda: self.assertEqual(
            along_contours(result, doc), [], f"{dxf.stem}: tratti di loose lungo un contorno"))
    return test


for _dxf in SOURCES:
    setattr(TestOutOnce, case_name(_dxf), _make_out_once_test(_dxf))


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


_SCRAMBLED: dict = {}   # impronta della geometria -> differenze: i gemelli si leggono una volta


class TestScrambled(unittest.TestCase):
    """Lo stesso disegno scritto in un altro modo — entità in un altro ordine,
    ruotato, lontano dall'origine, specchiato — dà le stesse isole: la
    lettura non dipende né dall'ordine del file né dal sistema di
    riferimento (D143, D158). Una lettura sola, tutto insieme (D160), una
    volta per geometria (D180); gli altri angoli li provano i micro-casi
    (TestScrambledMicro)."""


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
               lambda: self.assertEqual(found, [], f"{dxf.stem}: scritto in un altro modo cambia le isole"))
    return test


for _dxf in SOURCES:
    setattr(TestScrambled, case_name(_dxf), _make_scrambled_test(_dxf))


# otto angoli qualunque: sui disegni interi ognuno costava una lettura per
# disegno (~25 s di suite), sui micro-casi pochi millisecondi
ANGLES = (0.13, 0.41, 0.97, 1.33, 1.9, 2.47, 3.01, 4.4)
# ritagli minimi dei disegni del repo che, prima di D180, cambiavano lettura
# con l'angolo, e a ROTATION no: ognuno era instabile sul codice di 3ea516b^
# ed è stabile da D180 (TODO.md, Tempo della suite)
MICRO_CASES = {
    # anch_03, anch_03_noframe, regr_02: una V di 60° col cerchio inscritto che
    # taglia ogni lato di 0.004; prima instabile a 6 angoli su 8
    "v_col_cerchio": [
        LineSeg(start=(746.518400822, 390.9160859284), end=(754.018400822, 395.2910859284)),
        LineSeg(start=(754.018400822, 395.2910859284), end=(739.018400822, 403.8625144998001)),
        CircleSeg(center=(748.5175721479, 395.281296222), radius=2.7545675962),
    ],
    # regr_04 ridotto a blocchi: due rette quasi allineate, sfalsate di 0.04,
    # inizi a 0.042; prima davano un contorno degenere a 4 angoli su 8
    "rette_sfalsate": [
        LineSeg(start=(1068.899871006625, 584.2766554286404), end=(1063.209502662657, 586.5054223191735)),
        LineSeg(start=(1068.884100771032, 584.2375217405909), end=(1069.529957804885, 583.9735163747837)),
    ],
}


class TestScrambledMicro(unittest.TestCase):
    """Come TestScrambled, a otto angoli, sui contatti che un angolo solo non
    vede: un contatto deciso male cambia la lettura solo ad alcuni angoli
    (D180). Un caso nuovo entra qui come ritaglio minimo, non come angolo in
    più sui disegni interi."""


def _make_micro_test(segments: list):
    def test(self):
        doc = topo.load_segments(segments)
        result = topo.heal(doc, max_gap=MAX_GAP).outlines()
        for seed, angle in enumerate(ANGLES):
            again = topo.heal(scrambled(doc, angle, seed), max_gap=MAX_GAP).outlines()
            self.assertEqual(_differences(result, again, lambda p: unscrambled(p, angle)), [],
                             f"{angle} rad: scritto in un altro modo cambia le isole")
    return test


for _name, _segments in MICRO_CASES.items():
    setattr(TestScrambledMicro, f"test_{_name}", _make_micro_test(_segments))


if __name__ == "__main__":
    unittest.main()
