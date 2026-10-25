# tests/unit/core/test_heal_invariants.py

"""
Invarianti di `heal()` che devono valere sempre, per qualunque disegno — come
quelle di `island()` (test_island_invariants.py): non confrontano contro un
valore congelato, o sono vere o il motore ha un difetto. Non si rigenerano
mai. Fixture: ogni disegno tracciato che si legge con `heal()` (tests/drawings.py,
D158), letto come lo legge `tests/real/test_golden.py`; i golden di heal,
`tests/data/golden/`, con tolleranza e ruoli da `tests/data/config/`.

Un golden congela un'uscita e protegge anche un difetto che c'era quando è
stato scritto; queste no (MAP.md D111).
"""

import json
import math
import unittest
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Optional

from shapely.geometry import LineString, MultiPoint, Point
from shapely.ops import unary_union

import topo
import topo_dxf
from topo.core.primitives import LineSeg
from topo.core.primitives.segments import DEFAULT_TOLERANCE
from topo.model.document import Document

from tests.drawings import case_name, drawing_key, drawings_for
from tests.invariants import MOTIONS, along_contours, uncovered, known_defect, contours, geometry as _geometry, moved, orders, shape_differences

DATA = Path(__file__).resolve().parent.parent.parent / "data"
SOURCE_DIR = DATA / "golden"
DEFAULT_HEAL_TOLERANCE = 0.5          # come tests/real/test_golden.py
GLOBAL_NAME_ROLES = {"MARK": "engrave", "Signature": "engrave"}
# disegni con un gap largo esattamente la tolleranza: ruotato di un angolo
# qualunque, l'arrotondamento dei nodi alla griglia (D96) lo porta di poco
# sopra o sotto la soglia — un caso sul filo, non un difetto; i moti esatti
# sulla griglia (quarto di giro, traslazione, specchio) li controllano comunque
GAP_AT_TOLERANCE = {"Multipolis"}
# difetti veri trovati da queste invarianti, aperti in TODO.md: quando sono
# risolti la lista si svuota
KNOWN_ORDER_DEPENDENT: set = set()
# (disegno, tolleranza) → voce del cancello: pezzi usciti due volte
KNOWN_TWICE: dict = {}
# disegno → voce del cancello: le corde cambiano l'outer (cave larghe quanto la
# tolleranza, riempite solo quando ci sono le corde)
KNOWN_CHORDS = {"data/SEGNI_TRACCIATI": "G6d"}
# tolleranze su cui si prova che ogni pezzo esce una volta, oltre a quella del disegno
OUT_ONCE_TOLERANCES = (DEFAULT_TOLERANCE, 0.05)
CHORDS_PER_CLUSTER = 6
# due letture dello stesso contorno possono differire della freccia della
# discretizzazione lungo tutto il bordo: area di scarto ammessa per mm di perimetro
SHAPE_BAND = 2 * DEFAULT_TOLERANCE


def _sources() -> list:
    return drawings_for("heal")


def _config(dxf: Path) -> dict:
    # tolleranza e ruoli scelti per i golden di heal (test_golden.py); ogni
    # altro disegno si legge con quelli di default
    path = DATA / "config" / f"{dxf.stem}.json"
    if dxf.parent != SOURCE_DIR:
        return {}
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _tolerance(dxf: Path) -> float:
    return _config(dxf).get("tolerance", DEFAULT_HEAL_TOLERANCE)


@lru_cache(maxsize=None)
def _read(dxf: Path, tol: Optional[float] = None):
    """(documento, risultato di heal) come in test_golden, alla tolleranza del
    disegno o a `tol`."""
    rules = topo.name_rules({**GLOBAL_NAME_ROLES, **_config(dxf).get("name_roles", {})})
    tol = _tolerance(dxf) if tol is None else tol
    doc = topo_dxf.load_dxf(str(dxf), upgrade=True, explode_inserts=True, flatten_z_flag=True,
                         tolerance=tol, role_rules=rules)
    return doc, topo.heal(doc, tolerance=tol)


def _shape_differences(before: list, after: list) -> list:
    return shape_differences(before, after, SHAPE_BAND)


def _outers(result) -> list:
    return [c.outer.polygon for c in result.clusters]


def _register(cls, make, known: frozenset = frozenset()):
    for dxf in _sources():
        test = make(dxf)
        if dxf.stem in known:
            test = unittest.expectedFailure(test)
        setattr(cls, case_name(dxf), test)


# ---------------------------------------------------------------------------

class TestPolygonValidity(unittest.TestCase):
    """Ogni outer e ogni inner è una forma semplice di area positiva."""


def _make_validity_test(dxf: Path):
    def test(self):
        _, result = _read(dxf)
        for ci, cluster in enumerate(result.clusters):
            for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in
                                                               enumerate(cluster.inners)]:
                self.assertTrue(contour.polygon.is_valid, f"{dxf.stem}.cluster[{ci}].{name} non è semplice")
                self.assertGreater(contour.polygon.area, 0, f"{dxf.stem}.cluster[{ci}].{name} ha area nulla")
    return test


