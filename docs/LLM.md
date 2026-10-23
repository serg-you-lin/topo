# topo — AI reference

Dense, token-minimal reference for an AI writing code against `topo`. No
narrative, no rationale — those live in `API.md` (full reference), `ARCHITECTURE.md`
(why), `MAP.md` (decision history), `INDEX.md` (generated inventory of every
module-level name, internal helpers included — the place to check before writing
a new one). Load this file alone to use the library; load the others only if this
one doesn't answer the question.

## What it is

Deterministic 2D-geometry reconstruction engine for technical drawings.
Not a DXF library: `topo` knows no file format (D123). One distribution
(`g-topo`), three packages: `topo` (the engine; `shapely`, `numpy`),
`topo_dxf` (DXF/DWG adapter, `g-topo[dxf]`, brings `ezdxf`), `topo_pdf`
(experimental, `g-topo[pdf]`). `topo` never imports an adapter; an adapter
uses topo's public names only (D129, checked by `gen_index --check`). Takes messy CAD
geometry (DXF/DWG via `topo_dxf`, experimental PDF, or raw point/primitive dicts) and
produces a lossless domain model: healed closed contours, a containment
hierarchy, texts, an open overlay for features a consumer detects
(snapbend's `detect_flat()` attaches holes/bends/engraving; topo itself knows
no process — D88) — then renders that model to DXF, JSON, XML, SVG, or a
render-oriented view-model dict. Everything unclassified survives in
`loose`; nothing from the source is silently dropped.

Process-agnostic by design: sheet/plate manufacturing is topo's first consumer,
not its scope. The manufacturing vocabulary (`hole`/`countersink`/`threaded_hole`/
`bending`/`engrave`/`marking`) and the detection that uses it live in snapbend
(`snapbend.flat`, D88). The engine itself knows three roles and no material,
process or product.

## Pipeline

```
topo_dxf.load_dxf / load_geometry / load_segments  →  Document   (edges + texts, zero topology)
heal(doc)                                       →  Result     (topology only: closed contours, outer/inner tree — NO hole/bend classification)
island(doc, max_gap=)                           →  Result     (alternative to heal for drawings of VIEWS: one cluster per outer contour not inside another, outer = outer face of its planar network)
(a consumer's reading, e.g. snapbend.flat.detect_flat)  →  writes cluster.detected (the open overlay)
split(result)                                   →  list[Result], one per part (no format)
topo_dxf.to_dxf / to_json / save_json / to_svg / to_view_model  →  render from the model (never re-reads source)
```

### Which output gives you what

Every `to_*` renders the same model; pick by what you need, not by habit. If
you are running Python, the `Result` itself is the richest source: query
it directly and render only what you hand on.

| output | what is in it | exact curves | coordinates | texts | `detected` | weight | use it when |
|---|---|---|---|---|---|---|---|
| `Result` (in memory) | everything: contours, segments, roles, loose curves, texts with `references`/`target`, `detected` | yes (native primitives) | full precision | yes | yes | — | you can run code: ask the model, don't parse an export |
| `topo_dxf.to_dxf` | the geometry back as CAD, one layer per role | **yes** (arcs, circles, native `SPLINE`) | full precision | yes (opt.) | written per item (D70) | like a DXF | a machine or a CAD user needs the file |
| `to_json` / `save_json` / `save_xml` | per-part metadata (counts, areas, bbox, custom fields) | — | **none** | no | counts only | tiny | a business system needs numbers about parts |
| `to_view_model` *(outside 1.0 stable, D133)* | every feature as polylines + role + colour | no (discretized) | full precision | yes | every collection drawn under `features` (D90) | can exceed the DXF on sheets of views | an external renderer draws it |
| `to_svg` *(outside 1.0 stable, D133)* | the view model as an image | no (discretized) | full precision | yes | as the view model | like the view model | a person looks at it |
| `to_text` *(experimental, D84)* | contours named by shape with ids (`C1.3`), unnamed ones side by side, open edges inside clusters, measures/pointers by id, texts, `detected` generically, what was not understood | splines described (ends, bbox, length); exact data with `spline_data=True` | rounded (`decimals=3`) | yes, by id | yes, generically | a fraction of the DXF; size watched by `tests/real/test_text_budget.py` | a language model has to answer questions about the drawing |

`topo_dxf.split_to_files(doc, folder)` = `heal` + `split` + `to_dxf` + `.saveas()` per part — the only function that writes to disk on its own.

## How to write a call

`import topo` (plus `import topo_dxf` to read or write DXF), then every name
with its full path: `topo.heal(...)`, `topo_dxf.load_dxf(...)`, `topo.Result`, `topo.geometry.contour_shape(...)`, `topo.steps.find_loops(...)`.
Never `from topo.steps import find_loops` or `from topo import steps`: a name
read alone in the middle of a script doesn't say whose it is;
`topo.steps.find_loops` does. Every example in this file follows it — write
your code the same way (D119).

## Golden path

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("part.dxf", tolerance=0.5)
check = topo.validate(doc)                      # input validation, optional
result = topo.heal(doc, label="P-1024")
if not result.is_valid:                           # check before handing output to a machine
    raise SystemExit(result.errors)
topo_dxf.to_dxf(result, doc).saveas("out.dxf")
for part in topo.split(result):                   # one Result per part, any format
    topo_dxf.to_dxf(part, doc).saveas(f"{part.clusters[0].label}.dxf")
