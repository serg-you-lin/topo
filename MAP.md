# MAP.md — topo decision log

The register of the **rules in force**: one entry per rule, at most 5 lines;
a superseded rule is one line ("D59 → D99, D161"). The full text of every
decision, with its why and its history, is in `MAP_ARCHIVE.md` (local, not in
git; the same text is in git at `67fda38:MAP.md`). Not documentation (that's
`docs/`) and not a session log (that's the git log).

Rule: a closed decision is **not re-decided from scratch**. To reopen it, say
so — "reopening D##". A new decision takes the next `D##` and one entry here.

- **What topo is, how to use it** → `README.md`, `docs/API.md`, `docs/LLM.md`
- **How it's built inside** → `docs/ARCHITECTURE.md`
- **What exists in the code** → `docs/INDEX.md` (generated, `scripts/gen_index.py`, D72)
- **Where to start a session** → `CLAUDE.md` (routing + non-negotiables, D72)
- **What is open** → `TODO.md`, `ROADMAP.md`; the 1.0 gate is D148/D193

`scripts/check_map_shrink.py` checks this file against the full text: every
`D##` keeps one entry, none defined twice, no reference left dangling.

---

## The public API contract

```python
import topo, topo_dxf                       # g-topo[dxf]: topo + the DXF adapter

doc    = topo_dxf.load_dxf("file.dxf")      # the adapter: the only code that reads a format
result = topo.heal(doc)                     # topology — no format
doc_out = topo_dxf.to_dxf(result, doc)      # a new document — never the source's entities
for part in topo.split(result):             # one Result per part
    topo_dxf.to_dxf(part, doc).saveas(f"{part.clusters[0].label}.dxf")
doc = topo.load_segments(topo.geometry.rectangle(200, 100))   # no file at all
```

topo has no file format (D123): geometry and roles, never layers. `topo`
never imports `ezdxf`, PyMuPDF or an adapter; the adapters (`topo_dxf`,
`topo_pdf`, siblings in the same distribution, D124, D129) use topo's public
names only (`gen_index --check`). An adapter produces a `Document` of pure
data; after loading, the source disappears. `to_dxf` builds a **new**
document from the model's own segments. The model is the product; DXF is one
of its representations. Every function: `docs/API.md`.

## Status

Version in `pyproject.toml`. Open: the 1.0 gate in `TODO.md` (D148, D193,
closed list, feature freeze until `scripts/release_check.py` exits 0).
Everything else — the PDF adapter in `topo_pdf` included — is 1.x (D174).

---

## DECISIONS IN FORCE

Names in the older entries are the names of their day (`forge`, `ForgeCluster`,
`Feature`, `detect`); the rename is D108/D119, the move of detection D88–D90.

- ~~D1~~ → D108, D119: the library was `forge`, then `topo` / `g-topo`.
- ~~D2~~ → D88, D90: `heal_and_detect` is gone; detection left topo, the
  path is load → heal → render.
- **D3** — an enrichment step returns the same, mutated result so calls chain
  (`result = step(result)`); `detect` itself left topo (D90).
- **D4** — no bridge layer between the adapter and the model: `heal` builds
  the model directly from native segments; "has a polygon / doesn't" is kept
  (`Feature` → `Curve`, D114; no `.polygon`, D166).
- ~~D5~~ → D88, D90: `source`/`confidence` on detected features, four
  separate types — detection lives in snapbend.
- **D6** — `segments_from_loop` lives in `core/topology/loop_finder.py`
  (domain logic, not parsing); every primitive has `.reversed()`.
- **D7** — one entity→primitive dispatcher for production and tests. It
  surfaced a real bug (`ArcSeg.from_chord` on major arcs, signed `r·cos`).
- **D8** — feature counts are a derived `summary`, not copied by `inject()`;
  `inject()` is only the hook for external enrichment (material, thickness).
- **D9** — the inspector (`topo.inspect`, `topo_dxf.inspect`) prints three
  levels: raw entities, what the adapter understood, what the model holds.
- **D10** — `load_pdf` is frozen: returns `list[Edge]`, not a `Document`,
  out of `__all__`; to resume in `topo_pdf` (TODO "Aperti minori").
- **D11** — the version has one source, `pyproject.toml`
  (`importlib.metadata`); nothing else is bumped by hand.
- **D12** — SVG is output only (`to_view_model` = the JSON contract for a
  renderer, `to_svg` on top of it, one palette per role). The viewer is
  outside the stable 1.0 (D133); its redesign would reopen D12's flattening.
- ~~D13~~ → D90: `detect_engrave` deferred — moot, detection left topo.
- **D14** — the numbered scripts are an API-learning gym: one per public
  function, default inputs in `tests/examples/`, runnable with zero setup.
- ~~D15~~ → D88–D90: `detect()` parametric, hole classification there. The
  principle stays: a process parameter is the caller's, never topology
  (CLAUDE.md non-negotiable 4).
- **D16** — a dashboard/UI is its own repo that installs topo; the library
  carries no web or GUI dependency.
- **D17** — invariant: the pipeline never translates geometry. Endpoints move
  only to close gaps; writers emit segments verbatim; a split part lands at
  the same absolute XY as the source (`test_golden_split`). Z flattens to 0.
- **D18** — topo does not nest. `to_nester_input` is out of `__all__`
  (`topo.experimental`), kept, undocumented.
- **D19** — `Edge` lives in `core/topology/edge.py`; `core` never depends on
  `adapters` (the dependency rule, D44).
- **D20** — one typed annotation model, no `data` dict, no shapely in
  fields; the adapter only reads/writes the format; interpretation is its own
  step (`anchor_texts`, D43). Types folded into `Text` by D138.
- **D21** — `heal()` yields clusters, spatially separate groups; whether one
  is a part, a view or a title block is the consumer's reading. The `Forge`
  prefix went with D119.
- **D22** — `core` holds the engine's one act, `tools` optional composable
  steps on a result, `io` the renderers; no `pipeline/`. D58 reopened it:
  the engine has two readings.
- **D23** — scripts live in `scripts/`; the first line is `import _paths`
  (a `chdir` to the repo root), so a relative path means the same everywhere.
- **D24** — frame and title-block detection are not topo's (they run before
  `heal` on raw geometry): the frame detector was deleted; `frame` is only a
  role a consumer may assign.
- **D25** — recognition heuristics sit next to their consumer in `tools/`,
  never in `core/`, which is only the deterministic geometric engine.
- **D26** — `model/` holds one concept per file; a type the result holds
  stays in `model/` (so `model` never imports `tools`). `classified_entities`
  left with D150.
- **D27** — `role` is an open vocabulary (`role: str`). The enum is never
  authoritative or a reverse lookup of caller data (`dict.get` only);
  `normalize_role` is the single point at load (`[a-z0-9_-]`, ≤ 64 chars);
  sinks defend again (unknown role → trash layer, SVG escapes it).
- **D28** — the non-contour edge finder keeps a neutral name
  (`NonContourEdgeDetector`): topologically it excludes chords from the graph
  before loop search, which is `heal`'s job.
- **D29** — frame/title-block recognition is `snapdraw`, a consumer that tags
  edges `frame`/`title_block` before `heal`; it enters topo through `role`.
- **D30** — one predicate for "this role is part-contour topology"
  (`STRUCTURAL_ROLES`, `is_structural_role`); `heal` pulls every edge with a
  decided non-structural role out of the topology (no gap solving, no corner
  repair) into `loose` with its role intact; unknown roles are left alone.
- **D31** — consumer roles are not topo's: `ContourRole.FRAME` was removed;
  output by role was settled in D128.
- **D32** — `load_geometry` is public: a consumer brings generated geometry
  into a `Document` without a file (first user: snapbend's developments).
- **D33** — point→primitive reconstruction (`simplify_points`) is topo's job:
  it takes an ordered point sequence, finds corners by angle and refits each
  stretch. Its thresholds are the caller's parameters, never constants.
  Rewritten in D141.
- **D34** — every contour carries `depth` (0 outer, 1 child, …) and `parent`,
  filled in the one recursion that builds the containment tree; the tree is
  recomputed on every `heal()`, so the caller decides when a root is a root.
- **D35** — all loaders expose the same entity vocabulary: whatever `Edge`
  supports (line, arc, circle, spline, ellipse), not the subset a use case
  needs. `load_geometry` mirrors each primitive's fields 1:1.
- ~~D36~~ → D141: `fit_primitives` with arc fitting (`arc_fit_tolerance`,
  Kasa circle fit); the rule is now one chain in `simplify_points`.
- ~~D37~~ → D128: `RoleStyle` — colour/linetype/weight per role, on the layer
  (true colour: ACI has no pure black); now neutral in the model.
- **D38** — point-sequence math (`detect_corners`, `fit_circle_kasa`,
  `arc_angles`, …) lives in `core/geometry`, next to the segment math; the
  orchestrator imports it back.
- ~~D39~~ → D40: `cut_tabs`, a gap within one contour (draft).
- ~~D40~~ → D134, D142: `bridge_tabs` / `bridge_nested_tabs` — a tab from a
  child to its direct parent, never a skipped level; now `tools.strips`.
- **D41** — a SPLINE is written from control points + knots only, never with
  `fit_points` as well (some CAM readers, SigmaNest, fail on both); `closed`
  only when the whole closed contour is one stretch.
- **D42** — `BSplineSeg.discretize` evaluates the real curve (de Boor,
  rational with weights), adaptive to `tolerance`; pure `math`, so `core`
  works without `ezdxf`. The control polygon is never the curve.
- **D43** — anchoring a text is geometry (containment, optional snap), with
  no judgment of meaning, so it is `anchor_*`, not "interpret", and stays in
  topo (`anchor_texts`).
- **D44** — `cluster.detected` is an open-by-name overlay, `None` until a
  tool writes it (`attach(name, items)`); an item is a `Protocol` (`source`,
  `confidence`), not a hierarchy; `model` does not import `tools`;
  `cluster.summary` is a generic count per collection.
- **D45** — `EllipseSeg` is the fifth primitive: a native conic, written as
  ELLIPSE and never as a spline or a discretized fallback; `major_axis` is a
  vector, one class for a full ellipse and an arc, adaptive discretization
  shared with splines. Found a golden that had silently dropped an ellipse.
- **D46** — `.rotated(angle, origin)` on every primitive. A rigid rotation
  never changes topology, so `rotate_result` transforms an already-healed
  result with no second `heal()`; what to align is structural (`outer` vs
  `inners`), never by `role`. Overlays and annotations are not rotated
  (detect after rotating). `topo.tools.rotate` is experimental.

- **D47** — `core` and `model` hold no process vocabulary (no hole, bend,
  engrave). `heal(is_structural=...)` takes the predicate "is this role part
  of a contour" and threads it to the three places that ask (label split,
  loop check, trash collection); without one a labelled non-outer/inner edge
  is non-structural and a generic warning says so. `ContourRole` is only
  `UNKNOWN`/`OUTER`/`INNER`. The style-registry half was reopened by D128.
