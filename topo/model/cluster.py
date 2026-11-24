"""
model/cluster.py

The Cluster: a part, an outer contour with its inner contours and a consumer's
overlay.
"""
from __future__ import annotations

from dataclasses import KW_ONLY, dataclass, field
from typing import Any, List, Optional

from topo.core.geometry.integrals import ring_area
from topo.core.geometry.rings import ring_perimeter
from topo.model.contour import Contour


@dataclass
class Cluster:
    """
    One outer contour (`outer`) and its inner contours (`inners`), with a
    `label`; the file it comes from is the `Result`'s. `overlay` is the open
    overlay of a consumer's reading, `None` until a consumer writes to it.
    """
    outer:         Contour
    _: KW_ONLY
    inners:        List[Contour]                      = field(default_factory=list)
    label:         str                                     = ""
    # A consumer's overlay (snapbend, snapdraw, a custom tool), normally a
    # `model.overlay.Overlay`. `None` until someone has written to it: it tells
    # "nobody has read the cluster yet" from "read and no element", which the old
    # fixed fields (always empty lists) could not. The only contract required,
    # never enforced at runtime, is duck-typed: `.get(name, default)` and `.items()`.
    overlay:       Optional[Any]                           = None

    def features(self, name: str) -> list:
        """Collection `name` attached to `self.overlay`, or `[]` if `overlay` is `None`
        or that name was not written — safe access for a consumer that does not want
        to handle `None` by hand. Generic: it does not need to know which names exist
        (`"holes"`, `"flange_view_hint"`, any other)."""
        if self.overlay is None:
            return []
        return self.overlay.get(name, [])

    @property
    def overlay_voids(self) -> list:
        """The overlay elements that are voids of the part: whoever read them declares
        `is_void = True` and carries the `segments` of a closed loop. A consumer that
        takes a contour out of `inners` to make an element of its own (a snapbend
        hole) does not change the part's area."""
        if self.overlay is None:
            return []
        return [
            item for _name, items in self.overlay.items() for item in items
            if getattr(item, "is_void", False) and getattr(item, "segments", None)
        ]

    @property
    def bbox(self):
        return self.outer.bbox

    @property
    def area(self) -> float:
        """Net area: odd depth is void, even depth is material (an island in the
        parent's void) — the signs alternate with the level."""
        return (
            self.outer.area
            - sum(_void_area(v) for v in self.overlay_voids)
            - sum(i.area if i.depth % 2 else -i.area for i in self.inners)
        )

    @property
    def summary(self) -> dict:
        """Raw count by name — `{name}_count: len(items)` for every collection attached
        to `self.overlay` (`{}` if `overlay is None`).

        Generic and always available, no runtime import: it works the same for whoever
        only did `heal()` (today: always `{}`) and for any custom name attached by an
        external tool — topo does not need to know what it is.

        The rich count by type (holes by type, grouped bends) belongs to the consumer
        that read them (snapbend `describe_features`)."""
        if self.overlay is None:
            return {}
        return {f"{name}_count": len(items) for name, items in self.overlay.items()}

    def to_dict(self) -> dict:
        """The geometric facts of the part, without coordinates: `label`, `area`, exact
        perimeters on the primitives, number of inner contours, `bbox`, and how many
        elements each `overlay` collection has. In mm, no rounding."""
        outer_perimeter = ring_perimeter(self.outer.segments)
        inner_perimeter = sum(ring_perimeter(i.segments) for i in self.inners)
        minx, miny, maxx, maxy = self.bbox
        return {
            "label":           self.label,
            "area":            self.area,
            "outer_perimeter": outer_perimeter,
            "inner_perimeter": inner_perimeter,
            "inner_count":     len(self.inners),
            "bbox":            {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy},
            "overlay":        {} if self.overlay is None
                               else {name: len(items) for name, items in self.overlay.items()},
        }


def _void_area(item) -> float:
    """Area of an overlay void, exact on its `segments`."""
    return ring_area(item.segments)

