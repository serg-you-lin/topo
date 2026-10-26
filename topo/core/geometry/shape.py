"""
topo/core/geometry/shape.py
----------------------------
Fatti di forma di un contorno chiuso: cerchio, ellisse, stadio, rettangolo,
poligono. Elenco chiuso (MAP.md D136): una forma ha un nome solo se centro,
lunghezza, larghezza e angolo la determinano; il resto è `polygon` o `other`.
Le regole leggono le primitive come sono: un cerchio fatto di spline resta
`other`. Geometria pura, vale uguale su `heal()` e su `island()`. "circle" non vuol
dire foro: cosa sia quel cerchio lo dice chi legge il disegno o il processo
(MAP.md D68).
In coda i fatti fra più contorni: cerchi concentrici, archi attorno a un
cerchio (MAP.md D91).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from shapely.geometry import Polygon

from .measure import Reach, chord_angle_deg, golden_max
from ..primitives.segments import ArcSeg, CircleSeg, EllipseSeg, LineSeg, segment_endpoints, segment_is_closed

Point = Tuple[float, float]


class ShapeKind(str, Enum):
    """
    Le sei forme di `contour_shape`, elenco chiuso e stabile (MAP.md D136).
    Eredita da str: `kind == "circle"` funziona e il testo stampa il valore.
    """
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    STADIUM = "stadium"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return format(self.value, spec)


CIRCLE = ShapeKind.CIRCLE
ELLIPSE = ShapeKind.ELLIPSE
STADIUM = ShapeKind.STADIUM
RECTANGLE = ShapeKind.RECTANGLE
POLYGON = ShapeKind.POLYGON
OTHER = ShapeKind.OTHER

SHAPE_TOLERANCE = 0.01       # frazione della dimensione del contorno
ANGLE_TOLERANCE_DEG = 1.0


@dataclass(frozen=True)
class ContourShape:
    """
    kind:   un `ShapeKind` (circle | ellipse | stadium | rectangle | polygon | other)
    center: centro (cerchio, ellisse, stadio, rettangolo) o baricentro (il resto)
    length: dimensione maggiore — cerchio: diametro; ellisse: asse maggiore;
            stadio: fuori tutto
    width:  dimensione minore — cerchio: diametro; ellisse: asse minore;
            stadio: 2 × raggio
    angle:  gradi [0, 180) dell'asse lungo; None per il cerchio
    sides:  segmenti del contorno dopo la ricomposizione
    """
    kind: ShapeKind
    center: Point
    length: float
    width: float
    angle: Optional[float]
    sides: int

    @property
    def diameter(self) -> Optional[float]:
        return self.length if self.kind == CIRCLE else None

    def to_dict(self) -> dict:
        return {"kind": self.kind.value, "center": list(self.center),
                "length": round(self.length, 4), "width": round(self.width, 4),
                "angle": None if self.angle is None else round(self.angle, 4),
                "sides": self.sides}


def contour_shape(item, tolerance: float = SHAPE_TOLERANCE,
                  angle_tolerance: float = ANGLE_TOLERANCE_DEG) -> Optional[ContourShape]:
    """
    Forma di un contorno chiuso (`Contour`, o qualunque oggetto con
    `.segments`, o la lista di segmenti). None se non ci sono segmenti o se,
    in fila, non chiudono in anello (D162).
    I segmenti consecutivi sulla stessa retta o circonferenza sono prima
    ricomposti, così un lato spezzato da un nodo resta un lato.
    """
    segments = list(getattr(item, "segments", item) or [])
    if not segments or not _closes(segments, tolerance):
        return None
    segments, _ = merge_runs(segments, [None] * len(segments))
    for rule in (_circle, _ellipse, _stadium, _rectangle):
        shape = rule(segments, tolerance, angle_tolerance)
        if shape is not None:
            return shape
    return _generic(segments)


def _closes(segments, tol) -> bool:
    """I segmenti, in fila, fanno un anello: ognuno parte dove finisce il
    precedente (in un verso o nell'altro) e l'ultimo torna al primo. Un pezzo
    aperto non ha forma (D162)."""
    if len(segments) == 1:
        return segment_is_closed(segments[0])
    ends = [segment_endpoints(s) for s in segments]
    xs = [p[0] for e in ends for p in e]
    ys = [p[1] for e in ends for p in e]
    eps = tol * math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    for first, last in (ends[0], ends[0][::-1]):
        here = last
        for a, b in ends[1:]:
            if math.dist(here, a) <= eps:
                here = b
            elif math.dist(here, b) <= eps:
                here = a
            else:
                break
        else:
            if math.dist(here, first) <= eps:
                return True
    return False


def _radius(seg, tol) -> Optional[float]:
    """Raggio di un pezzo di cerchio; un'ellisse ad assi uguali è un cerchio, esattamente."""
    if isinstance(seg, (ArcSeg, CircleSeg)):
        return seg.radius
    if isinstance(seg, EllipseSeg) and abs(1.0 - seg.ratio) <= tol:
        return math.hypot(*seg.major_axis)
    return None


def _circle(segments, tol, _angle_tol):
    radii = [_radius(s, tol) for s in segments]
    if any(r is None for r in radii):
        return None
    s0, r0 = segments[0], radii[0]
    if any(abs(r - r0) > tol * r0 or math.dist(s.center, s0.center) > tol * r0
           for s, r in zip(segments, radii)):
        return None
    sweep = sum(2 * math.pi if isinstance(s, CircleSeg) else s._sweep() for s in segments)
    if abs(sweep - 2 * math.pi) > math.radians(1.0):
        return None
    d = 2 * r0
    return ContourShape(CIRCLE, tuple(s0.center), d, d, None, len(segments))


def _ellipse(segments, tol, angle_tol):
    """Pezzi della stessa ellisse (centro, semiassi, direzione dell'asse) per un giro intero."""
    if not all(isinstance(s, EllipseSeg) for s in segments):
        return None
    s0 = segments[0]
    a = math.hypot(*s0.major_axis)
    angle = math.degrees(math.atan2(s0.major_axis[1], s0.major_axis[0])) % 180
    for s in segments:
        if (abs(math.hypot(*s.major_axis) - a) > tol * a or abs(s.ratio - s0.ratio) > tol
                or math.dist(s.center, s0.center) > tol * a
                or _angle_diff(math.degrees(math.atan2(s.major_axis[1], s.major_axis[0])), angle) > angle_tol):
            return None
    if abs(sum(s._sweep() for s in segments) - 2 * math.pi) > math.radians(1.0):
        return None
    return ContourShape(ELLIPSE, tuple(s0.center), 2 * a, 2 * a * s0.ratio, angle, len(segments))


def _stadium(segments, tol, angle_tol):
    if len(segments) != 4:
        return None
    k = 0 if isinstance(segments[0], ArcSeg) else 1
    a1, l1, a2, l2 = segments[k:] + segments[:k]
    if not (isinstance(a1, ArcSeg) and isinstance(a2, ArcSeg)
            and isinstance(l1, LineSeg) and isinstance(l2, LineSeg)):
        return None
    r = a1.radius
    if abs(a2.radius - r) > tol * r:
        return None
    if any(abs(a._sweep() - math.pi) > math.radians(angle_tol) for a in (a1, a2)):
        return None
    axis = math.dist(a1.center, a2.center)
    if axis <= tol * r:
        return None
    angle = chord_angle_deg(a1.center, a2.center)
    for line in (l1, l2):
        if abs(_length(line) - axis) > tol * (axis + 2 * r):
            return None
        if _angle_diff(chord_angle_deg(line.start, line.end), angle) > angle_tol:
            return None
    center = ((a1.center[0] + a2.center[0]) / 2, (a1.center[1] + a2.center[1]) / 2)
    return ContourShape(STADIUM, center, axis + 2 * r, 2 * r, angle, 4)


def _rectangle(segments, tol, angle_tol):
    if len(segments) != 4 or not all(isinstance(s, LineSeg) for s in segments):
        return None
    angles = [chord_angle_deg(s.start, s.end) for s in segments]
    if any(abs(_angle_diff(angles[i], angles[i - 1]) - 90) > angle_tol for i in range(4)):
        return None
    lengths = [_length(s) for s in segments]
    size = max(lengths)
    if abs(lengths[0] - lengths[2]) > tol * size or abs(lengths[1] - lengths[3]) > tol * size:
        return None
    i = 0 if lengths[0] >= lengths[1] else 1
    xs = [s.start[0] for s in segments]
    ys = [s.start[1] for s in segments]
    center = (sum(xs) / 4, sum(ys) / 4)
    return ContourShape(RECTANGLE, center, lengths[i], lengths[1 - i], angles[i], 4)


def _generic(segments):
    kind = POLYGON if len(segments) >= 3 and all(isinstance(s, LineSeg) for s in segments) else OTHER
    points = [p for s in segments for p in s.discretize()]
    polygon = Polygon(points) if len(points) >= 3 else Polygon()
    box = polygon.minimum_rotated_rectangle
    if box.geom_type != "Polygon":
        return None
    # il poligono dà l'orientamento di partenza del rettangolo minimo; le misure
    # sono la portata delle primitive, e per una curva anche l'angolo si
    # rifinisce su di loro (MAP.md D156)
    corners = list(box.exterior.coords)[:4]
    theta = math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0])
    reaches = [Reach(s) for s in segments]
    if kind == OTHER:
        theta = _min_area_angle(reaches, theta)
    sides = [_reach(reaches, _unit(theta)), _reach(reaches, _unit(theta + math.pi / 2))]
    i = 0 if sides[0] >= sides[1] else 1
    angle = math.degrees(theta + i * math.pi / 2) % 180
    c = polygon.centroid
    return ContourShape(kind, (c.x, c.y), sides[i], sides[1 - i], angle, len(segments))


