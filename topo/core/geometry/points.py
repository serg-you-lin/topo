"""
topo/core/geometry/points.py
-----------------------------
Sequenze ordinate di punti (un contorno campionato: da un raster, da una
polilinea che scrive una curva a punti): doppioni, passo regolare,
Douglas-Peucker, spigoli per svolta su una scala, cerchio per tre punti, fit
di un cerchio, b-spline interpolante e b-spline approssimante entro una
tolleranza (MAP.md D141).
"""

import math
from typing import Optional, Tuple, List
import numpy as np

from ..primitives.segments import LineSeg, ArcSeg

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Sequenze di punti — angolo interno, deduplica, fit a cerchio (D38)
# ---------------------------------------------------------------------------
# Matematica generica su una sequenza ordinata di punti (x, y): non sa nulla
# di primitive topo (LineSeg/ArcSeg/...) né di come il chiamante la userà.
# Nata dentro tools/simplify_points.py (D33/D36), spostata qui perché un
# secondo consumatore ne ha bisogno senza
# duplicarla — `core/primitives/fitting.py` resta l'orchestratore che decide
# quando/come usarla per ricostruire linee/archi/spline.

DEFAULT_DUPLICATE_TOLERANCE = 1e-6


def drop_duplicate_points(
    points: List[Point], tolerance: float = DEFAULT_DUPLICATE_TOLERANCE
) -> List[Point]:
    """Rimuove punti consecutivi coincidenti entro `tolerance`."""
    if not points:
        return []
    cleaned = [points[0]]
    for p in points[1:]:
        last = cleaned[-1]
        if math.hypot(p[0] - last[0], p[1] - last[1]) > tolerance:
            cleaned.append(p)
    return cleaned


def fit_circle_kasa(points: List[Point]) -> Optional[Tuple[Point, float, float]]:
    """
    Fit algebrico (Kasa) ai minimi quadrati di un cerchio su `points`: minimizza
    `x²+y²+Dx+Ey+F=0`, che è un cerchio di centro `(-D/2,-E/2)` e raggio
    ricavabile da `D,E,F`. Ritorna `(center, radius, max_residual)` —
    `max_residual` è lo scostamento massimo di un punto dal cerchio fittato,
    per decidere se accettarlo. `None` se il fit è degenere (meno di 3 punti,
    punti quasi collineari, raggio non reale).
    """
    if len(points) < 3:
        return None

    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    a_matrix = np.column_stack([x, y, np.ones_like(x)])
    b_vector = -(x**2 + y**2)
    try:
        (d, e, f), *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    except np.linalg.LinAlgError:
        return None

    center = (-d / 2.0, -e / 2.0)
    radius_sq = (d**2 + e**2) / 4.0 - f
    if radius_sq <= 0:
        return None
    radius = math.sqrt(radius_sq)

    residuals = np.hypot(x - center[0], y - center[1]) - radius
    max_residual = float(np.max(np.abs(residuals)))
    return center, radius, max_residual


def interpolate_bspline(points: List[Point], degree: int = 3) -> Tuple[List[Point], List[float]]:
    """
    B-spline di grado `degree` che passa per tutti i `points` (interpolazione
    globale, Piegl & Tiller cap. 9.2.1): parametri per lunghezza di corda,
    nodi "natural" per grado dispari e mediati per grado pari. Ritorna
    `(control_points, knots)`, nodi normalizzati in [0, 1].
    """
    n = len(points) - 1
    p = degree
    if n < p:
        raise ValueError(f"Servono almeno {p + 1} punti per una spline di grado {p}")

    dists = [math.dist(points[i], points[i + 1]) for i in range(n)]
    total = sum(dists)
    if total > 0:
        t, acc = [0.0], 0.0
        for d in dists:
            acc += d
            t.append(acc / total)
        t[-1] = 1.0
    else:
        t = [i / n for i in range(n + 1)]

    if p % 2:
        inner = t[2:n - p + 2]
    else:
        inner = [sum(t[j:j + p]) / p for j in range(1, n - p + 1)]
    knots = [0.0] * (p + 1) + list(inner) + [1.0] * (p + 1)

    basis = np.array([_bspline_basis_row(u, p, knots, n) for u in t])
    control = np.linalg.solve(basis, np.array(points, dtype=np.float64))
    return [(float(x), float(y)) for x, y in control], knots


