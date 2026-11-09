"""
topo/inspect.py
----------------
Strumento di ispezione a tre livelli. Serve a *vedere* cosa succede a un file
reale senza leggere il codice — pensato per il debug quando si lavora su file
veri.

I due livelli di topo, in ordine di pipeline:

    inspect_document(doc)    → edge + primitive + grafo — "cosa ha capito l'adapter"
    inspect_result(result)   → il modello                 — "cosa ha prodotto topo"

Il livello del file (le entità grezze) è di un formato: `topo_dxf.inspect_dxf`,
e `topo_dxf.inspect_file` stampa i tre livelli in fila su un file (D129).

Tutto stampa su stdout con `print`. Nessun logger da configurare.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional, Sequence

from topo.core.geometry.measure import track_points
from topo.core.primitives.polygon_builder import curve_polygon

__all__ = [
    "inspect_document",
    "inspect_result",
]

_RULE = "=" * 72
_SUB = "-" * 72


def _h(title: str) -> None:
    print(f"\n{_RULE}\n{title}\n{_RULE}")


def _p(x, nd: int = 2) -> str:
    """Formatta un punto (x, y) con nd decimali."""
    if x is None:
        return "None"
    return f"({x[0]:.{nd}f}, {x[1]:.{nd}f})"


def _role(r) -> str:
    """Nome del ruolo come stringa piatta ('outer'), non 'ContourRole.OUTER'."""
    return getattr(r, "value", str(r))


# ===========================================================================
# LIVELLO 2 — Document: edge, primitive, grafo
# ===========================================================================

def inspect_document(doc, *, graph: bool = True, limit: Optional[int] = 60) -> None:
    """
    Prints a Document produced by an adapter (`topo_dxf.load_dxf`, …) or by
    `topo.load_geometry`: what it extracted and translated. To start from a
    file: `topo_dxf.inspect_file`.
    """

    _h("LEVEL 2 — Document (adapter → domain)")

    print(f"\nsource_path : {doc.source_path}")
    print(f"source_meta : {doc.source_meta}")
    if getattr(doc, "warnings", None):
        print(f"\nloader warnings ({len(doc.warnings)}):")
        for w in doc.warnings:
            print(f"  - {w}")

    edges = doc.edges
    by_role = Counter(_role(e.role) for e in edges)
    by_seg = Counter(type(e.segment).__name__ for e in edges)
    print(f"\nedge: {len(edges)} in all")
    print(f"  by role      : {dict(by_role)}")
    print(f"  by primitive : {dict(by_seg)}")

    print(f"\nedge detail{' (first %d)' % limit if limit else ''}:")
    for i, e in enumerate(edges):
        if limit is not None and i >= limit:
            print(f"  ... and {len(edges) - limit} more")
            break
        print(f"  [{i}] role={_role(e.role):<13} {_p(e.start)} -> {_p(e.end)}  "
              f"{_describe_segment(e.segment)}")

    anns = doc.texts or []
    if anns:
        print(f"\ntexts: {len(anns)}")
        kinds = Counter(a.source_kind for a in anns)
        print(f"  by kind: {dict(kinds)}")
        for a in anns[:20]:
            content = (a.text or "")[:40]
            print(f"  - {a.source_kind:<10} @ {_p(a.position)}  {content!r}")

    if not graph:
        return

    from .core.topology.graph import build_node_graph
    g = build_node_graph(edges)
    branching = g.branching_nodes()
    open_nodes = g.open_nodes()
    print(f"\nnode graph:")
    print(f"  nodes             : {len(g.nodes)}")
    print(f"  one-curve loops   : {len(g.degenerate_loops)}  (circle / closed spline)")
    print(f"  branching nodes   : {len(branching)} (degree > 2)  {[_p(n) for n in branching[:8]]}")
    print(f"  free ends         : {len(open_nodes)} (degree 1)   {[_p(n) for n in open_nodes[:8]]}")
    if not branching and not open_nodes and g.nodes:
        print("  → clean graph: every node has degree 2, contours closed")


def _describe_segment(seg) -> str:
    from .core.primitives.segments import LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg

    if seg is None:
        return "<no segment>"
    if isinstance(seg, LineSeg):
        d = math.hypot(seg.end[0] - seg.start[0], seg.end[1] - seg.start[1])
        return f"line    len={d:.2f}"
    if isinstance(seg, ArcSeg):
        sweep = math.degrees(seg._sweep())
        return (f"arc     c={_p(seg.center)} r={seg.radius:.2f} sweep={sweep:.1f}° "
                f"{'ccw' if seg.ccw else 'cw'}")
    if isinstance(seg, CircleSeg):
        return f"circle  c={_p(seg.center)} r={seg.radius:.2f}"
    if isinstance(seg, EllipseSeg):
        sweep = math.degrees(seg._sweep())
        semi_major = math.hypot(*seg.major_axis)
        return (f"ellipse c={_p(seg.center)} a={semi_major:.2f} ratio={seg.ratio:.3f} "
                f"sweep={sweep:.1f}° {'ccw' if seg.ccw else 'cw'}")
    if isinstance(seg, BSplineSeg):
        return (f"spline  deg={seg.degree} cp={len(seg.control_points)} "
                f"closed={seg.closed} periodic={seg.periodic}")
    return type(seg).__name__


# ===========================================================================
# LIVELLO 3 — Result: il modello
# ===========================================================================

def inspect_result(result, *, coords: bool = False) -> None:
    """
    Prints a Result after heal(): topo's real product.

    coords : if True also prints the contours' coordinates
    """
    _h("LEVEL 3 — Result (the model)")

    print(f"\nsource_file : {result.source_file}")
    print(f"is_valid    : {result.is_valid}")
    print(f"cluster_count  : {result.cluster_count}")

    if result.errors:
        print(f"\nerrors ({len(result.errors)}):")
        for e in result.errors:
            print(f"  ERROR: {e}")
    if result.warnings:
        print(f"\nwarnings ({len(result.warnings)}):")
        for w in result.warnings:
            print(f"  warn: {w}")

    for i, cluster in enumerate(result.clusters):
        _sub_part(i, cluster, coords)

    loose = result.loose or []
    if loose:
        print(f"\n{_SUB}\nloose: {len(loose)}  (curves that are no cluster's contour)")
        kinds = Counter(
            "closed" if curve_polygon(t) is not None
            else ("line" if len(track_points(getattr(t, "segments", []) or [])) == 2 else "curve")
            for t in loose
        )
        roles = Counter(_role(getattr(t, "role", "?")) for t in loose)
        print(f"  by kind : {dict(kinds)}")
        print(f"  by role : {dict(roles)}")

    anns = result.texts or []
    if anns:
        print(f"\ntexts in the model: {len(anns)}  ({dict(Counter(a.source_kind for a in anns))})")


def _sub_part(i: int, cluster, coords: bool) -> None:
    print(f"\n{_SUB}\nPART {i}  label={cluster.label!r}")
    o = cluster.outer
    print(f"  outer  : role={_role(o.role):<10} area={o.area:.1f}  "
          f"bbox={tuple(round(v, 1) for v in o.bbox)}  segments={len(o.segments)}")
    print(f"  net area (outer - voids - inners): {cluster.area:.1f}")

    if cluster.inners:
        print(f"  inners : {len(cluster.inners)}")
        for inn in cluster.inners:
            print(f"    - role={_role(inn.role):<10} area={inn.area:.1f} segments={len(inn.segments)}")

    if cluster.overlay is not None:
        for name, items in cluster.overlay.items():
            print(f"  {name}: {len(items)}")
            for item in items:
                fields = item.to_dict() if callable(getattr(item, "to_dict", None)) else {}
                print(f"    - role={_role(getattr(item, 'role', '?'))} {fields}")

    if coords:
        print(f"  outer coords: {[tuple(round(c, 1) for c in pt) for pt in o.points()]}")