topo.save_json(result, "out.json")
```

## Functions — `topo.<name>`

| name | signature (defaults trimmed) | does |
|---|---|---|
| `RoleRule` | `(role, name=None, name_contains=None, dashed=None, dash=None, color=None)` | a rule: all given conditions true → `role`. `name`/`name_contains` = source group name (the DXF layer, case-insensitive); `dashed` = linetype pattern has a gap (`EdgeStyle.is_dashed`), not the linetype name (chains included); `dash` = `"continuous"`/`"uniform"`/`"chain"` (`EdgeStyle.dash_kind`: chain = marks of different lengths alternate, e.g. long dash + dot; uniform = one mark repeated), unknown value → `ValueError`; `color` = effective RGB: `(r, g, b)`, `"#rrggbb"` or a base name (`cyan`, ...); a DXF ACI index is read as its canonical RGB (7 is white), an int is an error (D126). No condition, or unknown colour name → `ValueError`. topo ships no vocabulary: the caller writes the rules (D63). |
| `name_rules` | `(mapping: dict[str, str]) -> list[RoleRule]` | `{name: role}` → one `RoleRule(role, name=...)` per entry. |
| `load_geometry` | `(entities: list[dict], tolerance=0.05, source_path="") -> Document` | builds a `Document` from pure geometry, no file. Entity `type`: `line`(start,end) / `arc`(center,radius,start_angle,end_angle deg,ccw) / `circle`(center,radius) / `polygon`(points; always closed, D96) / `spline`(control_points,knots,degree,weights?) — `BSplineSeg` carries geometry only, `closed`/`periodic` are derived (D135) / `ellipse`(center,major_axis vector,ratio?,start_param?,end_param?,ccw?). Optional `role` per entity, same open vocabulary as `RoleRule.role`. |
| `load_segments` | `(segments, tolerance=0.05, role="unknown", source_path="") -> Document` | a `Document` from topo segments (or lists of them, e.g. the `topo.geometry` builders); every edge gets `role`. The way to draw with topo in hand: `topo.load_segments(fg.rectangle(200, 100) + fg.circle(5))` (D96). |
| `validate` | `(doc: Document) -> Result` | input validation, no mutation. `is_valid=False` = unworkable (no geometry / NaN / all-degenerate). Warnings = workable but flagged. |
| `validate_result` | `(result: Result) -> Result` | output validation, **mutates** `result`. Called automatically by `heal()` — call manually only if you build a `Result` another way. |
| `heal` | `(doc, tolerance=None, label="", source_file="", is_structural=None) -> Result` | topology reconstruction: gap-closing, non-contour edge exclusion (candidates for "something else" — `non_contour_candidates()` exposes the same criterion, see below), loop search, outer/inner containment tree. Does **not** classify holes (D15). `tolerance=None` → reuses `doc.source_meta["tolerance"]`. If no closed outer forms, `result.is_valid=False`. `is_structural(role)->bool` decides which already-labeled edges stay in the graph — `heal()` alone knows only outer/inner; without it a labeled `"hole"` is treated as non-structural (excluded, warned). A consumer passes its own (snapbend: `snapbend.flat.is_structural`). |
| `island` | `(doc, *, max_gap, tolerance=None, is_structural=None) -> Result` — `max_gap` required, by name, no default (D98); no layout distance (D99) | the other way to read a document (see "Reading drawings of views" below). Same output contract as `heal()`: pieces are the edges that touch (within `max_gap`); one `Cluster` per outer contour that is not inside another (`outer` + `inners` = closed loops inside); a piece whose outer lies inside another's becomes interior of the outermost one. A piece that closes by itself (one closed segment, or a chain where every node has degree 2: a hole, a slot, a whole view inside the frame) goes to `loose` as one `ClosedCurve` — read it with `contour_shape` (D162); other edges go to `loose` as `OpenCurve` with `cluster_ref` = index of the island they touch or that contains them, `None` outside every island (D99, D137). Edges with a decided non-structural role (`frame`, `title_block`...) are left out and go to `loose` with their role — same D30 contract as `heal`. No closed outer anywhere → `is_valid=False`. Contour segments come back recomposed where the planar network split them: consecutive pieces on the same circle/line, same direction and style, are one segment — a hole crossed by its axes is one `CircleSeg` (D65; polygons unchanged). A nested island gives its host **all** its closed loops, also those outside the loop chosen as its outer — a group of detached holes in the middle of a view (D71). |
| `read_islands` | `(edges, tolerance, max_gap) -> list[IslandReading]` | `island()` before it becomes a `Result`: per piece (edges that touch) what was decided, edge by edge; `nested_in` also for a piece with no outer whose edges all lie inside an island. `IslandReading`: `edges`, `outer: OuterFace\|None`, `inner_loops`, `spurs`, `outside`, `non_contour`, `unclassified`, `nested_in: int\|None`. |
| `read_island` | `(edges, tolerance, max_gap) -> IslandReading` | one island: normalize (renode, `refit_tessellations`, heal's merge/weld, gaps up to `max_gap`), `split_at_crossings`, `outer_face`, classify the rest. |
| `steps.spatial_islands` | `(edges, gap_tolerance) -> list[Island]` | union-find on edge pairs within true segment distance `gap_tolerance` (STRtree). No notion of closure. `Island`: `edges`, `bbox`, `.width`, `.height`. |
| `steps.split_at_crossings` | `(edges, tolerance, decimals=3) -> NodedEdges` | planar network: `LineSeg`/`ArcSeg`/`CircleSeg` split wherever another edge crosses or touches them (T within `tolerance`). Node identity, format-agnostic (D101): two cuts within `tolerance` of each other are one node, not two — a near-tangent line/arc crosses at two mathematically distinct roots a fraction of a mm apart; treating them as separate nodes leaves a sliver edge between them that can split a face in two. `NodedEdges.pieces`, `.parent_of(piece) -> Edge`. Splines/ellipses stay whole. |
| `steps.outer_face` | `(edges, epsilon=0.0) -> OuterFace\|None` | outer contour of a planar network: walk of its outer face starting from the leftmost geometric point, per connected component, largest area wins. `OuterFace`: `polygon`, `segments`, `styles`, `loop`, `.edges`, `spurs` (walked there and back — axes, marks). |
| `steps.refit_tessellations` | `(edges, max_segment=0.1, min_run=10, tolerance=0.02, node_decimals=3) -> list[Edge]` | a chain of ≥`min_run` short `LineSeg`s (a curve written as points) is refitted by `simplify_points` (lines/arcs/splines within `tolerance`, corners as a turn over `max_segment`, D141); chain ends keep their original nodes. |
| heal steps, all in `topo.steps` (D117) | `merge_collinear_overlaps`, `merge_cocircular_overlaps`, `weld_degenerate_linesegs`, `split_non_finite(edges) -> (finite, broken)`, `split_labeled(edges, is_structural=None) -> (kept, labeled)`, `close_near_full_arcs(edges, tolerance, max_missing_angle=NEAR_FULL_ARC_MISSING) -> (edges, n)` (arc → circle only if the gap is within `tolerance` AND at most 2° are missing; `tolerance=math.inf` for angle only, D112), `close_free_gaps(edges, tolerance)` (free ends paired two by two by nearness, never an edge with itself: a side shorter than the tolerance stays, D112), `dangling_splines(edges)`, `find_non_contour_edges(edges, tolerance) -> set[id]`, `find_joining_edges(edges, candidate_ids)`, `free_ends(edges, epsilon=0.0) -> [(point, mm)]`, `find_loops(edges, non_contour_ids, tolerance) -> LoopSearch`, `repair_merged_corners(edges, tolerance, exclude_ids) -> (edges, n, skipped)`, `structural_loops(loops, is_structural=None)`, `loops_to_curves(loops) -> [ClosedCurve | OpenCurve]` (a loop that makes no contour — no area, a micro-circle — comes back as one `OpenCurve` per edge, D151), `polygonize_edges(edges, tolerance) -> list[Polygon]`, `polygons_to_curves(polygons)`, `edges_to_open_curves(edges, exclude_ids)`, `labeled_curves(edges)`, `build_hierarchy(features, label="", source_file="", is_structural=None) -> (clusters, loose)` | `heal()` is a recipe composing these, in this order (D62); compose your own (e.g. stop before `build_hierarchy`). None mutates its input. `LoopSearch`: `edges` (after corner repair — use these downstream), `loops`, `method` (`"exact"`/`"corner_repair"`/`"tolerant"`/`"none"`), `repaired`, `skipped_corners`, `unrepaired_corners`, `open_nodes`. When `method == "none"`, `heal()` falls back to `polygonize_edges` + `polygons_to_curves`. |
| `promote` | `(result, curve, cluster, name, item=None) -> None` | moves `curve` out of `result.loose` into `cluster.detected[name]` (`item` = what you made of it, else the curve itself), creating `detected` if needed (D137). Position doesn't bind: any loose curve to any cluster — a guide line outside a part can belong to it. Raises `ValueError` if `curve` is not in `result.loose` or `cluster` not in `result.clusters`: never in both places, never dropped. topo promotes nothing by itself. |
| `split` | `(result, namer=None, min_area=50.0) -> list[Result]` (`DEFAULT_MIN_CLUSTER_AREA`) | one `Result` per kept part, no format (D124, D129): its one cluster plus the loose curves and texts that belong to it — a loose curve goes to its `cluster_ref`'s part (D137), a text to the part that contains it, else the nearest of **all** parts; nothing duplicated or lost; each copied with `cluster_ref` relative to the part (`0` or `None`); promoted curves travel inside `cluster.detected`; other fields copied. `namer(i, cluster)` sets `cluster.label` (default `f"{label}_P{i+1}"`). Parts under `min_area` mm² dropped with a warning. **Mutates** labels and `result.warnings`. Raises `ValueError` if `result` is invalid. Write each part with any renderer: `topo_dxf.to_dxf(part, doc)`, `topo.to_svg(part)`. No `on_part`: your loop is the hook. |
| `inject` | `(result, data_injector=None, snap_distance=0.0) -> Result` | optional enrichment from texts. **Mutates** `cluster.custom`. `data_injector(cluster, list[str]) -> dict` receives the strings of `result.texts` inside each part's outer; `snap_distance > 0` also hands a text outside every part to the nearest one within that distance (same rule as `anchor_texts`, D82). No-op without `data_injector`. |
| `anchor_texts` | `(result, snap_distance=0.0, pointer_distance=0.5) -> Result` | assigns `Text.cluster_ref` — which cluster a text belongs to, by containment (+ optional snap distance for texts just outside) — `target` via `pointer_target` for texts with a `pointer`, and `references` via `measured_references` for texts with `measured_points`. **Mutates** texts in place, also returns. Run it after a consumer has chosen its features (a detection that moves holes from `inners` to `holes` makes targets computed before go stale). |
| `pointer_target` | `(result, text, distance=0.5) -> str\|None` | element the tip of `text.pointer` (`pointer[0]`) lands on, as a path in `result`: `"clusters[0].outer"`, `"clusters[0].inners[3]"`, `"clusters[1].holes[2]"` (any `cluster.detected` collection), `"loose[4]"` (a closed curve in `result.loose` without a non-structural role, D162). Nearest boundary within `distance` (tie → smaller element); else smallest closed non-outer element covering the tip; else `None` (e.g. arrows outside the view). Geometry only, never reads the string (D66). |
| `measured_references` | `(result, text, distance=0.5) -> list[str]` | elements the `measured_points` of `text` fall on, as `target`-style paths: for each point, the element whose boundary passes within `distance` (tie → smaller). No duplicates, in point order: two opposite points on a circle give the circle, two ends one or two elements. Pure geometry — reading `"M5"` as a thread is the reader's job. |
| `resolve_target` | `(result, target) -> Any` | inverse of `pointer_target`: the contour/feature object, or `None` if the path no longer exists. |
| — | — | **Geometry facts live in `topo.geometry`** (package `topo/core/geometry/`, D95): call `topo.geometry.contour_shape(...)` etc. with the full path — never `topo.contour_shape`, never the name imported bare (D119). Helpers not exported in `topo.geometry` (in `measure`, `points`, `lines`, `axis`) still live in the submodules of `topo.core.geometry`: internal, no guarantee until the 1.0 public surface. |
| `geometry.polygon` / `rectangle` / `regular_polygon` / `circle` / `ellipse` / `stadium` | `polygon(points)`, `rectangle(length, width, center=(0,0), angle=0)`, `regular_polygon(sides, radius, center, angle)`, `circle(radius, center)`, `ellipse(length, width, center, angle)` (one full `EllipseSeg`), `stadium(length, width, center, angle)` -> list of segments | build a closed loop as topo segments (stadium with true `ArcSeg`s), feed it to `load_segments`. Arguments are what `contour_shape` reports (angle in degrees), so build and read round-trip. Rhombus, trapezoid, any straight-sided shape = `polygon` (D96). |
| `geometry.contour_shape` | `(item, tolerance=0.01, angle_tolerance=1.0) -> ContourShape \| None` | shape of a closed contour (`Contour`, a `ClosedCurve` in `loose`, anything with `.segments`, or a segment list; `None` if the segments do not close in a ring, D162): `kind` = `ShapeKind` (a `str` enum) `circle` / `ellipse` / `stadium` / `rectangle` / `polygon` / `other` — **closed and stable (D136)**: no new kind in 1.x and a contour never changes kind; rules read primitives as they are (equal-axis ellipse = circle, a spline circle stays `other`; rounded rectangle = `other`). Plus `center`, `length`, `width` (circle: both = diameter; ellipse: the two axes; stadium (two equal semicircles + two parallel lines — geometric name, not "slot"): overall length, 2r), `angle` (deg [0,180) of the long axis, `None` for circle), `sides`, `diameter`. A geometric fact, **not** a feature: `circle` does not mean hole. Same on `heal` and `island`. Collinear/co-circular runs are recomposed first (D68). |
| `geometry.concentric_groups` | `(items, tolerance=0.1) -> list[ConcentricGroup]` | circular contours of `items` partitioned by center (absolute tolerance, drawing units); every circle in exactly one group, singletons too. `ConcentricGroup`: `center` (smallest circle's), `items`, `shapes`, `diameters`, smallest radius first. Geometric fact: pairing circles into countersinks/seats is the consumer's (D91). |
| `geometry.arcs_around` | `(center, radius, arcs, tolerance=0.1) -> list[ArcAround]` | `ArcSeg`s concentric to a circle and larger, nearest first. `ArcAround`: `arc`, `sweep` (degrees, in the arc's direction), `radius_ratio`. No angle threshold: "~270°, ratio ≤ 1.6 = thread crest" lives in snapbend/snapdraw (D91). |
| `geometry.splits_polygon` | `(polygon, start, end, reach=0.0) -> bool` | the chord start-end, extended by `reach` at both ends, cuts the (shapely) polygon into 2+ parts. Geometric fact; "it is a bend" is the consumer's reading (D93). |
| `geometry.bridged_runs` | `(segments, bridges, tolerance=0.1, angle_tolerance=1e-6) -> list[CollinearRun]` | runs of 2+ collinear segments (`LineString` or `(start, end)`) where each gap lies inside one of the `bridges` polygons (e.g. a part's voids). `CollinearRun`: `start`, `end`, `members` (indices into `segments`, ordered along the line). Also in `topo.core.geometry.lines`: `are_collinear`, `group_collinear_lines`, `point_line_distance` (D93). |
| `geometry.dash_line` | `(start, end, head, tail, middle=0.0, n_middle=0) -> list[(Point, Point)]` | the segment cut into dashes: `head` anchored at `start`, `tail` anchored at `end`, `n_middle` dashes of `middle` between them, all gaps equal. Whole segment back if the dashes cover it; zero-length dashes dropped; negatives raise `ValueError` (D115). |
| `geometry.intersections` | `(a, b) -> list[Point]` | where two primitives meet (crossings and touches, ends included). Exact for `LineSeg`/`ArcSeg`/`CircleSeg`; within 1e-4 on splines/ellipses. Overlapping pieces give no point (D118). |
| `geometry.point_on_contour` | `(segments, point, tolerance=0.01, angle_tolerance=1e-3) -> ContourPoint \| None` | where a point falls on a ring: `kind` `vertex` / `smooth` (tangent joint) / `edge`, `segments` (indices), `turn_deg`, `concave` (from the ring's direction, exact tangents) (D118). |
| `geometry.nearest_point` | `(segments, point) -> Point` | the point of a ring (or any primitives) closest to any point, mid-side included; exact on lines/arcs/circles, splines and ellipses within 1e-4. Snap a click with it, then `point_on_contour` says where it fell (D140). |
| `geometry.cut_by` | `(segment, region, keep="outside") -> list` | pieces of `segment` outside/inside a closed region (any ring of primitives: `circle`, `rectangle`, `contour.segments`); same primitive type; piece along the border raises `ValueError` (D118). |
| `geometry.contour_minus` | `(contour, region) -> list[list]` | rings left of `contour` minus `region`, head-to-tail: outers keep the contour's direction, a hole is opposite; `[]` if covered, `[contour]` if apart; several rings if a piece is cut off — the caller picks. Shared border raises `ValueError`. Feed to `Contour.from_segments` (D118). |
| `geometry.covered_rectangles` | `(items, min_side, eps=0.5, cluster_tolerance=1.5, coverage=0.85) -> list[CoveredRectangle]` | axis-aligned rectangles whose 4 sides are covered ≥ `coverage` by straight items (anything with `start`/`end`), built on items ≥ `min_side`. No polygonize: tick marks on a border don't break it, a double border gives two. `CoveredRectangle`: `polygon`, `items` (on its sides), `bbox`, `area`, `long_side`, `short_side`, `ratio`. "Frame"/"title block" is snapdraw's reading (D94). |
| `geometry.spanning_lines` | `(bounds, items, coverage=0.85, eps=0.5, cluster_tolerance=1.5) -> (ys, xs)` | lines strictly inside `bounds` crossing ≥ `coverage` of its width (horizontal) / height (vertical). |
| `geometry.sides_on_border` | `(bounds, border, tolerance) -> list[str]` | sides of `bounds` (`left`/`bottom`/`right`/`top`) lying on the same side of `border` within `tolerance`. |
| `geometry.axis_aligned_share` | `(segments, angle_tolerance) -> float\|None` | share of `LineSeg` length within `angle_tolerance` degrees of horizontal/vertical; `None` with no `LineSeg`. Also in `topo.core.geometry.axis`: `merge_intervals`, `interval_coverage`, `cluster_values`, `axis_lines`, `items_inside`. |
| `to_json` / `save_json` | `(result, indent=2, extra_metadata: Callable[[Cluster], dict]=None) -> str / None(writes path)` | per-part metadata per `rules/metadata_schema.py`, no coordinates. `extra_metadata(cluster)` called once per cluster, result merged in outside the schema. |
| `save_xml` | `(result, path, extra_metadata=None) -> None` | same fields as `save_json`, XML. |
| `to_view_model` *(outside 1.0 stable, not in `__all__`, D133)* | `(result, tolerance=0.05, include_loose=True, include_texts=True, role_styles=None) -> dict` | render-oriented JSON: every feature's coordinates + role + hex color (topo's palette with `role_styles` on top), **discretized to polylines**; the overlay under `cluster["features"][name]`, one entry per contour plus the scalar fields of the item's `to_dict()` (D90). Feeds `to_svg`; usable by an external renderer. |
| `to_svg` / `save_svg` *(outside 1.0 stable, not in `__all__`, D133)* | `(result, tolerance=0.05, include_loose=True, include_texts=True, padding=0.03, background="#1e1e1e", true_circles=True, stroke_width=None, size=None, units=None, allow_invalid=True, role_styles=None) -> str / None(writes path)` | SVG render, one `<g data-cluster>` per part, Y flipped. `units="mm"` = true scale (1 unit = 1 mm), e.g. for a machine that imports SVG. Geometry still discretized — use `to_dxf` when exact curves matter. Invalid result rendered anyway; `allow_invalid=False` → `ValueError` (D83). |
| `build_metadata` | `(cluster, schema=None, extra=None) -> dict` | one cluster's metadata per the active schema: the single source of `save_json`, `save_xml` and `topo_dxf.write_metadata_to_dxf`. |
| `set_schema` | `(schema: dict) -> None` | replaces the active metadata schema at runtime (for pip-installed use where you can't edit `metadata_schema.py`). |
| `inspect_document` / `inspect_result` | see below | debug print of levels 2–3, stdout only; level 1 (the raw file) is `topo_dxf.inspect_dxf`. |
| `normalize_role` / `is_structural_role` | `(value) -> str` / `(role) -> bool` | role-vocabulary primitives (see below). `is_structural_role` is the engine's own minimal predicate (outer/inner only) — a consumer passes its own extended one to `heal(is_structural=...)`. |
| `RoleStyle` | `dataclass(color: tuple[int,int,int]|None, linetype: str|None, dash: tuple[float,...]|None, lineweight: float|None)` (`topo.RoleStyle`, `topo.model.RoleStyle`) | how the caller wants a role drawn, no format (D37, D128): passed as `role_styles={role: RoleStyle(...)}` to `to_dxf`/`split`/`split_to_files`/`to_svg`/`to_view_model`. Always on top of topo's palette: `None` fields keep the palette's. `dash` uses `EdgeStyle.dash` signs; in DXF it is registered as `linetype` or `<ROLE>_DASH`. A `linetype` with no `dash`, neither in the output document nor in ezdxf's standard table → `ValueError` (D85). Where a role goes is not here: `to_dxf(layers=...)`. |
| `DEFAULT_ROLE_STYLES` / `CONSUMER_ROLE_STYLE` / `role_style` | `topo.model`; `role_style(role, role_styles=None) -> RoleStyle` | topo's palette (D128), one for every format: `outer` green (0,255,0), `inner` yellow (255,255,0), `unknown` red (255,0,0), any other role gray (128,128,128). `role_style` = palette with the non-`None` fields of the caller's map on top. Every exporter calls it and only translates; an adapter author picks no colours. |
| `non_contour_candidates` | `(doc, tolerance=None) -> list[Edge]` | same topological criterion `heal()` uses internally to exclude an edge from the contour graph (a chain of edges through degree-2 nodes, ending on two distinct branching nodes, that the boundary of its connected component's outer face does not traverse exactly once — D111, D131) — asserts **no** meaning (not "bending", not anything). snapbend's bend detection is just one interpretation of these candidates. A consumer (snapdraw, the interpreter) that wants a different interpretation (a raised-feature edge in a plan view is not a bend line) calls this to get the same candidate set without re-deriving the criterion, then sets `edge.role` on the returned `Edge`s (references into `doc.edges` — mutation is reflected there) **before** `heal()`. Runs on `doc.edges` as-is, before `heal()`'s own merge/gap-closing preprocessing — meant to decide roles pre-`heal()`, not to predict its exact excluded set to the edge case. |

## Adapters — `topo_dxf.<name>`, `topo_pdf.<name>`

`import topo_dxf` needs `ezdxf` (`pip install g-topo[dxf]`); without it the
import error names the extra. Layer names and colours are the caller's
(`layers=`, `role_styles=`); the rest is the adapter's default.

| name | signature (defaults trimmed) | does |
|---|---|---|
| `topo_dxf.load_dxf` | `(path, upgrade=False, explode_inserts=True, flatten_z_flag=True, verbose=False, tolerance=0.05, role_rules=(), ignore_layers=None, skip_layers=SKIP_LAYERS) -> Document` | reads DXF/DWG via ezdxf (once), audits, upgrades legacy, explodes INSERTs, translates to pure `Edge`/`Annotation`. `role_rules` assign `Edge.role` at load — in order, first match wins, none → `unknown` — and `Annotation.role` from the rules on the name only (D127; the source layer itself is not kept, D128); unknown roles become consumer role slugs, not errors. `ignore_layers`: substring match; `skip_layers`: exact name, any case, default `("Trash", "Annotation")` — the writer's own layers, so a file topo wrote reads back clean; `()` reads everything (D129). DWG needs ODA File Converter (`ODA_PATH` env var). |
| `topo_dxf.document_from_msp` | `(msp, tolerance=0.05, role_rules=(), ignore_layers=None, source_path="", skip_layers=SKIP_LAYERS) -> Document` | same as `load_dxf` but from an already-open ezdxf `modelspace`; no audit/upgrade/sanitize. |
| `topo_dxf.to_dxf` | `(result, source_doc=None, filter_cluster=None, include_texts=True, include_loose=True, text_layer="Annotation", role_styles=None, layers=None, allow_invalid=True, exclude_types=None) -> ezdxf.Drawing` | renders the model to a **new** DXF (R2010), never rereads source. Layers and looks are the caller's (D128): `layers={role: "Name"}` or `{role: fn(element) -> name}` (a function splits one role over several layers — the element is the Contour, `cluster.detected` item, loose curve or Text being written); `role_styles={role: RoleStyle}`, applied on the layer. Unnamed roles keep the adapter's default layer: `OuterContour`/`InnerContour`/`Trash` for `unknown`/the slug for any other role. Colours are topo's palette (`role_style`), written as the exact ACI index (3/2/1/8); a caller's colour is true color. A text with a role goes on its role's layer, one without on `text_layer`; a text with a `rendered` image is written as that image, else as the string. topo keeps no map between calls. `source_doc` only for header vars (`$INSUNITS`...). Writes everything the `Result` holds (loose curves, texts): for one file per part pass a part from `topo.split`. `filter_cluster(cluster)` skips clusters only; `exclude_types={"TEXT"}` removes those DXF entity types. An invalid result is rendered anyway (loose + texts), like `to_svg`; `allow_invalid=False` → `ValueError` (for a caller feeding a machine, D83). Writes **every collection attached to `cluster.detected`**, none known by name (D70, D90): an item with a `role` goes on its role's layer, geometry from `item.contours` (each with `segments`/`styles`/`polygon` and optionally its own consumer role) or the item itself; with `polygon` → closed entity, without → one entity per primitive. |
| `topo_dxf.split_to_files` | `(doc, output_folder, label="", source_file="", tolerance=None, namer=None, include_texts=True, min_area=50.0, exclude_types=None, text_layer="Annotation", is_structural=None, role_styles=None, layers=None) -> Result` | multi-part flow + disk write: `topo.heal → topo.split → to_dxf + .saveas()` per part; writing options go to `to_dxf`. Filename `f"{cluster.label}.dxf"`. The **only** function that writes to disk. |
| `topo_dxf.write_metadata_to_dxf` / `read_metadata_from_dxf` | `(doc, cluster, extra=None) -> None` / `(doc) -> dict` | writes/reads the `save_json` fields (`topo.build_metadata`) as `TOPO` XDATA on the `OuterContour`-layer entity. |
| `topo_dxf.inspect_dxf` / `inspect_file` | see below | level 1 debug (raw DXF entities); `inspect_file` prints all three levels for a file. |
| `topo_dxf.LAYER_OUTER` / `LAYER_INNER` / `TRASH_LAYER` / `LAYER_ANNOTATION` / `DEFAULT_LAYERS` / `SKIP_LAYERS` | `"OuterContour"` / `"InnerContour"` / `"Trash"` / `"Annotation"` / `{role: layer}` / `("Trash", "Annotation")` | the adapter's default layers (topo has none, D123). |
| `topo_dxf.role_to_dxf_layer` | `(role, element=None, layers: LayerMap=None) -> str` | the layer `to_dxf` writes a role on: the caller's map (a name, or the function called with `element`), else the default, else the role slug (D31). `LayerMap = Mapping[str, str \| Callable[[object], str]]`. |
| `topo_pdf.load_pdf` | `(path, snap_tolerance=0.15) -> list[Edge]` | **experimental** (D10): PDF vector geometry in mm, Y up, nodes snapped. Returns edges, not a `Document`: does not feed `heal()` yet. |

### Debug/inspect (stdout only, 3 levels in order)

```python
topo_dxf.inspect_dxf(path, entities=True, limit=40)      # L1: raw DXF entities, no topo
topo.inspect_document(doc, graph=True, limit=60)         # L2: Document — what the adapter understood
topo.inspect_result(result, coords=False)                # L3: Result — what topo produced
topo_dxf.inspect_file(path, tolerance=0.05, role_rules=(),
                      run_heal=True, entities=True, coords=False)  # orchestrates all three
