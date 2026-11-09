# MAP.md — topo decision log

The register of the **rules in force**: one entry per rule, a `### D##` title
(the rule in one sentence; consumer sessions list these titles) and at most
4 lines under it; a superseded rule is one line ("D59 → D99, D161"). The full text of every
decision, with its why and its history, is in `MAP_ARCHIVE.md` (local, not in
git; the same text is in git at `67fda38:MAP.md`). Not documentation (that's
`docs/`) and not a session log (that's the git log).

Rule: a closed decision is **not re-decided from scratch**. To reopen it, say
so — "reopening D##". A new decision takes the next `D##` and one entry here.

- **What topo is, how to use it** → `README.md`, `docs/API.md`, `docs/LLM.md`
- **How it's built inside** → `docs/ARCHITECTURE.md`
- **What exists in the code** → `docs/INDEX.md` (generated, `scripts/gen_index.py`, D72)
- **Where to start a session** → `CLAUDE.md` (routing + non-negotiables, D72)
- **What is open** → `TODO.md`; the 1.0 gate is D148/D193

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

### ~~D1~~ → D108, D119: the library was `forge`, then `topo` / `g-topo`.
### ~~D2~~ → D88, D90: `heal_and_detect` is gone; detection left topo.
### ~~D3~~ → D176: an enrichment step returned the mutated result (now `None`).
### D4 — no bridge layer between adapter and model: `heal` builds the model from native segments (`Curve`: D114; no `.polygon`: D166).
### ~~D5~~ → D90: `source`/`confidence` and the detected-feature types are snapbend's.
### D6 — `.reversed()` on every primitive; a loop → segments is domain logic.
### D7 — one entity→primitive dispatcher for production and tests.
### D8 — `inject()` is only the hook for external enrichment; counts are derived.
### D9 — the inspector prints three levels: raw entities, what the adapter understood, what the model holds.
### D10 — `load_pdf` is frozen (`list[Edge]`, out of `__all__`); resume in `topo_pdf`.
### D11 — the version has one source, `pyproject.toml`.
### D12 — SVG and view model are output only; the viewer is outside the 1.0 (D133).
### ~~D13~~ → D90: `detect_engrave` deferred — moot.
### D14 — numbered scripts: one per public function, runnable with zero setup.
### ~~D15~~ → D88, D90: parametric `detect()`; a process parameter is the caller's, never topology (CLAUDE.md non-negotiable 4).
### D16 — a dashboard/UI is its own repo; the library carries no web/GUI dependency.
### D17 — the pipeline never translates geometry: endpoints move only to close gaps, writers emit segments verbatim, a split part keeps its XY.
### D18 — topo does not nest; `to_nester_input` is experimental.
### D19 — `core` never depends on `adapters` (the dependency rule, D44).
### D20 — one typed text model, no `data` dict; the adapter only reads and writes the format; interpretation is its own step (D43).
Now `Text` (D138).
### D21 — `heal()` yields clusters; part, view or title block is the consumer's reading.
### D22 — `core` the engine, `tools` optional steps on a result, `io` renderers.
D58 reopened "heal is the core act".
### D23 — scripts live in `scripts/`; first line `import _paths` (chdir to root).
### D24 — frame/title-block detection is not topo's; `frame` is only a role.
### D25 — recognition heuristics sit with their consumer, never in `core/`.
### D26 — `model/` holds one concept per file and never imports `tools`.
### D27 — `role` is an open vocabulary (`str`).
`normalize_role` is the one point at load (`[a-z0-9_-]`, ≤ 64); the enum is
never a lookup of caller data.
### D28 — the non-contour finder keeps a neutral name (`NonContourEdgeDetector`).
### D29 — frame/title-block recognition is snapdraw's, entering through `role`.
### D30 — `is_structural_role` is the one predicate.
`heal` sets edges with a decided non-structural role aside in `loose`, role
intact; unknown roles untouched.
### D31 — consumer roles are not topo's (`ContourRole.FRAME` removed); D128.
### D32 — `load_geometry` is public: generated geometry enters without a file.
### ~~D33~~ → D141: `simplify_points`, point→primitive reconstruction.
### D34 — every contour has `depth` and `parent`, set in the one recursion that builds the containment tree.
### D35 — every loader exposes the full segment vocabulary, not one use case's subset.
### ~~D36~~ → D141: arc fitting in `fit_primitives`.
### ~~D37~~ → D128: `RoleStyle` per role.
### D38 — point-sequence math lives in `core/geometry`, beside the segment math.
### ~~D39~~ → D40: `cut_tabs`, a gap within one contour (draft).
### ~~D40~~ → D134, D142: tabs from a child to its direct parent.
### D41 — a SPLINE is written from control points + knots only, never with `fit_points` too (SigmaNest fails on both).
`closed` only for a whole contour.
### D42 — `BSplineSeg.discretize` evaluates the real curve (de Boor), never the control polygon; pure `math`, so `core` needs no `ezdxf`.
### D43 — anchoring a text is geometry, not interpretation: `anchor_texts`.
### D44 — `cluster.detected` is an open-by-name overlay, `None` until written; items are a `Protocol`; `model` does not import `tools`.
### D45 — `EllipseSeg` is the fifth primitive: a native conic, never a spline.
### D46 — `.rotated()` on every primitive.
A rigid rotation never changes topology, so `rotate_result` needs no second
`heal()`; align by `outer` or `inners`, never by `role`; overlays are not
rotated.
### D47 — `core` and `model` hold no process vocabulary.
`heal(is_structural=)` injects "is this role part of a contour"; `ContourRole`
is `UNKNOWN`/`OUTER`/`INNER`. The registry half went with D128.
### D48 — `Text.width_factor` (1.0 = none), the axis a PDF `Tz` also has; an MTEXT group 41 is a wrap width, never a stretch.
### D49 — the non-contour test works per connected component (the hull went in D111).
### D50 — `merge_collinear_overlaps`: fragments that touch or overlap on one exact line are one edge.
Fixed tight key, not the heal tolerance; runs first; `UNKNOWN` role only;
input order kept; a source-format fact (`closed_path`) is never a criterion.
D110 for junctions.
### D51 — `closed_path` left `Edge`: how a CAD author grouped entities is no model fact.
### D52 — `merge_cocircular_overlaps`: D50 for arcs; a full turn is a `CircleSeg`, never a 360° `ArcSeg`.
### ~~D53~~ → D63: `layer_to_role` → `label_to_role`; no format word in core names.
### ~~D54~~ → D90: a labelled line on the outer boundary is absorbed (detection).
### D55 — `non_contour_candidates(doc)`: the detector `heal()` uses, returning `Edge`s so a caller sets `.role`.
Topo says "candidate", the caller says what.
### D56 — `weld_degenerate_linesegs`: a `LineSeg` under a fixed 0.05 mm is welded by union-find, never deleted; `UNKNOWN` only; bounded by D152, D186.
### ~~D57~~ → D189: corner repair whenever free ends remain.
### D58 — two readings, `heal()` (from inside) and `island()` (from outside), same ingredients, same model; the caller chooses by the drawing.
### ~~D59~~ → D99, D161: `island()` by proximity; its planar network and outer-face walk live on.
### D60 — `refit_tessellations`: ≥ 10 `LineSeg` under 0.1 mm are a tessellation, refitted as arc/circle (0.02 mm) or spline.
Since D189 in both readings.
### D61 — B-spline interpolation is topo's own math; no format library in `core`.
### D62 — `HealStep` is gone: steps are public edges-in/edges-out functions, `heal()` a recipe beside `island()`; D187–D189 put both on one base.
### D63 — `role_rules` (`RoleRule`: `name`, `name_contains`, `dashed`, `color`; first match wins) replace the three maps.
The source's group name never leaves the adapter; "dashed" is a fact of the
pattern; vocabularies are the caller's.
### D64 — `EdgeStyle.dash_kind`: `continuous`, `uniform`, `chain` (marks differing by > 5%); `RoleRule(dash=)`.
Chain → construction is snapdraw's.
### D65 — `island()` recomposes after the cut.
Consecutive segments on one circle or line become one; a contour of arcs of
one circle is a `CircleSeg`.
### D66 — a pointer's target: the nearest boundary within 0.5 mm (tie → the smaller), else the smallest closed element covering the tip.
Objects: D177.
### ~~D67~~ → D88: `detect` → `detect_flat`.
### D68 — `contour_shape` says circle / stadium / rectangle / polygon / other, never hole or slot (that needs other views or the process).
Closed list: D136.
### D69 — `measured_points` + `measured_references` anchor a measure to elements within 0.5 mm.
`<>` is resolved on reading; scale checks are snapdraw's.
### ~~D70~~ → D90, D128: `to_dxf` writes every overlay collection.
### ~~D71~~ → D161: a nested island brings its closed loops to its host.
### D72 — `CLAUDE.md` is the router; `docs/INDEX.md` is generated by `gen_index.py` (also checks duplicate names and the dependency rule).
### D73 — no client drawing name, part code or order number in a tracked file, and no sentence mapping a fixture to its origin.
`audit_names.py --strict`.
### D74 — the consumer is spelled `snapdraw`; no `snapforge` alias.
### D75 — tracked fixtures get invented names saying what they exercise; a rename checks the target name is free.
### D76 — the audit reads drawing content too.
Part codes in fixtures become invented sigils; `audit_fixtures.py` lists what
the suite needs and git lacks.
### ~~D77~~ → D80: `anonymize`.
### D78 — fixtures are read one string at a time; a name has no shape, so cleaning follows the string across every copy.
Putting a client-sourced drawing in git is Federico's call.
### D79 — `tests/data/` is the tracked root; `tests/examples/` stays local.
### D80 — `anonymize` is `dxf-anonymize`, private (pipx); no public repo may declare it.
### D81 — history rewritten once (2 Oct) from a list kept outside the repo; forward only: `audit_names --strict`, `--history` before a release.
Redone in D97.
### D82 — `inject(snap_distance)` and `anchor_texts` share one rule.
A covered text belongs to its outer; else the nearest within `snap_distance`;
else none.
### D83 — `allow_invalid=True` on `to_dxf`/`to_svg`; a machine caller passes `False`; `split` always raises on an invalid result.
### ~~D84~~ → D213: `to_text` (experimental): Markdown for a language model; removed.
Ids `Cn`, `Cn.k`; size budgeted by `test_text_budget.py`, regenerated only
after reading it.
### D85 — `ensure_linetype`: document → caller's pattern → standard table → `None` (BYLAYER for a source edge, `ValueError` for a caller's style).
### D86 — `gen_index --similar` finds one job under different names: candidates to read, not verdicts.
### D87 — the collinear and cocircular merges are one engine (`_merge_on_carrier`).
### D88 — the boundary: topo reads structure, consumers read meaning.
Both readings and `split` stay; process thresholds and hole/bend/engrave
leave. The sheet-metal consumer is `snapbend`.
### D89 — golden: `json/` is geometry (topo), `process/` the consumer's; `cluster.area` follows depth parity (odd subtract, even add back).
### D90 — detection lives in `snapbend.flat`.
Topo keeps the open overlay and renderers read `role` + geometry, never a
collection name; `is_void` subtracts.
### D91 — `concentric_groups` and `arcs_around` are geometric facts; thresholds and a shared `Hole` model are the consumers'.
### D92 — `gen_index.py` is one file in every project, its rule in `pyproject.toml`, enforced by `tests/package/test_index.py`.
### D93 — line facts in `core/geometry/lines.py` (`are_collinear`, `bridged_runs`, `splits_contour`); reaches and "is a bend" stay the consumer's.
### D94 — axis-aligned facts in `core/geometry/axis.py`; consumers keep their numbers.
### D95 — one package, `core/geometry/`, public as `topo.geometry`; facts are frozen dataclasses computed on demand, never cached on the model.
### D96 — builders `polygon`, `rectangle`, `regular_polygon`, `circle`, `stadium` take the measures `contour_shape` reports.
`load_segments`; the dict schema says `polygon`.
### D97 — no history rewrite or force push without Federico's yes to that step.
### D98 — `island()` takes no domain default: `max_gap` is required, by name.
### D99 — pieces are the edges that touch at `max_gap`; every outer contour not inside another is an island.
D161 reopened what it reads inside.
### D100 — the outer face is the boundary of the union of the closed faces (per whole piece); D199 keeps the union.
### D101 — two cuts of one edge closer than `tolerance` are one node; raising `GRAPH_EPSILON` instead was rejected (global, percolates, drops holes).
### D102 — a gap-fix across two ends of one connected component is a sliver, not a gap.
### ~~D103~~ → D157, D161: drop of boundary-duplicate loops.
### D104 — permanent `island()` invariants: polygon and segments describe one shape, polygons simple, DXF round-trip stable.
### ~~D105~~ → D106: reopening D104; a second graph on the rim edges was refuted.
### D106 — a face's segments are read off its own boundary (`rim.face_segments`).
A self-touching loop is one face per lobe; a face thinner than `tolerance` is
not a face.
### D107 — invariants: nothing dropped (within `max_gap`), inners disjoint or nested; pieces no face uses go to `loose` (`off_faces`).
### D108 — `topo` / `g-topo`, no `forge` alias.
### D109 — editing a contour by a region is topo's geometry, in topo's words; built as D118.
### D110 — in `heal()` two collinear pieces that only touch at a node where another line ends stay apart (`keep_junctions`); `island()` keeps D50.
### D111 — an edge is contour when the outer face's boundary traverses it exactly once, on the planar network; `heal()` invariants; ambiguity warnings.
### D112 — the tolerance measures a gap, not a side.
Free ends pair nearest-first in `heal()`; an arc closes on itself only if the
gap ≤ tolerance and the missing angle ≤ 2°.
### D113 — one node grid, `NODE_DECIMALS = 3`; the tolerance only bounds the gaps that may close.
### D114 — `Feature` → `Curve` (`ClosedCurve`, `OpenCurve`): the base of the model is geometry, not a reading; the overlay keeps `DetectedFeature`.
No alias.
### D115 — `geometry.dash_line(start, end, head, tail, middle, n_middle)`.
A dash glued to each end, equal dashes and gaps between; straight segments
only.
### D116 — `INTERPRETER.md` and `SNAPDRAW.md` left the repo.
### D117 — no brand in type names (`topo.Document`, `Result`, `Cluster`, `Contour`); the steps of the readings are in `topo.steps`, now `experimental`.
### D118 — primitives for a caller's own algorithms, on rings.
`intersections`, `point_on_contour`, `cut_by`, `contour_minus` (the region is
*any* closed ring, never a named shape), `Contour.from_segments`. Which points
and radii is the caller's.
### D119 — the rename is applied; formats follow (XML root `<topo>`, XDATA id `TOPO`, `<name>.topo.md`).
A call is `import topo` then the full path, never `from topo import steps`;
every doc example uses that form.
### D120 — surface, first half: `topo.primitives` (pure math) and `topo.model` (types, roles, `Edge`); everything under `topo.core` is internal.
### D121 — direction: trust is two-way fidelity (built in D143, D152).
One `Curve` protocol with `as_analytic(tol)` as a *question*, a contour
signature public, patterns the caller's — protocol, `as_analytic`, signature
are 1.x.
### D122 — surface, second half: measures and axis facts in `topo.geometry`.
Not public: the DXF layer table (topo has roles) and tabs (D142). A lab may
reach inside; a published package may not.
### D123 — topo has **no file format**: geometry and roles, never layers.
Adapters sit at the edges; an exporter maps role → weight, colour, linetype
and DXF layer(s). `ezdxf` is not a dependency of topo.
### D124 — one repo, one distribution, packages `topo/`, `topo_dxf/`, `topo_pdf/`, extras `[dxf]`, `[pdf]`; the boundary is checked mechanically.
`split` is topo's (it chooses parts on the model); each adapter writes one
part.
### D125 — the adapter contract, in public names.
`Edge.of(segment, role, style=)` (the node grid is topo's), no base class,
`segment_endpoints`, `RoleRule`, `resolve_role`, `DEFAULT_NODE_TOLERANCE` in
`topo.model`.
### D126 — neutral vocabulary: `EdgeStyle(linetype, linetype_desc, dash, color)` — `dash` the signed marks (`> 0` dash, `0` dot, `< 0` gap), `color` an RGB; `RoleRule(color=)` takes RGB, `#rrggbb` or a base name, never an index.
### D127 — `Text.role` is the consumer's, set by the same `role_rules` on the source group name; topo holds the slot and never reads it.
### D128 — output by role: neutral `RoleStyle` in the model.
`to_dxf(layers={role: name | fn(element)})` lets a role produce several
layers; topo's palette (`role_style()`) with the caller's map on top; the
global registry (reopening D47) and `Annotation.group` went.
### D129 — the move: `topo_dxf/`, `topo_pdf/`.
`topo.split(result) -> list[Result]`; `load_dxf(skip_layers=)`;
`test_no_format.py` proves `topo` runs without `ezdxf`.
### D130 — 0.20.0: every name in the three `__all__` has a card in API.md and a line in LLM.md (checked by script).
### D131 — the non-contour criterion judges a **chain** (`Graph.chains()`; degree-2 nodes are not forks) between two distinct branching nodes, whole, by D111's rule; a chain closed on one node is a loop, never a candidate.
Edge order is tested (`TestEdgeOrder`: reversed + 5 shuffles).
### D132 — non-contour choices, each pinned in `test_non_contour_choices.py`.
An interior chain (0 passes) is a chord; a bridge (2 passes) splits the parts;
a chain on the boundary for ≤ half its length is a chord; sides crossing
without a node are judged on the planar network and **reported**
(`interior_crossings`), never repaired.
### D133 — the viewer stays outside the stable 1.0 (`to_view_model`, `to_svg`, `save_svg`, now `topo.experimental`).
### D134 — joining nested regions: topo gives facts (facing boundaries, gap, strip, unconnected regions) and the construction.
The policy is the caller's; names are geometric. Done in D142.
### D135 — `SplineSeg` → `BSplineSeg` (`degree`, `control_points`, `knots`, `weights`; `clamped`/`closed`/`periodic` derived).
Format fields left the model.
### D136 — `contour_shape.kind` is a closed list of six (`circle`, `stadium`, `rectangle`, `ellipse`, `polygon`, `other`; `ShapeKind`).
A kind needs a contour fully determined by its measures. A contour's kind
never changes in 1.x.
### D137 — `trash_entities` → `loose`: one list.
Each curve has `cluster_ref` (the cluster whose outer encloses it, else
`None`); a consumer promotes a curve (`Result.promote`, D173) — never in two
places, never dropped.
### D138 — `Annotation`/`Note`/`Dimension`/`Leader` → `Text` (`pointer`, `target`, `measured_points`, `measure`, `measure_is_angle`, `references`, `rendered`, `source_kind`): "dimension" is a reading.
The writer re-emits `rendered`, never a native DIMENSION.
### ~~D139~~ → D142: tabs at caller-chosen points; its findings live on in D142.
### D140 — a consumer uses topo as it uses numpy: topo is read-only from a consumer's session; needs go to `## Richieste a topo` in its `TODO.md`.
What varies between consumers must be an *argument*, never a new function.
### D141 — `simplify_points(points, tolerance, scale, ...)` (experimental).
A corner is a turn ≥ `corner_turn_deg` over `scale`; a line where straight, an
arc through its ends, else a spline within `tolerance`; a head-to-tail chain.
### D142 — `strips` (experimental): D134's facts on primitives (`facing_boundaries`, `gap`, `link`, `unconnected_regions`, `open_boundaries`).
A strip leaves perpendicular from the nearer boundary and is refused, with the
reason, if it crosses a third boundary.
### D143 — what 1.0 promises: names and signatures do not break, and the geometry as invariants — **faithful** (Hausdorff both ways ≤ tolerance), **complete** (every curve a contour or in `loose`), **deterministic**.
Not promised: segment counts, a contour's start point, ambiguous `island()`
cases.
### D144 — for 1.0 `API.md`, `ARCHITECTURE.md` and the docstrings of public names are English; internal code stays Italian.
### D145 — circles and arcs discretize on one grid per circle, no side cap.
N sides with sagitta ≤ `tol` (≥ 64, a multiple of 4) from angle 0; same curve,
same polygon however the file cut it.
### D146 — a piece the outer contour uses is never also a spur.
### D147 ⏸ — suspended (branch `d147-t-ends`, 1.x): an end on another edge's interior is not a free end.
### D148 — feature freeze: *1.0-ready* = `scripts/release_check.py` exits 0 and every commit on `main` keeps it at 0.
The gate list in TODO is closed and can only shrink.
### D149 — reopening D143: heal's per-entity deviation report is 1.x; the two-way fidelity test stays.
### D150 — `Result` lost `classified_entities`, `all_arcs` and `_open_shapes`.
### D151 — a loop that makes no contour goes to `loose`, one `OpenCurve` per edge, never dropped (`loops_to_curves`).
### D152 — a welded group spans ≤ 0.05; fidelity is tested per reading (`test_fidelity.py`).
`heal()` Hausdorff ≤ node tolerance, `island()` ≤ `max_gap`. Drawings in
`golden_islands/` and `golden_anchoring/` are read with `island()`, every
other with `heal()`.
### D153 — an ellipse discretizes on the parameter grid of the circle of radius `a`: within `tol` by proof, a piece is a piece of the whole.
### D154 — a curve of zero size is refused by the primitives; the DXF adapter turns a refused entity into a `doc.warnings` line.
### D155 — each closed gate item is one micro bump and one push.
### D156 — `contour_shape` measures `other` on the primitives (`segment_reach`); correctness over speed until the Rust engine.
### ~~D157~~ → D161: gate G6, the four doubts on D103 verified one by one.
### D158 — the gate closes on invariants: each promise of D143 is a permanent test on every fixture, in both readings.
The red ones *were* the rest of the gate.
### D159 — `tests/drawings.py` lists every tracked DXF with its reading.
A known red case is registered per case (`KNOWN`): it runs, must fail, shows
as a skip. Order dependence is a defect.
### D160 — the suite runs serial in under ~3 minutes, every test capped (`pytest-timeout` 60 s).
Readings are cached; a change that exceeds it is fixed in the same change;
after a red run only `--lf`, then one full run.
### D161 — `island()` reads **outer contours and nothing else**.
Every other piece goes to `loose` with `cluster_ref`; a closed loop inside an
outer has no meaning geometry can decide. `heal()` is untouched.
### D162 — a `loose` piece that closes by itself (one closed segment, or all nodes of degree 2) is one `ClosedCurve`.
The rest one `OpenCurve` per edge.
### D163 — a piece the border takes only in part leaves exactly its remainder in `loose` (`rim.off_rim`).
### D164 — a short `LineSeg` with a free end is a tip: welded only if both its nodes are touched by another edge.
### D165 — area is exact, integrated on the segments (Green); a gap closed within `tol` counts as its chord.
### D166 — no shapely type in the public surface.
`topo.to_shapely` is the explicit conversion; `contains` is the closed region;
a cluster converts even-odd; guarded by `test_no_shapely_surface`.
### D167 — geometry is written port-ready for Rust and the suite judges a port; the primitive is the truth, discretization a view.
### D168 — G13 closed (0.23.0); the old → new table is in the archive.
### D169 — dependencies are replaceable details, replaced only on a measure.
No shapely/numpy type in the surface; after 1.0 piece by piece, as D167
judges.
### D170 — `mirrored(*, origin, angle)` and `scaled(factor, *, origin)` on all primitives, exact, same type; no general affine map.
### D171 — `geometry.contour_union(contour, other)`: the rings of the union, shared border included; a border piece with no twin raises `ValueError`.
### D172 — `promote` takes one or several curves; all checks first; `item` is required for more than one.
### D173 — `promote` is a method of `Result`: it keeps D137's invariant.
### D174 — reopening D148: G14, one alignment of the API with how a mature library designs and evolves (scikit-learn).
"then it is a 2.0" is never an answer.
### D175 — the promise.
Public = `__all__` + cards; patch fixes, minor adds and deprecates
(`FutureWarning` for two minors, then a test forces removal), no major
planned; `topo.experimental` has no promise. Form: data positional / options
keyword-only, one way, mutation declared, typed returns, standard errors.
### D176 — G14 step 2 (0.25.0): options keyword-only.
Mutators return `None`; `split` copies; `set_schema`, `ignore_layers`,
`track_shape_type`, `split_to_files` removed; `validate_document`; non-stable
names in `topo.experimental`.
### D177 — `Text.target` and `references` are the objects (`repr=False, compare=False`), not paths; `split` relinks them.
### D178 — `test_surface_rules.py` declares every public callable's positional parameters (all data): a new one fails until a person decides.
### ~~D179~~ → D180: the union-of-faces network decided contacts by a grid cell.
### D180 — a contact is decided **once, on the true curves**, and gives one shared node (`split_at_crossings`).
A crossing, an end within `GRAPH_EPSILON`, or two curves within it; meetings
of one pair within `tolerance` are one; every type is cut. Node identity is
`GRAPH_EPSILON`, never `tolerance` (percolates).
### D181 — an angle-dependent contact is held by a micro-case read at eight angles (`TestScrambledMicro`), never by one more angle on whole drawings.
### D182 — a gap closes only at a meeting within reach of the end; else a segment.
### D183 — "within the tolerance" includes it: compare with `tolerance + FLOAT_NOISE` (1e-6 mm).
### D184 — "same line / same circle" is judged on the true segments (parallel within 1e-7, ends within 1e-3 mm), never by a rounded key.
### D185 — an end with two equally near partners closes no gap, and `heal()` says so.
### D186 — reopening D152: short strokes are grouped by shared nodes.
A group within diameter 0.05 is welded whole onto its smallest node, a wider
one is a curve and none of it is welded.
### D187 — one foundation for every reading (Federico).
A geometric rule is decided once, in one place (`base.prepare`, `normalize`);
a fix inside one reading is not a fix.
### D188 — `core/healing/` → `core/base/` and `core/readings/`; public names unchanged.
### D189 — one ingredient per job for both readings.
One `normalize`, one gap rule (the nearest point within tolerance, or where
the end's continued curve meets an edge; never a perpendicular bridge), one
planar network (`cut_crossings` is the reading's meaning), one non-contour
test, contours from `face_loops`, one `loose_curves`. Reopens D57, D60, D110,
D112.
### D190 — a non-finite number is refused by the primitive at birth; the DXF adapter drops the entity with a warning.
### D191 — G6e closes on a finite list of decisions in `core/`: each needs a red→green micro-case or a line on why it does not decide.
Exit reopened by D193.
### D192 — a meeting is decided in millimetres against `FLOAT_NOISE`, on the measure whose error is linear (the radial gap, not the half-chord).
### D193 — G6e leaves the gate on a counted bar: inventory closed, one re-pass at the call sites, the 121-drawing sweep once; the rest is fixed in 1.x.
### D194 — on a planar network a node is the piece's tuple; the graph does not re-judge it (`epsilon` 0 for identity).
### D195 — reopening D166's means: congruent copies are equal within `FLOAT_NOISE × perimeter` (area) and `FLOAT_NOISE` (`xmin`), chained along sorted values.
### D196 — G6e stays line by line: no shared noise module, no lint on comparisons.
### D197 — `concentric_groups` joins a circle to the nearest group within `tolerance`, not the first made.
### D198 — a node holding several distinct input endpoints is their mean (`fsum`, node grid), not the smallest in `(x, y)`.
### D199 — D100's union stays; its re-noding on discretizations is a known 1.x defect, to go only once the walk orders branches by how they leave a node.
### D200 — two islands are apart on the true curves (refined inside a band of 2·`DEFAULT_TOLERANCE` round `max_gap`).
A point of a piece says who hosts it.
### D201 — G6e closed for 1.0 on D193's bar.
Three residues go to 1.x: `hierarchy.py:70` (a tangent hole read as two
clusters), one drawing past 300 s, one 1 mm face read by frame.
### D202 — reopening G14 before 1.0: `heal()` repairs and returns a `Network`; `Network.faces()` and `Network.outlines()` read it.
One repair for every reading (no per-reading gap reach, junction rule or scope:
what differs today moves into the reading or goes). `island` → `outlines`:
"island" already names the depth-2 region. Clean break, no aliases (pre-1.0).
Two numbers, measured: `tolerance` (nodes) and `max_gap` (gaps, default `tolerance`); one number at 0.5 left a contour open by 0.41 mm, still `is_valid`.

### D203 — `loose` always comes from the repaired network, in every reading.
An island the reading does not read (frame, nested, no contour) no longer goes out
as drawn: doubles merged, gaps closed, like every other loose curve. The file as
drawn stays in `doc`. Measured: 0.000 mm of input lost on 51 drawings.

### D204 — `Network` carries what every reading copies: `source_file` (default `doc.source_path`), `label` (on the Clusters of both readings), `tolerance`, `max_gap`.
The two numbers are public because `heal()` resolves them (from the document, `max_gap ≥ tolerance`)
and a caller must know what was used. Built only by `heal()` (keyword-only fields); the
predicate, the texts and the planar net (`NodedEdges`) stay private. Modules: `heal.py`, `faces.py`, `outline.py`.
### D205 — `topo_dxf` explodes a pattern `HATCH` into its pattern lines, as plain `LINE` edges.
The adapter only translates: recognizing "a hatch" is the consumer's reading (rule 4), never
topo's. `jiggle_origin=False`: ezdxf otherwise shifts the pattern origin by `random.random()`,
and the same file read twice gave different `faces()`/`outlines()`. Solid fills stay a warning.
### D206 — a delivered contour is exactly closed; a gap is never hidden (G15, extends D143).
A gap within tolerance is closed by the engine: every segment starts where the previous one ends,
the last returns to the first. A jump left in a delivered contour is an engine bug, not a tolerance
case. A gap beyond tolerance leaves the profile open (in `loose`) with a warning; the rest of the drawing is still read.
### D207 — the 1.0 gate only shrinks, with a ratchet: no engine rewrites, a commit that adds a defect is reverted.
Measured: contours with a jump went 32 (0.23.0) → 48 (2 November) while the gate stayed at 7 items;
each rewrite broke what no test measured. A found defect goes to 1.x, never into a new G item;
the jump count never rises. Plan in TODO.md "PIANO".
### D209 — a jump within tolerance in a delivered contour becomes a new straight segment (G15, how D206 closes).
No curve is moved: the readings insert a `LineSeg` between the two ends (`close_contour_jumps`) and
say how many in `warnings`. Moving an end sideways changes the drawing; a new segment only adds what
the polygon already counted as its chord. A jump beyond tolerance stays an error.
### D210 — what is not a contour is removed by the consumer before `heal()`, by role (G16).
A hatch or any other fill is a meaning, not geometry: the consumer gives those edges a non-structural
role and `heal()` keeps them out of the network, in `loose`. topo does not recognize hatches. The
readings only rejoin what their own cut split; two different curves of the file are never merged.
### D211 — merging nearly collinear / cocircular curves is a public function on the result, 1.x.
Called by the user after `faces()`/`outlines()`, with their own threshold; never inside a reading,
never a flag (merging moves the vertex between two curves). `outlines()` still does it today via
`merge_runs`: removed when the function exists.
### D212 — D160's suite time is a 1.0 gate item (Federico, 6 November).
D160 was always in force; the TODO of 1 November filed it as "outside the gate", so nothing tracked it.
Last measured 4:27 against ~3 min.
### D213 — reopening D84: `to_text` is removed (Federico, 6 November).
It had no caller in any consumer, and the run that was to prove its value on anonymized drawings
was never made. `topo.experimental` carries no promise (D175), so it goes without deprecation; its
tests left the suite (~15 s). It is in git history if a caller ever needs it.
### D214 — 0.27.0: G15 and G16 closed (D155), with D202's `heal()` → `Network` and D209 since 0.26.0.
A minor, not a micro: the public surface changed after 0.26.0 (`heal()` returns a `Network`, read
with `.faces()`/`.outlines()`; a jump within tolerance becomes a new `LineSeg` with a warning).
`to_text` leaves `topo.experimental` (D213).
### D215 — reopening D143: "deterministic" means same bytes → same result; the same geometry under a motion is not promised (Federico, 7 November).
Every yes/no rule on a measured number has an edge, and the rounding of a rotation (~1e-14 mm)
can push a value across it; no tolerance, digit count or language removes the edge. Explained
for any reader in `docs/LIMITS.md` (`LIMITS_IT.md`). What can shrink is how many edges there are (D216).
### D216 — reopening D113: no node grid; two ends are one node by distance (Federico, 7 November).
A grid puts an edge every 0.001 mm; distance has one per threshold. Measured 6-7 November on a
copy with the grid off (4 lines): moved drawings changing contour count 123→21 of 3000 generated,
635→360 of 3998 harsh, 46→29 of 3551 real DXFs; jumps 4→0; same time. Done: `node_point`, no `decimals`
(experimental `split_at_crossings`/`refit_tessellations` lose it, D175); G6e's chord case closes.
### D217 — a circle written twice is one circle: `merge_cocircular_overlaps` takes `CircleSeg` as a full turn (D52).
Before, two equal circles were two holes with no warning; an arc over a circle now vanishes into it.
### D218 — free arcs on one circle join across every hole within tolerance and ≤ 2°; all holes closed is a circle (Federico, 7 November).
D112's rule judged one arc only: two arcs with 1.72° holes got two segments; with holes of 1° and 3° the 1° joins and
one arc stays open by 3°, as a lone arc would (a thread is a ~270° arc and must stay open, snapbend).
### D219 — a closed curve has one node, its start, however its Edge was written: `renode` sets it, as `Edge.of` does.
`renode` left closed curves' nodes as given: an Edge whose end was re-evaluated 1e-13 from its start (`rotate_document`,
a hand-built Edge) stayed open, and a closed spline crossing itself went whole to `loose` in `outlines()`. D216/D187:
the node comes from the geometry, once, for every reading.
### D220 — G7 closed (Federico, 7 November): every golden is current, no expected failure; known defects stay as 1.0 limits in TODO.
Island goldens regenerated after review beside the original (inners 0 by D161; a circle crossed by a V keeps
the tip, D101); anchoring goldens accepted without judging (22 texts lost their anchor, TODO). No `_noframe` goldens.
### D221 — "island" means one thing: the depth-2 region (Federico, 7 November). `spatial_islands`/`Island` → `experimental.touching_groups`/`TouchingGroup`.
The name says the job (edges that touch within a distance); it stays public, the step of the compose-your-own recipe
(`experimental` carries no promise, D175). Tests, data and scripts name the readings `faces`/`outlines`
(`golden_outlines/`, golden key `clusters`, values unchanged); D202's rename finished.
### D222 — Tests are filed by what they prove (Federico, 7 November): `engine/`, `promises/`, `golden/`, `adapters/dxf/`, `package/`, `tools/`.
`engine/` mirrors the package (primitives, geometry, topology, base, readings, model, tools, io); `promises/` holds the
invariants on every drawing, `golden/` the comparisons, `adapters/dxf/` what proves the format, `package/` the guards on
the whole package. unit/integration/real sorted by size and no longer held. Paths come from `tests/paths.py`, never `__file__`.

### D223 — The tracked DXF is the fixture; ezdxf generators go (Federico, 7 November).
The adapter tests (writeback, split) need a real source file, so building the same drawings with topo would not remove
one: the files stay, the 4 generators written with ezdxf go (rule 2; they live in git history). Byte-identical copies
nobody reads by name go too: the invariants already read each content once.

### D224 — A test file that proves one promise across layers stays whole (Federico, 7 November).
D222 files by what a test proves: `test_role_palette` (one palette in DXF and SVG), `test_text_role`, `test_degenerate_curves`
are one promise end to end and are not split by layer. A test moves when its subject is another one (e.g. the DXF
dimension string inside the anchoring tests), and a move that would mean rewriting the test is not a move.

### D225 — A near-copy of a line within `tolerance` closes a thin face, and that is the right reading (Federico, 8 November).
Two parallel lines 0.18 mm apart at tolerance 0.5 are two distinct curves: nothing in the geometry says one is a
mistake. The tolerance joins their ends, not the lines; once joined the thin ring is a closed face and `faces()` gives it
(`outlines()` does not). "This line is a stray copy" is a reading of intent: the consumer's, before `heal`. Not D184's authority.
### D226 — reopening D211: the near-copy merge takes curves and gives curves; the caller calls it wherever they want (Federico, 8 November).
Before `heal()` it closes contours a near-copy keeps open, which on a result it cannot. topo never applies it and never takes
a flag for it. `heal()` warns of each pair of lines nearly on one another but outside D184's thresholds: where, which, how much.
### D227 — a warning is a `topo.Diagnostic`: what, where, why topo left it, and the call with the smallest threshold that fixes it (Federico, 8 November).
Rust-style, for humans and LLMs alike. It subclasses `str`, so every `warnings` list stays a list of strings and
nothing breaks; `code`/`at`/`param`/`value` let a program act without parsing. New warnings use it, old ones move one
at a time. The `help` value is computed from the case and rounded up, never a guess. A warning says what nearly closed:
`open-arc` only while at most 8° are missing (Federico), so a thread (~90° open) never warns, whatever its radius.
One Diagnostic per kind (Federico): the text shows three places, `points` holds all. `near-gap`: a free end whose
partner, by the gap rule itself, is beyond `max_gap` and within twice it; past that it is geometry, not a missed gap.

### D228 — linking a text to the elements it touches is experimental; the declared goal is the link on the raw edges (Federico, 8 November).
`anchor_texts` sets only `cluster_ref` (containment, D82). `target`/`references` come from `topo.experimental.anchor_elements`
(with `pointer_target`, `measured_references`): their candidates depend on the reading (with `outlines()` on view sheets 63%
of the dimensions link nothing, open curves are never candidates), and what a dimension relates (datum, hole to edge) is the
reader's. Goal, 1.x: one new form that links to the edges of the network, independent of the reading; nothing in between.

## Open questions

- **Name of the role `outer`** in the outlines reading: unresolved; it stays
  `ContourRole.OUTER` (renaming touches `heal`, golden and layers).
- `inspect_dxf` wants an entity-type filter (`types`): queued.
  face 1 mm wide read as outer or inner by frame.

### D229 — one name, one copy (Federico, 8 November): a drawing lives in one folder of `tests/data/`, found by `tests.paths.drawing(name)`.
A copy in two places is edited in one while a test reads the other. Byte-identical copies went (42 files, 36 names);
`tests/package/test_one_copy.py` fails on a new double. Names still double with different content are a shrink-only list there.

### D230 — topo's JSON is geometry only (Federico, 8 November): `Result.to_dict()` is its one source, `to_json`/`save_json(extra=)` add a consumer's fields per cluster.
Material, thickness and quantity are a process's, renaming fields for a CAM is the consumer's, and units are not topo's (the
drawing's units, no `_mm`). Out: `metadata_schema`, `schema=`, `build_metadata`, `save_xml`, `inject`, `Cluster.custom`,
`to_nester_input`, `topo_dxf.write/read_metadata_*` (XDATA gives a bad DXF, Federico). One extension slot: `cluster.detected`;
an `extra` key topo already writes raises `ValueError`, so a consumer's field never silently replaces a geometric one.
### D231 — the source format travels: `Document.source_format` (the adapter says `dxf`, `pdf`, `geometry`, …) reaches every `Result` with `tolerance`, `max_gap` and `reading`.
A JSON read alone must say where the geometry came from and how it was read; the value is the adapter's, an open string.
### D232 — `split` drops nothing by default (`min_area=0.0`) and works on both readings (Federico, 8 November).
A smallest size is a process threshold: 50 mm² is scrap on a sheet and a real part on a watch drawing.
### D233 — every warning is an English `Diagnostic` in topo's words (no `LINE`, `SPLINE`, modelspace in the engine): done with G9 and the rename of the old names (Federico, 8 November).
Three levels: `warnings` advise on the drawing, `notes` say what topo did by itself (not shown every time, never
hidden: D206), `errors` mean nothing to read. Codes closed, listed in LLM.md, held by `tests/invariants.DIAGNOSTIC_CODES`.
### D234 — D124 stays: one repo, the adapter tests in `tests/adapters/`, the engine tests read the tracked DXF (D223) (Federico, 8 November).
Splitting topo_dxf out means two releases kept in step and 158 drawings converted to a format-free fixture, for no measured gain.
### D235 — a near-copy lies over the longer line: both its ends project inside it (Federico, 9 November).
A piece past the longer line's end continues the contour; within `distance` of that end it was taken for a copy, and the
`near-copy` help removed it and opened the contour (brute force: 67,844 pairs in 346 seeds, >90% such pieces). No angle
limit: measured, 5° or 1° on top of this changes nothing (help right in 235 / 235 / 231 of 351).
### D236 — a ring within 0.02 mm of a circle all the way round is that circle, at any side length (Federico, 9 November).
After the gaps close, a connected group's core (free branches set aside) within 0.02 mm of one circle all the way
round becomes a `CircleSeg`, with free pieces lying on it; radius mid-band, lines measured at their nearest point, so a
real polygon stays. D60's 0.1 mm side left 0.14 mm sides as lines and broke damaged holes into lines + arcs + splines.
### D237 — `near-copy` stays as it is for 1.0 (Federico, 9 November).
heal() reads both lines and changes nothing; only the help can mislead, by calling the experimental merge on a real corner.
A 1.x fix narrows where it fires; code, message and fields stay.
### D238 — `cluster.detected` → `cluster.overlay`, `DetectedFeatures` → `Overlay`, JSON key `overlay`; `DetectedFeature` removed (Federico, 9 November).
topo detects nothing: the layer is where a consumer writes its own reading (D44, D90). Clean break before 1.0 (0.28.0); the Protocol had no user. Consumers adapt in their own sessions.
### D239 — for 1.0 the source stays the working notebook: internal comments and docstrings Italian, D## references kept (Federico, 9 November).
Only what a user reads (README, docs/, public docstrings) is the public face (D144). Translating 84 internal files or dropping 484 D## gives a user nothing for 1.0.
Whether D## belong in the code at all is an open thread: Federico discusses it with the forum first; until then nothing is removed.
