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


def inspect_dxf(path: str, entities: bool = True, limit: Optional[int] = 40) -> None:
    """
    Apre un DXF/DWG con ezdxf e stampa cosa contiene, senza toccare topo.

    entities : se True elenca ogni entità con i suoi attributi chiave
    limit    : numero massimo di entità elencate (None = tutte)
    """
    _header(f"LIVELLO 1 — DXF grezzo\n{path}")

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ents = list(msp)

    print(f"\nversione DXF : {doc.dxfversion}")
    print(f"$INSUNITS    : {doc.header.get('$INSUNITS', 'n/d')}   "
          f"$MEASUREMENT : {doc.header.get('$MEASUREMENT', 'n/d')}")

    counts = Counter(e.dxftype() for e in ents)
    print(f"\nentità ({len(ents)} totali):")
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

    print(f"\ndettaglio entità{' (primi %d)' % limit if limit else ''}:")
    for i, e in enumerate(ents):
        if limit is not None and i >= limit:
            print(f"  ... e altre {len(ents) - limit}")
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
            return f"{tag}  vertici={n} chiusa={closed}"
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
        return f"{tag}  <errore lettura: {ex}>"
    return tag


# ===========================================================================
# ORCHESTRATORE — i tre livelli in fila su un file
# ===========================================================================

def inspect_file(
    path: str,
    tolerance: float = DEFAULT_NODE_TOLERANCE,
    role_rules: Sequence[RoleRule] = (),
    run_heal: bool = True,
    entities: bool = True,
    coords: bool = False,
) -> None:
    """
    Apre un file e stampa i tre livelli in fila:
    DXF grezzo → Document → Result.

    run_heal              : disattivalo per fermarti al Document.
    role_rules            : come in load_dxf().
    """
    inspect_dxf(path, entities=entities)

    doc = load_dxf(
        path, tolerance=tolerance, role_rules=role_rules,
    )
    topo.inspect_document(doc)

    if not run_heal:
        return

    result = topo.heal(doc, tolerance=tolerance)

    topo.inspect_result(result, coords=coords)
