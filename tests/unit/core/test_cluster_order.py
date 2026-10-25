"""
tests/unit/core/test_cluster_order.py

Ordine dei cluster (D166, G13 passo 2): dal più grande per area esatta, e
fra copie congruenti per posizione (xmin, ymin) — mai il rumore
dell'arrotondamento, mai l'ordine in cui il disegno le elenca.
"""

import pytest

import topo

g = topo.geometry


def _drawing(order):
    # tre copie dello stesso stadio in tre posizioni, e un rettangolo più grande
    copies = {"a": (300.0, 0.0), "b": (0.0, 50.0), "c": (0.0, 0.0)}
    segments = g.rectangle(80, 40, center=(150.0, 200.0))
    for key in order:
        segments += g.stadium(40, 20, center=copies[key], angle=30)
    return topo.load_segments(segments)


@pytest.mark.parametrize("order", ["abc", "cab", "bca"])
@pytest.mark.parametrize("read", ["heal", "island"])
def test_copie_congruenti_in_ordine_di_posizione(order, read):
    doc = _drawing(order)
    result = topo.heal(doc) if read == "heal" else topo.island(doc, max_gap=0.1)
    corners = [(round(c.bbox[0], 6), round(c.bbox[1], 6)) for c in result.clusters]
    assert result.clusters[0].outer.area == pytest.approx(3200.0)
    assert corners[1:] == sorted(corners[1:])
    assert len({round(c.outer.area, 6) for c in result.clusters[1:]}) == 1
