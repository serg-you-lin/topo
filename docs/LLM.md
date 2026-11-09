# topo — AI reference

Dense, token-minimal reference for an AI writing code against `topo`. No
narrative, no rationale — those live in `API.md` (full reference), `ARCHITECTURE.md`
(why), `MAP.md` (decision history), `INDEX.md` (generated locally by `scripts/gen_index.py`, not in git: inventory of every
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
no process — D88) — then renders that model to DXF, JSON, SVG, or a
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
heal(doc)                                       →  Network    (the repaired drawing, once: nodes, doubles, gaps up to max_gap)
network.faces()                                 →  Result     (topology only: closed contours, outer/inner tree — NO hole/bend classification)
network.outlines()                              →  Result     (for drawings of VIEWS: one cluster per outer contour not inside another, outer = outer face of its group)
(a consumer's reading, e.g. snapbend.flat.detect_flat)  →  writes cluster.overlay (the open overlay)
split(result)                                   →  list[Result], one per part (no format)
topo_dxf.to_dxf / to_json / save_json / to_svg / to_view_model  →  render from the model (never re-reads source)
```

### Which output gives you what

Every `to_*` renders the same model; pick by what you need, not by habit. If
you are running Python, the `Result` itself is the richest source: query
it directly and render only what you hand on.

| output | what is in it | exact curves | coordinates | texts | `overlay` | weight | use it when |
|---|---|---|---|---|---|---|---|
| `Result` (in memory) | everything: contours, segments, roles, loose curves, texts with `references`/`target`, `overlay` | yes (native primitives) | full precision | yes | yes | — | you can run code: ask the model, don't parse an export |
| `topo_dxf.to_dxf` | the geometry back as CAD, one layer per role | **yes** (arcs, circles, native `SPLINE`) | full precision | yes (opt.) | written per item (D70) | like a DXF | a machine or a CAD user needs the file |
| `to_json` / `save_json` | the source, the reading, the warnings and per-part facts (area, perimeters, bbox, counts), plus the caller's `extra` fields | — | **none** | no | counts only | tiny | a business system needs numbers about parts |
| `to_view_model` *(outside 1.0 stable, D133)* | every feature as polylines + role + colour | no (discretized) | full precision | yes | every collection drawn under `features` (D90) | can exceed the DXF on sheets of views | an external renderer draws it |
| `to_svg` *(outside 1.0 stable, D133)* | the view model as an image | no (discretized) | full precision | yes | as the view model | like the view model | a person looks at it |

Writing one file per part is the caller's loop: `for part in topo.split(result): topo_dxf.to_dxf(part, doc).saveas(...)` (`split_to_files` removed, D176).

## How to write a call

`import topo` (plus `import topo_dxf` to read or write DXF), then every name
with its full path: `topo.heal(...)`, `topo_dxf.load_dxf(...)`, `topo.Result`, `topo.geometry.contour_shape(...)`, `topo.experimental.face_loops(...)`.
Never `from topo.experimental import face_loops`: a name read alone in the
middle of a script doesn't say whose it is; `topo.experimental.face_loops`
does. Every example in this file follows it — write your code the same way
(D119).

**The promise (D175, D176).** Every name here is stable except those in
`topo.experimental`, usable but free to change in a minor. From 1.0 a stable
name that changes shape arrives under its new form; the old one stays with a
`FutureWarning` for two minors, then goes. In every signature **data** is
positional and **options are keyword-only** (the `*`): `topo.heal(doc,
tolerance=0.5)`, never `topo.heal(doc, 0.5)`. A function that mutates its
argument returns `None`.

## Golden path

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("part.dxf", tolerance=0.5)
check = topo.validate_document(doc)             # input validation, optional
result = topo.heal(doc, label="P-1024").faces()
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
| `RoleRule` | `(role, *, name=None, name_contains=None, dashed=None, dash=None, color=None)` | a rule: all given conditions true → `role`. `name`/`name_contains` = source group name (the DXF layer, case-insensitive); `dashed` = linetype pattern has a gap (`EdgeStyle.is_dashed`), not the linetype name (chains included); `dash` = `"continuous"`/`"uniform"`/`"chain"` (`EdgeStyle.dash_kind`: chain = marks of different lengths alternate, e.g. long dash + dot; uniform = one mark repeated), unknown value → `ValueError`; `color` = effective RGB: `(r, g, b)`, `"#rrggbb"` or a base name (`cyan`, ...); a DXF ACI index is read as its canonical RGB (7 is white), an int is an error (D126). No condition, or unknown colour name → `ValueError`. topo ships no vocabulary: the caller writes the rules (D63). |
| `name_rules` | `(mapping: dict[str, str]) -> list[RoleRule]` | `{name: role}` → one `RoleRule(role, name=...)` per entry. |
| `load_geometry` | `(entities: list[dict], *, tolerance=0.05, source_path="") -> Document` | builds a `Document` from pure geometry, no file. Entity `type`: `line`(start,end) / `arc`(center,radius,start_angle,end_angle deg,ccw) / `circle`(center,radius) / `polygon`(points; always closed, D96) / `spline`(control_points,knots,degree,weights?) — `BSplineSeg` carries geometry only, `closed`/`periodic` are derived (D135) / `ellipse`(center,major_axis vector,ratio?,start_param?,end_param?,ccw?). Optional `role` per entity, same open vocabulary as `RoleRule.role`. |
| `load_segments` | `(segments, *, tolerance=0.05, role="unknown", source_path="") -> Document` | a `Document` from topo segments (or lists of them, e.g. the `topo.geometry` builders); every edge gets `role`. The way to draw with topo in hand: `topo.load_segments(fg.rectangle(200, 100) + fg.circle(5))` (D96). |
| `validate_document` | `(doc: Document) -> Result` | input check, no mutation: what the adapter said about the source, error `empty` (no edges, or all of zero length; a NaN/inf coordinate never reaches a Document, the primitive refuses it, D190), warning `zero-length`. Facts about the input only, never a guess about `heal()` (D233). |
| `validate_result` | `(result: Result) -> None` | output validation, **mutates** `result`. Called automatically by `Network.faces()` — call manually only if you build a `Result` another way. |
| `heal` | `(doc, *, tolerance=None, max_gap=None, is_structural=None, source_file="", label="") -> Network` | the one repair behind every reading (D202): non-structural roles set aside, nodes decided, doubles merged, tessellations refitted, gaps closed up to `max_gap` (default `tolerance`; never below it), a ring within 0.02 of a circle all the way round made that `CircleSeg` (D236), degenerate pieces dropped. `tolerance=None` → `doc.source_meta["tolerance"]`. `source_file` empty → `doc.source_path`. `is_structural(role)->bool` decides which already-labeled edges stay in the network — alone topo knows only outer/inner/unknown; without it a labeled `"hole"` is set aside (goes to `loose`, warned). A consumer passes its own (snapbend: `snapbend.flat.is_structural`). Read the network with `.faces()` or `.outlines()`. |
| `Network` | `.edges`, `.set_aside`, `.crossings`, `.free_ends`, `.tolerance`, `.max_gap`, `.source_file`, `.label`, `.warnings`, `.notes`, `.errors`, `.is_valid`; `.faces() -> Result`, `.outlines() -> Result` | the repaired drawing, built only by `heal()` (D204). Both readings copy `source_file` and `label` onto every `Result`/`Cluster`, and put in `loose` every curve of the network that is no contour, repaired (D203). An empty document gives `is_valid=False` and both readings return its errors. |
| `Network.faces` | `() -> Result` | read from the inside: non-contour edges excluded (candidates for "something else" — `non_contour_candidates()` exposes the same criterion), loop search, outer/inner containment tree. Does **not** classify holes (D15). No closed outer → `is_valid=False`. Calls `validate_result`. |
| `Network.outlines` | `() -> Result` | read from the outside (see "Reading drawings of views" below): edges that touch within `max_gap` are a group; crossings cut; one `Cluster` per outer face of a group not inside another — `outer` only, **no inners** (D161). Everything else goes to `loose` with `cluster_ref` = index of the cluster it touches or that contains it, `None` outside every cluster (D99, D137); a group nested in another goes to `loose` whole. Outer segments come back recomposed where the cut split them (a hole crossed by its axes is one `CircleSeg`, D65). No closed outer → `is_valid=False`. |
| `experimental.read_outlines` | `(edges, tolerance, max_gap) -> list[OutlineReading]` | `outlines()` before it becomes a `Result`, on loose edges (same repair as `heal()`): per group (edges that touch) what was decided, edge by edge; `nested_in` also for a group with no outer whose edges all lie inside another. `OutlineReading`: `edges`, `outer: OuterFace\|None`, `spurs`, `outside`, `non_contour`, `unclassified`, `nested_in: int\|None`. |
| `experimental.read_outline` | `(edges, tolerance, max_gap) -> OutlineReading` | one group: the same repair as `heal()`, `split_at_crossings`, `outer_face`, the rest classified. |
| `experimental.touching_groups` | `(edges, gap_tolerance) -> list[TouchingGroup]` | the groups of edges that touch: union-find on edge pairs within true segment distance `gap_tolerance` (STRtree), chained. No notion of closure or inside. `TouchingGroup`: `edges`, `bbox`, `.width`, `.height`. |
| `experimental.split_at_crossings` | `(edges, tolerance, cut_crossings=True) -> NodedEdges` | planar network (D180): every contact decided once per pair of edges, on the true curves — a crossing, an endpoint within `GRAPH_EPSILON` (0.01 mm) of the other curve (T or two ends), two curves passing within `GRAPH_EPSILON` without crossing — and one shared node tuple for every edge it touches (union-find; never both ends of one edge). Several meetings of the same pair within `tolerance` along either edge are one contact (D101: the two roots of a near-tangent line/arc). Every type is cut, splines/ellipses included (`sub_segment`; a periodic spline stays whole). `NodedEdges.pieces`, `.parent_of(piece) -> Edge`, `.crossings` (interior crossings, D132). |
| `experimental.outer_face` | `(edges, epsilon=0.0) -> OuterFace\|None` | outer contour of a planar network: walk of its outer face starting from the leftmost geometric point, per connected component, largest area wins. `OuterFace`: `segments`, `styles`, `loop`, `.edges`, `spurs` (polygon: `topo.to_shapely(face)`) (walked there and back — axes, marks). |
| `experimental.refit_tessellations` | `(edges, max_segment=0.1, min_run=10, tolerance=0.02) -> list[Edge]` | a chain of ≥`min_run` short `LineSeg`s (a curve written as points) is refitted by `simplify_points` (lines/arcs/splines within `tolerance`, corners as a turn over `max_segment`, D141); chain ends keep their original nodes. |
| heal steps, all in `topo.experimental` (D117, D176) — the same foundation for every reading (D187, D189) | `prepare(edges, is_structural=None) -> Prepared` (non-structural set aside, nodes decided once within `GRAPH_EPSILON`), `normalize(edges, gap, *, keep_junctions) -> Normalized` (refit, merges, weld, near-full arcs, gaps — `gap` already through `reach`), `merge_collinear_overlaps`, `merge_cocircular_overlaps`, `weld_degenerate_linesegs`, `refit_tessellations`, `split_labeled`, `close_near_full_arcs(edges, tolerance, max_missing_angle=NEAR_FULL_ARC_MISSING) -> (edges, n)` (free arcs on one circle join across each hole within tolerance and ≤ 2°: all closed is a `CircleSeg`, else one `ArcSeg` open on the rest, D112, D218), `close_free_gaps(edges, tolerance)` (each free end closes on the nearest point of the network: another free end, or where its own curve continued meets an edge; never a perpendicular bridge; a tie closes nothing, D185, D189), `dangling_splines(edges)`, `split_at_crossings(edges, tolerance, cut_crossings=True) -> NodedEdges` (heal passes `cut_crossings=False`, D132), `non_contour_pieces(noded, tolerance) -> set[id]`, `find_non_contour_edges(edges, tolerance) -> set[id]`, `find_joining_edges(edges, candidate_ids)`, `free_ends(edges, epsilon=0.0)`, `face_loops(edges, epsilon=GRAPH_EPSILON) -> [loop]` (bounded faces as simple CCW rings, plus closed pieces), `structural_loops(loops, is_structural=None)`, `loops_to_curves(loops)` (a loop that makes no contour comes back as one `OpenCurve` per edge, D151), `loose_curves(edges)` (D162), `build_hierarchy(features, label="", source_file="", is_structural=None) -> (clusters, loose)` | `heal()` is a recipe composing these, in this order (D62); compose your own. None mutates its input. `NodedEdges.whole(loop)` gives back the file's edge where a loop runs all its pieces. |
| `split` | `(result, *, namer=None, min_area=0.0) -> list[Result]` | one `Result` per kept part, no format (D124, D129): its one cluster plus the loose curves and texts that belong to it — a loose curve goes to its `cluster_ref`'s part (D137), a text to the part that contains it, else the nearest of **all** parts; nothing duplicated or lost; each copied with `cluster_ref` relative to the part (`0` or `None`); promoted curves travel inside `cluster.overlay`; other fields copied. `namer(i, cluster)` sets `cluster.label` (default `f"{label}_P{i+1}"`). Nothing dropped by default (D232); parts under a given `min_area` (drawing units²) dropped with a warning. Works on `faces()` and `outlines()` alike. **Mutates** only `result.warnings` (drop notices; each part's cluster is a copy with its own label, the original is untouched, D176). Raises `ValueError` if `result` is invalid. Write each part with any renderer: `topo_dxf.to_dxf(part, doc)`, `topo.experimental.to_svg(part)`. No `on_part`: your loop is the hook. |
| `anchor_texts` | `(result, *, snap_distance=0.0) -> None` (**mutates** the texts) | assigns `Text.cluster_ref` — which cluster a text belongs to, by containment (+ optional snap distance for texts just outside, D82). Which element a dimension or a pointer lands on is `topo.experimental.anchor_elements` (D228). **Mutates** texts in place, returns `None`. |
| — | — | **Geometry facts live in `topo.geometry`** (package `topo/core/geometry/`, D95): call `topo.geometry.contour_shape(...)` etc. with the full path — never `topo.contour_shape`, never the name imported bare (D119). Helpers not exported in `topo.geometry` (in `measure`, `points`, `lines`, `axis`) still live in the submodules of `topo.core.geometry`: internal, no guarantee until the 1.0 public surface. |
| `geometry.polygon` / `rectangle` / `regular_polygon` / `circle` / `ellipse` / `stadium` | `polygon(points)`, `rectangle(length, width, center=(0,0), angle=0)`, `regular_polygon(sides, radius, center, angle)`, `circle(radius, center)`, `ellipse(length, width, center, angle)` (one full `EllipseSeg`), `stadium(length, width, center, angle)` -> list of segments | build a closed loop as topo segments (stadium with true `ArcSeg`s), feed it to `load_segments`. Arguments are what `contour_shape` reports (angle in degrees), so build and read round-trip. Rhombus, trapezoid, any straight-sided shape = `polygon` (D96). |
| `geometry.contour_shape` | `(item, tolerance=0.01, angle_tolerance=1.0) -> ContourShape \| None` | shape of a closed contour (`Contour`, a `ClosedCurve` in `loose`, anything with `.segments`, or a segment list; `None` if the segments do not close in a ring, D162): `kind` = `ShapeKind` (a `str` enum) `circle` / `ellipse` / `stadium` / `rectangle` / `polygon` / `other` — **closed and stable (D136)**: no new kind in 1.x and a contour never changes kind; rules read primitives as they are (equal-axis ellipse = circle, a spline circle stays `other`; rounded rectangle = `other`). Plus `center`, `length`, `width` (circle: both = diameter; ellipse: the two axes; stadium (two equal semicircles + two parallel lines — geometric name, not "slot"): overall length, 2r), `angle` (deg [0,180) of the long axis, `None` for circle), `sides`, `diameter`. A geometric fact, **not** a feature: `circle` does not mean hole. Same on `faces()` and `outlines()`. Collinear/co-circular runs are recomposed first (D68). |
| `geometry.concentric_groups` | `(items, tolerance=0.1) -> list[ConcentricGroup]` | circular contours of `items` partitioned by center (absolute tolerance, drawing units); every circle in exactly one group, singletons too, and among the groups within `tolerance` it joins the nearest. Groups ordered by center (x, y), equal within float noise; at equal diameter the order given decides the group's reference, so the partition does not depend on the frame (D197). `ConcentricGroup`: `center` (smallest circle's), `items`, `shapes`, `diameters`, smallest radius first. Geometric fact: pairing circles into countersinks/seats is the consumer's (D91). |
| `geometry.arcs_around` | `(center, radius, arcs, tolerance=0.1) -> list[ArcAround]` | `ArcSeg`s concentric to a circle and larger, nearest first. `ArcAround`: `arc`, `sweep` (degrees, in the arc's direction), `radius_ratio`. No angle threshold: "~270°, ratio ≤ 1.6 = thread crest" lives in snapbend/snapdraw (D91). |
| `geometry.splits_contour` | `(contour, start, end, reach=0.0) -> bool` | the chord start-end, extended by `reach` at both ends, cuts the region of `contour` (a `Contour`, anything with a closed ring of `segments`, or the segment list) into 2+ parts: some stretch runs boundary to boundary through the inside; a touch or a stretch along the boundary does not. On the primitives (D166). Geometric fact; "it is a bend" is the consumer's reading (D93). |
| `geometry.bridged_runs` | `(segments, bridges, tolerance=0.1, angle_tolerance=1e-6) -> list[CollinearRun]` | runs of 2+ collinear strokes (`(start, end)` or anything with `start`/`end`) where each gap lies inside one of the `bridges` contours (e.g. a part's voids; boundary included, on the primitives). `CollinearRun`: `start`, `end`, `members` (indices into `segments`, ordered along the line). Also in `topo.core.geometry.lines`: `are_collinear`, `group_collinear_lines`, `point_line_distance` (D93). |
| `geometry.dash_line` | `(start, end, head, tail, middle=0.0, n_middle=0) -> list[(Point, Point)]` | the segment cut into dashes: `head` anchored at `start`, `tail` anchored at `end`, `n_middle` dashes of `middle` between them, all gaps equal. Whole segment back if the dashes cover it; zero-length dashes dropped; negatives raise `ValueError` (D115). |
| `geometry.intersections` | `(a, b) -> list[Point]` | where two primitives meet (crossings and touches, ends included). Exact for `LineSeg`/`ArcSeg`/`CircleSeg`; within 1e-4 on splines/ellipses. Overlapping pieces give no point (D118). |
| `geometry.point_on_contour` | `(segments, point, tolerance=0.01, angle_tolerance=1e-3) -> ContourPoint \| None` | where a point falls on a ring: `kind` `vertex` / `smooth` (tangent joint) / `edge`, `segments` (indices), `turn_deg`, `concave` (from the ring's direction, exact tangents) (D118). |
| `geometry.nearest_point` | `(segments, point) -> Point` | the point of a ring (or any primitives) closest to any point, mid-side included; exact on lines/arcs/circles, splines and ellipses within 1e-4. Snap a click with it, then `point_on_contour` says where it fell (D140). |
| `geometry.cut_by` | `(segment, region, keep="outside") -> list` | pieces of `segment` outside/inside a closed region (any ring of primitives: `circle`, `rectangle`, `contour.segments`); same primitive type; piece along the border raises `ValueError` (D118). |
| `geometry.contour_minus` | `(contour, region) -> list[list]` | rings left of `contour` minus `region`, head-to-tail: outers keep the contour's direction, a hole is opposite; `[]` if covered, `[contour]` if apart; several rings if a piece is cut off — the caller picks. Shared border raises `ValueError`. Feed to `Contour.from_segments` (D118). |
| `geometry.contour_union` | `(contour, other) -> list[list]` | rings of the union of two rings, largest first: outers keep `contour`'s direction, a hole closed between them is opposite; two rings if apart or touching in one point. A shared border is handled: side by side it disappears, overlapping it stays once; it must coincide piece by piece (same line, circle, or curve between the same ends), else `ValueError`. Where the border goes on along one line or circle the pieces become one (D171). |
| `geometry.covered_rectangles` | `(items, *, min_side, eps=0.5, cluster_tolerance=1.5, coverage=0.85) -> list[CoveredRectangle]` | axis-aligned rectangles whose 4 sides are covered ≥ `coverage` by straight items (anything with `start`/`end`), built on items ≥ `min_side`. No polygonize: tick marks on a border don't break it, a double border gives two. `CoveredRectangle`: `bbox`, `items` (on its sides), `segments` (four `LineSeg`), `area`, `long_side`, `short_side`, `ratio`. "Frame"/"title block" is snapdraw's reading (D94). |
| `geometry.spanning_lines` | `(bounds, items, coverage=0.85, eps=0.5, cluster_tolerance=1.5) -> (ys, xs)` | lines strictly inside `bounds` crossing ≥ `coverage` of its width (horizontal) / height (vertical). |
| `geometry.sides_on_border` | `(bounds, border, tolerance) -> list[str]` | sides of `bounds` (`left`/`bottom`/`right`/`top`) lying on the same side of `border` within `tolerance`. |
| `geometry.axis_aligned_share` | `(segments, angle_tolerance) -> float\|None` | share of `LineSeg` length within `angle_tolerance` degrees of horizontal/vertical; `None` with no `LineSeg`. Also in `topo.core.geometry.axis`: `merge_intervals`, `interval_coverage`, `cluster_values`, `axis_lines`, `items_inside`. |
| `to_shapely` | `(item, *, tolerance=None) -> Polygon \| MultiPolygon \| LineString` | the explicit conversion to shapely for overlay, buffer, WKT — the model exposes no shapely type (D166). Closed curve → `Polygon`; `OpenCurve` → `LineString`; `Cluster` → its material by the even-odd rule of `area` (D89: outer minus depth-1 holes, plus depth-2 islands minus their holes, …, minus overlay voids), a `MultiPolygon` when islands sit in holes. `tolerance=None` = the reading's own polygon; a number rebuilds it from `segments`. `ValueError` if no valid polygon, `TypeError` if no geometry. shapely is topo's dependency but not its contract: a consumer calling shapely itself declares it (D168). |
| `to_json` / `save_json` | `(result, *, indent=2, extra: Callable[[Cluster], dict]=None) -> str` / `(result, path, *, ...) -> None` | `result.to_dict()` as JSON, geometry only (D230, D231): top level `source_file`, `source_format` (`dxf`/`dwg`/`pdf`/`geometry`, the adapter's), `reading` (`faces`/`outlines`), `tolerance`, `max_gap`, `is_valid`, `warnings`, `errors`, `loose_count`, `text_count`, `clusters`; each cluster `label`, `area`, `outer_perimeter`, `inner_perimeter`, `inner_count`, `bbox`, `overlay` (items per collection). Drawing units, exact on the primitives, no coordinates, nothing of a process. `extra(cluster) -> dict` adds the caller's fields (material, part code) to each cluster; a key topo already writes → `ValueError`. |
| `experimental.to_view_model` *(outside 1.0 stable, D133)* | `(result, tolerance=0.05, include_loose=True, include_texts=True, role_styles=None) -> dict` | render-oriented JSON: every feature's coordinates + role + hex color (topo's palette with `role_styles` on top), **discretized to polylines**; the overlay under `cluster["features"][name]`, one entry per contour plus the scalar fields of the item's `to_dict()` (D90). Feeds `to_svg`; usable by an external renderer. |
| `experimental.to_svg` / `save_svg` *(outside 1.0 stable, D133)* | `(result, tolerance=0.05, include_loose=True, include_texts=True, padding=0.03, background="#1e1e1e", true_circles=True, stroke_width=None, size=None, units=None, allow_invalid=True, role_styles=None) -> str / None(writes path)` | SVG render, one `<g data-cluster>` per part, Y flipped. `units="mm"` = true scale (1 unit = 1 mm), e.g. for a machine that imports SVG. Geometry still discretized — use `to_dxf` when exact curves matter. Invalid result rendered anyway; `allow_invalid=False` → `ValueError` (D83). |
| `inspect_document` / `inspect_result` | see below | debug print of levels 2–3, stdout only; level 1 (the raw file) is `topo_dxf.inspect_dxf`. |
| `normalize_role` / `is_structural_role` | `(value) -> str` / `(role) -> bool` | role-vocabulary primitives (see below). `is_structural_role` is the engine's own minimal predicate (outer/inner only) — a consumer passes its own extended one to `heal(is_structural=...)`. |
| `RoleStyle` | `dataclass(color: tuple[int,int,int]|None, linetype: str|None, dash: tuple[float,...]|None, lineweight: float|None)` (`topo.RoleStyle`, `topo.model.RoleStyle`) | how the caller wants a role drawn, no format (D37, D128): passed as `role_styles={role: RoleStyle(...)}` to `to_dxf`/`to_svg`/`to_view_model`. Always on top of topo's palette: `None` fields keep the palette's. `dash` uses `EdgeStyle.dash` signs; in DXF it is registered as `linetype` or `<ROLE>_DASH`. A `linetype` with no `dash`, neither in the output document nor in ezdxf's standard table → `ValueError` (D85). Where a role goes is not here: `to_dxf(layers=...)`. |
| `DEFAULT_ROLE_STYLES` / `CONSUMER_ROLE_STYLE` / `role_style` | `topo.model`; `role_style(role, *, role_styles=None) -> RoleStyle` | topo's palette (D128), one for every format: `outer` green (0,255,0), `inner` yellow (255,255,0), `unknown` red (255,0,0), any other role gray (128,128,128). `role_style` = palette with the non-`None` fields of the caller's map on top. Every exporter calls it and only translates; an adapter author picks no colours. |
| `non_contour_candidates` | `(doc, *, tolerance=None) -> list[Edge]` | same topological criterion `heal()` uses internally to exclude an edge from the contour graph (a chain of edges through degree-2 nodes, ending on two distinct branching nodes, that the boundary of its connected component's outer face does not traverse exactly once — D111, D131) — asserts **no** meaning (not "bending", not anything). snapbend's bend detection is just one interpretation of these candidates. A consumer (snapdraw, the interpreter) that wants a different interpretation (a raised-feature edge in a plan view is not a bend line) calls this to get the same candidate set without re-deriving the criterion, then sets `edge.role` on the returned `Edge`s (references into `doc.edges` — mutation is reflected there) **before** `heal()`. Runs on `doc.edges` as-is, before `heal()`'s own merge/gap-closing preprocessing — meant to decide roles pre-`heal()`, not to predict its exact excluded set to the edge case. |

## Adapters — `topo_dxf.<name>`, `topo_pdf.<name>`

`import topo_dxf` needs `ezdxf` (`pip install g-topo[dxf]`); without it the
import error names the extra. Layer names and colours are the caller's
(`layers=`, `role_styles=`); the rest is the adapter's default.

`load_dxf` speaks in `topo.Diagnostic` too (D233): `doc.warnings` = `dxf-audit`, `dxf-inserts-ignored` (→ `explode_inserts=True`), `dxf-not-modeled`, `dxf-no-curve`, `dxf-layer-skipped`, `dxf-explode-failed`, `dxf-oda-path`; `doc.notes` = `dxf-dwg-converted`, `dxf-upgraded`, `dxf-inserts-exploded`, `dxf-hatches-exploded`, `dxf-duplicates-removed`, `dxf-flattened`. `topo.validate_document(doc)` hands both on.

| name | signature (defaults trimmed) | does |
|---|---|---|
| `topo_dxf.load_dxf` | `(path, *, upgrade=False, explode_inserts=True, flatten_z=True, verbose=False, tolerance=0.05, role_rules=(), skip_layers=()) -> Document` | reads DXF/DWG via ezdxf (once), audits, upgrades legacy, explodes INSERTs, translates to pure `Edge`/`Annotation`. `role_rules` assign `Edge.role` at load — in order, first match wins, none → `unknown` — and `Annotation.role` from the rules on the name only (D127; the source layer itself is not kept, D128); unknown roles become consumer role slugs, not errors. `skip_layers`: exact names, any case, or a function `name -> bool` (substring, regex, anything: D176); default `()`: every layer is read (D243); to read back a file topo wrote without its `loose` and text layers pass `skip_layers=topo_dxf.SKIP_LAYERS`. Skipped curves are counted per layer in a `dxf-layer-skipped` warning, never dropped silently (D242). DWG needs ODA File Converter (`ODA_PATH` env var). |
| `topo_dxf.document_from_msp` | `(msp, *, tolerance=0.05, role_rules=(), source_path="", skip_layers=()) -> Document` | same as `load_dxf` but from an already-open ezdxf `modelspace`; no audit/upgrade/sanitize. |
| `topo_dxf.to_dxf` | `(result, source_doc=None, *, filter_cluster=None, include_texts=True, include_loose=True, text_layer="Annotation", role_styles=None, layers=None, allow_invalid=True, exclude_types=None) -> ezdxf.Drawing` | renders the model to a **new** DXF (R2010), never rereads source. Layers and looks are the caller's (D128): `layers={role: "Name"}` or `{role: fn(element) -> name}` (a function splits one role over several layers — the element is the Contour, `cluster.overlay` item, loose curve or Text being written); `role_styles={role: RoleStyle}`, applied on the layer. Unnamed roles keep the adapter's default layer: `OuterContour`/`InnerContour`/`Trash` for `unknown`/the slug for any other role. Colours are topo's palette (`role_style`), written as the exact ACI index (3/2/1/8); a caller's colour is true color. A text with a role goes on its role's layer, one without on `text_layer`; a text with a `rendered` image is written as that image, else as the string. topo keeps no map between calls. `source_doc` only for header vars (`$INSUNITS`...). Writes everything the `Result` holds (loose curves, texts): for one file per part pass a part from `topo.split`. `filter_cluster(cluster)` skips clusters only; `exclude_types={"TEXT"}` removes those DXF entity types. An invalid result is rendered anyway (loose + texts), like `to_svg`; `allow_invalid=False` → `ValueError` (for a caller feeding a machine, D83). Writes **every collection attached to `cluster.overlay`**, none known by name (D70, D90): an item with a `role` goes on its role's layer, geometry from `item.contours` (each with `segments`/`styles` and optionally its own consumer role) or the item itself; closed entity if the contour is a `ClosedCurve`, its item `is_void`, or its segments close a ring (`topo.model.feature_closed`), else one entity per primitive. |
| `topo_dxf.inspect_dxf` / `inspect_file` | see below | level 1 debug (raw DXF entities); `inspect_file` prints all three levels for a file. |
| `topo_dxf.LAYER_OUTER` / `LAYER_INNER` / `TRASH_LAYER` / `LAYER_ANNOTATION` / `DEFAULT_LAYERS` / `SKIP_LAYERS` | `"OuterContour"` / `"InnerContour"` / `"Trash"` / `"Annotation"` / `{role: layer}` / `("Trash", "Annotation")` | the adapter's default layers (topo has none, D123). |
| `topo_dxf.role_to_dxf_layer` | `(role, element=None, *, layers: LayerMap=None) -> str` | the layer `to_dxf` writes a role on: the caller's map (a name, or the function called with `element`), else the default, else the role slug (D31). `LayerMap = Mapping[str, str \| Callable[[object], str]]`. |
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
| `topo.primitives` | the native segments `LineSeg`, `ArcSeg`, `CircleSeg`, `BSplineSeg`, `EllipseSeg` (pure math, no role; coordinates stored as plain Python floats whatever they are built from, D169) and `sub_segment(seg, a, b, via)` — the piece of `seg` from `a` to `b`. Every segment has `reversed()`, `translated(dx, dy)`, `rotated(angle, origin=(0,0))`, `mirrored(origin=(0,0), angle=0)` (about the line through `origin` at `angle` radians; default the x axis, y → −y) and `scaled(factor, origin=(0,0))` (`factor > 0`, uniform); each returns a new segment of the same type, exact (a mirrored arc reverses its direction, a scaled arc multiplies its radius). Chain them for a rigid motion: `s.mirrored(o, a).rotated(t).translated(dx, dy)`. No non-uniform scale or general affine map: it would turn an arc into an ellipse (D170) |
| `topo.model` | the model types: `Document`, `Result`, `Cluster`, `Contour`, `Curve`, `ClosedCurve`, `OpenCurve`, `Edge` (a segment + role + style), `EdgeStyle`, `Text`, `Overlay`, and the roles: `ContourRole`, `role_str`, `normalize_role`, `is_structural_role`. The four most used are also `topo.Document/Result/Cluster/Contour`. |
| `topo.experimental` | usable, no stability promise (D175 C, D176): the steps of `heal()` and of its readings, the viewer, `rotate_*`, `simplify_points`, the strips of D134/D142 |

```python
import topo

side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))
class Hole(topo.model.ClosedCurve): ...
```

**`Document`** (from `load_dxf`/`document_from_msp`/`load_geometry`): `edges: list[Edge]`, `texts: list[Text]`, `source_meta: dict`, `source_path: str`, `source_format: str` (what the geometry came from, set by the adapter: `dxf`, `dwg`, `pdf`, `geometry`, …; D231), `warnings`/`notes: list[Diagnostic]` (what to look at in the source / what the adapter did, D233).

**`Result`** (from `Network.faces()`/`outlines()`, enriched by a consumer): `clusters: list[Cluster]` (largest exact outer area first; equal areas — congruent copies — by bbox corner `(xmin, ymin)`, same in `faces()` and `outlines()`), `source_file`, `source_format` (the `Document`'s, D231), `reading` (`"faces"`/`"outlines"`), `tolerance`, `max_gap`, `is_valid: bool` (**check before handing output to a machine**), `warnings`/`notes`/`errors: list[Diagnostic]` (D233), `loose: list[OpenCurve | ClosedCurve]` (every curve that is no cluster's contour — chains that close nothing, open traces, closed curves with a non-structural role; each with `cluster_ref` = index of the cluster whose outer contour contains it entirely, boundary and holes included, else `None`, D137 — move one into `cluster.overlay` with `result.promote`), `texts: list[Text]`, `cluster_count` (property). Every arc of the drawing is in a contour's or a loose curve's `segments` (an open arc, e.g. a thread crest, is in `loose`). `.to_dict()` for JSON.

`result.promote(curves, cluster, name, item=None) -> None` (D137, D172, D173 — a method of `Result`, not a top-level function): moves `curves` (one curve or a sequence) out of `result.loose` into **one** item of `cluster.overlay[name]` (`item` = what you made of them; may be omitted only for a single curve, then it is the curve itself), creating `overlay` if needed. Several curves read as one thing (a hole and its seat) are one item. Position doesn't bind: any loose curve to any cluster. Raises `ValueError`, touching nothing, if a curve is not in `result.loose` or given twice, `curves` is empty, `cluster` not in `result.clusters`, several curves come without `item`, or `item` carries no geometry a renderer draws (no contour with `segments` and a role, D244): never in both places, never dropped. topo promotes nothing by itself.

**`Cluster`**: `outer: Contour`, `inners: list[Contour]`, `label: str`, `overlay: Overlay|None` (open-by-name overlay, `None` until something writes to it — D44), `.features(name)` → collection or `[]` (whatever name a consumer attached — snapbend writes `"holes"`, `"bending_lines"`, `"engrave_lines"`), `.summary` property (raw `{name}_count` for every `overlay` collection, `{}` if `overlay is None`), `.overlay_voids` (overlay items with `is_void = True` and the `segments` of a closed ring: voids a consumer read, subtracted from `.area` — D90), `.area` (outer − overlay voids − odd-depth inners + even-depth inners, D89), `.bbox`, `.to_dict()` (the facts `to_json` writes). `Contour` also has `.depth`/`.parent` (D34) — position in the containment tree, needed e.g. by the strips in `topo.experimental`.

A consumer attaches its detection (`topo.Overlay`):
```python
cluster.overlay = cluster.overlay or Overlay()
cluster.overlay.attach("flange_view_hint", [...])
cluster.features("flange_view_hint")   # reads it back
```

**`Contour`**: `role: ContourRole`, `segments` (native primitives, a head-to-tail ring — checked by `test_heal_invariants`), and facts computed on the segments, not the polygon (D165, D166): `.area`, `.centroid` (exact, Green; `ValueError` if no area), `.bbox` (exact: arcs/ellipses at their true extremes), `.contains(point, tolerance=1e-6)` (closed region: boundary within `tolerance` counts as inside), `.points(tolerance=0.01)` (ring as `(x, y)` tuples, first point not repeated). Same on every `ClosedCurve` in `loose`. `Contour.from_segments(segments, role, *, depth=0, parent=None, tolerance=0.01)` builds one from a caller's ring, checks it closes and encloses an area; `ValueError` otherwise (D118). No shapely type on it (D166): `topo.to_shapely(contour)` gives the polygon; the constructor takes no `polygon`.

**`Text`** (one type, D138 — whether it is a note, a dimension or a callout is the reader's call, even when the format says so): `position (x,y)`, `text` (the string as drawn; a DXF dimension's `<>` already resolved: `"Ø6.5"`, `"M5"`, `"12 H7"`; formatting codes stripped, Ø/°/± decoded at load), `height`, `rotation`, `width_factor`, `role`, `cluster_ref` (set by `anchor_texts`), `source_kind` (`"TEXT"`/`"MTEXT"`/`"DIMENSION"`/`"LEADER"`/`"MULTILEADER"` in a DXF), `pointer` (polyline from the tip, `[0]` = tip) and `target` (the element itself, set by `topo.experimental.anchor_elements`; out of `repr`/`==`, D177), `measured_points` (points on the geometry the number was measured between: two ends; two opposite points on a circle — that is how a diameter reads; one point on an arc), `measure` (the number the source says it measured, `None` if it says none) and `measure_is_angle` (an angle, not a length — leave it out of a scale), `references` (the elements under `measured_points`, the objects themselves, set by `topo.experimental.anchor_elements`, D69/D177), `rendered` (the image the source draws around the string; `to_dxf` writes that). `measure` is in drawing units: if the view is drawn at another scale it differs from the number written (e.g. 6.625 measured, `∅5,3` written, on a sheet drawn at 1.25:1). A callout's string is often a separate `Text` with no pointer.


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
result = topo.heal(doc, is_structural=roles.is_structural).faces()   # only if FLANGE_UP is structural
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

result = topo.heal(doc, is_structural=roles.is_structural).faces()
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
per-feature data (not just a color), use the `cluster.overlay` overlay
instead — see `Cluster` above.

## Reading drawings of views: `outlines()`

`faces()` reads from the inside (who touches whom, which loops close, which is
inside which). On a drawing of views — several views on a sheet, isometric/3D
projections, near-coincident silhouette lines — that graph is ambiguous.
`outlines()` reads from the outside: edges that touch → planar network with
crossings cut → outer face → every outer not inside another is a cluster →
the rest is `loose`, owned by containment (D99, D161). Both read the same
repaired network (D202). Choose by the drawing:

| drawing | call |
|---|---|
| flat outlines (a cutting file, a development), one or more separate parts, exact geometry to stitch | `heal(doc).faces()` |
| technical drawing with views (plan, side, isometric) on a sheet | `heal(doc, max_gap=...).outlines()` |

What `outlines()` does **not** know: which outline is a view, a part, the frame,
the title block, a magnifier circle over a view, a break line. Those are
roles — the caller's job (D21, D30). There is no distance between views:
two outer contours are two clusters however close (D99); `max_gap` only decides
which edges touch and which gaps close. With the frame still in the drawing,
the frame is the only outer and every view is in its `loose`.

### Consumer recipe (snapdraw / a drawing reader)

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("sheet.dxf")

# 1. your own semantics: mark what is not part geometry, by role
for edge in doc.edges:
    if my_tool.is_frame_or_title_block(edge) or my_tool.is_magnifier_circle(edge):
        edge.role = topo.normalize_role("frame")     # any non-structural slug

# 2. repair once, read by outlines — marked edges are left out (loose, with their role)
result = topo.heal(doc, max_gap=0.5).outlines()
for cluster in result.clusters:                     # one view (or part) each
    cluster.outer
inside = [c for c in result.loose if c.cluster_ref == 0]   # what lies in the first one

# 3. need the details per edge (what was a spur, what stayed outside)?
edges = [e for e in doc.edges if e.role == "unknown"]
for reading in topo.experimental.read_outlines(edges, tolerance=0.05, max_gap=0.5):
    reading.outer, reading.spurs, reading.outside, reading.non_contour, reading.nested_in
```