```

## Domain types

Three public namespaces besides the top level (D120); everything under `topo.core` is internal, no guarantee:

| namespace | holds |
|---|---|
| `topo.primitives` | the native segments `LineSeg`, `ArcSeg`, `CircleSeg`, `BSplineSeg`, `EllipseSeg` (pure math, no role) and `sub_segment(seg, a, b, via)` — the piece of `seg` from `a` to `b` |
| `topo.model` | the model types: `Document`, `Result`, `Cluster`, `Contour`, `Curve`, `ClosedCurve`, `OpenCurve`, `Edge` (a segment + role + style), `EdgeStyle`, `Text`, `DetectedFeature(s)`, and the roles: `ContourRole`, `role_str`, `normalize_role`, `is_structural_role`. The four most used are also `topo.Document/Result/Cluster/Contour`. |
| `topo.steps` | the steps of `heal()` and of the island reading (see Functions) |

```python
import topo

side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))
class Hole(topo.model.ClosedCurve): ...
```

**`Document`** (from `load_dxf`/`document_from_msp`/`load_geometry`): `edges: list[Edge]`, `texts: list[Text]`, `source_meta: dict`, `source_path: str`, `warnings: list[str]`.

**`Result`** (from `heal`, enriched by a consumer/`inject`): `clusters: list[Cluster]`, `is_valid: bool` (**check before handing output to a machine**), `warnings`/`errors: list[str]`, `loose: list[OpenCurve | ClosedCurve]` (every curve that is no cluster's contour — chains that close nothing, open traces, closed curves with a non-structural role; each with `cluster_ref` = index of the cluster whose outer contour contains it entirely, boundary and holes included, else `None`, D137 — move one into `cluster.detected` with `promote`), `texts: list[Text]`, `cluster_count` (property). Every arc of the drawing is in a contour's or a loose curve's `segments` (an open arc, e.g. a thread crest, is in `loose`). `.to_dict()` for JSON.

**`Cluster`**: `outer: Contour`, `inners: list[Contour]`, `label: str`, `custom: dict` (from `data_injector`), `detected: DetectedFeatures|None` (open-by-name overlay, `None` until something writes to it — D44), `.features(name)` → collection or `[]` (whatever name a consumer attached — snapbend writes `"holes"`, `"bending_lines"`, `"engrave_lines"`), `.summary` property (raw `{name}_count` for every `detected` collection, `{}` if `detected is None`), `.overlay_voids` (overlay items with `is_void = True` and a `polygon`: voids a consumer read, subtracted from `.area` — D90), `.area` (outer − overlay voids − odd-depth inners + even-depth inners, D89), `.bbox`. `Contour` also has `.depth`/`.parent` (D34) — position in the containment tree, needed e.g. by `topo.tools.strips`.

A consumer attaches its detection (`topo.DetectedFeatures`):
```python
cluster.detected = cluster.detected or DetectedFeatures()
cluster.detected.attach("flange_view_hint", [...])
cluster.features("flange_view_hint")   # reads it back
```

**`Contour`**: `role: ContourRole`, `polygon` (shapely), `segments` (native primitives, a head-to-tail ring — checked by `test_heal_invariants`), `.area`, `.bbox`. `Contour.from_segments(segments, role, depth=0, parent=None, tolerance=0.01)` builds one from a caller's ring, checks it closes and computes the polygon; `ValueError` otherwise (D118).

**`Text`** (one type, D138 — whether it is a note, a dimension or a callout is the reader's call, even when the format says so): `position (x,y)`, `text` (the string as drawn; a DXF dimension's `<>` already resolved: `"Ø6.5"`, `"M5"`, `"12 H7"`; formatting codes stripped, Ø/°/± decoded at load), `height`, `rotation`, `width_factor`, `role`, `cluster_ref` (set by `anchor_texts`), `source_kind` (`"TEXT"`/`"MTEXT"`/`"DIMENSION"`/`"LEADER"`/`"MULTILEADER"` in a DXF), `pointer` (polyline from the tip, `[0]` = tip) and `target` (set by `anchor_texts`, resolve with `resolve_target`), `measured_points` (points on the geometry the number was measured between: two ends; two opposite points on a circle — that is how a diameter reads; one point on an arc), `measure` (the number the source says it measured, `None` if it says none) and `measure_is_angle` (an angle, not a length — leave it out of a scale), `references` (paths of the elements under `measured_points`, set by `anchor_texts`, D69), `rendered` (the image the source draws around the string; `to_dxf` writes that). `measure` is in drawing units: if the view is drawn at another scale it differs from the number written (e.g. 6.625 measured, `∅5,3` written, on a sheet drawn at 1.25:1). A callout's string is often a separate `Text` with no pointer.


## Roles — open vocabulary

**The engine (`core`/`model`) knows exactly three roles**: `unknown`, `outer`, `inner` — nothing else, by design (MAP.md D47, "roles out of core"). Everything else — `hole`/`countersink`/`threaded_hole`/`bending`/`engrave`/`marking` included — is a consumer's vocabulary (those six: snapbend, D88), used through the public mechanisms `heal(is_structural=...)` and the caller's maps passed to an exporter (`role_styles=`, `layers=`, D128).

**Any role string is legal** — a consumer can assign anything (`"frame"`, `"title_block"`, `"hole"`, `"section"`...); it passes through `normalize_role()` (slugified `[a-z0-9_-]`, ≤64 chars), topo keeps it without raising; the DXF adapter writes it by default to a layer named by the slug (`unknown` → `Trash`) unless the caller's `layers=` says otherwise. Whether `heal()` keeps a labeled edge **inside the topology graph** (structural) or excludes it (decoration) depends entirely on the `is_structural` predicate you pass it:

- No predicate (bare `heal(doc)`): only `outer`/`inner` count as structural. A `role_rules`-tagged `"hole"` edge is excluded from the graph, ends up in `loose`, and `heal()` appends a warning.
- `heal(doc, is_structural=snapbend.flat.is_structural)`: also recognizes `hole`/`countersink`/`threaded_hole` as structural (they're real part contours, not decoration) — `bending`/`engrave`/`marking` and any unknown consumer role still get excluded.

To mark geometry before `heal` excludes it from the graph: set `edge.role = topo.normalize_role("frame")` on `doc.edges` entries.

### Building your own role + palette (external-tool recipe)

A tool built on top of topo (snapdraw, snapbend, or your own)
defines its own roles the same way snapbend does for holes and bends — **no
privileged path exists**, this is the only mechanism. Minimal pattern, one module in your own project:

```python
# your_tool/roles.py
import topo

