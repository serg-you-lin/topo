"""
tests/engine/tools/test_anchor_texts.py
-------------------------------
`anchor_texts()`: assigns `cluster_ref` (index of the containing part) to the
model's texts. Separate and optional phase (topo/tools/). What a tip lands on
or what a dimension measures is the consumer's reading.
"""

import unittest

import topo
from topo.model.cluster import Cluster
from topo.model.contour import Contour
from topo.model.result import Result
from topo.model.role import ContourRole
from topo.model.text import Text
from topo.tools.anchor import anchor_texts

def _part(x0, y0, x1, y1):
    ring = topo.geometry.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return Cluster(outer=Contour(segments=ring, role=ContourRole.OUTER))


def _result(*clusters, texts=()):
    return Result(clusters=list(clusters), texts=list(texts))


class TestAnchorTexts(unittest.TestCase):

    def test_containment_assigns_part_index(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(200, 0, 300, 100),
            texts=[
                Text(position=(50, 50), text="inside part 0"),
                Text(position=(250, 50), text="inside part 1"),
            ],
        )
        anchor_texts(res)
        self.assertEqual(res.texts[0].cluster_ref, 0)
        self.assertEqual(res.texts[1].cluster_ref, 1)

    def test_outside_all_parts_stays_none(self):
        res = _result(
            _part(0, 0, 100, 100),
            texts=[Text(position=(500, 500), text="titleblock")],
        )
        anchor_texts(res)
        self.assertIsNone(res.texts[0].cluster_ref)

    def test_snap_distance_assigns_near_part(self):
        res = _result(
            _part(0, 0, 100, 100),
            texts=[Text(position=(105, 50), text="callout just outside")],
        )
        anchor_texts(res, snap_distance=0.0)
        self.assertIsNone(res.texts[0].cluster_ref)

        anchor_texts(res, snap_distance=10.0)
        self.assertEqual(res.texts[0].cluster_ref, 0)

    def test_first_covering_part_wins_on_overlap(self):
        res = _result(
            _part(0, 0, 100, 100),
            _part(50, 50, 150, 150),   # overlapping the first
            texts=[Text(position=(75, 75), text="in the common zone")],
        )
        anchor_texts(res)
        self.assertEqual(res.texts[0].cluster_ref, 0)

    def test_no_parts_is_noop(self):
        res = _result(texts=[Text(position=(1, 1), text="x")])
        anchor_texts(res)
        self.assertIsNone(res.texts[0].cluster_ref)


if __name__ == "__main__":
    unittest.main()
