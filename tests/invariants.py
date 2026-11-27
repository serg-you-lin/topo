"""
tests/invariants.py
-------------------
The tools common to the invariants of the two readings (test_heal_invariants.py,
test_outlines_invariants.py):

- what is done to a drawing without changing its shape: rigid motions
  (rotation, translation far from the origin, mirror) and different orders of
  the entities. A reading that depends on one of these depends on how the file
  was written, not on the geometry;
- the comparison of two readings (polygons paired one to one);
- the `loose` stretches running along a contour: an input piece that came out
  twice;
- the jumps inside a delivered contour.
"""

import math
import random
from dataclasses import replace

from shapely import affinity
from shapely.errors import GEOSException
from shapely import STRtree, prepare
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from topo.core.geometry.measure import FLOAT_NOISE
from topo.core.topology.edge import node_point
from topo.core.geometry.rings import ring_jumps
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE, segment_endpoints
from topo.core.primitives.motion import _rotate_point, _translate_point
from topo.model.document import Document
from topo import to_shapely

QUARTER = math.pi / 2                 # exact on the node grid: no new rounding
ROTATION = 0.7                        # radians, any angle: the nodes come back on the grid
# far from the origin (2.5 km, 1.5 km), on the node grid: a double still has ~10
# digits below the millimetre, but every product of coordinates (cross products,
# areas) loses 6-7 digits relative to the origin
FAR = (2.5e6, -1.5e6)
SHUFFLES = 5                          # shufflings per drawing, seed 0..SHUFFLES-1
GRID = 1e-6
# two discretizations of the same stretch of curve are at most this far apart
# (every chord is within DEFAULT_TOLERANCE of the curve, on the same side)
ON_CONTOUR = DEFAULT_TOLERANCE
# a `loose` stretch within ON_CONTOUR of a contour for more than this runs along
# the contour: a crossing stays there only below ~1° (2·ON_CONTOUR/sin θ), a
# tangency only with radius above ~12 mm (2·√(2·R·ON_CONTOUR))
ALONG = 1.0
TWICE = 1.9                           # input along the stretch, in stretch lengths: two pieces


def moved(doc: Document, move) -> Document:
    """`doc` with every segment passed through `move` (segment → segment) and the
    nodes on the load grid, like `topo.experimental.rotate_document`."""
    edges = []
    for edge in doc.edges:
        seg = move(edge.segment)
        start, end = segment_endpoints(seg)
        edges.append(replace(edge, segment=seg, start=node_point(start), end=node_point(end)))
    return replace(doc, edges=edges)


def rigid(angle: float, dx: float, dy: float):
    """(motion of the segment, motion of the point) for any motion: rotate by `angle`
    about the origin, then translate. The point does the same computation as the
    segment (`.rotated().translated()`), bit for bit: for micro-cases, where the
    red comes from a precise motion, not from MOTIONS."""
    def point(p):
        return _translate_point(_rotate_point(p, angle, (0.0, 0.0)), dx, dy)
    return (lambda s: s.rotated(angle).translated(dx, dy)), point


# (name, segment motion, inverse motion of a shapely polygon, exact on the grid)
MOTIONS = [
    ("rotation", lambda s: s.rotated(ROTATION),
     lambda p: affinity.rotate(p, -ROTATION, origin=(0, 0), use_radians=True), False),
    ("quarter turn", lambda s: s.rotated(QUARTER),
     lambda p: affinity.rotate(p, -QUARTER, origin=(0, 0), use_radians=True), True),
    ("far", lambda s: s.translated(*FAR),
     lambda p: affinity.translate(p, -FAR[0], -FAR[1]), True),
    ("mirror", lambda s: s.mirrored(),
     lambda p: affinity.scale(p, 1.0, -1.0, origin=(0, 0)), True),
]


def scrambled(doc: Document, angle: float = ROTATION, seed: int = 0) -> Document:
    """`doc` written another way, all at once: edges shuffled (`seed`), rotated by
    `angle`, moved by FAR and mirrored. One reading instead of one per motion and
    per order: if the reading depends on any of these, it changes here too; which
    one is told by the diagnosis, which tries the motions and orders one at a time."""
    edges = list(doc.edges)
    random.Random(seed).shuffle(edges)
    return moved(replace(doc, edges=edges), lambda s: s.rotated(angle).translated(*FAR).mirrored())


def unscrambled(poly, angle: float = ROTATION):
    """The shapely polygon of a reading of `scrambled(doc, angle)` brought back to
    the frame of `doc`."""
    poly = affinity.scale(poly, 1.0, -1.0, origin=(0, 0))
    poly = affinity.translate(poly, -FAR[0], -FAR[1])
    return affinity.rotate(poly, -angle, origin=(0, 0), use_radians=True)