FLANGE_UP = "flange_up"          # any slug — normalize_role() sanitizes it anyway

def is_structural(role) -> bool:
    """
    Only needed if your role marks REAL part-contour geometry (like a hole) —
    something that must stay inside heal()'s loop-finding graph. Skip this
    entirely if your role is decoration/annotation (like frame/title_block):
    topo's default (no predicate) already excludes anything non-outer/inner,
    which is what you want.
    """
    return topo.is_structural_role(role) or role == FLANGE_UP

# your maps, published like snapbend.flat.ROLE_STYLES / LAYERS — topo keeps none (D128)
ROLE_STYLES = {FLANGE_UP: topo.RoleStyle(color=(255, 165, 0))}
LAYERS = {FLANGE_UP: "FlangeUp"}
```

Then, in your pipeline:

```python
import topo, topo_dxf
import your_tool.roles as roles

doc = topo_dxf.load_dxf("part.dxf", role_rules=topo.name_rules({"FlangeMarks": roles.FLANGE_UP}))
result = topo.heal(doc, is_structural=roles.is_structural)   # only if FLANGE_UP is structural
topo_dxf.to_dxf(result, doc, role_styles=roles.ROLE_STYLES, layers=roles.LAYERS)   # FlangeUp layer, orange
```

That assumes the source already groups flange edges under their own name
(`topo.name_rules({"FlangeMarks": ...})`). When it doesn't — you only know
geometrically that an edge sits where a bend line *would* sit (on a chain
between two branching nodes, not on its shape's outer boundary) and have to decide for
yourself whether it's really a bend or a raised-feature edge — use
`non_contour_candidates(doc)` instead of a name rule:

```python
for edge in topo.non_contour_candidates(doc):
    if your_tool.looks_like_flange(edge):     # your own geometry/cross-view logic
        edge.role = roles.FLANGE_UP

