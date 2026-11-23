"""
tests/engine/readings/test_cluster_order.py

Order of the clusters: from the largest by exact area, and among congruent
copies by position (xmin, ymin) — never the rounding noise, never the order in
which the drawing lists them.
"""

import pytest

import topo

g = topo.geometry


def _drawing(order):
    # three copies of the same stadium in three positions, and a larger rectangle
    copies = {"a": (300.0, 0.0), "b": (0.0, 50.0), "c": (0.0, 0.0)}
    segments = g.rectangle(80, 40, center=(150.0, 200.0))
    for key in order:
        segments += g.stadium(40, 20, center=copies[key], angle=30)
    return topo.load_segments(segments)


@pytest.mark.parametrize("order", ["abc", "cab", "bca"])
@pytest.mark.parametrize("read", ["faces", "outlines"])
def test_congruent_copies_in_order_of_position(order, read):
    doc = _drawing(order)
    result = topo.heal(doc).faces() if read == "faces" else topo.heal(doc, max_gap=0.1).outlines()
    corners = [(round(c.bbox[0], 6), round(c.bbox[1], 6)) for c in result.clusters]
    assert result.clusters[0].outer.area == pytest.approx(3200.0)
    assert corners[1:] == sorted(corners[1:])
    assert len({round(c.outer.area, 6) for c in result.clusters[1:]}) == 1