- **D48** — text stretch is domain data: `Text.width_factor` (1.0 = none), the
  axis a PDF `Tz` or CSS `font-stretch` also has. The DXF adapter reads a
  `TEXT`'s own width, else its style's; an `MTEXT` group 41 is a wrap width,
  never a stretch. The writer applies it per format; no style is matched by name.
- **D49** — the non-contour test works per connected component, not on the
  whole sheet (a small view next to a big one lost 3 of its 4 sides to the
  big one's hull). D111 removed the hull; the per-component scope stays.
- **D50** — `merge_collinear_overlaps`: fragments that touch or overlap on the
  same exact line are one edge. The line key is a fixed tight precision, not
  the heal tolerance; it runs first, so the graph never sees the spurious
  nodes; the merged edge keeps the rounded node coordinates; only
  `role == UNKNOWN` merges; input order is kept (a cleanup pre-pass is a
  no-op on what it does not touch). A source-format fact (`closed_path`) is
  never a criterion. D110 reopened it for `heal()` at junction nodes.
- **D51** — `closed_path` is gone from `Edge`: it recorded how one CAD author
  grouped entities, which no model rule can derive and no other adapter can
  fill. The core stands without it (suite unchanged); the dead boundary-dedup
  step in `detect` went too.
- **D52** — `merge_cocircular_overlaps`: D50 for arcs (angles unwrapped, a
  full turn is a `CircleSeg`, never a 360° `ArcSeg`). The graph no longer drops
  an edge whose endpoints cluster together if its real extent (`r·sweep`)
  exceeds epsilon. Round-trip tests have their own tolerances (measured).
- ~~D53~~ → D63: `layer_to_role` → `label_to_role`; `label_map` is now
  `role_rules`. The rule stands: no format word (layer, entity) in core names.
- ~~D54~~ → D90: a labelled line fully on the outer boundary is absorbed
  (`covers`, not `contains`) — assignment lives with detection in snapbend.
- **D55** — the non-contour test is a public primitive
  (`tools.non_contour.non_contour_candidates(doc)`): the same detector `heal()`
  uses, returning the `Edge` objects so a caller sets `.role` before `heal()`.
  topo only says "candidate"; what it is belongs to the caller. It runs on the
  raw edges, so on a dirty drawing it can differ slightly from `heal()`.
- **D56** — `weld_degenerate_linesegs`: a `LineSeg` shorter than a fixed
  0.05 mm (not the caller's tolerance, a gap-closing radius) is welded by
  union-find on its two nodes, never deleted (deleting detaches chains). Only
  the node moves, `segment` keeps the real point; `UNKNOWN` role only.
  D152 and D186 bounded and ordered the welding.
- **D57** — corner repair runs whenever free ends remain
  (`not loops or graph.open_nodes()`), not only when no loop exists: one
  closed hole elsewhere must not shield a broken contour from repair.
- **D58** — the engine has two readings of a `Document`, `heal()` (from the
  inside, by connectivity) and `island()` (from the outside); they compose the
  same ingredients and fill the same model, which is the product. The caller
  chooses by the drawing (flat cutting file vs views). Reopens D22's "heal is
  the core act". A cluster may be a view, a part or the frame (D21).
- ~~D59~~ → D99, D161: `island()` by proximity of islands, planar network
  (`split_at_crossings`, one fine grid) and the outer face as the walk of the
  smallest counter-clockwise turn from the leftmost geometric point.
  The network and the walk survive; the grouping and the interior do not.
- **D60** — view normalization: a chain of ≥ 10 `LineSeg` shorter than
  0.1 mm is a tessellation and is refitted (`refit_tessellations`: arc or
  circle within 0.02 mm, else spline); `island()` closes drawing gaps up to
  `max_gap` through `local_gap_fixes` (a fix never moves an endpoint further
  than the gap itself). `heal()` uses neither. D98 made `max_gap` required.
- **D61** — the B-spline interpolation is topo's own math
  (`interpolate_bspline`, Piegl & Tiller 9.2.1, equal to ezdxf's to 2e-12):
  no format library is imported in `core`, `model` or `tools`.
- **D62** — `HealStep` is gone: the steps of `heal()` are public functions
  edges-in/edges-out (typed only where a step answers more than one question,
  `LoopSearch`), `heal()` is a recipe in `core/heal.py` beside `island()`, and
  there is no shared `normalize()` — each reading prepares its edges its own
  way. D187/D189 later put both on one base.
- **D63** — `role_rules` (`RoleRule`: `name`, `name_contains`, `dashed`,
  `color`, all must hold, first match wins, evaluated in the caller's order)
  replace `label_map`/`linetype_map`/`color_map`. The source's grouping name
  never leaves the adapter; "dashed" is a fact of the pattern (a gap), not
  of the linetype's name; heuristic vocabularies ("construction") are the
  caller's content.
- **D64** — `EdgeStyle.dash_kind` is `continuous`, `uniform` (one mark
  repeated) or `chain` (marks differing by > 5% of the pattern length);
  `RoleRule(dash=)` matches on it. Chain → construction is snapdraw's
  mapping, not topo's.
- **D65** — `island()` merges after the cut: consecutive segments of a
  contour on the same circle or line, same direction, same style become one;
  a contour made only of arcs of one circle becomes a `CircleSeg`. It does
  not restore the parent edge (that would only undo topo's own cuts).
- **D66** — a leader's target is the element its tip lands on: the nearest
  boundary within 0.5 mm (tie → the smaller element), else the smallest closed
  element covering the tip, else none. Text reading is not topo's. The path
  form (`"clusters[0].inners[3]"`) became the objects themselves in D177.
- ~~D67~~ → D88: `detect` renamed `detect_flat` (a flat part seen from its
  face); it left topo with the rest of detection.
- **D68** — `contour_shape(contour)` says **circle**, **stadium**,
  **rectangle**, **polygon**, **other**, never hole or slot (a circle in a
  view may be a pin; "slot" needs the other views, "drill" needs the
  process). Tolerance 1% of size and 1°; segments are recomposed first.
  The list of kinds is closed by D136.
- **D69** — `Dimension.measured_points` (neutral: the points on the measured
  geometry; a radius gives the point on the arc, not the centre) and
  `dimension_references` anchor a dimension to the elements within 0.5 mm.
  `display_text` is the author's text with `<>` replaced by the value as
  drawn; MTEXT formatting is stripped, `%%c` → Ø. Scale checks are snapdraw's.
- ~~D70~~ → D90, D128: `to_dxf` writes every collection of the overlay, an
  item on the layer of its role — now output by role.
- ~~D71~~ → D161: a nested island brings all its closed loops to its host.
- **D72** — `CLAUDE.md` is the router (table of "which file for which
  question" + non-negotiables); `docs/INDEX.md` is generated by
  `scripts/gen_index.py` from `ast`, and the script checks names defined in
  more than one module and the dependency rule. A hand-written inventory
  lies at the next commit.
- **D73** — a client drawing name, part code or order number never appears
  in a tracked file (MAP, script CONFIG, comment, commit message) and no
  sentence maps an anonymized fixture back to its origin: describe the case
  ("a dense strip view"). `scripts/audit_names.py --strict` enforces it
  (`--from-disk` also looks for untracked drawing names); false positives go
  in `ALLOWED`.
- **D74** — the consumer is spelled `snapdraw` everywhere, lowercase. No
  `snapforge` alias: an import name changes for real or not at all.
- **D75** — a tracked fixture has an invented name saying what it exercises;
  unused client files leave git but stay on disk. An anonymizing rename must
  check the target name is free (a collision once fed the wrong drawing to a
  test). A name is anonymized by script; the text inside a drawing is read by
  a person.
- **D76** — the audit reads drawing content too (UNC paths, printer names,
  part codes as layers and title-block texts): `git ls-files -z`, tokens split
  on non-alphanumerics, a bare-digit name is a code. A part code in a fixture
  becomes an invented sigil. `audit_fixtures.py` lists the drawings the
  suite needs and git lacks (a golden without its parent only `skipTest`s).
- ~~D77~~ → D80: `anonymize` — clean a DXF as a file (tag pairs, strings
  replaced never deleted, by value), with `heal()` as the oracle that refuses
  to write if a number moved.
- **D78** — fixtures are read one string at a time, aggregated to one row per
  distinct string. A name (an initialism on dimension styles) has no shape
  and slips past `audit_names`; cleaning follows the string across every copy
  of a drawing. Putting a client-sourced drawing into git is Federico's call.
- **D79** — `tests/data/` is the tracked root: a drawing is publishable
  *because it lives there*, not because someone remembers a flag.
  `tests/examples/` stays local (client originals, scratch). Goldens carry a
  bare file name, so moving a drawing is invisible to them.
- **D80** — `anonymize` is not in topo: it is `dxf-anonymize`, a private
  project that depends on topo, installed with `pipx`. No public or shared
  repo may declare it, not even as an extra: a dependency line naming it is
  a suspicion by itself.
- **D81** — the history was rewritten once (2 October): data files gone from
  HEAD leave the history, strings are replaced everywhere (commit messages
  included) from a list kept outside the repo; proof is HEAD's tree hash
  unchanged. Forward only: `audit_names --strict` on every change,
  `--history` before a release. Redone in D97.
- **D82** — `inject(snap_distance=...)` and `anchor_texts` share one rule: a
  text covered by an outer belongs to it; else to the single nearest outer
  within `snap_distance`; else to none. Default 0 is strict containment.
- **D83** — `to_dxf` and `to_svg` take `allow_invalid=True`: topo renders
  whatever the model holds (nothing is dropped). A caller delivering to a
  machine passes `False` and gets `ValueError`. `split` always raises on an
  invalid result: it has no parts to make.
- **D84** — `to_text(result)` is a Markdown reading for a language model,
  experimental (outside `__all__`). Ids are topo's (`Cn` cluster, `Cn.k`
  inner), never "view"; shapes by `contour_shape`; splines by ends, bbox and
  length (`spline_data=True` adds the data); the size is budgeted by
  `tests/real/test_text_budget.py`, regenerated only after reading the text.
- **D85** — one `ensure_linetype(doc, name, pattern)`: already in the
  document → the caller's pattern → the standard table → `None`. `None` means
  BYLAYER for a source edge, but `ValueError` for a caller's style naming a
  linetype nobody defines.
- **D86** — `gen_index.py --similar` compares bodies (locals renamed) and
  prints candidates, not verdicts; each is read before touching. Found and
  merged: `point_on_circle`, `_sagitta_step`, `angle_from_start`,
  `loop_geometry`, `DEFAULT_NODE_TOLERANCE`.
- **D87** — the collinear and cocircular merges are one engine
  (`_merge_on_carrier`): an edge is an interval on its line or its circle;
  group by carrier, chain what touches or overlaps, put the result where its
  first member was. Proved equal to the old pair on 611 DXF (0 differences).
- **D88** — the boundary: topo reads **structure** (what closes, what lies
  inside what, what connects); consumers read **meaning** (hole, bend, view,
  dimension). So `heal()` and `island()` both stay (neither is a cutting
  mode), `split()` stays, and process thresholds, hole/bend/engrave and
  their layers leave. Without a consumer's reading a hole is an inner contour.
  The sheet-metal consumer is `snapbend`.
- **D89** — golden are two halves: `json/` is geometry, checked by `heal()`
  alone; `process/` belongs to the consumer. `cluster.area` follows the
  parity of depth: odd depths subtract, even depths add back (outer − voids
  + islands − voids in islands); an island was once removed twice.
- **D90** — detection lives in `snapbend.flat`. topo keeps the open overlay
  (`DetectedFeatures`) but knows no name in it: renderers read `role` +
  geometry, never a collection name; `feature_role` picks the role to draw
  (the contour's own if it is a consumer role, else the item's); an item
  with `is_void` and a region subtracts from the area, whoever names it.
- **D91** — two geometric facts in `topo.geometry`, under D68's "circle,
  never hole": `concentric_groups` (a partition of circles by centre, smallest
  first) and `arcs_around` (arcs concentric and larger, with sweep and radius
  ratio). Thresholds ("~270°", "ratio ≤ 1.6", the drill limit) are the
  consumers'; there is no shared `Hole` model.
- **D92** — `gen_index.py` is the same file in every project, the rule is in
  `pyproject.toml` (`[tool.gen_index.layers]`; a forbidden name may be an
  external package), `--check` fails on a stale index or a broken rule, and
  `tests/unit/test_index.py` runs it on every `pytest`.
- **D93** — line facts live in `core/geometry/lines.py`: `point_line_distance`,
  `are_collinear`, `group_collinear_lines`, `bridged_runs`, and a chord cut
  (`splits_polygon`, now `splits_contour`, D168). Reaches, tolerances and
  "this is a bend" stay the consumer's.
- **D94** — axis-aligned facts live in `core/geometry/axis.py`:
  `merge_intervals`, `interval_coverage`, `cluster_values`, `axis_lines`,
  `covered_rectangles` (four sides covered by straight items, no polygonize),
  `spanning_lines`, `items_inside`, `axis_aligned_share`. A consumer keeps its
  numbers (a frame side ≥ 30%, the ISO ratio).
- **D95** — all geometry is one package, `core/geometry/`, public as
  `topo.geometry` (`__init__.py` is the map; building blocks import from their
  submodule). Facts are frozen dataclasses computed on demand, never
  precomputed or cached on the model; no "Geometry" wrapper of a drawing.
- **D96** — drawing with topo: builders `polygon`, `rectangle`,
  `regular_polygon`, `circle`, `stadium` (the very measures `contour_shape`
  reports, so build and read round-trip) and `load_segments`. The dict schema
  of `load_geometry` says `polygon`, never `polyline`.
- **D97** — a history rewrite or force push happens only after Federico says
  yes to that specific step (Claude Code asks too: `permissions.ask`). The
  second rewrite (4 October) was done with the `dxf-anonymize repo` tool
  and a local map of names and code families.
- **D98** — `island()` takes no domain default: `max_gap` is required and by
  name (`island_gap`, D59's second number, went in D99). Judged right by eye
  it varied from 17 to 78 mm; the "scale of a drawing" is not published.
- **D99** — islands are outer contours, not distances. Pieces are the edges
  that touch (`spatial_islands` at `max_gap`); every outer contour not inside
  another is an island and what lies inside it is its own by containment;
  open edges stay in `loose` but carry `cluster_ref`. Reopened by D161.
- **D100** — the outer face is the boundary of the union of the closed faces
  (per whole piece, not per graph component): where a line is tangent to an
  arc, the walk could go down one side and back along the other. D199 keeps
  the union; its re-noding on discretizations is a known 1.x defect. The
  13 island golden are topo's (`tests/data/golden_islands/`).
- **D101** — one node criterion: two cuts of one edge closer than `tolerance`
  are the same node (`_split_params` deduplicated with `_MIN_PIECE`, 1e-4 mm,
  so a near-tangent line gave two roots hundredths of a mm apart and a sliver
  between them). Raising `GRAPH_EPSILON` instead was tried and rejected: it is
  global, percolates, and drops real holes.
- **D102** — a gap-fix across two endpoints already in the same connected
  component is a sliver, not a gap (`_drop_redundant_meets`): a real gap
  always spans two components; closing this one only opens a parallel path
  beside a contour that already closes.
- ~~D103~~ → D157, D161: `_drop_boundary_duplicates` — a loop whose whole
  boundary lies within `tolerance + max_gap` of a larger accepted loop is a
  duplicate, not an inner; its edges go to `loose`. D157 verified the four
  doubts, D161 changed what `island()` reads.

## Open questions

- **Reading for a language model (D84).** Measured (o200k): a raw DXF costs
  ~2.3× "bytes/4" in tokens; `to_view_model`/`to_svg` can exceed the source on
  spline-heavy sheets; an image alone misses exactness (thickness, small
  features, which dimension measures what); image + a topo reading 6/6, raw
  DXF 6/6 at ~3.5× the tokens. The case is cost and scale; the headline is
  correct answers. A serious run must use anonymized drawings. Detection on
  islands is a consumer's.
- **Name of the role `outer`** in the island reading: unresolved. It stays
  `ContourRole.OUTER` in both readings (renaming touches `heal`, golden and
  layers).
- `inspect_dxf` wants an entity-type filter (a `types` parameter): queued.
- **D104** — permanent invariants on `island()` (never regenerated):
  `.polygon` and `build_polygon(.segments)` describe the same shape (± 1% of
  area), every `.polygon` is simple with positive area, and a DXF round-trip
  gives the same islands back. The divergence they exposed was closed in D106.
- ~~D105~~ → D106: reopening D104 — a 40% failure rate is not a gap to shelve;
  a second graph on the rim edges was a lead that D106 refuted by measurement.
- **D106** — a face's segments are read off its own boundary
  (`rim.face_segments`): walk the ring, split it among edges with the fewest
  switches over (edge, sense), each run is its edge trimmed exactly
  (`sub_segment`; B-splines by knot insertion). A loop that touches itself is
  one face per lobe (`buffer(0)` kept only the largest). A face whose mean
  width 2·area/perimeter is below `tolerance` is not a face (its edges go to
  `loose`). Guard comparisons are at the resolution of the representation.
- **D107** — two more invariants: nothing dropped (every input piece within
  `max_gap` of some output; the gap-fix may move an end that far, D98) and
  inner contours of one island are disjoint or nested. Pieces of a loop that
  no face uses go to `loose` (`off_faces`); a run keeps one direction along
  its edge, so it ends at a tip instead of folding back.
- **D108** — the package is `topo`, distributed on PyPI as `g-topo` (`topo` is
  an abandoned 2019 project); no `forge` alias. Applied in D119.
- **D109** — editing a contour by a region (a disk out of an outer, a trace
  cut by a region) is topo's geometry, in topo's words, never "relief"; which
  traces, crossings and radius is the consumer's. Built as D118.
- **D110** — reopening D50 for `heal()`: `merge_collinear_overlaps(
  keep_junctions=True)` keeps two collinear pieces apart when they only touch
  at a node where an edge on another line also ends (a real node, which
  `heal()`'s graph does not create itself). `island()` nodes the network
  itself and keeps D50's behaviour. Lines only.
- **D111** — reopening D49: an edge is contour when the boundary of its
  component's outer face traverses it exactly once (a chord is never
  traversed, a bridge or spur twice), walked on the planar network at the heal
  tolerance; a convex hull is no criterion. `heal()` has permanent invariants
  (valid polygons, nothing dropped, chords and their roles don't matter,
  rigid motion, edge order, never raises); `split_non_finite` sets NaN edges
  aside; `free_ends` and `find_joining_edges` feed the ambiguity warnings.
- **D112** — the tolerance measures a gap, not a side. In `heal()` free ends
  pair two by two, nearest first (`pairwise=True`); an end closes one gap;
  `island()` keeps every pair. An arc closes on itself only if both the gap
  is ≤ `tolerance` and the missing angle ≤ `NEAR_FULL_ARC_MISSING` (2°);
  the tolerant graph never closes an edge on itself.
- **D113** — one node grid for every reading, `NODE_DECIMALS = 3`: two ends
  are one node only if they coincide on it. The tolerance only bounds the
  gap that `close_free_gaps`, the tolerant loop step and `max_gap` may
  close; it no longer shapes nodes (a sharp corner's arc was lost to a
  0.1 grid).
- **D114** — `Feature` → `Curve` (`ClosedCurve`, `OpenCurve`): the base of
  the model is geometry, not a reading; a feature is what a consumer finds,
  and the overlay keeps its `DetectedFeature` names. No alias.
- **D115** — `geometry.dash_line(start, end, head, tail, middle, n_middle)`:
  one dash glued to each end, `n` equal dashes between, equal gaps, placed from
  the ends inward; whole segment back if the dashes cover it. Straight only.
  Arithmetic along a segment is topo's (D91), not a consumer's second copy.
- **D116** — `INTERPRETER.md` and `SNAPDRAW.md` left the repo: design notes of
  projects around topo are not topo's documentation.
- **D117** — no brand in type names: `topo.Document`, `Result`, `Cluster`,
  `Contour` (applied in D119). The steps of `heal()` and of the island
  reading live in `topo.steps`; the top level keeps the pipeline.
- **D118** — primitives for a caller's own algorithms, on rings of native
  primitives: `geometry.intersections` (exact for lines, arcs, circles; within
  1e-4 for splines and ellipses), `point_on_contour`, `cut_by(segment, region)`,
  `contour_minus(contour, region)`, `Contour.from_segments`. The region is
  *any* closed ring, never a named shape; every ring left is returned, the
  caller chooses. Which points, radii and groupings is the caller's. Pure
  functions and typed results, with a later Rust port in mind.
- **D119** — the rename is applied (`topo` / `g-topo`, no `Forge*`, steps in
  `topo.steps`). Formats follow: XML root `<topo>`, DXF XDATA id `TOPO`,
  `<name>.topo.md`. A call is written `import topo` then the full path
  (`topo.geometry.contour_shape(...)`), never `from topo import steps`; every
  example in the docs uses that form.
- **D120** — the public surface, first half: `topo.primitives` (five segments,
  `sub_segment`, pure math) and `topo.model` (types, roles, `Edge`, which is a
  segment *with* a role). Everything under `topo.core` is internal. `gen_index`
  gets a `"*"` layer and dotted names. The second half is D122.
- **D121** — direction: what makes topo trustworthy is two-way fidelity (the
  part written overlays the original; built as D143/D152). One `Curve`
  protocol with `as_analytic(tol)` as a *question* (the original geometry
  stays the truth), a contour's *signature* public, patterns (countersink,
  section) the caller's. Curve protocol, `as_analytic`, signature: 1.x.
- **D122** — the public surface, second half: measures and axis facts in
  `topo.geometry` (`segment_length`, `length_inside`, `chord_angle_deg`,
  `track_*`, `group_collinear_lines`, `axis_lines`, `items_inside`,
  `merge_intervals`). Not public on purpose: the DXF layer table (topo has
  roles, D123) and the tabs (D142). A lab may reach inside; a published
  package may not (`"*"` rule).
- **D123** — topo has **no file format**: geometry and roles, never layers.
  DXF, PDF, SVG are adapters at the edges; an exporter maps a role to a
  weight, colour, linetype and, in DXF, a layer (or two). `ezdxf` is not a
  dependency of topo. The pure-geometry entry (`load_geometry`,
  `load_segments`) is no format and stays.
- **D124** — one repo, one distribution, several packages: `g-topo` ships
  `topo/`, `topo_dxf/`, `topo_pdf/`; `g-topo[dxf]`, `[pdf]` bring the heavy
  dependencies. The boundary is checked mechanically (`gen_index` forbids
  `topo` from importing an adapter, `ezdxf`, `fitz`). `split` is topo's: it
  chooses parts on the model; each adapter writes one part.
- **D125** — the adapter contract, in public names: `Edge.of(segment, role,
  style)` (the node grid is topo's), no adapter base class, `segment_endpoints`
  public, `RoleRule`/`resolve_role`/`name_rules`/`DEFAULT_NODE_TOLERANCE` in
  `topo.model`; an adapter imports only `topo.model` and `topo.primitives`.
- **D126** — a neutral vocabulary: `EdgeStyle(linetype, linetype_desc, dash,
  color)` with `dash` the signed marks (`> 0` dash, `0` dot, `< 0` gap, `()`
  continuous, `None` unknown) and `color` an RGB; `RoleRule(color=)` takes RGB,
  `"#rrggbb"` or a base name, never an index. Role slugs keep `[a-z0-9_-]` for
  safety in any output.
- **D127** — an annotation has a role, the consumer's (`Text.role`), set by the
  same `role_rules` on its source group name only (a rule reading the style
  never matches a text). topo holds the slot and never reads it.
- **D128** — output by role. `RoleStyle` (RGB, linetype, dash, lineweight) is
  neutral in the model; `to_dxf(layers={role: name | fn(element)})` lets a
  role produce several layers; the palette is topo's
  (`DEFAULT_ROLE_STYLES`, `role_style()` with the caller's map on top); the
  global registry went (reopening D47) and `Annotation.group` with it.
- **D129** — the move: `topo_dxf/` and `topo_pdf/` beside `topo/`;
  `topo.split(result) -> list[Result]`; `load_dxf(skip_layers=SKIP_LAYERS)`;
  `gen_index` indexes every package and each adapter imports only topo's public
  names. `tests/unit/test_no_format.py` proves `topo` runs with no `ezdxf`.
- **D130** — 0.20.0 closed the split into three packages: README, API (§9
  `topo_dxf`, §10 `topo_pdf`), ARCHITECTURE and LLM speak of three packages,
  and every name in the three `__all__` has a card in API.md and a line in
  LLM.md (checked by script).
- **D131** — the non-contour criterion judges a **chain**, not an edge. A
  node of degree 2 is not a fork (`Graph.chains()`); the candidate is a chain
  between two distinct branching nodes, judged whole by D111's rule summed
  over its pieces (on the outer boundary for more than half its length) and
  kept or excluded whole. A chain closed on one node is a loop, never a
  candidate. Edge order no longer changes `heal()`: `TestEdgeOrder` tries the
  reversed order and 5 seeded shuffles on every golden.
- **D132** — the non-contour choices, each pinned by a minimal drawing in
  `test_non_contour_choices.py`: an interior chain (0 passes) is a chord; a
  bridge (2 passes) splits the parts; a chain on the outer boundary for half
  its length or less is a chord; sides that cross without a node are judged on
  the planar network and **reported** (`interior_crossings`), never repaired;
  a chain closed on one node is never a candidate (a hole sharing a vertex
  with the outer stays a hole — open). A default changes by a written decision.
- **D133** — the viewer stays outside the stable 1.0: `to_view_model`,
  `to_svg`, `save_svg` are out of `__all__` (importable, like `to_text`), so
  1.0 freezes neither their signatures nor their output.
- **D134** — joining nested regions: topo gives **facts** (which boundaries
  face each other, siblings included; the gap between two; the strip between
  them at a place and width, refused if it crosses a third boundary; which
  filled regions stay unconnected) and the construction; **policy** (how many,
  where, who joins whom) is the caller's. Names are geometric, never a trade's
  ("tab", "cut", "sheet"). Done in D142.
- **D135** — `SplineSeg` → `BSplineSeg`: `degree`, `control_points`, `knots`,
  `weights`, with `clamped`/`closed`/`periodic` derived; the fields that
  described how one format stored the curve left the model, and a spline given
  by fit points is converted on reading. Every spline is discretized by topo
  from its definition; the 400-point cap of `_refine_segment` is gone.
- **D136** — `contour_shape.kind` is a closed list of six: `circle`,
  `stadium`, `rectangle`, `ellipse`, `polygon`, `other` (`ShapeKind`). A kind
  needs a contour fully determined by the measures the record carries; a
  rounded rectangle or a D-hole is read from the signature by the caller. A
  contour's kind never changes in 1.x: only exact equivalence counts (an
  equal-axis ellipse is a circle), never an approximation.
- **D137** — `trash_entities` → `loose`: every curve attached to no contour.
  One list; each curve gets `cluster_ref` (the cluster whose outer encloses it
  entirely, else `None`); a consumer promotes any curve to any cluster
  (`promote`, now a method of `Result`, D173) out of `loose` into
  `cluster.detected`, never in both, never dropped. topo decides none.
- **D138** — `Annotation`/`Note`/`Dimension`/`Leader` are one type, `Text`
  (`position`, `text`, `pointer`, `target`, `measured_points`, `measure`,
  `measure_is_angle`, `references`, `rendered`, `source_kind`): "dimension" and
  "leader" are drafting readings. `dim_type` and `text_override` went; the
  adapter resolves `<>` on reading. The writer re-emits `rendered`, never a
  native DIMENSION.
- ~~D139~~ → D142: `bridge_parent_tabs`, tabs at caller-chosen points. Its
  geometric findings (the strip leaves perpendicular, read from the ring's
  orientation; a parent is split once on all its cuts; an island that cannot
  be joined is reported whole) live on in D142.
- **D140** — a consumer uses topo as it uses numpy: from a session opened in a
  consumer topo is **read-only** (a global hook). What is lacking becomes a
  line in the consumer's `TODO.md`, `## Richieste a topo`, triaged here as
  fact / piece of an algorithm / the caller's choice. Test for a new name: what
  varies between consumers must be an *argument*, never a new function.
  `topo.geometry.nearest_point` is the one fact that came out of it.
- **D141** — `simplify_points(points, tolerance, scale, closed=True,
  corner_turn_deg=35, arcs=True, spline_degree=3)` (experimental): a corner is
  a Douglas-Peucker vertex where the curve *turns* by ≥ `corner_turn_deg` over
  `scale` before and after; a stretch within `tolerance` of its chord is a
  line, of an arc through its two ends (and middle) an arc, else a spline
  (`approximate_bspline`, fewest control points within `tolerance`). The output
  is a head-to-tail chain; `tolerance` and `scale` are required lengths topo
  cannot guess. Also used by `refit_tessellations`.
- **D142** — `tools.tabs` → `topo.tools.strips` (experimental): D134's facts on
  primitives, not points — `facing_boundaries`, `gap`, `link` (refused with the
  reason if a side misses, crosses a third boundary or touches a placed
  strip), `unconnected_regions`, `open_boundaries`. A strip leaves
  perpendicular from the nearer boundary toward the other; the stretch it
  covers is the one holding its foot. Policy (`is_tab_island`, counts) is
  the caller's.
- **D143** — what 1.0 promises: (1) names and signatures of `topo`,
  `topo.geometry`, `topo_dxf` do not break, and the stable surface holds facts
  only; (2) the geometry, as invariants checked on every input — **faithful**
  (Hausdorff both ways ≤ tolerance, identical coefficients where heal did not
  intervene, on the DXF read back), **complete** (every input curve is a
  contour or in `loose`), **deterministic** (any edge order). Not promised:
  segment counts, a contour's start point or direction, ambiguous `island()`
  cases. A golden freezes a number, an invariant states what matters.
- **D144** — for 1.0 the reader's documents are English: `docs/API.md`,
  `docs/ARCHITECTURE.md` and the docstrings of public names (`__all__` of
  `topo`, `topo.geometry`, `topo_dxf`), short; internal code stays Italian.
  A topo exception to the general convention, checked rather than remembered.
- **D145** — circles and arcs discretize on one grid per circle, with no side
  cap: N sides with sagitta ≤ `tol` (at least 64, a multiple of 4), at angles
  k·2π/N from angle 0; an arc takes its exact ends plus the grid points
  between. Same curve, same polygon however the file cut it; the price is that
  rotating a part no longer rotates its vertices. `to_dxf` still writes native
  ARC/CIRCLE.
- **D146** — a piece the chosen outer contour uses is contour, never also a
  spur: `outer_face` removes from `spurs` every edge of its loop.
- **D147** ⏸ — suspended: an end lying on another edge's interior is not a free
  end, and a loop with a side on its host contour goes to `loose`. Federico
  judged `regr_04` worse; code kept on branch `d147-t-ends`, reverted on `main`
  (1.x, TODO).
- **D148** — feature freeze: topo is *1.0-ready* when `scripts/release_check.py`
  exits 0 (suite with no `expectedFailure`, `gen_index --check`,
  `audit_names --strict`, `audit_fixtures --strict`, English docstrings of public
  names) and every commit on `main` keeps it at 0. The gate list in `TODO.md`
  is closed and can only shrink; the rest is 1.x.
- **D149** — reopening D143 on one point: heal's per-entity deviation report is
  1.x (a new field, additive); the two-way fidelity test stays blocking.
- **D150** — `Result` loses `classified_entities` (a consumer's, process
  vocabulary), `all_arcs` (a duplicate of contours + `loose`) and
  `_open_shapes`. What a consumer classifies it writes into the cluster that
  contains it, else it stays in `loose`.
- **D151** — a loop the graph closed that makes no contour (no valid polygon,
  area under the minimum, a tiny lone circle) goes to `loose`, one `OpenCurve`
  per edge with its native segment — never dropped, never a `ClosedCurve`.
  The fix is in the step `loops_to_curves`, so a hand-made recipe gets it too.
- **D152** — reopening D56: a welded group spans at most `0.05` mm (its
  bounding-box diagonal), welded in canonical order. Fidelity is tested per
  reading (`tests/real/test_fidelity.py`): Hausdorff ≤ node tolerance for
  `heal()`, `max_gap` for `island()`; identical coefficients for curves the
  reading had no reason to touch. Drawings in `golden_islands/` and
  `golden_anchoring/` are read with `island()`, every other with `heal()`.
- **D153** — an ellipse discretizes on the parameter grid of the circle of
  radius `a` (its semi-major axis): the map to the ellipse never lengthens a
  vector, so the result is within `tol` by proof, a piece is a piece of the
  whole, and a reversed ellipse gives the same points backwards.
- **D154** — a curve of zero size is a point: `ArcSeg`, `EllipseSeg` and
  `CircleSeg` refuse radius/axis/ratio 0 (and NaN), `ArcSeg.from_chord` a null
  chord; the DXF adapter turns a null polyline bulge into a null `LineSeg` and
  reports a refused ARC/CIRCLE/ELLIPSE in `doc.warnings` instead of failing.
- **D155** — each closed gate item is one micro bump (the third digit; the
  second if a public name goes) and one push of `main`, until 1.0-ready.
- **D156** — `contour_shape` measures `other` on the primitives
  (`segment_reach`: exact projection of the curve, not of the inscribed
  polygon) at the minimum-area angle searched on the curve itself; correctness
  over speed until the Rust engine. The countersink's area was right: the Ø10
  inside the Ø30 is material by the parity rule (D89).
- ~~D157~~ → D161: gate G6 — the four doubts on D103 checked one by one on
  every island golden: a dropped loop had no boundary of its own at the
  reading's contact distance (`tolerance + max_gap`), the duplicates were real,
  and every dropped loop was in `loose`. The machinery left with the inners.
- **D158** — the 1.0 gate closes on invariants. Permanent: every promise of
  D143 is a test on every fixture, in both readings where it applies —
  faithful both ways, complete, every piece out once, deterministic (edge
  order), invariant under rigid motion and mirror. Temporary: the list of red
  invariants *was* the rest of the gate; after the sweep an item enters only
  if it turns an invariant red on a fixture in the repo.
- **D159** — the sweep: `tests/drawings.py` lists every tracked DXF with its
  reading (D152) and all invariant tests draw from it, so a new drawing gets
  every invariant; `translated`/`mirrored` exist on every primitive. A red
  case is registered per case (`KNOWN`, with its gate item): it runs, must
  fail, shows as a skip, and fails the test when it heals. Order dependence is
  a defect, not one of the "ambiguous cases".
- **D160** — the full suite runs serial in under ~3 minutes with every test
  capped (`pytest-timeout`, 60 s); no parallel workers, no test removed.
  Each reading is computed once and cached (`tests/readings.py`); checks are
  local and build each band once. A change that pushes the suite over is
  fixed in the same change. After a red run only `--lf` until green, then one
  full run before the commit.
- **D161** — `island()` reads **outer contours and nothing else**. Every other
  piece — closed or open, inside or outside, a whole nested island — goes to
  `loose` with `cluster_ref` of the island it touches or lies in; `island()`
  never builds an inner. A closed loop inside an outer has no meaning the
  geometry can decide (a cell, a logo letter, a hidden line): that is the
  consumer's, and it gets every piece untouched. `heal()` is untouched (a
  loop inside the outer of a flat part is a hole by construction).
- **D162** — a piece in `loose` that closes by itself (one closed segment, or
  a chain where every node has degree 2) comes out as one `ClosedCurve`; the
  rest stays one `OpenCurve` per edge. `contour_shape` reads them (and returns
  `None` on one that does not close); `anchor_texts` targets them. Which cycle
  to see at a branch is the consumer's.
- **D163** — a piece the border takes only in part leaves exactly its
  remainder in `loose`: `rim.face_segments` reports which stretch of which edge
  each run used, `rim.off_rim` cuts the edge there and keeps the pieces that
  leave the border by more than `band` (by their farthest point). `heal()`'s
  last-resort polygonize does the same (`off_faces`, `band = tolerance`).
- **D164** — a short `LineSeg` with a free end is a tip, not a double node: it is
  welded only if both its nodes are touched by another edge. Welding a tip only
  deletes geometry and moves a free end (against D143).
- **D165** — the area of a contour is exact, integrated on its segments
  (Green: shoelace for lines, chord plus circular segment for arcs, closed
  forms for ellipses, Gauss for splines; `integrals.py`: `ring_area`,
  `ring_centroid`). A gap closed within `tol` counts as its chord. The polygon
  area was off by up to `tol × perimeter` and changed with the tolerance.
- **D166** — no shapely type in topo's public surface. A contour exposes
  `segments`, exact `bbox`, `area`, `centroid`, `contains(p)` (the *closed*
  region, winding number on the primitives) and `points(tolerance)`; a caller
  who needs overlay or buffer calls `topo.to_shapely(item)`. A cluster
  converts even-odd (the parity of `area`, D89). The polygon a reading built
  survives only as a private cache (`_polygon`). `splits_contour`,
  `bridged_runs` and the facts of a ring run on the primitives. Guarded by
  `test_no_shapely_surface`.
- **D167** — topo's geometry is written ready for a Rust port, and the judge
  is the suite: a Rust function replaces its Python twin only when the same
  goldens, invariants and fidelity tests pass. New code is pure functions over
  plain data, typed results, explicit dispatch per primitive, no shapely or
  numpy in a signature. The primitive is the truth, discretization a view: a
  question about one curve is answered exactly on the primitive; between many
  curves, on polygons from the one grid.
- **D168** — G13 closed (0.23.0): `topo`, `topo.geometry`, `topo.steps`,
  `topo.model`, `topo_dxf` take and return no shapely type except
  `topo.to_shapely`. shapely is a dependency of topo, not a promise of it: a
  consumer that calls it declares it. The old → new table for the consumers
  (`c.polygon.area` → `c.area`, `.bounds` → `c.bbox`, `splits_polygon` →
  `splits_contour`, …) is in `MAP_ARCHIVE.md` / `67fda38:MAP.md`.
- **D169** — dependencies are replaceable details behind the API, replaced
  only on a measure. numpy is not a saving (shapely and ezdxf need it);
  shapely does the numerically hard part (noding, faces, index). What keeps
  them replaceable: no type of theirs in the surface (primitives store plain
  floats, `_plain`). After 1.0, piece by piece, each judged as D167 judges a
  port; a Rust core only for reading time or a host without Python.
- **D170** — on all five primitives: `mirrored(*, origin, angle)` about any
  line (the default is the x axis) and `scaled(factor, *, origin)` uniform with
  `factor > 0`; each returns the same type, exact. No non-uniform or general
  affine map (an arc would become an elliptical arc) and no matrix type:
  `s.mirrored().rotated().translated()` composes exactly.
- **D171** — `geometry.contour_union(contour, other)`: the rings of the union's
  boundary, largest first, shared border included. A pair of border pieces
  running opposite ways is interior and goes; the same way stays once; a piece
  on the border with no twin raises `ValueError`. Cuts are the crossings plus
  the other ring's segment ends; runs on one line or circle merge.
- **D172** — `promote` takes one curve or several: all checks run before
  anything moves (a curve not in `loose`, given twice, an empty list, a
  foreign cluster raise `ValueError`), and `item` is required for more than
  one curve — what they are together is the caller's, not invented.
- **D173** — `promote` is a method of `Result`, not a tool: it computes
  nothing, it keeps D137's promise (a curve is never in two places and never
  lost). `result.promote(curves, cluster, name, item=None)`.
- **D174** — reopening D148: the gate gets G14, one alignment of the API with
  how a mature library designs and evolves its API (scikit-learn: years at
  0.x, then a stable 1.0 with a written deprecation policy). The yardstick is
  not how Federico's own consumers call topo. "Then it is a 2.0" is not an
  answer to a design wish. Bounded: the rule, one pass over the names, tests.
- **D175** — the promise. **Public**: `__all__` of `topo`, `topo.geometry`,
  `topo_dxf` and the public submodules, each with a card in `docs/API.md`;
  the building blocks of an algorithm are not. **Versions**: patch fixes;
  minor adds and deprecates (old form stays with `FutureWarning` for two
  minors, then goes, with a test that fails if it is still there); no major
  planned. **Experimental** (`topo.experimental`): no promise. **Form**:
  data positional / options keyword-only; one way to do a thing; mutation
  declared; a method keeps an invariant, a function computes; typed stable
  returns; `ValueError`/`TypeError`; card and English docstring.
- **D176** — G14 step 2 (0.25.0), all breaks in one release: options keyword-only
  everywhere (containers use `KW_ONLY`); a mutating function returns `None`
  (`anchor_texts`, `inject`, `validate_result`); `split` copies each part's
  cluster; `set_schema` gone (`schema=` per call); `skip_layers` takes names
  or a function and `ignore_layers` went; `validate` → `validate_document`;
  `track_shape_type` and `split_to_files` removed; `topo/steps.py` and every
  non-stable name moved to `topo.experimental`.
- **D177** — `Text.target` and `Text.references` are the objects themselves
  (`repr=False, compare=False`), not string paths: a path is a position in
  one list at one moment, and `promote`, `split` or a reorder moved it.
  `resolve_target` is gone; `split` relinks each text to its part (an element
  of another part becomes `None`); `distance` is keyword-only.
- **D178** — G14 rule 1 held by a test: `tests/unit/test_surface_rules.py`
  declares the positional parameters of every public callable, methods
  included, in one table, all data; a new name or parameter fails until a
  person decides data (table) or option (after `*`), and a name that reads
  like an option (`tolerance`, `distance`, `min_*`, `include_*`) fails even if
  declared. Rule 8 (card + docstring, with G9) and the removal test remain.
- ~~D179~~ → D180: G6c — D100's union-of-faces network decided contacts by
  a GEOS grid cell fixed to the axes (a turned drawing moved the cell border);
  it was given contacts by distance, the union running on `UNION_GRID = 1e-6`.
  Folded into the noding of D180.
- **D180** — a contact is decided **once, on the true curves**, and gives one
  shared node (`noding.split_at_crossings`). Every pair of nearby edges is
  judged once (closed form for lines, arcs, circles; splines and ellipses on
  the node grid); a contact is a crossing, an end within `GRAPH_EPSILON` of
  the other curve, or two curves passing within it. Meetings of the *same
  pair* within `tolerance` are one contact (D101). Stops united by union-find
  give one node tuple for every edge the contact touches. Every type is cut,
  splines included. Node identity uses `GRAPH_EPSILON`, never `tolerance`
  (it percolates).
- **D181** — an angle-dependent contact is held by a micro-case built with
  `topo.load_segments` and read at eight angles, scrambled, far and mirrored
  (`TestScrambledMicro`), never by one more angle on whole drawings (each angle
  costs ~25 s of suite). A new case enters as a crop.
- **D182** — a gap is closed only at a meeting within reach of the end: a
  meeting that moves an endpoint further than the tolerance gives the gap a
  segment instead (parallel lines in the file became non-parallel in the last
  bit after a rotation and met 1e10 mm away). One rule for both readings; D189
  rewrote the gap step on it.
- **D183** — "within the tolerance" includes it, up to float noise: every step
  compares with `reach = tolerance + FLOAT_NOISE` (`1e-6` mm, above the noise a
  rigid motion adds and far below the node grid), so a gap drawn exactly as
  wide as the tolerance closes in every frame.
- **D184** — "same line, same circle" is judged on the true segments, never by
  a rounded key: parallel within `1e-7` and every end within `1e-3` mm of the
  other's line (arcs: centre and radius). A grid cell has a border and the
  canonical angle has a seam on the verticals. Groups are connected components
  of near pairs.
- **D185** — an end with two equally near partners (within `FLOAT_NOISE`)
  closes no gap, its partners still pair with others, and `heal()` lists those
  ends in a warning: what topology cannot decide is left to the drawing, and
  said (D111's stance). No coordinate rule gives the same partner in every
  frame of a symmetric figure.
- **D186** — reopening D152: short strokes are grouped by shared nodes; a
  group whose nodes lie within the diameter `0.05` is welded whole onto its
  smallest node, a wider group is a curve drawn with short strokes and none of
  it is welded. "Which strokes to weld" along a long chain has no geometric
  answer, so there is no order to depend on.
- **D187** — one foundation for every reading (Federico): a geometric rule is
  decided once, in one place, and `heal()`, `island()` and any recipe use it;
  a fix inside one reading is not a fix. `base.prepare` sets aside
  non-structural roles and decides the nodes (`decide_nodes`: ends within
  `GRAPH_EPSILON` are one node, a wider group is a dense curve and keeps its
  nodes); `normalize` runs the same clean-up in the same order.
- **D188** — `core/healing/` became `core/base/` (`prepare`, `cleanup`,
  `normalizer`, `gap_solver`, `hierarchy`) and `core/readings/` (`heal`,
  `island`, `heal_steps`, `islands`, `outer_scan`): a place named after one
  reading invites fixing one reading. Public names do not change.
- **D189** — one ingredient per job, for both readings: one `normalize` with
  no switches (tessellations refitted); one gap rule (each free end closes on
  the nearest point of the network within the tolerance — another free end, or
  where its own *continued* curve meets another edge — never a perpendicular
  bridge); one planar network (`cut_crossings` is the reading's meaning:
  island yes, heal no, D132); one non-contour test; contours from
  `outer_face.face_walks`/`face_loops` (CCW, simple rings); one `loose_curves`
  (D162). `LoopFinder`, `find_loops`, the polygonize fallback and the corner
  repair are gone. Reopens D57, D60, D110, D112; heal takes every bounded face
  and nests them, island groups by `max_gap` and keeps each outer face.
- **D190** — a non-finite number is refused by the primitive at birth
  (`ValueError`), like a curve of zero size (D154): no segment without a
  position can exist from any source. The DXF adapter drops the entity with a
  `doc.warnings` line, so a drawing with a NaN reads valid on the rest.
- **D191** — G6e closes on a finite list of decisions in the code, not on
  drawings: every place in `topo/core/` where a number decides (a threshold
  near float noise, a nearest or largest choice, a tie, a grid) needs a
  micro-case red before and green after, or one line on why it does not decide
  the reading. Same input, same reading; a rigid motion, same reading, except
  a measure on the tolerance itself within float noise, which heal reports.
### D192 — G6e group A: a meeting is decided in millimetres at float noise, on the measure whose error is linear ✅
`intersections.py` decided with fixed thresholds in the wrong units: parallel
lines at `|denom| < 1e-10` (mm²), "on the segment" at `t` within `1e-9` of
an end (a pure number), tangency on the discriminant (`< 1e-10`, mm⁴) and on
the half-chord `h < 1e-10`. Far from the origin a rigid motion moves a
coordinate by ~1e-10 mm, and each of these flipped: a segment inside another
on the same line got an invented meeting, a T on a short line and an arc
ending on a line lost theirs, and a tangent line or two tangent circles gave
0 or 2 points in 199 motions out of 200.

**Rule.** Every decision there is a distance in millimetres compared with
`FLOAT_NOISE` (1e-6 mm, D183): two lines are parallel when along the longer
segment their directions part by at most that; a point is on a segment or an
arc when it overshoots an end by at most that (as a parameter `/length`, as
an angle `/radius`); a line is tangent to a circle when the centre-to-line
distance is the radius within that, two circles when the centre distance is
the sum or the difference of the radii within that.

**Why on the radial gap, not on the half-chord.** The half-chord grows as the
square root of the radial gap: a noise of 1e-10 mm on r = 5 gives
h ≈ 3e-5 mm, so no threshold on `h` is stable. The radial gap carries the
coordinates' error linearly, so a threshold above that noise is.

**The rest of group A** (one line each in the inventory, no change;
argued, not covered by a test, except where a probe is named): `outer_scan.py` has no reading calling it; `outer_face.py:218`
is NOT closed: the probe written for it on 1 November found no faces at all
(not even at rest), so it proved nothing — it stays in the inventory;
`segments.py:46` is already in mm and only drops a vertex closer than 1e-9
to an end; `noding.py:404` is a shortcut of `merge_along_edges`, which joins
a stop within `node` of an end anyway; `noding.py:658` is never asked for
concentric arcs within `node`, because their ends give a T first;
`points.py:282` a circle from noise is the chord itself, and the tolerance
check after it rejects it exactly where `None` would.
Held by `tests/unit/core/test_intersections.py` (red before, ten motions
up to 3e6 mm).

### D193 — Reopening D191 on its exit: G6e leaves the 1.0 gate on a counted bar, not on "every drawing" ✅
D191 closed G6e on a finite list of places in `core/`. On 1 November the list
proved to be a list of candidates, not a proof: `segments.py:679`
(`segment_is_closed`) looked harmless on its own line and decided the
reading at its call site in the noding (commit "a short line or arc is a
stroke to node, never a loop"). "A rigid motion
never changes the reading, on any drawing" has no end by construction:
each new drawing can find another place.

**Rule.** G6e is in the 1.0 gate with this bar, and only this:
1. the inventory is closed (the 44 lines, each corrected with a red→green
   micro-case or one line on why it does not decide);
2. one re-pass of the lines classified harmless "because at the tolerance"
   that sit in a function called by `readings/`, `base/` or `topology/`:
   judged at the call site, not on the line;
3. the snapdraw sweep (121 drawings) run once. The gate passes when no
   drawing changes its reading under a rigid motion, except a measure on
   the tolerance itself within float noise, which heal reports (D183, D185).

What the sweep still finds after that is a known issue, listed, and fixed
in a 1.x patch.

**Why that is not churn.** G6e corrects readings that depend on the frame of
reference; it changes no public name or signature. D174/D175 forbid moving
the public surface after 1.0, not fixing a wrong reading, so a residue fixed
in 1.x breaks no consumer. Keeping "every drawing" as the bar would keep 1.0
out of reach for ever, which is the churn D174 exists to stop.

### D194 — G6e group B: on a planar network a node is its tuple, the graph does not re-judge it ✅
`noding.py:539-540` (inventory line 527-528): a node with no input endpoint
is the mean of its contact points, rounded to the node grid (D113). Alone
that is harmless: every piece at that node shares the one tuple. It decided
the reading because the graph built on the pieces of `split_at_crossings`
(`outer_face`, `face_loops`, `non_contour_pieces`) clustered the tuples
again at `GRAPH_EPSILON` with `cluster_points`, on the rounded coordinates.
The grid moves a distance by up to ~1.4e-3, so the 0.01 threshold became a
band that a rigid motion crosses. D180 already said the node is decided once
on the true curves "so the graph has nothing left to re-judge"; the graph did.

Micro-case (`test_noding.py::TestCrossingNodesUnderMotion`): three long
lines, the third cutting the first two near their crossing, a small
triangle with two crossing vertices 0.01074 apart. At rest `island()` reads
an outer of 3 sides and 5 loose; turned by 0.8127 rad the two rounded
tuples are 0.00985 apart, the graph fused them: 2 sides, the third loose.
Red on the old code at that motion, green at rest on both.

**Rule.** On a planar network the node is the piece's tuple: those three
build the graph with `epsilon` 0 for identity. `epsilon` keeps its other
two jobs: the sliver threshold of `_close_self_loop`, now a keyword
`sliver` of `build_node_graph` (default `epsilon`, so every other caller is
unchanged), and the band of D100's union in `outer_face`.

**Options weighed (Federico chose this one after seeing them drawn).** The
mean not rounded: one line, but tuples off the one grid (against D113), and
endpoint nodes keep the same amplification. Measured on 3001 small random
networks turned 31 ways, graph node count: 428 unstable today, 399 with the
exact mean, 2 with the graph not re-judging (simulated by patching; those 2
already differ in the number of pieces, another cause, inventory). Part of
`noding.py:524` (`min(ends)`, group D) reached the reading through the same
re-judging; that line stays open, its choice still moves the tuple.

**Gate.** G6e is in the 1.0 gate on D193's bar. No public name or signature
changes (`build_node_graph` is internal; `outer_face`/`face_loops` are
experimental and keep their parameters). Suite 2975 passed, goldens
unchanged, 3:44 (the level since D189, still over budget, open there).

### D195 — G6e group B: congruent copies are equal within the noise, not within a grid cell ✅

Reopening D166, only its means. D166's rule stays: clusters from the largest
exact outer area, and at equal area by the bbox corner `(xmin, ymin)`. What
D166 used for "equal" was `round(area, 6)`: two copies were equal only if
their areas fell into the same 1e-6 mm² cell. With the area half a cell from
a boundary (two 10 × 1.00000005 rectangles, area 10.0000005) the last bits,
which a translation changes, put the two copies in two cells, and the order
came from the noise: the copy on the right first at 3 of 24 translations.
Far from the origin the exact area of a copy moves by up to 2.5e-8 mm²
(shoelace on large coordinates), so no fixed cell can hold it.

**Rule** (`sort_clusters`): two areas are equal when they differ by at most
`FLOAT_NOISE` times the perimeter — the area a boundary sweeps when every
point moves by the noise (D183) — and two `xmin` when they differ by at most
`FLOAT_NOISE` (copies stacked one above the other: red at one translation
before). Equality chains along the sorted values, so it does not depend on
the input order.

`_build_tree`'s `round(area, 6)` (hierarchy.py, same family) is kept: the
order there only decides which contour holds which, and nested contours
differ in area far beyond 1e-6 (on the tracked drawings: 344 pairs within
1e-5, none nested). Held by `TestTreeOrderUnderMotion`, which does not cover
the order of the inners between themselves (not a contract).

**Held by:** `tests/unit/core/test_hierarchy_builder.py::TestCopiesOrderUnderMotion`
(red on the old code at 4 translations).

**Gate.** G6e, in the 1.0 gate. No public name or signature changes; the
documented order of `Result.clusters` is the same rule, now kept under motion.

### D196 — G6e stays line by line: no shared "noise" module, no lint on comparisons ✅
Federico, 2 November, asked whether the inventory should give way to one
place every numeric decision goes through, with a suite check forbidding raw
comparisons in `core/`. Measured before deciding, on the work already done.

Of the ten real corrections so far, five were structural — decide once and
share (refit joints, `_is_loop`, D194), or drop a rounding that served no
purpose (`rim.py:80`, `axis.py:179`) — and a comparison helper would not
have touched them. The other five each needed their own measure: drift along
the longer segment, overshoot over the length or the radius, the radial gap,
the area over the perimeter, the angle the noise subtends on `scale`. What
they share is `abs(x) <= FLOAT_NOISE`; the work was choosing `x`, and a
module cannot choose it.

A pattern check (`1e-N` literals, `round(`, `== 0`, signs against 0) hits 101
lines in 24 files of `core/`, about 25 of the 44 inventory lines: some 75
false alarms to allow-list, while it misses the whole tie group (`min`,
`max`, `sorted`) and `segments.py:679`, which hid behind a named constant
and was the worst one found.

So G6e goes on as D191/D193 say. Snap rounding and exact predicates were
also weighed and do not answer G6e: a grid fixed to the axes moves under a
rotation (the defect D180 removed), and an exact predicate answers exactly
on the rotated doubles, where a tie at rest is no tie any more.

### D197 — G6e group D: a circle joins the nearest concentric group, not the first one made ✅
`shape.py:316, 326` (`concentric_groups`, public since D91; no reading of
topo calls it, snapdraw and snapbend do). The inventory said "used by
`island`": it is not.

What it decided: circles sorted by diameter, then by centre `(x, y)`; each
one joined the *first* group made whose reference centre lay within
`tolerance`. Diameter order is a fact of the geometry; at equal diameter the
order came from `(x, y)`, which a rotation changes. Two equal holes 0.15
apart and a larger circle 0.06 from one and 0.09 from the other: the large
one went with the hole of smaller x, so a half turn moved it to the other
(4 motions of 9). Two equal circles within `tolerance` gave the group the
reference of the smaller x; the groups' final order on `(x, y)` broke on an
ulp for holes stacked at one x.

**Rule.** Among the groups within `tolerance` a circle joins the nearest
(centre distance, invariant); equidistant within `FLOAT_NOISE`, the group
made first. Diameters equal within `FLOAT_NOISE` keep the order of `items`,
which a motion does not change, so the reference of a group is the first
circle given. Groups are ordered by `x`, then `y`, equal within
`FLOAT_NOISE` as D195. The run-splitting helper of D195 moved from
`base/hierarchy.py` to `geometry/measure.py` (`noise_runs`), one copy for
both.

**Held by** `tests/unit/core/test_concentric.py::TestConcentricGroupsUnderMotion`
(red on the old code: 4 of 9 motions on each partition case, 2 of 4
translations on the order).

**Gate.** G6e, in the 1.0 gate. No name or signature changes; the result
differs only where the old one depended on the frame. A consumer that relied
on "first group made" with two candidate groups was reading the frame.

### D198 — G6e group D: a node with several input endpoints is their mean, not the smallest ✅
`noding.py:524` in the inventory (`min(ends[root])` in `_Contacts.nodes`, at
:536 before this change). A node of `split_at_crossings` is a union-find
group of stops; when the group holds endpoints of the input, the node was
the smallest of them in `(x, y)`. With one distinct endpoint that is the
endpoint itself. With several — an end 0.009 from a curve and within `node`
of that curve's own end, or a chain of such — the smallest in `(x, y)` is
a fact of the frame: a half turn picked the other end, 0.0127 away.
Reached by `island()` on 5 of the test drawings (anch_03 and its copies,
regr_01, regr_02; groups up to 0.11 wide), never by `heal()`.

**Rule.** One distinct endpoint: the node is that endpoint, unchanged.
Several: their mean (`math.fsum`, independent of order), rounded to the node
grid like a contact node (D113, D194). Between two ends of two curves no
geometry says which one is the vertex; the mean is the one choice that a
motion and a reordering of the input (D160) both leave alone. Options
weighed: the end nearest the mean is a tie with two ends; the end of the
first edge given depends on input order.

**Held by** `tests/unit/core/test_noding.py::TestEndNodeUnderMotion` (red on
the old code at a half and a quarter turn, the node 0.0127 from the moved
one; green within one grid cell). Suite 3012 passed, goldens unchanged, 3:47.

**Gate.** G6e, in the 1.0 gate. No public name or signature changes.

### D199 — G6e, last line: D100's union stays; its re-noding on discretizations is a known defect for 1.x ✅
`outer_face._network`, the line added to the inventory with `UNION_GRID`
(D195's session): the fallback of D100 builds its network with the ends on
the rounded tuples (`_on_nodes`, up to 7e-4 off) and lets
`unary_union` node the discretizations again (sagitta up to 0.01). A contact
the noding on the true curves excluded (D180) can come back there. Built
case: a bite of an arc with a sagitta just under 0.01, a triangle's corner
0.0100003 from the true arc; at the origin the corner's tuple passes the
chord and the union welds the two faces (46.2 mm² instead of 44.2); turned
by 0.7 the angular grid (D145) moves the chord and it does not.

**Measured.** Removing the fallback (only the walk on the planar graph; the
faces of `face_walks` united as polygons give the same numbers):
31 island drawings, 0 of 779 calls change, `island()` 21% faster; the 121
drawings of the snapdraw sweep, 39 of 3074 calls change in 10 drawings, and
one reading changes, wrongly: three copies of a small figure lose a 4.6 mm²
lobe to `loose` (Federico looked: today's reading is right). The cause is
not the union: at a node a spline leaves at about −146° and swings past a
0.54 mm line leaving at −90°; `_leaving_angle` reads directions at
`DIRECTION_SAMPLE` (3 mm, or half the edge) where the spline already points
at −67.5°, so the order of the branches round the node is inverted, the
walk goes round the lobe twice and calls it a spur. The union corrects the
walk there — the same family as the tangent arcs D100 was born on.
The defect itself is reached on the 121: the union adds 40 nodes between
curves more than 0.01 apart, in 6 drawings; none changes a reading (in 5
`outer_face` is identical with or without the union, in the sixth only
nested pieces change, which go to `loose` anyway). On the 31: 0 such nodes.

**Rule.** The union stays. The line is closed for the gate as known and not
deciding a reading (D193 point 1, the D158 form): it decides only on the
built case. Removing the union (and with it `rim.py`, `UNION_GRID`,
`_on_nodes`) first needs the walk to order the branches at a node by how
they actually leave it, then the same two measures again: 1.x, TODO.
Options weighed: remove it now (one wrong reading on a real drawing in
exchange for a red built case — moving a defect, not fixing one); fix
`_leaving_angle` now (a new front inside the gate, touching the walk of
both readings).

**Held by** `tests/unit/core/test_outer_face.py::TestChordContactUnderMotion`,
a `known_defect`: skips while the reading changes with the motion (value at
the origin checked: 46.2, the faces welded), fails once it does not.
Probes: `_debug/2026-10-31_topo_G6e-inventario/attrezzi/probe_network_road1*.py`,
`probe_union_contacts_121.py`, `probe_network_45*.py`.

**Gate.** G6e, in the 1.0 gate; it closes the inventory (D193 point 1). No
public name or signature changes.

### D200 — G6e, D193 point 2: two islands are apart on the true curves, and a point says who hosts whom ✅
`islands.py:66` judged `dwithin(max_gap)` on the discretizations, whose
error (up to DEFAULT_TOLERANCE per curve) turns with the drawing (D145): a
square 0.496 from a circle, `max_gap` 0.5, was one island at the origin and
two half a grid step away. Now the discretizations decide only outside a
band of 2·DEFAULT_TOLERANCE round the threshold; inside it the distance is
refined on the primitives (`strips.refine_gap`, the loop of `gap` taken out
so both use it). `island.py:146` asked the host's polygon grown by
`tolerance` to contain the whole piece; a chord bulging into a concave bite
let it cover a 0.003 circle 0.051 from the true arc at some motions. Since
two islands are now farther apart than the threshold on the true curves, a
piece lies inside a host iff one point of it does: `ring_contains` on the
primitives, one endpoint of the piece. Measured: 0 readings change on the 31
and on the 121; `island()` ~3% (D200 pairs) and ~10% (nesting) slower on the
121; suite 3:49 → 4:15. Held by `test_islands.py::TestGapOnTrueCurvesUnderMotion`
and `test_island.py::TestHostOfATinyPieceUnderMotion` (red before, green
after). Gate: G6e, in the 1.0 gate; no public name changes.

### D201 — G6e closed for 1.0 on D193's bar; three residues of the sweep go to 1.x ✅
D193's three points: the inventory is closed (last line D199); the re-pass
at the call sites corrected `islands.py:66` and `island.py:146` (D200); the
snapdraw sweep (`scripts/21_sweep_invariants.py`, the 121 drawings of
31 October) ran once on `b10aa2b`. `island()` keeps every invariant on all
121. `heal()` changes its reading under a motion on 2 drawings, down from
32 (sweep indices 8 and 62: one small face 1 mm wide becomes an outer instead
of an inner; 60 → 56 inners). One drawing (index 79) went past the 300 s
limit; on 31 October it took 133 s. Found during the re-pass and not
corrected: in `heal()` a hole tangent from inside to the outer can read as
two clusters depending on the motion (`hierarchy.py:70`, `contains` between
discretized polygons; built case in
`_debug/2026-10-31_topo_G6e-inventario/attrezzi/case_hier70.py`). By D193
these are known issues, fixed in a 1.x patch; G6e leaves the gate.