def _bspline_basis_row(u: float, p: int, knots: List[float], n: int) -> List[float]:
    """Le n+1 funzioni di base N_i,p(u) (Cox-de Boor, Piegl & Tiller A2.2)."""
    row = [0.0] * (n + 1)
    if u >= knots[n + 1]:
        row[n] = 1.0
        return row
    span = p
    while span < n and knots[span + 1] <= u:
        span += 1
    funcs = [1.0] + [0.0] * p
    left, right = [0.0] * (p + 1), [0.0] * (p + 1)
    for j in range(1, p + 1):
        left[j] = u - knots[span + 1 - j]
        right[j] = knots[span + j] - u
        saved = 0.0
        for r in range(j):
            temp = funcs[r] / (right[r + 1] + left[j - r])
            funcs[r] = saved + right[r + 1] * temp
            saved = left[j - r] * temp
        funcs[j] = saved
    for j in range(p + 1):
        row[span - p + j] = funcs[j]
    return row


# ---------------------------------------------------------------------------
# Passo, Douglas-Peucker, spigoli per svolta (D141)
# ---------------------------------------------------------------------------

def even_spacing(points: List[Point], closed: bool) -> List[Point]:
    """
    I punti con altri aggiunti dove due vicini distano più del passo mediano.
    Un lato lungo senza punti in mezzo farebbe passare per buono un arco per
    3 punti (3 punti stanno sempre su un cerchio) e oscillare una spline a
    passo irregolare. I punti dati restano tutti, nello stesso ordine.
    """
    ring = list(points) + [points[0]] if closed else list(points)
    steps = sorted(math.dist(a, b) for a, b in zip(ring, ring[1:]))
    step = steps[len(steps) // 2] if steps else 0.0
    if step <= 0:
        return list(points)
    out: List[Point] = []
    for a, b in zip(ring, ring[1:]):
        out.append(a)
        extra = int(math.dist(a, b) / step)
        for k in range(1, extra):
            t = k / extra
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    if not closed:
        out.append(points[-1])
    return out


def offset_from_line(p: Point, a: Point, b: Point) -> float:
    """Distanza con segno di `p` dalla retta a->b (positiva a sinistra)."""
    length = math.dist(a, b)
    if length == 0:
        return math.dist(p, a)
    return ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / length


def douglas_peucker(points: List[Point], tolerance: float) -> List[int]:
    """
    Indici dei vertici che Douglas-Peucker tiene sulla polilinea aperta
    `points`, estremi compresi: ogni punto scartato dista al più `tolerance`
    dal lato che lo sostituisce.
    """
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        best, best_k = 0.0, -1
        for k in range(i + 1, j):
            d = abs(offset_from_line(points[k], points[i], points[j]))
            if d > best:
                best, best_k = d, k
        if best > tolerance:
            keep.add(best_k)
            stack.append((i, best_k))
            stack.append((best_k, j))
    return sorted(keep)


def _turn(back: Point, at: Point, forward: Point) -> float:
    """Di quanto gira (gradi, 0..180) chi va da `back` ad `at` e poi a `forward`."""
    v1 = (at[0] - back[0], at[1] - back[1])
    v2 = (forward[0] - at[0], forward[1] - at[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _point_at(points: List[Point], cum: List[float], s: float) -> Point:
    """Punto della polilinea `points` all'ascissa curvilinea `s` (troncata agli estremi)."""
    if s <= 0:
        return points[0]
    if s >= cum[-1]:
        return points[-1]
    lo, hi = 0, len(cum) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if cum[mid] <= s:
            lo = mid
        else:
            hi = mid
    t = (s - cum[lo]) / (cum[hi] - cum[lo]) if cum[hi] > cum[lo] else 0.0
    a, b = points[lo], points[hi]
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def turn_corners(points: List[Point], closed: bool, turn_deg: float, scale: float,
                 tolerance: float) -> List[int]:
    """
    Indici degli spigoli di una sequenza campionata: vertici Douglas-Peucker
    (a `tolerance`) dove la curva svolta di almeno `turn_deg` gradi fra il
    punto a `scale` prima e quello a `scale` dopo, lungo la curva. Misurata su
    una scala e non fra due campioni vicini, un angolo vivo smussato dal
    campionamento conta per tutta la sua svolta. Fra spigoli più vicini di
    `scale` resta quello che svolta di più. Su una sequenza aperta gli
    estremi non sono mai spigoli.
    """
    n = len(points)
    if n < 3:
        return []
    # chiusa: tre giri di fila, la finestra attorno al giro centrale non si tronca mai
    ring = list(points) * 3 if closed else list(points)
    cum = [0.0]
    for a, b in zip(ring, ring[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    if closed:
        perimeter = cum[n]
        candidates = [n + k for k in douglas_peucker(ring[n: 2 * n + 1], tolerance) if k < n]
    else:
        perimeter = math.inf
        candidates = douglas_peucker(ring, tolerance)[1:-1]

    scored = []
    for k in candidates:
        s = cum[k]
        if not closed and (s < scale or s > cum[-1] - scale):
            continue
        turn = _turn(_point_at(ring, cum, s - scale), ring[k], _point_at(ring, cum, s + scale))
        if turn >= turn_deg:
            scored.append((turn, k))

    def apart(k: int, a: int) -> float:
        d = abs(cum[k] - cum[a])
        return min(d, perimeter - d)

    accepted: List[int] = []
    for _, k in sorted(scored, reverse=True):
        if all(apart(k, a) >= scale for a in accepted):
            accepted.append(k)
    return sorted(k - n for k in accepted) if closed else sorted(accepted)


def circle_through(a: Point, m: Point, b: Point) -> Optional[Tuple[Point, float]]:
    """Il cerchio per tre punti: `(center, radius)`, None se sono allineati."""
    den = 2 * (a[0] * (m[1] - b[1]) + m[0] * (b[1] - a[1]) + b[0] * (a[1] - m[1]))
    if abs(den) < 1e-12:
        return None
    sa, sm, sb = a[0] ** 2 + a[1] ** 2, m[0] ** 2 + m[1] ** 2, b[0] ** 2 + b[1] ** 2
    center = ((sa * (m[1] - b[1]) + sm * (b[1] - a[1]) + sb * (a[1] - m[1])) / den,
              (sa * (b[0] - m[0]) + sm * (a[0] - b[0]) + sb * (m[0] - a[0])) / den)
    return center, math.dist(center, a)


# ---------------------------------------------------------------------------
# B-spline approssimante entro una tolleranza (D141)
# ---------------------------------------------------------------------------

def _chord_params(points: List[Point]) -> List[float]:
    dists = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(dists)
    if total == 0:
        return [i / (len(points) - 1) for i in range(len(points))]
    t, acc = [0.0], 0.0
    for d in dists:
        acc += d
        t.append(acc / total)
    t[-1] = 1.0
    return t


def _least_squares(points: np.ndarray, t: List[float], degree: int, count: int):
    """
    Spline di grado `degree` con `count` punti di controllo ai minimi quadrati
    sui punti, primo e ultimo fissati (Piegl & Tiller 9.4.1, nodi per media,
    eq. 9.68-9.69). Ritorna `(control, knots, max_error)`: l'errore è la
    distanza di ogni punto dalla curva al suo parametro, che maggiora la
    distanza vera dalla curva.
    """
    m, n, p = len(points) - 1, count - 1, degree
    d = (m + 1) / (n - p + 1)
    inner = []
    for j in range(1, n - p + 1):
        i = int(j * d)
        alpha = j * d - i
        inner.append((1 - alpha) * t[i - 1] + alpha * t[i])
    knots = [0.0] * (p + 1) + inner + [1.0] * (p + 1)
    basis = np.array([_bspline_basis_row(u, p, knots, n) for u in t])
    q0, qm = points[0], points[-1]
    rhs = points[1:-1] - np.outer(basis[1:-1, 0], q0) - np.outer(basis[1:-1, n], qm)
    inner_ctrl, *_ = np.linalg.lstsq(basis[1:-1, 1:n], rhs, rcond=None)
    control = np.vstack([q0, inner_ctrl, qm])
    error = float(np.max(np.hypot(*(basis @ control - points).T)))
    return control, knots, error


def approximate_bspline(points: List[Point], degree: int, tolerance: float) -> Tuple[List[Point], List[float]]:
    """
    La B-spline di grado `degree` con meno punti di controllo che passa per il
    primo e l'ultimo punto e resta entro `tolerance` da tutti gli altri
    (minimi quadrati, Piegl & Tiller 9.4.1). Su punti rumorosi o a passo
    irregolare non oscilla come quella che li interpola tutti; quando nessuna
    approssimazione basta è l'interpolazione stessa (`interpolate_bspline`).
    Ritorna `(control_points, knots)`, nodi in [0, 1].
    """
    if len(points) <= degree + 1:
        return interpolate_bspline(points, degree)
    pts = np.array(points, dtype=np.float64)
    t = _chord_params(points)
    lo, hi = degree, len(points)   # `lo` non basta mai (meno di degree+1 controlli), `hi` è l'interpolazione
    best = None
    # raddoppia finché basta, poi bisezione fra l'ultimo che non basta e il primo che basta
    count = degree + 1
    while count < hi:
        control, knots, error = _least_squares(pts, t, degree, count)
        if error <= tolerance:
            best = (control, knots)
            break
        lo, count = count, min(hi, count * 2)
    if best is None:
        return interpolate_bspline(points, degree)
    hi = count
    while hi - lo > 1:
        mid = (lo + hi) // 2
        control, knots, error = _least_squares(pts, t, degree, mid)
        if error <= tolerance:
            hi, best = mid, (control, knots)
        else:
            lo = mid
    control, knots = best
    return [(float(x), float(y)) for x, y in control], [float(k) for k in knots]
