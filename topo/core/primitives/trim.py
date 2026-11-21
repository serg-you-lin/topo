"""
topo/core/primitives/trim.py
-----------------------------
Il tratto di una primitiva fra due suoi punti: la stessa curva, accorciata —
stessi centro e assi per un cerchio o un'ellisse, gli stessi
pezzi polinomiali per una B-spline (inserimento di nodi, Piegl & Tiller
A5.1), non un'approssimazione.

Puro: solo primitive, nessun formato.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import List, Optional, Tuple

from ..geometry.measure import FLOAT_NOISE
from .segments import LineSeg, Point, BSplineSeg, _bspline_find_span
from .conics import CircleSeg, EllipseSeg, HyperbolaSeg, ParabolaSeg
from .clothoid import ClothoidSeg
from .formula import FormulaSeg

_TWO_PI = 2 * math.pi
_SAMPLES = 64          # campioni per il primo aggancio di un punto sulla spline
_REFINE_STEPS = 60     # passi di ricerca ternaria sul parametro della spline


def sub_segment(seg, a: Point, b: Point, via: Point):
    """
    Il tratto di `seg` da `a` a `b` (punti sulla curva, o a una tolleranza
    da lei), percorso da `a` verso `b`. `via` è un punto interno al tratto:
    serve solo su una curva chiusa (cerchio, ellisse piena) per sapere da
    che parte girare. None se `seg` non si taglia esatto (spline periodica o
    senza vettore dei nodi).
    """
    if isinstance(seg, LineSeg):
        return LineSeg(start=_on_line(seg, a), end=_on_line(seg, b))
    if isinstance(seg, (CircleSeg, EllipseSeg)):
        return _sub_angular(seg, a, b, via)
    if isinstance(seg, BSplineSeg):
        return _sub_spline(seg, a, b, via)
    if isinstance(seg, (ParabolaSeg, HyperbolaSeg)):
        return _sub_open_conic(seg, a, b)
    if isinstance(seg, (FormulaSeg, ClothoidSeg)):
        return _sub_interval(seg, a, b)
    return None


def _sub_interval(seg, a: Point, b: Point):
    """La stessa curva su un intervallo più corto: dal parametro di `a` a quello di `b`."""
    t0, t1 = seg.t_range
    sign = 1.0 if seg.end_param >= seg.start_param else -1.0
    ta, tb = (_nearest_param(seg.point_at, p, t0, t1) for p in (a, b))
    return replace(seg, start_param=seg.start_param + sign * ta, end_param=seg.start_param + sign * tb)


def _sub_open_conic(seg, a: Point, b: Point):
    """Parabola e iperbole sono aperte: il tratto va dal parametro di `a` a
    quello di `b`, dentro il pezzo. Parabola: s = (p − V)·n; iperbole:
    s = asinh((p − C)·N / |N|²), N il secondo asse."""
    lo, hi = sorted((seg.start_param, seg.end_param))

    def param(pt: Point) -> float:
        if isinstance(seg, ParabolaSeg):
            _, _, n = seg._frame()
            s = (pt[0] - seg.vertex[0]) * n[0] + (pt[1] - seg.vertex[1]) * n[1]
        else:
            nx, ny = seg._minor()
            b2 = nx * nx + ny * ny
            # (p − C)·N = sinh(s)·|N|², perché M ⟂ N
            s = math.asinh(((pt[0] - seg.center[0]) * nx + (pt[1] - seg.center[1]) * ny) / b2)
        return min(max(s, lo), hi)

    return type(seg)(*_fields_before_params(seg), param(a), param(b))


def _fields_before_params(seg) -> tuple:
    """I campi che fissano la curva, senza l'intervallo del parametro."""
    if isinstance(seg, ParabolaSeg):
        return (seg.vertex, seg.focus)
    return (seg.center, seg.major_axis, seg.ratio)


# ---------------------------------------------------------------------------
# Retta
# ---------------------------------------------------------------------------