def orders(edges: list) -> list:
    """(name, edges) for every order tried: reversed, plus SHUFFLES reproducible shufflings."""
    result = [("reversed", list(reversed(edges)))]
    for seed in range(SHUFFLES):
        shuffled = list(edges)
        random.Random(seed).shuffle(shuffled)
        result.append((f"seed {seed}", shuffled))
    return result


def geometry(segment):
    """The segment as a shapely geometry, discretized at DEFAULT_TOLERANCE."""
    pts = segment.discretize(tolerance=DEFAULT_TOLERANCE)
    if len(pts) < 2 or all(p == pts[0] for p in pts):
        return Point(pts[0])
    return LineString(pts)


def _differ_by(a, b) -> float:
    """Area of the symmetric difference of `a` and `b`, on the micron grid: GEOS, on
    two polygons equal to 1e-13 with nearly aligned vertices, may give the whole
    union as the difference. Infinite if GEOS cannot compute it (a non-simple
    polygon): two shapes that cannot be compared are not twins."""
    try:
        return a.symmetric_difference(b, grid_size=GRID).area
    except GEOSException:
        return math.inf


def _could_be_twins(a, b, band: float) -> bool:
    """False only if the symmetric difference of `a` and `b` certainly exceeds
    `band`: with disjoint extents it is the sum of the areas. It avoids the real
    comparison, which is the expensive computation, between distant holes."""
    ax0, ay0, ax1, ay1 = a.bounds
    bx0, by0, bx1, by1 = b.bounds
    apart = ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0
    return not apart or a.area + b.area <= band


def shape_differences(before: list, after: list, band_per_mm: float) -> list:
    """The polygons of `before` without a twin in `after` (symmetric difference below
    `band_per_mm` per mm of perimeter), paired one to one."""
    free = list(after)
    missing = []
    for poly in before:
        band = poly.length * band_per_mm
        twin = next((other for other in free if _could_be_twins(poly, other, band)
                     and _differ_by(poly, other) <= band), None)
        if twin is None:
            missing.append(tuple(round(v, 2) for v in poly.bounds))
        else:
            free.remove(twin)
    return missing


def contours(result) -> list:
    """(outer, inner) of `result`: the polygons of the outers and of all the inners."""
    return ([to_shapely(c.outer) for c in result.clusters],
            [to_shapely(i) for c in result.clusters for i in c.inners])


class _Bands:
    """The bands of width `distance` around `geoms`, built once per geometry. The
    band around a union is the union of the bands: redoing the neighbours' buffer
    for every curve cost millions of vertices on a drawing with many short sides."""

    def __init__(self, geoms: list, distance: float):
        self.distance = distance
        self.tree = STRtree(geoms)
        self.bands = [g.buffer(distance) for g in geoms]
        prepare(self.bands)

    def near(self, curve):
        """The band around the geometries near `curve`, or None if none is near. Within
        `distance` of `curve` it is the band around all of them: the others do not reach it."""
        near = self.tree.query(curve, predicate="dwithin", distance=self.distance)
        if len(near) == 0:
            return None
        # the normal case: the curve lies wholly in the band of a single neighbour
        for i in near:
            if self.bands[i].covers(curve):
                return self.bands[i]
        return unary_union([self.bands[i] for i in near])


def _rims(result) -> list:
    return [geometry(s) for c in result.clusters for ct in [c.outer] + c.inners for s in ct.segments]


def along_contours(result, doc: Document) -> list:
    """The stretches of `result.loose` running along a contour (within ON_CONTOUR for
    more than ALONG mm): (length, point) for each. Every input piece comes out once
    — either in a contour or in `loose` — so the list is empty. A stretch where
    the input of `doc` has two pieces (a circle retraced by a polyline) does not
    count: they are two pieces, and each comes out once."""
    rims = _rims(result)
    if not rims:
        return []
    bands = _Bands(rims, ON_CONTOUR)
    inputs = [geometry(e.segment) for e in doc.edges]
    tree = STRtree(inputs)
    found = []
    for curve in result.loose:
        for segment in curve.segments:
            loose = geometry(segment)
            band = bands.near(loose)
            if band is None:
                continue
            shared = loose.intersection(band)
            for piece in getattr(shared, "geoms", [shared]):
                if piece.length > ALONG and not _twice_in_input(piece, inputs, tree):
                    point = piece.representative_point()
                    found.append((round(piece.length, 2), (round(point.x, 1), round(point.y, 1))))
    return found


def _twice_in_input(piece, inputs: list, tree) -> bool:
    """True if the input covers `piece` at least twice: its length within ON_CONTOUR
    of `piece` is nearly double `piece`."""
    zone = piece.buffer(ON_CONTOUR)
    near = tree.query(zone, predicate="intersects")
    covered = sum(inputs[int(i)].intersection(zone).length for i in near)
    return covered >= TWICE * piece.length


