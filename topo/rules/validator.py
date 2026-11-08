"""
rules/validator.py
------------------
Validazione della salute geometrica: legge e restituisce i fatti come
`Diagnostic` dentro un Result (D233), mai un'ipotesi su cosa farà heal().

Due validazioni distinte, entrambe utili:

    validate_document(doc) — INPUT, prima di heal(): i fatti sul Document
                           (vuoto, tratti di lunghezza nulla) e quello che
                           l'adapter ha detto del file.
    validate_result(res) — OUTPUT, dopo heal(). Controlla che i cluster prodotti
                           siano sani (poligono valido, fori contenuti, area).
                           Chiamata da faces() e outlines().
"""


import math

from ..model import Result
from ..model.document import Document
from ..model.diagnostic import Diagnostic, plural
from ..core.primitives.segments import BSplineSeg, CircleSeg, EllipseSeg
from ..core.primitives.polygon_builder import curve_polygon
from ..core.geometry.measure import FLOAT_NOISE
from ..core.geometry.rings import ring_jumps


# ---------------------------------------------------------------------------
# INPUT — prima di heal()
# ---------------------------------------------------------------------------

def validate_document(doc: Document) -> Result:
    """
    Check a `Document` before `heal()`, without changing it.

    Returns a `Result` with only `warnings` / `notes` / `errors` / `is_valid`
    (no clusters), all `topo.Diagnostic` (D233): what the adapter said about
    the source, plus

    - error `empty`: no edges (only texts, or nothing), or every edge has zero length;
    - warning `zero-length`: edges whose two ends are one point.

    It reports facts about the input, never a guess about what `heal()` will do.
    """
    if not isinstance(doc, Document):
        raise TypeError(f"topo.validate_document() takes a Document, got {type(doc).__name__}")

    result = Result(source_file=doc.source_path, source_format=doc.source_format)
    edges = doc.edges
    # quello che l'adapter ha detto sul file grezzo: validate_document() è
    # l'unico punto da guardare prima di heal()
    result.warnings.extend(doc.warnings)
    result.notes.extend(getattr(doc, "notes", []))

    if not edges:
        result.errors.append(Diagnostic(
            "empty", "the document has only texts, no edges" if doc.texts else "the document has no edges",
            level="error"))
        result.is_valid = False
        return result

    zero_len = [e for e in edges
                if e.start == e.end and not isinstance(e.segment, (CircleSeg, BSplineSeg, EllipseSeg))]
    if zero_len and len(zero_len) == len(edges):
        result.errors.append(Diagnostic(
            "empty", "every edge has zero length", points=[e.start for e in zero_len], level="error"))
        result.is_valid = False
        return result
    if zero_len:
        result.warnings.append(Diagnostic(
            "zero-length", f"{plural(len(zero_len), 'edge', 'edges')} of zero length, dropped by heal()",
            points=[e.start for e in zero_len],
            help="remove them from the drawing, or leave them: they change nothing"))
    return result


# ---------------------------------------------------------------------------
# OUTPUT — dopo heal()
# ---------------------------------------------------------------------------

def validate_result(result: Result) -> None:
    """
    Check the clusters of a `Result` a reading produced. **Mutates** `result`:
    adds `topo.Diagnostic` warnings and errors and lowers `is_valid`; returns
    `None` (D176). Called by `Network.faces()` and `Network.outlines()`.

    - error `open-contour`: an outer or inner that does not close head to tail
      beyond float noise (D206);
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
                    points=[p for p, _ in jumps], notes=[f"widest {max(d for _, d in jumps):.6g}"],
                    level="error"))
                result.is_valid = False

        poly = curve_polygon(cluster.outer)
        if poly is None or poly.is_empty or poly.area <= 0:
            result.errors.append(Diagnostic(
                "no-area", f"{label}: the outer encloses no area",
                points=[cluster.outer.segments[0].start] if cluster.outer.segments else [], level="error"))
            result.is_valid = False
            continue

        if not poly.is_valid:
            result.warnings.append(Diagnostic(
                "self-intersecting", f"{label}: the outer polygon crosses itself",
                points=[cluster.outer.segments[0].start],
                help="in the drawing, remove the crossing of the outer contour"))

        outside = [inner for inner in cluster.inners if not poly.contains(curve_polygon(inner))]
        if outside:
            result.warnings.append(Diagnostic(
                "inner-outside", f"{label}: {plural(len(outside), 'inner is', 'inners are')} not wholly "
                                 f"inside the outer",
                points=[inner.segments[0].start for inner in outside]))
