"""
topo/core/geometry/fitting.py
------------------------------
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
from typing import List, Optional, Sequence, Tuple

from ..primitives.line import LineSeg
from ..primitives.spline import BSplineSeg
from ..primitives.mathseg import MathSeg, Point
from ..primitives.conics import CircleSeg, EllipseSeg, HyperbolaSeg, is_arc
from .measure import FLOAT_NOISE
from .points import (
    DEFAULT_DUPLICATE_TOLERANCE, approximate_bspline, circle_through, douglas_peucker, drop_duplicate_points,
    even_spacing, fit_circle_kasa, offset_from_line, turn_corners, within_chord, within_circle_through,
    within_conic_through, within_smooth_curve,
)

Primitive = MathSeg

DEFAULT_SPLINE_DEGREE = 3


@dataclass
class _Part:
    """Un pezzo della sequenza: `kind` "line" o "curve", coi punti che copre (estremi condivisi coi vicini)."""
    kind: str
    points: List[Point]


def _signed_turn(a: Point, b: Point, c: Point) -> float:
    """Svolta con segno (gradi) in `b` andando da `a` a `c`: positiva a sinistra.
    0 se `b` sta sulla retta `a`-`c` entro il rumore: il segno lì è dell'ultimo bit."""
    if abs(offset_from_line(b, a, c)) <= FLOAT_NOISE:
        return 0.0
    v1, v2 = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    return math.degrees(math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1]))


def _split_stretch(points: List[Point], tolerance: float, scale: float, corner_turn_deg: Optional[float],
                   arcs: bool) -> List[_Part]:
    """
    Un tratto senza spigoli: tutto entro `tolerance` dalla corda -> una linea;
    tutto entro `tolerance` da un arco per i suoi estremi (con `arcs`) -> un
    arco. Altrimenti i lati Douglas-Peucker lunghi almeno `scale` diventano
    linee, tranne quelli che stanno DENTRO una curva — svolta piccola e nello
    stesso verso ai capi che hanno un vicino, e non molto più lunghi dei
    vicini: sono faccette di una curva, non un lato dritto (il lato dritto di
    una O squadrata è lungo più del doppio dei vicini). Svolta piccola: sotto
    `corner_turn_deg`, o con `None` il lato, con `scale` di qua e di là, entro
    `tolerance` da una curva liscia (D283).
    """
    if within_chord(points, tolerance):
        return [_Part("line", points)]
    if arcs and len(points) >= 4 and (_arc_through_ends(points, tolerance) is not None
                                      or _ellipse_fits(points, tolerance)):
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
        if corner_turn_deg is None:
            # il lato più `scale` di qua e di là: un vicino lungo e dritto non c'entra
            first, last = i, j
            while first > 0 and math.dist(points[first - 1], points[i]) <= scale:
                first -= 1
            while last < len(points) - 1 and math.dist(points[last + 1], points[j]) <= scale:
                last += 1
            inside_curve = same_way and within_smooth_curve(points[first: last + 1], tolerance)
        else:
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


