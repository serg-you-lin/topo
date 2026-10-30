"""
topo/core/geometry/lines.py
----------------------------
Fatti fra rette e contorni: distanza da una retta, tratti sulla stessa retta,
file di tratti unite attraverso dei contorni, una corda che divide un
contorno, il tratteggio di un segmento. Geometria pura: che quella corda sia
una piega lo dice il consumatore (MAP.md D93). Le domande su un contorno si
fanno sulle sue primitive (`rings`, D166, D167).

Un tratto è una coppia di punti `(start, end)` o qualunque cosa porti
`start`/`end` (un `LineSeg`, un `Edge`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence, Tuple

from .rings import ON_BOUNDARY, ring_bbox, ring_covers_chord, ring_split_by_chord

Point = Tuple[float, float]

COLLINEAR_TOLERANCE = 0.1        # distanza massima dalla retta, unità del disegno
COLLINEAR_ANGLE_TOLERANCE = 1e-6  # differenza massima di direzione, radianti


def _ends(item) -> Tuple[Point, Point]:
    """I due capi di un tratto: `(start, end)`, o `item.start`/`item.end`."""
    if hasattr(item, "start") and hasattr(item, "end"):
        return tuple(item.start[:2]), tuple(item.end[:2])
    start, end = item
    return tuple(start), tuple(end)


def point_line_distance(point: Point, a: Point, b: Point) -> float:
    """Distanza di `point` dalla retta infinita per `a`, `b`; da `a` se i due coincidono."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return math.dist(point, a)
    return abs(dy * (point[0] - a[0]) - dx * (point[1] - a[1])) / length


