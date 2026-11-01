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

Older entries use the names of their day (`forge`, `Feature`, `detect`): the
rename is D108/D119, the move of detection D88–D90.

- ~~D1~~ → D108, D119: the library was `forge`, then `topo` / `g-topo`.
- ~~D2~~ → D88, D90: `heal_and_detect` is gone; detection left topo.
- ~~D3~~ → D176: an enrichment step returned the mutated result (now `None`).
- **D4** — no bridge layer between adapter and model: `heal` builds the model
  from native segments (`Curve`: D114; no `.polygon`: D166).
- ~~D5~~ → D90: `source`/`confidence` and the detected-feature types are snapbend's.
- **D6** — `.reversed()` on every primitive; a loop → segments is domain logic.
- **D7** — one entity→primitive dispatcher for production and tests.
- **D8** — `inject()` is only the hook for external enrichment; counts are derived.
- **D9** — the inspector prints three levels: raw entities, what the adapter
  understood, what the model holds.
- **D10** — `load_pdf` is frozen (`list[Edge]`, out of `__all__`); resume in `topo_pdf`.
- **D11** — the version has one source, `pyproject.toml`.
- **D12** — SVG and view model are output only; the viewer is outside the 1.0 (D133).
- ~~D13~~ → D90: `detect_engrave` deferred — moot.
- **D14** — numbered scripts: one per public function, runnable with zero setup.
- ~~D15~~ → D88, D90: parametric `detect()`; a process parameter is the
  caller's, never topology (CLAUDE.md non-negotiable 4).
- **D16** — a dashboard/UI is its own repo; the library carries no web/GUI dependency.
- **D17** — the pipeline never translates geometry: endpoints move only to
  close gaps, writers emit segments verbatim, a split part keeps its XY.
- **D18** — topo does not nest; `to_nester_input` is experimental.
- **D19** — `core` never depends on `adapters` (the dependency rule, D44).
- **D20** — one typed text model, no `data` dict; the adapter only reads and
  writes the format; interpretation is its own step (D43). Now `Text` (D138).
- **D21** — `heal()` yields clusters; part, view or title block is the consumer's reading.
- **D22** — `core` the engine, `tools` optional steps on a result, `io`
  renderers. D58 reopened "heal is the core act".
- **D23** — scripts live in `scripts/`; first line `import _paths` (chdir to root).
- **D24** — frame/title-block detection is not topo's; `frame` is only a role.
- **D25** — recognition heuristics sit with their consumer, never in `core/`.
- **D26** — `model/` holds one concept per file and never imports `tools`.
- **D27** — `role` is an open vocabulary (`str`); `normalize_role` is the one
  point at load (`[a-z0-9_-]`, ≤ 64); the enum is never a lookup of caller data.
- **D28** — the non-contour finder keeps a neutral name (`NonContourEdgeDetector`).
- **D29** — frame/title-block recognition is snapdraw's, entering through `role`.
- **D30** — `is_structural_role` is the one predicate; `heal` sets edges with a
  decided non-structural role aside in `loose`, role intact; unknown roles untouched.
- **D31** — consumer roles are not topo's (`ContourRole.FRAME` removed); D128.
- **D32** — `load_geometry` is public: generated geometry enters without a file.
- ~~D33~~ → D141: `simplify_points`, point→primitive reconstruction.
- **D34** — every contour has `depth` and `parent`, set in the one recursion
  that builds the containment tree.
- **D35** — every loader exposes the full segment vocabulary, not one use case's subset.
- ~~D36~~ → D141: arc fitting in `fit_primitives`.
- ~~D37~~ → D128: `RoleStyle` per role.
- **D38** — point-sequence math lives in `core/geometry`, beside the segment math.
- ~~D39~~ → D40: `cut_tabs`, a gap within one contour (draft).
- ~~D40~~ → D134, D142: tabs from a child to its direct parent.
- **D41** — a SPLINE is written from control points + knots only, never with
  `fit_points` too (SigmaNest fails on both); `closed` only for a whole contour.
- **D42** — `BSplineSeg.discretize` evaluates the real curve (de Boor), never
  the control polygon; pure `math`, so `core` needs no `ezdxf`.
- **D43** — anchoring a text is geometry, not interpretation: `anchor_texts`.
- **D44** — `cluster.detected` is an open-by-name overlay, `None` until written;
  items are a `Protocol`; `model` does not import `tools`.
