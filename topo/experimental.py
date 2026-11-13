"""
topo/experimental.py
--------------------
Tutto ciò che topo espone senza promessa di stabilità (MAP.md D175 C, D176):
si usa, ma può cambiare in una minor. Un nome che diventa stabile si promuove
in una minor; qui resta come alias con avviso per due minor.

- i passi di `heal()` e delle sue letture, uno per funzione (D117):
  `topo.heal()`, `Network.faces()` e `Network.outlines()` sono le
  composizioni di default; chi
  compone la sua ricetta (D58, D62) prende i mattoni da qui, per esempio
  senza `build_hierarchy` finché non ha deciso da sé cosa significa un
  contorno dentro un altro;
- `read_outlines` / `read_outline` / `OutlineReading`: `outlines()` prima di
  diventare un `Result` (D58);
- `merge_near_copies` / `near_copies`: le rette quasi una sopra l'altra,
  fuse con la soglia del chiamante, dove vuole lui (D226);
- `simplify_points` (D33, D141), `rotate_*` (D46),
  `to_view_model` / `to_svg` / `save_svg` (D133);
- `anchor_elements` / `pointer_target` / `measured_references`: su quale
  elemento cade una quota o una freccia (D228; obiettivo: sugli edge grezzi);
- le strisce fra bordi affacciati: `facing_boundaries`, `link`,
  `unconnected_regions`, `open_boundaries` (D134, D142; la distanza fra due
  bordi è pubblica, `topo.geometry.gap`, D251);
- `parity_faces`: una terza lettura della rete, per parità (D250). Il limite
  è dichiarato: dove la scelta ha pareggi dipende dalle coordinate.

Si scrive per intero, `topo.experimental.<nome>`: chi legge lo script vede
che quel nome non ha la promessa (D119).
"""
# gruppi per contatto, rete piana, faccia esterna, tassellature (D58)
from .core.readings.touching import touching_groups, TouchingGroup
from .core.topology.noding import split_at_crossings, NodedEdges
from .core.topology.outer_face import outer_face, OuterFace, face_loops
from .core.base.normalizer import refit_tessellations
# le basi di ogni lettura (D187, D189) e i passi di heal() (D62)
from .core.base.prepare import prepare, Prepared, normalize, Normalized
from .core.topology.non_contour_edges import non_contour_pieces
from .core.base.normalizer import (merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
                                   merge_near_copies, near_copies, NearCopy)
from .core.base.cleanup import (split_labeled, close_free_gaps, dangling_splines, close_near_full_arcs, NEAR_FULL_ARC_MISSING)
from .core.readings.heal_steps import (find_non_contour_edges, find_joining_edges, free_ends, structural_loops, build_hierarchy)
from .core.base.curves import loops_to_curves, loose_curves
from .core.readings.outline import read_outlines, read_outline, OutlineReading
from .core.primitives.fitting import simplify_points
from .tools.rotate import rotate_result, rotate_cluster, rotate_document, rotate_to_longest
from .io.view_model import to_view_model
from .io.svg import to_svg, save_svg
from .tools.anchor import anchor_elements, pointer_target, measured_references
from .core.readings.parity_faces import parity_faces
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
    "close_near_full_arcs", "NEAR_FULL_ARC_MISSING",
    "structural_loops", "loops_to_curves",
    "loose_curves", "build_hierarchy",
    "read_outlines", "read_outline", "OutlineReading",
    "simplify_points",
    "rotate_result", "rotate_cluster", "rotate_document", "rotate_to_longest",
    "to_view_model", "to_svg", "save_svg",
    "anchor_elements", "pointer_target", "measured_references",
    "facing_boundaries", "Facing", "link", "Link", "Strip",
    "unconnected_regions", "open_boundaries", "Opened",
    "parity_faces",
]
