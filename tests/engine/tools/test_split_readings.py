"""
tests/engine/tools/test_split_readings.py

`topo.split` (D232): per default non scarta niente, e lavora uguale sulle due
letture — `faces()` e `outlines()` danno un `Result`, split non sa quale.
"""

import pytest

import topo

g = topo.geometry


def _network():
    # una piastra 100×60 con un foro Ø20, e a parte un quadratino 2×2 (area 4)
    return topo.heal(topo.load_segments(
        g.rectangle(100, 60) + g.circle(10) + g.rectangle(2, 2, center=(200, 0))))


@pytest.mark.parametrize("reading", ["faces", "outlines"])
def test_una_parte_per_cluster_niente_scartato(reading):
    result = getattr(_network(), reading)()
    parts = topo.split(result)
    assert [len(p.clusters) for p in parts] == [1, 1]
    assert sorted(round(p.clusters[0].outer.area) for p in parts) == [4, 6000]
    assert not any("dropped" in w for w in result.warnings)


def test_outlines_il_foro_va_alla_sua_parte():
    # outlines() mette il foro in loose (D161): split lo dà alla piastra
    plate, small = topo.split(_network().outlines())
    assert [c.cluster_ref for c in plate.loose] == [0]
    assert small.loose == []


def test_min_area_dato_scarta_con_un_avviso():
    result = _network().faces()
    parts = topo.split(result, min_area=10)
    assert len(parts) == 1
    assert any("dropped" in w for w in result.warnings)
