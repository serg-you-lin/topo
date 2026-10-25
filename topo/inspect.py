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

from topo.core.geometry.measure import track_points, track_shape_type
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

def inspect_document(doc, graph: bool = True, limit: Optional[int] = 60) -> None:
    """
    Stampa un Document prodotto da un adapter (`topo_dxf.load_dxf`, …) o da
    `topo.load_geometry`: cosa ha estratto e tradotto. Per partire da un
    file: `topo_dxf.inspect_file`.
    """

    _h("LIVELLO 2 — Document (adapter → dominio)")

    print(f"\nsource_path : {doc.source_path}")
    print(f"source_meta : {doc.source_meta}")
    if getattr(doc, "warnings", None):
        print(f"\nwarnings del loader ({len(doc.warnings)}):")
        for w in doc.warnings:
            print(f"  - {w}")

    edges = doc.edges
    by_role = Counter(_role(e.role) for e in edges)
    by_seg = Counter(type(e.segment).__name__ for e in edges)
    print(f"\nedge: {len(edges)} totali")
    print(f"  per ruolo    : {dict(by_role)}")
    print(f"  per primitiva: {dict(by_seg)}")

    print(f"\ndettaglio edge{' (primi %d)' % limit if limit else ''}:")
    for i, e in enumerate(edges):
        if limit is not None and i >= limit:
            print(f"  ... e altri {len(edges) - limit}")
            break
        print(f"  [{i}] role={_role(e.role):<13} {_p(e.start)} -> {_p(e.end)}  "
              f"{_describe_segment(e.segment)}")

    anns = doc.texts or []
    if anns:
        print(f"\ntesti: {len(anns)}")
        kinds = Counter(a.source_kind for a in anns)
        print(f"  per tipo: {dict(kinds)}")
        for a in anns[:20]:
            content = (a.text or "")[:40]
            print(f"  - {a.source_kind:<10} @ {_p(a.position)}  {content!r}")

    if not graph:
        return

    from .core.topology.graph import build_node_graph
    g = build_node_graph(edges)
    branching = g.branching_nodes()
    open_nodes = g.open_nodes()
    print(f"\ngrafo nodi:")
    print(f"  nodi              : {len(g.nodes)}")
    print(f"  loop degeneri     : {len(g.degenerate_loops)}  (CIRCLE / SPLINE chiusa)")
    print(f"  nodi di branching : {len(branching)} (grado > 2)  {[_p(n) for n in branching[:8]]}")
    print(f"  estremi liberi    : {len(open_nodes)} (grado 1)   {[_p(n) for n in open_nodes[:8]]}")
    if not branching and not open_nodes and g.nodes:
        print("  → grafo pulito: ogni nodo ha grado 2, contorni chiusi")


def _describe_segment(seg) -> str:
    from .core.primitives.segments import LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg

    if seg is None:
        return "<nessun segmento>"
    if isinstance(seg, LineSeg):
        d = math.hypot(seg.end[0] - seg.start[0], seg.end[1] - seg.start[1])
        return f"LINE  len={d:.2f}"
    if isinstance(seg, ArcSeg):
        sweep = math.degrees(seg._sweep())
        return (f"ARC   c={_p(seg.center)} r={seg.radius:.2f} sweep={sweep:.1f}° "
                f"{'ccw' if seg.ccw else 'cw'}")
    if isinstance(seg, CircleSeg):
        return f"CIRCLE c={_p(seg.center)} r={seg.radius:.2f}"
    if isinstance(seg, EllipseSeg):
        sweep = math.degrees(seg._sweep())
        semi_major = math.hypot(*seg.major_axis)
        return (f"ELLIPSE c={_p(seg.center)} a={semi_major:.2f} ratio={seg.ratio:.3f} "
                f"sweep={sweep:.1f}° {'ccw' if seg.ccw else 'cw'}")
    if isinstance(seg, BSplineSeg):
        return (f"SPLINE deg={seg.degree} cp={len(seg.control_points)} "
                f"closed={seg.closed} periodic={seg.periodic}")
    return type(seg).__name__


# ===========================================================================
# LIVELLO 3 — Result: il modello
# ===========================================================================

def inspect_result(result, coords: bool = False) -> None:
    """
    Stampa un Result dopo heal(): il prodotto vero di topo.

    coords : se True stampa anche le coordinate dei contorni
    """
    _h("LIVELLO 3 — Result (il modello)")

    print(f"\nsource_file : {result.source_file}")
    print(f"is_valid    : {result.is_valid}")
    print(f"cluster_count  : {result.cluster_count}")

    if result.errors:
        print(f"\nerrori ({len(result.errors)}):")
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
        print(f"\n{_SUB}\nloose: {len(loose)}  (curve che non sono contorno di nessun cluster)")
        kinds = Counter(
            "closed" if curve_polygon(t) is not None
            else track_shape_type(track_points(getattr(t, "segments", []) or []))
            for t in loose
        )
        roles = Counter(_role(getattr(t, "role", "?")) for t in loose)
        print(f"  per tipo : {dict(kinds)}")
        print(f"  per ruolo: {dict(roles)}")

    anns = result.texts or []
    if anns:
        print(f"\ntesti nel modello: {len(anns)}  ({dict(Counter(a.source_kind for a in anns))})")


def _sub_part(i: int, cluster, coords: bool) -> None:
    print(f"\n{_SUB}\nPARTE {i}  label={cluster.label!r}")
    o = cluster.outer
    print(f"  outer  : role={_role(o.role):<10} area={o.area:.1f}  "
          f"bbox={tuple(round(v, 1) for v in o.bbox)}  segmenti={len(o.segments)}")
    print(f"  area netta (outer - vuoti - inner): {cluster.area:.1f}")

    if cluster.inners:
        print(f"  inners : {len(cluster.inners)}")
        for inn in cluster.inners:
            print(f"    - role={_role(inn.role):<10} area={inn.area:.1f} segmenti={len(inn.segments)}")

    if cluster.detected is not None:
        for name, items in cluster.detected.items():
            print(f"  {name}: {len(items)}")
            for item in items:
                fields = item.to_dict() if callable(getattr(item, "to_dict", None)) else {}
                print(f"    - role={_role(getattr(item, 'role', '?'))} {fields}")

    if cluster.custom:
        print(f"  custom : {cluster.custom}")

    if coords:
        print(f"  outer coords: {[tuple(round(c, 1) for c in pt) for pt in o.points()]}")
