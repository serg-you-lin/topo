"""
topo/core/primitives/fitting.py
--------------------------------
Da una sequenza di punti ordinata e densa (un contorno tracciato da un
raster, una curva scritta a punti da un CAD) a primitive pulite: linee dove
è dritta, archi dove è a raggio costante, spline solo per il resto, spigoli
vivi dove svolta — l'inverso della discretizzazione (MAP.md D141).

    simplify_points — l'unico ingresso

Tre garanzie, tutte geometriche: ogni punto dato sta entro `tolerance` dalle
primitive; le primitive sono una catena testa-coda (una sequenza aperta
parte e finisce esattamente nei suoi estremi, una chiusa si richiude); una
primitiva è una linea o un arco solo se i suoi punti lo sono entro
`tolerance`. Le soglie sono sempre del chiamante.

La matematica sui punti (Douglas-Peucker, spigoli per svolta, cerchio per tre
punti, b-spline approssimante) vive in `core/geometry/points.py`; qui c'è
l'orchestrazione: spezzare sugli spigoli, decidere linea, arco o spline.
Nata in smoother (`smoother/fitting.py`, smoother D21), provata sulle lettere
di un'insegna tracciata, portata qui perché è ricostruzione geometrica
generica (D33, D36).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple, Union

from .segments import ArcSeg, CircleSeg, LineSeg, BSplineSeg, Point
from ..geometry.points import (
    DEFAULT_DUPLICATE_TOLERANCE, approximate_bspline, circle_through, douglas_peucker,
    drop_duplicate_points, even_spacing, fit_circle_kasa, offset_from_line, turn_corners,
)

Primitive = Union[LineSeg, ArcSeg, CircleSeg, BSplineSeg]

DEFAULT_CORNER_TURN_DEG = 35.0
DEFAULT_SPLINE_DEGREE = 3


@dataclass
class _Part:
    """Un pezzo della sequenza: `kind` "line" o "curve", coi punti che copre (estremi condivisi coi vicini)."""
    kind: str
    points: List[Point]


def _within(points: List[Point], tolerance: float) -> bool:
    """Tutti i punti entro `tolerance` dalla corda primo-ultimo."""
    a, b = points[0], points[-1]
    return all(abs(offset_from_line(p, a, b)) <= tolerance for p in points[1:-1])


def _signed_turn(a: Point, b: Point, c: Point) -> float:
    """Svolta con segno (gradi) in `b` andando da `a` a `c`: positiva a sinistra."""
    v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    return math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1]))


def _split_stretch(points: List[Point], tolerance: float, scale: float, corner_turn_deg: float,
                   arcs: bool) -> List[_Part]:
    """
    Un tratto senza spigoli: tutto entro `tolerance` dalla corda -> una linea;
    tutto entro `tolerance` da un arco per i suoi estremi (con `arcs`) -> un
    arco. Altrimenti i lati Douglas-Peucker lunghi almeno `scale` diventano
    linee, tranne quelli che stanno DENTRO una curva — svolta piccola e nello
    stesso verso ai capi che hanno un vicino, e non molto più lunghi dei
    vicini: sono faccette di una curva, non un lato dritto (il lato dritto di
    una O squadrata è lungo più del doppio dei vicini).
    """
    if _within(points, tolerance):
        return [_Part("line", points)]
    if arcs and len(points) >= 4 and _arc_through_ends(points, tolerance) is not None:
        return [_Part("curve", points)]
    dp = douglas_peucker(points, tolerance)
    sides = list(zip(dp, dp[1:]))
    lengths = [math.dist(points[i], points[j]) for i, j in sides]

    def is_line(e: int) -> bool:
        if lengths[e] < scale:
            return False
        turns, neighbours = [], []
        i, j = sides[e]
        if e > 0:
            turns.append(_signed_turn(points[sides[e - 1][0]], points[i], points[j]))
            neighbours.append(lengths[e - 1])
        if e < len(sides) - 1:
            turns.append(_signed_turn(points[i], points[j], points[sides[e + 1][1]]))
            neighbours.append(lengths[e + 1])
        if not turns:
            return True
        same_way = all(t > 0 for t in turns) or all(t < 0 for t in turns)
        inside_curve = same_way and max(abs(t) for t in turns) < corner_turn_deg
        return not inside_curve or lengths[e] >= 2 * max(neighbours)

    parts: List[_Part] = []
    curve_from = 0
    for e, (i, j) in enumerate(sides):
        if is_line(e):
            if i > curve_from:
                parts.append(_Part("curve", points[curve_from: i + 1]))
            parts.append(_Part("line", points[i: j + 1]))
            curve_from = j
    if curve_from < len(points) - 1:
        parts.append(_Part("curve", points[curve_from:]))
    return parts


def _arc_through_ends(points: List[Point], tolerance: float) -> Optional[ArcSeg]:
    """
    L'arco che passa esattamente per il primo e l'ultimo punto (e per quello a
    metà), se tutti i punti stanno entro `tolerance` dal suo cerchio. Passa
    per gli estremi e non ai minimi quadrati: un arco che li sposta lascia un
    buco con la primitiva accanto.
    """
    a, m, b = points[0], points[len(points) // 2], points[-1]
    circle = circle_through(a, m, b)
    if circle is None:
        return None
    center, radius = circle
    if any(abs(math.dist(center, p) - radius) > tolerance for p in points):
        return None
    # da a a b passando per m: antiorario se m sta a destra della corda a->b
    return ArcSeg(center=center, radius=radius,
                  start_angle=math.atan2(a[1] - center[1], a[0] - center[0]),
                  end_angle=math.atan2(b[1] - center[1], b[0] - center[0]),
                  ccw=offset_from_line(m, a, b) < 0)


def _fit_curve(points: List[Point], tolerance: float, arcs: bool, degree: int) -> List[Primitive]:
    """Un pezzo curvo: arco per gli estremi se basta (e `arcs`), altrimenti spline entro `tolerance` per gli estremi."""
    if len(points) <= degree:
        return [LineSeg(start=a, end=b) for a, b in zip(points, points[1:])]
    if arcs and len(points) >= 4:
        arc = _arc_through_ends(points, tolerance)
        if arc is not None:
            return [arc]
    control, knots = approximate_bspline(points, degree, tolerance)
    return [BSplineSeg(degree=degree, control_points=control, knots=knots)]


def _line_fit(points: List[Point]) -> Tuple[Point, Point]:
    """Retta ai minimi quadrati sui punti: (punto, direzione unitaria)."""
    n = len(points)
    cx, cy = sum(p[0] for p in points) / n, sum(p[1] for p in points) / n
    sxx = sum((p[0] - cx) ** 2 for p in points)
    syy = sum((p[1] - cy) ** 2 for p in points)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in points)
    angle = 0.5 * math.atan2(2 * sxy, sxx - syy)
    return (cx, cy), (math.cos(angle), math.sin(angle))


def _crossing(l1, l2) -> Optional[Point]:
    (p, d), (q, e) = l1, l2
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + t * d[0], p[1] + t * d[1])


def _length(points: List[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _line_turn(a: _Part, b: _Part) -> float:
    """Di quanti gradi svolta chi passa dalla linea `a` alla linea `b`."""
    (ax, ay), (bx, by) = a.points[0], a.points[-1]
    (cx, cy), (dx, dy) = b.points[0], b.points[-1]
    u, v = (bx - ax, by - ay), (dx - cx, dy - cy)
    return abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))


def _restore_corners(parts: List[_Part], closed: bool, tolerance: float, scale: float,
                     corner_turn_deg: float) -> List[_Part]:
    """
    Gli spigoli vivi che il campionamento ha smussato. Un pezzo curvo più
    corto di `scale` fra due linee che svoltano di almeno `corner_turn_deg` è
    l'arrotondamento di uno spigolo: sparisce. Poi fra due linee consecutive
    il vertice comune va nell'incrocio delle due rette ai minimi quadrati,
    dove sta lo spigolo vero, se cade entro `scale` dal vertice campionato e
    i punti delle due linee più lontani di `scale` da lì restano entro
    `tolerance`. Un estremo di una sequenza aperta non si sposta mai.
    """
    kept: List[_Part] = []
    n = len(parts)
    for k, part in enumerate(parts):
        before, after = parts[k - 1] if (closed or k > 0) else None, parts[(k + 1) % n] if (closed or k < n - 1) else None
        if (part.kind == "curve" and before is not None and after is not None and n > 2
                and before.kind == "line" and after.kind == "line" and before is not after
                and _length(part.points) < scale and _line_turn(before, after) >= corner_turn_deg):
            continue
        kept.append(part)
    parts = kept

    count = len(parts)
    for i in (range(count) if closed else range(count - 1)):
        a, b = parts[i], parts[(i + 1) % count]
        if a.kind != "line" or b.kind != "line" or a is b:
            continue
        joint_a, joint_b = a.points[-1], b.points[0]
        corner = _crossing(_line_fit(a.points), _line_fit(b.points))
        if corner is None or math.dist(corner, joint_a) > scale + math.dist(joint_a, joint_b):
            if joint_a != joint_b:   # rimasto un buco dove c'era l'arrotondamento: lo chiude il punto medio
                mid = ((joint_a[0] + joint_b[0]) / 2, (joint_a[1] + joint_b[1]) / 2)
                a.points, b.points = a.points[:-1] + [mid], [mid] + b.points[1:]
            continue
        far_a = [q for q in a.points[:-1] if math.dist(q, corner) > scale] + [corner]
        far_b = [corner] + [q for q in b.points[1:] if math.dist(q, corner) > scale]
        if _within(far_a, tolerance) and _within(far_b, tolerance):
            a.points, b.points = a.points[:-1] + [corner], [corner] + b.points[1:]
        elif joint_a != joint_b:
            mid = ((joint_a[0] + joint_b[0]) / 2, (joint_a[1] + joint_b[1]) / 2)
            a.points, b.points = a.points[:-1] + [mid], [mid] + b.points[1:]
    return parts


def _join_seam(prims: List[Primitive], tolerance: float) -> List[Primitive]:
    """
    Un contorno senza spigoli si apre in un punto qualunque: se il primo e
    l'ultimo pezzo sono lo stesso arco o la stessa retta, la giuntura non è
    un punto del contorno e i due tornano uno.
    """
    if len(prims) < 2:
        return prims
    last, first = prims[-1], prims[0]
    if isinstance(last, ArcSeg) and isinstance(first, ArcSeg) and last.ccw == first.ccw             and math.dist(last.center, first.center) <= tolerance and abs(last.radius - first.radius) <= tolerance:
        merged = ArcSeg(center=last.center, radius=last.radius, start_angle=last.start_angle,
                        end_angle=first.end_angle, ccw=last.ccw)
        return [merged] + prims[1:-1]
    if isinstance(last, LineSeg) and isinstance(first, LineSeg)             and abs(offset_from_line(last.end, last.start, first.end)) <= tolerance:
        return [LineSeg(start=last.start, end=first.end)] + prims[1:-1]
    return prims


def _to_primitives(parts: List[_Part], tolerance: float, arcs: bool, degree: int) -> List[Primitive]:
    out: List[Primitive] = []
    for part in parts:
        if part.kind == "line":
            if math.dist(part.points[0], part.points[-1]) > 0:
                out.append(LineSeg(start=part.points[0], end=part.points[-1]))
        else:
            out.extend(_fit_curve(part.points, tolerance, arcs, degree))
    return out


def simplify_points(
    points: Sequence[Point],
    tolerance: float,
    scale: float,
    closed: bool = True,
    corner_turn_deg: float = DEFAULT_CORNER_TURN_DEG,
    arcs: bool = True,
    spline_degree: int = DEFAULT_SPLINE_DEGREE,
) -> List[Primitive]:
    """
    Primitive (LineSeg/ArcSeg/CircleSeg/BSplineSeg) per la sequenza di punti
    `points`, in catena testa-coda, ogni punto entro `tolerance` da esse —
    tranne quelli entro `scale` da uno spigolo che il campionamento aveva
    smussato e che qui torna vivo.

    Args:
        points:           punti ordinati; `closed=True` un contorno (l'ultimo
                          torna al primo), `closed=False` un tratto aperto i cui
                          estremi restano esattamente dove sono
        tolerance:        scostamento massimo dai punti (unità dei punti)
        scale:            la lunghezza su cui si misura la svolta di uno spigolo:
                          un tratto dritto più corto resta parte di una curva,
                          una curva più corta fra due lati è uno spigolo smussato
        corner_turn_deg:  svolta minima (gradi) su `scale` per uno spigolo:
                          più bassa, più spigoli
        arcs:             False: niente archi né cerchi, solo linee e spline
        spline_degree:    grado delle spline
    """
    pts = [(float(p[0]), float(p[1])) for p in drop_duplicate_points(list(points), DEFAULT_DUPLICATE_TOLERANCE)]
    if closed and len(pts) > 1 and math.dist(pts[0], pts[-1]) <= DEFAULT_DUPLICATE_TOLERANCE:
        pts.pop()
    if len(pts) < 2:
        return []
    if len(pts) == 2:
        return [] if closed else [LineSeg(start=pts[0], end=pts[1])]
    pts = even_spacing(pts, closed)
    corners = turn_corners(pts, closed, corner_turn_deg, scale, tolerance)

    if closed and not corners:
        if arcs:
            fit = fit_circle_kasa(pts)
            if fit is not None and fit[2] <= tolerance:
                return [CircleSeg(center=fit[0], radius=fit[1])]
        # nessuno spigolo: si apre il giro nel punto più lontano dal primo
        far = max(range(len(pts)), key=lambda k: math.dist(pts[0], pts[k]))
        loop = pts[far:] + pts[:far] + [pts[far]]
        parts = _split_stretch(loop, tolerance, scale, corner_turn_deg, arcs)
        parts = _restore_corners(parts, False, tolerance, scale, corner_turn_deg)
        return _join_seam(_to_primitives(parts, tolerance, arcs, spline_degree), tolerance)

    if closed:
        start = corners[0]
        ordered = pts[start:] + pts[:start] + [pts[start]]
        bounds = [k - start for k in corners] + [len(pts)]
    else:
        ordered = pts
        bounds = [0] + corners + [len(pts) - 1]

    parts: List[_Part] = []
    for i, j in zip(bounds, bounds[1:]):
        parts.extend(_split_stretch(ordered[i: j + 1], tolerance, scale, corner_turn_deg, arcs))
    parts = _restore_corners(parts, closed, tolerance, scale, corner_turn_deg)
    return _to_primitives(parts, tolerance, arcs, spline_degree)