result = topo.heal(doc, is_structural=roles.is_structural)
```

Same candidates `heal()` would have excluded and left as `role="unknown"` in
`loose` anyway — this just lets you label them with your own meaning
before `heal()` runs, instead of after, and instead of snapbend's default
guess (`"bending"`, confidence 0.9).

If your role is purely decorative (never part-contour geometry), skip
`is_structural` entirely and skip passing anything to `heal()` — the default
already keeps it out of the graph and routes it to its own named layer via
`normalize_role`. Your `role_styles`/`layers` maps are what give it a
color/layer name instead of the generic gray "consumer role" fallback. To attach richer
per-feature data (not just a color), use the `cluster.detected` overlay
instead — see `Cluster` above.

## Reading drawings of views: `island()`

`heal()` reads from the inside (who touches whom, which loops close, which is
inside which). On a drawing of views — several views on a sheet, isometric/3D
projections, near-coincident silhouette lines — that graph is ambiguous.
`island()` reads from the outside: pieces that touch → planar network →
outer face → every outer not inside another is an island → interior by
containment (D99). Choose by the drawing:

| drawing | call |
|---|---|
| flat outlines (a cutting file, a development), one or more separate parts, exact geometry to stitch | `heal()` |
| technical drawing with views (plan, side, isometric) on a sheet | `island()` |

What `island()` does **not** know: which island is a view, a part, the frame,
the title block, a magnifier circle over a view, a break line. Those are
roles — the caller's job (D21, D30). There is no distance between views:
two outer contours are two islands however close (D99); `max_gap` (required,
no default, D98) only decides which edges touch. With the frame still in the drawing, the
frame is the only outer and every view becomes its interior.

### Consumer recipe (snapdraw / a drawing reader)

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("sheet.dxf")

# 1. your own semantics: mark what is not part geometry, by role
for edge in doc.edges:
    if my_tool.is_frame_or_title_block(edge) or my_tool.is_magnifier_circle(edge):
        edge.role = topo.normalize_role("frame")     # any non-structural slug

# 2. read the rest by islands — marked edges are left out (loose, with their role)
result = topo.island(doc, max_gap=0.5)
for cluster in result.clusters:                     # one view (or part) each
    cluster.outer.polygon, cluster.inners

# 3. need the details per edge (what was a spur, what stayed outside)?
edges = [e for e in doc.edges if e.role == "unknown"]
for reading in topo.read_islands(edges, tolerance=0.05, max_gap=0.5):
    reading.outer, reading.spurs, reading.outside, reading.non_contour, reading.nested_in
```

