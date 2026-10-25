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
from shapely import STRtree, prepare
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from topo.core.geometry.measure import round_point
from topo.core.primitives.segments import DEFAULT_TOLERANCE, segment_endpoints
from topo.model.document import Document
from topo import to_shapely

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
TWICE = 1.9                           # ingresso lungo il tratto, in lunghezze del tratto: due pezzi


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


def scrambled(doc: Document) -> Document:
    """`doc` scritto in un altro modo, tutto insieme: edge rimescolati (seed 0),
    ruotati di ROTATION, spostati di FAR e specchiati. Una lettura sola al
    posto di una per moto e per ordine (D160): se la lettura dipende da una
    qualunque di queste cose, cambia anche qui; quale sia lo dice la
    diagnosi, che prova i moti e gli ordini uno alla volta."""
    edges = list(doc.edges)
    random.Random(0).shuffle(edges)
    return moved(replace(doc, edges=edges), lambda s: s.rotated(ROTATION).translated(*FAR).mirrored())


def unscrambled(poly):
    """Il poligono shapely di una lettura di `scrambled(doc)` riportato nel
    sistema di `doc`."""
    poly = affinity.scale(poly, 1.0, -1.0, origin=(0, 0))
    poly = affinity.translate(poly, -FAR[0], -FAR[1])
    return affinity.rotate(poly, -ROTATION, origin=(0, 0), use_radians=True)


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


def _could_be_twins(a, b, band: float) -> bool:
    """Falso solo se la differenza simmetrica di `a` e `b` supera certo
    `band`: con gli ingombri disgiunti è la somma delle aree. Evita il
    confronto vero, che è il conto caro, fra i fori lontani (D160)."""
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    apart = ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0
    return not apart or a.area + b.area <= band


def shape_differences(before: list, after: list, band_per_mm: float) -> list:
    """I poligoni di `before` senza un gemello in `after` (differenza
    simmetrica sotto `band_per_mm` per mm di perimetro), accoppiati uno a uno."""
    free = list(after)
    missing = []
    for poly in before:
        band = poly.length * band_per_mm
        twin = next((other for other in free if _could_be_twins(poly, other, band)
                     and _differ_by(poly, other) <= band), None)
        if twin is None:
            missing.append(tuple(round(v, 2) for v in poly.bounds))
        else:
            free.remove(twin)
    return missing


def contours(result) -> list:
    """(outer, inner) di `result`: i poligoni degli outer e di tutti gli inner."""
    return ([to_shapely(c.outer) for c in result.clusters],
            [to_shapely(i) for c in result.clusters for i in c.inners])


class _Bands:
    """Le fasce larghe `distance` attorno a `geoms`, costruite una volta per
    geometria. La fascia attorno a un'unione è l'unione delle fasce: rifare il
    buffer dei vicini a ogni curva costava milioni di vertici su un disegno
    con molti lati corti (D160)."""

    def __init__(self, geoms: list, distance: float):
        self.distance = distance
        self.tree = STRtree(geoms)
        self.bands = [g.buffer(distance) for g in geoms]
        prepare(self.bands)

    def near(self, curve):
        """La fascia attorno alle geometrie vicine a `curve`, o None se
        nessuna è vicina. Dentro `distance` da `curve` è la fascia attorno a
        tutte: le altre non la raggiungono."""
        near = self.tree.query(curve, predicate="dwithin", distance=self.distance)
        if len(near) == 0:
            return None
        # il caso normale: la curva sta tutta nella fascia di un vicino solo
        for i in near:
            if self.bands[i].covers(curve):
                return self.bands[i]
        return unary_union([self.bands[i] for i in near])


def _rims(result) -> list:
    return [geometry(s) for c in result.clusters for ct in [c.outer] + c.inners for s in ct.segments]


def along_contours(result, doc: Document) -> list:
    """I tratti di `result.loose` che corrono lungo un contorno (entro
    ON_CONTOUR per più di ALONG mm): (lunghezza, punto) per ognuno. Ogni
    pezzo d'ingresso esce una volta — o in un contorno o in `loose` (D137) —
    quindi la lista è vuota. Un tratto dove l'ingresso di `doc` ha due pezzi
    (un cerchio ripassato da una polilinea) non conta: sono due pezzi, e
    ognuno esce una volta."""
    rims = _rims(result)
    if not rims:
        return []
    bands = _Bands(rims, ON_CONTOUR)
    inputs = [geometry(e.segment) for e in doc.edges]
    tree = STRtree(inputs)
    found = []
    for curve in result.loose:
        for segment in curve.segments:
            loose = geometry(segment)
            band = bands.near(loose)
            if band is None:
                continue
            shared = loose.intersection(band)
            for piece in getattr(shared, "geoms", [shared]):
                if piece.length > ALONG and not _twice_in_input(piece, inputs, tree):
                    point = piece.representative_point()
                    found.append((round(piece.length, 2), (round(point.x, 1), round(point.y, 1))))
    return found


def _twice_in_input(piece, inputs: list, tree) -> bool:
    """Vero se l'ingresso copre `piece` almeno due volte: la sua lunghezza
    entro ON_CONTOUR da `piece` è quasi il doppio di `piece`."""
    zone = piece.buffer(ON_CONTOUR)
    near = tree.query(zone, predicate="intersects")
    covered = sum(inputs[int(i)].intersection(zone).length for i in near)
    return covered >= TWICE * piece.length


def uncovered(doc: Document, result, distance: float):
    """La geometria in ingresso di `doc` più lontana di `distance` da ogni
    uscita di `result` (segmenti dei contorni e di `loose`)."""
    outputs = _rims(result) + [geometry(s) for f in result.loose for s in f.segments]
    # un ingresso uscito tale e quale (nei due versi) è coperto: si salta il
    # conto della fascia, che è il caro, per quasi ogni edge (D160)
    same = {tuple(g.coords) for g in outputs} | {tuple(g.coords)[::-1] for g in outputs}
    bands = _Bands(outputs, distance)
    lost = []
    for edge in doc.edges:
        curve = geometry(edge.segment)
        if tuple(curve.coords) in same:
            continue
        band = bands.near(curve)
        lost.append(curve if band is None else curve.difference(band))
    return unary_union(lost)


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
