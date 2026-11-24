"""
tests/adapters/dxf/test_attached_export.py
----------------------------------
`to_dxf` writes every collection attached to `cluster.overlay` by a consumer
(all of them, topo knows none by name). An element with a `role` goes on the
layer of its role: its `contours` if it has them, otherwise its `segments`.
Without a role or without geometry it is skipped.
"""

import unittest
from dataclasses import dataclass, field

import topo
import topo_dxf
from topo.model import Overlay
from topo import to_shapely


@dataclass
class _Mark:
    """A consumer's element: only what the exporter reads."""
    role: str
    segments: list = field(default_factory=list)
    styles: list = field(default_factory=list)
    source: str = "test"
    confidence: float = 1.0


@dataclass
class _Composite:
    """An element made of several closed contours (a hole with its seat)."""
    role: str
    contours: list = field(default_factory=list)
    source: str = "test"
    confidence: float = 1.0


def _plate():
    # 100x50 plate with two concentric holes and a single one
    doc = topo.load_geometry([
        {"type": "polygon", "points": [(0, 0), (100, 0), (100, 50), (0, 50)]},
        {"type": "circle", "center": (20, 25), "radius": 3},
        {"type": "circle", "center": (20, 25), "radius": 6},
        {"type": "circle", "center": (70, 25), "radius": 4},
    ])
    return doc, topo.heal(doc).faces()


def _layers(out):
    return [e.dxf.layer for e in out.modelspace()]


class TestAttachedExport(unittest.TestCase):

    def test_element_with_segments_on_its_role_layer(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        single = next(i for i in cluster.inners if abs(to_shapely(i).area - 3.1416 * 16) < 1)
        cluster.overlay = Overlay()
        cluster.overlay.attach("my_marks", [_Mark(role="my_role", segments=single.segments)])
        layers = _layers(topo_dxf.to_dxf(result))
        self.assertEqual(layers.count("my_role"), 1)

    def test_element_with_contours_writes_every_contour(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        pair = [i for i in cluster.inners if abs(to_shapely(i).centroid.x - 20) < 1e-6]
        self.assertEqual(len(pair), 2)
        cluster.overlay = Overlay()
        cluster.overlay.attach("my_marks", [_Composite(role="my_seat", contours=pair)])
        self.assertEqual(_layers(topo_dxf.to_dxf(result)).count("my_seat"), 2)

    def test_without_role_or_without_geometry_is_skipped(self):
        doc, result = _plate()
        cluster = result.clusters[0]
        before = len(_layers(topo_dxf.to_dxf(result)))
        cluster.overlay = Overlay()
        cluster.overlay.attach("my_marks", [_Mark(role="", segments=cluster.inners[0].segments),
                                             _Mark(role="my_role"), object()])
        self.assertEqual(len(_layers(topo_dxf.to_dxf(result))), before)


if __name__ == "__main__":
    unittest.main()
