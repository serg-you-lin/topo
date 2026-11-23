"""
tests/promises/test_outlines_single_use.py
------------------------------------
A piece of the planar network has a single fate: if the outer contour uses it,
it is not also a protrusion. Before, the loop chosen by the fallback could use
an edge that the walk had counted twice: it ended in the contour and in
`loose`, the same line twice. On the drawings without frame of
`golden_anchoring`, where the views are islands of their own.

"""

import unittest


import topo
import topo_dxf
from topo.core.readings.outline import read_outlines
from tests.paths import DATA

SOURCE_DIR = DATA / "golden_anchoring"
FILES = [f"anch_{i:02d}_noframe.dxf" for i in range(1, 9)]
MAX_GAP = 0.5


class TestOutlinesSingleUse(unittest.TestCase):

    def test_outer_edges_are_not_spurs(self):
        for name in FILES:
            with self.subTest(name=name):
                doc = topo_dxf.load_dxf(str(SOURCE_DIR / name))
                for i, r in enumerate(read_outlines(doc.edges, topo.precision.SAME_POINT, MAX_GAP)):
                    if r.outer is None:
                        continue
                    both = {id(e) for e in r.outer.edges} & {id(e) for e in r.spurs}
                    self.assertFalse(both, f"{name} isola {i}: {len(both)} edge nel contorno e fra le sporgenze")


if __name__ == "__main__":
    unittest.main()