def are_collinear(a, b, tolerance: float = COLLINEAR_TOLERANCE,
                  angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> bool:
    """
    I tratti `a` e `b` stanno sulla stessa retta infinita: direzioni uguali
    entro `angle_tolerance` (radianti, a meno del verso) e i due capi di `b`
    entro `tolerance` dalla retta di `a`.
    """
    (a0, a1), (b0, b1) = _ends(a), _ends(b)
    ang_a = math.atan2(a1[1] - a0[1], a1[0] - a0[0]) % math.pi
    ang_b = math.atan2(b1[1] - b0[1], b1[0] - b0[0]) % math.pi
    diff = abs(ang_a - ang_b)
    if min(diff, math.pi - diff) > angle_tolerance:
        return False
    return all(point_line_distance(q, a0, a1) <= tolerance for q in (b0, b1))


def group_collinear_lines(lines: list, *, tolerance: float = COLLINEAR_TOLERANCE,
                          angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> list:
    """
    Tratti raggruppati per retta: [[L1, L2], [L3], ...]. Ogni gruppo prende la
    retta del suo primo tratto, nell'ordine dato.
    """
    groups = []
    assigned = set()
    for i, line in enumerate(lines):
        if i in assigned:
            continue
        group = [line]
        assigned.add(i)
        for j, other in enumerate(lines):
            if j not in assigned and are_collinear(line, other, tolerance, angle_tolerance):
                group.append(other)
                assigned.add(j)
        groups.append(group)
    return groups


def splits_contour(contour, start: Point, end: Point, *, reach: float = 0.0) -> bool:
    """
    True if the chord `start`-`end`, extended by `reach` at both ends, cuts
    the region of `contour` in two or more parts: some stretch of it runs
    from boundary to boundary through the inside. A touch, or a stretch along
    the boundary, does not cut. `contour` is a `Contour`, anything with a
    closed ring of `segments`, or the segment list itself (MAP.md D166).
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    norm = math.hypot(dx, dy)
    if norm == 0:
        return False
    ux, uy = dx / norm * reach, dy / norm * reach
    return ring_split_by_chord(_ring(contour), (start[0] - ux, start[1] - uy), (end[0] + ux, end[1] + uy))


def _ring(item) -> list:
    return list(getattr(item, "segments", item) or [])


@dataclass(frozen=True)
class CollinearRun:
    """
    Tratti sulla stessa retta, in fila lungo di essa.

    start, end: i capi esterni della fila
    members:    indici dei tratti nell'input, nell'ordine lungo la retta
    """
    start: Point
    end: Point
    members: Tuple[int, ...]


def bridged_runs(segments: Sequence, bridges: Sequence, *, tolerance: float = COLLINEAR_TOLERANCE,
                 angle_tolerance: float = COLLINEAR_ANGLE_TOLERANCE) -> list[CollinearRun]:
    """
    Runs of two or more strokes on one line where the gap between a stroke
    and the next lies wholly inside one of `bridges` (contours, items with a
    closed ring of `segments`, or segment lists; boundary included). A
    stroke is a `(start, end)` pair or anything with `start`/`end`; it
    belongs to one run at most, strokes left alone are not returned.
    """
    rings = [(r, ring_bbox(r)) for r in map(_ring, bridges) if r]
    ends = [_ends(s) for s in segments]
    runs: list[CollinearRun] = []
    used: set[int] = set()
    for i, (p0, p1) in enumerate(ends):
        if i in used:
            continue
        group = [j for j in range(len(ends))
                 if j not in used and are_collinear((p0, p1), ends[j], tolerance, angle_tolerance)]
        used.update(group)
        if len(group) < 2:
            continue
        norm = math.dist(p0, p1)
        ux, uy = (p1[0] - p0[0]) / norm, (p1[1] - p0[1]) / norm
        along = lambda q: (q[0] - p0[0]) * ux + (q[1] - p0[1]) * uy
        spans = sorted(((along(lo), lo, hi, j) for j in group
                        for lo, hi in [sorted(ends[j], key=along)]), key=lambda t: t[0])
        chain = [spans[0]]
        for span in spans[1:]:
            if _bridged(chain[-1][2], span[1], rings):
                chain.append(span)
                continue
            if len(chain) >= 2:
                runs.append(CollinearRun(chain[0][1], chain[-1][2], tuple(t[3] for t in chain)))
            chain = [span]
        if len(chain) >= 2:
            runs.append(CollinearRun(chain[0][1], chain[-1][2], tuple(t[3] for t in chain)))
    return runs


def _bridged(a: Point, b: Point, rings: list) -> bool:
    """Lo spazio `a`→`b` sta tutto dentro uno dei giri (bordo compreso)."""
    if math.dist(a, b) == 0:
        return False
    e = ON_BOUNDARY
    lo_x, hi_x, lo_y, hi_y = min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1])
    return any(box[0] - e <= lo_x and hi_x <= box[2] + e and box[1] - e <= lo_y and hi_y <= box[3] + e
               and ring_covers_chord(ring, a, b) for ring, box in rings)


def dash_line(start: Point, end: Point, head: float, tail: float,
              *, middle: float = 0.0, n_middle: int = 0) -> list[Tuple[Point, Point]]:
    """
    Il segmento `start`→`end` ridotto a tratti: uno lungo `head` che parte da
    `start`, uno lungo `tail` che finisce in `end`, e `n_middle` tratti lunghi
    `middle` fra i due, con tutti i vuoti uguali. Ogni tratto è `(start, end)`
    nel verso del segmento; un tratto lungo zero non compare.

    Se i tratti coprono tutto il segmento (o di più) il segmento torna intero:
    non resta nessun vuoto da lasciare. Lunghezze negative → ValueError.
    """
    if min(head, tail, middle) < 0 or n_middle < 0:
        raise ValueError("dash_line: lunghezze e numero di tratti devono essere ≥ 0")
    length = math.dist(start, end)
    covered = head + tail + n_middle * middle
    if covered >= length:
        return [(start, end)]
    ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    at = lambda t: (start[0] + ux * t, start[1] + uy * t)
    gap = (length - covered) / (n_middle + 1)
    spans = [(0.0, head)]
    t = head
    for _ in range(n_middle):
        t += gap
        spans.append((t, t + middle))
        t += middle
    spans.append((length - tail, length))
    return [(at(a), at(b)) for a, b in spans if b > a]
