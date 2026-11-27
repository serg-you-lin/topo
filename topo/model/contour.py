"""
model/contour.py

Generic closed contour — a loop with a role, with no feature semantics.

It is the type `heal()` produces for the cluster's outer and for its inner
loops not yet classified (`cluster.inners`). A consumer may promote a
circular `Contour` to an element of its own; what remains is a contour cut.
It lives in a file of its own, not nested in
`cluster.py`, which defines only the container.

`depth` and `parent` carry the containment tree that `HierarchyBuilder` builds
internally (parent → children → grandchildren, at arbitrary depth) and that
would otherwise be lost by flattening everything into `cluster.inners`: the
outer has `depth=0`/`parent=None`, a direct child `depth=1`, a grandchild
`depth=2`, and so on. Purely geometric (containment between polygons,
computed in `heal()`), not semantic — a consumer can give the contours whatever
meaning it wants, these two fields do not change.

`Contour.from_segments()` builds a contour from a ring of primitives written
by a caller: it checks that the ring closes and encloses an area.
"""
from __future__ import annotations

import math
from dataclasses import KW_ONLY, dataclass, field
from typing import Optional, Sequence

from topo.core.geometry.shapely_polygons import build_polygon, with_polygon
from topo.core.primitives.mathseg import DEFAULT_TOLERANCE, segment_endpoints
from topo.model.curve import _Ring


@dataclass
class Contour(_Ring):
    """
    A closed contour: a closed curve with its depth in the containment
    hierarchy (`depth`, 0 = outermost) and its parent contour (`parent`,
    `None` for an outermost one).
    """
    _: KW_ONLY
    depth:  int                        = 0
    parent: Optional["Contour"]   = field(default=None, repr=False)   # the parent is printed where it is, not inside every child

    @classmethod
    def from_segments(cls, segments: Sequence, role: str, *, depth: int = 0,
                      parent: Optional["Contour"] = None,
                      tolerance: float = DEFAULT_TOLERANCE) -> "Contour":
        """Contour from a head-to-tail ring of primitives: each segment starts where the
        previous ends (within `tolerance`), the last closes on the first. ValueError
        if the ring does not close or does not enclose a valid polygon."""
        segs = list(segments)
        for k, seg in enumerate(segs):
            end, start = segment_endpoints(seg)[1], segment_endpoints(segs[(k + 1) % len(segs)])[0]
            if math.dist(end, start) > tolerance:
                raise ValueError(f"from_segments(): segment {k} ends at {end}, "
                                 f"the next starts at {start}: not a ring")
        polygon = build_polygon(segs, tolerance)
        if polygon is None:
            raise ValueError("from_segments(): the segments do not enclose a valid polygon")
        return with_polygon(cls(role=role, segments=segs, depth=depth, parent=parent), polygon)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "area": round(self.area, 4),
            "depth": self.depth,
        }
