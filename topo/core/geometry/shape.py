"""
topo/core/geometry/shape.py
----------------------------
Fatti di forma di un contorno chiuso: cerchio, ellisse, stadio, rettangolo,
poligono. Elenco chiuso (MAP.md D136): una forma ha un nome solo se centro,
lunghezza, larghezza e angolo la determinano; il resto è `polygon` o `other`.
Le regole leggono le primitive come sono: un cerchio fatto di spline resta
`other`. Geometria pura, vale uguale su `faces()` e su `outlines()`. "circle" non vuol
dire foro: cosa sia quel cerchio lo dice chi legge il disegno o il processo
(MAP.md D68). I fatti fra più contorni (cerchi concentrici, archi attorno a
un cerchio, D91) stanno in `concentric.py`.
"""

from __future__ import annotations

from ...precision import ANGLE_BRACKET_DEG
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from shapely.geometry import Polygon

from .measure import Reach, chord_angle_deg, segment_length, SAME_POINT
from .numeric import golden_min
from ..primitives.line import LineSeg
from ..primitives.mathseg import segment_endpoints, segment_is_closed
from ..primitives.conics import CircleSeg, EllipseSeg, is_arc

Point = Tuple[float, float]


class ShapeKind(str, Enum):
    """
    The six shapes of `contour_shape`, a closed and stable list (MAP.md D136).
    Inherits from str: `kind == "circle"` works and the text prints the value.
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



@dataclass(frozen=True)
class ContourShape:
    """
    kind:   a `ShapeKind` (circle | ellipse | stadium | rectangle | polygon | other)
    center: center (circle, ellipse, stadium, rectangle) or centroid (the rest)
    length: larger dimension — circle: diameter; ellipse: major axis;
            stadium: overall length
    width:  smaller dimension — circle: diameter; ellipse: minor axis;
            stadium: 2 × radius
    angle:  degrees [0, 180) of the long axis; None for the circle
    sides:  contour segments after recomposition
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


def contour_shape(item) -> Optional[ContourShape]:
    """
    Shape of a closed contour (`Contour`, or any object with `.segments`, or
    the list of segments). None if there are no segments or if, in sequence,
    they do not close into a ring (D162).
    Consecutive segments on the same line or circle are first recomposed, so
    a side split by a node stays one side. Every measure of the shape agrees
    within `SAME_POINT`: a rectangle off by more is a polygon (D281).
    """
    segments = list(getattr(item, "segments", item) or [])
    if not segments or not _closes(segments):
        return None
    segments, _ = merge_runs(segments, [None] * len(segments))
    for rule in (_circle, _ellipse, _stadium, _rectangle):
        shape = rule(segments)
        if shape is not None:
            return shape
    return _generic(segments)


def _closes(segments) -> bool:
    """I segmenti, in fila, fanno un anello: ognuno parte dove finisce il
    precedente (in un verso o nell'altro) e l'ultimo torna al primo. Un pezzo
    aperto non ha forma (D162)."""
    if len(segments) == 1:
        return segment_is_closed(segments[0])
    ends = [segment_endpoints(s) for s in segments]
    for first, last in (ends[0], ends[0][::-1]):
        here = last
        for a, b in ends[1:]:
            if math.dist(here, a) <= SAME_POINT:
                here = b
            elif math.dist(here, b) <= SAME_POINT:
                here = a
            else:
                break
        else:
            if math.dist(here, first) <= SAME_POINT:
                return True
    return False


def _radius(seg) -> Optional[float]:
    """Raggio di un pezzo di cerchio; un'ellisse con gli assi uguali entro SAME_POINT è un cerchio."""
    if isinstance(seg, CircleSeg):
        return seg.radius
    if isinstance(seg, EllipseSeg) and abs(1.0 - seg.ratio) * math.hypot(*seg.major_axis) <= SAME_POINT:
        return math.hypot(*seg.major_axis)
    return None


def _circle(segments):
    radii = [_radius(s) for s in segments]
    if any(r is None for r in radii):
        return None
    s0, r0 = segments[0], radii[0]
    if any(abs(r - r0) > SAME_POINT or math.dist(s.center, s0.center) > SAME_POINT
           for s, r in zip(segments, radii)):
        return None
    sweep = sum(s._sweep() for s in segments)
    if abs(sweep - 2 * math.pi) * r0 > SAME_POINT:
        return None
    d = 2 * r0
    return ContourShape(CIRCLE, tuple(s0.center), d, d, None, len(segments))


def _ellipse(segments):
    """Pezzi della stessa ellisse (centro, semiassi, direzione dell'asse) per un giro intero."""
    if not all(isinstance(s, EllipseSeg) for s in segments):
        return None
    s0 = segments[0]
    a = math.hypot(*s0.major_axis)
    angle = math.degrees(math.atan2(s0.major_axis[1], s0.major_axis[0])) % 180
    for s in segments:
        if (abs(math.hypot(*s.major_axis) - a) > SAME_POINT or abs(s.ratio - s0.ratio) * a > SAME_POINT
                or math.dist(s.center, s0.center) > SAME_POINT
                or math.radians(_angle_diff(math.degrees(math.atan2(s.major_axis[1], s.major_axis[0])), angle)) * a > SAME_POINT):
            return None
    if abs(sum(s._sweep() for s in segments) - 2 * math.pi) * a > SAME_POINT:
        return None
    return ContourShape(ELLIPSE, tuple(s0.center), 2 * a, 2 * a * s0.ratio, angle, len(segments))


