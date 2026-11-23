"""
tests/engine/io/test_json.py

`topo.to_json` / `save_json`: geometry only, the declared source and reading,
the consumer's fields added without ever replacing topo's.
"""

import json
import math

import pytest

import topo

g = topo.geometry


def _result(reading="faces"):
    # 100×60 plate with a Ø20 hole
    net = topo.heal(topo.load_segments(g.rectangle(100, 60) + g.circle(10)), label="piastra")
    return net.faces() if reading == "faces" else net.outlines()


def test_says_where_it_comes_from_and_how_it_is_read():
    data = json.loads(topo.to_json(_result()))
    assert data["source_format"] == "geometry"
    assert data["reading"] == "faces"
    assert (data["tolerance"], data["max_gap"]) == (topo.precision.SAME_POINT, 0.0)   # without max_gap no gap closes
    assert json.loads(topo.to_json(_result("outlines")))["reading"] == "outlines"


def test_exact_facts_without_coordinates_or_process():
    cluster = json.loads(topo.to_json(_result()))["clusters"][0]
    assert set(cluster) == {"label", "area", "outer_perimeter", "inner_perimeter",
                            "inner_count", "bbox", "overlay"}
    assert cluster["area"] == pytest.approx(100 * 60 - math.pi * 10 ** 2, abs=1e-9)
    assert cluster["outer_perimeter"] == pytest.approx(320, abs=1e-9)
    assert cluster["inner_perimeter"] == pytest.approx(2 * math.pi * 10, abs=1e-9)
    assert cluster["inner_count"] == 1
    assert cluster["bbox"] == {"minx": -50, "miny": -30, "maxx": 50, "maxy": 30}


def test_extra_adds_the_consumers_fields():
    data = json.loads(topo.to_json(_result(), extra=lambda c: {"material": "x", "code": c.label}))
    assert data["clusters"][0]["material"] == "x"
    assert data["clusters"][0]["code"] == "piastra"


def test_extra_does_not_replace_a_topo_field():
    with pytest.raises(ValueError, match="area"):
        topo.to_json(_result(), extra=lambda c: {"area": 0})


def test_save_json_writes_the_same_text(tmp_path):
    result = _result()
    path = tmp_path / "out.json"
    topo.save_json(result, str(path))
    assert path.read_text(encoding="utf-8") == topo.to_json(result)
