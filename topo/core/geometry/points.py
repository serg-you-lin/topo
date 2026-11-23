"""
topo/core/geometry/points.py
-----------------------------
Sequenze ordinate di punti (un contorno campionato: da un raster, da una
polilinea che scrive una curva a punti): doppioni, passo regolare, distanza
da una retta, Douglas-Peucker, cerchio per tre punti, fit di un cerchio
(MAP.md D141). Le spline sono in `spline_fit.py`, le prove "i punti stanno su
una curva?" in `curve_tests.py`, gli spigoli per svolta in `corners.py`.
"""

import math
from typing import Optional, Tuple, List
import numpy as np

from ...precision import FLOAT_NOISE

Point = Tuple[float, float]


# Matematica generica su una sequenza ordinata di punti (x, y): non sa nulla
# di primitive topo (LineSeg/CircleSeg/...) né di come il chiamante la userà.
# Nata dentro tools/simplify_points.py (D33/D36), spostata qui perché un
# secondo consumatore ne ha bisogno senza
# duplicarla — `core/geometry/fitting.py` resta l'orchestratore che decide
# quando/come usarla per ricostruire linee/archi/spline.

DEFAULT_DUPLICATE_TOLERANCE = FLOAT_NOISE  # D269


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

    pts = np.asarray(points, dtype=float)[:, :2]
    # nel riferimento dei punti: x²+y² su coordinate grandi cancella le cifre,
    # e il cerchio dipenderebbe da dove sta il disegno (G6e)
    origin = pts.mean(axis=0)
    x, y = pts[:, 0] - origin[0], pts[:, 1] - origin[1]
    a_matrix = np.column_stack([x, y, np.ones_like(x)])
    b_vector = -(x**2 + y**2)
    try:
        (d, e, f), *_ = np.linalg.lstsq(a_matrix, b_vector, rcond=None)
    except np.linalg.LinAlgError:
        return None

    local = (-d / 2.0, -e / 2.0)
    radius_sq = (d**2 + e**2) / 4.0 - f
    if radius_sq <= 0:
        return None
    radius = math.sqrt(radius_sq)
    center = (float(local[0] + origin[0]), float(local[1] + origin[1]))

    residuals = np.hypot(x - local[0], y - local[1]) - radius
    max_residual = float(np.max(np.abs(residuals)))
    return center, radius, max_residual


def circle_through(a: Point, m: Point, b: Point) -> Optional[Tuple[Point, float]]:
    """Il cerchio per tre punti: `(center, radius)`, None se sono allineati.
    Calcolato nel riferimento di `a`: le coordinate al quadrato non perdono
    cifre lontano dall'origine (G6e)."""
    ox, oy = a[0], a[1]
    a, m, b = (0.0, 0.0), (m[0] - ox, m[1] - oy), (b[0] - ox, b[1] - oy)
    den = 2 * (m[0] * b[1] - b[0] * m[1])
    if abs(den) < 1e-12:
        return None
    sm, sb = m[0] ** 2 + m[1] ** 2, b[0] ** 2 + b[1] ** 2
    cx = (sm * b[1] - sb * m[1]) / den
    cy = (sb * m[0] - sm * b[0]) / den
    return (cx + ox, cy + oy), math.hypot(cx, cy)


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
        dist = {k: abs(offset_from_line(points[k], points[i], points[j])) for k in range(i + 1, j)}
        best = max(dist.values(), default=0.0)
        if best > tolerance:
            # i più lontani a pari merito (entro il rumore) si tengono tutti:
            # sceglierne uno lo farebbe il verso o l'ultimo bit (G6e)
            cuts = [i] + [k for k, d in dist.items() if d >= best - FLOAT_NOISE] + [j]
            keep.update(cuts)
            stack.extend(zip(cuts, cuts[1:]))
    return sorted(keep)
