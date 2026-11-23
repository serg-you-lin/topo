"""
tests/engine/tools/test_split_readings.py

`topo.split`: by default it discards nothing, and works the same on the two
readings — `faces()` and `outlines()` give a `Result`, split does not know which.
"""

import pytest

import topo

g = topo.geometry


def _network():
    # a 100×60 plate with a Ø20 hole, and separately a small 2×2 square (area 4)
    return topo.heal(topo.load_segments(
        g.rectangle(100, 60) + g.circle(10) + g.rectangle(2, 2, center=(200, 0))))


@pytest.mark.parametrize("reading", ["faces", "outlines"])
def test_one_part_per_cluster_nothing_discarded(reading):
    result = getattr(_network(), reading)()
    parts = topo.split(result)
    assert [len(p.clusters) for p in parts] == [1, 1]
    assert sorted(round(p.clusters[0].outer.area) for p in parts) == [4, 6000]
    assert not any("dropped" in w for w in result.warnings)


def test_outlines_the_hole_goes_to_its_part():
    # outlines() puts the hole in loose: split gives it to the plate
    #
    plate, small = topo.split(_network().outlines())
    assert [c.cluster_ref for c in plate.loose] == [0]
    assert small.loose == []


def test_given_min_area_discards_with_a_warning():
    result = _network().faces()
    parts = topo.split(result, min_area=10)
    assert len(parts) == 1
    assert any("dropped" in w for w in result.warnings)
