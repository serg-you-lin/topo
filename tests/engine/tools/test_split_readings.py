"""
tests/engine/tools/test_split_readings.py

`topo.split`: it discards nothing and decides nothing, and works the same on the two
readings — `faces()` and `outlines()` give a `Result`, split does not know which.
What no part contains comes back in `Split.loose` / `Split.texts`.
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
    parts = topo.split(result).parts
    assert [len(p.clusters) for p in parts] == [1, 1]
    assert sorted(round(p.clusters[0].outer.area) for p in parts) == [4, 6000]
    assert result.warnings == []


def test_outlines_the_hole_goes_to_its_part():
    # outlines() puts the hole in loose: split gives it to the plate
    #
    plate, small = topo.split(_network().outlines()).parts
    assert [c.cluster_ref for c in plate.loose] == [0]
    assert small.loose == []


def _with_strays():
    # two 100×100 squares, a text in each, one text between them and one far away,
    # a segment on the second square (a loose curve with a cluster) and one far from both
    result = topo.heal(topo.load_segments(
        g.rectangle(100, 100, center=(50, 50)) + g.rectangle(100, 100, center=(350, 50))
        + [topo.primitives.LineSeg((350, 0), (350, 30)),
           topo.primitives.LineSeg((900, 0), (900, 30))])).faces()
    for text, at in (("A", (50, 50)), ("B", (350, 50)), ("between", (200, 50)), ("far", (900, 900))):
        result.texts.append(topo.Text(text=text, position=at))
    return result


def test_what_no_part_contains_comes_back_apart():
    result = _with_strays()
    outcome = topo.split(result)
    assert [[t.text for t in p.texts] for p in outcome.parts] == [["A"], ["B"]]
    assert sorted(t.text for t in outcome.texts) == ["between", "far"]
    assert len(outcome.loose) == len(result.loose) - sum(len(p.loose) for p in outcome.parts)
    assert [c.cluster_ref for c in outcome.loose] == [None] * len(outcome.loose)
    assert len(outcome.loose) >= 1


def test_nothing_is_lost_or_duplicated():
    result = _with_strays()
    outcome = topo.split(result)
    texts = [t.text for p in outcome.parts for t in p.texts] + [t.text for t in outcome.texts]
    assert sorted(texts) == sorted(t.text for t in result.texts)
    n_loose = sum(len(p.loose) for p in outcome.parts) + len(outcome.loose)
    assert n_loose == len(result.loose)


def test_a_text_follows_the_cluster_ref_anchor_texts_gave_it():
    result = _with_strays()
    topo.anchor_texts(result, snap_distance=120)
    outcome = topo.split(result)
    assert sorted(t.text for t in outcome.texts) == ["far"]
    assert [t.text for t in outcome.parts[0].texts] == ["A", "between"]


def test_split_does_not_change_the_result():
    result = _with_strays()
    before = [c.label for c in result.clusters]
    topo.split(result)
    assert [c.label for c in result.clusters] == before
    assert result.warnings == []