_ANGLE_BRACKET = math.radians(1.0)


def _min_area_angle(reaches, theta: float) -> float:
    """
    Angolo del rettangolo d'area minima attorno alle primitive, cercato a
    ±1° dall'angolo del poligono inscritto: i due differiscono solo per la
    sagitta dei lati curvi. Sulle portate rifinite anche per le spline: sui
    soli campioni una forma quasi simmetrica (area piatta con l'angolo)
    sceglie un altro minimo locale. Costa tempo, voluto (MAP.md D156).
    """
    def neg_area(t):
        return -_reach(reaches, _unit(t)) * _reach(reaches, _unit(t + math.pi / 2))

    best, value = golden_max(neg_area, theta - _ANGLE_BRACKET, theta + _ANGLE_BRACKET, iterations=30)
    return best if value > neg_area(theta) else theta


def _unit(t: float) -> Point:
    return (math.cos(t), math.sin(t))


def _reach(reaches, direction) -> float:
    """Ampiezza dell'insieme dei segmenti lungo `direction`, sulle primitive."""
    spans = [r(direction) for r in reaches]
    return max(hi for _lo, hi in spans) - min(lo for lo, _hi in spans)


def _length(line: LineSeg) -> float:
    return math.dist(line.start, line.end)


def _angle_diff(a: float, b: float) -> float:
    """Differenza fra due direzioni modulo 180, in [0, 90]."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


# ---------------------------------------------------------------------------
# Cerchi concentrici, archi attorno a un cerchio (MAP.md D91)
# ---------------------------------------------------------------------------
# Fatti geometrici fra più contorni: "questi cerchi hanno lo stesso centro",
# "questo arco gira attorno a quel cerchio". Cosa siano (svasatura, sede,
# cresta di un filetto) e con che soglie lo decide il consumatore.

CONCENTRIC_TOLERANCE = 0.1   # distanza massima fra i centri, unità del disegno


@dataclass(frozen=True)
class ConcentricGroup:
    """
    Contorni circolari con lo stesso centro, dal raggio minore al maggiore.

    center: centro del cerchio più piccolo (il riferimento del gruppo)
    items:  i contorni, nell'ordine dei raggi
    shapes: la `ContourShape` di ciascuno, nello stesso ordine
    """
    center: Point
    items: tuple
    shapes: Tuple[ContourShape, ...]

    @property
    def diameters(self) -> Tuple[float, ...]:
        return tuple(s.length for s in self.shapes)


def concentric_groups(items, tolerance: float = CONCENTRIC_TOLERANCE) -> list[ConcentricGroup]:
    """
    Partizione dei contorni circolari di `items` per centro: ogni cerchio sta
    in un solo gruppo, anche da solo. Un cerchio entra nel gruppo il cui
    centro dista al più `tolerance` dal suo; i non circolari non compaiono.
    Gruppi ordinati per centro (x, y).
    """
    circles = [(item, shape) for item in items
               if (shape := contour_shape(item)) is not None and shape.kind == CIRCLE]
    circles.sort(key=lambda c: (c[1].length, c[1].center))
    groups: list[list] = []
    for item, shape in circles:
        group = next((g for g in groups if math.dist(g[0][1].center, shape.center) <= tolerance), None)
        if group is None:
            groups.append([(item, shape)])
        else:
            group.append((item, shape))
    out = [ConcentricGroup(tuple(g[0][1].center), tuple(i for i, _ in g), tuple(s for _, s in g))
           for g in groups]
    return sorted(out, key=lambda g: g.center)


@dataclass(frozen=True)
class ArcAround:
    """
    Un arco concentrico a un cerchio e più grande di lui.

    arc:          l'`ArcSeg`
    sweep:        angolo spazzato, in gradi
    radius_ratio: raggio dell'arco / raggio del cerchio (> 1)
    """
    arc: ArcSeg
    sweep: float
    radius_ratio: float


def arcs_around(center: Point, radius: float, arcs,
                tolerance: float = CONCENTRIC_TOLERANCE) -> list[ArcAround]:
    """
    Gli archi di `arcs` col centro entro `tolerance` da `center` e raggio
    maggiore di `radius`, dal più vicino al cerchio al più lontano.
    """
    out = [ArcAround(a, math.degrees(a._sweep()), a.radius / radius) for a in arcs
           if isinstance(a, ArcSeg) and a.radius > radius and math.dist(a.center, center) <= tolerance]
    return sorted(out, key=lambda a: a.radius_ratio)


# ---------------------------------------------------------------------------
# Ricomposizione di un giro (usata qui e da island(), D95)
# ---------------------------------------------------------------------------

def merge_runs(segments: list, styles: list):
    """
    Segmenti consecutivi di un giro chiuso sulla stessa circonferenza (o
    retta), nello stesso verso e con lo stesso stile, fusi in uno: il merge
    di `_normalize` toglie i doppioni prima del taglio, questo ricompone
    dopo quello che `split_at_crossings` ha spezzato. Un giro fatto tutto di
    archi dello stesso cerchio torna un CircleSeg.
    """
    n = len(segments)
    if n < 2 or len(styles) != n:
        return segments, styles
    same = [_continues(segments[i - 1], styles[i - 1], segments[i], styles[i]) for i in range(n)]
    if all(same):
        s0 = segments[0]
        if isinstance(s0, ArcSeg):
            return [CircleSeg(center=s0.center, radius=s0.radius)], [styles[0]]
        return segments, styles
    k = same.index(False)          # il giro riparte da un inizio di tratto
    segments, styles, same = segments[k:] + segments[:k], styles[k:] + styles[:k], same[k:] + same[:k]
    out_s, out_st = [], []
    for seg, st, cont in zip(segments, styles, same):
        if cont:
            out_s[-1] = _joined(out_s[-1], seg)
        else:
            out_s.append(seg)
            out_st.append(st)
    return out_s, out_st


_MERGE_EPS = 1e-3   # mm — la griglia dei nodi (NODE_DECIMALS)


def _continues(prev, prev_style, seg, style) -> bool:
    """`seg` prosegue `prev` sulla stessa curva, nello stesso verso?"""
    if style != prev_style or type(seg) is not type(prev):
        return False
    if isinstance(seg, ArcSeg):
        return (seg.ccw == prev.ccw and abs(seg.radius - prev.radius) < _MERGE_EPS
                and math.dist(seg.center, prev.center) < _MERGE_EPS)
    if isinstance(seg, LineSeg):
        (ax, ay), (bx, by) = prev.start, prev.end
        length = math.hypot(bx - ax, by - ay)
        if length < _MERGE_EPS:
            return False
        ex, ey = seg.end
        cross = (bx - ax) * (ey - ay) - (by - ay) * (ex - ax)
        dot = (bx - ax) * (ex - bx) + (by - ay) * (ey - by)
        return abs(cross) / length < _MERGE_EPS and dot > 0
    return False


def _joined(prev, seg):
    if isinstance(prev, ArcSeg):
        # le ampiezze si sommano: `seg.end_angle` da solo può essere l'angolo
        # di partenza di `prev` a meno di un giro (arco che passa per lo 0)
        sweep = prev._sweep() + seg._sweep()
        return ArcSeg(center=prev.center, radius=prev.radius, start_angle=prev.start_angle,
                      end_angle=prev.start_angle + (sweep if prev.ccw else -sweep), ccw=prev.ccw)
    return LineSeg(start=prev.start, end=seg.end)