def _on_line(seg: LineSeg, pt: Point) -> Point:
    """Proiezione di `pt` sulla retta, dentro i suoi due estremi."""
    dx, dy = seg.end[0] - seg.start[0], seg.end[1] - seg.start[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return seg.start
    t = max(0.0, min(1.0, ((pt[0] - seg.start[0]) * dx + (pt[1] - seg.start[1]) * dy) / l2))
    return (seg.start[0] + t * dx, seg.start[1] + t * dy)


# ---------------------------------------------------------------------------
# Cerchio ed ellisse (un cerchio è un'ellisse): un parametro angolare percorso in un verso
# ---------------------------------------------------------------------------

def _sub_angular(seg, a: Point, b: Point, via: Point):
    # il parametro del cerchio è il suo angolo (D287): una formula per tutti e due
    start, sweep, ccw = seg.start_param, seg._sweep(), seg.ccw
    sign = 1.0 if ccw else -1.0
    closed = sweep >= _TWO_PI - 1e-9

    def offset(pt: Point) -> float:
        """Quanto si percorre da `start`, nel verso della curva, fino a `pt`."""
        return (sign * (_angle_of(seg, pt) - start)) % _TWO_PI

    if closed:
        oa = offset(a)
        ob = (offset(b) - oa) % _TWO_PI or _TWO_PI
        forward = (offset(via) - oa) % _TWO_PI <= ob
        lo = start + sign * oa
        hi = lo + sign * ob if forward else lo - sign * (_TWO_PI - ob)
        return _angular(seg, lo, hi, ccw if forward else not ccw)
    oa, ob = _clamp(offset(a), sweep), _clamp(offset(b), sweep)
    return _angular(seg, start + sign * oa, start + sign * ob, ccw if oa <= ob else not ccw)


def _clamp(offset: float, sweep: float) -> float:
    """Un punto appena oltre un estremo (entro tolleranza) sta su quell'estremo."""
    if offset <= sweep:
        return offset
    return sweep if offset - sweep < _TWO_PI - offset else 0.0


def _angle_of(seg, pt: Point) -> float:
    """Angolo (o parametro dell'ellisse) di `pt` visto dal centro della curva."""
    dx, dy = pt[0] - seg.center[0], pt[1] - seg.center[1]
    if isinstance(seg, CircleSeg):
        return math.atan2(dy, dx)
    mx, my = seg.major_axis
    nx, ny = -my * seg.ratio, mx * seg.ratio
    return math.atan2((dx * nx + dy * ny) / (nx * nx + ny * ny),
                      (dx * mx + dy * my) / (mx * mx + my * my))


def _angular(seg, lo: float, hi: float, ccw: bool):
    if isinstance(seg, CircleSeg):
        return CircleSeg(center=seg.center, radius=seg.radius, start_angle=lo, end_angle=hi, ccw=ccw)
    return EllipseSeg(center=seg.center, major_axis=seg.major_axis, ratio=seg.ratio,
                      start_param=lo, end_param=hi, ccw=ccw)


# ---------------------------------------------------------------------------
# B-spline
# ---------------------------------------------------------------------------

def _sub_spline(seg: BSplineSeg, a: Point, b: Point, via: Point) -> Optional[BSplineSeg]:
    if seg.periodic or not seg.knots or len(seg.control_points) < 2:
        return None
    p = seg.degree
    lo, hi = seg.knots[p], seg.knots[-(p + 1)]
    ta, tb = _spline_param(seg, a, lo, hi), _spline_param(seg, b, lo, hi)
    # un capo sulla giunzione di una spline chiusa ha due parametri, lo e hi,
    # a pari merito: vale quello che mette `via` dentro il tratto, come sul
    # cerchio (G6e)
    seam_a, seam_b = _on_seam(seg, a, lo, hi), _on_seam(seg, b, lo, hi)
    if seam_a and seam_b:
        ta, tb = lo, hi
    elif seam_a or seam_b:
        tv = _spline_param(seg, via, lo, hi)
        if seam_a:
            ta = lo if tv < tb else hi
        else:
            tb = lo if tv < ta else hi
    if ta == tb:
        return None
    reverse = ta > tb
    if reverse:
        ta, tb = tb, ta
    weights = seg.weights or [1.0] * len(seg.control_points)
    cpw = [(x * w, y * w, w) for (x, y), w in zip(seg.control_points, weights)]
    knots = list(seg.knots)
    for t in (ta, tb):
        knots, cpw = _insert_to_degree(p, knots, cpw, t)
    last_a = max(i for i, k in enumerate(knots) if k == ta)
    inner = [k for k in knots if ta < k < tb]
    sub_knots = [ta] * (p + 1) + inner + [tb] * (p + 1)
    first = last_a - p
    sub_cpw = cpw[first:first + len(sub_knots) - p - 1]
    out = BSplineSeg(
        degree=p,
        control_points=[(x / w, y / w) for x, y, w in sub_cpw],
        knots=sub_knots,
        weights=[w for _, _, w in sub_cpw] if seg.weights else None,
    )
    return out.reversed() if reverse else out


def _on_seam(seg: BSplineSeg, pt: Point, lo: float, hi: float) -> bool:
    """`pt` sta sui due capi della spline insieme: alla stessa distanza da tutti
    e due entro FLOAT_NOISE, e lì sopra."""
    d_lo, d_hi = math.dist(seg._evaluate(lo), pt), math.dist(seg._evaluate(hi), pt)
    return abs(d_lo - d_hi) <= FLOAT_NOISE and max(d_lo, d_hi) <= FLOAT_NOISE


def _spline_param(seg: BSplineSeg, pt: Point, lo: float, hi: float) -> float:
    """Parametro del punto della spline più vicino a `pt`."""
    return _nearest_param(seg._evaluate, pt, lo, hi)


def _nearest_param(at, pt: Point, lo: float, hi: float) -> float:
    """Parametro in [lo, hi] del punto della curva `at(t)` più vicino a `pt`:
    campioni, poi ricerca ternaria fra i due vicini del migliore."""
    step = (hi - lo) / _SAMPLES
    ts = [lo + i * step for i in range(_SAMPLES)] + [hi]
    best = min(range(len(ts)), key=lambda i: math.dist(at(ts[i]), pt))
    left, right = ts[max(best - 1, 0)], ts[min(best + 1, len(ts) - 1)]
    for _ in range(_REFINE_STEPS):
        m1, m2 = left + (right - left) / 3, right - (right - left) / 3
        if math.dist(at(m1), pt) <= math.dist(at(m2), pt):
            right = m2
        else:
            left = m1
    t = (left + right) / 2
    for end in (lo, hi):
        if math.dist(at(end), pt) <= math.dist(at(t), pt):
            t = end
    return t


def _insert_to_degree(p: int, knots: List[float], cpw: List[Tuple[float, float, float]],
                      t: float):
    """Inserisce `t` nel vettore dei nodi finché compare `p` volte (agli
    estremi, già bloccati, non serve): lì la curva passa per un punto di
    controllo e si separa in due tratti indipendenti."""
    if t <= knots[p] or t >= knots[-(p + 1)]:
        return knots, cpw
    while sum(1 for k in knots if k == t) < p:
        span = _bspline_find_span(t, p, knots, len(cpw) - 1)
        new = []
        for i in range(len(cpw) + 1):
            if i <= span - p:
                new.append(cpw[i])
            elif i > span:
                new.append(cpw[i - 1])
            else:
                alpha = (t - knots[i]) / (knots[i + p] - knots[i])
                new.append(tuple(alpha * cpw[i][c] + (1 - alpha) * cpw[i - 1][c] for c in range(3)))
        knots = knots[:span + 1] + [t] + knots[span + 1:]
        cpw = new
    return knots, cpw
