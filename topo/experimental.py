"""
topo/experimental.py
--------------------
Tutto ciò che topo espone senza promessa di stabilità (MAP.md D175 C, D176):
si usa, ma può cambiare in una minor. Un nome che diventa stabile si promuove
in una minor; qui resta come alias con avviso per due minor.

- i passi di `heal()` e della lettura per isole, uno per funzione (D117):
  `topo.heal()` e `topo.island()` sono le composizioni di default; chi
  compone la sua ricetta (D58, D62) prende i mattoni da qui, per esempio
  senza `build_hierarchy` finché non ha deciso da sé cosa significa un
  contorno dentro un altro;
- `read_islands` / `read_island` / `IslandReading`: `island()` prima di
  diventare un `Result` (D58);
- `simplify_points` (D33, D141), `rotate_*` (D46), `to_nester_input` (D18),
  `to_view_model` / `to_svg` / `save_svg` (D133), `to_text` / `save_text` (D84);
- le strisce fra bordi affacciati: `facing_boundaries`, `gap`, `link`,
  `unconnected_regions`, `open_boundaries` (D134, D142).

Si scrive per intero, `topo.experimental.<nome>`: chi legge lo script vede
che quel nome non ha la promessa (D119).
"""
# isole spaziali, rete piana, faccia esterna, tassellature (D58)
from .core.healing.islands import spatial_islands, Island
from .core.topology.noding import split_at_crossings, NodedEdges
from .core.topology.outer_face import outer_face, OuterFace
from .core.healing.normalizer import refit_tessellations
# normalizzazione e passi di heal() (D62)
from .core.healing.normalizer import (
    merge_collinear_overlaps, merge_cocircular_overlaps, weld_degenerate_linesegs,
)
from .core.healing.steps import (
    split_non_finite, split_labeled, close_free_gaps, dangling_splines, find_non_contour_edges,
    find_joining_edges, free_ends, close_near_full_arcs, NEAR_FULL_ARC_MISSING,
    repair_merged_corners, find_loops, LoopSearch, structural_loops,
    loops_to_curves, polygonize_to_curves,
    labeled_curves, build_hierarchy,
)
from .core.topology.loop_finder import edges_to_open_curves
from .core.island import read_islands, read_island, IslandReading
from .core.primitives.fitting import simplify_points
from .tools.rotate import rotate_result, rotate_cluster, rotate_document, rotate_to_longest
from .io.exporter import to_nester_input
from .io.view_model import to_view_model
from .io.svg import to_svg, save_svg
from .io.text import to_text, save_text
from .tools.strips import (
    facing_boundaries, Facing, gap, Gap, link, Link, Strip,
    unconnected_regions, open_boundaries, Opened,
)

__all__ = [
    "spatial_islands", "Island",
    "split_at_crossings", "NodedEdges",
    "outer_face", "OuterFace",
    "refit_tessellations",
    "merge_collinear_overlaps", "merge_cocircular_overlaps", "weld_degenerate_linesegs",
    "split_non_finite", "split_labeled", "close_free_gaps", "dangling_splines",
    "find_non_contour_edges", "find_joining_edges", "free_ends",
    "close_near_full_arcs", "NEAR_FULL_ARC_MISSING", "repair_merged_corners",
    "find_loops", "LoopSearch", "structural_loops",
    "loops_to_curves", "polygonize_to_curves",
    "edges_to_open_curves", "labeled_curves", "build_hierarchy",
    "read_islands", "read_island", "IslandReading",
    "simplify_points",
    "rotate_result", "rotate_cluster", "rotate_document", "rotate_to_longest",
    "to_nester_input",
    "to_view_model", "to_svg", "save_svg",
    "to_text", "save_text",
    "facing_boundaries", "Facing", "gap", "Gap", "link", "Link", "Strip",
    "unconnected_regions", "open_boundaries", "Opened",
]