def _arc_through_ends(points: List[Point], tolerance: float) -> Optional[CircleSeg]:
    """
    L'arco che passa esattamente per il primo e l'ultimo punto (e per quello a
    metà), se tutti i punti stanno entro `tolerance` dal suo cerchio. Passa
    per gli estremi e non ai minimi quadrati: un arco che li sposta lascia un
    buco con la primitiva accanto.
    """
    a, m, b = points[0], points[len(points) // 2], points[-1]
    circle = within_circle_through(points, tolerance)
    if circle is None:
        return None
    center, radius = circle
    # da a a b passando per m: antiorario se m sta a destra della corda a->b
    return CircleSeg(center=center, radius=radius,
                  start_angle=math.atan2(a[1] - center[1], a[0] - center[0]),
                  end_angle=math.atan2(b[1] - center[1], b[0] - center[0]),
                  ccw=offset_from_line(m, a, b) < 0)


def _ellipse_fits(points: List[Point], tolerance: float) -> bool:
    """Il tratto intero sta su un'ellisse per i capi. Non un'iperbole: i suoi rami
    stanno vicini ai loro asintoti, e una stretta passa entro `tolerance` da due
    rette che si incontrano. I lati dritti si separano prima; l'iperbole si prova
    poi sul pezzo curvo che resta (`_fit_curve`)."""
    fit = within_conic_through(points, tolerance)
    return fit is not None and fit[0] == "ellipse"


def _conic_through_ends(points: List[Point], tolerance: float):
    """L'arco d'ellisse o d'iperbole per il primo e l'ultimo punto, nel verso
    che passa per gli altri, se tutti stanno entro `tolerance` da lui (come
    `_arc_through_ends`); quale delle due lo dice la conica (D294)."""
    fit = within_conic_through(points, tolerance)
    if fit is None:
        return None
    kind, center, major_axis, ratio, params = fit
    ta, tm, tb = params[0], params[len(params) // 2], params[-1]
    if kind == "hyperbola":
        # su un ramo il parametro va dritto da un capo all'altro: il punto di mezzo sta fra loro
        if not min(ta, tb) < tm < max(ta, tb):
            return None
        return HyperbolaSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=ta, end_param=tb)
    ccw = (tm - ta) % (2 * math.pi) < (tb - ta) % (2 * math.pi)
    return EllipseSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=ta, end_param=tb, ccw=ccw)


_SPLINE_SAMPLES = 64     # punti al minimo su una spline da riconoscere: più dei 6 che una conica chiede


def _walked(params: Sequence[float], ccw: bool, closed: bool) -> Optional[List[float]]:
    """Il parametro (angolo) percorso dal primo punto, nel verso `ccw`; None se
    torna indietro: allora la curva non percorre la conica una volta sola."""
    sign = 1.0 if ccw else -1.0
    walked = [(sign * (p - params[0])) % (2 * math.pi) for p in params]
    walked[0] = 0.0
    if closed:
        walked[-1] = 2 * math.pi
    if any(b < a - FLOAT_NOISE for a, b in zip(walked, walked[1:])):
        return None
    return walked