_register(TestPolygonValidity, _make_validity_test)


class TestContoursAreRings(unittest.TestCase):
    """I segmenti di ogni outer e di ogni inner sono un anello testa-coda:
    ognuno parte dove finisce il precedente, l'ultimo chiude sul primo (D118).
    È quello che un chiamante trova in `contour.segments` e passa alle
    primitive di `topo.geometry.regions` senza riordinarlo."""


def _make_ring_test(dxf: Path):
    def test(self):
        from topo.core.primitives.segments import segment_endpoints
        _, result = _read(dxf)
        for ci, cluster in enumerate(result.clusters):
            for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in
                                                               enumerate(cluster.inners)]:
                segs = contour.segments
                for k, seg in enumerate(segs):
                    end = segment_endpoints(seg)[1]
                    start = segment_endpoints(segs[(k + 1) % len(segs)])[0]
                    self.assertLessEqual(math.dist(end, start), DEFAULT_TOLERANCE,
                                         f"{dxf.stem}.cluster[{ci}].{name}: il segmento {k} "
                                         f"finisce a {end}, il successivo parte da {start}")
    return test


_register(TestContoursAreRings, _make_ring_test)


class TestNothingDropped(unittest.TestCase):
    """Ogni pezzo di geometria in ingresso finisce in uscita — nei segmenti di
    un contorno o nel trash — entro la tolleranza di heal: chiudere un gap o
    riparare un angolo sposta un estremo fino a lì, non oltre."""


def _make_dropped_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        lost = uncovered(doc, result, tol)
        self.assertLessEqual(lost.length, DEFAULT_TOLERANCE,
                             f"{dxf.stem}: {lost.length:.3f} mm di geometria in ingresso non stanno "
                             f"in nessuna uscita (vicino a {lost.representative_point()})")
    return test


_register(TestNothingDropped, _make_dropped_test)


class TestOutOnce(unittest.TestCase):
    """Ogni pezzo d'ingresso esce una volta, o in un contorno o in `loose`
    (D137, D158): nessun tratto di `loose` corre lungo un contorno. Alla
    tolleranza del disegno e su OUT_ONCE_TOLERANCES (un'altra tolleranza
    cambia quali gap chiude e quali angoli ripara)."""


def _make_out_once_test(dxf: Path):
    def test(self):
        for tol in sorted({_tolerance(dxf), *OUT_ONCE_TOLERANCES}):
            with self.subTest(tolerance=tol):
                doc, result = _read(dxf, tol)
                check = lambda: self.assertEqual(along_contours(result, doc), [],
                                                 f"{dxf.stem} a tol {tol}: tratti di loose lungo un contorno")
                gate = KNOWN_TWICE.get((drawing_key(dxf), tol))
                if gate:
                    known_defect(self, f"{drawing_key(dxf)} a tol {tol}", gate, check)
                check()
    return test


_register(TestOutOnce, _make_out_once_test)


def _vertices(contour) -> list:
    pts = []
    for seg in contour.segments:
        for p in (seg.discretize(DEFAULT_TOLERANCE)[0], seg.discretize(DEFAULT_TOLERANCE)[-1]):
            p = (float(p[0]), float(p[1]))
            if all(math.dist(p, q) > 1e-6 for q in pts):
                pts.append(p)
    return pts


def _is_chord(polygon, a, b, margin: float) -> bool:
    """`a`–`b` attraversa il materiale: dentro il poligono, tocca il bordo solo
    nei due estremi, e non ci corre vicino."""
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
    """Coppie di corde da un vertice comune ai due estremi di un lato dritto:
    così i due estremi del lato diventano nodi di diramazione. Prima i lati
    fuori dal convex hull (la parte concava), poi gli altri."""
    polygon = cluster.outer.polygon
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
    """Una corda fra due vertici di un outer, dentro il materiale, divide il
    pezzo in due facce ma non ne cambia il bordo: rifatto heal sull'outer più
    le corde, esce lo stesso outer e le corde vanno nel trash. È il caso di
    una linea di piega senza ruolo (MAP.md D111)."""


def _make_chords_test(dxf: Path):
    def test(self):
        _, result = _read(dxf)
        tol = _tolerance(dxf)
        broken = []
        for ci, cluster in enumerate(result.clusters):
            chords = _chords(cluster, tol)
            if not chords:
                continue
            again = topo.heal(topo.load_segments(list(cluster.outer.segments) + chords, tolerance=tol),
                               tolerance=tol)
            if again.cluster_count != 1 or _shape_differences([cluster.outer.polygon], _outers(again)):
                broken.append(f"cluster[{ci}] (+{len(chords)} corde): {again.cluster_count} cluster")
        check = lambda: self.assertEqual(broken, [], f"{dxf.stem}: le corde cambiano l'outer")
        if drawing_key(dxf) in KNOWN_CHORDS:
            known_defect(self, drawing_key(dxf), KNOWN_CHORDS[drawing_key(dxf)], check)
        check()
    return test


