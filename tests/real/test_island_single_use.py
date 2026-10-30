"""
tests/real/test_island_single_use.py
------------------------------------
Un pezzo della rete piana ha un solo destino: se il contorno esterno lo usa,
non è anche una sporgenza (D146). Prima il giro scelto per D100 poteva usare
un edge che il percorso aveva contato due volte: finiva nel contorno e in
`loose`, la stessa linea due volte. Sui disegni senza cornice di
`golden_anchoring`, dove le viste sono isole loro.
"""

import sys
import unittest
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

import topo_dxf
from topo.core.island import read_islands

SOURCE_DIR = project_root / "tests" / "data" / "golden_anchoring"
FILES = [f"anch_{i:02d}_noframe.dxf" for i in range(1, 9)]
MAX_GAP = 0.5


class TestIslandSingleUse(unittest.TestCase):

    def test_outer_edges_are_not_spurs(self):
        for name in FILES:
            with self.subTest(name=name):
                doc = topo_dxf.load_dxf(str(SOURCE_DIR / name))
                for i, r in enumerate(read_islands(doc.edges, doc.node_tolerance(override=None), MAX_GAP)):
                    if r.outer is None:
                        continue
                    both = {id(e) for e in r.outer.edges} & {id(e) for e in r.spurs}
                    self.assertFalse(both, f"{name} isola {i}: {len(both)} edge nel contorno e fra le sporgenze")


if __name__ == "__main__":
    unittest.main()
