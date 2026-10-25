"""
tests/unit/test_no_shapely_surface.py

Guardiano di D166 e D169: nessun tipo shapely o numpy nella superficie
pubblica di topo.
Due controlli: le firme e i campi dichiarati di ogni nome pubblico, e gli
oggetti veri che escono da `heal`, `island`, `topo.steps` e `topo.geometry`,
percorsi campo per campo e proprietà per proprietà. Solo `to_shapely` lo
restituisce: è la conversione esplicita.
"""

import dataclasses
import inspect
import re
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry.base import BaseGeometry

import topo
import topo_dxf
from topo.primitives import LineSeg

DATA = Path(__file__).resolve().parents[1] / "data"
SHAPELY_WORDS = re.compile(r"\b(shapely|Polygon|MultiPolygon|LineString|LinearRing|BaseGeometry|STRtree)\b")
ALLOWED = {"to_shapely"}

MODULES = {
    "topo": topo,
    "topo.geometry": topo.geometry,
    "topo.steps": topo.steps,
    "topo.model": topo.model,
    "topo_dxf": topo_dxf,
}


def _public_names():
    for module_name, module in MODULES.items():
        for name in module.__all__:
            if name not in ALLOWED:
                yield f"{module_name}.{name}", getattr(module, name)


def _annotations(obj) -> list:
    """Le annotazioni scritte di una funzione, dei metodi e dei campi di una classe."""
    out = []
    if inspect.isclass(obj):
        for klass in obj.__mro__:
            if klass.__module__.startswith(("topo", "topo_dxf")):
                out += [str(v) for k, v in vars(klass).get("__annotations__", {}).items()
                        if not k.startswith("_")]
                for k, member in vars(klass).items():
                    if k.startswith("_"):
                        continue
                    fn = member.fget if isinstance(member, property) else member
                    if callable(fn):
                        out += _annotations(fn)
    elif callable(obj):
        try:
            sig = inspect.signature(obj)
        except (TypeError, ValueError):
            return out
        out += [str(p.annotation) for p in sig.parameters.values()]
        out.append(str(sig.return_annotation))
    return out


@pytest.mark.parametrize("qualname,obj", list(_public_names()), ids=lambda v: v if isinstance(v, str) else "")
def test_nessuna_firma_pubblica_nomina_shapely(qualname, obj):
    found = [a for a in _annotations(obj) if SHAPELY_WORDS.search(a)]
    assert not found, f"{qualname}: {found}"


def _walk(obj, path, seen, found, depth=0):
    """Ogni valore raggiungibile da `obj` per campi pubblici e proprietà."""
    if id(obj) in seen or depth > 8:
        return
    seen.add(id(obj))
    if isinstance(obj, (BaseGeometry, np.ndarray, np.generic)):
        found.append(path)
        return
    if isinstance(obj, (str, bytes, int, float, bool, type(None))):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk(v, f"{path}[{k!r}]", seen, found, depth + 1)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for i, v in enumerate(obj):
            _walk(v, f"{path}[{i}]", seen, found, depth + 1)
        return
    if not type(obj).__module__.startswith(("topo", "topo_dxf")):
        return
    names = [f.name for f in dataclasses.fields(obj)] if dataclasses.is_dataclass(obj) else list(vars(obj))
    names += [k for klass in type(obj).__mro__ for k, v in vars(klass).items() if isinstance(v, property)]
    for name in names:
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:      # una proprietà che non ha senso su questo oggetto (centroid senza area)
            continue
        _walk(value, f"{path}.{name}", seen, found, depth + 1)


def _shapely_in(obj, path) -> list:
    found = []
    _walk(obj, path, set(), found)
    return found


def _plate():
    # piastra con raccordo, foro, isola dentro un buco, e un tratto sciolto
    ring = [LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, 60)),
            LineSeg((100, 60), (0, 60)), LineSeg((0, 60), (0, 0))]
    segments = (ring + topo.geometry.circle(20, (40, 30)) + topo.geometry.circle(8, (40, 30))
                + topo.geometry.stadium(20, 8, (80, 15)) + [LineSeg((120, 0), (130, 0))])
    return topo.load_segments(segments)


def test_heal_e_island_non_portano_shapely():
    doc = _plate()
    for name, result in (("heal", topo.heal(doc)), ("island", topo.island(doc, max_gap=0.5))):
        assert result.clusters
        assert _shapely_in(result, name) == []


def test_un_disegno_vero_non_porta_shapely():
    doc = topo_dxf.load_dxf(str(DATA / "golden" / "example_4_polylines.dxf"))
    result = topo.heal(doc)
    assert result.clusters
    assert _shapely_in(result, "heal") == []
    assert _shapely_in(topo.split(result), "split") == []


def test_passi_e_fatti_non_portano_shapely():
    doc = _plate()
    edges = topo.steps.split_at_crossings(doc.edges, 0.01).pieces
    assert _shapely_in(topo.steps.outer_face(edges), "outer_face") == []
    assert _shapely_in(topo.steps.polygonize_to_curves(doc.edges, 0.1), "polygonize_to_curves") == []
    frame = [LineSeg(a, b) for a, b in (((0, 0), (200, 0)), ((200, 0), (200, 100)),
                                         ((200, 100), (0, 100)), ((0, 100), (0, 0)))]
    rects = topo.geometry.covered_rectangles(frame, min_side=50)
    assert rects and _shapely_in(rects, "covered_rectangles") == []
    cluster = topo.heal(doc).clusters[0]
    assert _shapely_in(topo.geometry.contour_shape(cluster.outer), "contour_shape") == []
