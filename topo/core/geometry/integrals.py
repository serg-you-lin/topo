"""
topo/core/geometry/integrals.py
-------------------------------
Area e baricentro esatti di un giro chiuso, integrati sulle sue primitive
col teorema di Green (MAP.md D165): nessuna discretizzazione, nessuna
tolleranza.

Per un tratto orientato il contributo è la terna

    area = ½ ∮ (x dy − y dx)     mx = ½ ∮ x² dy     my = −½ ∮ y² dx

e su un giro chiuso le tre somme danno l'area con segno (positiva in senso
antiorario) e i momenti ∬x dA, ∬y dA. Forma chiusa per retta, arco, cerchio
ed ellisse; per una spline polinomiale quadratura di Gauss esatta su ogni
intervallo di nodi, per una razionale quadratura fino alla precisione della
macchina. Funzioni pure su primitive, un ramo per tipo (D167).
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, List, Sequence, Tuple

import numpy as np

from ..primitives.segments import (
    ArcSeg, BSplineSeg, CircleSeg, EllipseSeg, LineSeg, _bspline_find_span, segment_endpoints,
)

Point = Tuple[float, float]
Vec = Tuple[float, ...]


@dataclass(frozen=True)
class Moments:
    """Area con segno e momenti primi (∬x dA, ∬y dA) di un tratto o di un giro."""
    area: float = 0.0
    mx: float = 0.0
    my: float = 0.0

    def __add__(self, other: "Moments") -> "Moments":
        return Moments(self.area + other.area, self.mx + other.mx, self.my + other.my)

    def __neg__(self) -> "Moments":
        return Moments(-self.area, -self.mx, -self.my)


def segment_moments(segment) -> Moments:
    """
    Contributo di Green di una primitiva percorsa nel suo verso. Un
    `CircleSeg` non ha verso: conta antiorario.
    """
    if isinstance(segment, LineSeg):
        return _line_moments(segment.start, segment.end)
    if isinstance(segment, ArcSeg):
        sign = 1.0 if segment.ccw else -1.0
        t0 = segment.start_angle
        return _trig_moments(segment.center, (segment.radius, 0.0), (0.0, segment.radius),
                             t0, t0 + sign * segment._sweep())
    if isinstance(segment, CircleSeg):
        return _trig_moments(segment.center, (segment.radius, 0.0), (0.0, segment.radius),
                             0.0, 2 * math.pi)
    if isinstance(segment, EllipseSeg):
        mx, my = segment.major_axis
        minor = (-my * segment.ratio, mx * segment.ratio)
        sign = 1.0 if segment.ccw else -1.0
        t0 = segment.start_param
        return _trig_moments(segment.center, (mx, my), minor, t0, t0 + sign * segment._sweep())
    if isinstance(segment, BSplineSeg):
        return _spline_moments(segment)
    raise TypeError(f"primitiva non supportata: {type(segment).__name__}")


def ring_moments(segments: Sequence) -> Moments:
    """
    Somma dei contributi di un giro chiuso, nell'ordine e nel verso dati. Un
    salto fra la fine di un segmento e l'inizio del successivo (un gap chiuso
    entro la tolleranza, coefficienti del sorgente intatti, D143) conta come
    la sua corda: senza, l'area dipenderebbe da dove sta il pezzo.
    """
    total = Moments()
    for segment, following in zip(segments, list(segments[1:]) + list(segments[:1])):
        total = total + segment_moments(segment)
        if isinstance(segment, CircleSeg) or isinstance(following, CircleSeg):
            continue
        end, start = segment_endpoints(segment)[1], segment_endpoints(following)[0]
        if end != start:
            total = total + _line_moments(end, start)
    return total


def ring_area(segments: Sequence) -> float:
    """Area esatta (senza segno) racchiusa da un giro chiuso di primitive."""
    return abs(ring_moments(segments).area)


def ring_centroid(segments: Sequence) -> Point:
    """
    Baricentro esatto dell'area racchiusa da un giro chiuso. Solleva
    `ValueError` se il giro non racchiude area.
    """
    m = ring_moments(segments)
    if m.area == 0.0:
        raise ValueError("il giro non racchiude area: baricentro indefinito")
    return (m.mx / m.area, m.my / m.area)


# ---------------------------------------------------------------------------
# Retta
# ---------------------------------------------------------------------------

def _line_moments(p0: Point, p1: Point) -> Moments:
    (x0, y0), (x1, y1) = p0, p1
    return Moments(
        area=0.5 * (x0 * y1 - x1 * y0),
        mx=(y1 - y0) * (x0 * x0 + x0 * x1 + x1 * x1) / 6.0,
        my=-(x1 - x0) * (y0 * y0 + y0 * y1 + y1 * y1) / 6.0,
    )


# ---------------------------------------------------------------------------
# Arco, cerchio, ellisse: P(t) = c + M cos t + N sin t
# ---------------------------------------------------------------------------

# Un polinomio in (cos t, sin t) è {(i, j): coefficiente di cosⁱ·sinʲ}.
Trig = dict


def _trig_moments(center: Point, m: Point, n: Point, t0: float, t1: float) -> Moments:
    """
    Contributo del tratto t0 → t1 di c + M cos t + N sin t (arco: M, N =
    (r, 0), (0, r); ellisse: asse maggiore e minore). Gli integrandi sono
    polinomi di grado ≤ 3 in cos t, sin t, integrati in forma chiusa.
    """
    x = {(0, 0): center[0], (1, 0): m[0], (0, 1): n[0]}
    y = {(0, 0): center[1], (1, 0): m[1], (0, 1): n[1]}
    dx = {(0, 1): -m[0], (1, 0): n[0]}
    dy = {(0, 1): -m[1], (1, 0): n[1]}
    area = _trig_add(_trig_mul(x, dy), _trig_mul(y, dx), -1.0)
    return Moments(
        area=0.5 * _trig_integral(area, t0, t1),
        mx=0.5 * _trig_integral(_trig_mul(_trig_mul(x, x), dy), t0, t1),
        my=-0.5 * _trig_integral(_trig_mul(_trig_mul(y, y), dx), t0, t1),
    )


def _trig_mul(a: Trig, b: Trig) -> Trig:
    out: Trig = {}
    for (i, j), u in a.items():
        for (k, l), v in b.items():
            out[(i + k, j + l)] = out.get((i + k, j + l), 0.0) + u * v
    return out


def _trig_add(a: Trig, b: Trig, scale: float = 1.0) -> Trig:
    out = dict(a)
    for key, v in b.items():
        out[key] = out.get(key, 0.0) + scale * v
    return out


def _trig_integral(poly: Trig, t0: float, t1: float) -> float:
    return sum(coef * _cos_sin_integral(i, j, t0, t1) for (i, j), coef in poly.items())


def _cos_sin_integral(i: int, j: int, t0: float, t1: float) -> float:
    """∫ cosⁱ t · sinʲ t dt da t0 a t1, in forma chiusa per i + j ≤ 3."""
    c0, s0, c1, s1 = math.cos(t0), math.sin(t0), math.cos(t1), math.sin(t1)
    if (i, j) == (0, 0):
        return t1 - t0
    if (i, j) == (1, 0):
        return s1 - s0
    if (i, j) == (0, 1):
        return c0 - c1
    if (i, j) == (2, 0):
        return 0.5 * (t1 - t0) + 0.5 * (s1 * c1 - s0 * c0)
    if (i, j) == (0, 2):
        return 0.5 * (t1 - t0) - 0.5 * (s1 * c1 - s0 * c0)
    if (i, j) == (1, 1):
        return 0.5 * (s1 * s1 - s0 * s0)
    if (i, j) == (3, 0):
        return (s1 - s1 ** 3 / 3.0) - (s0 - s0 ** 3 / 3.0)
    if (i, j) == (0, 3):
        return (-c1 + c1 ** 3 / 3.0) - (-c0 + c0 ** 3 / 3.0)
    if (i, j) == (2, 1):
        return (c0 ** 3 - c1 ** 3) / 3.0
    if (i, j) == (1, 2):
        return (s1 ** 3 - s0 ** 3) / 3.0
    raise ValueError(f"grado non previsto: cos^{i} sin^{j}")


# ---------------------------------------------------------------------------
# Spline
# ---------------------------------------------------------------------------

def _spline_moments(seg: BSplineSeg) -> Moments:
    """
    Su ogni intervallo di nodi non vuoto del dominio. Polinomiale: x, y di
    grado p, l'integrando più alto (x²·y') di grado 3p − 1, esatto con
    Gauss a 2p punti. Razionale: Gauss a 2p + 8 punti, con l'intervallo
    dimezzato finché due livelli coincidono alla precisione della macchina.
    """
    p = seg.degree
    knots = seg.knots
    if p < 1 or len(knots) != len(seg.control_points) + p + 1:
        raise ValueError("spline malformata: nodi e punti di controllo non concordano")
    weights = seg.weights or [1.0] * len(seg.control_points)
    hom = [(x * w, y * w, w) for (x, y), w in zip(seg.control_points, weights)]
    der = _derivative_points(hom, knots, p)
    rational = seg.weights is not None and len(set(weights)) > 1

    def integrand(t: float) -> Vec:
        xw, yw, w = _deboor(t, p, knots, hom)
        dxw, dyw, dw = _deboor(t, p - 1, knots[1:-1], der)
        x, y = xw / w, yw / w
        dx, dy = (dxw - x * dw) / w, (dyw - y * dw) / w
        return (0.5 * (x * dy - y * dx), 0.5 * x * x * dy, -0.5 * y * y * dx)

    total = (0.0, 0.0, 0.0)
    for a, b in zip(knots[p:len(knots) - p - 1], knots[p + 1:len(knots) - p]):
        if b <= a:
            continue
        if rational:
            part = _adaptive_gauss(integrand, a, b, 2 * p + 8)
        else:
            part = _gauss(integrand, a, b, 2 * p)
        total = tuple(u + v for u, v in zip(total, part))
    return Moments(*total)


def _derivative_points(points: List[Vec], knots: List[float], p: int) -> List[Vec]:
    """Punti di controllo della derivata (grado p − 1, nodi senza il primo e l'ultimo)."""
    out = []
    for i in range(len(points) - 1):
        span = knots[i + p + 1] - knots[i + 1]
        scale = p / span if span > 0 else 0.0
        out.append(tuple(scale * (b - a) for a, b in zip(points[i], points[i + 1])))
    return out


def _deboor(t: float, p: int, knots: List[float], points: List[Vec]) -> Vec:
    """Punto al parametro `t` di una B-spline di vettori (de Boor, A5.1)."""
    k = _bspline_find_span(t, p, knots, len(points) - 1)
    d = [list(points[k - p + j]) for j in range(p + 1)]
    for r in range(1, p + 1):
        for j in range(p, r - 1, -1):
            i = k - p + j
            denom = knots[i + p - r + 1] - knots[i]
            alpha = 0.0 if denom == 0 else (t - knots[i]) / denom
            d[j] = [(1 - alpha) * u + alpha * v for u, v in zip(d[j - 1], d[j])]
    return tuple(d[p])


@lru_cache(maxsize=None)
def _gauss_rule(n: int) -> Tuple[Tuple[float, ...], Tuple[float, ...]]:
    nodes, weights = np.polynomial.legendre.leggauss(n)
    return tuple(float(x) for x in nodes), tuple(float(w) for w in weights)


def _gauss(f: Callable[[float], Vec], a: float, b: float, n: int) -> Vec:
    nodes, weights = _gauss_rule(n)
    half, mid = 0.5 * (b - a), 0.5 * (a + b)
    total = None
    for x, w in zip(nodes, weights):
        value = f(mid + half * x)
        total = [w * v for v in value] if total is None else [s + w * v for s, v in zip(total, value)]
    return tuple(half * s for s in total)


def _adaptive_gauss(f: Callable[[float], Vec], a: float, b: float, n: int, depth: int = 0) -> Vec:
    whole = _gauss(f, a, b, n)
    mid = 0.5 * (a + b)
    left, right = _gauss(f, a, mid, n), _gauss(f, mid, b, n)
    halves = tuple(u + v for u, v in zip(left, right))
    scale = max(1.0, *(abs(v) for v in halves))
    if depth >= 12 or all(abs(u - v) <= 1e-14 * scale for u, v in zip(whole, halves)):
        return halves
    l = _adaptive_gauss(f, a, mid, n, depth + 1)
    r = _adaptive_gauss(f, mid, b, n, depth + 1)
    return tuple(u + v for u, v in zip(l, r))