_register(TestChordsKeepTheOuter, _make_chords_test)


class TestRolesOfChordsDontMatter(unittest.TestCase):
    """Gli edge non strutturali di un file (pieghe dal layer) che attraversano
    un outer da bordo a bordo, letti invece senza ruolo, non cambiano gli
    outer: la geometria da sola dice che sono corde. Salta i disegni senza
    edge del genere."""


def _crossing_edges(doc, result, tol: float) -> set:
    ids = set()
    for edge in doc.edges:
        if edge.role == "unknown" or not isinstance(edge.segment, LineSeg):
            continue
        a, b = Point(edge.start[:2]), Point(edge.end[:2])
        for cluster in result.clusters:
            ring = cluster.outer.polygon.exterior
            if ring.distance(a) <= tol and ring.distance(b) <= tol and \
                    cluster.outer.polygon.contains(LineString([edge.start[:2], edge.end[:2]]).interpolate(0.5, True)):
                ids.add(id(edge))
                break
    return ids


def _make_roles_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        ids = _crossing_edges(doc, result, tol)
        if not ids:
            self.skipTest("nessun edge non strutturale da bordo a bordo")
        blind = Document(edges=[replace(e, role="unknown") if id(e) in ids else e for e in doc.edges],
                              source_path=doc.source_path, source_meta=doc.source_meta)
        again = topo.heal(blind, tolerance=tol)
        self.assertEqual(again.cluster_count, result.cluster_count,
                         f"{dxf.stem}: {len(ids)} edge senza ruolo cambiano il numero di pezzi")
        self.assertEqual(_shape_differences(_outers(result), _outers(again)), [],
                         f"{dxf.stem}: {len(ids)} edge senza ruolo cambiano gli outer")
    return test


_register(TestRolesOfChordsDontMatter, _make_roles_test)


class TestRigidMotion(unittest.TestCase):
    """Ruotare, spostare lontano dall'origine o specchiare il disegno prima
    di heal dà gli stessi pezzi mossi, outer e inner: heal non dipende dal
    sistema di riferimento (né da "il punto più a sinistra", né da una
    griglia allineata agli assi, né dal verso in cui gira un contorno, né
    dalla grandezza delle coordinate)."""


def _make_motion_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        outers, inners = contours(result)
        for name, move, back, exact in MOTIONS:
            with self.subTest(motion=name):
                if not exact and dxf.stem in GAP_AT_TOLERANCE:
                    self.skipTest("gap largo esattamente la tolleranza: sul filo della soglia")
                again = topo.heal(moved(doc, move), tolerance=tol)
                outers_again, inners_again = ([back(p) for p in ps] for ps in contours(again))
                self.assertEqual(again.cluster_count, result.cluster_count, f"{dxf.stem}, {name}: cambia i pezzi")
                self.assertEqual(_shape_differences(outers, outers_again), [], f"{dxf.stem}, {name}: cambia gli outer")
                self.assertEqual(_shape_differences(inners, inners_again), [], f"{dxf.stem}, {name}: cambia i fori")
    return test


_register(TestRigidMotion, _make_motion_test)


class TestEdgeOrder(unittest.TestCase):
    """L'ordine in cui il file elenca le entità non conta: gli edge al
    contrario, e rimescolati con seed fissi, danno gli stessi pezzi."""


def _make_order_test(dxf: Path):
    def test(self):
        doc, result = _read(dxf)
        tol = _tolerance(dxf)
        for name, edges in orders(doc.edges):
            with self.subTest(order=name):
                again = topo.heal(Document(edges=edges, source_path=doc.source_path,
                                           source_meta=doc.source_meta), tolerance=tol)
                self.assertEqual(again.cluster_count, result.cluster_count,
                                 f"{dxf.stem}, {name}: l'ordine cambia i pezzi")
                self.assertEqual(_shape_differences(_outers(result), _outers(again)), [],
                                 f"{dxf.stem}, {name}: l'ordine cambia gli outer")
    return test


_register(TestEdgeOrder, _make_order_test, known=frozenset(KNOWN_ORDER_DEPENDENT))


class TestNeverRaises(unittest.TestCase):
    """Un ingresso degenere dà un risultato (non valido, o col pezzo nel
    trash), mai un'eccezione."""

    def test_coordinate_nan(self):
        square = topo.geometry.rectangle(100, 50)
        doc = topo.load_segments(square + [LineSeg(start=(float("nan"), 0.0), end=(10.0, 10.0))])
        result = topo.heal(doc)
        self.assertEqual(result.cluster_count, 1, "il rettangolo resta un pezzo")
        self.assertFalse(result.is_valid, "un edge senza posizione rende il risultato non valido")


if __name__ == "__main__":
    unittest.main()
