"""
topo/core/geometry/measure.py
------------------------------
Misure di primitive e tracce: arrotondamento dei nodi, lunghezza e angolo di
un segmento, vertici e tipo di una traccia aperta, "è circolare?".
"""

import math
from typing import Optional, Tuple, List

from shapely.geometry import LineString, box

from ..primitives.segments import LineSeg, ArcSeg, CircleSeg, EllipseSeg, BSplineSeg

Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Arrotondamento
# ---------------------------------------------------------------------------

NODE_DECIMALS = 3   # griglia unica dei nodi, per ogni lettura e ogni tolleranza (MAP.md D113)


def round_point(pt, decimals: int = NODE_DECIMALS) -> Tuple:
    return (round(float(pt[0]), decimals), round(float(pt[1]), decimals))


# ---------------------------------------------------------------------------
# Archi e bulge
# ---------------------------------------------------------------------------

def num_segments_for_bulge(bulge: float) -> int:
    """Numero di segmenti per discretizzare un arco dato il suo bulge."""
    angle = 4 * math.atan(abs(bulge))
    return max(8, int(angle / math.pi * 32))


# ---------------------------------------------------------------------------
# Tracce aperte — vertici / lunghezza / tipo da segmenti nativi
# ---------------------------------------------------------------------------
# Una traccia aperta (bending line, incisione, frammento non chiuso) nel modello
# è una lista di segmenti nativi (LineSeg / ArcSeg / BSplineSeg / CircleSeg).
# `pts`, `length`, `shape_type` sono valori DERIVATI da quei segmenti: qui, non
# stoccati sul modello. Chi li consuma — detect_flat(), write._write_loose,
# inspect() — li ricava con queste funzioni.

def track_points(segments, tolerance: Optional[float] = None) -> List[Point]:
    """
    Vertici di una traccia aperta come catena di segmenti nativi.

    Concatena `seg.discretize()` di ogni segmento, deduplicando il vertice
    condiviso alla giunzione fra un segmento e il successivo.
    """
    pts: List[Point] = []
    for seg in segments or []:
        seg_pts = seg.discretize() if tolerance is None else seg.discretize(tolerance)
        if not seg_pts:
            continue
        if pts and math.dist(pts[-1], seg_pts[0]) < 1e-9:
            pts.extend(seg_pts[1:])
        else:
            pts.extend(seg_pts)
    return pts


def track_length(pts) -> float:
    """Lunghezza totale di una polilinea (somma delle corde)."""
    return sum(
        math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    )


def track_shape_type(pts) -> str:
    """`"line"` se la traccia è un solo segmento retto (2 vertici), altrimenti `"curve"`."""
    return "line" if len(pts) == 2 else "curve"


# ---------------------------------------------------------------------------
# Lunghezza e angolo di UNA primitiva nativa — mai stoccati sul modello,
# sempre derivati (stesso principio di track_length/track_shape_type sopra,
# ma su un singolo segmento invece che su una catena)
# ---------------------------------------------------------------------------

def segment_length(segment) -> float:
    """
    Lunghezza reale di una primitiva nativa singola (`LineSeg`/`ArcSeg`/
    `BSplineSeg`/`CircleSeg`/`EllipseSeg`). `LineSeg`/`ArcSeg`/`CircleSeg`
    hanno una formula chiusa; `BSplineSeg`/`EllipseSeg` (curvatura non
    costante, nessuna formula chiusa comoda) riusano la stessa polilinea di
    `discretize()`, sommata come `track_length`.
    """
    if isinstance(segment, LineSeg):
        return math.hypot(segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])
    if isinstance(segment, ArcSeg):
        return segment.radius * segment._sweep()
    if isinstance(segment, CircleSeg):
        return 2 * math.pi * segment.radius
    return track_length(segment.discretize())


def length_inside(segment, bounds: Tuple[float, float, float, float]) -> float:
    """
    Quanta parte di `segment` (qualunque primitiva nativa) sta dentro il
    rettangolo `bounds` = (xmin, ymin, xmax, ymax), bordo compreso. Le curve
    sulla polilinea di `discretize()`.
    """
    pts = segment.discretize()
    if len(pts) < 2:
        return 0.0
    return LineString(pts).intersection(box(*bounds)).length