def _stadium(segments):
    if len(segments) != 4:
        return None
    k = 0 if is_arc(segments[0]) else 1
    a1, l1, a2, l2 = segments[k:] + segments[:k]
    if not (is_arc(a1) and is_arc(a2)
            and isinstance(l1, LineSeg) and isinstance(l2, LineSeg)):
        return None
    r = a1.radius
    if abs(a2.radius - r) > SAME_POINT:
        return None
    if any(abs(a._sweep() - math.pi) * r > SAME_POINT for a in (a1, a2)):
        return None
    axis = math.dist(a1.center, a2.center)
    if axis <= SAME_POINT:
        return None
    angle = chord_angle_deg(a1.center, a2.center)
    for line in (l1, l2):
        if abs(segment_length(line) - axis) > SAME_POINT:
            return None
        if math.radians(_angle_diff(chord_angle_deg(line.start, line.end), angle)) * segment_length(line) > SAME_POINT:
            return None
    center = ((a1.center[0] + a2.center[0]) / 2, (a1.center[1] + a2.center[1]) / 2)
    return ContourShape(STADIUM, center, axis + 2 * r, 2 * r, angle, 4)


def _rectangle(segments):
    if len(segments) != 4 or not all(isinstance(s, LineSeg) for s in segments):
        return None
    angles = [chord_angle_deg(s.start, s.end) for s in segments]
    lengths = [segment_length(s) for s in segments]
    # scarto dall'angolo retto lungo il più lungo dei due lati
    if any(math.radians(abs(_angle_diff(angles[i], angles[i - 1]) - 90)) * max(lengths[i], lengths[i - 1]) > SAME_POINT
           for i in range(4)):
        return None
    if abs(lengths[0] - lengths[2]) > SAME_POINT or abs(lengths[1] - lengths[3]) > SAME_POINT:
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
    sides = [_extent_along(reaches, _angle_direction(theta)), _extent_along(reaches, _angle_direction(theta + math.pi / 2))]
    i = 0 if sides[0] >= sides[1] else 1
    angle = math.degrees(theta + i * math.pi / 2) % 180
    c = polygon.centroid
    return ContourShape(kind, (c.x, c.y), sides[i], sides[1 - i], angle, len(segments))


_ANGLE_BRACKET = math.radians(ANGLE_BRACKET_DEG)


def _min_area_angle(reaches, theta: float) -> float:
    """
    Angolo del rettangolo d'area minima attorno alle primitive, cercato a
    ±1° dall'angolo del poligono inscritto: i due differiscono solo per la
    sagitta dei lati curvi. Sulle portate rifinite anche per le spline: sui
    soli campioni una forma quasi simmetrica (area piatta con l'angolo)
    sceglie un altro minimo locale. Costa tempo, voluto (MAP.md D156).
    """
    def area(t):
        return _extent_along(reaches, _angle_direction(t)) * _extent_along(reaches, _angle_direction(t + math.pi / 2))

    best, value = golden_min(area, theta - _ANGLE_BRACKET, theta + _ANGLE_BRACKET, iterations=30)
    return best if value < area(theta) else theta


def _angle_direction(t: float) -> Point:
    return (math.cos(t), math.sin(t))


def _extent_along(reaches, direction) -> float:
    """Ampiezza dell'insieme dei segmenti lungo `direction`, sulle primitive."""
    spans = [r(direction) for r in reaches]
    return max(hi for _lo, hi in spans) - min(lo for lo, _hi in spans)




def _angle_diff(a: float, b: float) -> float:
    """Differenza fra due direzioni modulo 180, in [0, 90]."""
    d = abs(a - b) % 180
    return min(d, 180 - d)


# ---------------------------------------------------------------------------
# Ricomposizione di un giro (usata qui e da outlines(), D95)
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
        if is_arc(s0):
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


_MERGE_EPS = SAME_POINT   # mm — il passo della vecchia griglia dei nodi (D113, D216)  # D268


def _continues(prev, prev_style, seg, style) -> bool:
    """`seg` prosegue `prev` sulla stessa curva, nello stesso verso?"""
    if style != prev_style or type(seg) is not type(prev):
        return False
    if is_arc(seg):
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
    if is_arc(prev):
        # le ampiezze si sommano: `seg.end_angle` da solo può essere l'angolo
        # di partenza di `prev` a meno di un giro (arco che passa per lo 0)
        sweep = prev._sweep() + seg._sweep()
        return CircleSeg(center=prev.center, radius=prev.radius, start_angle=prev.start_angle,
                      end_angle=prev.start_angle + (sweep if prev.ccw else -sweep), ccw=prev.ccw)
    return LineSeg(start=prev.start, end=seg.end)
