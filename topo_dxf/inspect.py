"""
topo_dxf/inspect.py
-------------------
Il primo livello dell'ispezione, quello del file: cosa contiene un DXF prima
che topo lo tocchi. `inspect_file` stampa i tre livelli in fila — DXF
grezzo, poi `topo.inspect_document` e `topo.inspect_result` (D129):

    topo_dxf.inspect_file("pezzo.dxf", role_rules=topo.name_rules({"Piega": "bending"}))

Tutto stampa su stdout con `print`. Nessun logger da configurare.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence

import ezdxf

import topo
from topo.model import DEFAULT_NODE_TOLERANCE, RoleRule

from .loader import load_dxf

_RULE = "=" * 72


def _header(title: str) -> None:
    print(f"\n{_RULE}\n{title}\n{_RULE}")


def _point(x, nd: int = 2) -> str:
    """Formatta un punto (x, y) con nd decimali."""
    return f"({x[0]:.{nd}f}, {x[1]:.{nd}f})"


def inspect_dxf(path: str, *, entities: bool = True, limit: Optional[int] = 40) -> None:
    """
    Opens a DXF/DWG with ezdxf and prints what it contains, without touching topo.

    entities : if True lists every entity with its key attributes
    limit    : maximum number of entities listed (None = all)
    """
    _header(f"LEVEL 1 — raw DXF\n{path}")

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ents = list(msp)

    print(f"\nDXF version  : {doc.dxfversion}")
    print(f"$INSUNITS    : {doc.header.get('$INSUNITS', 'n/a')}   "
          f"$MEASUREMENT : {doc.header.get('$MEASUREMENT', 'n/a')}")

    counts = Counter(e.dxftype() for e in ents)
    print(f"\nentities ({len(ents)} in all):")
    for t, n in sorted(counts.items()):
        print(f"  {t:<14} {n}")

    layers = Counter(
        (e.dxf.layer if e.dxf.hasattr("layer") else "?") for e in ents
    )
    print(f"\nlayer:")
    for name, n in sorted(layers.items()):
        print(f"  {name!r:<24} {n}")

    if not entities:
        return

    print(f"\nentity detail{' (first %d)' % limit if limit else ''}:")
    for i, e in enumerate(ents):
        if limit is not None and i >= limit:
            print(f"  ... and {len(ents) - limit} more")
            break
        print(f"  [{i}] {_describe_dxf_entity(e)}")


def _describe_dxf_entity(e) -> str:
    t = e.dxftype()
    layer = e.dxf.layer if e.dxf.hasattr("layer") else "?"
    tag = f"{t:<12} layer={layer!r}"
    try:
        if t == "LINE":
            return f"{tag}  {_point((e.dxf.start.x, e.dxf.start.y))} -> {_point((e.dxf.end.x, e.dxf.end.y))}"
        if t == "ARC":
            return (f"{tag}  c={_point((e.dxf.center.x, e.dxf.center.y))} r={e.dxf.radius:.2f} "
                    f"{e.dxf.start_angle:.1f}°->{e.dxf.end_angle:.1f}°")
        if t == "CIRCLE":
            return f"{tag}  c={_point((e.dxf.center.x, e.dxf.center.y))} r={e.dxf.radius:.2f}"
        if t in ("LWPOLYLINE", "POLYLINE"):
            try:
                n = len(list(e.get_points())) if t == "LWPOLYLINE" else len(list(e.vertices))
            except Exception:
                n = "?"
            closed = getattr(e, "is_closed", getattr(e, "closed", "?"))
            return f"{tag}  vertices={n} closed={closed}"
        if t == "SPLINE":
            return f"{tag}  cp={len(e.control_points)} closed={getattr(e, 'closed', '?')}"
        if t in ("TEXT", "MTEXT"):
            txt = (e.dxf.text if t == "TEXT" else e.text)[:40]
            return f"{tag}  {txt!r}"
        if t == "DIMENSION":
            return f"{tag}  text={getattr(e.dxf, 'text', '')!r}"
        if t == "INSERT":
            return f"{tag}  block={e.dxf.name!r}"
    except Exception as ex:
        return f"{tag}  <read error: {ex}>"
    return tag


# ===========================================================================
# ORCHESTRATORE — i tre livelli in fila su un file
# ===========================================================================

def inspect_file(
    path: str,
    *, tolerance: float = DEFAULT_NODE_TOLERANCE,
    role_rules: Sequence[RoleRule] = (),
    run_heal: bool = True,
    entities: bool = True,
    coords: bool = False,
) -> None:
    """
    Opens a file and prints the three levels in a row:
    raw DXF → Document → Result.

    run_heal              : turn it off to stop at the Document.
    role_rules            : as in load_dxf().
    """
    inspect_dxf(path, entities=entities)

    doc = load_dxf(
        path, tolerance=tolerance, role_rules=role_rules,
    )
    topo.inspect_document(doc)

    if not run_heal:
        return

    result = topo.heal(doc, tolerance=tolerance).faces()

    topo.inspect_result(result, coords=coords)