def longest_segment(segments) -> Tuple[Optional[object], float]:
    """
    `(segment, length)` del segmento più lungo in `segments` — `(None, 0.0)`
    se la lista è vuota. Confronto lineare via `segment_length`.
    """
    best_seg, best_len = None, 0.0
    for seg in segments or []:
        length = segment_length(seg)
        if best_seg is None or length > best_len:
            best_seg, best_len = seg, length
    return best_seg, best_len


def chord_angle_deg(a: Point, b: Point) -> float:
    """
    Angolo (gradi, 0-180°) della corda da `a` a `b`. Modulo 180 perché una
    linea non ha un verso proprio (`a->b` e `b->a` sono lo stesso
    orientamento) — stesso calcolo già usato da `detect._detect_bending` per
    l'angolo di una bending line, ora condiviso qui invece che duplicato.
    """
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


# ---------------------------------------------------------------------------
# Portata di una primitiva lungo una direzione — sulla curva, non sul poligono
# ---------------------------------------------------------------------------
# Il poligono di discretize() è inscritto: la sua proiezione è più corta della
# curva fino a 2·tol. Qui (min, max) di p·d sulla curva vera (MAP.md D156).

def segment_reach(segment, direction: Point) -> Tuple[float, float]:
    """
    (min, max) della proiezione dei punti di `segment` sul versore
    `direction`. Esatta per retta, arco, cerchio, ellisse (estremi in forma
    chiusa); per la B-spline estremi locali dei campioni raffinati sul
    parametro fino alla precisione di macchina. Per molte direzioni sullo
    stesso segmento usa `Reach`, che campiona la spline una volta sola.
    """
    return Reach(segment)(direction)


class Reach:
    """`segment_reach` di un segmento fissato, per molte direzioni."""

    def __init__(self, segment):
        self.segment = segment
        self._samples = _spline_samples(segment) if isinstance(segment, BSplineSeg) else None

    def __call__(self, direction: Point) -> Tuple[float, float]:
        dx, dy = direction
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm

        def dot(p):
            return p[0] * dx + p[1] * dy

        segment = self.segment
        if isinstance(segment, LineSeg):
            a, b = dot(segment.start), dot(segment.end)
            return min(a, b), max(a, b)
        if isinstance(segment, CircleSeg):
            c = dot(segment.center)
            return c - segment.radius, c + segment.radius
        if isinstance(segment, ArcSeg):
            # p·d = c·d + r·cos(θ − φ): estremi a θ = φ e φ + π, se l'arco ci passa
            phi = math.atan2(dy, dx)
            sweep = segment._sweep()
            values = [dot(segment._point_at(segment.start_angle)),
                      dot(segment._point_at(segment.end_angle))]
            values += [dot(segment._point_at(t)) for t in (phi, phi + math.pi)
                       if _on_sweep(segment.start_angle, segment.ccw, sweep, t)]
            return min(values), max(values)
        if isinstance(segment, EllipseSeg):
            # p·d = c·d + A·cos t + B·sin t: estremi a t = atan2(B, A) e + π
            mx, my = segment.major_axis
            a_coef = mx * dx + my * dy
            b_coef = segment.ratio * (-my * dx + mx * dy)
            t0 = math.atan2(b_coef, a_coef)
            sweep = segment._sweep()
            values = [dot(segment._point_at(segment.start_param)),
                      dot(segment._point_at(segment.end_param))]
            values += [dot(segment._point_at(t)) for t in (t0, t0 + math.pi)
                       if _on_sweep(segment.start_param, segment.ccw, sweep, t)]
            return min(values), max(values)
        if isinstance(segment, BSplineSeg):
            return self._spline(dot)
        raise TypeError(f"Primitiva non supportata: {type(segment).__name__}")

    def _spline(self, dot) -> Tuple[float, float]:
        """
        Estremi dei campioni, poi ogni estremo locale che può ancora vincere
        raffinato per sezione aurea fra i due campioni vicini. Fra due campioni
        la curva non si allontana dalla loro proiezione più della sua
        lunghezza lì, stimata dalle due corde: un estremo locale più indietro
        di così non può superare quello dei campioni.
        """
        ts, pts, reach = self._samples
        values = [dot(p) for p in pts]
        lo_v, hi_v = min(values), max(values)
        best = {1.0: hi_v, -1.0: -lo_v}
        last = len(ts) - 1
        for sign in (1.0, -1.0):
            for i in range(len(ts)):
                a, b = max(i - 1, 0), min(i + 1, last)
                v = sign * values[i]
                if v < sign * values[a] or v < sign * values[b] or v + reach[i] < best[sign]:
                    continue
                _t, refined = golden_max(lambda t: sign * dot(self.segment._evaluate(t)), ts[a], ts[b])
                best[sign] = max(best[sign], refined)
        return -best[-1.0], best[1.0]


