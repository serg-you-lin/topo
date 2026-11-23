"""
tests/engine/io/test_to_shapely.py

`topo.to_shapely`: the explicit conversion. A contour is the reading's polygon
(or rebuilt at a tolerance), an open curve a LineString, a cluster its material
by even-odd like `area`.
"""

import math

import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon

import topo

g = topo.geometry


def _nested():
    # 100×60 plate, Ø40 hole with a Ø20 island inside it holed Ø8, and a separate Ø6 hole
    doc = topo.load_segments(g.rectangle(100, 60) + g.circle(20) + g.circle(10) + g.circle(4)
                             + g.circle(3, center=(40, 0)))
    return topo.heal(doc).faces().clusters[0]


def test_contour_is_the_polygon_of_the_reading():
    cluster = _nested()
    assert topo.to_shapely(cluster.outer).equals(Polygon([(-50, -30), (50, -30), (50, 30), (-50, 30)]))
    hole = next(i for i in cluster.inners if i.depth == 1 and i.area > 1000)
    coarse, fine = topo.to_shapely(hole, tolerance=0.1), topo.to_shapely(hole, tolerance=0.001)
    exact = math.pi * 20 ** 2
    assert exact - coarse.area > exact - fine.area > 0
    assert len(fine.exterior.coords) > len(coarse.exterior.coords)


def test_cluster_even_odd_like_the_area():
    cluster = _nested()
    material = topo.to_shapely(cluster, tolerance=0.001)
    assert isinstance(material, MultiPolygon) and len(material.geoms) == 2
    assert material.is_valid
    # the polygon is within tol × perimeter of the exact area
    perimeter = sum(topo.to_shapely(c).exterior.length for c in [cluster.outer, *cluster.inners])
    assert material.area == pytest.approx(cluster.area, abs=0.001 * perimeter)
    assert material.contains(Polygon([(5, -1), (7, -1), (7, 1), (5, 1)]))       # the island is material
    assert not material.intersects(Polygon([(12, -1), (18, -1), (18, 1), (12, 1)]))  # the hole around it is not


def test_without_islands_a_single_polygon():
    doc = topo.load_segments(g.rectangle(100, 60) + g.circle(5))
    material = topo.to_shapely(topo.heal(doc).faces().clusters[0])
    assert isinstance(material, Polygon) and len(material.interiors) == 1


def test_open_curve_is_a_linestring():
    doc = topo.load_geometry([{"type": "line", "start": (0, 0), "end": (10, 0)}])
    curve = topo.heal(doc).faces().loose[0]
    line = topo.to_shapely(curve)
    assert isinstance(line, LineString) and line.length == pytest.approx(10.0)


def test_without_geometry_type_error():
    with pytest.raises(TypeError):
        topo.to_shapely(object())


def test_the_model_carries_no_polygon():
    contour = topo.Contour(segments=topo.geometry.rectangle(10, 5), role="outer")
    assert not hasattr(contour, "polygon")
    assert not hasattr(topo.Cluster(outer=contour), "polygon_with_holes")
    with pytest.raises(TypeError):
        topo.Contour(segments=topo.geometry.rectangle(10, 5), role="outer", polygon=None)
    assert topo.to_shapely(contour).area == pytest.approx(50.0)


class _Item:
    def __init__(self, segments, is_void=False):
        self.segments, self.is_void = segments, is_void


def test_drawn_closed_an_ambit_a_void_or_a_closed_curve():
    from topo.model import feature_closed
    ring = topo.geometry.rectangle(10, 5)
    open_run = ring[:3]
    assert feature_closed(_Item(ring), _Item(ring))
    assert not feature_closed(_Item(open_run), _Item(open_run))
    assert feature_closed(_Item(open_run), _Item(open_run, is_void=True))
    closed = topo.Contour(segments=open_run, role="outer")
    assert feature_closed(closed, None)