def conic_of_spline(spline: BSplineSeg, tolerance: float) -> Optional[EllipseSeg]:
    """
    L'arco (o cerchio) o l'arco d'ellisse (o ellisse) che è la spline: per i
    suoi capi esatti, ogni punto fitto della curva vera entro `tolerance` da
    lui, percorso una volta sola nel verso della spline. Prima il cerchio,
    più semplice; mai l'iperbole (D296). None se nessuno dei due.
    """
    pts = spline.discretize(tolerance=tolerance / 10)
    if len(pts) < _SPLINE_SAMPLES:
        t0, t1 = spline.t_range
        pts = [spline.point_at(t0 + (t1 - t0) * k / (_SPLINE_SAMPLES - 1)) for k in range(_SPLINE_SAMPLES)]
    start, end = spline.endpoints()
    pts[0], pts[-1] = start, end
    closed = math.dist(start, end) <= FLOAT_NOISE
    if closed:
        pts[-1] = start
        # nel verso in cui la curva gira: l'area con segno del suo poligono
        ccw = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:])) > 0
        n = len(pts)
        circle = circle_through(start, pts[n // 3], pts[2 * n // 3])
    else:
        ccw = offset_from_line(pts[len(pts) // 2], start, end) < 0
        circle = circle_through(start, pts[len(pts) // 2], end)
    if circle is not None:
        center, radius = circle
        angles = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in pts]
        if (all(abs(math.dist(center, p) - radius) <= tolerance for p in pts)
                and _walked(angles, ccw, closed) is not None):
            a0 = angles[0]
            a1 = a0 + (2 * math.pi if ccw else -2 * math.pi) if closed else angles[-1]
            return CircleSeg(center=center, radius=radius, start_angle=a0, end_angle=a1, ccw=ccw)
    fit = within_conic_through(pts, tolerance)
    if fit is None or fit[0] != "ellipse":
        return None
    _, center, major_axis, ratio, params = fit
    if _walked(params, ccw, closed) is None:
        return None
    p0 = params[0]
    p1 = p0 + (2 * math.pi if ccw else -2 * math.pi) if closed else params[-1]
    return EllipseSeg(center=center, major_axis=major_axis, ratio=ratio, start_param=p0, end_param=p1, ccw=ccw)


def _fit_curve(points: List[Point], tolerance: float, arcs: bool, degree: int) -> List[Primitive]:
    """Un pezzo curvo: la famiglia più semplice entro `tolerance` per gli estremi —
    arco, arco d'ellisse o d'iperbole (con `arcs`), spline."""
    if len(points) <= degree:
        return [LineSeg(start=a, end=b) for a, b in zip(points, points[1:])]
    if arcs and len(points) >= 4:
        arc = _arc_through_ends(points, tolerance)
        if arc is not None:
            return [arc]
        conic = _conic_through_ends(points, tolerance)
        if conic is not None:
            return [conic]
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


def _is_rounding(part: _Part, before: _Part, after: _Part, tolerance: float,
                 corner_turn_deg: Optional[float]) -> bool:
    """Il pezzo curvo fra le linee `before` e `after` è lo smusso di uno spigolo."""
    if corner_turn_deg is not None:
        return _line_turn(before, after) >= corner_turn_deg
    lines = [(before.points[0], before.points[-1]), (after.points[0], after.points[-1])]
    return all(min(abs(offset_from_line(q, a, b)) for a, b in lines) <= tolerance for q in part.points)


def _restore_corners(parts: List[_Part], closed: bool, tolerance: float, scale: float,
                     corner_turn_deg: Optional[float]) -> List[_Part]:
    """
    Gli spigoli vivi che il campionamento ha smussato. Un pezzo curvo più
    corto di `scale` fra due linee che svoltano di almeno `corner_turn_deg` (con
    `None`: i cui punti stanno entro `tolerance` dall'una o dall'altra retta, D283)
    è l'arrotondamento di uno spigolo: sparisce. Poi fra due linee consecutive
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
                and _length(part.points) < scale and _is_rounding(part, before, after, tolerance, corner_turn_deg)):
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
        if within_chord(far_a, tolerance) and within_chord(far_b, tolerance):
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
    if is_arc(last) and is_arc(first) and last.ccw == first.ccw             and math.dist(last.center, first.center) <= tolerance and abs(last.radius - first.radius) <= tolerance:
        merged = CircleSeg(center=last.center, radius=last.radius, start_angle=last.start_angle,
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
    *,
    corner_turn_deg: Optional[float],
    arcs: bool = True,
    spline_degree: int = DEFAULT_SPLINE_DEGREE,
) -> List[Primitive]:
    """
    Primitive (rette, archi, cerchi, ellissi, spline) per la sequenza di punti
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
        corner_turn_deg:  svolta minima (gradi) su `scale` per uno spigolo,
                          scelta da chi chiama: più bassa, più spigoli. None:
                          spigolo dove nessuna retta né arco sta entro `tolerance`
                          su `scale`; solo per punti fitti, come il rifit di
                          `heal()` (D283). Transitorio: esce quando smoother ha il
                          suo fitter
        arcs:             False: niente archi, cerchi né coniche, solo linee e spline
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
            ring = within_conic_through(pts + [pts[0]], tolerance)
            if ring is not None and ring[0] == "ellipse":      # un anello chiuso: un'iperbole non si chiude
                return [EllipseSeg(center=ring[1], major_axis=ring[2], ratio=ring[3],
                                   start_param=0.0, end_param=2 * math.pi)]
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