def _on_sweep(start: float, ccw: bool, sweep: float, t: float) -> bool:
    """True se l'angolo `t` cade nell'intervallo percorso da `start` per `sweep`."""
    offset = ((t - start) if ccw else (start - t)) % (2 * math.pi)
    return offset <= sweep + 1e-12


_SPLINE_SAMPLES_PER_SPAN = 16


def _spline_samples(segment: BSplineSeg):
    """
    (parametri, punti, portata di ciascun campione): campioni regolari su ogni
    intervallo di nodi (uno span è un polinomio di grado basso, 16 campioni
    separano i suoi estremi); la portata è la somma delle due corde vicine.
    """
    k, p = segment.knots, segment.degree
    breaks = sorted(set(k[p:len(k) - p]))
    ts = [breaks[0]]
    for lo, hi in zip(breaks, breaks[1:]):
        ts += [lo + (hi - lo) * i / _SPLINE_SAMPLES_PER_SPAN for i in range(1, _SPLINE_SAMPLES_PER_SPAN + 1)]
    pts = [segment._evaluate(t) for t in ts]
    chords = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    reach = [(chords[i - 1] if i > 0 else 0.0) + (chords[i] if i < len(chords) else 0.0)
             for i in range(len(pts))]
    return ts, pts, reach


def golden_max(f, a: float, b: float, iterations: int = 40) -> Tuple[float, float]:
    """(x, f(x)) del massimo di `f` unimodale su [a, b], per sezione aurea."""
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iterations):
        if fc > fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return (c, fc) if fc > fd else (d, fd)


# ---------------------------------------------------------------------------
# Geometria circolare — diametro / centro di un contorno chiuso ~circolare
# ---------------------------------------------------------------------------
# Serve alla regola di processo `Ø < max_drill_diameter → foro` che vive in
# detect_flat(): dato un contorno interno, questo helper dice se è geometricamente
# un cerchio e con quale diametro/centro. Prima la stessa logica stava in
# `hierarchy._single_loop_geometry` e i valori erano stoccati su ClosedCurve
# (campi rimossi in D15) — ora si ricava qui, al momento della classificazione.

CIRCULAR_BBOX_ASPECT_TOLERANCE = 0.15


def circular_geometry(polygon, segments=None):
    """
    (diameter, center) se il contorno è ~circolare, altrimenti (None, None).

    Un contorno è "circolare" (candidato foro da punta) solo se:
      - è fatto di UNA sola primitiva nativa (`len(segments) == 1`) — un CIRCLE
        o un arco chiuso, non una polilinea multi-lato; e
      - il suo bounding box è ~quadrato (larghezza e altezza combaciano entro
        `CIRCULAR_BBOX_ASPECT_TOLERANCE`).
    Diametro = min(width, height) del bbox, centro = centro del bbox.

    È la stessa regola del vecchio `hierarchy._single_loop_geometry`
    (gate `len(loop) == 1` + aspect ratio): D15 la sposta qui senza cambiarne
    i numeri, così i golden non si spostano per la sola misura.
    """
    if len(list(segments or [])) != 1:
        return None, None

    if polygon is None or polygon.is_empty:
        return None, None

    minx, miny, maxx, maxy = polygon.bounds
    width  = maxx - minx
    height = maxy - miny
    if width <= 0 or height <= 0:
        return None, None
    if abs(width - height) / max(width, height) > CIRCULAR_BBOX_ASPECT_TOLERANCE:
        return None, None

    return min(width, height), ((minx + maxx) / 2, (miny + maxy) / 2)
