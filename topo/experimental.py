"""
topo/experimental.py
--------------------
Everything topo exposes with no stability promise: it can be used, but may
change in a minor. A name that becomes stable is promoted in a minor; here it
stays as an alias with a warning for two minors.

- the steps of `heal()` and its readings, one per function: `topo.heal()`,
  `Network.faces()` and `Network.outlines()` are the default compositions;
  whoever composes a recipe takes the bricks from here, for example without
  `build_hierarchy` until they have decided for themselves what a contour
  inside another means;
- `read_outlines` / `read_outline` / `OutlineReading`: `outlines()` before it
  becomes a `Result`;
- `merge_near_copies` / `near_copies`: lines nearly on top of one another,
  merged with the caller's threshold, where they want;
- `simplify_points`, `rotate_*`, `to_view_model` / `to_svg` / `save_svg`;
- the strips between facing boundaries: `facing_boundaries`, `link`,
  `unconnected_regions`, `open_boundaries` (the distance between two boundaries
  is public, `topo.geometry.gap`);
- `parallel_families`: strokes split by direction and, in each, by line with its
  distance from the first row and the stretch each stroke covers;
- `parity_faces`: a third reading of the network, by parity. The limit is
  declared: where the choice has ties it depends on the coordinates.

Written in full, `topo.experimental.<name>`: whoever reads the script sees that
that name has no promise.
"""
# groups by contact, planar network, outer face, tessellations
from .core.topology.touching import touching_groups, TouchingGroup
from .core.topology.noding import split_at_crossings, NodedEdges
from .core.topology.outer_face import outer_face, OuterFace, face_loops
from .core.base.refit import refit_tessellations
# the foundations of every reading and the steps of heal()
from .core.base.prepare import prepare, Prepared, normalize, Normalized
from .core.topology.non_contour_edges import non_contour_pieces
from .core.base.merge import (merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
                                   merge_near_copies, near_copies, NearCopy)
from .core.base.cleanup import (split_labeled, close_free_gaps, dangling_splines, close_near_full_arcs)
from .core.readings.heal_steps import (find_non_contour_edges, find_joining_edges, free_ends, structural_loops, build_hierarchy)
from .core.base.curves import loops_to_curves, loose_curves
from .core.readings.outline import read_outlines, read_outline, OutlineReading
from .core.geometry.fitting import simplify_points
from .tools.rotate import rotate_result, rotate_cluster, rotate_document, rotate_to_longest
from .io.view_model import to_view_model
from .io.svg import to_svg, save_svg
from .core.readings.parity_faces import parity_faces
from .core.geometry.lines import parallel_families, ParallelFamily, ParallelRow
from .tools.strips import (
    facing_boundaries, Facing, link, Link, Strip,
    unconnected_regions, open_boundaries, Opened,
)

__all__ = [
    "touching_groups", "TouchingGroup",
    "split_at_crossings", "NodedEdges",
    "outer_face", "OuterFace", "face_loops",
    "prepare", "Prepared", "normalize", "Normalized", "non_contour_pieces",
    "refit_tessellations",
    "merge_collinear_overlaps", "merge_cocircular_overlaps", "weld_degenerate_linesegs",
    "merge_near_copies", "near_copies", "NearCopy",
    "split_labeled", "close_free_gaps", "dangling_splines",
    "find_non_contour_edges", "find_joining_edges", "free_ends",
    "close_near_full_arcs",
    "structural_loops", "loops_to_curves",
    "loose_curves", "build_hierarchy",
    "read_outlines", "read_outline", "OutlineReading",
    "simplify_points",
    "rotate_result", "rotate_cluster", "rotate_document", "rotate_to_longest",
    "to_view_model", "to_svg", "save_svg",
    "facing_boundaries", "Facing", "link", "Link", "Strip",
    "unconnected_regions", "open_boundaries", "Opened",
    "parity_faces",
    "parallel_families", "ParallelFamily", "ParallelRow",
]
