"""
tests/tools/generate_hatch_small.py
-----------------------------
Genera `tests/data/tratteggio_stretto_piccolo.dxf`: il disegno del tratteggio
stretto (G16) in piccolo, perché le invarianti ci girino in un secondo e non
in sette minuti. Il contorno di `test_non_structural_role.py` scalato di 1/8,
con il restringimento di 0,3 mm e il lato appena storto (0,049) tenuti alla
misura vera; righe a 45° ogni 0,125 mm, tagliate sul bordo come un tratteggio
esploso. Si legge come l'originale: `faces()` con il contorno a pezzi,
`outlines()` a 15 segmenti, le righe in `loose`.

Uso: python tests/tools/generate_hatch_small.py
"""

import math
from pathlib import Path

import ezdxf

import topo
from topo.primitives import LineSeg
from topo_dxf.exporter import write_native_segments

SCALE = 1 / 8
SPACING = 0.125
BIG = [(40, 20), (90, 20), (140, 60), (250, 60), (250, 100), (170, 100),
       (170, 140), (210, 140), (210, 100), (264, 100), (264, 180), (40, 180)]


def _small_contour() -> list:
    pts = [(40 + (x - 40) * SCALE, 20 + (y - 20) * SCALE) for x, y in BIG]
    pts[8] = (pts[8][0], pts[4][1] + 0.3)
    pts[9] = (pts[9][0] - 0.049, pts[4][1] + 0.3)
    return [LineSeg(start=pts[i], end=pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def _hatch_rows(contour: list) -> list:
    step = SPACING * math.sqrt(2)
    rows = []
    for k in range(-4000, 4000):
        c = k * step
        line = LineSeg(start=(-10, -10 + c), end=(400, 400 + c))
        rows += topo.geometry.cut_by(line, contour, keep="inside")
    return rows


if __name__ == "__main__":
    contour = _small_contour()
    doc = ezdxf.new(dxfversion="R2010")
    write_native_segments(contour + _hatch_rows(contour), doc.modelspace(), "0")
    path = Path(__file__).resolve().parents[1] / "data" / "tratteggio_stretto_piccolo.dxf"
    doc.saveas(str(path))
    print(path)
