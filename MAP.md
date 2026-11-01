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
### D130 — point 0 closed: 0.20.0, the docs speak of three packages ✅
Step 6 of D123 (TODO road to 1.0, point 0), Federico, 18 October. The
breaking minor that D125 announced: **0.20.0**. The docs follow D129:
README/README_IT install with `[dxf]`, a table of the three packages, the
multi-part example as `topo.split` + a writer per part; `docs/API.md` keeps
§1–§8 for `topo` (§1 is now "geometry in", the `split` card rewritten, a
`build_metadata` card) and gains §9 `topo_dxf` (every DXF card moved there,
with `skip_layers`, `exclude_types` and the default layers) and §10
`topo_pdf`; `docs/LLM.md` gets an adapters table and a hard rule naming the
removed `topo.*` names; `docs/ARCHITECTURE.md` draws three packages and states
the boundary rule as `gen_index` checks it. Every name in the three
`__all__` is in API.md and LLM.md (checked by script). The contract and the
current status at the top of this file, frozen at forge 0.9.0, are rewritten.
Suite: 1318 passed, only `anch_02`/`anch_06` red.

### D131 — the non-contour criterion judges a chain, not an edge; edge order no longer changes `heal()` ✅
Road to 1.0, point 4 (TODO), Federico, 18 October. Closes the defect D111
left open (`KNOWN_ORDER_DEPENDENT`).

**The defect.** On `linee_di_piegatura_interne` three bends run from one
vertex of a quadrilateral to the opposite one, through two points that lie
on the top and bottom sides. `heal()`'s graph never nodes a T-junction, so
those two points have degree 2 there. D111's criterion 1 asked of each
*edge* that both its ends be branching nodes. No piece of the chain
qualified, so the chain stayed in the graph. The graph is then a theta (two
nodes joined by three paths), and `LoopFinder` takes the first loop its
greedy walk closes: in file order that was the outer, reversed it was not,
and `polygonize` gave 4 faces.

**The criterion now.** A node of degree 2 is not a fork: the edges through
it are one arc of the graph, cut into pieces. `Graph.chains()` returns the
maximal chains (edges in a row through degree-2 nodes, with the two nodes
they end on). The candidate is the chain whose two ends are *distinct*
branching nodes. It is judged whole, by D111's rule summed over its pieces
(on the boundary of the outer face for more than half its length), and kept
or excluded whole: a degree-2 path is either all in a loop or in none, so
judging its pieces apart could only leave stubs. A chain closed on one node
is already a loop, never a chord between two points of a boundary, so it is
never a candidate (a hole touching the outer at one node stays a hole). A
single edge between two branching nodes is a chain of one: the same as
before.

**The ambiguity this extends, on purpose.** Topology alone says only that
the outer face is empty. A line between two closed faces is either contour
(material on one side) or chord (material on both), and D111 chose chord
for whatever does not border the outer face. That now reaches chains too:
a closed face that touches the outer face only across a contour edge, and
the rest of the part through a chain, now reads as material, and the chain
goes to the trash, recoverable.

**Effect.** Old vs new `heal()` on the 782 DXF under topo/ and snapbend/
`tests/`: 85 change. `linee_di_piegatura_interne` is now right in every
order. All the others are drawing sheets read with `heal()`, where its
output means nothing (non-negotiable 5); Federico judged them by eye
(`tests/lab/chain_candidates/`, not in git). No golden changes; `island()`
uses the detector only to sort its leftovers, and its goldens and
invariants are unchanged. snapbend green; snapdraw's red `regr_03`/`regr_05`
were red before.

**Tests.** `TestEdgeOrder` now tries the reversed order plus 5 shuffles with
fixed seeds (`SHUFFLES`), every golden; `KNOWN_ORDER_DEPENDENT` is empty.
`TestChainCandidates` and `TestGraphChains` in `test_non_contour_edges.py`.
`main` → **0.20.1** (`heal()` output changes, no signature change).

### D132 — the non-contour choices, each pinned by an edge case; crossing sides are reported, not repaired
Federico, 18 October, after D131 (a page drawing each choice). The criterion
has facts (the chain is the unit; a candidate ends on two distinct branching
nodes; the passes of the outer face are a count) and choices. Each choice now
has its minimal drawing in `tests/unit/core/test_non_contour_choices.py`,
which states the default. A default changes there, on purpose and by a
written decision.

- **A. An interior chain (0 passes) is a chord.** Rectangle + inner square +
  4 corner-to-corner diagonals reads as one solid part, 8 lines in the trash.
  On sheet metal those diagonals cannot be bends (a flat like that does not
  fold); the only sensible reading is stiffening creases, so solid is right
  there. Federico wants "chord, and optionally hole" for readings where a
  closed interior face is empty (a future mesh reading, a consumer that
  knows from another view). The rule for which faces the option empties is
  not decided: open in TODO.
- **B. A bridge (2 passes) splits the parts:** two parts and the joining-edge
  warning, unchanged. A consumer that wants them as one (smoother building
  ribs by hand) does so itself.
- **C. A chain on the outer boundary for half its length or less is a chord.**
  A chord grazing the outline goes to the trash; a bend line drawn a little
  long or short ends there too (spur or free end), and `detect_flat` reads it
  with its own bending tolerance, not heal's. Unchanged.
- **D. Sides that cross without a node are judged on the planar network and
  reported.** The planar copy is only how the detector counts passes; it never
  changes the delivered geometry. A drawing whose contour sides cross is
  broken, and the caller must hear it: `heal()` now warns with the points and
  what to fix (`interior_crossings` in `topology/noding.py`: a cut interior to
  two edges; a T contact does not count). No repair by default: a family of
  bad drawings gets its own algorithm, as an explicit step.
- **E. A chain closed on one node is never a candidate**, so a hole sharing a
  vertex with the outer stays a hole today. Federico's view is that it is
  trash; no golden of heal and no snapbend DXF has one (counted), so it stays
  open in TODO until a real drawing shows it.

The new warning appears on no heal golden and no snapbend test DXF. Suite
1333 passed; snapbend green; snapdraw's `regr_03`/`regr_05` red as before.

### D133 — the viewer stays outside the 1.0 stable API
Road to 1.0, point 5, Federico, 18 October: the viewer can stay out for now.
`to_view_model`, `to_svg` and `save_svg` leave `__all__` and stay importable
as `topo.<name>`, the same treatment as `to_text` (D84) and the rotations.
They are known to need a rewrite (TODO, "Rifare il viewer": it discretizes
arcs and circles, and on a sheet of views it outweighs the source DXF), so
1.0 must not freeze their signatures or output. API.md keeps their cards
under a note; LLM.md, ARCHITECTURE.md and the READMEs mark them. Callers
(smoother, snapbend's tests) use `topo.to_svg`, which still works.

### D134 — joining nested regions: topo gives the facts and the construction, the caller the policy; siblings join too; geometric names only (done in D142)
Federico, 19 October, correcting Claude (who had proposed moving the code
out of topo, against D39). Supersedes the "known unresolved limit" of D40.

**The defect.** `bridge_nested_tabs` joins every filled region of even
depth ≥ 2 to its direct parent, `tab_count` strips equally spaced around its
centroid. Two sibling regions side by side in the same empty region are each
joined to the parent, unaware of each other: the strip aimed at the parent
runs into the sibling, or the long way round when the sibling is 10 units
away. Seen in smoother's output.

**The split (D39 restated).** Constructing a strip of width `w` between two
boundaries at a given place is deterministic geometry: topo. How many, where,
and which region joins which is the caller's. topo gives, as facts:

1. **Which boundaries face each other**: for every empty region, its own
   boundary plus the boundaries of the filled regions directly inside it.
   Two regions inside different empty regions (cousins) never face each
   other: material lies between them, a strip would cross a third boundary.
   They are excluded by construction, not by a rule.
2. **The gap between two facing boundaries**: minimum distance and the pair
   of closest points.
3. **The strip**: between any two facing boundaries (parent–child *and*
   sibling–sibling) at a given place and width; refused if it crosses a
   third boundary.
4. **Which filled regions are not connected** to the outermost filled region,
   through any chain of strips, given a set of strips. A caller placing
   strips by hand learns what is still unconnected.

**Policy stays with the caller.** "Join each region to its nearest
neighbour" alone fails: two discs 10 apart in a window, 100 from its edge,
join each other and neither reaches the edge. Growing from the parent,
joining each time the nearest region to something already connected, gives
the nearest-neighbour behaviour and connects everything. That is one policy
among several (count, mid-point snaps, by hand), so it lives in the caller
(smoother today); fact 4 is how the caller checks it. No separate project
for it: one caller places strips today; when a second does, what both
rebuild gets promoted.

**Names are geometry only.** topo is geometry for the real world, never the
vocabulary of one trade. No manufacturing words in names, docstrings or
docs: not "tab", "bridge" in the cutting sense, "fall out", "cut", "laser",
"sheet". The current names (`tools/tabs.py`, `bridge_tabs`,
`bridge_nested_tabs`, `tab_width`, `tab_count`) are renamed when rewritten;
experimental and outside `__all__`, so a clean break (smoother updated in
the same change).

**Not blocking 1.0**: all of it is new names, added in a 1.x.

### D135 — `SplineSeg` becomes `BSplineSeg`, and carries geometry only ✅
Federico, 19 October. Reopens D121 on the form of the name only (D121 said
`BSpline`).

Every spline topo holds is a B-spline: degree, control points, knots, and
weights when it is rational. The same type receives a free-form profile from
any source: cubic Béziers are B-splines with clamped knots, a conic exported
as a spline needs weights. So the name says the representation: `BSplineSeg`,
keeping the family `LineSeg`/`ArcSeg`/`CircleSeg`/`EllipseSeg` (the user
writes one pattern, not five).

Fields: `degree`, `control_points`, `knots`, `weights` (optional), plus what
follows from them (closed, periodic). Today half the fields describe how one
file format stored the curve (raw flags, three tolerances, 3D fit points and
tangents, sampled points); topo has no format (D123), so they leave the
model. Whatever an adapter needs to keep about its source stays in the
adapter. Fidelity (D121): an untouched spline comes out with the same control
points, knots and weights. To verify in the adapter: a source spline given by
fit points only is turned into control points on reading.

Clean break before 1.0 (49 files in topo and its adapters, 3 lines in
smoother, nothing in snapbend/snapdraw/snapfence).

**Done (19 October).** Fields `degree`, `control_points`, `knots`,
`weights`; `clamped`, `closed` (start and end within `DEFAULT_TOLERANCE`) and
`periodic` (closed and not clamped) are properties, `endpoints()` evaluates
the curve at the ends of its domain (for an unclamped spline they are not
the first and last control point; `_evaluate` no longer returns them outside
the domain either). The DXF reader keeps control points, knots and weights
as written; a SPLINE given by fit points only, or without knots, gets them
from the CAD's own construction (ezdxf `construction_tool`). The writer sets
only the closed/periodic/rational flags. `load_geometry` and
`_fit_spline` lose `fit_points`/`closed`.

The sampled points the reader used to keep (`approx_points`, ezdxf's
flattening) are gone, so every spline is now discretized by topo from its
definition. That exposed a bug in `_refine_segment`: a cap of 400 points per
curve left the rest of the curve at coarse chords, out of tolerance, so a
finer tolerance gave a *worse* area (a spline hole: 12478.4 at 0.001 against
12482.8 true). The cap is gone; `max_depth` still bounds a noisy stretch.
At 0.01 both samplings are within tolerance (max deviation 0.00988 topo,
0.00999 ezdxf), so four expected areas moved inside the error the tolerance
allows, and were updated value by value, not regenerated:
`quadro_fori_spline` (65537.43 → 65537.55, true 65536.11; its hole 12481.47
→ 12481.35), `fa_che_non_mi_incazzi__001`/`sviluppo_multiparte__004`
(38791.157 → 38791.054, true 38791.035), and the two island regressions
(16.247 → 16.287, true 16.289; 1011.27 → 1011.35, true 1011.36).

Cost: without the reader's points, `heal()` on the drawings with splines
went from 17.8 s to 63.8 s — it asks for the same spline ~4 times at the
same tolerance, and de Boor ran on tuples built per step. A per-tolerance
cache inside the spline (not a field: a spline is never changed in place)
and de Boor on plain coordinate lists bring it to 19.5 s.

`main` → **0.21.0** (D135 and D136, one bump: public names and
`contour_shape` output changed).

### D136 — `contour_shape.kind` is a closed list of six, and a contour's kind never changes in 1.x ✅
Federico, 19 October: "the choice that gives fewer problems tomorrow".

**The criterion for a kind**: the contour is fully determined by the measures
the record already carries (centre, length, width, angle). Circle, stadium,
rectangle pass, and so does the **ellipse** (centre, two axes, angle).
`polygon` and `other` are the two catch-alls (their measures are the minimum
rotated rectangle, not a determination). A rounded rectangle (needs a corner
radius), an arc-shaped slot, a D-shaped hole, a regular hexagon (a `polygon`,
D96) fail the criterion: they are read from the contour's signature (D121,
1.x) by the caller.

The ellipse is decided now because adding it later would reclassify existing
`other` contours: every circle seen in an isometric view is an ellipse.

**A contour's kind is stable, not only the list of names.** The rules read
the primitives as they are: a circle made of four Béziers stays `other` even
after `as_analytic` exists (1.x); a caller who wants recognition asks for it
in its own step. Only exact equivalence counts: an ellipse with equal axes is
a `circle`, arcs on one circle merged by `merge_runs` are a circle; an
approximation within a tolerance is not. The default tolerances (1 %, 1°)
are part of the contract.

`kind` becomes `ShapeKind(str, Enum)` (comparisons with `"circle"` keep
working); an `ellipse()` builder joins the others for the round trip (D96);
one test fixes the set of kinds and the edge cases (square, equal-axis
ellipse, spline circle, rounded rectangle, a hole in an isometric view).

**Done** the same day: `TestShapeKindStabile` in `test_shape.py`, the
`ellipse()` round trip in `test_build.py`; `to_text` writes an ellipse on one
line like a rectangle or a stadium. No golden of topo, snapbend or snapdraw
changed (no fixture has a closed ellipse today). `ShapeKind` overrides
`__str__`/`__format__` rather than using `StrEnum`, which needs Python 3.11
while the package declares 3.10. Failing before and after, untouched: the two
`to_text` budgets (`anch_02`, `anch_06`) and snapdraw's frame bbox on
`regr_03`/`regr_05`.

### D137 — `trash_entities` becomes `loose`: every curve knows which cluster contains it, and any curve can be promoted ✅
Federico, 19 October. The DXF layer is not an argument (a format's concern,
D123); the name is.

**What is in it.** Every curve that is not a contour of any cluster: chains
that close nothing (D131), open curves, closed curves with a non-structural
role, curves the caller had already labelled. Some of it is stray geometry,
much of it is not (lines inside a part a consumer reads as folds or ribs, a
guide line a reader uses to locate a feature). "Trash" judged them; `loose`
only says they are attached to no contour.

**One list, one geometric fact per curve.** `result.loose` stays a single
list (no split per cluster): what a curve *is* is the consumer's, and a
consumer promotes it. topo adds the fact consumers recompute by hand today
(snapbend finds the containing cluster by midpoint, twice): `cluster_ref`,
the index of the cluster whose outer contour contains the curve entirely,
boundary and holes included (a line from edge to edge, a centre cross inside
a hole), `None` otherwise. Same name and convention as annotations (`anchor`)
and `island()` (D99), which already set it.

