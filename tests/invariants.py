"""
tests/invariants.py
-------------------
Gli attrezzi comuni alle invarianti delle due letture (test_heal_invariants.py,
test_island_invariants.py, MAP.md D143, D158):

- quello che si fa a un disegno senza cambiarne la forma: i moti rigidi
  (rotazione, traslazione lontano dall'origine, specchio) e gli ordini diversi
  delle entità. Una lettura che dipende da uno di questi dipende da come il
  file è stato scritto, non dalla geometria;
- il confronto fra due letture (poligoni accoppiati uno a uno);
- i tratti di `loose` che corrono lungo un contorno: un pezzo d'ingresso
  uscito due volte.
"""

import math
import random
from dataclasses import replace

from shapely import affinity
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from topo.core.geometry.measure import round_point
from topo.core.primitives.segments import DEFAULT_TOLERANCE, segment_endpoints
from topo.model.document import Document

QUARTER = math.pi / 2                 # esatto sulla griglia dei nodi: nessun arrotondamento nuovo
ROTATION = 0.7                        # radianti, un angolo qualunque: i nodi tornano sulla griglia
# lontano dall'origine (2.5 km, 1.5 km), sulla griglia dei nodi: un double ha
# ancora ~10 cifre sotto il millimetro, ma ogni prodotto di coordinate
# (prodotti vettoriali, aree) perde 6-7 cifre rispetto all'origine
FAR = (2.5e6, -1.5e6)
SHUFFLES = 5                          # rimescolamenti per disegno, seed 0..SHUFFLES-1
GRID = 1e-6
# due discretizzazioni dello stesso tratto di curva distano al più così (ogni
# corda sta entro DEFAULT_TOLERANCE dalla curva, dallo stesso lato)
ON_CONTOUR = DEFAULT_TOLERANCE
# un tratto di `loose` entro ON_CONTOUR da un contorno per più di così corre
# lungo il contorno: un incrocio ci resta solo sotto ~1° (2·ON_CONTOUR/sin θ),
# una tangenza solo con raggio oltre ~12 mm (2·√(2·R·ON_CONTOUR))
ALONG = 1.0


def moved(doc: Document, move) -> Document:
    """`doc` con ogni segmento passato per `move` (segmento → segmento) e i
    nodi sulla griglia del caricamento, come `topo.rotate_document`."""
    edges = []
    for edge in doc.edges:
        seg = move(edge.segment)
        start, end = segment_endpoints(seg)
        edges.append(replace(edge, segment=seg, start=round_point(start), end=round_point(end)))
    return replace(doc, edges=edges)


# (nome, moto del segmento, moto inverso di un poligono shapely, esatto sulla griglia)
MOTIONS = [
    ("rotation", lambda s: s.rotated(ROTATION),
     lambda p: affinity.rotate(p, -ROTATION, origin=(0, 0), use_radians=True), False),
    ("quarter turn", lambda s: s.rotated(QUARTER),
     lambda p: affinity.rotate(p, -QUARTER, origin=(0, 0), use_radians=True), True),
    ("far", lambda s: s.translated(*FAR),
     lambda p: affinity.translate(p, -FAR[0], -FAR[1]), True),
    ("mirror", lambda s: s.mirrored(),
     lambda p: affinity.scale(p, 1.0, -1.0, origin=(0, 0)), True),
]


def orders(edges: list) -> list:
    """(nome, edge) per ogni ordine provato: al contrario, più SHUFFLES
    rimescolamenti riproducibili."""
    result = [("reversed", list(reversed(edges)))]
    for seed in range(SHUFFLES):
        shuffled = list(edges)
        random.Random(seed).shuffle(shuffled)
        result.append((f"seed {seed}", shuffled))
    return result


def geometry(segment):
    """Il segmento come geometria shapely, discretizzato a DEFAULT_TOLERANCE."""
    pts = segment.discretize(DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


def _differ_by(a, b) -> float:
    """Area della differenza simmetrica di `a` e `b`, sulla griglia del micron:
    GEOS, su due poligoni uguali a 1e-13 con vertici quasi allineati, può dare
    come differenza l'unione intera. Infinita se GEOS non sa calcolarla (un
    poligono non semplice): due forme che non si confrontano non sono gemelle."""
    try:
        return a.symmetric_difference(b, grid_size=GRID).area
    except GEOSException:
        return math.inf


def shape_differences(before: list, after: list, band_per_mm: float) -> list:
    """I poligoni di `before` senza un gemello in `after` (differenza
    simmetrica sotto `band_per_mm` per mm di perimetro), accoppiati uno a uno."""
    free = list(after)
    missing = []
    for poly in before:
        band = poly.length * band_per_mm
        twin = next((other for other in free if _differ_by(poly, other) <= band), None)
        if twin is None:
            missing.append(tuple(round(v, 2) for v in poly.bounds))
        else:
            free.remove(twin)
    return missing


def contours(result) -> list:
    """(outer, inner) di `result`: i poligoni degli outer e di tutti gli inner."""
    return ([c.outer.polygon for c in result.clusters],
            [i.polygon for c in result.clusters for i in c.inners])


def along_contours(result) -> list:
    """I tratti di `result.loose` che corrono lungo un contorno (entro
    ON_CONTOUR per più di ALONG mm): (lunghezza, punto) per ognuno. Ogni
    pezzo d'ingresso esce una volta — o in un contorno o in `loose` (D137) —
    quindi la lista è vuota."""
    rims = [geometry(s) for c in result.clusters for ct in [c.outer] + c.inners for s in ct.segments]
    if not rims:
        return []
    band = unary_union(rims).buffer(ON_CONTOUR)
    found = []
    for curve in result.loose:
        for segment in curve.segments:
            shared = geometry(segment).intersection(band)
            for piece in getattr(shared, "geoms", [shared]):
                if piece.length > ALONG:
                    point = piece.representative_point()
                    found.append((round(piece.length, 2), (round(point.x, 1), round(point.y, 1))))
    return found


def known_defect(test, where: str, gate: str, check) -> None:
    """Esegue `check()` per un caso di un difetto noto, aperto nel cancello
    (`gate`, TODO.md): deve fallire, e il caso esce come skip con la voce del
    cancello. Se passa il difetto è risolto e il test fallisce finché il caso
    non esce dalla lista."""
    try:
        check()
    except AssertionError:
        test.skipTest(f"difetto noto, {gate}: {where}")
    test.fail(f"{where} passa: il difetto di {gate} è risolto, togli il caso dalla lista")