- **D45** — `EllipseSeg` is the fifth primitive: a native conic, never a spline.
- **D46** — `.rotated()` on every primitive. A rigid rotation never changes
  topology, so `rotate_result` needs no second `heal()`; align by `outer` or
  `inners`, never by `role`; overlays are not rotated.
- **D47** — `core` and `model` hold no process vocabulary; `heal(is_structural=)`
  injects "is this role part of a contour"; `ContourRole` is `UNKNOWN`/`OUTER`/`INNER`.
  The registry half went with D128.
- **D48** — `Text.width_factor` (1.0 = none), the axis a PDF `Tz` also has; an
  MTEXT group 41 is a wrap width, never a stretch.
- **D49** — the non-contour test works per connected component (the hull went in D111).
- **D50** — `merge_collinear_overlaps`: fragments that touch or overlap on one
  exact line are one edge. Fixed tight key, not the heal tolerance; runs first;
  `UNKNOWN` role only; input order kept; a source-format fact (`closed_path`) is
  never a criterion. D110 for junctions.
- **D51** — `closed_path` left `Edge`: how a CAD author grouped entities is no model fact.
- **D52** — `merge_cocircular_overlaps`: D50 for arcs; a full turn is a
  `CircleSeg`, never a 360° `ArcSeg`.
- ~~D53~~ → D63: `layer_to_role` → `label_to_role`; no format word in core names.
- ~~D54~~ → D90: a labelled line on the outer boundary is absorbed (detection).
- **D55** — `non_contour_candidates(doc)`: the detector `heal()` uses, returning
  `Edge`s so a caller sets `.role`; topo says "candidate", the caller says what.
- **D56** — `weld_degenerate_linesegs`: a `LineSeg` under a fixed 0.05 mm is
  welded by union-find, never deleted; `UNKNOWN` only; bounded by D152, D186.
- ~~D57~~ → D189: corner repair whenever free ends remain.
- **D58** — two readings, `heal()` (from inside) and `island()` (from outside),
  same ingredients, same model; the caller chooses by the drawing.
- ~~D59~~ → D99, D161: `island()` by proximity; its planar network and outer-face walk live on.
- **D60** — `refit_tessellations`: ≥ 10 `LineSeg` under 0.1 mm are a tessellation,
  refitted as arc/circle (0.02 mm) or spline; since D189 in both readings.
- **D61** — B-spline interpolation is topo's own math; no format library in `core`.
- **D62** — `HealStep` is gone: steps are public edges-in/edges-out functions,
  `heal()` a recipe beside `island()`; D187–D189 put both on one base.
- **D63** — `role_rules` (`RoleRule`: `name`, `name_contains`, `dashed`, `color`;
  first match wins) replace the three maps. The source's group name never leaves
  the adapter; "dashed" is a fact of the pattern; vocabularies are the caller's.
- **D64** — `EdgeStyle.dash_kind`: `continuous`, `uniform`, `chain` (marks
  differing by > 5%); `RoleRule(dash=)`. Chain → construction is snapdraw's.
- **D65** — `island()` recomposes after the cut: consecutive segments on one
  circle or line become one; a contour of arcs of one circle is a `CircleSeg`.
- **D66** — a pointer's target: the nearest boundary within 0.5 mm (tie → the
  smaller), else the smallest closed element covering the tip; objects: D177.
- ~~D67~~ → D88: `detect` → `detect_flat`.
- **D68** — `contour_shape` says circle / stadium / rectangle / polygon / other,
  never hole or slot (that needs other views or the process); closed list: D136.
- **D69** — `measured_points` + `measured_references` anchor a measure to
  elements within 0.5 mm; `<>` is resolved on reading; scale checks are snapdraw's.
- ~~D70~~ → D90, D128: `to_dxf` writes every overlay collection.
- ~~D71~~ → D161: a nested island brings its closed loops to its host.
- **D72** — `CLAUDE.md` is the router; `docs/INDEX.md` is generated by
  `gen_index.py` (also checks duplicate names and the dependency rule).
- **D73** — no client drawing name, part code or order number in a tracked
  file, and no sentence mapping a fixture to its origin; `audit_names.py --strict`.
- **D74** — the consumer is spelled `snapdraw`; no `snapforge` alias.
- **D75** — tracked fixtures get invented names saying what they exercise; a
  rename checks the target name is free.
