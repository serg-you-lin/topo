"""
tests/real/test_island_single_use.py
------------------------------------
Un pezzo della rete piana ha un solo destino: se il contorno esterno lo usa,
non è anche una sporgenza (D146), e un estremo che cade a metà di un edge non
si chiude con un ponte sopra quell'edge (D147). Prima il giro scelto per D100 poteva usare
un edge che il percorso aveva contato due volte: finiva nel contorno e in
`loose`, la stessa linea due volte. Sui disegni senza cornice di
`golden_anchoring`, dove le viste sono isole loro.
"""

import math
import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo.core.island import read_islands
from topo.primitives import LineSeg

SOURCE_DIR = project_root / "tests" / "data" / "golden_anchoring"
FILES = [f"anch_{i:02d}_noframe.dxf" for i in range(1, 9)]
MAX_GAP = 0.5


class TestIslandSingleUse(unittest.TestCase):

    def test_outer_edges_are_not_spurs(self):
        for name in FILES:
            with self.subTest(name=name):
                doc = topo_dxf.load_dxf(str(SOURCE_DIR / name))
                for i, r in enumerate(read_islands(doc.edges, doc.node_tolerance(None), MAX_GAP)):
                    if r.outer is None:
                        continue
                    both = {id(e) for e in r.outer.edges} & {id(e) for e in r.spurs}
                    self.assertFalse(both, f"{name} isola {i}: {len(both)} edge nel contorno e fra le sporgenze")

    def test_ends_on_an_edge_are_not_bridged(self):
        # D147: due linee che partono a metà del lato sinistro, a 0.2 l'una
        # dall'altra (< max_gap). Prima si allungavano fino a incontrarsi
        # fuori dal quadrato: il contorno deviava e il tratto vero di lato
        # finiva in loose. Ora in loose ci sono solo le due linee.
        segs = [LineSeg((0, 0), (20, 0)), LineSeg((20, 0), (20, 20)), LineSeg((20, 20), (0, 20)),
                LineSeg((0, 20), (0, 0)), LineSeg((0, 10), (5, 10)), LineSeg((0, 10.2), (3, 13))]
        result = topo.island(topo.load_segments(segs), max_gap=MAX_GAP)
        loose = sum(math.dist(s.start, s.end) for c in result.loose for s in c.segments)
        self.assertAlmostEqual(loose, 5 + math.dist((0, 10.2), (3, 13)), places=6)
        self.assertEqual(result.clusters[0].outer.polygon.bounds, (0.0, 0.0, 20.0, 20.0))


if __name__ == "__main__":
    unittest.main()
