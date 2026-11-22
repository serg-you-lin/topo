"""
topo/core/primitives/spline.py
------------------------------
La spline: `BSplineSeg` (NURBS coi pesi, D135), con de Boor, le derivate e
la ricerca dell'intervallo dei nodi. Il nome è il termine matematico
(Schoenberg, de Boor).
"""

from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from ...precision import FLOAT_NOISE
from .mathseg import Algebra, DEFAULT_TOLERANCE, MathSeg, Point, _plain, _real
from .motion import _check_factor, _mirror_point, _rotate_point, _scale_point, _translate_point
from .polyline import _point_to_segment_distance


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


def _insert_to_degree(p: int, knots: List[float], cpw: List[Tuple[float, float, float]],
                      t: float):
    """Inserisce `t` nel vettore dei nodi finché compare `p` volte: lì la curva
    passa per un punto di controllo e si separa in due tratti indipendenti.
    Anche agli estremi del tratto, dove una spline non bloccata non passa
    per un punto di controllo; fuori dal tratto nulla."""
    if t < knots[p] or t > knots[-(p + 1)]:
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


def _bezier_pieces(p: int, knots: List[float], cpw: List[Tuple[float, float, float]]) -> List[list]:
    """I pezzi di Bézier della curva fra `knots[p]` e `knots[-(p + 1)]`, in
    coordinate omogenee: ogni nodo del tratto inserito fino a molteplicità `p`,
    così la curva passa per un punto di controllo a ogni nodo."""
    lo, hi = knots[p], knots[-(p + 1)]
    for t in sorted({k for k in knots if lo <= k <= hi}):
        knots, cpw = _insert_to_degree(p, knots, cpw, t)
    first = max(i for i, k in enumerate(knots) if k == lo) - p
    count = len({k for k in knots if lo <= k <= hi}) - 1
    return [cpw[first + i * p:first + i * p + p + 1] for i in range(count)]


def _halves(c: list) -> Tuple[list, list]:
    """de Casteljau a metà del pezzo `c` (omogeneo): le due metà, stessa curva."""
    left, right, cur = [c[0]], [c[-1]], list(c)
    while len(cur) > 1:
        cur = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2) for a, b in zip(cur, cur[1:])]
        left.append(cur[0])
        right.append(cur[-1])
    return left, right[::-1]


def _flat_polygon(piece: list, tolerance: float, out: List[Point]) -> None:
    """Aggiunge a `out` i vertici del pezzo dopo il primo: si dimezza finché i
    punti di controllo stanno entro `tolerance` dalla corda. La curva sta
    nel loro inviluppo convesso (pesi positivi), quindi entro `tolerance`
    dalla corda: dimostrato, non stimato (D299)."""
    stack = [piece]
    while stack:
        c = stack.pop()
        pts = [(x / w, y / w) for x, y, w in c]
        a, b = pts[0], pts[-1]
        if all(_point_to_segment_distance(q, a, b) <= tolerance for q in pts[1:-1]):
            out.append(b)
        else:
            left, right = _halves(c)
            stack.append(right)
            stack.append(left)


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
        self._pieces_cache: Optional[list] = None

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
        Discretizza la spline in polilinea entro `tolerance` dalla curva vera,
        per dimostrazione: pezzi di Bézier dimezzati finché i loro punti di
        controllo stanno entro `tolerance` dalla corda (D299). Capi esatti.
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

        start, end = self.endpoints()
        out: List[Point] = [start]
        for _, _, piece in self._pieces():
            _flat_polygon(piece, tolerance, out)
        out[-1] = end
        return out

    def _pieces(self) -> List[Tuple[float, float, list]]:
        """(t0, t1, pezzo di Bézier omogeneo) da un nodo al successivo (D299).
        Pesi positivi: solo così la curva sta nell'inviluppo dei punti di controllo."""
        if self._pieces_cache is None:
            if self.weights and min(self.weights) <= 0:
                raise ValueError("a spline's weights must be positive to be discretized")
            weights = self.weights or [1.0] * len(self.control_points)
            cpw = [(x * w, y * w, w) for (x, y), w in zip(self.control_points, weights)]
            p, knots = self.degree, list(self.knots)
            ks = sorted({k for k in knots if knots[p] <= k <= knots[-(p + 1)]})
            self._pieces_cache = list(zip(ks, ks[1:], _bezier_pieces(p, knots, cpw)))
        return self._pieces_cache

    def _minimize(self, value: Callable[[Point], float],
                  bound: Callable[[List[Point]], float]) -> Tuple[float, float, float]:
        """(t, lo, hi): il parametro dove `value(punto)` è minimo sulla curva,
        entro FLOAT_NOISE, e il tratto [lo, hi] attorno a lui da rifinire.
        `bound(punti di controllo)` minora `value` su tutto il pezzo (la curva
        sta nel loro inviluppo): un pezzo che non scende sotto il migliore di
        FLOAT_NOISE si scarta, gli altri si dimezzano. Certificato, nessun
        campionamento: un ramo vicino non può vincere per sbaglio (D300)."""
        best = (math.inf, 0.0, 0.0, 0.0)
        heap: list = []
        order = itertools.count()   # a pari minorante, nell'ordine di arrivo
        for t0, t1, c in self._pieces():
            for t, q in ((t0, c[0]), (t1, c[-1])):
                v = value((q[0] / q[2], q[1] / q[2]))
                if v < best[0]:
                    best = (v, t, t0, t1)
            heap.append((bound([(x / w, y / w) for x, y, w in c]), next(order), t0, t1, c))
        heapq.heapify(heap)
        while heap:
            b, _, t0, t1, c = heapq.heappop(heap)
            if b >= best[0] - FLOAT_NOISE:
                break
            tm = (t0 + t1) / 2
            if not t0 < tm < t1:
                continue
            left, right = _halves(c)
            q = left[-1]
            v = value((q[0] / q[2], q[1] / q[2]))
            if v < best[0]:
                best = (v, tm, t0, t1)
            for a, z, half in ((t0, tm, left), (tm, t1, right)):
                heapq.heappush(heap, (bound([(x / w, y / w) for x, y, w in half]), next(order), a, z, half))
        return best[1], best[2], best[3]
