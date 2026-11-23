"""
tests/package/test_no_shapely_surface.py

Guardian: no shapely or numpy type in the public surface of topo.
Two checks: the signatures and declared fields of every public name, and the
real objects that come out of `faces()`, `outlines()`, `topo.experimental` and
`topo.geometry`, walked field by field and property by property. Only
`to_shapely` returns one: it is the explicit conversion.
"""

import dataclasses
import inspect
import re

import numpy as np
import pytest
from shapely.geometry.base import BaseGeometry

import topo
import topo_dxf
from topo.primitives import LineSeg
from tests.paths import DATA

SHAPELY_WORDS = re.compile(r"\b(shapely|Polygon|MultiPolygon|LineString|LinearRing|BaseGeometry|STRtree)\b")
ALLOWED = {"to_shapely"}

MODULES = {
    "topo": topo,
    "topo.geometry": topo.geometry,
    "topo.experimental": topo.experimental,
    "topo.model": topo.model,
    "topo_dxf": topo_dxf,
}


def _public_names():
    for module_name, module in MODULES.items():
        for name in module.__all__:
            if name not in ALLOWED:
                yield f"{module_name}.{name}", getattr(module, name)


def _annotations(obj) -> list:
    """The written annotations of a function, the methods and the fields of a class."""
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
def test_no_public_signature_names_shapely(qualname, obj):
    found = [a for a in _annotations(obj) if SHAPELY_WORDS.search(a)]
    assert not found, f"{qualname}: {found}"


def _walk(obj, path, seen, found, depth=0):
    """Every value reachable from `obj` by public fields and properties."""
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
        except Exception:      # a property that makes no sense on this object (centroid without area)
            continue
        _walk(value, f"{path}.{name}", seen, found, depth + 1)


def _shapely_in(obj, path) -> list:
    found = []
    _walk(obj, path, set(), found)
    return found


def _plate():
    # plate with a fillet, a hole, an island inside a hole, and a loose stretch
    ring = [LineSeg((0, 0), (100, 0)), LineSeg((100, 0), (100, 60)),
            LineSeg((100, 60), (0, 60)), LineSeg((0, 60), (0, 0))]
    segments = (ring + topo.geometry.circle(20, center=(40, 30)) + topo.geometry.circle(8, center=(40, 30))
                + topo.geometry.stadium(20, 8, center=(80, 15)) + [LineSeg((120, 0), (130, 0))])
    return topo.load_segments(segments)


def test_faces_and_outlines_carry_no_shapely():
    doc = _plate()
    for name, result in (("faces", topo.heal(doc).faces()), ("outlines", topo.heal(doc, max_gap=0.5).outlines())):
        assert result.clusters
        assert _shapely_in(result, name) == []


def test_a_real_drawing_carries_no_shapely():
    doc = topo_dxf.load_dxf(str(DATA / "golden_faces" / "example_4_polylines.dxf"))
    result = topo.heal(doc).faces()
    assert result.clusters
    assert _shapely_in(result, "faces") == []
    assert _shapely_in(topo.split(result), "split") == []


def test_steps_and_facts_carry_no_shapely():
    doc = _plate()
    edges = topo.experimental.split_at_crossings(doc.edges, 0.01).pieces
    assert _shapely_in(topo.experimental.outer_face(edges), "outer_face") == []
    frame = [LineSeg(a, b) for a, b in (((0, 0), (200, 0)), ((200, 0), (200, 100)),
                                         ((200, 100), (0, 100)), ((0, 100), (0, 0)))]
    rects = topo.geometry.covered_rectangles(frame, min_side=50, eps=0.5, cluster_tolerance=1.5, coverage=0.85)
    assert rects and _shapely_in(rects, "covered_rectangles") == []
    cluster = topo.heal(doc).faces().clusters[0]
    assert _shapely_in(topo.geometry.contour_shape(cluster.outer), "contour_shape") == []