**Promotion is not bound by position.** A curve outside every part can still
belong to one: a guide line next to a part that points at a feature. A
consumer attaches any loose curve to any cluster, through one public
operation that moves it out of `loose` into `cluster.detected` (D44, D90):
never in both places (snapbend's comment: the same line written twice), never
dropped (non-negotiable 7). No default: topo never decides which loose curves
matter.

`split` hands each curve to the cluster of its `cluster_ref` (one rule
instead of its own probe point); a promoted curve travels with its cluster.
The type is declared (`List[OpenCurve | ClosedCurve]`, not `List[Any]`).
`Result.classified_entities` (D88), which snapbend fills next to this, is
looked at in the review of `Result`/`Cluster` fields, not here.

**Done (19 October).** `Result.loose: List[OpenCurve | ClosedCurve]`;
`ClosedCurve` gains `cluster_ref` next to `OpenCurve`'s. The fact is
`geometry.regions.enclosing` (smallest outer polygon whose exterior covers
the whole trace, buffered by the node tolerance), written by
`assign_cluster_refs` in `heal()` on every loose curve. `island()` keeps D99
for what it already attaches (the island a curve touches) and gives the
curves that touch nothing the island that contains them, if any: a detached
axis inside a view, a caller-marked frame stays `None`. `topo.promote(result,
curve, cluster, name, item=None)` is public; it raises if the curve is not in
`loose` or the cluster is not in the result. `split` hands each curve to the
part of its `cluster_ref` (nearest part only for `None`, as before) and gives
each part *copies* whose `cluster_ref` refers to that part (`0` or `None`);
the same for annotations, which before kept their index in the whole result
and pointed past the end of a one-cluster part.

Found on the way: `rotate_result` rotated only open loose curves, a closed
one (a marked circle) kept its old position; it now goes through
`_rotate_contour` like any closed contour.

What did not change: the DXF adapter's default layer for role `unknown` is
still `Trash` (`TRASH_LAYER`, `SKIP_LAYERS`) — a layer name is the format's
(D123), and a file written before reads back the same. `include_trash` is
`include_loose` in `to_dxf`/`to_view_model`/`to_svg`, and the view model's
key is `loose`.

Consumers: snapbend's `detect_flat` reads `cluster_ref` instead of probing
midpoints (bend lines, open and closed engravings) and moves bend lines with
`promote` instead of filtering `loose` by id; its 435 tests and goldens are
unchanged. snapdraw, snapfence, cogo: rename only. No golden of topo changed.
`main` stays **0.21.0**: not released yet, D137 joins D135 and D136 in it.

### D138 — `Annotation`, `Note`, `Dimension`, `Leader` become one type, `Text` ✅
Federico, 19 October, reopening the naming of D20 (the typed model stays).
"Annotation" is the vocabulary of whoever draws on top of a drawing; a quote
and a leader are drafting notation. Neither is topo's: the test of
non-negotiable 1 fails for `Dimension` and `Leader` — a PDF gives two lines,
two arrows and a string, and calling that a dimension is a reading, a
consumer's. They exist in topo only because a DXF has DIMENSION and LEADER
entities.

What stays when the drafting names go is geometry: a string at a point
(today's `Note`); a string with a polyline whose tip lands on something
(`Leader`: `vertices`, `target`); a string with the points it measures
between (`Dimension`: `measured_points`, `references`). One type, `Text`,
with those parts optional: `pointer` (tip first) and `target`,
`measured_points` and `references`, `rendered` (the image the source draws
around the string, which the DXF writer already re-emits instead of a native
DIMENSION/LEADER). Where it came from stays a fact of the source,
`source_kind`, so the writer can rebuild it faithfully. Saying "this is a
dimension" is a consumer's, even when the format says it already.

Consequences on public names (frozen for 1.0, so before it):
`result.annotations`/`doc.annotations` → `texts`, `anchor_annotations` →
`anchor_texts`, `include_annotations` → `include_texts`, `display_text` →
the text itself. The DXF adapter's default layer `Annotation` stays, as
`Trash` stayed in D137: a layer name is the format's (D123).
Consumers: snapdraw (reads `Dimension`, `dim_type`, `measured_value`,
`topo.Note`), to_text.

Decided with Federico the same day, on the three fields of `Dimension`
that are drafting words:
- **`dim_type` goes.** "Diameter" is a reading of the points: two
  `measured_points` opposite on one circle (a Ø12 on a hole; a linear
  dimension tangent to a circle at its two extremes is its diameter too, and
  reads as one). What geometry cannot say is whether the number is a length
  or an angle — a consumer computing a scale must leave angles out — so that
  one fact stays: `measure_is_angle: bool`.
- **`measured_value` → `measure`**: the number the source says it measured,
  a fact of the source like a text height; `None` when the source says none
  (a PDF).
- **`text_override` goes**: its `<>` is DXF syntax ("<> H7" = the measure,
  then H7). The adapter resolves it on reading and `text` is what is shown
  ("12 H7"); the writer re-emits `rendered`, never a native DIMENSION, so
  `<>` had no effect on output anyway.
Federico: `measured_points` and `measure` are also what a future datum (a
reference frame on the drawing) would read — nothing to build for it now.

**Done (19 October).** `topo/model/text.py` (was `annotation.py`): `Text`
with `position`, `text`, `height`, `rotation`, `width_factor`, `role`,
`origin`, `cluster_ref`, `source_kind`, `pointer`, `target`,
`measured_points`, `measure`, `measure_is_angle`, `references`, `rendered`.
`kind` (an alias of `source_kind`) and `display_text` are gone. The DXF
reader is `topo_dxf/text_extractor.py`: the logic that was
`Dimension.display_text` (override with `<>` → the measure as drawn, else the
drawn fragments, else the measure) runs there, once, on reading. The writer
picks by geometry, not by type: a `Text` with a `rendered` image is written as
that image, one without as a TEXT/MTEXT — the same split as before, since
only DIMENSION/LEADER entities ever carried an image. `anchor_texts`
(`pointer_distance`), `pointer_target`, `measured_references`;
`include_texts`, `text_layer`; view-model key `texts`. `to_text` format 1:
`## measures and pointers`, lines `measure '…' measured N [(angle)] -> …` and
`pointer …`.

Goldens: the two families that stored the old types (`golden/texts`, was
`golden/annotations`; `golden_anchoring/json`) were converted key by key
with the same values — `kind` → `source_kind`, `display_text` → `text`,
`measured_value` → `measure`, `dim_type` → `measure_is_angle` (true for
angular), `vertices` → `pointer`; `text_override` dropped, its effect was
already in `display_text`. The new code reproduces them unchanged. Nothing
else in topo's goldens moved. `text_budget` anch_06 now fits (the lines are
shorter); anch_02 still does not (open, not to be reopened).

snapdraw: `dim_type == "diameter"` became geometry, as decided — two
measured points, one element, a circle, their midpoint on its centre (so a
dimension on a thread's crest, anchored to the core circle, still counts);
`_anchor_by_center` already tested centre and radius and only lost the type
check; `parse_callout(text, diameter=False)` gets the "a bare 15 is a Ø" rule
from its caller. The scale leaves out `measure_is_angle` (now also 3-point
angles, which `== "angular"` missed). Its regression readings are unchanged
(regr_03/05 fail on the frame bbox as before). snapbend, snapfence: rename.

### D139 — Tabs at caller-chosen points: `bridge_parent_tabs`, one parent split once ✅ (names re-scoped by D140: experimental, not the stable surface) — superseded by D142
Federico, 19 October, from smoother (its D20): tabs placed by hand, a click
with snap in smoother's web UI, instead of `tab_count` equally spaced around
the island centroid. `topo.tools.tabs.bridge_parent_tabs(parent,
[(island, anchors), ...], tab_width)` → `ParentBridgeResult`.

Three geometric choices, each forced by a case that broke:

- **The tab leaves the contour perpendicular at the chosen point**, outward
  from the island or inward from the parent (into the island; if the island
  is not that way, toward its closest point). Toward "the closest point of
  the other contour" fails on a straight side: from the middle of an
  island's side the parent's closest point can be beside it, the offset
  lines run along the side and `bridge_tabs` finds no intersection.
  Outward is read from the ring's orientation (signed area), exact on thin
  or concave contours where a nudged inside/outside test is not.
- **A parent is split once, on the cuts of all its islands.** Splitting it
  once per island (what a per-island call would do) gives overlapping
  copies of the parent that no longer close.
- **An island that cannot be bridged goes to `failed` with the reason**,
  all its tabs dropped (never an island half attached); the other islands
  go on. Nothing silently dropped, and one bad island does not cost the
  whole parent.

Found on the way, fixed: `_split_closed_polyline_at_cuts` dropped both arcs
when a contour had a single tab (both cuts belong to the same tab, so the
rest of the contour also ran "from a cut of tab 0 to a cut of tab 0"). With
one tab only the shorter arc is the one under the tab. `bridge_nested_tabs`
with `tab_count=1` had the same hole.

Also added `topo.core.geometry.measure.closest_point_on_track` and the
predicate `is_tab_island` (even depth >= 2 with a parent), now shared by
both bridging functions. Not addressed: a perpendicular tab can still cross
another island of the same parent (the obstacle question already open for
`bridge_nested_tabs`).

### D140 — a consumer uses topo as it uses numpy: topo is read-only from a consumer's session, and what it lacks arrives as a request ✅
Federico, 19 October, from smoother: "the consumers I build must be as if I
imported numpy. I don't touch numpy to fix what it exports for a thing of
mine, I adapt my code to what I have to do, as I do here with shapely."

**What happened.** Working in smoother, a session could also write in
`../topo`, and did: `bridge_island_tabs`, then `bridge_parent_tabs`,
`is_tab_island`, `closest_point_on_track`, and D139, all shaped by one web
UI (a click with snap). Each was reasonable alone; together they are the
road to one API per consumer, which is the fear that would block 1.0. D139 also
went against D134 without reopening it (trade words in names: "tab",
"bridge"; a policy, the anchor rule, inside topo).

**The rule.**
1. From a session opened in a consumer, topo is **read-only**. A global hook
   (`~/.claude/hooks/library_guard.py`, Federico's machine, outside this repo)
   refuses every Edit/Write/shell write into this repo unless the session is
   opened in topo, and at session start puts in context what a consumer needs:
   `docs/LLM.md`, `docs/INDEX.md`, the titles of every decision here.
2. The consumer adapts to the public surface. What it lacks is a line in
   **its own** `TODO.md`, section `## Richieste a topo` (what, why, which code
   would use it); meanwhile the consumer writes it locally.
3. A session opened in topo triages those lines, as "richieste dalla
   superficie" already says: a geometric fact → a public name with docs, test
   and a D##; a piece of an algorithm → offer what it was rebuilding; a choice
   of the caller → stays in the caller.
4. The test for a new name: what changes from one consumer to the next must be
   an **argument** (a point, a width, a ring), never a **new function**. D118
   (`cut_by` takes any ring, not "a disc" and "a square") and D134 (the four
   facts for joining regions) are the precedents.

**What it means for D139.** Its geometric findings stay true and stay
recorded (perpendicular exit read from the ring's orientation; a parent split
once on all its cuts; an island that cannot be joined is reported, not half
joined; the one-cut split bug, fixed). Its names do not enter the stable
surface: `topo.tools.tabs` stays experimental and outside 1.0 (D122), frozen
from consumer sessions, and is rewritten as D134's facts with geometric names;
`bridge_nested_tabs` and the click rule then become smoother's policy on top
of them, migrated from smoother's own session. Until then smoother keeps
importing `topo.tools.tabs` as a prototype does (D122).

**Point 2, done now.** The one fact the click rule really needed was "the point
of a contour closest to a point": `topo.geometry.nearest_point(segments,
point)`, on the exact primitives (lines, arcs, circles exact; splines and
ellipses within `CURVE_TOLERANCE`), composable with `point_on_contour`.
`closest_point_on_track` is now that same function on a track's sides (one
job, one implementation); it stays internal, used by `tools.tabs`.

**Not blocking 1.0.** The stable surface already holds facts only; what the
hook adds is that nothing else gets in by accident. The sentence "what 1.0
promises" (TODO, road to 1.0) should say it in so many words.

### D141 — `simplify_points` rewritten: corners are a turn over a scale, lines where straight, arcs through their ends, splines within a tolerance; one chain ✅
The first requests that arrived through D140 (smoother `TODO.md`, "Richieste
a topo", 19 October): four of them are one thing. Working read-only on topo,
smoother had rebuilt the whole point→primitive reconstruction in its own
`smoother/fitting.py` (smoother D21), because `simplify_points` was wrong in
three ways on a traced contour:

- **A corner was an interior angle between two neighbouring samples** under
  a threshold (50°). A right angle never is, and a corner traced from a
  raster is spread over 2–3 samples, none under threshold: letters came out
  rounded. Now a corner is a Douglas-Peucker vertex where the curve **turns**
  by at least `corner_turn_deg` between the point `scale` before and `scale`
  after, along the curve — measured over a length, the rounding counts for
  the whole turn. Of two corners closer than `scale`, the one that turns more.
- **Every stretch between corners became one spline**, also when straight.
  Now: within `tolerance` of its chord → a line; within `tolerance` of an arc
  → an arc; otherwise the long straight Douglas-Peucker sides become lines
  (not the facets inside a curve: small turns the same way at their ends,
  not much longer than their neighbours) and the rest arcs or splines.
- **The arc was a least-squares (Kåsa) fit**, which moves the ends onto the
  circle: between an arc and the line next to it a gap opened and the
  contour no longer closed (smoother counted 321 loose pieces). Now an arc
  passes exactly through its two ends (and the middle sample) and is taken
  only if every point is within `tolerance` of its circle. Kåsa stays for a
  whole closed loop with no corner, which has no ends to keep.
- (fourth request) **The spline interpolated every point**, oscillating on
  noisy or irregularly spaced samples. Now `approximate_bspline`
  (Piegl & Tiller 9.4.1: chord-length parameters, averaged knots, least
  squares with both ends fixed) finds the fewest control points that keep
  every sample within `tolerance`; when none is enough it is the
  interpolation.

Two more facts the port needed, both geometric: samples are first evened out
to the median step (a long side with no samples would let three points pass
for an arc), and a corner rounded by sampling is rebuilt sharp — a curved
piece shorter than `scale` between two lines that turn by ≥ `corner_turn_deg`
is the rounding, and the shared vertex goes to the crossing of the two
least-squares lines. Found while testing, both fixed here rather than
ported: smoother's first and last Douglas-Peucker sides were always lines
("an end is a corner, never inside a curve"), so a pure arc came out
line-arc-line; an end side is now judged on the one neighbour it has, and a
stretch that is one arc is tried first. A closed contour with no corner is
opened at an arbitrary point; when the first and last pieces are the same arc
or the same line they are joined again.

**The guarantees, all geometric**: the output is a head-to-tail chain (an
open sequence starts and ends exactly at its ends; a closed one closes);
every sample is within `tolerance`, except samples within `scale` of a
rebuilt corner; a primitive is a line or an arc only if its samples are,
within `tolerance`. `scale` is the caller's statement of what is detail and
what is shape: the length over which a turn is a corner, under which a
straight run belongs to a curve and a curve between two sides is a rounded
corner.

**Signature, a clean break** (experimental since D33, outside `__all__`):
`simplify_points(points, tolerance, scale, closed=True, corner_turn_deg=35,
arcs=True, spline_degree=3)`. `tolerance` and `scale` are required: they are
lengths in the caller's units and topo cannot guess them. Gone:
`detect_corners`, `fit_primitives`, `interior_angle_deg`, `arc_angles`,
`DEFAULT_ANGLE_THRESHOLD_DEG`, `min_points_for_spline`,
`duplicate_tolerance`, `arc_fit_tolerance`. New in `core/geometry/points.py`:
`even_spacing`, `offset_from_line`, `douglas_peucker`, `turn_corners`,
`circle_through`, `approximate_bspline`.

**Internal caller**: `steps.refit_tessellations` (inside `island()`) now calls
it with `tolerance` (renamed from `arc_fit_tolerance`, it now bounds lines and
splines too) and `scale=max_segment`. All island goldens unchanged.

**Proof on real traces** (smoother's images: a gear, a hand-drawn circle, a
stylised dandelion; tolerance 0.3, scale 2): same kinds of primitives as
smoother's D21 (gear 35 lines, 1 arc, 2 circles, 18 splines vs 37/1/2/17), joints
within 4e-11, maximum deviation 0.299 everywhere — smoother's own code reached
0.319 on the dandelion, over its own tolerance, because its corner
sharpening did not check. DXF for the eye: `pipeline_output/D141_fit/`
(`*_raw`, `*_smoother`, `*_topo`).

**Not done here**: the fifth request (strips that cross nothing) is fact 3 of
D134 and lands with that rewrite. smoother's `fitting.py` is now the duplicate:
it moves onto `simplify_points` from smoother's own session (D140).

### D142 — `tools.tabs` becomes `tools.strips`: D134's four facts and the construction, on primitives; policy and `is_tab_island` go back to the caller ✅
Federico, 19 October ("implement what belongs here"). Implements D134 and
judges D139, which had entered because it was already written, not because a
triage admitted it (TODO, "richieste dalla superficie").

**What topo gives** (`topo.tools.strips`, experimental, D140):
`facing_boundaries(cluster)` → `Facing(region, inside)` per empty region
(fact 1); `gap(a, b)` → `Gap(distance, on_a, on_b)` (fact 2);
`link(facing, a, b, at, width, placed=())` → `Link(a, b, strip)` (fact 3);
`unconnected_regions(cluster, links)` (fact 4); `open_boundaries(links)` →
`Opened(boundaries, sides)`, the construction. The ring-level geometry (no
hierarchy) is `topo/core/geometry/strips.py`: `gap`, `strip_between`,
`open_ring`, `Strip` — a brick, not in `topo.geometry.__all__` until a
second caller uses it.

**Choices, each with its reason:**
- **Primitives, not points.** The old code discretized every contour
  (`discretize_tolerance`) and returned point lists to be refitted. Now the
  cuts are `intersections` of the side lines with the contour's own
  primitives, and the opened boundary is chains of the same primitives (a cut
  circle is an arc, exact). A caller tracing a raster still gets its
  polyline back as `LineSeg`s; a caller with real arcs no longer loses them.
- **The direction keeps D139's rule** (perpendicular from the nearer
  boundary, toward the other, else toward its closest point), made
  hierarchy-free: the normal points inward if the boundary contains the other
  one, outward otherwise. Tangents are exact on lines, arcs and circles: a
  one-sided difference at a circle's seam tilted the strip by 3e-5.
- **Refused, with the reason**, when a side misses `a` or `b`, crosses
  another boundary of the `Facing` or its own two boundaries again (concave
  shapes), when a boundary lies wholly inside the strip, or when it touches a
  strip in `placed`. This is smoother's `_crossing_islands`, now a fact.
- **Which stretch the strip covers** is the one between its two cuts that
  holds its foot (`a_at`/`b_at`), never "the shorter one": the old single-tab
  rule was a guess that breaks on a strip wider than half a small contour.
  Two strips overlapping on one boundary raise in `open_boundaries`.
- **Removed, back to the caller** (policy, D134): `is_tab_island` (which
  regions get strips), `tab_count` spaced round the centroid
  (`bridge_nested_tabs`), the per-island `failed` bookkeeping
  (`bridge_parent_tabs`: the caller catches `link`'s `ValueError` per
  region). Also removed, used only by tabs: `polyline_line_intersections`,
  `closest_point_on_track`.

D134 said "smoother updated in the same change": superseded by D140, smoother
adapts from its own session (the mapping is in TODO). Script 16 is now
`16_strips_on_fixture.py` and holds its own policy (4 strips at 90°). Proof:
`tests/unit/test_strips.py` — sisters and window, cousins never facing,
four nesting levels, perpendicular from a straight side, refusals, the
fixture rejoined and healed back to a valid cluster with four empty sectors.

### D143 — what 1.0 promises: names and signatures, *and* the geometry, as invariants rather than golden numbers ✅

A library that promises only its names promises that the caller's code still
imports, not that the part comes out right; for a geometry engine that is no
promise at all. So 1.0 promises two things for the whole 1.x line:

1. **The surface:** the public names and signatures (`__all__` of `topo`,
   `topo.geometry`, `topo_dxf`) do not break. The stable surface holds facts
   only, never the shape of a consumer (D140).
2. **The geometry**, as three invariants checked on every input:
   - **faithful** — Hausdorff distance between input and output, *in both
     directions*, ≤ heal's tolerance; where heal did not intervene, the
     coefficients are identical (centre, radius, control points). Checked on
     the DXF written and read back, not only on the model in memory (D121);
   - **complete** — every input curve is a contour of some cluster or lies in
     `result.loose` (D137); nothing is dropped, not even as a "duplicate";
   - **deterministic** — same input, same output, whatever the order of the
     edges (D131).

**Not promised:** the exact number of segments of a discretization, the start
point or direction of a contour, the outcome of ambiguous cases of
`island()`. These may improve in a minor. The reason: a golden freezes a
number, an invariant states what matters — the part stays superimposable on
the original — so a 1.x that discretizes better keeps the promise instead of
breaking it.

**What it makes blocking for 1.0** (TODO, "la strada verso la 1.0.0"): the
two-way fidelity test and heal's per-entity deviation report (D121); the
128-side cap on `CircleSeg.discretize`, which already violates the tolerance
past r ≈ 33 at tol 0.01 (and `ArcSeg`/`EllipseSeg` checked the same way);
the four doubts on D103, verified rather than excluded — `island()` is one of
the two readings, leaving it outside the promise removes half its value; and
a loop discarded as a boundary duplicate goes to `result.loose`, never to a
discard bucket (non-negotiable 7).

### D144 — for 1.0, the reader's documents are English: `API.md`, `ARCHITECTURE.md`, and the docstrings of public names; internal code stays Italian ✅

1.0 is for a third party who builds on topo's primitives (D143). That reader
meets topo in three places: `API.md` (the reference), `ARCHITECTURE.md` (why it
is built this way), and the docstring of a public name — what an IDE shows on
hover and `help(topo.heal)` prints. For that reader the docstring of a public
name is part of the API, like its signature; in Italian it is a wall exactly
where they need it. So, blocking for 1.0:

- `docs/API.md` and `docs/ARCHITECTURE.md` in English (the repo rule already
  said so; both were still Italian). `LLM.md` already is.
- Docstrings of the public names — `__all__` of `topo`, `topo.geometry`,
  `topo_dxf` — in English, short; the full card stays in `API.md`.
- Everything internal (private helpers, `core/`, comments) stays Italian: its
  reader is the maintainer, with the code in front of him.

This is a topo exception to the general convention (docstrings in Italian),
written in topo's `CLAUDE.md`. The public set is known to `gen_index`, so the
rule can be checked rather than remembered.

### D145 — circles and arcs discretize on one grid per circle: no side cap, sides grow with the radius, an arc is a piece of its circle's polygon ✅

The first item made blocking by D143. Two changes, one reason: the same curve
must give the same polygon, within `tol`, however the file cut it.

**No cap.** A chord of angle θ on radius r leaves a sagitta r(1 − cos θ/2);
held at `tol`, the sides needed are ~π·√(r / 2·tol) — they grow with the
radius. The old cap of 128 sides broke the tolerance from r ≈ 33 at tol 0.01,
linearly with r: 0.15 at r 500, 0.60 at r 2000. Now 994 sides at r 2000,
deviation 0.00999.

**One grid per circle.** Before, a circle had at least 64 sides and an arc
at least 32 whatever its sweep (a small quarter was eight times denser than
its circle), with vertices starting at its own start angle: a hole that
arrives as one CIRCLE, two halves or four quarters gave three different
polygons — a fact about how one file was authored (non-negotiable 1). Now the
circle has N sides (`_circle_sides`: sagitta ≤ tol, at least 64, rounded up to
a multiple of 4) at angles k·2π/N anchored at angle 0; an arc takes its exact
ends plus every grid point between them (`_grid_angles`). So the four
quarters joined are the circle's polygon exactly, an arc is a piece of it, a
reversed arc gives the same points backwards. The two end chords are shorter
than a step (smaller sagitta, so within `tol`); an arc shorter than a step is
one chord; a grid point is skipped only when it coincides with an end
(1e-9), never within a fraction of a step, which would stretch a chord past
the step and break `tol`. N a multiple of 4: the grid is symmetric about both
axes, so quarters fall on vertices and a mirrored part gives the mirrored
polygon.

**The price, chosen:** a circle has no direction of its own, so the grid is
anchored to the world's angle 0; rotating a part no longer rotates its
vertices (they still lie on the curve within `tol`). Same curve → same polygon
is the stronger invariant, and D143 promises the tolerance, not the vertices.
Output to a machine is unaffected: `to_dxf` writes native ARC/CIRCLE.

`ArcSeg`/`EllipseSeg` were measured already within `tol` (ellipse untouched).
Proof: `tests/unit/core/test_discretize_tolerance.py` (every scale; quarters
= circle; off-grid arc = piece of the circle; reversed; one chord; no
degenerate side); `test_segment_rotation` now checks points on the rotated
arc. Goldens of `heal` regenerated after proof: every changed part's area
recomputed at tol 1e-5 and the error checked against tol × perimeter — all
within (22 of 33 closer to the true area, 11 a little farther: small fillets
lost the 32-side floor, still within `tol`). Goldens of `island()`
(`golden_anchoring`, `text_budget` of anch_06) left red on purpose, frozen
under the D103 doubts: anchoring changes only `length`/`width` of `other`
shapes (≤ 0.017, polygon bbox), but anch_06 changes topology — `island()`
decides self-contact on the discretized polygon, so the reading moves below
the tolerance (TODO).

### D146 — a piece of the outer contour is not also a spur: `outer_face` removes from `spurs` every edge its chosen loop uses ✅
`outer_face` counts spurs on the walk (an edge walked twice), then may choose
another loop: the boundary of the union of closed faces (D100), when nodes
miss each other by microns. That loop can use an edge the walk counted twice,
so the edge came back in `loop` *and* in `spurs`, and `island()` wrote it
twice: in the outer contour and in `loose` (anch_08 without frame: 24 lines,
one of 37.9 mm). The rule, where the data is made: a piece the chosen contour
uses is contour, never a spur. Nothing else moves: suite identical.
Proof: `tests/real/test_island_single_use.py` (no edge in both lists, on the
eight `anch_NN_noframe` drawings; fails without the fix).

Found on the same pass, not fixed here (TODO): `island()` closes gaps from
"free" ends that lie mid-edge (a T within tolerance): the bridge lies on the
existing edge and doubles it. Skipping those ends removes the duplicates but
loses the loops that share a side with the outer contour — they closed only
through the duplicate. And two coincident circles are never merged
(`merge_cocircular_overlaps` takes `ArcSeg` only).

### D147 — `island()`: an end that lies on another edge's interior is not a free end; a closed loop with a side on the contour that holds it is not an inner — ⏸ suspended, code on branch `d147-t-ends`
**Suspended the same evening:** Federico judged `regr_04` worse after — the
outer of the pictorial (3D) view was right before and is wrong after (the
30.8 mm² pocket at its left edge). The code is reverted on `main`, kept on
branch `d147-t-ends` (commit 71ca4f0); the decision on loops with a side on
the contour (trash, Federico) stands. What follows is the state as committed
there.

`island()` closes drawing gaps up to `max_gap` (D60) from the free ends of
the graph. An end that falls mid-edge (a T within the node tolerance) is
"free" for the graph — the edge has no node there until
`split_at_crossings` — so two such ends close to each other were joined: a
bridge laid on the edge, or both lines stretched to meet outside it. Either
way the same stretch came out twice, in the contour and in `loose` (what
Federico saw as "inner with a part in trash"). Rule (`_on_edge_interiors`):
an end within tolerance of another edge, away from that edge's nodes, is
already connected — the noding makes it a node — and takes no gap fix. It
stays free when another free end lies within tolerance (a corner: the two
ends are one node; without this a corner on a crossing circle closed
through a 0.01 arc and the DXF round trip changed, `regr_01`/`anch_08`).

The duplicate was the only thing closing loops that share a side with the
contour around them (`read_island` looks for inners among the pieces the
outer does not use). They now go to `loose`. Federico's call: a rectangle
0.5 × 1.2 hanging under the outer line of a section view is a feature of
that view, "trash tutta la vita", not an inner. Measured on every island
fixture: the inners lost are all thin loops (0.5 wide) with one side of
0.5–1.04 on the larger contour; `regr_02` loses a 0.18 nub (0.06 mm²) and
`regr_04` a 30.8 mm² pocket at its left edge (DXF in `_debug/`, to judge).
Goldens of island that move (`anch_01`, `anch_04`, `regr_03`; anchoring and
text budget of `anch_01`) are expected failures with the others, redone
from scratch on the `_noframe` drawings. Proof:
`tests/real/test_island_single_use.py` (the T case, built with topo's API;
fails without the fix), all `island_invariants` green (round trip included).

### D148 — feature freeze until topo is *1.0-ready*: a closed gate of eleven items, then every commit on `main` keeps it releasable ✅
Federico, 22 October: stop adding things. The goal is not "release 1.0" but
reach, as soon as possible, the state from which 1.0 can be pushed at any
moment with nothing else to do. The version number may stay where it is; what
matters is that from that day `main` is always releasable.

**1.0-ready** means one command, `scripts/release_check.py` (gate item G11),
exits 0: the suite green with **no** `expectedFailure`, `gen_index --check`,
`audit_names --strict`, `audit_fixtures --strict`, the English-docstring check
on public names. From that day every commit on `main` keeps it at 0; a change
that cannot is a branch.

**The gate is closed** — the list in `TODO.md` ("IL CANCELLO DELLA 1.0", G1–G11)
is the whole of it. Only two kinds of work enter it: what changes a public name
or signature (it must happen before 1.0 or wait for 2.0), and what D143's
invariants (faithful, complete, deterministic) need to be true and proven on
the existing fixtures, plus the reader's documents (D144) and the client-data
history rewrite. Everything else — PDF, the `Curve` model, contour signature,
viewer, strips, D147's T ends, coincident circles, curves from equations,
recognition facts, new consumer requests that add names — is 1.x, additive,
after the gate. A problem found while closing the gate enters it only if it
breaks a public name or violates an invariant on a fixture already in the repo;
otherwise it is a line under "dopo la 1.0".

Why a closed list: the road to 1.0 in `TODO.md` grew with every session
(D135–D147 were each right, and each added scope). A list that can grow has no
end; a list that can only shrink does.

### D149 — reopening D143 on one point: heal's per-entity deviation report is 1.x, the two-way fidelity test stays blocking ✅
Federico, 22 October, closing the 1.0 gate (D148, item G2). D143 made two
things blocking for fidelity: the test (Hausdorff both ways ≤ tolerance,
identical coefficients where heal did not intervene) and a report on `Result`
of how far heal moved each entity. The promise is kept by the test: it is what
proves, on every fixture, that the output is superimposable on the input. The
report is a new field on `Result` — a new name, so additive, and a 1.x minor
can add it without breaking anyone. It leaves the gate; the test (G3) stays.

### D150 — `Result` loses `classified_entities`, `all_arcs` and `_open_shapes` ✅
Gate item G1 (D148): the fields of `Result` typed `List[Any]` are public
surface and 1.0 would freeze them.

- `_open_shapes`: nothing wrote or read it. Removed.
- `classified_entities`: snapbend's. What went in it is a `ClassifiedEntity` —
  `work_type` (bending, marking, …), `confidence`, `source`, `data` "ready
  for CAM": process vocabulary (non-negotiable 4). Its geometry was already in
  topo's result, as the loose curve or inner it came from. It stayed on
  `Result` only because `detect()` lived in topo before D88. Removed;
  snapbend writes what it classifies into the cluster that contains it, and a
  shape no cluster contains now stays in `result.loose` instead of living only
  in a list topo did not know about (D137: nothing disappears from the result).
- `all_arcs`: geometry, but a duplicate. Every curve is a cluster's contour or
  in `loose` (D137), so the arcs are already in their `segments`; an open arc
  (a thread crest) is in `loose`. The need behind it is already public —
  `topo.geometry.arcs_around(center, radius, arcs)` takes the arcs as an
  argument. Removed; `rotate_result` no longer rotates a parallel list.

Checked before removing: on 376 local drawings the arcs of contours + `loose`
equal `all_arcs` (direction aside) on 362. On the other 14, two quarter arcs
(r 0.64–0.8) are in `all_arcs` and nowhere in the result — a D137/D143
"complete" violation by `heal()`, not a reason to keep the field. All 14 are
untracked and warn of contour crossings without a common node; to reproduce
with topo's API (TODO, G3).

Suites: topo unchanged (1377 passed, 20 xfailed). snapbend 16 failed and
snapdraw 3 failed, the same tests before and after this change (snapbend's are
process-golden areas, e.g. `arc_arc_gap` 7851.96 vs 7850.83: plausibly D145's
finer arcs, to be judged in snapbend, not regenerated). `main` stays 0.21.0,
unreleased: D150 joins D135–D138 in it.

### D151 — A loop that makes no contour goes to `loose`, edge by edge ✅
Found under G3 (D148), the 14 drawings of D150. `loops_to_curves` dropped a
loop the graph had closed but that made no contour: no valid polygon, area
under `MIN_CONTOUR_AREA`, or a single circle under `MIN_SINGLE_LOOP_DIAMETER`.
Its edges were already counted as "in a loop", so `edges_to_open_curves`
skipped them too: they vanished from the result, with no warning. A D137/D143
"complete" violation.

The 14 cases are one shape: a quarter arc drawn twice, as the `ARC` and as its
chord approximation (15 chords of 0.07 on r 0.64). Arc and chords share both
ends, so the graph closes them into a loop of area ~6e-4 mm². The crossing
warning those drawings carry is unrelated. Reproduced with topo's API in
`tests/unit/core/test_heal_steps.py::TestLoopsToCurves` (arc + chords inside a
square: before, 16 segments lost; now 16 in `loose`).

The fix is in the step, not in `heal()`, so a caller composing its own recipe
from `topo.steps` (D62) gets it too: a rejected loop comes back as one
`OpenCurve` per edge, native segment kept. An `OpenCurve`, never a
`ClosedCurve`, also for a lone circle: a rejected loop is by definition no
contour, and a `ClosedCurve` would be put back in the containment tree by
`build_hierarchy`. Only zero-length segments are left out (no geometry to
lose). `loops_to_curves` now returns `list[ClosedCurve | OpenCurve]`.

Checked: the 376 local drawings lose no source arc (was 14); suite unchanged.

### D152 — Reopening D56 on one point: a welded group spans at most 0.05 mm; fidelity is tested per reading ✅
Found by G3's measurement (D148): on `golden_islands/regr_01`, read with
`heal()`, a source point lay 0.59 mm from the output against a tolerance of
0.05. `weld_degenerate_linesegs` (D56) used an unbounded union-find: a curve
drawn as a chain of 0.02 mm LineSegs welded into one node, the welded edges
vanished, the curve collapsed to a point. D56 stays — welding, not deleting —
but a group of welded nodes now spans at most `_DEGENERATE_LENGTH_EPS` (its
bounding-box diagonal); a sub-threshold LineSeg whose weld would exceed that
stays as a real edge. Candidates are welded in a canonical order (length, then
nodes), not input order, so the groups do not depend on edge order (D131).

Effect on local drawings: only sheets of views change, and Federico judged
them (23 Oct): heal on a sheet of views is not a case heal is designed for, so
those changes are irrelevant; on `island()` the result is a little better
(fewer false micro-inners). Rounded rectangles drawn twice (arcs + chord
corners) were read before as sharp-cornered inners plus a false inner per
corner arc; now they are in `loose` — better, though not yet a contour.

**Which reading a fixture gets.** It was already in the golden tests and is
now written down: drawings in `tests/data/golden_islands/` and
`tests/data/golden_anchoring/` are sheets of views, read with `island()`;
every other tracked drawing is read with `heal()`. A fidelity failure of
`heal()` on a sheet of views is not a defect.

**The test** (`tests/real/test_fidelity.py`, closes G3): every tracked drawing,
written with `to_dxf` and read back with `document_from_msp(skip_layers=())`
(loose included), identical copies measured once (216 drawing/reading pairs):
1. Hausdorff in both directions ≤ the reading's bound: the node tolerance for
   `heal()`, `max_gap` for `island()` — gap closures are the only thing that
   moves geometry in a view.
2. Identical coefficients (≤ 1e-9: centre and radius, ellipse, control points,
   a spline also reversed) for every curve the reading had no reason to touch:
   both ends coincide with another source edge's, and no near-duplicate of
   the same kind within 0.05. A free end may have been closed within the
   tolerance, and then an arc read back from an LWPOLYLINE bulge has its centre
   and radius recomputed from moved ends (0.09 mm on an r 420 arc of small
   sweep — ill-conditioned, still within Hausdorff). That is heal intervening,
   which D143 exempts. Today 7391 of 11838 source curves are compared; the
   test asserts the count stays above 1000, so the rule cannot quietly
   exclude everything.
Mutation check: a bulge off by 0.1% in the writer fails 77 sub-tests. Suite
time 90 → 154 s.

### D153 — an ellipse discretizes on its parameter grid, like an arc on its circle's (D145): within `tol` by construction, a piece is a piece of the whole ✅
Gate G4. `EllipseSeg.discretize` sampled uniformly by the smallest radius of
curvature, then halved a piece while its *parametric midpoint* was farther
than `tol` from the chord. Two faults, measured on 200 random ellipses:
- **Out of tolerance on flat ellipses.** On an ellipse with ratio below
  ~0.006 the sharp tips at the ends of the major axis are not at the
  parametric midpoint of a piece. The midpoint passed and the piece stayed
  too coarse: 0.0152 at a 18.6, ratio 0.0054; 0.0113 at a 139, ratio 0.0027.
- **Same curve, different polygon.** An ellipse in two halves gave 169
  vertices, the whole one 171, not the same points. That is the fault D145
  removed for circles.

The rule: an ellipse is the circle of radius `a` (semi-major axis) seen through
a linear map with factors 1 and `ratio`, and that map never lengthens a
vector. A point of the circle within `tol` of its chord maps to a point within
`tol` of the mapped chord. So the circle's grid (`_circle_sides(a, tol)`,
k·2π/N) taken on the *parameter* keeps the ellipse within `tol`: a proof,
not an estimate, and no subdivision is needed. As for an arc, the exact ends
plus every grid point between them (`_grid_angles`). The four quarters are
the whole ellipse, a reversed ellipse gives the same points backwards, and the
grid starts at the major axis, so it rotates with the ellipse. A `ratio`
above 1 (outside the format) uses the larger factor as the radius.
Vertex count is the same order as before (161 against 171 on a 40×16
ellipse). `MIN_SEGMENTS_ARC` and `FALLBACK_ANGLE_DEG` are removed: nothing
uses them any more. `_adaptive_polyline` stays, for splines.
Proof: `test_discretize_tolerance` (flat ellipse, rotated partial clockwise
ellipse far from the origin, quarters = whole, reversed); the two new
invariants fail on the old code. No golden changed. Arcs were measured again
(300 random: radius 0.001–3000, centers at 1e5, both directions): all within
`tol`, nothing to change.

### D154 — a curve of zero size is a point, not a curve: the primitive refuses it, the DXF adapter turns it into a warning ✅
Gate G4. `ArcSeg.discretize` raised ZeroDivisionError on radius 0. The source
of those arcs was not an ARC entity: 6 arcs in 4 local drawings came from
LWPOLYLINEs with a repeated vertex that carries a bulge. `from_chord` divided
0 by 0 on numpy floats, which warns instead of raising, and built an arc with
center NaN and radius 0. Separately, a CIRCLE of radius 0 stopped `load_dxf`
on the whole drawing (`CircleSeg` refuses it, nothing caught it).
The rule, one for all three closed-form curves: a radius 0, a null axis or a
`ratio` of 0 has no extent. It is a point (or, for the ellipse, a segment),
and topo has no point primitive. `ArcSeg` and `EllipseSeg` refuse it at
construction like `CircleSeg` already did (`not x > 0`, so NaN is refused
too), and `ArcSeg.from_chord` refuses a null chord. In the adapter:
- a null chord with a bulge in a polyline becomes the null `LineSeg` it would
  be without the bulge (welded by D56);
- an ARC, CIRCLE or ELLIPSE the primitive refuses is counted by type and
  reported in `doc.warnings`, the channel D137 gives to what the model cannot
  hold, instead of ending the load.
Proof: `tests/integration/test_degenerate_curves.py` (all five fail on the old
code); 683 local drawings load, 376 heal without errors, no zero-radius arc
left in any source or result.
D112 already met this NaN arc, on the writing side: a lone near-full arc was
written with a zero chord and read back as a NaN arc. D112 stopped topo from
writing it, so it now becomes a `CircleSeg`. The reading side stayed open, and
the 4 local drawings were most likely written before D112. D154 closes the
reading side for any file.

### D155 — each closed gate item is one micro bump and one push ✅
Federico, 23 October: "micro bump e push per ogni passo del cancello chiuso".
Until 1.0-ready, closing an item of the D148 gate ends with a version bump in
`pyproject.toml`, recorded here, and a push of `main`. The bump is the third
digit, unless the item removes or renames a public name, which bumps the
second, as before (0.21.0). A consumer then always sees the gate's progress as
a version, and nothing waits unpushed.
The first push under this rule carries everything since 0.21.0. That includes
D149/D150 (public fields removed from `Result`) and D151 (`loops_to_curves`
return type), so it is **0.22.0**. From the next item on, the bump is the
third digit.
`main` → **0.22.0** (G1, G2, G3, G4 closed: D145–D154; public fields removed,
`heal()` output changes, arcs and ellipses of zero size refused).

### D156 — gate G5: `contour_shape` measures `other` on the primitives; the countersink's area was the parity reading, not a bug ✅

Two measurement doubts found with D145, both checked against an exact value.

**`cluster.area` of `rect_with_countersink` is right.** The TODO note called the
Ø10 circle "an inner not subtracted", comparing with outer minus the *union* of
the inners (19293.14). But the Ø10 lies inside the Ø30: depth 2, an island in
the void, material by the parity rule (D89). The exact value of that reading is
200·100 − π·15² + π·5² = 19371.68; `heal()` gives 19372.16, a difference of 0.47,
within tol × perimeter of the two circles (1.26). No code changes; a test
(`TestHealerCountersink.test_003_area_per_parita`) now holds both the depths and
the value. Reading the pair as one hole is a process reading (snapbend).

**`contour_shape` of `other` measured the inscribed polygon.** `_generic` took
`length`/`width` from the minimum rotated rectangle of `discretize()`: a chord
lies inside its arc, so every curved side came out short, up to 2·tol. Measured
on the anchoring drawings against a 1e-6 reference: up to 0.016 short — beyond
tol. Now:
- `segment_reach(segment, direction)` (`core/geometry/measure.py`, internal) is
  the (min, max) of the projection of the curve itself: closed form for line,
  arc, circle, ellipse; for a B-spline 16 samples per knot span, then every
  local extreme that can still win refined by golden section on the parameter.
  `Reach` keeps a spline's samples for many directions.
- The polygon only gives the starting angle. For `other` the angle of the
  minimum-area rectangle is searched on the primitives within ±1° of it (the two
  differ only by the sagitta of the curved sides), and length/width are the
  reach along the two axes. So at the returned angle the rectangle contains the
  curve and touches it on all four sides, exactly. `polygon` (all lines) is
  unchanged: its polygon is exact.
- Result: within 4e-5 of the reference on every `other` of anch_01–07.

**The price, chosen:** time. Searching the angle on sampled splines only was
about 12× faster but, on nearly symmetric shapes (area almost flat with the angle),
landed in another local minimum (3e-4 off). Federico, 23 October: correctness
now, speed when the geometric questions move to the Rust engine (ROADMAP).
`contour_shape` on anch_02 (133 spline shapes): 0.03 s → 5 s.

Golden: anch_01 changes only `length` of one contour, 7.894 → 7.895 (reference
7.895). anch_02–07 stay frozen for G7.
`main` → **0.22.1**.

### D157 — gate G6: the four doubts on D103 checked one by one; a dropped loop has no boundary of its own at the contact distance, and its edges are in `loose` ✅

Checked on every `golden_islands` drawing by intercepting
`_drop_boundary_duplicates` (`island()`, max_gap 0.5, tol 0.01): 56 loops
dropped, on anch_02 (50), anch_03 (4), anch_06 (1), anch_07 (1); regr_02 and
regr_05 drop the same loops as anch_03 and anch_07 (same geometry). For each
loop: the host it was matched to, the directed distance of its boundary from
the host's and back, the share of its area inside the host, and how much of
its boundary is in the output.

**What the rule says, in geometry.** A loop is dropped when every point of its
boundary lies within `band` = tolerance + max_gap of the boundary of a larger
loop already accepted. In `island()` two curves closer than max_gap touch (D98,
D99), so such a loop touches an accepted contour all along: it has no boundary
of its own at the reading's contact distance and adds no contour. The
docstring said it was "the wall of a hole in an isometric view": that is an
interpretation of one drawing, now removed (non-negotiable 8). The threshold is
the caller's parameter, and the drops follow it exactly: on anch_02, 50 at
max_gap 0.5, 1 at 0.34 and 0.25 (only the true duplicate is left); on anch_03,
4 at 0.5 and 0.34, 0 at 0.25.

**The four doubts:**
1. **anch_02/anch_03, "grandchild inners at depth 2?"** — 48 of anch_02's 50
   and all 4 of anch_03's are a closed loop fully inside another (share
   inside 1.000), with the boundaries within band in *both* directions: 18 at
   0.504/0.505 (11.3 mm² inside 16.3), 30 at 0.351 (4.96 inside 7.24), 4 at
   0.31 (3.01 inside 4.62). The ring between the two is narrower than band
   everywhere, so at max_gap 0.5 there is one contour, not two. `heal()` keeps
   both (anch_02: 16.287 and 11.326 as two inners; anch_03: 4.623 an outer
   with 3.011 inside) because its contact distance is tol, 0.01, and 0.3–0.5
   is far beyond it. Two readings, two resolutions; not a contradiction.
2. **anch_06, "a real drawing symbol overlapping the outer?"** — no: a single
   circle of Ø≈1.07 drawn twice, Hausdorff distance 0 between the two. The
   second copy is the dropped loop. anch_02's 50th is the same kind: a ring of
   42 lines retracing a 5.56 mm² outline within 0.004.
3. **anch_07/regr_05, "0.07 mm² should go to the trash, not a discard
   bucket"** — there is no discard bucket: a dropped loop's edges stay in the
   rest of the island and go to `non_contour`/`unclassified`, hence to
   `loose` with the island's `cluster_ref`. The loop is a sliver along the
   outer, mean width 0.068 (wider than tol, so D106's thin-face rule does not
   take it; narrower than max_gap).
4. **Not in the TODO list, found here:** one anch_02 loop (3.09 mm²) is only
   33% inside its host, a Ø5 circle: it is the perimeter around the circle's
   edge, a line and the 3/4 arc of r 3 drawn around it — a cycle that is not a
   face. The rule drops it for the same reason as the others (every point of
   its boundary within 0.503 of the circle); the faces it encloses (a lens
   0.5 wide inside the circle, the 0.5 ring between r 2.5 and r 3) are all
   narrower than band.

**Dropped loops are in `loose`:** for all 56, the share of the boundary
covered by `result.loose` (within 0.011) is 1.000. `TestNothingDropped` would
not see a lost one (it measures at max_gap, and a dropped loop is by
definition within band of a contour), so two unit tests in `test_island.py`
hold it on two concentric circles 0.4 apart: at max_gap 0.5 one inner and the
other circle whole in `loose` with `cluster_ref` 0; at max_gap 0.2 two inners.

**Not D103, left for G7:** the inners that cross on anch_03/regr_02
(`KNOWN_CROSSING_INNERS`, D107) are cycles that are not faces *among accepted
loops*, none of them dropped by this rule. They were filed "inside the D103
doubts"; they are a separate defect, and G7 (zero `expectedFailure`) now names
them. The island goldens can be regenerated (G7) once Federico has looked at
the dropped loops: DXFs in `_debug/2026-10-23_topo_G6_D103/` (layer
`GIRO_SCARTATO`, red).

No change to `island()` output. `main` → **0.22.2**.

### D158 — the 1.0 gate closes on invariants: D143's promises become tests on every fixture, both readings; what they do not see goes to 1.x

Federico, 23 October, after G6b appeared: the gate keeps growing because
defects are found by looking, one drawing at a time, and looking never ends.
D143 states the promise as a finite set of invariants; three were already
tests, one ("every input piece comes out once") was not, and that is where G6b
was hiding. So:

**Permanent (stays after 1.0):** every invariant of D143 is a test in the
suite, run on every fixture in the repo, in both readings where it applies —
faithful both ways (`test_fidelity`), complete (`TestNothingDropped`), every
piece out once (new, G6b), deterministic (edge order, `TestEdgeOrder`), and
invariant under rigid motion (rotation exists for `heal()`; translation far
from the origin, mirror, and all of them for `island()` are missing). A
reading's facts are properties of the shape, not of where it sits or in what
order it was read, so moving, turning, mirroring or reordering a drawing must
not change them beyond the tolerance. These are the guard every 1.x change
must keep green, and a new fixture gets them for free.

**Temporary (deleted when topo is 1.0-ready):** the list of red invariants
on today's fixtures *is* the rest of the gate. After that sweep, an item
enters the gate only if it turns one of these invariants red on a fixture in
the repo; a defect found by eye that no invariant sees is a 1.x fix.

### D159 — the D158 sweep: every invariant on every tracked drawing, known defects registered per case

**Where they run.** `tests/drawings.py` lists every DXF tracked by git with
its reading (D152, the list `test_fidelity` already used); the invariant
tests of both readings now take their fixtures from it, not from
`golden/` and `golden_islands/` alone: 185 drawings read with `heal()`, 31
with `island()`. A drawing added to the repo gets every invariant.

**What was added.** `translated(dx, dy)` and `mirrored()` (y → −y) on every
primitive, next to `rotated`: a mirrored arc or elliptic arc changes the
sign of its angles and its direction, because the point at angle *a* goes to
−*a*; the circle grid anchored at angle 0 (D145) is symmetric, so a mirrored
arc has the mirrored vertices. Tested on a grid of cases (negative
coordinates, near zero, 3·10⁶ from the origin). The invariants, shared in
`tests/invariants.py`: rigid motion (rotation 0.7 rad, quarter turn,
translation to (2.5e6, −1.5e6), mirror) comparing outers *and* inners, edge
order, and **every piece out once**: no stretch of `loose` lies within 0.01
(two discretizations of one curve, chords on the same side) of a contour for
more than 1 mm — a crossing does that only under ~1°, a tangency only past
R ≈ 12 mm. For `heal()` it also runs at tol 0.01 and 0.05, because a
tolerance changes which gaps close and which corners are repaired.

**Known defects, per case.** A red case is registered with its gate item
(`KNOWN` in the island tests, `KNOWN_TWICE` / `KNOWN_CHORDS` in heal's):
it runs, must fail, and shows as a skip naming the item; when it passes the
test fails until the case is removed. An `expectedFailure` on a whole test
would hide a new red in the same drawing and say nothing when it heals.

**Result.** `heal()` passes motion, mirror, far translation and order on all
185 drawings; red only `rect_overlap` at tol < 0.1 (out once, G6b) and
`SEGNI_TRACCIATI` (chords change the outer, G6d). `island()` is red on order
(22 of 31) and rigid motion (20 of 31) — G6c —, out once (13, G6b), inners
crossing and roundtrip (G7). Order dependence is a defect, not one of the
"ambiguous cases" D143 leaves open: an ambiguous case may be decided either
way, but by the geometry, and the same geometry listed in another order is
the same case.

### D160 — the full suite runs in under 3 minutes, serial, every test capped

A suite nobody can run often blocks delivery: past ~3 minutes it is not
run, or it is run while waiting, and both cost more than the tests save.
After the D158 sweep the serial suite took 10 minutes, and a run that hung
gave no name. The budget holds on a machine with few cores, so it is
measured serial, and no test is removed:

- **Every test has a cap.** `pytest-timeout` (`--timeout=60` in
  `pyproject.toml`): a test that hangs fails with its name and the stack
  where it stood, instead of freezing the run at 99%. No parallel workers:
  each xdist worker rebuilt the cached readings for itself, multiplying the
  work, and wall time on many cores hid the cost a small machine pays.
- **Each reading is computed once.** The base reading of `island()` and one
  `scrambled` variant per drawing (D158) are cached in `tests/readings.py`
  and handed out as fresh copies.
- **The checks are local and build each band once.** "Out once" and
  "nothing dropped" compare a curve with the band around the outputs near
  it (an STRtree query), which is the same set inside that width; the band
  around each output is buffered once and reused, because the band of a
  union is the union of the bands (rebuilding it per input edge cost more
  than 60 s on one sheet with 7,500 short edges, now under 3 s). The twin
  search between holes skips pairs with disjoint bounds whose areas already
  exceed the band, where the symmetric difference is the sum of the areas.

When a full run finds a failure, only the failures are rerun (`--lf`) until
green, then the full suite once before the commit.

A change that pushes the suite over 3 minutes is fixed in the same change,
by caching, cheaper checks or fewer cases — slimming tests or goldens is
preferred to a slow suite.

### D161 — reopening D59, D71, D103, D106, D157: `island()` reads outer contours and nothing else; everything inside an outer goes to `loose`

Decided by Federico, 23 October 2026, on G6c. `island()` returns, for each
island, its outer contour; every other piece — closed or open, inside or
outside the outer, a whole nested island — goes to `result.loose` with
`cluster_ref` set to the island it touches or lies in (D137). `island()`
never builds an inner.

Why. `island()` reads drawings (views, isometrics, sheets with notation),
where a closed loop inside an outer has no meaning the geometry can decide:
the cell of a strip crossed by slots, a logo letter, a hidden line that
closes on a view. Which closed loops to call inners was chosen by walking
cycles (`LoopFinder`: from the nodes in insertion order, each edge once,
the straightest way at a branch), so the answer depended on the order of
the entities in the file and on the frame (G6c: 22 of 31 drawings changed
with the order, 20 with a rigid motion). A planar-face reading would make
it deterministic, but deterministic is not meaningful: no face criterion
tells a hole from a cell without knowing what the drawing represents. That
is the consumer's call (the same split as D88/D90: topo reads structure,
the consumer reads meaning), and the consumer gets every piece, untouched,
in `loose`.

What goes: the inner loops and their machinery in `topo/core/island.py`
(`LoopFinder` on the rest, `_drop_boundary_duplicates` D103, the faces per
loop D106, the closed loops outside the chosen contour D71), the
`IslandReading` fields `inner_loops`, `outside_loops`, `off_faces` (clean
break, D140 surface is pre-1.0). A nested island no longer becomes an
inner of its host: its edges go to `loose` with the host's `cluster_ref`.
What stays: the outer face (D59, D100), spurs, outside, non-contour (D49)
and the nesting index, which now only decides `cluster_ref`. `heal()` is
untouched: in a flat part a closed loop inside the outer is a hole by
construction (D88 is snapbend's reading of it).

Consequences on the gate: G6c's inner families and G7's crossing inners
and inner roundtrip have no object any more; what remains of G6c is
whether the outers change with order or frame. The island goldens change
and are regenerated only after Federico has looked at them (non-negotiable
9). D147 (suspended) is moot for its inner half.

### D162 — a piece that closes by itself comes out of `island()` as one closed curve in `loose`; `anchor_texts` targets it

Decided by Federico, 23 October 2026, on the D161 follow-up. Among the pieces
`island()` puts in `loose`, the ones that close by themselves — one closed
segment (a circle, a full ellipse, a closed spline) or a chain where every
node has degree 2 — come out as one `ClosedCurve` (polygon, segments in ring
order), still in `loose` with their `cluster_ref`. Everything else stays one
`OpenCurve` per edge. `contour_shape` reads them like any contour; on a piece
that does not close it returns `None` (it used to crash). `anchor_texts`
targets them as `"loose[k]"` (`resolve_target` resolves it); loose closed
curves with a non-structural role (a frame marked by the caller) are not
targets.

Why. topo exposes its shapes, nothing more: the consumer finds its own
patterns (a bent sheet seen from the side, a counterbore's section) among
the loose curves and skips what already has a shape. A ring with only
degree-2 nodes has one cycle and no choice, so D161 holds: nothing depends
on entity order or on the frame. A chain with a branch stays open edges;
which cycle to see there is the consumer's. `heal()` is untouched.

Not done, on purpose: no new type, no new function, no path for a group of
open curves, no open loose curves as anchor targets (a leader tip on a
centre line would compete with the hole it crosses).

### D163 — a piece the border takes only in part leaves exactly its remainder in `loose` (G6b)

Gate item G6b, 25 October 2026. Every input piece comes out once: in a
contour or in `loose` (D137). Two readings broke it where the contour is
read from faces instead of a graph loop, because they marked as "taken"
only the edges lying *entirely* on the border:

- `island()`, outer from the union of faces (D100): an edge the border
  runs along only in part (a crossing shapely nodes and the planar network
  does not) gave its part to the contour (D106) and went whole to `loose`
  too. Measured on regr_01, anch_06, regr_04, anch_06_noframe: 21 stretches,
  up to 5 mm, within 1e-4 mm of the contour.
- `heal()`, the last-resort `polygonize` (no graph loop closes): no edge
  was taken at all, so every line came out twice (`rect_overlap` at tol
  0.01 and 0.05: outer right, all four lines whole in `loose`).

Rule. `rim.face_segments` now also returns which stretch of which edge
each border run used. An edge with a run is taken; `rim.off_rim` cuts it
at the ends of its runs and keeps, as new edges, the pieces that move away
from the border by more than `band` — the farthest point, not the
midpoint: a stub of length 2·band starts on the border and its midpoint is
only band away. An original end keeps its node. `heal()` applies the same
to every ring of every polygonize face (`rim.off_faces`) with
`band = tolerance`, so nothing farther than the tolerance disappears
(D143); `island()` keeps the rim band of D100 (2·GRAPH_EPSILON). Contours
do not change: only `loose`, which loses exactly the doubled length.

Two test rules made precise, because they confused two input pieces with
one piece output twice:
- `along_contours` (the "out once" invariant) ignores a stretch where the
  input itself has two pieces (a circle traced again by a polyline in
  anch_06): each comes out once.
- the fidelity test (G3) accepts an untouched spline that comes out *cut*,
  not refitted: pieces within 2e-6 of it covering it up to the rim band.
  regr_04 passed before only thanks to the doubled whole copy in `loose`.

Not done: the polygonize contours of `heal()` stay chains of `LineSeg`;
reading them along the edges like D106 would bring arcs back, but it is a
new behaviour, not a G6b fix.

### D164 — a short LineSeg with a free end is a tip, not a double node: it is not welded

Found by Federico on 25 October 2026 looking at the G6b review files:
`golden_islands/regr_01` read with `island()` had lost its top view since
the D152 draft (6fffe48, 22 October) — the plate outline did not close and
its five Ø19 holes came out as outers. The D152 review (23 October) did not
catch it.

Cause. The view is drawn as ~3500 LineSegs under 0.05 mm. Where an arc meets
a branch of two tessellated chains, a 0.03 mm LineSeg bridged them: one end
on the branch node, the other free, 0.004 mm from the arc's end.
`weld_degenerate_linesegs` (D56) deleted it and moved its free end onto the
branch node; the arc's end was then 0.026 mm from a node of degree 2, and gap
closing, which pairs free ends only, had nothing to pair it with. Before
D152 the unbounded union-find hid this by collapsing whole chains.

Rule. A candidate is welded only if both its nodes are touched by another
edge. Welding merges two nodes; a tip has only one, and welding it only
deletes geometry and moves a free end (against D143). The tip stays as a
real edge, and its free end meets the next free end through the normal gap
closing. Of the 31 island drawings only regr_01 changes (top view back as
one island, 630–1810 × 967–1032, holes inside it in `loose` per D161); the
suite and every heal golden are unchanged.

### D165 — the area of a contour is exact, integrated on its segments; it enters the gate

Decided by Federico, 25 October 2026. `area` is today `polygon.area`: the
area of the polygon discretized within `tol` (D145). Its chords lie inside
every convex arc, so the error has one sign (outers and holes both
underestimated, never compensating), is bounded by about `tol × perimeter`,
and the number changes with the tolerance the drawing is read at — a fact
about the reading, not about the part (a Ø20 hole at tol 0.01: 313.76
instead of 314.16).

Rule. By Green's theorem the area of a closed region is an integral over its
boundary, and topo knows the boundary exactly: the `segments`. Each
primitive contributes a closed form — a line its shoelace term, an arc the
same term on its chord plus the signed circular segment ½r²(Δθ − sin Δθ), an
ellipse its own closed form, a polynomial spline an exact polynomial
integral (a rational one by quadrature to machine precision). Holes subtract
as in D89. Exact *for the model* — the healed contour, gaps closed within
`tol` — which is the promise of D143.

Why before 1.0, against the D148 freeze: no name changes, but the value of a
public name does, by about 0.1 %. Changing what a number means after 1.0 is
worse than adding a name; the work is one function per primitive in
`topo/core/geometry/`.

**Implemented (G12, 25 October 2026).** `topo/core/geometry/integrals.py`:
`segment_moments` (area and first moments of one oriented primitive),
`ring_moments`, `ring_area`, `ring_centroid`. Line, arc, circle and ellipse
share one closed form (c + M cos t + N sin t, polynomials of degree ≤ 3 in
cos, sin); a polynomial spline is exact by Gauss with 2p points per knot
span; a rational one by Gauss halved until two levels agree to 1e-14.
`ClosedCurve.area` and the overlay voids of `Cluster.area` use it.

Two facts found on the fixtures (4144 heal curves, 1112 island curves):
- A healed contour may jump between one segment's end and the next one's
  start (a gap closed within `tol`, source coefficients kept, D143). The
  jump counts as its chord, as the polygon does implicitly; without it the
  area would change with where the part sits.
- The error of `polygon.area` has **one sign only on convex arcs**, not in
  general as written above: on an outer with concave fillets the chord lies
  outside the material and the polygon *over*estimates (44 of 223 golden
  values went down). The bound, |Δ| ≤ tol × perimeter, holds everywhere:
  largest golden change 1.17 mm² on a 178.7 mm perimeter.

Goldens: only the `area`/`area_mm2` fields were rewritten (223 values in 66
files), copied from a full regeneration; every other field kept as it was,
because the full regeneration also moved perimeters and WKT that were stale
from earlier decisions and are not this change. Orientation and the order
of contours (`polygon.area` in hierarchy, island, outer face) still use the
polygon: they leave with G13.

`main` → **0.22.3** (D155 micro bump: G6b closed by D163/D164, G12 by D165;
no public name changes, the value of `area` does).

### D166 — no shapely type in topo's public surface; `to_shapely` is an explicit conversion outside the model

Decided by Federico, 25 October 2026. `Contour.polygon` (and every public
field or return value typed with shapely) puts an external library's type in
topo's contract: if the core moves to Rust (ROADMAP) or shapely breaks
compatibility, topo's surface breaks for a reason that is not topo's.
shapely is a *representation* of the geometry, like DXF — and formats live
outside the model (D129).

Rule. A contour exposes topo's own types only: `segments` (the truth),
`bbox`, exact `area` and `centroid` (Green's integrals, D165), `contains(p)`
on the segments, and the ring's points discretized within a tolerance as
plain tuples. A caller who needs overlay, buffer or WKT converts explicitly
with `to_shapely(contour)`, which builds the polygon from those points and
keeps working whatever the core is written in. Inside topo shapely stays
what it is good at — spatial index, unions, polygonize — as an
implementation detail.

Measured on the consumers: about 120 `.polygon` lines in snapbend, snapdraw,
snapfence and smoother; most are `bounds`, `exterior`, `centroid`,
`contains`, `area`, with a direct replacement; nine are real shapely
operations (`buffer`, `symmetric_difference`, `wkt`) and go through
`to_shapely`. They adapt (D140). It breaks a public name, so it enters the
gate under Surface, done first together with G12.

**Implemented, step 1 (G13, 25 October 2026): the facts of a ring, on the
primitives.** `topo/core/geometry/rings.py`: `ring_bbox`, `ring_perimeter`,
`ring_points`, `ring_contains`, and `ring_jumps` (the chords of the gaps
closed within `tol`, now shared with `ring_moments`). `ClosedCurve` (so
`Contour`) gains `centroid`, `contains(point, tolerance=1e-6)` and
`points(tolerance=0.01)`; `bbox` is computed on the segments.
- `bbox` is exact: `segment_reach` on the two axes, so an arc or an ellipse
  reaches its true extreme instead of the nearest chord vertex. On the 4362
  heal contours of the fixtures the change is at most 0.0038 mm (within
  `tol`); no golden moved.
- `contains` is the **closed** region (decided by Federico): a point on the
  boundary within `tolerance` is inside. A measured point lying on an edge
  is on the part; the open-region reading would make the answer depend on
  the last float of a coordinate. Default tolerance 1e-6, the node grid
  (D113).
- How: winding number of the primitives seen from the point. A line sweeps
  its chord angle; an arc, circle or ellipse sweeps its chord angle plus a
  full turn in its own direction exactly when the point lies in the conic
  segment between arc and chord — tested in the conic's (cos, sin)
  coordinates, where it is the unit disc on the side of the arc's midpoint.
  A point on that chord is in the closed segment (the chord angle there is
  ±π and its sign is rounding noise). A spline sweeps the angle of a
  polyline within δ, refined only near the point: a polyline farther than
  2δ from the point cannot differ from the curve by a turn around it.
- Checked against the fine polygon (tol 1e-4) on every fixture contour:
  143 363 points away from the boundary, 0 disagreements.

**Implemented, step 2 (G13, 25 October 2026): direction and order from the
integral.** Every place where the polygon's area decided the direction or
the order of contours now reads the exact area on the segments: the
direction of a loop (`LoopFinder`, was `LinearRing.is_ccw`), the minimum
area of a contour (`loop_to_closed_curve`), the order of the containment
tree, the largest loop of an outer face and the face chosen against the
union (`outer_face`), the nesting of islands (`read_islands`), the
`min_area` filter of `split`, and the signed area of `regions`/`strips`
(concavity, inward normal). Left on polygons, by D167, because they compare
polygons with polygons or have no primitive: the union of faces and its
0.99 ratio, `orient` of the union's ring in `rim`, the largest piece of an
invalid ring in `polygon_builder`, every `contains`/`buffer` between curves,
and the validator's checks of the polygon itself (they move with step 3).

The order of clusters had a hidden defect: between congruent copies (equal
area) it was the rounding noise of the polygon area, so it changed with
where a part sits and with the discretization. **Rule** (`sort_clusters`,
one function for `heal` and `island`): exact outer area rounded to 1e-6 mm²,
largest first; at equal area the bbox corner `(xmin, ymin)` — between two
congruent copies the position is the only fact that tells them apart.
Goldens: two drawings with identical parts (`sviluppo_multiparte`, six
copies; `example_4_polylines`, four) had their equal parts recorded in the
noise order. Proved a permutation before touching them (each new part
matches one golden within 1 mm², same area and inner count); the golden
files were reordered, not regenerated. A test fixture of `test_loops` built
a degree-1 spline with no knots, which the polygon tolerated and the
integral refuses: the fixture now has its clamped knots.

**Implemented, step 3 (G13, 25 October 2026): `topo.to_shapely`, and the
inside reads no `.polygon`.**
- `topo.to_shapely(item, tolerance=None)` (`topo/io/shapes.py`, a
  conversion like a format, D129): closed curve → `Polygon`, `OpenCurve` →
  `LineString`, `Cluster` → its material. `tolerance=None` is the polygon
  the reading used, so a consumer sees the same vertices topo's own
  containment tests see; a number rebuilds it from the segments.
- A cluster converts by the **even-odd rule** of `area` (D89): every
  contour at even depth is a shell, its odd-depth children are its holes,
  overlay voids are subtracted — `MultiPolygon` when an island sits in a
  hole. Why: it is the same parity `area` already uses, so the shapely area
  and `cluster.area` agree within the discretization, and no contour is
  lost: a depth-2 island is a piece of its own. The old
  `polygon_with_holes` put every inner as a hole, so an island inside a
  hole made a polygon shapely itself calls invalid. Whether an island is
  tied to the rest (tabs, bridges) is a consumer's choice, not geometry.
  Federico was unsure; the argument above was given and he confirmed it
  the same day ("ok, pari-dispari va bene").
- Inside topo every read of a curve's polygon goes through one function,
  `curve_polygon` (`core/primitives/polygon_builder.py`): the polygon the
  reading gave, else built once from the segments and kept on the object,
  `None` for an open curve. tools (anchor, inject, split, rotate), io
  (text, view_model, exporter, inspect), the validator and the hierarchy
  use it; step 4 only has to change where the polygon lives. Suite time
  unchanged (182 s): nothing is built twice.
- `to_json`/`build_metadata`: `outer_perimeter`/`inner_perimeter` are exact
  (`ring_perimeter`), no longer the polygon's (a Ø20 hole: 62.832 instead
  of the chords' shorter length). No golden reads them.
- Still on polygons, by plan: `CoveredRectangle`, `OuterFace.polygon` (step
  5), the `polygon=` handed to the constructors and the D90 overlay
  contract (step 4).

**Implemented, step 4 (G13, 25 October 2026): the model carries no shapely
type.** Agreed with Federico point by point.
- `ClosedCurve.polygon` and the `polygon=` argument are gone. The polygon a
  reading built (fused with the planar network in `island`, `buffer(0)` of
  a dirty ring in `heal`) is a private cache, `_polygon` (not in `__init__`,
  `repr` or `==`), set by `with_polygon` and read by `curve_polygon`, both
  in `core/primitives/polygon_builder.py`. `dataclasses.replace` drops it,
  so a rotated contour gets its own (`tools/rotate`). Why private and not
  removed: the polygon is how topo answers questions between many curves
  (D167); rebuilding it from the segments would change island's vertices
  and cost time for nothing.
- A consumer builds a curve from `segments` only (snapbend's `Hole` stops
  passing `polygon`) and asks `topo.to_shapely(curve)` when it needs one —
  that returns the cached polygon, built by nobody else. shapely is a
  dependency of topo, so importing it costs a caller nothing new; a consumer
  that imports it itself declares it, because topo's contract no longer
  promises it (a Rust core could drop it).
- `Cluster.polygon_with_holes` is gone: `topo.to_shapely(cluster)` replaces
  it (even-odd, step 3). `ClosedCurve.area`/`bbox` no longer fall back to a
  polygon: no segments, no geometry (0).
- The D90 overlay contract: a void is `is_void = True` plus the `segments` of a
  closed ring (no `polygon`). A renderer draws a contour closed if it is a
  `ClosedCurve`, its item `is_void`, or its segments close a ring head to
  tail within 0.01 (`topo.model.feature_closed`, used by `to_dxf` and
  `to_view_model`; `ring_closes` in `core/geometry/rings.py`). Why the
  third case: an overlay mark that is a closed ring but not a void (a
  circle a consumer marked) was closed before because it carried a polygon;
  its segments say the same thing. A consumer that wants a closed ring as
  separate primitives no longer can — a geometric fact wins over a
  convention (non-negotiable 8).
- `Cluster.to_dict` writes the same lists of `(x, y)` as before (the
  reading's polygon vertices, ring closed), read through `curve_polygon`:
  values unchanged, no golden touched.
- `heal` builds no `ClosedCurve` without segments any more
  (`loop_to_closed_curve` returns `None`); the hierarchy tracks classified
  proxies by identity, not by their polygon's.
- Tests and scripts read `topo.to_shapely(x)` where they read `x.polygon`;
  fixtures build contours from `topo.geometry.polygon(...)`. Suite 2723
  passed, 183 s.

**Implemented, step 5 (G13, 25 October 2026): `topo.geometry` and
`topo.steps` take and return no shapely type.** Names agreed with Federico.
- `splits_polygon(polygon, …)` → `splits_contour(contour, start, end,
  reach=0.0)`: a contour, a ring of `segments` or the segment list. Renamed
  because the argument changed: a caller passing a polygon gets a
  `NameError`, not a silent wrong answer. On the primitives (D167):
  `rings.ring_split_by_chord` cuts the chord where it meets the boundary
  (`intersections`, jumps included) and a stretch between two meets whose
  midpoint is strictly inside cuts the region. Why that is enough: a ring
  is simply connected, so a cross-cut from boundary to boundary always
  splits it; a touch, or a stretch along the boundary, has no inside
  midpoint. A meet counts as on the boundary by construction (on splines
  and ellipses `intersections` is only within 1e-4; re-testing it at 1e-6
  is what failed first).
- `bridged_runs(segments, bridges)`: `bridges` are contours (or rings of
  segments), a gap is bridged if `rings.ring_covers_chord` (ends and every
  piece's midpoint in the closed region — the old `buffer(1e-6).covers`).
  A stroke, here and in `are_collinear`/`group_collinear_lines`, is a
  `(start, end)` pair or anything with `start`/`end`; a `LineString` is no
  longer read.
- Both checked against shapely on the eight rings of `test_rings` (both
  directions, 150 random chords each, tangent chords left out): same
  answer everywhere. Then over every fixture in `tests/examples` (heal,
  12 random chords per contour, tangent chords left out): 4550 contours,
  54 600 chords, 0 differences; 454 contours skipped because their fine
  polygon is not valid for shapely (rings that touch themselves).
- `CoveredRectangle` carries `bbox` (floats) and `items`; `segments` gives
  the four sides; `area`/`long_side`/`short_side`/`ratio` read the bbox.
- `OuterFace.polygon` is private (`_polygon`, read by `curve_polygon`), as
  on contours.
- `topo.steps.polygonize_edges` + `polygons_to_curves` → one step,
  `polygonize_to_curves(edges, tolerance) -> list[ClosedCurve]`. The two
  stay inside `core/healing/steps.py` because `heal`'s fallback also needs
  the faces for `off_faces`; only the merged step is public.
- Found on the way: the fallback gave the OUTER curve the face polygon
  *with its holes* while its segments are the outer ring only, so
  `to_shapely(outer)` was 84 mm² for a 100 mm² ring. Its polygon is now its
  ring (`Polygon(poly.exterior)`); the holes are their own INNER curves. No
  golden moved.
- Guardian `tests/unit/test_no_shapely_surface.py`: no annotation of any
  name in `__all__` of `topo`, `topo.geometry`, `topo.steps`, `topo.model`,
  `topo_dxf` names a shapely type (except `to_shapely`), and walking every
  public field and property of what `heal`, `island`, `split`,
  `outer_face`, `polygonize_to_curves`, `covered_rectangles` and
  `contour_shape` return finds no shapely object. Suite 2890 passed, 184 s.

### D167 — topo's code is written ready for a Rust port; the tests judge the port, not a reading of the Rust

Decided by Federico, 25 October 2026. He will not learn to read Rust well,
so "start when Federico can judge what he reads" (ROADMAP, 19 October) would
block the port forever. Two rules replace it.

**The judge is the suite.** A Rust function replaces its Python twin only
when, on the same drawings, it passes the same goldens, invariants and
two-way fidelity tests (D152). Federico judges the output DXF by eye, as
today; nobody has to read the Rust to accept it. The Python twin stays until
then.

**New geometry code is written port-ready** — the shape `rim` was already
written in (D118):
- pure functions over plain data (primitives, tuples of floats);
- typed results, no mixed return types; exceptions, not `None`/`False`;
- explicit dispatch per primitive type (an `enum` + `match` there);
- no shapely or numpy in a signature (D166); inside, only for operations
  with a direct Rust counterpart.

**The primitive is the truth; discretization is a view.** This is how the
two choices that look opposed — exact math per primitive (D165) and one
discretization grid per curve (D145, D153) — fit together. A question about
one curve (length, area, centroid, bbox, distance, a point on it) is answered
on the primitive, exactly. A question between many curves (who touches whom,
which faces close) is answered today on polygons; the grid exists so that
the same curve always gives the same vertices and the polygons do not
invent gaps or overlaps. Neither replaces the other. Where an exact
intersection exists (line, arc, circle among themselves) it may replace the
polygon later; between splines the numbers stay numeric anyway. The node
grid (D113, 1 µm) is what makes the topology integer-ready (ROADMAP, the
interface "same node? / where do they cross?").

### D168 — G13 closed: what replaces each shapely name, for the consumers; 0.23.0

Closed 25 October 2026, steps 1–6 of D166 ("Implemented" paragraphs there).
topo's public surface — `__all__` of `topo`, `topo.geometry`, `topo.steps`,
`topo.model`, `topo_dxf` — takes and returns no shapely type except
`topo.to_shapely`, the explicit conversion. `test_no_shapely_surface`
keeps it so: annotations of every public name, and every public field and
property of what the readings, the steps and the geometry facts return.

**What the contract says about shapely.** It is a dependency of topo
(installed with it), not a promise of topo: a consumer that calls shapely
itself declares it in its own dependencies, because a Rust core (D167)
could drop it. A question about one contour is a fact of the contour; only
overlay, buffer, WKT go through `to_shapely`.

**Old → new**, for snapbend, snapdraw, snapfence, smoother (they adapt,
D140; topo writes nothing in their repos):

| before | now |
|---|---|
| `c.polygon.area` | `c.area` (exact, D165) |
| `c.polygon.bounds` | `c.bbox` (exact: arcs at their true extremes) |
| `c.polygon.centroid` | `c.centroid` (a tuple; `ValueError` if no area) |
| `c.polygon.contains(Point(p))` | `c.contains(p)` (boundary within 1e-6 counts as inside) |
| `c.polygon.exterior.coords` | `c.points(tolerance)` (first point not repeated) |
| `c.polygon.exterior.length` | `sum(topo.geometry.segment_length(s) for s in c.segments)` |
| `c.polygon.buffer(…)`, `.wkt`, `.symmetric_difference(…)`, `a.polygon.contains(b.polygon)` | `topo.to_shapely(c)` and the same shapely call |
| `Contour(polygon=p, segments=s, …)`, `Hole(polygon=…)` | `Contour(segments=s, …)` — no `polygon` argument |
| `cluster.polygon_with_holes` | `topo.to_shapely(cluster)` (even-odd: an island in a hole is material) |
| overlay void: `is_void` + `polygon` | `is_void` + `segments` of a closed ring |
| overlay contour drawn closed because it has `polygon` | closed if `ClosedCurve`, `is_void`, or its segments close a ring (`topo.model.feature_closed`) |
| `topo.geometry.splits_polygon(cluster.outer.polygon, a, b, reach)` | `topo.geometry.splits_contour(cluster.outer, a, b, reach)` |
| `topo.geometry.bridged_runs(pieces, [i.polygon …])` | `bridged_runs(pieces, [i …])` — contours as bridges |
| a stroke as `LineString` (`group_collinear_lines`, `bridged_runs`, `are_collinear`) | `(start, end)`, or anything with `start`/`end` |
| `CoveredRectangle.polygon` | `.bbox`, `.segments` (`to_shapely(rect)` if a polygon is needed) |
| `OuterFace.polygon` | `topo.to_shapely(face)` |
| `topo.steps.polygonize_edges` + `polygons_to_curves` | `topo.steps.polygonize_to_curves(edges, tolerance)` |

Values that moved besides names: `Result.clusters` order is deterministic
(exact area, then bbox corner — step 2); JSON perimeters are exact (step
3); `bbox` is exact everywhere it is read.

`main` → **0.23.0** (D155: public names removed, second digit).

### D169 — dependencies are replaceable details behind the API; one is replaced, or topo ported, only on a measure ✅

Federico, 25 October 2026, after weighing "numpy as a heavy dependency" and
"a Rust core with a Python API". D167 says how a port is judged; this says
when a dependency goes and why not now.

**Why not now.** Dropping numpy saves 0 MB: shapely requires it, and so does
ezdxf behind `topo_dxf`, so every DXF user installs it anyway. topo's own
numpy is two files (Gauss-Legendre nodes in `integrals`, small least-squares
systems in `points`). What shapely still does is noding thousands of edges,
building faces (`polygonize`, union) and the spatial index — the numerically
hard part, where GEOS has years of fixes a hand-written module would have to
rediscover on real drawings. Small pure-Python geometry libraries do points
and vectors, not noding or faces.

**What makes them replaceable is the API, so that is what is kept.** No
shapely or numpy type in topo's public surface: no signature names one, and
no value reachable from what the readings, steps and facts return is one —
primitives store plain Python floats whatever they are built from (an ezdxf
polyline gave `np.float64` coordinates; `_plain` in `segments.py` converts
at construction). `test_no_shapely_surface` guards both libraries.

**When.** After 1.0, piece by piece, each piece accepted as D167 accepts a
port (same goldens, invariants, fidelity on every fixture): topo's direct
numpy; the spatial index (a bbox index of topo's); then `polygonize` against
topo's loop finder. Noding stays with GEOS until a real case needs otherwise.
A Rust core is started on one of two measured reasons: reading time on real
drawings, or a host without Python (a CAM kernel's SDK). The first step for
either is an inventory: each shapely/numpy operation used → what replaces it.

### D170 — segments mirror about any line and scale uniformly; no general affine map ✅

Federico, 26 October 2026, triaging pippo's request (`../pippo/TODO.md`,
`## Richieste a topo`): a view not drawn 1:1 needs its profile scaled, and a
flat-pattern prototype moves each flange with a rigid motion that includes a
mirror. Both are plane geometry with no process in them, so they are topo's.

**What enters.** On all five primitives, next to `rotated`/`translated`:
- `mirrored(origin=(0, 0), angle=0.0)` — the line through `origin` at
  `angle` radians. The defaults are the x axis, so every existing call is
  unchanged, value for value: no alias, no break. An arc's angles go to
  `2·angle − a` and its direction reverses; an ellipse's parameters change
  sign and its direction reverses on any axis (a reflection reverses the
  +90° turn that derives the minor axis from the major one); a spline
  mirrors its control points (a B-spline, rational too, is affine-invariant).
- `scaled(factor, origin=(0, 0))` — uniform, `factor > 0` and finite,
  else `ValueError`. Radius, ellipse axis vector and spline control points
  scale; angles, parameters, `ratio`, knots and weights do not. A negative
  factor is a rotation by π plus a scale, and is asked for that way.

Each returns a new segment **of the same type**, exact: the image of the
curve, not of its discretization. Off the x axis a mirrored arc's vertices
lie on the new arc's own grid (D145), not on the mirror of the old vertices.

**What does not.** A non-uniform scale or a general affine matrix: it maps a
circle to an ellipse and an arc to an elliptical arc, so an `ArcSeg` would
have to change type or be approximated, and the result would no longer be
"the same segment, moved". A one-call similarity type was also left out:
chaining (`s.mirrored(o, a).rotated(t).translated(dx, dy)`) is already one
expression and composes exactly; a matrix type would add a check that the
matrix is a similarity and nothing else.

**Why methods, not `topo.transform.scale(seg)`.** Each primitive knows how
it maps (an arc's radius, an ellipse's vector, a spline's control points);
a free function would have to dispatch on the segment type, which is what
the methods already are. `rotated`/`translated`/`mirrored` already lived
there. Moving a whole `Cluster`/`Result` (as `rotate_result` does) was not
asked for: it waits for a caller.

The other pippo request — union of contours sharing a border — is not
triaged yet (Federico: another time).

`main` → **0.23.1** (D155: names added, none removed or renamed — `mirrored()`
gains defaulted parameters, `scaled()` is new — so the third digit).

### D171 — `geometry.contour_union`: two rings united, shared border included ✅
Federico, 26 October: implement pippo's second request (union of contours
that share a border), triaged in D170 as "another time".

**What it does.** `contour_union(contour, other)` returns the rings of the
boundary of the union, largest first. Outers keep `contour`'s direction; a
hole closed between the two runs the opposite way. Two rings that are apart,
or touch in one point, stay two rings. It is the counterpart of
`contour_minus` (D118) and is built from the same parts: cut both rings, keep
each piece by the side of the other ring its points fall on, chain the kept
pieces.

**The shared border.** A piece of one ring that lies on the other ring is
matched to the other ring's piece with the same ends and the same middle
point. Both rings are first brought to the same direction. So a matched pair
running opposite ways means the interiors are on opposite sides: the two
pieces sit side by side, and both go. A pair running the same way means the
interiors overlap there, and the piece stays once. A piece on the border with
no such twin raises `ValueError`. That piece runs along the other ring without
coinciding with it, and the union has no exact border there.

**Why it is exact on every primitive.** Two overlapping lines or arcs cross
in no point. The cuts are therefore the crossings plus the ends of the other
ring's segments: an overlap always starts and ends at an end of one of the two
segments. A ring's own ends are not cuts, because a circle's end (its angle 0)
is a convention, not a node. Identical splines and ellipses are not crossed
against each other. Their discretizations would give a crossing at every
vertex.

**The output is a new contour.** Where the boundary goes on along one line
or one circle, as with two squares side by side or two half-disks, there is
no corner, and the pieces become one (`merge_runs`, D95). This is what pippo's
`cancel_on_line` did by hand, for straight borders only.

**Fixes found on the way.**
- `_chain` gains `inside_left`. At a node where two pieces leave (a touch in
  one point), it takes the one that encloses the narrowest wedge of the
  region, so two touching rings stay two rings and not a figure eight. A piece
  that leaves tangent and backwards counts as the full turn.
- A piece's side is read at its middle point and, if that point is on the
  border (a touch exactly there), at a third and two thirds of its length.
  The middle alone made a circle tangent at its angle π look like a shared
  border. `cut_by` and `contour_minus` use the same test.
- `shape.merge_runs` joined two arcs across angle 0 into an arc of zero
  sweep, because it took the second arc's end angle as it stood. It now adds
  the two sweeps. This was latent in `island()`.

`main` → **0.23.2** (D155: a public name added, third digit).

### D172 — `promote` takes several curves as one item ✅
Federico, 30 October: triage snapdraw's request (its TODO, `## Richieste a
topo`). A feature with a seat (a hole and its counterbore) is two closed
curves in `loose` and one thing for snapdraw, so `tag_features` removed the
curves from `loose` by hand instead of calling `promote` (snapdraw D39).

**Why it enters topo.** It is not a reading: what the curves are stays the
caller's. It is D137's promise — a curve is never in two places and never
lost — applied to a group. Done by hand in a consumer, that promise is no
longer kept by topo.

**What it does.** `promote(result, curves, cluster, name, item=None)`:
`curves` is one curve or a sequence. All checks run before anything changes,
so a failure leaves `result` as it was: a curve not in `loose`, a curve given
twice, an empty sequence, a foreign cluster raise `ValueError`.

**`item` is required for more than one curve.** With one curve the curve
itself is a fair item: it carries geometry and role. A list of curves says
nothing about what they are together, and the only reason to group them is
that the caller made one object of them. So that object is asked for, not
invented.

Positional calls are unchanged (the parameter was renamed `curve` →
`curves`; no caller passed it by keyword). `main` → **0.23.3** (D155).

### D173 — reopening D137's placement: `promote` becomes a method of `Result` ✅
Federico, 30 October, asking whether `promote` is a tool. It is not.
`tools/` holds stages that compute something on a Document/Result (`split`,
`anchor_texts`, `strips`). `promote` computes nothing: it moves an object
between two containers of `Result` (`loose` → `cluster.detected`) and keeps
D137's promise that a curve is never in two places and never lost. That
promise belongs to `Result`, so `Result` keeps it, the way `DetectedFeatures`
keeps its own `add`. It imports only `model` types, so the dependency rule
(D44) is untouched.

**Why now.** After 1.0 removing `topo.promote` is a break (2.0); adding
`result.promote` beside it in a 1.x would leave two ways to do one thing.
The ARCHITECTURE tree did not list `tools/promote.py` at all, which is how
the question came up.

| old | new |
|---|---|
| `topo.promote(result, curves, cluster, name, item=None)` | `result.promote(curves, cluster, name, item=None)` |

Consumers to update in their own sessions: snapbend (`flat/detect.py`, two
calls), snapdraw (`tag_features`, still to adopt D172). `main` → **0.24.0**
(D155: a public name removed, second digit).

### D174 — reopening D148: the gate gets G14, one alignment of the API with mature-library practice ✅
Federico, 30 October. topo has bumped 0.x.0 for a long time, because each
step in a consumer showed that some name should be shaped differently, and
the name was changed. After 1.0 that must not continue as a major bump every
week, and "then it is a 2.0" is not an answer to a design wish: it only moves
today's churn to the first digit.

**The yardstick.** The consumers today (snapdraw, snapbend, smoother, pippo,
snapfence) are all Federico's, so how they call topo is biased evidence. The
surface is judged once against how a mature library designs and evolves its
API. The closest case is scikit-learn: years at 0.x, then a 1.0 that declared
the surface stable rather than breaking it, with a written deprecation policy
from then on.

**Why in the gate.** Before 1.0 a break costs nothing. After 1.0 every fix
becomes a deprecation to carry. Federico: "ho bisogno di essere più
tranquillo possibile alla release".

**Bounded.** Three steps (TODO.md G14): the rule, read by Federico before it
is written; one pass over the public names against that rule only, giving a
table he decides on, with all breaks in one release; tests for whatever the
machine can check. No new names, no rewrites.

Also: while the gate is open, consumer requests go to "after 1.0", which is
what D158 already says. D172 should have gone there, and entered by mistake.

### D175 — G14 step 1: what is public, the compatibility promise, the form rules ✅
Federico, 30 October: "la cosa migliore per uno come me. non voglio
rilasciare la 2.0 tra 6 mesi". The model is scikit-learn's, and step 2 of
G14 measures every public name against this entry only.

**A. What is public.** The names in `__all__` of `topo`, `topo.geometry`,
`topo_dxf` and of the public submodules, with their public attributes and
methods, each with a card in `docs/API.md`. A submodule, or a name in it, is
public if a user meets it in a result or needs it to build input. The
building blocks of an algorithm are not. Everything else is internal and
changes freely. Applied: `primitives` public; `model` public for the types a
user meets, the rest judged name by name; `steps` (the pieces of `heal`) goes
to experimental, because making it stable would freeze how the algorithm is
built inside, while the recipes thread is still open.

**B. The promise (scikit-learn's model, not strict semver).**
- Patch 1.0.x: fixes only.
- Minor 1.x.0: additions and deprecations. A name that changes shape arrives
  under its new form; the old one stays and emits `FutureWarning` for two
  minors, then goes, in a minor.
- Major: none planned. Removing a deprecated name is not a reason for one.
- A break is: a name removed or renamed, a default changed, a return type
  changed, a documented behavior changed. Making a result honor the
  documented invariants (D143) is a fix.
- Every deprecated name carries the version it goes in, and a test fails
  when topo reaches that version and the name is still there. For one
  person, removal must not depend on anyone's memory.

**C. Experimental.** `topo.experimental` (or a name declared outside the
stable part, as D133 does): the promise does not apply. What is not sure at
1.0 goes there instead of being half-fixed. Promoting a name to stable is an
addition, so it is done in a minor; the old experimental name stays as a
warned alias for two minors.

**D. Form rules** (the list for step 2, and only this list):
1. Data positional, options by name only (keyword-only). The data is what a
   function works on; an option is how it works. An option added later
   breaks no call. Today `island` does this and `heal` does not.
   (scikit-learn made it mandatory at 1.0, SLEP009.)
2. One way to do one thing: no duplicates.
3. Mutation is declared: a function returns a new object, or mutates its
   argument and says so. (pandas removed `inplace` for lack of this.)
4. A method when it keeps an invariant of its object (`Result.promote`,
   D173); a function when it computes. (shapely 2.0.)
5. Consistent names: verbs for functions, nouns for types and properties,
   one name for one concept everywhere.
6. Typed, stable returns: no loose dicts, no silent `None` instead of an
   error.
7. Standard errors: `ValueError`/`TypeError` with a message that says what is
   wrong.
8. Every public name has its card in `docs/API.md` and an English docstring
   (G9).

Step 2 of G14 will show that the real surface is about 150 names with the
submodules, not 97.

### D176 — G14 step 2: the public surface measured against D175, all breaks in one release ✅
Federico, 30 October, after the pass over every public name (table in his
debug folder): points 1–10 approved, point 11 left for later. Measured
against D175's rules only, not against how the consumers call topo.

**What changed, and the rule behind each.**
1. *Options by name only* (rule 1). Every public function, method and
   container: data positional, options after `*`. Containers use
   `dataclasses.KW_ONLY` after their data fields (`Cluster(outer, *, ...)`,
   `Contour(role, segments, *, ...)`, `Text(position, text, *, ...)`,
   `RoleRule(role, *, ...)`, `RoleStyle(*, ...)`, `EdgeStyle(*, ...)`, `Edge(role,
   start, end, segment, *, style)`). Primitives unchanged, their arguments are
   all data; their methods follow the rule (`discretize(*, tolerance)`,
   `rotated(angle, *, origin)`, `mirrored(*, origin, angle)`, `scaled(factor, *,
   origin)`). A tolerance is an option even when required, as `island`'s
   `max_gap` already was. One exception, declared: `DetectedFeatures.get(name,
   default)` keeps `dict.get`'s protocol.
2. *A mutating function returns `None`* (rule 3): `anchor_texts`, `inject`,
   `validate_result`. They mutated and returned the same object, which reads
   like a copy.
3. *`split` no longer renames the caller's clusters* (rule 3): each part's
   cluster is a copy with its label. It still appends the drop notices to
   `result.warnings`, declared: when every part is dropped there is no part
   to carry them, and a silent drop is forbidden (non-negotiable 7).
4. *`set_schema` removed* (rule 3, global state): the schema is `schema=` on
   `build_metadata`, `save_json`, `to_json`, `save_xml`,
   `topo_dxf.write_metadata_to_dxf`.
5. *One way to skip layers* (rule 2): `ignore_layers` (substring) removed;
   `skip_layers` takes exact names or a function `name -> bool`, which covers
   substring, regex and any algorithm on the name. Federico asked for the
   substring case not to be lost.
6. *Names* (rule 5): `validate` → `validate_document` (pairs with
   `validate_result`, `inspect_document`/`inspect_result`);
   `load_dxf(flatten_z_flag=)` → `flatten_z=`.
7. *`geometry.track_shape_type` removed* (rule 6): it returned `"line"`/`"curve"`
   for `len(pts) == 2`.
8. *`topo_dxf.split_to_files` removed* (rule 2): `heal` → `split` → `to_dxf` in
   one call with eleven options copied from those functions. The loop is four
   lines of the caller's (script 07).
9. *`topo.experimental`* (D175 C): `topo/steps.py` became
   `topo/experimental.py`, with `read_island`, `read_islands`,
   `IslandReading`, and every name that was "experimental, importable as
   `topo.<name>`, not in `__all__`" (`simplify_points`, `rotate_*`,
   `to_nester_input`, `to_view_model`, `to_svg`, `save_svg`, `to_text`,
   `save_text`) and the strips of D142 (`facing_boundaries`, `gap`, `link`,
   `unconnected_regions`, `open_boundaries` and their types), which consumers
   imported from the internal `topo.tools.strips`. Experimental is one place
   now, not a comment in `__init__.py`.
10. *Internal names*: none after all. `feature_closed`, `feature_role`,
    `resolve_role`, `DEFAULT_NODE_TOLERANCE`, `CONSUMER_ROLE_STYLE` are used by
    `topo_dxf`, i.e. by anyone writing a format adapter: public by D175 A. They
    get their cards in G9.

**Found on the way.** `topo_dxf.write_metadata_to_dxf` caught every
exception and printed a warning without writing anything (rule 7): it now
raises `ValueError` when there is no `OuterContour` entity.

**Left for later (point 11).** `Text.target`/`references` point to elements by
a string path (`"clusters[0].inners[3]"`) that breaks when the result
changes; `resolve_target` turns it back. Fixing it means pointing at the
object, a rewrite outside G14's bound. To decide with Federico: experimental
now and fixed in a 1.x, or fixed before 1.0.

**For the consumers** (each adapts in its own session):

| old | new |
|---|---|
| `f(data, opt_value)` | `f(data, opt=opt_value)` — every option by name |
| `r = topo.anchor_texts(result)` / `topo.inject(...)` / `topo.validate_result(...)` | call, then use `result` |
| `topo.split(...)` renaming `result.clusters[i].label` | read the label from `part.clusters[0].label` |
| `topo.set_schema(s)` | `schema=s` on each call |
| `load_dxf(ignore_layers=["x"])` | `skip_layers=lambda n: "x" in n.lower()` |
| `load_dxf(flatten_z_flag=)` | `flatten_z=` |
| `topo.validate(doc)` | `topo.validate_document(doc)` |
| `topo.geometry.track_shape_type(pts)` | `len(pts) == 2` |
| `topo_dxf.split_to_files(doc, folder, ...)` | `heal` → `split` → `to_dxf(...).saveas()` |
| `topo.steps.<x>`, `topo.read_island(s)`, `topo.IslandReading` | `topo.experimental.<x>` |
| `topo.to_svg`/`save_svg`/`to_view_model`/`to_text`/`save_text`/`simplify_points`/`rotate_*`/`to_nester_input` | `topo.experimental.<same>` |
| `from topo.tools.strips import ...` | `topo.experimental.<name>` |
| `seg.mirrored(o, a)`, `seg.rotated(t, o)`, `seg.discretize(tol)` | `seg.mirrored(origin=o, angle=a)`, `seg.rotated(t, origin=o)`, `seg.discretize(tolerance=tol)` |

`main` → **0.25.0** (D155: public names removed and renamed, second digit).

### D177 — G14 point 11: `Text.target`/`references` are the objects, not paths ✅
Federico, 30 October, reopening D174's bound ("no rewrites") for point 11
only. Options weighed: experimental now and fixed in a 1.x; a stable string
kept honest by `promote`/`split`; a stable id on every element; removal. He
chose the fix before 1.0.

**Why.** A path such as `"clusters[0].inners[3]"` or `"loose[4]"` is a
position in one list at one moment. `Result.promote` takes curves out of
`loose`, so `"loose[k]"` written earlier silently named another curve.
`split` left the paths as they were, so in a part they named nothing or the
wrong curve. And the collections of `cluster.detected` are a consumer's:
any reorder there after `anchor_texts` moved the paths, and topo cannot
remap what it does not manage. D66's argument ("it survives serialization")
did not hold either: no writer emits `target`/`references`, only the text
report reads them. A reference to the object is right whatever happens to
the lists around it.

**Still geometry (D138).** What is anchored is a fact between a point and an
element: the nearest boundary within `distance`, else the smallest closed
element covering the point. Whether the text is a dimension or a callout is
still the consumer's reading; only the 0.5 default knows about drawings, and
it is an option.

**What changed.**
- `Text.target: object | None`, `Text.references: list` — the element
  itself (a contour, an item of `detected`, a closed curve of `loose`). Both
  `repr=False, compare=False`: a contour in a text's repr is noise, and two
  texts are equal for what they are, not for what was anchored to them.
- `pointer_target`/`measured_references` return objects. Their `distance`
  is keyword-only (rule 1, missed in D176). Ties are broken by the element's
  place in the result as before, so the golden of `golden_anchoring/` is
  unchanged.
- `resolve_target` removed: nothing to resolve.
- `split` relinks each text to its part: contours and features are the same
  objects, loose curves are copies and the references follow the copies; an
  element of another part is not in that `Result`, so `target` becomes
  `None` and the reference leaves `references`. The caller's texts do not
  change.
- `deepcopy` of a `Result` keeps the links (the memo maps them to the copies).
- The text report labels the object (`C1`, `C1.3`, `C1.holes[2]`, `loose[4]`).

**For the consumers:**

| old | new |
|---|---|
| `topo.resolve_target(result, t.target)` | `t.target` |
| `t.target == "clusters[0].outer"` | `t.target is result.clusters[0].outer` |
| the collection from the path (`path.split(".")`) | look the object up: `item in cluster.inners` by identity, `cluster.detected.items()` |
| `pointer_target(r, t, 0.3)` | `pointer_target(r, t, distance=0.3)` |

`main` → **0.26.0** (D155: a public name removed, second digit).

### D178 — G14 step 3, rule 1: what D176's pass missed, and the test that holds it ✅
Federico, 30 October, after D177 found `distance` still positional on
`pointer_target`/`measured_references`: "come mai è stata violata la regola?
può esserci qualche altra violazione?"

**Why D176 missed names.** Its scan (the table in the debug folder) had
three holes. (1) A name whose "decision" column already held another point
was skipped for rule 1: `pointer_target`/`measured_references` were "11", and
point 11 was postponed whole. (2) It read functions and constructors, not
methods: the primitives' methods were fixed by hand, the model's were not.
(3) It listed only parameters with a default, while D176 itself says a
required tolerance is an option.

**Found and fixed** (stable surface, keyword-only now):
`Contour.from_segments(segments, role, *, depth, parent, tolerance)`,
`Edge.of(segment, role, *, style)` (as `Edge(...)` already was),
`geometry.covered_rectangles(items, *, min_side, ...)` (a threshold).
Kept positional as data, on purpose: `to_dxf(result, source_doc)` (the
document it writes onto), `role_to_dxf_layer(role, element)` (what goes to
the caller's function), `resolve_role(rules, name, style)` (the edge's style,
like its name), `dash_line(start, end, head, tail)` (the dashes are what it
makes), `sub_segment(seg, a, b, via)` (a point). `topo.experimental` keeps
positional options (`to_svg` has 11): outside the promise, fixed when a name
is promoted.

**The test** (`tests/unit/test_surface_rules.py`): every public callable of
`topo`, `topo.geometry`, `topo.primitives`, `topo.model`, `topo_dxf`, methods
included, declares its positional parameters in one table, all data. A new
name or parameter fails until someone decides data (add it to the table) or
option (after `*`): a person still judges, but can no longer forget. A name
that reads like an option (`tolerance`, `distance`, `eps`, `min_*`,
`include_*`, …) fails even if declared, except the declared
`DetectedFeatures.get(name, default)`. Checked: undoing the `Edge.of` fix
turns it red on that parameter.

Step 3 stays open for the other machine-checkable rules: rule 8 (card in
`docs/API.md`, English docstring — with G9) and B's removal test, which has
nothing to hold until the first deprecation.

**For the consumers:**

| old | new |
|---|---|
| `Contour.from_segments(ring, role, d, p, tol)` | `Contour.from_segments(ring, role, depth=d, parent=p, tolerance=tol)` |
| `Edge.of(seg, role, style)` | `Edge.of(seg, role, style=style)` |
| `covered_rectangles(items, 50)` | `covered_rectangles(items, min_side=50)` |

`main` stays **0.26.0**: not pushed yet, same release as D177.

### D179 — G6c: D100's union of faces decides contacts by distance, not by a grid cell ✅

What was left of G6c after D161: on `anch_08` (and `anch_08_noframe`) one outer
changed when the drawing was turned by 0.7 rad — 48 mm² apart, two small faces
at the two ends of an isometric part. Order of the entities, translation far
from the origin, a quarter turn and the mirror did not change it.

**Cause.** The walk on the graph (`_outer_face_walk`) was identical in both
frames: it decides contacts by distance (`cluster_points` at `GRAPH_EPSILON`,
a rigid motion keeps distances). On this part it stops short (16 311 of
48 465 mm²) because of a T on the interior of a spline, which `split_at_crossings`
does not cut (splines and ellipses stay whole, only used as knives), so D100's
fallback — the union of the closed faces — gives the outer. That fallback
built the network with `unary_union(..., grid_size=epsilon)`: GEOS snap-rounds
every vertex onto a 0.01 mm grid fixed to the axes and the origin. Two points
0.003 apart touch only if they fall into the same cell; turn the drawing and
the cell boundary moves. Here a line ends 0.003 from the side of a tessellated
ellipse: in one frame the face closed, in the other it did not. The grid also
did work nothing else did, by luck of position: T's on spline interiors (regr_04,
0.0005 and 0.0001 mm) and a line that misses an inscribed circle by 0.0037
without crossing it (anch_06). Removing the grid without replacing that work
lost them (regr_04 6 islands instead of 4, anch_06's tip face).

**Fix** (`outer_face._network`): the fallback's network is built with the
contacts decided by distance, the criterion of D101 and of the graph: endpoints
moved onto the graph's nodes (`_on_nodes`), two lines that do not touch but pass
within `epsilon` linked at their nearest points (a T on a spline, a line
grazing a circle), a free endpoint within `epsilon` of a line linked to it;
the union then runs on `UNION_GRID = 1e-6`, below the node grid (D113), where
only arithmetic decides. A rigid motion keeps every one of these distances.

**Measured on the 31 island drawings, old against new:** only `anch_08` changes
in shape (+47.9 mm², the two faces, now in every frame: the arc and the line
that close them are the outermost geometry). `anch_06`, `regr_01`, `regr_04`
move by slivers 0.003–0.004 mm thick on average (the old grid's rounding; the
new outer lies on the input, up to 0.038 mm where it follows a spline's hook the
grid flattened). Goldens unchanged (they store bbox and inner count). `island()`
~8% slower (~45 ms per drawing). `heal()` does not use this code.

**Held by:** `TestScrambled` with an empty `KNOWN` (anch_08 out of the list);
`tests/unit/core/test_outer_face.py::TestContattiPerDistanza` — a square whose
base is a spline, sides ending 0.004 above it, read at fractions of the old
cell and turned (red on the old code at dy 0.002, 0.004 and 2.0 rad), and a V
with an inscribed circle missed by 0.004 (red without the line-to-line links).

**Left open, 1.x:** when no edge lies entirely on the rim of the union,
`_faces_union_loop` returns `None` and the walk's smaller loop wins (the V with
its circle reads as the circle alone). Not red on any fixture (D158).

### D180 — G6c: a contact is decided once, on the true curves, and gives one shared node ✅

D179 fixed one frame-dependence of D100's fallback, but turning the drawings by
eight angles instead of one still gave 20 unstable readings (anch_03/regr_02 at
six angles, regr_04 at two). The common cause: a contact was decided several
times, by different criteria, sometimes on discretizations — the noding cut a
T within `tolerance` at the rounded projection, then the graph re-judged "same
node" within `GRAPH_EPSILON`; two cuts within `tolerance` on one edge merged
keeping the first while the other edge stayed at its own end; the STRtree
prefilter measured on chords up to 0.01 inside an arc; D179's links and
`unary_union` crossed discretizations; splines and ellipses were never cut, and
a near miss of a tangency was no contact.

**Rule** (`noding.split_at_crossings`, rewritten):
- every pair of nearby edges is judged once, on the true curves (closed form
  for lines, arcs, circles; splines and ellipses on their discretization at the
  node grid, 1e-3, D113). A contact is a crossing, an endpoint within
  `GRAPH_EPSILON` of the other curve (a T, or two ends), or two curves passing
  within `GRAPH_EPSILON` without crossing (the missed tangency, at the midpoint);
- several meetings of the *same pair* within `tolerance` along either edge are
  one contact (D101's two roots of a near-tangent line and arc);
- every contact unites a stop on each edge (union-find); two stops on one edge
  within `GRAPH_EPSILON` are one node, and one within `GRAPH_EPSILON` of the
  edge's end is that end. Never both ends of one edge: a short side does not
  vanish. The node is the group's smallest input endpoint if it has one (as
  `cluster_points`), else the mean of its contact points — one tuple for every
  edge the contact touches, so the graph has nothing left to re-judge;
- every type is cut, splines and ellipses included (`sub_segment`); a periodic
  spline stays whole.

**Why `GRAPH_EPSILON` and not `tolerance` for node identity.** Tried first:
a T within `tolerance` sharing the node. With heal's 0.5 it percolates — on
`output_polylines/BB_P1` a chain of T's and a crossing joined both ends of a
0.65 mm side, and on `gap_parallelo_healed` a corner 0.1 from a parallel side
became a node of that side; 17 `TestChordsKeepTheOuter` reds. D101 had already
rejected `tolerance` as a network-wide node radius for the same reason. The
old code never connected a T beyond `GRAPH_EPSILON` either (it cut at the
projection, the graph then kept the two nodes apart), so the effective rule is
unchanged; what changes is that it is decided once. `tolerance` keeps the one
job D101 gave it, scoped to a single pair.

**Also changed:** the outer-face walk reads an edge's leaving direction from the
node, not from the curve's first point (a node can sit up to `GRAPH_EPSILON`
off the curve, and two parallel pieces must leave it at different angles);
D100's fallback network no longer adds D179's distance links (the noding made
those contacts); `NonContourEdgeDetector.detect(..., planar=True)` does not
re-node `island()`'s already planar pieces; `NodedEdges.crossings` gives D132's
interior crossings from the union-find (`interior_crossings` reads it).

**Measured.** Eight angles (`_debug/2026-10-30_topo_G6c/stress_8_angles.py`):
20 → 0 unstable. All drawings, old against new: `heal()` identical everywhere;
`island()` changes shape only on anch_03/regr_02/anch_03_noframe — the two V's
with an inscribed circle now read as V plus circle (29.0 mm²) instead of the
circle alone (23.8 mm²), the case D179 left open for 1.x — and elsewhere only
the count of `loose` pieces (circles and splines cut at their contacts). Goldens
unchanged. Time: `island()` +10% on the 31 drawings (20.9 → 23.0 s), `heal()`
+6%; most of it is the spline discretization and `sub_segment` (De Boor in
Python, already the first job after 1.0).

**Held by:** `TestScrambled` reads every distinct geometry at two angles
(ROTATION and 0.13; twins such as regr_02/anch_03 once, `tests/readings.py
geometry_key`) — red on the old code for anch_03, anch_03_noframe, regr_02,
regr_04; `test_noding.py::TestContattoDecisoUnaVolta` (T within 0.01 shares the
node, a T on a spline cuts it, a missed tangency is a contact, two T's 0.03 apart
stay two nodes each equal to its stem, a 0.008 side keeps two ends) — four red
on the old code.

### D181 — Extra angles held by micro-cases, not by whole drawings ✅

**Problem.** D180 held its angle-dependence with `TestScrambled` reading every
distinct geometry at a second angle (0.13). Each angle costs one `island()`
reading per drawing, ~25 s of suite; the suite stood at 3:48, over its budget.

**Decision (option A of three; B kept the second angle on top, C did nothing).**
The 20 unstable cases of the eight-angle stress on the code before D180
(`3ea516b^`) were cropped to the smallest set of edges still unstable there, and
each crop was kept only if it is stable on D180. Two remain, written with
`topo.load_segments` in `TestScrambledMicro` (`test_island_invariants.py`) and
read at eight angles, scrambled, far and mirrored:
- a 60° V with an inscribed circle cutting each side by 0.004 (18 of the 20
  cases: anch_03, its noframe twin, regr_02);
- two nearly collinear lines 0.04 apart, ends 0.042 apart: regr_04 reduced by
  dropping edges in blocks while any angle stays unstable (a reduction keeps
  *an* instability of the drawing, not necessarily the very same face).
`EXTRA_ANGLES` is gone; whole drawings are read once, at ROTATION.

**Why.** A contact decided badly shows at some angles only, and only where the
contact is: the contact itself is the case, the rest of the drawing is cost.
A new angle-dependent contact enters as a crop, never as one more angle on
whole drawings.

**Measured.** Suite 3:48 → 3:23. Both micro-cases red on `3ea516b^`, green on
D180, 0.6 s together.

### D182 — G6e: a gap is closed at a meeting within reach, never at one decided by the last bit ✅

**Problem.** The snapdraw sweep (`scripts/21_sweep_invariants.py`) found 32 of
121 drawings where a rigid motion changes `heal()`'s reading. Traced step by
step, almost none pass through the polygonize fallback: the readings part
already in the clean-up passes. One family is `close_free_gaps`: two parallel
lines with their ends 0.004 apart (drw_0015, coordinates ~71500) are exactly
parallel in the file, `_line_intersection` finds no meeting and the gap gets
a segment; rotated, the parallelism is lost in the last bit (`abs(denom) <
1e-10` is an absolute threshold, so far from the origin rotation noise beats
it) and both ends were moved to the "meeting" at x = −1.8e10 mm.

**Rule.** A meeting that moves an endpoint further than the tolerance does
not close the gap: the gap gets the segment between the two ends instead
(`gap_solver._within_reach`, inside `compute_gap_fixes`). It is D60's rule
for `island()` ("a fix never moves an endpoint further than the gap"), now
for both readings in one place; `local_gap_fixes`, which dropped such moves
in `island()` alone, is gone. `repair_merged_corners` keeps an unbounded
reach (it passes `tolerance=inf`, D57: a corner two ends of which already
cluster).

**Why the tolerance as the reach.** It is the distance under which `heal()`
already treats two points as one; a move further than that invents geometry
the drawing does not have, and whether it happens depends on the frame.

**Measured.** Alone it makes no sweep drawing stable under a single motion
(drw_0015 still loses a hole, through another family below); it removes
endpoints moved by 1e10 mm. Suite and goldens unchanged, 3:23. Held by
`test_heal_steps.py::TestCloseFreeGaps::test_003` (the drw_0015 pair at four
angles, red on the old code at 0.7).

### D183 — G6e: "within the tolerance" includes it, up to float noise ✅

Decided by Federico, 31 October 2026 (option 1 of three: 2 was "strictly
below", which changes today's readings; 3 left the boundary to the input).

**Problem.** On 10 of the 31 sweep reds a gap is drawn exactly as wide as the
tolerance (regr_03: a 0.5 slot, `tolerance=0.5`). `d <= tolerance` is then
decided by the last bit: 0.4999999999 in the file's frame, 0.5000000001
rotated, and the hole closes in one and not in the other.

**Rule.** `heal()` compares every step with `reach = tolerance + FLOAT_NOISE`
(`topo.core.geometry.measure`, 1e-6 mm; the warnings still print the
tolerance asked for). `FLOAT_NOISE` is also `_CHAIN_GAP_EPS` in the
normalizer, the same float guard.

**Why 1e-6.** Above the noise a rigid motion adds (~1e-11 at coordinates
~1e5) and far below the node grid (1e-3, D113): no drawn value sits on the
new boundary, so the decision no longer depends on the frame. A gap equal to
the tolerance closes, as it already did in the file's frame.

**Measured.** Experiment with `tolerance=0.5+1e-6` on the sweep reds: 10 of
31 become stable under every single motion (the 6530-edge drawing not run).
Suite and goldens unchanged, 3:21. Held by
`test_heal_steps.py::TestGapAtTolerance` (the regr_03 slot under every
motion, red on the old code). `island()` is not touched: its gap comparisons
are a separate question, not yet measured.

### D184 — G6e: "same line, same circle" is judged on the true segments, never by a rounded key ✅

**Problem.** `merge_collinear_overlaps` and `merge_cocircular_overlaps`
grouped pieces by a rounded key: (angle to 1e-7, offset to 1e-3) for lines,
(center, radius) to 1e-3 for arcs. A grid cell has a border: on drw_0016 two
doubled verticals 2.5e-5 apart sit at x = 578.1875, exactly half-way between
two cells, so they fell in two buckets in the file's frame and in one once
rotated. And the canonical angle (-90°, 90°] has a seam on the verticals: on
drw_0015 1e-11 of noise on x put one of three doubled verticals on the other
side. The same disease D180 removed from the noding.

**Rule.** Two pieces share a carrier when, judged on the segments,
directions are parallel within `_SAME_DIRECTION` (1e-7, the sine of the
angle, either way) and every end of each lies within `_SAME_OFFSET` (1e-3 mm)
of the other's line; arcs when centers and radii are within `_SAME_OFFSET`.
The thresholds are the old ones; what goes is the grid and the seam. Only
nearby pairs are judged (`noding._near_pairs`), groups are their connected
components (`topology.graph.connected_groups`, the union-find
`spatial_islands` already had, now shared by both).

**Measured.** Suite and goldens unchanged, 3:22. On the sweep, drw_0016's
reading in its own frame loses two "holes" 146 mm long and 0 high (area 0.11)
— slivers between doubled lines that now merge. No more sweep drawing
becomes stable on its own: the remaining reds pass through other families.
Held by `test_normalizer.py::TestSameCarrierUnderMotion` (the drw_0016 pair,
the drw_0015 verticals, the drw_0016 pair as arcs; all red on the old code).

### D185 — G6e: an end with two equally near partners closes no gap, and heal() says so ✅

Decided by Federico, 31 October 2026 (of three: close with every tied
partner, which breaks D112's one-gap-per-end; leave the frame to decide).

**Problem.** On drw_0015 a small symmetric figure (two parallel strokes and
one between them) gives each end of the middle stroke two partners at the
same distance. `compute_gap_fixes` paired by distance, ties broken by
coordinates, so a rotation chose the other one. In a symmetric figure no
rule on coordinates gives the same partner in every frame.

**Rule.** With `pairwise=True` (heal) an end whose two nearest partners
within the tolerance are equally far (within `FLOAT_NOISE`) is left open; its
partners still pair with others. `heal()` lists those ends in a warning
(`steps.ambiguous_free_ends`, `gap_solver.ambiguous_gap_ends`). It is D111's
stance: what topology cannot decide is left to the drawing, and said.

**Measured.** drw_0015 becomes stable; j0099552 and regr_02 had ties too but
stay red through another path (same counts, different shapes). Suite and
goldens unchanged, 3:22. Held by `test_heal_steps.py::TestTiedGapPartners`
(the drw_0015 figure under every motion, red on the old code at rotation).

### D186 — Reopening D152 on one point: a group of short strokes is welded whole or not at all ✅

**Problem.** D152 capped a welded group at 0.05 mm and welded candidates in a
canonical order (length, then nodes) so the groups would not depend on edge
order. The order still depends on the frame: on J0118158 a fillet written as
chords 0.04 mm long, all equal, was welded every other chord, and which ones
was decided by the last bit of the lengths and by the coordinates — a
translation picked the others. Along a chain longer than the cap, *which*
strokes to weld has no geometric answer. The cap was also measured as the
bounding-box diagonal, which changes with a rotation.

**Rule.** The short strokes (D56's candidates, D164's tips excluded) are
grouped by shared nodes (`connected_groups`, D184). A group whose nodes are
all within `_DEGENERATE_LENGTH_EPS` of each other (diameter, not bbox
diagonal) is welded whole onto its smallest node; a wider group is a curve
drawn with short strokes and none of it is welded. D152's purpose — a curve
does not collapse into a point — holds without an order.

**Measured.** J0118158, j0097092 and regr_01 become stable under every
single motion (on the last two the merge and non-contour differences were
this weld seen downstream). Suite and goldens unchanged, 3:23. Slower where
long chains of strokes now stay whole: j0097092 7.8 → 14.0 s, regr_01
4.8 → 11.2 s for the five readings of the sweep. Held by
`test_normalizer.py::TestWeldUnderMotion` (a fillet of twelve 0.04 chords
between two sides; on the old code 8 edges in the file's frame, 9 rotated).

### D187 — One foundation for every reading ✅

Stated by Federico, 31 October 2026: `heal()`, `island()` and any recipe a
caller assembles stand on the same foundations. A geometric rule is decided
once, in one place, and every reading uses it; a fix inside one reading is
not a fix.

**What was wrong.** D180 (nodes decided once, by distance within
`GRAPH_EPSILON`) was built and tested for `island()` alone during G6c; its
measurement said "`heal()` identical everywhere", i.e. that heal had not
changed, not that it was free of the defect. `heal()` kept node identity by
the rounded tuple, the root of most of G6e. The two recipes also carried
their own copies of the front steps (island filtered the roles by hand and
did not look at non-finite coordinates; its gap clean-up lived in
`island.py`).

**Rule.** `topo/core/healing/base.py`:
- `prepare(edges, is_structural)`: non-finite coordinates and non-structural
  roles set aside, then `noding.decide_nodes` — nodes from the true segment
  points (`renode`), ends within `GRAPH_EPSILON` of each other one node (the
  smallest of the group); a group wider than that is a curve written as
  dense points and keeps its nodes (D186's rule, frame-free); an open edge
  whose two ends become one node is welded (D56).
- `normalize(edges, gap, *, keep_junctions, refit, pairwise, full_arcs)`:
  the same clean-up functions in the same order for every reading
  (collinear, cocircular, weld, near-full arcs, gaps through one
  `close_free_gaps`). What still differs between the readings is a named
  parameter, each with its decision: `keep_junctions` (D110), `refit` (D60),
  `pairwise` (D112), `full_arcs`. Whether each must stay a reading's choice
  is open, for Federico.

`_drop_redundant_meets` moved from `island.py` to the gap solver;
`within_diameter` is in `geometry.measure`, shared by D186's weld and
`decide_nodes`.

**Measured.** Suite and goldens unchanged, 3:24. One unit test changed
place, not expectation: `test_corner_repair::TestRepairWithOtherLoopClosed`
built nodes by hand on a 0.1 grid, so a 0.11 gap looked closed to the
tolerant graph; D57's rule it holds (a loop closed elsewhere does not stop
the ladder) is a rule of `find_loops` and is now tested there, green on the
old and the new code. Held by `tests/unit/core/test_base.py` (ends on either
side of a grid cell become one node; dense points wider than epsilon stay;
heal and island read the same outer under every motion).

**Hole found right after (same day).** The gap solver's bridging segment
took its nodes from `round_point` of the true ends, not from the nodes
`prepare` had decided: where an end's node was its group's representative,
the bridge hung free and a rotation lost two loops (drw_0028, 21 → 19).
`AddSegment` now carries the nodes of the two ends it joins (`node_a`,
`node_b`, set by one `_bridge`), and `apply_gap_fixes` uses them. Suite and
goldens unchanged.

### D188 — `core/healing/` becomes `core/base/` and `core/readings/` ✅

Asked by Federico, 31 October 2026. The name `healing/` said "the parts of
`heal()`" while it held the foundation of every reading, and a place that
reads as one reading's invites fixing one reading (D187's failure). Modules
are now grouped by job:
- `core/base/`: `prepare.py` (was `healing/base.py`), `cleanup.py` (the steps
  of the old `steps.py` that every reading uses: `split_non_finite`,
  `split_labeled`, `close_near_full_arcs`, `close_free_gaps`,
  `ambiguous_free_ends`, `dangling_splines`), `normalizer.py`,
  `gap_solver.py`, `hierarchy.py`;
- `core/readings/`: `heal.py`, `island.py`, `heal_steps.py` (the rest of
  `steps.py`: the loop ladder, the fallback, non-contour, hierarchy wrapper),
  `islands.py`, `outer_scan.py`.

The public surface does not change: `topo`, `topo.geometry` and
`topo.experimental` export names, not module paths. Internal paths broke for
three files outside the repo that import `topo.core.healing` directly:
snapdraw `lab/heal_repair_experiment.py`, `lab/island_rays.py`, cogo
`fixtures/corner_bend_problem.py` — lab and fixture code, adapted on their
side (D140), preferably to `topo.experimental`.

### D189 — One ingredient per job: heal() and island() on the same network, the same faces, the same gaps ✅

Asked by Federico, 31 October 2026: "the same flour and the same eggs for two
recipes". D187 had put the two readings' front steps behind one function but
kept switches (`pairwise`, `refit`, `full_arcs`) and left the rest in two
copies. An inventory of every function each reading reaches
(`_debug/2026-10-31_topo_G6e/ingredients.txt`) found 12 of 18 jobs done by
different code. This decision removes those copies; it reopens on one point
each D57 (the loop ladder), D60 (heal did not refit), D110/D112 (heal did not
node contacts; island closed every pair) and D100's polygonize fallback.

**One function per job, for every reading:**
- clean-up: `normalize` with no switches — tessellations refitted (deviation
  measured ≤ 0.0185 mm), collinear/cocircular merges, weld, near-full arcs,
  gaps (`geometry.measure.reach` gives every tolerance comparison D183's
  margin);
- gaps (`compute_gap_fixes`): each free end closes on the nearest point of
  the network within the tolerance — another free end (meeting or segment,
  D112), or where the end's own curve, *continued*, meets another edge (a line
  or arc extends to it; a spline takes its tangent). Never a perpendicular
  bridge: the drawing does not suggest it (a thread symbol 0.38 mm from its
  hole stays a symbol). An end with two equally near partners closes nothing
  (D185). This replaces D57's corner repair and the tolerant graph, and the
  `pairwise=False` + `drop_redundant_meets` of island, which did not close a
  rectangle's broken corner;
- the planar network: `split_at_crossings` for both. Where a contact cuts is
  the reading's meaning, a named parameter: `cut_crossings` — island yes
  (D101), heal no (D132: a crossing of contour sides is a broken drawing; an
  axis across a hole is not a side of the hole). `NodedEdges.planar` tells the
  non-contour detector whether to cut for its walk;
- non-contour: `non_contour_pieces`, on that network, for both;
- contours: `outer_face.face_walks` — the walk of the outer face (one
  `_stepper`) taken on every side of every edge; `face_loops` are the bounded
  faces split into simple rings (two slots touching at a corner are two
  holes), CCW (D166). `LoopFinder`, `find_loops`, `LoopSearch`,
  `repair_merged_corners`, the polygonize fallback, `off_faces`,
  `gap_endpoints_at_nodes` are gone; `outer_face` uses `face_loops` too;
- a side cut by a contact returns the file's segment when the ring runs all
  its pieces (`NodedEdges.whole`, D143); a ring that is no contour takes
  nothing, its edges go to `loose` whole;
- `loose`: `base/curves.loose_curves`, D162's rule for both (a piece that
  closes by itself is a ClosedCurve), labeled edges included; it replaces
  heal's `edges_to_open_curves` (which silently dropped a closed edge that was
  no contour, non-negotiable 7) and `labeled_curves`, and island's
  `_open`/`_pieces`.

- circle fits (`fit_circle_kasa`, `circle_through`, used by the refit) work in
  the frame of their own points: on x²+y² at coordinates ~1e6 the cancellation
  took the digits, refitted arcs came out with other centres and stopped
  merging — the reading depended on where the drawing sits.

What still distinguishes the readings is only their own step: heal takes
every bounded face and nests them; island groups by `max_gap` and keeps each
group's outer face.

**Measured.** Suite: 2955 passed, one red, 3:44 (over the time budget: heal
now nodes every drawing; to be measured and fixed). Goldens of heal: only F6
changes — two flaps joined by two short sides read as one outline with two
chords (before: two parts and an "edge joining two shapes" warning); a T gap
of 0.45 on one short side now closes. Federico judged the
DXF (31 October): the new F6 is better, the golden is regenerated at one part.
The reading is the same under every motion and 10 edge shuffles. What it
still says: 3 non-contour edges excluded; the two long strip sides and the
3.7 mm stub go to `loose`. The D111 "joining edge" warning no longer fires
there: with the gap closed the bridge is a chord inside one outline, no
longer the only link between two shapes. Goldens of island: unchanged; `loose`
changes count on 12 drawings (more arc pieces where ends now close on arcs).
G6d closes (SEGNI_TRACCIATI no longer depends on the chords). Sweep reds of
the morning (31, the 6530-edge one not run): 29 stable under every single motion;
left J0116004A (changes only with edge order) and drw_0017 (153 crossings: with
crossings uncut heal's network is not planar there, and the face walk on it is
not well defined). New tests:
`TestFaceLoops`, `TestGapOntoCurve` (drw_0015's symbol under every motion, a
broken corner in both readings), `TestTiedGapPartners` (an end-end tie); the
loop tests of `test_loops.py` run on `face_loops`; `test_corner_repair.py` is
gone with the repair.

### D190 — a non-finite number is refused by the primitive, like a curve of zero size ✅
Every reading began with `split_non_finite` (D111): it discretized every
curve of the drawing to look for a NaN/inf, about 13% of a reading on a
spline-heavy sheet, and it was a reading cleaning up a defect of its input.
A coordinate without a value has no position, so it is no curve: the same
case as D154's radius 0. One rule, where the segment is born: `_real` in
`primitives/segments.py` refuses a non-finite coordinate, radius, angle,
parameter, ratio, knot or weight (`ValueError`), so no `LineSeg`/`ArcSeg`/
`CircleSeg`/`EllipseSeg`/`BSplineSeg` without a position can exist, from any
source (DXF, PDF, primitives, a caller's own) and for every reading. The DXF
adapter already turns a refused entity into a `doc.warnings` line (D154,
D137); its text now names both causes. A caller who builds a segment with a
NaN gets the `ValueError` in their own code.
Behaviour change, Federico's choice (31 October): a drawing with a NaN entity
used to read as invalid (`errors`); now the entity is dropped at load with a
warning and the reading is valid on the rest, like every other entity the
model cannot hold. Removed: `topo.experimental.split_non_finite`,
`Prepared.broken`, the non-finite check of `validate_result` (dead: a result
can no longer carry one). Readings and goldens unchanged. Tests:
`test_degenerate_curves.py` (every primitive refuses NaN/inf; a DXF with a NaN
LINE and an inf CIRCLE loads, warns and heals valid).

### D191 — G6e closes on a finite list of decisions in the code, not on drawings
G6e (heal depends on the frame of reference) grew family by family: each new
drawing could bring a new one, so the item had no end. Every family found so
far (D182–D186) was the same defect: a decision taken at zero, on a grid,
with an absolute threshold near float noise, or on a tie, where a rigid motion
changes the last bit and so the answer. The places in `topo/core/` where a
number decides are finite. On 31 October they were listed (200 threshold
comparisons, 37 nearest/largest choices; about 35 suspects in about 15
files). G6e is closed when each suspect has either a micro-case built with
topo's API, red before and green after, or one line on why it does not
decide the reading. The snapdraw sweep is then run once, as a check; whatever
it still finds is a missing entry in the list, not a new family. The
promise stays D143's whole: same input, same reading; a rigid motion, same
reading, except a measure that falls on the tolerance itself within float
noise, which heal reports (D183, D185).

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
