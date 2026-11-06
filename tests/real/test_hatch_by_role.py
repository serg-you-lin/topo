"""
tests/real/test_hatch_by_role.py
--------------------------------
G16 (D210): un tratteggio dentro un pezzo non sporca il contorno, se il
consumer gli dà un ruolo non strutturale prima di `heal()`.

Due disegni: lo stesso contorno di 12 LINE (con un restringimento di 0,3 mm)
e un HATCH ANSI31, che `topo_dxf` esplode in righe a 45° (D205). `stretto`
ha il tratteggio fitto (2622 righe), `largo` rado (11). Il test fa la parte
del consumer: il tratteggio sono le righe a 45° ± 0,2° (le righe corte,
tagliate sul bordo, escono a 44,97°–45,09°; il lato obliquo più vicino del
contorno è a 38,66°).

Promessa: in `faces()` e in `outlines()`, a 0,05 e a 0,5, il pezzo è quello
delle 12 LINE da sole — un cluster, 12 segmenti, nessun foro, la stessa area —
e ogni riga di tratteggio sta in `loose`.
"""

import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf

DATA = project_root / "tests" / "data"
FILES = {
    "stretto": DATA / "sbagli_tratteggio_stretto.dxf",
    "largo": DATA / "golden" / "sbagli_tratteggio_largo.dxf",
}
TOLERANCES = (0.05, 0.5)
HATCH_ANGLE = 45.0
ANGLE_BAND = 0.2
CONTOUR_LINES = 12


class TestHatchByRole(unittest.TestCase):

    def test_hatch_stays_out_of_the_contour(self):
        for name, path in FILES.items():
            for tolerance in TOLERANCES:
                doc = topo_dxf.load_dxf(str(path))
                hatch = [
                    e for e in doc.edges
                    if abs(topo.geometry.chord_angle_deg(e.start, e.end)
                           - HATCH_ANGLE) < ANGLE_BAND
                ]
                lines = [e.segment for e in doc.edges if e not in hatch]
                self.assertEqual(len(lines), CONTOUR_LINES)
                # il pezzo senza tratteggio: le 12 LINE del file, da sole
                alone = topo.heal(topo.load_segments(lines),
                                  tolerance=tolerance)
                area = alone.faces().clusters[0].outer.area
                for edge in hatch:
                    edge.role = topo.normalize_role("hatch")
                network = topo.heal(doc, tolerance=tolerance)
                for reading in ("faces", "outlines"):
                    with self.subTest(file=name, tolerance=tolerance,
                                      reading=reading):
                        result = getattr(network, reading)()
                        self.assertTrue(result.is_valid, result.errors)
                        self.assertEqual(len(result.clusters), 1)
                        cluster = result.clusters[0]
                        self.assertEqual(len(cluster.outer.segments),
                                         CONTOUR_LINES)
                        self.assertEqual(cluster.inners, [])
                        self.assertAlmostEqual(cluster.outer.area, area,
                                               places=6)
                        self.assertEqual(len(result.loose), len(hatch))


if __name__ == "__main__":
    unittest.main()
