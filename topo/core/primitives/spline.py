"""
topo/core/primitives/spline.py
------------------------------
La spline: `BSplineSeg` (NURBS coi pesi, D135), con de Boor, le derivate e
la ricerca dell'intervallo dei nodi. Il nome è il termine matematico
(Schoenberg, de Boor).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .mathseg import Algebra, DEFAULT_TOLERANCE, MathSeg, Point, _plain, _real
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point
from .polyline import _adaptive_polyline

# Numero massimo di segmenti per tratto di spline (evita esplosione di punti)
MAX_SEGMENTS_SPLINE = 100


def _bspline_find_span(t: float, degree: int, knots: List[float], n: int) -> int:
    """
    Indice `i` tale che `knots[i] <= t < knots[i+1]` (ricerca binaria, "The
    NURBS Book" Algoritmo A2.1) — `n` è l'indice dell'ultimo control point.
    """
    if t >= knots[n + 1]:
        return n
    lo, hi = degree, n + 1
    mid = (lo + hi) // 2
    while t < knots[mid] or t >= knots[mid + 1]:
        if t < knots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


def _derivative_points(points: List[tuple], knots: List[float], p: int) -> List[tuple]:
    """Punti di controllo della derivata (grado p − 1, nodi senza il primo e l'ultimo)."""
    out = []
    for i in range(len(points) - 1):
        span = knots[i + p + 1] - knots[i + 1]
        scale = p / span if span > 0 else 0.0
        out.append(tuple(scale * (b - a) for a, b in zip(points[i], points[i + 1])))
    return out


def _deboor(t: float, p: int, knots: List[float], points: List[tuple]) -> tuple:
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


@dataclass
class BSplineSeg(MathSeg):
    """
    B-spline (NURBS se `weights` è impostato): grado, punti di controllo,
    nodi, pesi — solo la geometria (MAP.md D135). Quello che un formato
    sorgente tiene in più (flag, tolleranze, fit points, tangenti) resta
    nell'adapter; `closed` e `periodic` si ricavano dai campi.
    """
    degree: int
    control_points: List[Point]
    knots: List[float]
    weights: Optional[List[float]] = None

    def __post_init__(self):
        self.degree = int(self.degree)
        self.control_points = [_plain(p) for p in self.control_points]
        self.knots = [_real(k) for k in self.knots]
        if self.weights is not None:
            self.weights = [_real(w) for w in self.weights]
        # punti di discretize() per tolleranza: heal() chiede la stessa spline
        # più volte. Non è un campo (fuori da eq/repr/fields); vale perché una
        # spline non si modifica sul posto — reversed/rotated ne fanno una nuova.
        self._points: dict = {}

    @property
    def algebra(self) -> Algebra:
        """Polinomiale senza pesi o coi pesi tutti uguali (il fattore comune si
        semplifica), razionale altrimenti."""
        w = self.weights
        return "polynomial" if not w or all(v == w[0] for v in w) else "rational"

    @property
    def clamped(self) -> bool:
        """True se i primi e gli ultimi `degree + 1` nodi coincidono: la curva
        parte dal primo punto di controllo e finisce sull'ultimo."""
        p, k = self.degree, self.knots
        if len(k) < 2 * (p + 1):
            return True
        return k[0] == k[p] and k[-1] == k[-(p + 1)]

    @property
    def closed(self) -> bool:
        """True se la curva torna al punto di partenza (entro DEFAULT_TOLERANCE)."""
        if len(self.control_points) < 2:
            return False
        start, end = self.endpoints()
        return math.hypot(start[0] - end[0], start[1] - end[1]) < DEFAULT_TOLERANCE

    @property
    def periodic(self) -> bool:
        """True se la curva è chiusa e non clamped: si richiude senza un punto
        di controllo sul giunto."""
        return self.closed and not self.clamped

    def endpoints(self) -> Tuple[Point, Point]:
        """(inizio, fine) sulla curva vera — per una spline non clamped non
        sono il primo e l'ultimo punto di controllo."""
        if not self.control_points:
            return (0.0, 0.0), (0.0, 0.0)
        p = self.degree
        if len(self.knots) != len(self.control_points) + p + 1:
            return self.control_points[0], self.control_points[-1]
        return self._evaluate(self.knots[p]), self._evaluate(self.knots[-(p + 1)])

    def reversed(self) -> "BSplineSeg":
        """
        Spline con la parametrizzazione invertita — stesso luogo geometrico
        percorso al contrario.

        Invertire una B-spline NON è solo invertire i punti di controllo:
        va invertito anche il vettore dei nodi e rimappato sul dominio
        originale ``U'[i] = a + b - U[m-i]`` (con ``a = U[0]``, ``b = U[-1]``),
        e vanno invertiti i pesi. Invertire i soli control point lascia la
        curva accoppiata a un vettore nodi sbagliato: la curva
        risulta deformata all'interno (gli endpoint combaciano lo stesso
        perché una spline clamped interpola il primo e l'ultimo CP).
        """
        if self.knots:
            a, b = self.knots[0], self.knots[-1]
            new_knots = [a + b - k for k in reversed(self.knots)]
        else:
            new_knots = []
        return BSplineSeg(
            degree=self.degree,
            control_points=list(reversed(self.control_points)),
            knots=new_knots,
            weights=list(reversed(self.weights)) if self.weights else None,
        )

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """Stessa spline, ruotata di `angle` radianti attorno a `origin`: si
        ruotano i punti di controllo, nodi e pesi non cambiano."""
        return BSplineSeg(
            degree=self.degree,
            control_points=[_rotate_point(p, angle, origin) for p in self.control_points],
            knots=list(self.knots),
            weights=list(self.weights) if self.weights else None,
        )

    def translated(self, dx: float, dy: float) -> "BSplineSeg":
        """Stessa spline, spostata di (`dx`, `dy`): si spostano i punti di controllo."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_translate_point(p, dx, dy) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "BSplineSeg":
        """Stessa spline, specchiata sulla retta per `origin` a `angle` radianti
        (default: l'asse x): una mappa affine porta la curva nella curva dei
        punti di controllo specchiati."""
        return BSplineSeg(degree=self.degree,
                          control_points=[_mirror_point(p, origin, angle) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "BSplineSeg":
        """Stessa spline, scalata di `factor` (> 0) attorno a `origin`: si
        scalano i punti di controllo, nodi e pesi non cambiano."""
        factor = _check_factor(factor)
        return BSplineSeg(degree=self.degree,
                          control_points=[_scale_point(p, factor, origin) for p in self.control_points],
                          knots=list(self.knots), weights=list(self.weights) if self.weights else None)

    def _defined(self) -> bool:
        """I nodi definiscono la curva: tanti quanti i punti di controllo più
        grado + 1, e un dominio non vuoto."""
        p, knots = self.degree, self.knots
        return p >= 1 and len(knots) == len(self.control_points) + p + 1 and knots[-(p + 1)] > knots[p]

    @property
    def t_range(self) -> Tuple[float, float]:
        """Il dominio dei nodi: da `knots[degree]` a `knots[-(degree + 1)]`."""
        return (self.knots[self.degree], self.knots[-(self.degree + 1)])

    def point_at(self, t: float) -> Point:
        return self._evaluate(t)

    def derivative_at(self, t: float) -> Point:
        """In coordinate omogenee, anche razionale: C' = (A' − w'·C) / w."""
        p, knots, ctrl = self.degree, self.knots, self.control_points
        # nodi che non definiscono la curva: nessuna derivata (chi chiama ripiega sulla corda)
        if not self._defined():
            return (0.0, 0.0)
        t0, t1 = self.t_range
        t = min(max(t, t0), t1)
        weights = self.weights or [1.0] * len(ctrl)
        h = [(c[0] * w, c[1] * w, w) for c, w in zip(ctrl, weights)]
        a = _deboor(t, p, knots, h)
        d = _derivative_points(h, knots, p)
        da = _deboor(t, p - 1, knots[1:-1], d) if p > 1 else d[_bspline_find_span(t, 1, knots, len(ctrl) - 1) - 1]
        x, y = a[0] / a[2], a[1] / a[2]
        return ((da[0] - da[2] * x) / a[2], (da[1] - da[2] * y) / a[2])

    def _evaluate(self, t: float) -> Point:
        """
        Punto della curva vera al parametro `t` (algoritmo di de Boor, "The
        NURBS Book" Algoritmo A5.1 — razionale se `weights` è impostato).
        Sola matematica: nessuna libreria di formato coinvolta.
        """
        degree = self.degree
        knots = self.knots
        ctrl = self.control_points
        n = len(ctrl) - 1

        # Fuori dominio si valuta sul bordo: per una spline clamped è il
        # primo/ultimo punto di controllo (esatto), per una non clamped no.
        t_min, t_max = knots[degree], knots[-(degree + 1)]
        t = min(max(t, t_min), t_max)

        k = _bspline_find_span(t, degree, knots, n)
        first = k - degree
        weights = self.weights
        # coordinate omogenee (x·w, y·w, w); w = 1 se la spline non è razionale
        if weights:
            ws = weights[first:k + 1]
            xs = [ctrl[first + j][0] * ws[j] for j in range(degree + 1)]
            ys = [ctrl[first + j][1] * ws[j] for j in range(degree + 1)]
        else:
            ws = None
            xs = [ctrl[first + j][0] for j in range(degree + 1)]
            ys = [ctrl[first + j][1] for j in range(degree + 1)]

        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = first + j
                denom = knots[i + degree - r + 1] - knots[i]
                alpha = 0.0 if denom == 0 else (t - knots[i]) / denom
                beta = 1 - alpha
                xs[j] = beta * xs[j - 1] + alpha * xs[j]
                ys[j] = beta * ys[j - 1] + alpha * ys[j]
                if ws is not None:
                    ws[j] = beta * ws[j - 1] + alpha * ws[j]

        if ws is None:
            return (xs[degree], ys[degree])
        w = ws[degree]
        return (xs[degree], ys[degree]) if w == 0 else (xs[degree] / w, ys[degree] / w)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """
        Discretizza la spline in polilinea valutando la curva vera (non il
        poligono di controllo) via `_evaluate()`, con suddivisione adattiva
        finché la deviazione dalla corda resta entro `tolerance`.
        """
        cached = self._points.get(tolerance)
        if cached is None:
            cached = self._points[tolerance] = self._discretize(tolerance)
        return list(cached)

    def _discretize(self, tolerance: float) -> List[Point]:
        if not self.control_points:
            return []

        if len(self.control_points) == 1:
            return [self.control_points[0]]

        if not self.knots:
            return list(self.control_points)

        t_min, t_max = self.knots[self.degree], self.knots[-(self.degree + 1)]
        if t_max <= t_min:
            return list(self.control_points)

        approx_length = sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.control_points, self.control_points[1:])
        )
        n_initial = max(1, int(math.ceil(approx_length / tolerance))) if tolerance > 0 else MAX_SEGMENTS_SPLINE
        n_initial = min(n_initial, MAX_SEGMENTS_SPLINE)

        return _adaptive_polyline(self._evaluate, t_min, t_max, n_initial, tolerance)