def uncovered(doc: Document, result, distance: float):
    """The input geometry of `doc` farther than `distance` from every output of
    `result` (segments of the contours and of `loose`)."""
    outputs = _rims(result) + [geometry(s) for f in result.loose for s in f.segments]
    # an input that came out unchanged (in both directions) is covered: skip the
    # band computation, which is the expensive one, for almost every edge
    same = {tuple(g.coords) for g in outputs} | {tuple(g.coords)[::-1] for g in outputs}
    bands = _Bands(outputs, distance)
    lost = []
    for edge in doc.edges:
        curve = geometry(edge.segment)
        if tuple(curve.coords) in same:
            continue
        band = bands.near(curve)
        lost.append(curve if band is None else curve.difference(band))
    return unary_union(lost)


def known_defect(test, where: str, gate: str, check) -> None:
    """Run `check()` for a case of a known defect, open in the gate (`gate`):
    it must fail, and the case comes out as a skip with the gate's
    entry. If it passes the defect is solved and the test fails until the case
    leaves the list."""
    try:
        check()
    except AssertionError:
        test.skipTest(f"known defect, {gate}: {where}")
    test.fail(f"{where} passes: the defect of {gate} is solved, remove the case from the list")


def contour_jumps(result) -> list:
    """(cluster, contour, length, point) of every jump beyond FLOAT_NOISE between a
    segment and the next in the delivered contours: it must be empty."""
    found = []
    for ci, cluster in enumerate(result.clusters):
        for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in enumerate(cluster.inners)]:
            for end, start in ring_jumps(contour.segments):
                gap = math.dist(end, start)
                if gap > FLOAT_NOISE:
                    found.append((ci, name, gap, end))
    return found


# --- Messages: every warning, note and error of a reading is a Diagnostic of its level, with a code from this list. A new code is added here and in docs/LLM.md, never on the way. ---

DIAGNOSTIC_CODES = {
    "warning": {"set-aside", "near-copy", "open-arc", "near-gap", "tie", "crossing", "self-crossing", "closed-touch",
                "zero-length", "self-intersecting", "inner-outside", "not-rotated",
                "rim-cut", "face-colour"},
    "note": {"merged-lines", "merged-arcs", "welded", "arc-joined", "open-spline", "non-contour",
             "no-loop", "free-end", "joining-edge", "gap-closed", "ends-joined", "curves-moved", "tied-ends-joined", "arc-bent"},
    "error": {"empty", "no-closed-outer", "open-contour", "no-area"},
}

# The codes of the DXF adapter: its warnings and notes travel in `Document.warnings` / `Document.notes`.
DXF_DIAGNOSTIC_CODES = {
    "warning": {"dxf-audit", "dxf-dimension-no-block", "dxf-dimension-written-number", "dxf-explode-failed",
                "dxf-hatch-open-boundary", "dxf-inserts-ignored", "dxf-layer-skipped", "dxf-no-curve",
                "dxf-not-modeled", "dxf-oda-path"},
    "note": {"dxf-dwg-converted", "dxf-fills-exploded", "dxf-flattened", "dxf-hatches-exploded",
             "dxf-inserts-exploded", "dxf-leaders-exploded", "dxf-upgraded"},
}

# Codes built in a loop, so the scan of the sources does not see them as literals.
DYNAMIC_CODES = {"merged-lines", "merged-arcs", "welded"}

# Codes no input has made fire. Each one waits for a decision (an input that fires it, or its removal):
# the suite fails when one of them fires, so it leaves this set, and when any other code never fires.
UNREACHED_CODES = {"rim-cut", "face-colour"}


def all_codes() -> set:
    return {c for table in (DIAGNOSTIC_CODES, DXF_DIAGNOSTIC_CODES) for codes in table.values() for c in codes}


def source_codes(root) -> set:
    """The codes written as a literal in `Diagnostic("code", ...)` calls of the packages under `root`."""
    import ast
    found = set()
    for package in ("topo", "topo_dxf", "topo_pdf"):
        for path in (root / package).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Diagnostic" and node.args                         and isinstance(node.args[0], ast.Constant):
                    found.add(node.args[0].value)
    return found


def message_problems(result) -> list:
    """The messages of `result` that do not respect the rule: not a Diagnostic, in
    the wrong channel, or with a code outside the list."""
    from topo.model.diagnostic import Diagnostic
    problems = []
    for channel, level in ((result.warnings, "warning"), (result.notes, "note"), (result.errors, "error")):
        for m in channel:
            if not isinstance(m, Diagnostic):
                problems.append(f"{level}: not a Diagnostic: {m[:80]!r}")
            elif m.level != level or m.code not in DIAGNOSTIC_CODES[level]:
                problems.append(f"{level}: {m.level}[{m.code}] out of place")
    return problems
