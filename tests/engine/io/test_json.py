"""
tests/engine/io/test_json.py

`topo.to_json` / `save_json` (D230, D231): solo geometria, la sorgente e la
lettura dichiarate, i campi del consumatore aggiunti senza mai sostituire
quelli di topo.
"""

import json
import math

import pytest

import topo

g = topo.geometry


def _result(reading="faces"):
    # piastra 100×60 con un foro Ø20
    net = topo.heal(topo.load_segments(g.rectangle(100, 60) + g.circle(10)), label="piastra")
    return net.faces() if reading == "faces" else net.outlines()


def test_dice_da_dove_arriva_e_come_e_letto():
    data = json.loads(topo.to_json(_result()))
    assert data["source_format"] == "geometry"
    assert data["reading"] == "faces"
    assert data["tolerance"] == data["max_gap"] == 0.05
    assert json.loads(topo.to_json(_result("outlines")))["reading"] == "outlines"


def test_fatti_esatti_senza_coordinate_ne_processo():
    cluster = json.loads(topo.to_json(_result()))["clusters"][0]
    assert set(cluster) == {"label", "area", "outer_perimeter", "inner_perimeter",
                            "inner_count", "bbox", "detected"}
    assert cluster["area"] == pytest.approx(100 * 60 - math.pi * 10 ** 2, abs=1e-9)
    assert cluster["outer_perimeter"] == pytest.approx(320, abs=1e-9)
    assert cluster["inner_perimeter"] == pytest.approx(2 * math.pi * 10, abs=1e-9)
    assert cluster["inner_count"] == 1
    assert cluster["bbox"] == {"minx": -50, "miny": -30, "maxx": 50, "maxy": 30}


def test_extra_aggiunge_i_campi_del_consumatore():
    data = json.loads(topo.to_json(_result(), extra=lambda c: {"material": "x", "code": c.label}))
    assert data["clusters"][0]["material"] == "x"
    assert data["clusters"][0]["code"] == "piastra"


def test_extra_non_sostituisce_un_campo_di_topo():
    with pytest.raises(ValueError, match="area"):
        topo.to_json(_result(), extra=lambda c: {"area": 0})


def test_save_json_scrive_lo_stesso_testo(tmp_path):
    result = _result()
    path = tmp_path / "out.json"
    topo.save_json(result, str(path))
    assert path.read_text(encoding="utf-8") == topo.to_json(result)