Composing your own reading from the bricks (same pieces `island()` uses, no
duplicated criteria): `spatial_islands` → `refit_tessellations` →
`split_at_crossings` → `outer_face`. `island()` never calls `heal()`.

The one parameter is the caller's, never guessed by topo — required, no
default (D98): `max_gap` (edges closer than this touch; drawing gaps closed on
a view). 0.5 mm in the examples above is what the default used to be, not a
recommendation. The layout distance `island_gap` is gone (D99): islands are
decided by outer contours and containment, not by spacing.

## Hard rules (violate these = broken output)

- `heal()` never classifies holes/bends — that is a consumer's reading (snapbend `detect_flat`, D88).
- **Check `result.is_valid`** before using output for anything but looking at it. `topo_dxf.to_dxf`/`to_svg` render an invalid result anyway (default `allow_invalid=True`); pass `allow_invalid=False` to get `ValueError` instead. `split` always raises on invalid (D83).
- `tolerance` default `0.05`; a gap ≥ 4× tolerance is **not** auto-closed (deliberate — raise `tolerance` or fix the source).
- `tolerance` is the widest gap topo may close, never a node snap: every endpoint sits on one grid, `NODE_DECIMALS = 3` (`topo.core.geometry.measure`), whatever the tolerance or the reading (D113). Two ends are one node only if they coincide on that grid.
- `role_rules` is a `topo_dxf.load_dxf`/`document_from_msp` param, **not** a `heal` param.
- `topo.load_dxf`, `topo.to_dxf`, `topo.split_to_files`, `topo.inspect_dxf`/`inspect_file`, `topo.write/read_metadata_*`, `topo.load_pdf` **no longer exist** (D129, clean break): they are `topo_dxf.<name>` / `topo_pdf.load_pdf`. `topo.split` returns `list[Result]`, not drawings.
- `label_map`/`linetype_map`/`color_map` **no longer exist** (D63, clean break). Migration: `label_map=m` → `role_rules=topo.name_rules(m)`; `linetype_map={"DASHED": r}` → `topo.RoleRule(r, dashed=True)` (dash is read from the pattern, not the linetype name); `color_map={"cyan": r}` → `topo.RoleRule(r, color="cyan")`. The old fixed priority (name, then linetype, then colour) is gone: put the rules in the order you want, first match wins. `Result.label_map` and `doc.source_meta["label_map"]` are gone too.
- `topo_dxf.to_dxf` never re-reads the source file — it renders from the model only.
- Splines are re-emitted as native `SPLINE`, open overlay geometry (e.g. a consumer's engraving) as native per-primitive entities — **never** discretized to `LWPOLYLINE` in DXF output. `to_svg`/`to_view_model` **do** discretize everything (visualization, not exact curves).
- Nothing is silently dropped: unclassified geometry → `loose`/`Trash` layer, unmodeled DXF types (`HATCH`,`IMAGE`,`TABLE`,`3DFACE`,`XLINE`...) → warning in `doc.warnings`.
- `island()` and `heal()` are two readings, not two steps: never chain them on the same document. Both return a `Result`; `split()` and every renderer work on either.
- snapbend's `detect_flat()` assumes a **flat part seen from its face** (cutting file, sheet development). **Never run it on `island()` views**: it finds "bends" in isometrics and assembly views and "holes" in logo letters — meaningless by construction. Feature reading on views is snapdraw's: in topo use the geometry — `inners` + `contour_shape` (circle, stadium, rectangle...), `concentric_groups`, `arcs_around` — and say so; calling a circle a hole is the reader's call, not topo's. The name states the precondition (renamed from `detect`, D67).
- `island()` puts closed loops inside an outer in `inners` without saying hole or face — same as `heal()` (D15).

## Experimental — importable, not in `__all__`, no stability guarantee

Not documented in `API.md` until proven by a real caller. Import path shown since they aren't `topo.<name>` re-exports beyond the ones listed.

| name | import | signature | does |
|---|---|---|---|
| `rotate_result` | `topo.rotate_result` | `(result, angle_rad, origin=(0,0)) -> Result` | rigid-rotates an already-healed result; no re-heal (rotation doesn't change topology). |
| `rotate_cluster` | `topo.rotate_cluster` | `(cluster, angle_rad, origin=(0,0)) -> Cluster` | same, one cluster. |
| `rotate_document` | `topo.rotate_document` | `(doc, angle_rad, origin=(0,0)) -> Document` | rotates a raw pre-heal `Document`; nodes back on the node grid. |
| `rotate_to_longest` | `topo.rotate_to_longest` | `(result, include_inners=False, target_angle_deg=0.0, origin=None) -> (Result, float)` | finds the longest structural segment, rotates the result so it lands at `target_angle_deg`; returns result + angle applied. |
| `simplify_points` | `topo.simplify_points` (module: `topo.core.primitives.fitting`) | `(points, tolerance, scale, closed=True, corner_turn_deg=35.0, arcs=True, spline_degree=3) -> list[LineSeg\|ArcSeg\|CircleSeg\|BSplineSeg]` | a sampled curve (traced from a raster, a curve written as points) back to primitives: a head-to-tail chain (open: exact ends; closed: closes), every point within `tolerance` except within `scale` of a corner the sampling had rounded; a line where straight, an arc through its ends where constant-radius, a least-squares spline within `tolerance` elsewhere; a corner where the curve turns ≥ `corner_turn_deg` over `scale`, rebuilt sharp at the crossing of its two sides (D141). |
| `to_text` / `save_text` | `topo.to_text` | `(result, source_name="", decimals=3, spline_data=False) -> str` / `(result, path, ...) -> None` | the model as Markdown for a language model (`<name>.topo.md`): header + legend, `## contours` (`Cn` = cluster n, `Cn.k` = k-th closed contour inside; named shapes on one line, others segment by segment), `## open edges` (unclassified, inside a cluster), `## measures and pointers` (`-> Cn.k`, from `anchor_texts` — run it first), `## texts`, `## detected` (any collection, generically), `## not understood` (unanchored measures and pointers, counted edges, warnings, invalid result). Pure renderer: computes no anchoring. D84. |
| `facing_boundaries` | `topo.tools.strips` | `(cluster) -> list[Facing]` | fact 1 of D134: for every empty region (odd-depth contour), `Facing(region, inside)` — its boundary and the filled regions directly inside; `.boundaries` = both. Only boundaries of one `Facing` can be joined: regions in different empty regions have material between them. |
| `gap` | `topo.tools.strips` (rings: `topo.core.geometry.strips.gap`) | `(a: Contour, b: Contour) -> Gap(distance, on_a, on_b)` | fact 2: minimum distance between two boundaries and the closest pair; exact on lines/arcs/circles. |
| `link` | `topo.tools.strips` | `(facing, a, b, at, width, placed=()) -> Link(a, b, strip: Strip)` | fact 3: a strip of `width` between two boundaries of `facing` (parent–child or sister–sister) at the caller's point `at`: it leaves the nearer boundary perpendicular, toward the other (or its closest point). `ValueError` with the reason when a side misses a boundary, crosses another boundary of `facing` or its own boundaries again, a boundary lies inside it, or it touches a `placed` strip. `Strip`: `a_at`, `b_at`, `a_cuts`, `b_cuts`, `sides` (2 `LineSeg`), `.outline` (D142). |
| `unconnected_regions` | `topo.tools.strips` | `(cluster, links) -> list[Contour]` | fact 4: filled regions (even depth) not joined to `cluster.outer` by any chain of `links`. |
| `open_boundaries` | `topo.tools.strips` | `(links) -> Opened(boundaries: [(Contour, [chain of primitives])], sides: [LineSeg])` | the construction: every boundary touched by a strip opened once on all its cuts, the stretch under each strip removed; pieces keep their type (a cut circle is an arc). Untouched boundaries are absent (they stay whole). Two strips overlapping on a boundary → `ValueError`. Where, how many and which region with which is the caller's policy (D134). |

Also recent but stable/documented already: `EllipseSeg` (5th primitive, `"ellipse"` in `load_geometry`), the `"spline"` entity type in `load_geometry`, `RoleStyle`, `Contour.depth`/`.parent`, `cluster.detected`/`.features()` open overlay.

## Module layout (only if you need to import something not re-exported)

```
topo_dxf/        DXF/DWG adapter (loader, writer, layers, xdata, recipes: split_to_files, inspect)
topo_pdf/        PDF adapter (experimental, frozen)
topo/core/       pure geometry engine (+ geometry_input: load_geometry / load_segments): primitives (+ fitting: simplify_points), topology (+ noding, outer_face),
                  healing (+ islands), heal(), island()
topo/model/      the domain: Document, Result, Cluster, Text, role.py, detected.py (overlay)
topo/tools/      optional Result stages: split, anchor, inject, rotate, strips, non_contour
topo/io/         renderers with no format dependency: svg.py, view_model.py, text.py, exporter.py (json/xml)
topo/rules/      metadata schema, validator
topo/inspect.py  debug levels 2-3
```
Dependency rule: `topo` never imports `ezdxf`/`fitz`/`pymupdf`/`topo_dxf`/`topo_pdf`; an adapter never imports `topo.core`/`tools`/`io`/`rules` nor the other adapter; inside `topo`, `core`/`model` never import `tools`/`io`.