Composing your own reading from the bricks (same pieces `outlines()` uses, no
duplicated criteria): `prepare` → `normalize` → `touching_groups` →
`split_at_crossings` → `outer_face`.

`max_gap` is the caller's, never guessed by topo: edges closer than this touch,
and drawing gaps up to it are closed. 0.5 mm in the examples above is an
example, not a recommendation. The layout distance `island_gap` is gone (D99):
clusters are decided by outer contours and containment, not by spacing.

## Hard rules (violate these = broken output)

- `faces()` never classifies holes/bends — that is a consumer's reading (snapbend `detect_flat`, D88).
- **Check `result.is_valid`** before using output for anything but looking at it. `topo_dxf.to_dxf`/`to_svg` render an invalid result anyway (default `allow_invalid=True`); pass `allow_invalid=False` to get `ValueError` instead. `split` always raises on invalid (D83).
- `tolerance` default `0.05` (from the loader); a gap wider than `max_gap` (default `tolerance`) is **not** closed (deliberate — pass a larger `max_gap` or fix the source). Two numbers, not one: with one number at 0.5 a contour stayed open by 0.41 mm (D202).
- `tolerance` decides nodes (two cuts of an edge closer than it are one node, D101), never a node snap: an endpoint is its true point, no grid (D216); `heal()` makes two ends one node by distance.
- `role_rules` is a `topo_dxf.load_dxf`/`document_from_msp` param, **not** a `heal` param.
- `topo.island()` **no longer exists** (D202, clean break): `topo.island(doc, max_gap=g)` → `topo.heal(doc, max_gap=g).outlines()`; `topo.heal(doc)` now returns a `Network`, the old `Result` is `topo.heal(doc).faces()`. `experimental.read_island(s)`/`IslandReading` → `read_outline(s)`/`OutlineReading`.
- `topo.load_dxf`, `topo.to_dxf`, `topo.inspect_dxf`/`inspect_file`, `topo.write/read_metadata_*`, `topo.load_pdf` **no longer exist** (D129, clean break): they are `topo_dxf.<name>` / `topo_pdf.load_pdf`. `topo.split` returns `list[Result]`, not drawings.
- `label_map`/`linetype_map`/`color_map` **no longer exist** (D63, clean break). Migration: `label_map=m` → `role_rules=topo.name_rules(m)`; `linetype_map={"DASHED": r}` → `topo.RoleRule(r, dashed=True)` (dash is read from the pattern, not the linetype name); `color_map={"cyan": r}` → `topo.RoleRule(r, color="cyan")`. The old fixed priority (name, then linetype, then colour) is gone: put the rules in the order you want, first match wins. `Result.label_map` and `doc.source_meta["label_map"]` are gone too.
- `topo_dxf.to_dxf` never re-reads the source file — it renders from the model only.
- Splines are re-emitted as native `SPLINE`, open overlay geometry (e.g. a consumer's engraving) as native per-primitive entities — **never** discretized to `LWPOLYLINE` in DXF output. `to_svg`/`to_view_model` **do** discretize everything (visualization, not exact curves).
- Nothing is silently dropped: unclassified geometry → `loose`/`Trash` layer, unmodeled DXF types (`HATCH`,`IMAGE`,`TABLE`,`3DFACE`,`XLINE`...) → warning in `doc.warnings`.
- `faces()` and `outlines()` are two readings of one network, not two steps: never feed one's output to the other. Both return a `Result`; `split()` and every renderer work on either.
- snapbend's `detect_flat()` assumes a **flat part seen from its face** (cutting file, sheet development). **Never run it on `outlines()` views**: it finds "bends" in isometrics and assembly views and "holes" in logo letters — meaningless by construction. Feature reading on views is snapdraw's: in topo use the geometry — the closed curves in `loose` + `contour_shape` (circle, stadium, rectangle...), `concentric_groups`, `arcs_around` — and say so; calling a circle a hole is the reader's call, not topo's. The name states the precondition (renamed from `detect`, D67).
- A line drawn twice, the copy shifted by less than `tolerance` (e.g. 0.18 mm at 0.5), is **two lines**: nothing in the geometry makes one a mistake. The tolerance joins their ends, and `faces()` returns the thin ring between them as an inner (D225). If such copies are not meant, remove them before `heal()`.
- **Read the warnings; judge their `help` before applying it** (`help`/`param`/`value` are experimental, D240). Every message of a reading is a `topo.Diagnostic` (D227, D233), a `str` with fields: `level`, `code`, `message`, `points` (every place, nearest first; the text shows three), `at`, `notes`, `help` (the call with the smallest threshold that fixes them all), `param`, `value`. One per kind per call. Three channels: `warnings` = advice about the drawing, `notes` = what topo did by itself (read them when you want to know), `errors` = nothing to read. topo never applies a `help` itself (D226). Warning codes:
  - `near-gap`: free ends whose partner (same rule as the gap closing) is beyond `max_gap` and within twice it → `topo.heal(doc, max_gap=...)`; it closes every gap up to that value.
  - `near-copy`: a line lying over a longer one (both ends project inside it) within `tolerance`, not "one line" for D184 → `doc.edges = topo.experimental.merge_near_copies(doc.edges, distance=...)` before `heal()` keeps the longer (same length: the median).
  - `open-arc`: an arc whose hole is within tolerance but misses more than 2° (D218) and at most 8° (a thread never warns) → `doc.edges, _ = topo.experimental.close_near_full_arcs(doc.edges, tolerance, max_missing_angle=math.radians(...))` before `heal()`. A ~270° thread must stay open: raise the angle only where the drawing means a circle.
  - `set-aside`: edges with a role other than outer/inner/unknown left out of the contours → `topo.heal(doc, is_structural=...)`.
  - `tie`: a free end with two partners at the same distance, left open (D185); no threshold fixes it, the drawing does.
  - `crossing`: contour sides crossing with no shared node; fix the drawing.
  - `self-crossing`: a spline that crosses itself, not cut there: a reading takes the whole ring as one contour (known defect, D241); the points are the crossings.
  - `closed-touch`: the node of a closed curve lies on another closed curve: `outlines()` may keep one and put the other in `loose` (known defect, D241).
  - `self-intersecting` / `inner-outside` (from `validate_result`): an outer polygon that crosses itself, an inner not wholly inside its outer.
  - `zero-length` (from `validate_document`): edges whose two ends are one point; `heal()` drops them.
  - `dropped-part` (from `split` with a `min_area`) → `topo.split(result)` keeps every part; `not-rotated` (from `rotate_*`): texts and `cluster.overlay` stay where they were.
  - notes: `merged-lines`, `merged-arcs`, `welded`, `arc-joined`, `open-spline`, `non-contour`, `no-loop`, `free-end`, `joining-edge`, `gap-closed` (a jump closed with a new segment, D206). Errors: `empty`, `no-closed-outer`, `open-contour`, `no-area`. The list is closed: a new code is a decision.
- `outlines()` puts closed loops inside an outer in `loose` (as `ClosedCurve`, D161, D162) without saying hole or face; `faces()` puts them in `inners`, same silence (D15).

## Experimental — `topo.experimental`, no stability guarantee (D175 C, D176)

Every name below is `topo.experimental.<name>`: usable, may change in a minor; promoted to stable in a minor when a real caller proves it.

| name | import | signature | does |
|---|---|---|---|
| `rotate_result` | `topo.experimental.rotate_result` | `(result, angle_rad, origin=(0,0)) -> Result` | rigid-rotates an already-healed result; no re-heal (rotation doesn't change topology). |
| `rotate_cluster` | `topo.experimental.rotate_cluster` | `(cluster, angle_rad, origin=(0,0)) -> Cluster` | same, one cluster. |
| `rotate_document` | `topo.experimental.rotate_document` | `(doc, angle_rad, origin=(0,0)) -> Document` | rotates a raw pre-heal `Document`; nodes on the true rotated points. |
| `rotate_to_longest` | `topo.experimental.rotate_to_longest` | `(result, include_inners=False, target_angle_deg=0.0, origin=None) -> (Result, float)` | finds the longest structural segment, rotates the result so it lands at `target_angle_deg`; returns result + angle applied. |
| `simplify_points` | `topo.experimental.simplify_points` | `(points, tolerance, scale, closed=True, corner_turn_deg=35.0, arcs=True, spline_degree=3) -> list[LineSeg\|ArcSeg\|CircleSeg\|BSplineSeg]` | a sampled curve (traced from a raster, a curve written as points) back to primitives: a head-to-tail chain (open: exact ends; closed: closes), every point within `tolerance` except within `scale` of a corner the sampling had rounded; a line where straight, an arc through its ends where constant-radius, a least-squares spline within `tolerance` elsewhere; a corner where the curve turns ≥ `corner_turn_deg` over `scale`, rebuilt sharp at the crossing of its two sides (D141). |
| `anchor_elements` | `topo.experimental.anchor_elements` | `(result, *, distance=0.5) -> None` (**mutates** the texts) | sets `Text.target` (via `pointer_target`) on texts with a `pointer` and `Text.references` (via `measured_references`) on texts with `measured_points`; the objects themselves (D177): they stay right if the consumer later reorders `overlay` or promotes a curve, and `split` relinks them to the part's copies. Experimental (D228): candidates are the reading's contours and closed loose pieces, never open curves, so on a view sheet read by `outlines()` most dimensions link nothing; goal (1.x) a link to the network's edges, independent of the reading. What a dimension relates (datum, hole to edge) is the reader's. |
| `pointer_target` | `topo.experimental.pointer_target` | `(result, text, *, distance=0.5) -> object\|None` | the element the tip of `text.pointer` (`pointer[0]`) lands on, **the object itself** (D177): a contour of a cluster (`outer`, `inners`), an item of any `cluster.overlay` collection, or a closed curve in `result.loose` without a non-structural role (D162). Nearest boundary within `distance` (tie → smaller element); else smallest closed non-outer element covering the tip; else `None` (e.g. arrows outside the view). Geometry only, never reads the string (D66). |
| `measured_references` | `topo.experimental.measured_references` | `(result, text, *, distance=0.5) -> list` | elements the `measured_points` of `text` fall on, the objects themselves like `target`: for each point, the element whose boundary passes within `distance` (tie → smaller). No duplicates, in point order: two opposite points on a circle give the circle, two ends one or two elements. Pure geometry — reading `"M5"` as a thread is the reader's job. |
| `facing_boundaries` | `topo.experimental.facing_boundaries` | `(cluster) -> list[Facing]` | fact 1 of D134: for every empty region (odd-depth contour), `Facing(region, inside)` — its boundary and the filled regions directly inside; `.boundaries` = both. Only boundaries of one `Facing` can be joined: regions in different empty regions have material between them. |
| `gap` | `topo.experimental.gap` | `(a: Contour, b: Contour) -> Gap(distance, on_a, on_b)` | fact 2: minimum distance between two boundaries and the closest pair; exact on lines/arcs/circles. |
| `link` | `topo.experimental.link` | `(facing, a, b, at, width, placed=()) -> Link(a, b, strip: Strip)` | fact 3: a strip of `width` between two boundaries of `facing` (parent–child or sister–sister) at the caller's point `at`: it leaves the nearer boundary perpendicular, toward the other (or its closest point). `ValueError` with the reason when a side misses a boundary, crosses another boundary of `facing` or its own boundaries again, a boundary lies inside it, or it touches a `placed` strip. `Strip`: `a_at`, `b_at`, `a_cuts`, `b_cuts`, `sides` (2 `LineSeg`), `.outline` (D142). |
| `unconnected_regions` | `topo.experimental.unconnected_regions` | `(cluster, links) -> list[Contour]` | fact 4: filled regions (even depth) not joined to `cluster.outer` by any chain of `links`. |
| `open_boundaries` | `topo.experimental.open_boundaries` | `(links) -> Opened(boundaries: [(Contour, [chain of primitives])], sides: [LineSeg])` | the construction: every boundary touched by a strip opened once on all its cuts, the stretch under each strip removed; pieces keep their type (a cut circle is an arc). Untouched boundaries are absent (they stay whole). Two strips overlapping on a boundary → `ValueError`. Where, how many and which region with which is the caller's policy (D134). |

Also recent but stable/documented already: `EllipseSeg` (5th primitive, `"ellipse"` in `load_geometry`), the `"spline"` entity type in `load_geometry`, `RoleStyle`, `Contour.depth`/`.parent`, `cluster.overlay`/`.features()` open overlay.

## Module layout (only if you need to import something not re-exported)

```
topo_dxf/        DXF/DWG adapter (loader, writer, layers, xdata, inspect)
topo_pdf/        PDF adapter (experimental, frozen)
topo/core/       pure geometry engine (+ geometry_input: load_geometry / load_segments): primitives (+ fitting: simplify_points), topology (+ noding, outer_face),
                  base/ (the foundation of every reading: prepare, normalize, gaps, hierarchy, D187), readings/ (heal() → Network, faces(), outlines() and their own steps)
topo/model/      the domain: Document, Result, Cluster, Text, role.py, overlay.py (overlay)
topo/tools/      optional Result stages: split, anchor, rotate, strips, non_contour
topo/io/         renderers with no format dependency: svg.py, view_model.py, exporter.py (json)
topo/rules/      validator
topo/inspect.py  debug levels 2-3
```
Dependency rule: `topo` never imports `ezdxf`/`fitz`/`pymupdf`/`topo_dxf`/`topo_pdf`; an adapter never imports `topo.core`/`tools`/`io`/`rules` nor the other adapter; inside `topo`, `core`/`model` never import `tools`/`io`.
