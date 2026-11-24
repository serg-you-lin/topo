"""
rules/validator.py
------------------
Validation of geometric health: it reads and returns facts as `Diagnostic`
inside a Result, never a guess about what heal() will do.

Two distinct validations, both useful:

    validate_document(doc) — INPUT, before heal(): the facts about the Document
                           (empty, zero-length strokes) and what the adapter
                           said about the file.
    validate_result(res) — OUTPUT, after heal(). Checks that the clusters
                           produced are sound (valid polygon, contained holes,
                           area). Called by faces() and outlines().
"""


import math

from ..model import Result
from ..model.document import Document
from ..model.diagnostic import Diagnostic, plural
from ..core.primitives.line import LineSeg
from ..core.geometry.shapely_polygons import curve_polygon
from ..core.geometry.measure import FLOAT_NOISE
from ..core.geometry.rings import ring_jumps
from ..core.geometry.intersections import intersections
from ..precision import SAME_POINT


# INPUT — before heal()

def validate_document(doc: Document) -> Result:
    """
    Check a `Document` before `heal()`, without changing it.

    Returns a `Result` with only `warnings` / `notes` / `errors` / `is_valid`
    (no clusters), all `topo.Diagnostic`: what the adapter said about
    the source, plus

    - error `empty`: no edges (only texts, or nothing), or every edge has zero length;
    - warning `zero-length`: edges whose two ends are one point.

    It reports facts about the input, never a guess about what `heal()` will do.
    """
    if not isinstance(doc, Document):
        raise TypeError(f"topo.validate_document() takes a Document, got {type(doc).__name__}")

    result = Result(source_file=doc.source_path, source_format=doc.source_format)
    edges = doc.edges
    # what the adapter said about the raw file: validate_document() is the only
    # point to look at before heal()
    result.warnings.extend(doc.warnings)
    result.notes.extend(doc.notes)

    if not edges:
        result.errors.append(Diagnostic(
            "empty", "the document has only texts, no edges" if doc.texts else "the document has no edges",
            level="error"))
        return result

    zero_len = [e for e in edges
                if e.start == e.end and isinstance(e.segment, LineSeg)]
    if zero_len and len(zero_len) == len(edges):
        result.errors.append(Diagnostic(
            "empty", "every edge has zero length", points=[e.start for e in zero_len], level="error"))
        return result
    if zero_len:
        result.warnings.append(Diagnostic(
            "zero-length", f"{plural(len(zero_len), 'edge', 'edges')} of zero length, dropped by heal()",
            points=[e.start for e in zero_len],
            help="remove them from the drawing, or leave them: they change nothing"))
    return result


# OUTPUT — after heal()

def validate_result(result: Result) -> None:
    """
    Check the clusters of a `Result` a reading produced. **Mutates** `result`:
    adds `topo.Diagnostic` warnings and errors (an error makes it invalid); returns
    `None`. Called by `Network.faces()` and `Network.outlines()`.

    - error `open-contour`: an outer or inner that does not close head to tail
      beyond float noise;
    - error `no-area`: an outer with no polygon or zero area;
    - warning `self-intersecting`: an outer polygon that crosses itself;
    - warning `inner-outside`: an inner not wholly inside its outer.
    """
    for i, cluster in enumerate(result.clusters):
        label = cluster.label or f"cluster {i}"

        for name, contour in [("outer", cluster.outer)] + [
                (f"inner {j}", c) for j, c in enumerate(cluster.inners)]:
            jumps = [(end, math.dist(end, start)) for end, start in ring_jumps(contour.segments)
                     if math.dist(end, start) > FLOAT_NOISE]
            if jumps:
                result.errors.append(Diagnostic(
                    "open-contour", f"{label}: {name} does not close, {plural(len(jumps), 'jump', 'jumps')}",
                    points=[p for p, _ in jumps], notes=[f"widest {max(d for _, d in jumps):.6g} mm"],
                    level="error"))

        poly = curve_polygon(cluster.outer)
        if poly is None or poly.is_empty or poly.area <= 0:
            result.errors.append(Diagnostic(
                "no-area", f"{label}: the outer encloses no area",
                points=[cluster.outer.segments[0].start] if cluster.outer.segments else [], level="error"))
            continue

        if not poly.is_valid:
            result.warnings.append(Diagnostic(
                "self-intersecting", f"{label}: the outer contour crosses itself",
                points=_ring_crossings(cluster.outer.segments) or [cluster.outer.segments[0].start],
                help="in the drawing, remove the crossing of the outer contour"))

        outside = [inner for inner in cluster.inners if not poly.contains(curve_polygon(inner))]
        if outside:
            result.warnings.append(Diagnostic(
                "inner-outside", f"{label}: {plural(len(outside), 'inner is', 'inners are')} not wholly "
                                 f"inside the outer",
                points=[inner.segments[0].start for inner in outside]))


def _ring_crossings(segments: list) -> list:
    """Where a ring meets itself away from the joint of two consecutive sides."""
    n, found = len(segments), []
    for i in range(n):
        for j in range(i + 1, n):
            for p in intersections(segments[i], segments[j]):
                joints = []
                if j == i + 1:
                    joints.append(segments[i].endpoints()[1])
                if i == 0 and j == n - 1:
                    joints.append(segments[0].endpoints()[0])
                if all(math.dist(p, q) > SAME_POINT for q in joints) and                         all(math.dist(p, q) > SAME_POINT for q in found):
                    found.append(p)
    return found