- **D76** — the audit reads drawing content too; part codes in fixtures become
  invented sigils; `audit_fixtures.py` lists what the suite needs and git lacks.
- ~~D77~~ → D80: `anonymize`.
- **D78** — fixtures are read one string at a time; a name has no shape, so
  cleaning follows the string across every copy. Putting a client-sourced drawing
  in git is Federico's call.
- **D79** — `tests/data/` is the tracked root; `tests/examples/` stays local.
- **D80** — `anonymize` is `dxf-anonymize`, private (pipx); no public repo may declare it.
- **D81** — history rewritten once (2 Oct) from a list kept outside the repo;
  forward only: `audit_names --strict`, `--history` before a release. Redone in D97.
- **D82** — `inject(snap_distance)` and `anchor_texts` share one rule: a covered
  text belongs to its outer; else the nearest within `snap_distance`; else none.
- **D83** — `allow_invalid=True` on `to_dxf`/`to_svg`; a machine caller passes
  `False`; `split` always raises on an invalid result.
- **D84** — `to_text` (experimental): Markdown for a language model; ids `Cn`,
  `Cn.k`; size budgeted by `test_text_budget.py`, regenerated only after reading it.
- **D85** — `ensure_linetype`: document → caller's pattern → standard table →
  `None` (BYLAYER for a source edge, `ValueError` for a caller's style).
- **D86** — `gen_index --similar` finds one job under different names:
  candidates to read, not verdicts.
- **D87** — the collinear and cocircular merges are one engine (`_merge_on_carrier`).
- **D88** — the boundary: topo reads structure, consumers read meaning. Both
  readings and `split` stay; process thresholds and hole/bend/engrave leave.
  The sheet-metal consumer is `snapbend`.
- **D89** — golden: `json/` is geometry (topo), `process/` the consumer's;
  `cluster.area` follows depth parity (odd subtract, even add back).
- **D90** — detection lives in `snapbend.flat`; topo keeps the open overlay and
  renderers read `role` + geometry, never a collection name; `is_void` subtracts.
- **D91** — `concentric_groups` and `arcs_around` are geometric facts; thresholds
  and a shared `Hole` model are the consumers'.
- **D92** — `gen_index.py` is one file in every project, its rule in
  `pyproject.toml`, enforced by `tests/unit/test_index.py`.
- **D93** — line facts in `core/geometry/lines.py` (`are_collinear`,
  `bridged_runs`, `splits_contour`); reaches and "is a bend" stay the consumer's.
- **D94** — axis-aligned facts in `core/geometry/axis.py`; consumers keep their numbers.
- **D95** — one package, `core/geometry/`, public as `topo.geometry`; facts are
  frozen dataclasses computed on demand, never cached on the model.
- **D96** — builders `polygon`, `rectangle`, `regular_polygon`, `circle`,
  `stadium` take the measures `contour_shape` reports; `load_segments`; the dict
  schema says `polygon`.
- **D97** — no history rewrite or force push without Federico's yes to that step.
- **D98** — `island()` takes no domain default: `max_gap` is required, by name.
- **D99** — pieces are the edges that touch at `max_gap`; every outer contour
  not inside another is an island. D161 reopened what it reads inside.
- **D100** — the outer face is the boundary of the union of the closed faces
  (per whole piece); D199 keeps the union.
- **D101** — two cuts of one edge closer than `tolerance` are one node; raising
  `GRAPH_EPSILON` instead was rejected (global, percolates, drops holes).
- **D102** — a gap-fix across two ends of one connected component is a sliver, not a gap.
- ~~D103~~ → D157, D161: drop of boundary-duplicate loops.
- **D104** — permanent `island()` invariants: polygon and segments describe one
  shape, polygons simple, DXF round-trip stable.
- ~~D105~~ → D106: reopening D104; a second graph on the rim edges was refuted.
- **D106** — a face's segments are read off its own boundary
  (`rim.face_segments`); a self-touching loop is one face per lobe; a face
  thinner than `tolerance` is not a face.
- **D107** — invariants: nothing dropped (within `max_gap`), inners disjoint or
  nested; pieces no face uses go to `loose` (`off_faces`).
- **D108** — `topo` / `g-topo`, no `forge` alias.
- **D109** — editing a contour by a region is topo's geometry, in topo's words; built as D118.
- **D110** — in `heal()` two collinear pieces that only touch at a node where
  another line ends stay apart (`keep_junctions`); `island()` keeps D50.
- **D111** — an edge is contour when the outer face's boundary traverses it
  exactly once, on the planar network; `heal()` invariants; ambiguity warnings.
- **D112** — the tolerance measures a gap, not a side: free ends pair
  nearest-first in `heal()`; an arc closes on itself only if the gap ≤ tolerance
  and the missing angle ≤ 2°.
- **D113** — one node grid, `NODE_DECIMALS = 3`; the tolerance only bounds the gaps that may close.
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
- **D192** — G6e group A: a meeting (`intersections.py`) is decided in
  millimetres against `FLOAT_NOISE`, on the measure whose error is linear:
  parallel = directions part by at most the noise along the longer segment;
  on a segment or arc = overshoot of an end ≤ the noise; tangent = the radial
  gap (centre-to-line, centre distance vs radii) within the noise, never the
  half-chord, which grows as the square root of the gap.
- **D193** — reopening D191's exit: G6e is in the 1.0 gate on a counted bar,
  not on "every drawing" (which has no end): (1) the inventory is closed, each
  line corrected by a red→green micro-case or argued harmless; (2) one re-pass
  of the "harmless because at the tolerance" lines at their call sites; (3) the
  snapdraw sweep (121 drawings) run once. Whatever it still finds is a known
  issue fixed in a 1.x patch: no name changes, so no churn.
- **D194** — G6e group B: on a planar network a node is the piece's tuple and
  the graph does not re-judge it (`epsilon` 0 for identity in `outer_face`,
  `face_loops`, `non_contour_pieces`): re-clustering rounded tuples at
  `GRAPH_EPSILON` made a band a rigid motion crosses. `epsilon` keeps only the
  sliver threshold (`sliver`) and D100's union band.
- **D195** — reopening D166's means only: congruent copies are equal within
  the noise, not within a grid cell. `sort_clusters`: areas equal if they differ
  by ≤ `FLOAT_NOISE` × perimeter, `xmin` by ≤ `FLOAT_NOISE`, chained along the
  sorted values (independent of input order). `_build_tree` keeps its
  `round(area, 6)`: nested contours differ far beyond it.
- **D196** — G6e stays line by line: no shared "noise" module and no lint on
  comparisons. Half of the corrections were structural (decide once, drop a
  rounding), half each needed their own measure; a pattern check hits ~75 false
  alarms and misses ties and named constants. Snap rounding and exact
  predicates do not answer G6e (a fixed grid moves under rotation).
- **D197** — G6e group D: `concentric_groups` joins a circle to the *nearest*
  group within `tolerance` (equidistant within the noise: the first made);
  equal diameters keep the order of `items`; groups are ordered by `x` then
  `y` equal within the noise (`noise_runs`). "First group made" was the frame.
- **D198** — G6e group D: a node of `split_at_crossings` holding several
  distinct input endpoints is their mean (`math.fsum`, rounded to the node
  grid), not the smallest in `(x, y)`; one distinct endpoint stays itself.
  Between two ends of two curves no geometry names the vertex.
- **D199** — G6e, last line: D100's union stays. Its re-noding on
  discretizations (sagitta ≤ 0.01) can weld a contact D180 excluded on a built
  case; removing it makes one real drawing read wrongly, because
  `_leaving_angle` reads directions at `DIRECTION_SAMPLE` and inverts branch
  order at a node. Known defect for 1.x (`TestChordContactUnderMotion` skips
  while it holds); the union goes only after the walk orders branches by how
  they actually leave the node.
- **D200** — G6e, D193 point 2: two islands are apart on the true curves —
  discretizations decide only outside a band of 2·`DEFAULT_TOLERANCE` round
  `max_gap`, inside it the distance is refined on the primitives
  (`strips.refine_gap`) — and a point of a piece, tested on the primitives
  (`ring_contains`), says whether its host contains it.
- **D201** — G6e closed for 1.0 on D193's bar: inventory closed, re-pass done,
  the sweep run once on `b10aa2b`. `island()` keeps every invariant on all 121;
  `heal()` changes under a motion on 2 drawings (from 32). Three residues go to
  1.x as known issues: `hierarchy.py:70` (a hole tangent from inside to the
  outer can read as two clusters), one drawing past the 300 s limit, one small
  face 1 mm wide read as outer or inner by frame.