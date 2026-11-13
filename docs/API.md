# topo — API reference

One distribution (`g-topo`), three packages (MAP.md D123, D124, D129):
`topo`, the engine, which knows no file format; `topo_dxf`, the DXF adapter
(`pip install g-topo[dxf]`); `topo_pdf`, the experimental PDF adapter
(`g-topo[pdf]`). Internal modules are not imported directly. This
document covers every name exported in `topo.__all__` (§1–§8),
`topo_dxf.__all__` (§9) and `topo_pdf.__all__` (§10).

Conventions of this document:

- **signature** — real parameters and defaults
- **takes / returns** — the types
- **mutates** — whether it modifies something in place (important: several
  processing stages work by side effect)
- **raises** — the exceptions the caller must expect

The domain types (`Document`, `Result`, `Cluster`, …) are described
at the end.

**How to write a call.** `import topo` (and `import topo_dxf` if you read or
write DXF), then every name with its full path: `topo.heal(...)`,
`topo_dxf.load_dxf(...)`, `topo.Result`,
`topo.geometry.contour_shape(...)`, `topo.experimental.face_loops(...)`. Never
`from topo.experimental import face_loops`: a name read on its own halfway
through a script does not say whose it is, `topo.experimental.face_loops` does.
All the examples in this document are written this way (MAP.md D119).

**The promise** (MAP.md D175, D176). Every name in this document is stable
except those of `topo.experimental`, which are meant to be used but may change in a
minor. From 1.0 on, a stable name that changes shape arrives under the new name, the
old one stays with a `FutureWarning` for two minors and then goes away. In every
signature the **data** are positional and the **options** are passed by name only
(the `*` in the signature): `topo.heal(doc, tolerance=0.5)`, never `topo.heal(doc, 0.5)`.
A function that modifies its argument returns `None`.

---

## Index

1. [Input geometry](#1-input-geometry) — `load_segments`, `load_geometry`, `RoleRule`, `name_rules`, writing an adapter
2. [Validation](#2-validation) — `validate_document`, `validate_result`
3. [Processing](#3-processing) — `heal` → `Network` (`faces()` / `outlines()`) and their building blocks (core), experimental `parity_faces` (a third reading, D250), `split`, `anchor_texts` (tools)
4. [Export](#4-export) — `save_json`, `to_json`, `to_shapely`; experimental `to_view_model`, `to_svg`, `save_svg`
5. [Removed before 1.0](#5-removed-before-10-d230) — metadata, `inject`, `custom`
6. [Inspection / debug](#6-inspection--debug) — `inspect_document`, `inspect_result`
7. [Domain types](#7-domain-types)
8. [The complete flow, in order](#8-the-complete-flow-in-order)
9. [`topo_dxf` — the DXF adapter](#9-topo_dxf--the-dxf-adapter) — `load_dxf`, `document_from_msp`, `to_dxf`, `inspect_dxf` / `inspect_file`, the default layers
10. [`topo_pdf` — the PDF adapter](#10-topo_pdf--the-pdf-adapter) — `load_pdf` (experimental)

---

## 1. Input geometry

topo opens no files: a file enters through an adapter (`topo_dxf.load_dxf`, §9;
`topo_pdf.load_pdf`, §10), the geometry you already hold comes in from here. The
role rules (`RoleRule`, `name_rules`) belong to topo and every adapter
applies them.

### `RoleRule`

```python
topo.RoleRule(role, *, name=None, name_contains=None, dashed=None, dash=None, color=None)
```

One rule: if **all** the given conditions are true, the line takes `role`.
topo provides the mechanism; the content (which names, which styles, which
role) is written by the caller (MAP.md D63).

| field | meaning |
|---|---|
| `role` | assigned role, cleaned by `normalize_role`. Open vocabulary: topo knows only `outer`, `inner`, `unknown`; `hole`, `bending`, `engrave`, … belong to snapbend (MAP.md D88); any other slug (`frame`, `title_block`, …) is preserved, treated as non-structural and written to the output on a layer of its own name (MAP.md D27 / D31). |
| `name` | name of the source group, equal (case ignored). |
| `name_contains` | substring of the group name (case ignored). |
| `dashed` | `True` only dashed lines, `False` only continuous ones. Dashed = the linetype pattern has at least one gap (`EdgeStyle.is_dashed`), not the name of the linetype. Chains count too. |
| `dash` | shape of the stroke (`EdgeStyle.dash_kind`), read from the marks of the pattern: `"continuous"` no gap; `"uniform"` a single mark repeated (all dashes equal, or only dots); `"chain"` different marks alternating (long dash + short dash or dot). Two marks are different if they differ by more than 5% of the pattern length. Unknown value → `ValueError`. |
| `color` | effective colour in RGB: `(r, g, b)`, `"#rrggbb"` or a basic name (`red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `white`, `black`, `gray`/`grey`, `lightgray`/`lightgrey`, `pink`). Every adapter reads the colour of the source as RGB: for a DXF an ACI index becomes its canonical RGB (7 is white) (MAP.md D126). An integer is an error. |

Method `matches(name, style) -> bool`. Conditions left as `None` do not
count.

**Raises** `ValueError` if there is no condition at all (it would match everything), if
the colour name is not recognised or if `dash` is not one of the three shapes.

```python
rules = [
    topo.RoleRule("bending", name="Piega"),         # a chain-dashed bend stays a bend
    topo.RoleRule("construction", dash="chain"),    # axes and construction lines
]
```

### `name_rules`

```python
topo.name_rules(mapping: dict[str, str]) -> list[RoleRule]
```

Shortcut: `{name: role}` → one `RoleRule(role, name=name)` per entry, in the
same order.

```python
rules = topo.name_rules({"Piega": "bending", "MARK": "engrave"})
rules.append(topo.RoleRule("bending", dashed=True))   # after the names
```

### `load_segments`

```python
topo.load_segments(segments, *, tolerance=0.05, role="unknown", source_path="") -> Document
```

A `Document` from topo segments (`LineSeg`, `ArcSeg`, `CircleSeg`, …) or
from lists of segments — the ones the constructors of
`topo.geometry` return. All edges take `role`. It is the way to draw with
topo in hand; `load_geometry` remains for those who do not import topo (D96).

```python
fg = topo.geometry
doc = topo.load_segments(fg.rectangle(200, 100) + fg.rectangle(100, 50))
result = topo.heal(doc).faces()     # one part: outer 200×100, one inner 100×50
```

---

### `load_geometry`

```python
topo.load_geometry(
    entities,
    *, tolerance=0.05,
    source_path="",
) -> Document
```

Builds a `Document` from pure geometry — Python dicts, not a file.
Same return contract as `topo_dxf.load_dxf`, but the source is
the caller: a parametric generator (a cone/cylinder development computed
elsewhere) or a contour reconstructor from points (a vectorised trace from
computer vision). The caller imports no internal topo type.

| parameter | meaning |
|---|---|
| `entities` | list of dicts, one per geometric entity. Supported `type`s: `line` (`start`, `end`), `arc` (`center`, `radius`, `start_angle`/`end_angle` **in degrees**, `ccw`), `circle` (`center`, `radius`), `polygon` (`points` — always closed, D96), `spline` (`control_points`, `knots`, `degree`, plus optional `weights` — same fields as `BSplineSeg`, which carries only the geometry: `closed`/`periodic` are derived, D135), `ellipse` (`center`, `major_axis` as a **vector** from the centre, plus optional `ratio`/`start_param`/`end_param`/`ccw` — same fields as `EllipseSeg`, same parametrisation as the DXF ELLIPSE group; default = full ellipse). `role` is optional on every entity — same vocabulary as `RoleRule.role` (`outer`, `hole`, `bending`, …); a different value is preserved as a consumer slug, not an error. |
| `tolerance` | rounding tolerance of the topological nodes — same meaning as `topo_dxf.load_dxf(tolerance=...)`. |
| `source_path` | free label for `Document.source_path`; it is not a file, it is only for diagnostics. |

```python
doc = topo.load_geometry([
    {"type": "arc",  "center": (0, 0), "radius": 50,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (43.3, -25.0), "end": (34.6, -20.0), "role": "outer"},
    {"type": "arc",  "center": (0, 0), "radius": 40,
     "start_angle": -30, "end_angle": 30, "role": "outer"},
    {"type": "line", "start": (34.6, 20.0), "end": (43.3, 25.0), "role": "outer"},
])
result = topo.heal(doc, label="sviluppo_cono").faces()
topo_dxf.to_dxf(result)
```

```python
# "spline" entity — the fields are those of BSplineSeg, taken 1:1
segments = topo.experimental.simplify_points(points, tolerance=0.01, scale=25.0, arcs=False)
doc = topo.load_geometry([
    {
        "type": "spline",
        "control_points": seg.control_points,
        "knots": seg.knots,
        "degree": seg.degree,
        "role": "outer",
    }
    for seg in segments
])
```

Tried on a real case (`snapbend`, formerly bendly, which uses it to bring the developments it
generates into a `Document` without going through a file — see MAP.md D32; the
`spline` type comes from `smoother`, which passes it the output of `simplify_points()` —
see MAP.md D35). The `ellipse` type (MAP.md D45) exists because `EllipseSeg`
is a topo primitive like the others — it needs no real case of its own,
it follows the same scheme as `spline`/`circle`.

### Writing an adapter

An adapter (DXF, PDF, a format of your own) is a topo consumer like any other: it uses
public names only and delivers a `Document` (MAP.md D125). `topo_dxf` and
`topo_pdf` are written this way, and the index check enforces it:
they do not import `topo.core`/`tools`/`io`/`rules` (D129). What it needs:

| name | what it is for |
|---|---|
| `topo.primitives.LineSeg` … `EllipseSeg` | the geometry read from the source, native (never discretised by the adapter) |
| `topo.model.Edge.of(segment, role, *, style=None) -> Edge` | the `Edge` of a segment: endpoints on the segment's true points (no grid, D216); a closed circle, spline or ellipse has a single node |
| `topo.model.EdgeStyle(*, linetype="", linetype_desc="", dash=None, color=None)` | the effective look of the source entity, with no words of any format (D126): `dash` are signed marks (`> 0` dash, `0` dot, `< 0` gap; `()` continuous, `None` unknown — a dash-array `[3, 1]` is `(3, -1)`), `color` is `(r, g, b)`. The adapter resolves inheritance (a "by layer" style) before handing it over |
| `topo.model.RoleRule`, `topo.model.resolve_role(rules, name, style) -> str` | the role of an entity from the caller's rules: the first that matches, otherwise `unknown` |
| `topo.model.Document`, `topo.model.DEFAULT_NODE_TOLERANCE` | the adapter's result and the default tolerance that `heal()` will close |
| `topo.model.Text`, `RenderedGeometry`, `RenderedText` | the texts read from the source, each with its `role` (D127, D138; the source group does not stay in the model, D128) |

To write out in a format: `topo.primitives.segment_endpoints(segment)` gives the
two endpoints of a segment, `topo.model.feature_role(contour, item_role)` the
role with which a contour of an overlay item is drawn,
`topo.model.role_style(role, *, role_styles=None)` how it is drawn: topo's
palette with the caller's map laid over it (D128). An exporter does not choose colours,
it translates what `role_style` gives it into the encoding of its format.

```python
edges = [topo.model.Edge.of(seg, topo.model.resolve_role(rules, name, style), style=style)
         for seg, name, style in read_my_format(path)]
doc = topo.model.Document(edges=edges, source_path=str(path))
```

---

## 2. Validation

### `validate_document`

```python
topo.validate_document(doc: Document) -> Result
```

Validates the **input** before `heal()`. Modifies nothing. Returns a
`Result` with only `warnings` / `errors` / `is_valid` (`clusters` empty).

- **`is_valid = False`** — the file cannot be processed: no geometry, all
  segments degenerate. A NaN/inf coordinate does not reach the document: the
  primitive rejects it and the loader reports it in `doc.warnings` (D190).
- **warning** — processable but to keep an eye on: zero-length edges
  (`zero-length`, `heal()` drops them). It also includes the loader's
  `doc.warnings`. Open ends and gaps are not checked here: `heal()` reports them.

**Raises** `TypeError` if you do not pass a `Document`.

```python
check = topo.validate_document(doc)
if not check.is_valid:
    raise SystemExit(check.errors)
for w in check.warnings:
    print("warn:", w)
```

### `validate_result`

```python
topo.validate_result(result: Result) -> None
```

Validates the **output** after `Network.faces()`. **Mutates** the `result` passed and returns
`None` (D176): it adds `warnings` / `errors` and may set `is_valid = False`. For each cluster it checks:
outer polygon valid and non-empty, area > 0, every inner contained in the outer.

It is **already called automatically by `Network.faces()`** — you call it by hand only if
you build a `Result` by other means.

---

## 3. Processing

`heal` repairs the drawing once and returns a `Network`; `faces()` and
`outlines()` are its two readings (`topo/core/`), one from the inside and one
from the outside — the caller picks the one that suits the drawing (D202);
`split`, `anchor_texts` are optional stages on a
`Result` (`topo/tools/`, the caller chooses which and in what order). Writing
in a format belongs to an adapter: `topo_dxf.to_dxf` (§9); `to_svg`/`to_view_model`
are in §4, experimental. Holes, bends, engravings are
a process reading, in snapbend (`snapbend.flat`, MAP.md D88).

### `heal`

```python
topo.heal(doc: Document, *, tolerance=None, max_gap=None, is_structural=None,
           source_file="", label="") -> Network
```

The repair, one for every reading (D202): non-structural roles set
aside, nodes decided, duplicates merged, tessellations refitted, gaps closed up to
`max_gap`. It works on `doc.edges`, zero `ezdxf`. It reads nothing yet: the
contours are found by `faces()` and `outlines()`.

| parameter | meaning |
|---|---|
| `tolerance` | two points closer than this are one node. If `None`, taken from `doc.source_meta["tolerance"]` (the one passed to `topo_dxf.load_dxf`). |
| `max_gap` | the widest gap that is closed between free endpoints, and the distance at which `outlines()` puts two edges in the same group. If `None`, `tolerance`; never less than `tolerance`. |
| `is_structural` | `Callable[[str], bool] \| None` — "is this role part-contour topology?", used to decide which already-labelled `Edge`s (by `role_rules`) stay in the network. By itself it knows only `outer`/`inner`/`unknown`; without this parameter a consumer role (`"hole"`, ...) is treated as non-structural and **leaves** the network (heal reports it with a warning). The consumer passes its own (snapbend: `snapbend.flat.is_structural`). |
| `source_file` | source file name, ends up in every `Result`. Empty: `doc.source_path` (D204). |
| `label` | label, ends up in `cluster.label` of both readings (D204). |

`role_rules` is **not a parameter of `heal`** — it is passed to `topo_dxf.load_dxf()`, which
assigns the roles to the `Edge`s.

**Returns** a `Network`. An empty drawing does not raise: `net.errors` is
populated and `net.is_valid` is `False`.

**Raises** `TypeError` if you do not pass a `Document`, or if `tolerance`/`max_gap`
is not a number; `ValueError` if `tolerance` (given, or the loader's) is not a finite
number greater than zero, or `max_gap` is negative or not finite.

```python
net = topo.heal(doc, tolerance=0.5, label="P-1024")
result = net.faces()
```

### `Network`

The repaired network (D204), built only by `heal()` (keyword-only fields).
The readings do not modify it.

| field | type | meaning |
|---|---|---|
| `edges` | `list[Edge]` | the repaired edges, nodes decided |
| `set_aside` | `list[Edge]` | the edges with a non-structural role (D30): each reading puts them in `loose` with their role |
| `crossings` | `list` | the points where two edges cross without a node (D132) |
| `free_ends` | `list[(point, mm)]` | the endpoints that no other edge touches, with the distance from the nearest node |
| `tolerance` | `float` | the node tolerance used |
| `max_gap` | `float` | the widest gap closed (at least `tolerance`) |
| `source_file`, `label` | `str` | copied onto every `Result` and `Cluster` read from here |
| `warnings`, `errors` | `list[str]` | what the repair did; with `errors` no reading finds anything |
| `is_valid` | `bool` | `True` if the repair gave no errors |
| method | returns | what it does |
|---|---|---|
| `faces()` | `Result` | reads from the inside: edges that do not close a contour are left out (`non_contour_candidates()` exposes the same criterion to a consumer, section 8), closed loops, outer / inner containment tree. **Does not classify holes** (D15): `Cluster(outer, inners=[Contour...])`; calling a circle a hole is a process reading (snapbend, D88). No closed outer contour → `is_valid=False`, `errors` populated (`loose` stays full for diagnostics). |
| `outlines()` | `Result` | reads from the outside, see below. |

`faces()` and `outlines()` are two readings of the same network, not two steps:
do not feed the output of one to the other. Both give a `Result`; `split()` and every
renderer work on either.

#### The steps of `heal()` — experimental

They live in `topo.experimental` (D175 C, D176): they are meant to be used, but making them stable
would freeze how the algorithm inside is built. A step that a real recipe
proves solid is promoted to stable in a minor.

`heal()` is a recipe: it composes these steps, in the order below, and writes the
warnings that tell their story. Exposed for those who compose their own (snapdraw: for example
stopping before `build_hierarchy`, until it has decided for itself what a
contour inside another means — D62). The same pieces as `heal()`, no criterion
duplicated.

```python
topo.experimental.prepare(edges, is_structural=None) -> Prepared
topo.experimental.normalize(edges, gap, *, keep_junctions) -> Normalized
topo.experimental.merge_collinear_overlaps(edges, keep_junctions=False) -> list[Edge]
topo.experimental.merge_cocircular_overlaps(edges) -> list[Edge]
topo.experimental.weld_degenerate_linesegs(edges) -> list[Edge]
topo.experimental.refit_tessellations(edges, ...) -> list[Edge]
topo.experimental.split_labeled(edges, is_structural=None) -> tuple[list[Edge], list[Edge]]
topo.experimental.close_near_full_arcs(edges, tolerance, max_missing_angle=NEAR_FULL_ARC_MISSING)
    -> tuple[list[Edge], int]
topo.experimental.close_free_gaps(edges, tolerance) -> list[Edge]
topo.experimental.dangling_splines(edges) -> list[Edge]
topo.experimental.split_at_crossings(edges, tolerance, cut_crossings=True) -> NodedEdges
topo.experimental.non_contour_pieces(noded, tolerance) -> set[int]
topo.experimental.find_non_contour_edges(edges, tolerance) -> set[int]
topo.experimental.find_joining_edges(edges, candidate_ids) -> list[Edge]
topo.experimental.free_ends(edges, epsilon=0.0) -> list[tuple[point, float]]
topo.experimental.face_loops(edges, epsilon=GRAPH_EPSILON) -> list[loop]
topo.experimental.structural_loops(loops, is_structural=None) -> list[loop]
topo.experimental.loops_to_curves(loops) -> list[ClosedCurve | OpenCurve]
topo.experimental.loose_curves(edges) -> list[ClosedCurve | OpenCurve]
topo.experimental.build_hierarchy(features, label="", source_file="", is_structural=None)
    -> tuple[list[Cluster], list]
```

The foundations are the same for every reading (D187, D189): `faces()`, `outlines()` and
a recipe composed by a caller go through the same functions.

| step | takes → returns | what it does |
|---|---|---|
| `prepare` | `list[Edge]` → `Prepared` (`edges`, `labeled`, `welded`) | non-structural roles set aside (`split_labeled`), then the nodes decided once: from the real points, endpoints within `GRAPH_EPSILON` are one node (D180, D187). |
| `normalize` | `list[Edge]`, `gap` → `Normalized` (`edges` and the counts of each step) | tessellations refitted, duplicates merged, degenerate strokes welded, near-full arcs closed, gaps closed: the same cleanups for everyone (D189). `gap` already with the margin (`reach(tolerance)`, D183). `keep_junctions`: two collinear pieces that touch only at a junction are not merged (D110). |
| `merge_collinear_overlaps` | `list[Edge]` → `list[Edge]` | merges lines drawn as overlapping pieces, judging "same line" on the true segments (D50, D184). |
| `merge_cocircular_overlaps` | `list[Edge]` → `list[Edge]` | the same on co-circular arcs (D52, D184). |
| `weld_degenerate_linesegs` | `list[Edge]` → `list[Edge]` | welds `LineSeg`s under 0.05 mm into a single node; a wider group is a piecewise curve and stays (D56, D186). |
| `split_labeled` | `list[Edge]` → `(kept, labelled)` | sets aside the edges with an already decided, non-structural role (D30). Without `is_structural`, only `outer`/`inner` are structural. |
| `close_near_full_arcs` | `list[Edge]` → `(edges, n_closed)` | the `ArcSeg`s with free ends on the same circle are joined across every gap within `tolerance` **and** within `max_missing_angle` (`NEAR_FULL_ARC_MISSING` = 2°): all closed gives a `CircleSeg`, otherwise an `ArcSeg` open on the remaining gaps; `n` = edges rebuilt. `tolerance=math.inf` leaves only the angle (D112, D218). |
| `close_free_gaps` | `list[Edge]` → `list[Edge]` | every free endpoint closes onto the nearest point of the network within `tolerance`: another free endpoint (meeting or segment, each endpoint at most one gap, D112) or the point where its curve, continued, meets another edge — never with a bridge across. An endpoint whose two nearest points tie does not choose (D185, D189). |
| `dangling_splines` | `list[Edge]` → `list[Edge]` | the open `BSplineSeg`s with one unconnected endpoint — diagnostics only. |
| `split_at_crossings` | `list[Edge]` → `NodedEdges` | the planar network: every contact decided once on the true curves (D180). `cut_crossings`: a crossing cuts too — yes for `outlines()` (D101), no for the network of `heal()` (D132, D189: the cut is made by the reading); the crossings are in `crossings` anyway. `NodedEdges.whole(loop)` gives back the original edge where a loop runs along all its pieces. |
| `non_contour_pieces` | `NodedEdges` → `set[id(piece)]` | the pieces that do not close a contour (chords and bridges, D111, D131), on the network: the same judgement for every reading. |
| `find_non_contour_edges` | `list[Edge]` → `set[id(Edge)]` | the same, on whole edges (all their pieces non-contour). `non_contour_candidates(doc)` is the same thing on a document. |
| `find_joining_edges` | `list[Edge]`, `set[id]` → `list[Edge]` | among the candidates, the edges that join two shapes that would otherwise be detached: heal() reports them in a warning (D111). |
| `free_ends` | `list[Edge]`, `epsilon` → `[(point, mm)]` | the endpoints that no other edge touches, with the distance from the nearest node. |
| `face_loops` | `list[Edge]` → `list[loop]` | the loops of the bounded faces of the network, split into simple loops (two lobes touching at a point are two loops), counter-clockwise, plus the pieces closed on their own. The walk is that of the outer face, taken on each side of each edge: no choice depends on the order (D189). |
| `structural_loops` | loop → loop | keeps the loops with no edge of a non-structural role. |
| `loops_to_curves` | loop → `list[ClosedCurve \| OpenCurve]` | one `ClosedCurve` per loop, native geometry; a loop that does not make a contour (zero area, micro-circle) comes back as one `OpenCurve` per edge, never lost (D151). |
| `loose_curves` | `list[Edge]` → `list[ClosedCurve \| OpenCurve]` | the curves of `loose`, one rule for all (D162): a piece that closes on its own is a `ClosedCurve`, the rest one `OpenCurve` per edge; role intact. |
| `build_hierarchy` | feature → `(cluster, loose)` | containment tree: each root a `Cluster`, the descendants `inners` with `depth`/`parent`. |

None **mutates** the input: they return new lists/objects.

```python
# the recipe of heal() up to the closed contours, without hierarchy
x = topo.experimental
prepared = x.prepare(doc.edges, is_structural)
edges = x.normalize(prepared.edges, 0.1 + 1e-6, keep_junctions=True).edges
noded = x.split_at_crossings(edges, 0.1, cut_crossings=False)
non_contour = x.non_contour_pieces(noded, 0.1)
loops = [noded.whole(l) for l in x.face_loops([p for p in noded.pieces if id(p) not in non_contour])]
curves = x.loops_to_curves(x.structural_loops(loops, is_structural))
```

---

### `Network.outlines`

```python
topo.heal(doc, max_gap=g).outlines() -> Result
```

The second reading of a repaired network, beside `faces()`: **by outlines**.
`faces()` rebuilds the topology from the inside (which loops close, what
lies inside what) and finds the part by containment. `outlines()` reads the drawing
from the outside. The repair is already done by `heal()` (gaps up to `max_gap`,
tessellations refitted, duplicates merged); `outlines()`:

1. separates the **groups**: the edges that touch, within `max_gap` (`touching_groups`);
2. for each group makes the network **planar** (`split_at_crossings`, crossings
   cut);
3. the **outline** is the border of the outer face of the network (`outer_face`) —
   edges walked there and back (axes, protruding marks) are not
   outline;
4. every outline that does not lie inside another is a `Cluster` with only the `outer`;
   a group that lies inside another, with its outline or without, is not a
   cluster (D99, D161);
5. everything else — closed or open, inside or outside the outline — goes into
   `loose`, from the repaired network (D203), with the role it had (`unknown` if
   nobody decided one) and with `cluster_ref`, the index of the cluster that
   contains or touches it (`None` outside all of them).

**When to use it instead of `faces()`**: drawings of views — several views on a
sheet, projected isometric/3D views, silhouettes with nearly coincident lines
where the graph of `faces()` is ambiguous. For a drawing of flat silhouettes (one or more
separate parts, exact geometry to be stitched) `faces()` remains.

**No `inner`** (D161): the closed loops inside an outline go into `loose`
as `ClosedCurve`, without saying hole or face. Two outer outlines are two
clusters however close they are: there is no distance between views (D99). With
the frame in the drawing, therefore, the only cluster is the frame: removing it (or giving
a role to frame, title block, magnification circles) is the caller's
job. What a cluster is — view, part — is decided by whoever uses it (D21).

The numbers are those of `heal()` (`net.tolerance`, `net.max_gap`); `max_gap`
is also the distance at which two edges belong to the same group.

**Returns** a `Result` with one `Cluster` per outline, sorted by the area of the
outer contour. Invalid network (`net.errors`) or no closed outline →
`is_valid=False`, `errors` populated.

```python
doc = topo_dxf.load_dxf("tavola.dxf")
result = topo.heal(doc, max_gap=0.5).outlines()
for cluster in result.clusters:          # one view / one part per cluster
    print(cluster.outer.area)
```

#### The building blocks of `outlines()` — experimental

In `topo.experimental`, like the steps of `heal()`. Exposed for those who compose their own recipe (snapdraw: removing frame and title block
by role, then reading the views) — the same pieces, no criterion duplicated.

```python
topo.experimental.read_outlines(edges, tolerance, max_gap) -> list[OutlineReading]
topo.experimental.read_outline(edges, tolerance, max_gap) -> OutlineReading
topo.experimental.touching_groups(edges, gap_tolerance) -> list[TouchingGroup]
topo.experimental.split_at_crossings(edges, tolerance, cut_crossings=True) -> NodedEdges
topo.experimental.outer_face(edges, epsilon=0.0) -> OuterFace | None
topo.experimental.refit_tessellations(edges, max_segment=0.1, min_run=10,
                          tolerance=0.02) -> list[Edge]
```

| function | takes → returns | what it does |
|---|---|---|
| `read_outlines` | `list[Edge]` → `list[OutlineReading]` | the same repair as `heal()` on loose edges, then the touching groups + `read_outline` for each + nesting (`nested_in`, also for a group with no outline lying entirely inside another). It is `outlines()` before it becomes a `Result`. |
| `read_outline` | `list[Edge]` → `OutlineReading` | one group: the same repair as `heal()`, planar network, outer face, the rest classified. |
| `touching_groups` | `list[Edge]` → `list[TouchingGroup]` | the groups of edges that touch: union-find on the pairs at true distance `<= gap_tolerance` (STRtree), chained. No notion of closure or of inside. `TouchingGroup`: `edges`, `bbox`, `.width`, `.height`. |
| `split_at_crossings` | `list[Edge]` → `NodedEdges` | planar network (D180): every contact is decided once per pair of edges, on the true curves — a crossing, an endpoint within `GRAPH_EPSILON` (0.01 mm) of the other curve (T or two endpoints), two curves that pass within `GRAPH_EPSILON` without crossing — and gives a single node tuple for all the edges it touches (union-find; never the two endpoints of the same edge). Several meetings of the same pair within `tolerance` along one of the two edges are a single contact (D101: the two roots of a near-tangency). Every type is cut, splines and ellipses included (a periodic spline stays whole). `NodedEdges.parent_of(piece)` gives the original `Edge`, `.crossings` the interior crossings (D132). |
| `outer_face` | `list[Edge]` (planar network) → `OuterFace \| None` | border of the outer face, per component, the one of largest area; `spurs` = edges walked there and back. |
| `refit_tessellations` | `list[Edge]` → `list[Edge]` | chains of short `LineSeg`s (a curve written as points) refitted by `simplify_points` (lines, arcs, splines within `tolerance`, corners by turn over `max_segment`, D141); chain endpoints on the original nodes. |

None **mutates** the input: they return new lists/objects.

`topo.experimental.OutlineReading` — what was decided on a group, piece by piece:

| field | type | meaning |
|---|---|---|
| `edges` | `list[Edge]` | the edges of the group, as they arrive |
| `outer` | `OuterFace \| None` | outer contour (`segments`, `styles`, `edges`, `spurs`; the polygon with `topo.to_shapely(outer)`) |
| `spurs` | `list[Edge]` | edges walked there and back from the contour |
| `outside` | `list[Edge]` | pieces of the group left outside the contour (detached network) |
| `non_contour` | `list[Edge]` | non-contour candidates, same criterion as `faces()` (D49) |
| `unclassified` | `list[Edge]` | the rest |
| `nested_in` | `int \| None` | index of the outermost group that contains it |

### `topo.experimental.parity_faces` — a third reading, by parity (experimental, D250)

```python
topo.experimental.parity_faces(network) -> Result      # result.reading == "parity"
```

Reads the network so that every remaining line separates an inside face from an outside one. Same `Result` as
`faces()` (clusters, inners by containment, `loose`, diagnostics); crossings are cut; edges with a decided
non-structural role take no part.

- **Guaranteed — every node of even degree.** The faces of a planar network admit an inside/outside labelling with
  every line a contour if and only if every node has even degree, and then the labelling is unique (the colour of a
  face is the parity of the lines crossed to reach it from outside: the even-odd rule). Here the reading is the only one
  that keeps every line, and it does not depend on the frame.
- **Chosen — a node of odd degree.** No reading keeps every line. Free ends and bridges go first (the same face on both
  sides, never a contour). Then the set of lines that leaves every node even, removing first the least length of the
  outer boundary, then the least length overall: a minimum T-join, exact on integer lengths. This minimum is a choice
  ("change the drawing as little as possible"), not a theorem.
- **Declared limit — ties.** Where two such sets have the same length (symmetric drawings: a slot crossed by two axes),
  the coordinates decide which one goes, so a moved or mirrored drawing can read differently: 108 of the 631 drawings
  in `tests/` do. This is why it is not `faces()`.

New diagnostics: `rim-cut` (warning: part of the outer boundary had to go), `face-colour` (warning: two neighbouring
faces read the same side, where the walk round a node does not order tangent branches, D199).

---


## Geometry — `topo.geometry`

**Constructing** (`topo.geometry.<name>`, they return a list of segments,
a closed loop, to be passed to `topo.load_segments`). The arguments are the
measures that `contour_shape` returns, so `contour_shape(rectangle(80, 30,
angle=20))` gives back 80, 30, 20 (D96):

| constructor | shape |
|---|---|
| `polygon(points)` | the polygon through the given points, closed on its own; at least 3 points |
| `rectangle(length, width, *, center=(0, 0), angle=0)` | rectangle, long side at `angle` degrees |
| `regular_polygon(sides, radius, *, center=(0, 0), angle=0)` | regular polygon inscribed in the circle of radius `radius`, first vertex at `angle` |
| `circle(radius, *, center=(0, 0))` | a `CircleSeg` |
| `ellipse(length, width, *, center=(0, 0), angle=0)` | a whole `EllipseSeg`, axes `length` × `width` (`length` >= `width`), long axis at `angle` |
| `stadium(length, width, *, center=(0, 0), angle=0)` | two true semicircles (`ArcSeg`) and two parallel sides; overall `length` × `width` |

Rhombi, trapezoids and every other shape with straight sides are a `polygon`.

**Reading**:

The geometric facts all live in `topo.geometry` (the package
`topo/core/geometry/`, D95) and are called in full,
`topo.geometry.<name>(...)`, without importing the name on its own (D119). Geometric
names: "circle", never "hole". The basic measures (length of a
segment, open traces, strokes on axes, intervals) have been public since
D122; what remains in the submodules of `topo.core.geometry` (node rounding,
point sequences, `circular_geometry`, …) is internal, with no
guarantees. `python scripts/gen_index.py` writes the list with `file:line`
to `docs/INDEX.md` (generated locally, not in git).

### `contour_shape`

```python
topo.geometry.contour_shape(item, *, tolerance=0.01, angle_tolerance=1.0) -> ContourShape | None
```

The shape of a closed contour (`Contour`, an object with `.segments`
or the list of segments): `circle`, `ellipse`, `stadium` (two
equal semicircles and two parallel lines — a geometric name, not "slot"),
`rectangle`, `polygon` (lines only), `other`. A geometric
fact, not a feature: `circle` does not mean hole, that is decided by whoever reads the
drawing or the process. It holds equally on `faces()` and on `outlines()`. Consecutive
segments on the same line or circumference are recomposed first.
`tolerance` is a fraction of the size of the contour.

**Closed and stable list** (D136): `kind` is a `ShapeKind` (`str`, so
`kind == "circle"` works) and in 1.x no other kinds are born and no
contour changes kind. A shape has a name only if centre, length,
width and angle determine it; a filleted rectangle, an arc slot,
a hexagon are `other` or `polygon`. The rules read the primitives as they are:
an ellipse with equal axes is a `circle` (same points, exactly), a
circle made of splines stays `other`.

`ContourShape`: `kind`, `center`, `length` (major; circle: diameter;
ellipse: major axis; stadium: overall), `width` (minor; ellipse: minor
axis; stadium: 2 × radius), `angle` (degrees
[0, 180) of the long axis, `None` for the circle), `sides` (segments after
recomposition), `diameter` (circle only), `.to_dict()`.

**Mutates** nothing.

---

### `concentric_groups`

```python
topo.geometry.concentric_groups(items, *, tolerance=0.1) -> list[ConcentricGroup]
```

The circular contours of `items` (as for `contour_shape`) grouped by
centre: each circle is in exactly one group, even alone; non-circular ones do not
appear. `tolerance` is the maximum distance between centres, in drawing
units; among several groups within `tolerance` a circle joins the nearest.
At equal diameter the reference of the group is the first given; groups sorted
by centre (x, y), ties within noise: the partition does not depend on the
reference (D197). A geometric fact: two concentric circles are not a countersink,
how to pair them is decided by the consumer (D91).

`ConcentricGroup`: `center` (of the smallest circle), `items` and `shapes`
(`ContourShape`) from smallest to largest radius, `diameters`.

**Mutates** nothing.

---

### `arcs_around`

```python
topo.geometry.arcs_around(center, radius, arcs, *, tolerance=0.1) -> list[ArcAround]
```

The `ArcSeg`s of `arcs` concentric to the circle (`center`, `radius`) within
`tolerance` and larger than it, from nearest to farthest. No threshold
on the angle: "~270°, slightly larger" is how a thread crest is drawn,
the consumer applies it (D91).

`ArcAround`: `arc`, `sweep` (degrees, in the direction of the arc), `radius_ratio`
(radius of the arc / `radius`).

**Mutates** nothing.

---

### `splits_contour`

```python
topo.geometry.splits_contour(contour, start, end, *, reach=0.0) -> bool
```

The chord `start`-`end`, extended by `reach` at both ends, divides the region
of the contour into two or more parts: a stretch of it runs from edge to edge passing
through the inside; a touch or a stretch along the edge does not divide. `contour` is a `Contour`,
anything that carries a closed loop of `segments`, or the list of segments.
Computed on the primitives (D166, D167): an arc is the true arc, not chords. A geometric fact: whether that chord is a bend
is decided by the consumer (snapbend extends it by 1 mm, D93).

**Mutates** nothing.

---

### `bridged_runs`

```python
topo.geometry.bridged_runs(segments, bridges, *, tolerance=0.1, angle_tolerance=1e-6) -> list[CollinearRun]
```

Rows of two or more strokes on the same line where the space between one stroke and the
next lies entirely inside one of the contours of `bridges` (for example the voids
of a part; a `Contour`, a loop of `segments` or the list of segments, border
included, computed on the primitives). A stroke is a pair `(start, end)` or
anything that carries `start`/`end` (a `LineSeg`, an `Edge`);
`tolerance` is the maximum distance from the line, `angle_tolerance` the difference
of direction in radians. Strokes left alone do not appear.

`CollinearRun`: `start`, `end` (the outer ends of the row), `members` (indices into
`segments`, in order along the line).

**Mutates** nothing.

---

### `intersections`

```python
topo.geometry.intersections(a, b) -> list[Point]
```

The points where two primitives meet: crossings and touches, endpoints included.
Exact between `LineSeg`, `ArcSeg`, `CircleSeg` (closed form); on `BSplineSeg` and
`EllipseSeg` within `CURVE_TOLERANCE` (1e-4), because there is no closed
form. Two overlapping strokes (same line, same circle) give no points: their
meeting is a stretch (D118).

**Mutates** nothing.

---

### `point_on_contour`, `ContourPoint`

```python
topo.geometry.point_on_contour(segments, point, *, tolerance=0.01, angle_tolerance=1e-3) -> ContourPoint | None
```

Where `point` falls on the ring `segments` (head to tail, like `contour.segments`).
`ContourPoint`: `point`, `kind` (`"vertex"` two sides with an angle, `"smooth"`
two sides that continue into one another — a fillet —, `"edge"` in the middle of a
side), `segments` (indices: incoming and outgoing for a vertex, a single one for a
side), `turn_deg`, `concave` (the interior occupies more than half a turn). The tangents
are exact; concave or convex is told by the direction of the ring. None if `point`
is farther than `tolerance` (D118).

**Mutates** nothing.

---

### `nearest_point`

```python
topo.geometry.nearest_point(segments, point) -> Point
```

The point of the primitives `segments` nearest to `point`, even in the middle of a
side. Exact on lines, arcs and circles; on splines and ellipses within `1e-4`.
`point` may be anywhere (a click, the centre of another figure): to know
where the result falls on the contour, pass it to `point_on_contour` (D140).

**Mutates** nothing. **Raises** `ValueError` if `segments` is empty.

---

### `cut_by`

```python
topo.geometry.cut_by(segment, region, *, keep="outside") -> list
```

The pieces of `segment` outside (`"outside"`) or inside (`"inside"`) the closed
region `region`, in the direction of `segment`, cut at the points of
`intersections`. A region is a ring of any primitives
(`topo.geometry.circle`, `rectangle`, `polygon`, `contour.segments`). The pieces
stay primitives of the same type: a cut arc is an arc (D118).

**Mutates** nothing. **Raises** `ValueError` if a piece runs along the border
of the region (neither inside nor outside).

---

### `contour_minus`

```python
topo.geometry.contour_minus(contour, region) -> list[list]
```

The ring `contour` minus the closed region `region`: the rings of the border that
remains, each head to tail. An outer ring has the direction of `contour`, a hole
(region entirely inside) the opposite one. `[]` if the region covers everything,
`[contour]` if it does not touch it. As many rings as result: a cut that
detaches a piece gives two, and which to keep is decided by the caller. A single touch
(tangency) does not change the shape. To be passed to `Contour.from_segments`
(D118).

**Mutates** nothing. **Raises** `ValueError` if the two borders run
along each other.

---

### `contour_union`

```python
topo.geometry.contour_union(contour, other) -> list[list]
```

The union of the rings `contour` and `other`: the rings of the resulting border,
each head to tail, the largest first. An outer ring has the direction of
`contour`, a hole (enclosed between the two) the opposite one. Two distant contours, or
ones that touch at a single point, remain two rings. A shared border is the
case that matters: where the two sit side by side the common stretch disappears, where they
overlap it remains once. Where the border continues on the same line or
the same circle the pieces become one again (two half discs give a
`CircleSeg`). To be passed to `Contour.from_segments` (D171).

**Mutates** nothing. **Raises** `ValueError` if one border runs along the other
without coinciding piece by piece (same line, same circle, same curve
between the same endpoints).

---

### `dash_line`

```python
topo.geometry.dash_line(start, end, head, tail, *, middle=0.0, n_middle=0) -> list[tuple[Point, Point]]
```

The segment `start`→`end` reduced to strokes: one of length `head` attached to
`start`, one of length `tail` attached to `end`, and `n_middle` strokes of length
`middle` between the two, with all the gaps equal. Each stroke is `(start, end)` in the
direction of the segment; a zero-length stroke does not appear. If the strokes cover all of
the segment, `[(start, end)]` comes back, whole. A geometric fact: whether that segment
is a bend is decided by the consumer (D115).

**Mutates** nothing. **Raises** `ValueError` on negative lengths or `n_middle`.

---

### `covered_rectangles`

```python
topo.geometry.covered_rectangles(items, *, min_side, eps=0.5, cluster_tolerance=1.5, coverage=0.85) -> list[CoveredRectangle]
```

The axis-aligned rectangles whose four sides are covered at least by
`coverage` by straight strokes (`items`: objects with `start`/`end`, for example the
straight `Edge`s of a document), built on the coordinates of the strokes at least
`min_side` long. It does not use `polygonize`: a border full of notches remains a
rectangle, a double-bordered frame gives two. Whether a rectangle is a
frame or a title block is decided by the consumer (snapdraw, D94).

`CoveredRectangle`: `bbox`, `items` (the strokes on its sides), `segments` (the
four sides as `LineSeg`), `area`, `long_side`, `short_side`, `ratio`.

**Mutates** nothing.

---

### `spanning_lines`

```python
topo.geometry.spanning_lines(bounds, items, *, coverage=0.85, eps=0.5, cluster_tolerance=1.5) -> (list[float], list[float])
```

`(ys, xs)`: the lines strictly inside `bounds` that cross it for
at least `coverage` of the width (horizontal) or of the height (vertical).

**Mutates** nothing.

---

### `sides_on_border`

```python
topo.geometry.sides_on_border(bounds, border, *, tolerance) -> list[str]
```

The sides of `bounds` (`"left"`, `"bottom"`, `"right"`, `"top"`) that lie on the
homologous side of `border` within `tolerance`: a box resting on the border of
another. Empty list if it touches none.

**Mutates** nothing.

---

### `axis_aligned_share`

```python
topo.geometry.axis_aligned_share(segments, *, angle_tolerance) -> float | None
```

Fraction of the length of the `LineSeg`s that is horizontal or vertical within
`angle_tolerance` degrees; `None` without `LineSeg`s.

**Mutates** nothing.

---

### `axis_lines`

```python
topo.geometry.axis_lines(items, *, eps=0.5) -> (list[AxisLine], list[AxisLine])
```

`(horizontal, vertical)`: the strokes (`items`, objects with `start`/`end`) that
deviate from the axis by at most `eps`; the others do not appear.
`AxisLine`: `item` (the stroke received), `lo`, `hi` (the interval along its
axis: x for a horizontal one), `at` (the constant coordinate, mean of the two ends).

**Mutates** nothing.

---

### `items_inside`

```python
topo.geometry.items_inside(bounds, items, *, margin=0.0) -> list
```

The strokes with both ends inside `bounds` = `(xmin, ymin, xmax, ymax)`
enlarged by `margin`, in the order given.

**Mutates** nothing.

---

### `merge_intervals`

```python
topo.geometry.merge_intervals(intervals, *, tolerance=0.0) -> list[tuple[float, float]]
```

The intervals `(a, b)` joined where they overlap or are at most `tolerance`
apart, in increasing order.

**Mutates** nothing.

---

### `group_collinear_lines`

```python
topo.geometry.group_collinear_lines(lines, *, tolerance=COLLINEAR_TOLERANCE, angle_tolerance=COLLINEAR_ANGLE_TOLERANCE) -> list[list]
```

The strokes (`start`/`end`) grouped by line: `[[L1, L2], [L3], ...]`. Each
group takes the line of its first stroke, in the order given; it does not look at whether the
strokes touch (for rows across gaps: `bridged_runs`).

**Mutates** nothing.

---

### `segment_length`, `length_inside`, `chord_angle_deg`

```python
topo.geometry.segment_length(segment) -> float
topo.geometry.length_inside(segment, bounds) -> float
topo.geometry.chord_angle_deg(a, b) -> float
```

- `segment_length`: the length of a native primitive. Exact for
  `LineSeg`, `ArcSeg`, `CircleSeg`; for `BSplineSeg` and `EllipseSeg` it is the
  polyline of `discretize()`.
- `length_inside`: how much of `segment` lies inside the rectangle
  `bounds` = `(xmin, ymin, xmax, ymax)`, border included (curves on the
  polyline of `discretize()`).
- `chord_angle_deg`: the angle in degrees, in `[0, 180)`, of the chord from `a` to
  `b`; modulo 180 because a line has no direction.

**Mutate** nothing.

---

### `track_points`, `track_length`

```python
topo.geometry.track_points(segments, *, tolerance=None) -> list[Point]
topo.geometry.track_length(pts) -> float
```

An open trace (bend, engraving, unclosed fragment) is a chain of native
segments. `track_points` gives its vertices (the `discretize()` of each
segment, without repeating the junction point); `track_length` the length
of the polyline. A single straight stroke is `len(track_points(segments)) == 2`
(`track_shape_type`, which said it as a string, is removed: D176).

**Mutate** nothing.

---


### `split`

```python
topo.split(
    result: Result,
    *, namer=None,
    min_area=0.0,                # no discard (D232)
) -> list[Result]
```

**One `Result` per part**, with no format (D124, D129): choosing the parts is
a decision about the model, writing them is an adapter's. Each part is a
`Result` with a single cluster, plus the loose curves and the texts that
belong to it. A `loose` curve goes to the cluster of its `cluster_ref` (D137),
a text to the part that contains it; those that no part contains
go to the part nearest to its outer contour among **all** the parts (even
those discarded by `min_area`). Nothing is duplicated, nothing lost: each
element is copied with `cluster_ref` referring to the part (`0` if its
cluster contains it, `None` otherwise). A promoted curve (`Result.promote`) is
already in `cluster.overlay` and travels with its cluster. The other fields
(source, warnings) are copied. Every writer takes a `Result`, so a
part goes to DXF, SVG or text in the same way.

| parameter | meaning |
|---|---|
| `namer` | `callable(i, cluster) -> str` — gives the `label` of the part's cluster, so the name of a file can still be derived (`f"{cluster.label}.dxf"`). Without it, `f"{label}_P{i+1}"`. |
| `min_area` | by default `0.0`, no discard (D232): a size threshold belongs to a process. With a value, the parts with area below it (mm²) are discarded with a warning in `result.warnings` and in those of every part. |

**Mutates** only `result.warnings` (the discard warnings: even if it discards them all, the discard can be read). The cluster of each part is a copy with its `label`; the original does not change (D176).
**Returns** the parts in the order of the kept clusters.
**Raises `ValueError`** if `result.is_valid` is `False`: a file per part
makes no sense without parts.

```python
for part in topo.split(result, min_area=100.0):
    name = part.clusters[0].label
    topo_dxf.to_dxf(part, doc).saveas(f"{name}.dxf")
    topo.experimental.save_svg(part, f"{name}.svg")
```

---

### `RoleStyle`

```python
@dataclass(frozen=True)
class RoleStyle:                                          # topo.RoleStyle, topo.model.RoleStyle
    color:      tuple[int, int, int] | None = None   # RGB 0-255
    linetype:   str | None = None                     # name of the linetype; alone, a standard type ("DASHED")
    dash:       tuple[float, ...] | None = None       # the stroke, signed marks like EdgeStyle.dash
    lineweight: float | None = None                   # mm
```

How the caller wants a role drawn in the output, in the same vocabulary
as `EdgeStyle` and with no format (D37, D128). It holds for an engine role
(`"outer"`, `"inner"`, `"unknown"`) as for a consumer's — snapbend
(`"hole"`, ...), snapdraw (`"frame"`, `"title_block"`, ...) — none is
privileged. The dictionary `{role: RoleStyle}` is the caller's and is passed to
every exporter: `topo_dxf.to_dxf` and, experimental, `to_svg` and `to_view_model`.
Underneath there is always topo's palette; a `None` field
stays that of the palette. Where a role ends up (a DXF layer) is not
here: it is `topo_dxf.to_dxf(layers=...)`.

**topo's palette** (`topo.model.DEFAULT_ROLE_STYLES`, D128) gives the colour
to the roles that `faces()` and `outlines()` produce, the same for every format: `outer` green
(0, 255, 0), `inner` yellow (255, 255, 0), `unknown` red (255, 0, 0); every
other role is grey (`CONSUMER_ROLE_STYLE`, (128, 128, 128)) until the
caller gives it a colour. `topo.model.role_style(role, role_styles=...)`
resolves a style: the palette, with the non-`None` fields of the caller's map
laid over it. Every exporter calls it and only translates (ACI or true colour in
DXF, hex in SVG): whoever writes an adapter does not choose colours.

```python
topo.model.role_style("outer")                                   # green
topo.model.role_style("hole", role_styles=snapbend.flat.ROLE_STYLES)   # snapbend's magenta
topo.model.role_style("outer", role_styles={"outer": topo.RoleStyle(lineweight=0.3)})   # green, 0.3 mm
```

In DXF: a palette colour becomes its exact ACI index (3, 2, 1, 8);
the caller's `color` → true colour of the layer; `dash` → a linetype registered
under the name `linetype` or, without it, `<ROLE>_DASH`; a `linetype` without `dash` must
be in the document or among the standard ones, otherwise `ValueError` (D85);
`lineweight` → hundredths of a mm.

```python
topo_dxf.to_dxf(result, doc, role_styles={
    "frame":   topo.RoleStyle(color=(0, 0, 0)),          # frame: black
    "unknown": topo.RoleStyle(lineweight=0.05),          # loose curves: hairline
    "bending": topo.RoleStyle(dash=(5.0, -2.0)),         # bends: dash 5, gap 2
})
```

---

### `anchor_texts`

```python
topo.anchor_texts(result: Result, *, snap_distance=0.0) -> None
```

Links every text to the part that contains it: `cluster_ref` = index of the
cluster whose outer contour contains its position (with
`snap_distance` > 0, also the nearest within that distance, D82). Which
element a dimension or an arrow falls on is `topo.experimental.anchor_elements`
(D228).

**Mutates** the texts of `result` and returns `None` (D176).

#### Which element a text falls on — experimental (D228)

They live in `topo.experimental`: the candidates depend on the reading (contours
and closed pieces of `loose`, never an open curve), so on a sheet of views
read with `outlines()` most dimensions do not bind to anything; and
what relates a dimension (datum, hole relative to edge) belongs to whoever
reads the drawing. Goal for 1.x: the link on the edges of the network, the same for
every reading.

```python
topo.experimental.anchor_elements(result: Result, *, distance=0.5) -> None
```

For every text with a `pointer` it sets `target` (`pointer_target`), for every
text with `measured_points` `references` (`measured_references`). **Mutates** the
texts of `result` and returns `None`.

##### `pointer_target`

```python
topo.experimental.pointer_target(result: Result, text: Text, *,
                                 distance=0.5) -> Any | None
```

The element on which the tip (`pointer[0]`) of `text` falls: the object itself —
a contour of `result.clusters` (`outer`, `inners`), an object of a
collection of `cluster.overlay`, or a closed piece of `result.loose` (D162).
Not a position of it in the result (D177): it stays right if afterwards a consumer
reorders the collections or promotes a curve (`Result.promote`).

Rule: the border nearest to the tip, if within `distance` (on a tie, the
smallest element wins); otherwise the smallest closed element, not the outer
contour, that contains the tip (arrow ending inside a hole);
otherwise `None` (arrow outside the part). It does not read the string.

**Mutates** nothing.

##### `measured_references`

```python
topo.experimental.measured_references(result: Result, text: Text, *,
                                      distance=0.5) -> list
```

The elements on which the `measured_points` of `text` fall, the objects themselves
like `target`: for each point the element whose border passes within `distance`
(on a tie the smallest). Without duplicates, in the order of the points: two opposite
points on a circle give the circle, two ends one or two elements. It does not
read the string.

**Mutates** nothing.

---

## 4. Export

### `save_json` / `to_json`

```python
topo.save_json(result: Result, path, *, indent=2,
               extra: Callable[[Cluster], dict] = None) -> None   # writes to file
topo.to_json(result: Result, *, indent=2,
             extra: Callable[[Cluster], dict] = None) -> str      # returns the string
```

`result.to_dict()` as JSON, **geometry only** (D230, D231): where it comes from
(`source_format`, told by the adapter), how it was read (`reading`,
`tolerance`, `max_gap`), whether it is valid, the warnings, and the facts of each part.
No coordinates (the exact curves are carried by `topo_dxf.to_dxf`), nothing of a
process, lengths in mm. `extra(cluster) -> dict`, called once per
cluster, adds the caller's fields (material, part code, what
topo cannot know); a key that topo already writes → `ValueError`, never a
replacement. Structure:

```json
{
  "source_file": "batch.dxf", "source_format": "dxf", "reading": "faces",
  "tolerance": 0.05, "max_gap": 0.05,
  "is_valid": true, "warnings": [], "errors": [],
  "loose_count": 2, "text_count": 4,
  "clusters": [
    {
      "label": "P-1", "area": 12345.67,
      "outer_perimeter": 480.0, "inner_perimeter": 60.0, "inner_count": 1,
      "bbox": {"minx": 0, "miny": 0, "maxx": 200, "maxy": 100},
      "overlay": {"holes": 3}
    }
  ]
}
```

Area, perimeters and bbox are exact, measured on the primitives (D165, D166),
not on the discretised polygon.

### `to_shapely`

```python
topo.to_shapely(item, *, tolerance=None) -> Polygon | MultiPolygon | LineString
```

The explicit conversion to shapely, for those who need overlay, buffer or
WKT: the model exposes no shapely types (D166).

| takes | returns |
|---|---|
| a closed contour (`Contour`, a `ClosedCurve` of `loose`, any object with a ring of `segments`) | `Polygon` |
| an `OpenCurve` | `LineString` |
| a `Cluster` | its material by even-odd, like `area` (D89): the outer with the holes at depth 1, each island at depth 2 with its holes at depth 3, …, minus the voids of the overlay. `Polygon`, or `MultiPolygon` if there are islands inside the holes |

`tolerance=None`: the polygon of the reading, the same as topo's containment
tests; a number rebuilds it from the `segments` within that
tolerance. **Raises** `ValueError` if the segments do not enclose a
valid polygon, `TypeError` if `item` carries no geometry.

shapely is a dependency of topo, but topo's contract does not promise it
(D166, D168): a consumer that calls shapely itself declares it among its
dependencies. Questions about a contour (area, bbox, centroid, `contains`,
a chord that divides it) do not go through here: they are facts of the contour.

> **The viewer** — `to_view_model`, `to_svg`, `save_svg` — is **outside the
> stable 1.0** (MAP.md D133): it lives in `topo.experimental` (D176) and will be
> redone (TODO.md, "Viewer"). The signatures below hold today, with no
> guarantee that they stay.

### `to_view_model`

```python
topo.experimental.to_view_model(
    result: Result,
    tolerance=0.05,
    include_loose=True,
    include_texts=True,
    role_styles=None,
) -> dict
```

`Result` → **rendering-oriented** JSON dictionary: the coordinates of
*every* feature + role + hex colour. It is the geometric counterpart of `to_json` (which gives
metadata only). It is consumed by `to_svg` and would be consumed by an external front-end
(a JS dashboard that draws with SVG/Canvas).

All the geometry is **discretised to polylines** (`points: [[x, y], …]`):
arcs, circles, splines flattened. The overlay sits under `features`, by name
(D90): one entry per contour, with role, colour, points, `closed` and the
scalar fields of the element's `to_dict()` — whatever carries `center` + `diameter` can be
drawn as a true circle. Coordinates in the source's system (Y up).

```python
vm = topo.experimental.to_view_model(result, role_styles=None)   # the caller's {role: RoleStyle}: its colour is read
vm["clusters"][0]["outer"]        # {"role": "outer", "color": "#00ff00", "points": [...], "closed": true}
vm["clusters"][0]["features"]     # {"holes": [{"role": "hole", "points": [...], "diameter": ..., ...}], ...}
vm["palette"]                  # {"outer": "#00ff00", ...} + the roles that role_styles colours
```

It does not mutate `result`, does not raise on an invalid `result` (the dict comes back with
`is_valid=False`).

### `to_svg` / `save_svg`

```python
topo.experimental.to_svg(
    result: Result,
    tolerance=0.05,
    include_loose=True,
    include_texts=True,
    padding=0.03,
    background="#1e1e1e",     # None = transparent
    true_circles=True,        # an entry with center + diameter → <circle>
    stroke_width=None,        # None = auto (bbox diagonal / 400)
    size=None,                # None = no width/height → scales to the container
    units=None,               # "mm" = SVG at real scale, 1 unit = 1 mm
    allow_invalid=True,       # False → ValueError on an invalid result
    role_styles=None,         # {role: RoleStyle}: the colour of each role, as in topo_dxf.to_dxf
) -> str
topo.experimental.save_svg(result, path, **kwargs) -> None
```

SVG renderer of the model (MAP.md D12) — for visualisation (UI/report/
preview) or for a machine that imports SVG. One colour per role: topo's palette, with the caller's `role_styles` laid over it
(D128). The
Y is flipped (model Y-up → SVG Y-down). One part = one `<g data-cluster="…">`.
Built on top of `to_view_model`.

`size=None` (default) does **not** write `width`/`height` on the `<svg>`: the image is
vector and scales to fill the container (or the browser window) — you can zoom it as much as
you like. Pass `size="800"` to fix the width in px.

`units="mm"` produces an SVG **at real scale** (`width="…mm"`, padding and background
at zero) for those who import SVG into software that wants 1 unit = 1 mm.
**Warning:** arcs, circles and splines stay discretised to polylines — when
the exact curve matters (smooth circles, toleranced dimensions) use `topo_dxf.to_dxf`, not the SVG.

An invalid `result` is drawn all the same. `allow_invalid=False` →
`ValueError`, same contract as `topo_dxf.to_dxf` (D83).

```python
topo.experimental.save_svg(result, "pezzo.svg")
```

---

## 5. Removed before 1.0 (D230)

The JSON of topo is geometry only. These no longer exist:

| removed | in its place |
|---|---|
| `build_metadata(cluster)` | `cluster.to_dict()` |
| `save_xml`, `to_json(schema=)`, `topo/rules/metadata_schema.py` | `to_json`; renaming the fields or writing XML is the consumer's job |
| `to_json(extra_metadata=)` | `to_json(extra=)` |
| `inject(result, data_injector=)` | `anchor_texts(result)`, then the texts with `text.cluster_ref == i` passed to the consumer's function |
| `Cluster.custom` | `cluster.overlay` (the overlay, D44), or the consumer's own structures |
| `experimental.to_nester_input` | `to_view_model`, or the primitives of `cluster.outer.segments` |
| `topo_dxf.write_metadata_to_dxf` / `read_metadata_from_dxf` | none: the XDATA gave a wrong DXF |

---

## 6. Inspection / debug

The two levels of topo, in processing order; the first, the raw entities
of a file, belongs to the adapter (`topo_dxf.inspect_dxf`, and `topo_dxf.inspect_file`
which prints all three in a row, §9). All print to stdout.

```python
topo.inspect_document(doc, *, graph=True, limit=60) -> None
```
**Level 2** — a `Document`: `source_meta`, loader warnings,
the `Edge`s (role, primitive, endpoints), the texts, and the
node graph (total nodes, degenerate loops, branching nodes, free ends).
"What the adapter understood."

```python
topo.inspect_result(result, *, coords=False) -> None
```
**Level 3** — a `Result`: validity, warnings/errors, and for each part
outer/inner, the collections of `cluster.overlay` (what a consumer
attached), custom, plus `loose` and texts. "What topo produced."

---

## 7. Domain types

Besides the top level there are three public namespaces (MAP.md D120); what
lies under `topo.core`, `topo.tools`, `topo.io`, `topo.rules` is internal, with no
guarantees. The adapters are separate packages (§9, §10):

- **`topo.primitives`** — the native segments `LineSeg`, `ArcSeg`, `CircleSeg`,
  `BSplineSeg`, `EllipseSeg` (pure math, no role) and
  `sub_segment(seg, a, b, via)`, the stretch of `seg` from `a` to `b` (`via`, an
  interior point, is needed only on a closed curve). Every segment has
  `reversed()`, `translated(dx, dy)`, `rotated(angle, *, origin=(0, 0))`,
  `mirrored(*, origin=(0, 0), angle=0.0)` (about the line through `origin` at `angle`
  radians; by default the x axis, y → −y) and `scaled(factor, *, origin=(0, 0))`
  (`factor > 0`, uniform, otherwise `ValueError`): they return a new segment
  of the same type, exact. A rigid motion is the chain
  `s.mirrored(origin=o, angle=a).rotated(t).translated(dx, dy)`. No non-uniform
  scale nor generic affine: an arc would become an ellipse (D170).
- **`topo.model`** — the types below (`Document`, `Result`, `Cluster`,
  `Contour`), the curves (`Curve`, `ClosedCurve`, `OpenCurve`), `Edge` (a
  segment with role and style), `EdgeStyle`, the texts, the overlay
  and the roles: `ContourRole`, `role_str`, `normalize_role`,
  `is_structural_role`. The four most used are also in `topo.<Name>`.
- **`topo.experimental`** — what is used with no promise of stability (D175 C, D176): the steps of `heal()` and the building blocks of `outlines()` (§3), the viewer (§4), `rotate_*`, `simplify_points`.

```python
import topo

side = topo.primitives.LineSeg(start=(0, 0), end=(100, 0))

class Hole(topo.model.ClosedCurve): ...
```

### `Document`

Produced by `topo_dxf.load_dxf` / `topo_dxf.document_from_msp`. It is the contract between the adapter and the
core: after it, `ezdxf` is never touched again.

| field | type | content |
|---|---|---|
| `edges` | `list[Edge]` | geometry translated into pure primitives — input of `heal()` |
| `texts` | `list[Text]` | the texts of the source |
| `source_meta` | `dict` | `$INSUNITS`, `$MEASUREMENT`, `tolerance` |
| `source_path` | `str` | path of the file |
| `warnings` | `list[str]` | loader diagnostics on the raw file |

`node_tolerance(override=None) -> float`: the distance below which two endpoints
are the same node — `override` if given, otherwise `source_meta["tolerance"]`,
otherwise `DEFAULT_NODE_TOLERANCE` (0.05, `model/document.py`). It is the reading
that `heal` and `validate_document` use when `tolerance` is not passed (D86).

### `Text`

A text of the source, a single type (MAP.md D138). Whether it is a note, a
dimension or a callout is a reading by whoever uses it, even when the format
already says so: the format stays in `source_kind`.

| field | content |
|---|---|
| `position` | `(x, y)` — the anchor point |
| `text` | the string as it reads on the drawing (a DXF dimension with `<>` is already resolved: `"12 H7"`) |
| `height`, `rotation`, `width_factor` | how the string is written |
| `role` | what it is for whoever uses it (see below) |
| `cluster_ref` | index of the cluster that contains it (from `anchor_texts`) |
| `source_kind` | the entity type in the source format (`"TEXT"`, `"MTEXT"`, `"DIMENSION"`, `"LEADER"`, `"MULTILEADER"` in a DXF) |
| `pointer` | a polyline starting at the tip (`pointer[0]`): where the text points |
| `target` | the element on which the tip falls, the object itself (from `topo.experimental.anchor_elements`, D177); outside `repr` and `==` |
| `measured_points` | the points on the geometry between which the number was measured: two ends; two opposite points of a circle; a point of an arc |
| `measure` | the number that the source says it measured; `None` if it does not say (a PDF) |
| `measure_is_angle` | `measure` is an angle, not a length |
| `references` | the elements on which the `measured_points` fall, the objects themselves (from `topo.experimental.anchor_elements`, D177); outside `repr` and `==` |
| `rendered` | the image that the source draws around the string (lines, arrows, other texts): `to_dxf` rewrites that instead of the string alone |

`role` says what the text is for whoever uses it (`"title_block"`, `"part_code"`,
...), like the role of an edge (MAP.md D127). topo does not read it and does not
decide it: it is written by the consumer (`Text(..., role="title_block")`, cleaned by
`normalize_role`), or by its `role_rules` at load, on the name of the source
group (the layer of a DXF). On a text only the rules on the name count
(`name`, `name_contains`): a rule on stroke or colour does not touch it.
`unknown` if nobody said. The source group serves only this and does not
stay in the model (D128): whoever wants a distinct text in the output gives it a
role. `topo_dxf.to_dxf` writes a text that has a role on the layer of its
role, like an edge; without a role, on `text_layer`.

### `Result`

Produced by `Network.faces()` or `Network.outlines()`, enriched by a consumer.

| field | type | content |
|---|---|---|
| `clusters` | `list[Cluster]` | one element per closed outer contour |
| `is_valid` | `bool` | **check it before `split` or before writing (`topo_dxf.to_dxf`)** |
| `warnings` / `errors` | `list[str]` | diagnostics |
| `loose` | `list[OpenCurve \| ClosedCurve]` | every curve that is the contour of no cluster: chains that close nothing, open traces, closed curves with a non-structural role (D137). `curve.cluster_ref` = index of the cluster whose outer contour contains all of it, border and holes included (a line from side to side, a cross inside a hole); `None` otherwise. With `outlines()` also the cluster that the curve touches (D99). A consumer moves it into `cluster.overlay` with `result.promote` |
| `texts` | `list[Text]` | copied from the `Network` (from the `Document`) |
| `cluster_count` | property | `len(clusters)` |

Method `to_dict()` → JSON-ready dictionary (used internally by the exports).

#### `Result.promote`

```python
result.promote(
    curves,                           # an element of result.loose, or more than one
    cluster: Cluster,                 # an element of result.clusters
    name: str,                        # the collection of cluster.overlay
    *, item=None,                     # what to attach: the curve itself if None
) -> None
```

**Loose curves become part of a cluster** (D137, D172, D173). It removes `curves`
(a curve, or a sequence) from `result.loose` and puts **a single** `item`
in the collection `name` of `cluster.overlay`, creating it if missing. `item` is
what the caller made of the curves (an object of its own with `role` and
geometry, D90); with a single curve it may be absent, and then it is the curve itself.
Several curves read as one thing — a hole and its seat — are one item.

What the curves are is decided by the caller, and it does not matter where they are: a line
inside the part that a consumer reads as an axis, a guide outside the part
that points to a detail of it. topo promotes nothing on its own.

**Raises `ValueError`**, touching nothing, if a curve is not in
`result.loose` or is given twice, if `curves` is empty, if `cluster` is not in
`result.clusters`, if there are several curves and `item` is missing, or if
`item` carries no geometry a renderer draws (no contour with `segments` and a
role, D244): a curve is never in two places, nor
lost — the curves would otherwise leave `loose` and reach no file.

```python
for curve in list(result.loose):
    if curve.cluster_ref is not None and is_axis(curve):   # the reading is yours
        result.promote(curve, result.clusters[curve.cluster_ref], "axes")

# a hole with its seat: two curves, one item
result.promote([hole, seat], view, "features", item=my_counterbore)
```

### `Cluster`

| field | type | content |
|---|---|---|
| `outer` | `Contour` | outer profile (has `segments`, `role`, `area`, `bbox`) |
| `inners` | `list[Contour]` | closed contours inside the outer, with no reading (a circle is not a hole, D15) |
| `label` | `str` | label, basis of the file name |
| `overlay` | `Optional[Overlay]` | a consumer's overlay — `None` until someone has written to it (D44, D90) |
| `features(name)` | method | collection `name` from `overlay` — `[]` if `overlay` is `None` or `name` has not been written |
| `summary` | property | **raw** count, always available: `{name}_count: len(items)` for each collection in `overlay` — `{}` if `overlay` is `None` |
| `overlay_voids` | property | the elements of the overlay with `is_void = True` and the `segments` of a closed loop: voids of the part read by a consumer (D90) |
| `area` | property | outer − overlay voids − inners at odd depth + inners at even depth (D89, D90) |
| `bbox` | property | `(minx, miny, maxx, maxy)` |
| `to_dict()` | method | the facts that `to_json` writes: `label`, `area`, perimeters, `inner_count`, `bbox`, `overlay` (D230) |

A consumer attaches its detection like this (`topo.Overlay`):
`cluster.overlay = cluster.overlay or Overlay();
cluster.overlay.attach("flange_view_hint", [...])`, then reads it with
`cluster.features("flange_view_hint")`. No name is privileged (D44) and there is no contract on the elements, not even at runtime.

### `Contour`

`role` (`ContourRole`), `segments` (native primitives, a head-to-tail ring),
`depth`, `parent`. No shapely type (D166): the polygon is requested from
`topo.to_shapely(contour)`. Facts computed on the `segments`, not on the
polygon (D165, D166): exact `area` and `centroid` (Green; `centroid` raises
`ValueError` if the loop encloses no area), exact `bbox` (arcs and ellipses
at their true extremes, not on the chords), `contains(point, tolerance=1e-6)`
(closed region: the border within `tolerance` is inside), `points(tolerance=0.01)`
(the discretised loop as `(x, y)` tuples, the first point not repeated at the
end). The same on every `ClosedCurve` of `result.loose`.

```python
topo.Contour.from_segments(segments, role, *, depth=0, parent=None, tolerance=0.01) -> Contour
```

A contour from a ring of primitives written by a caller (for example the
result of `geometry.contour_minus`): it checks that every segment starts where
the previous one ends and that the last closes on the first.
**Raises** `ValueError` if the ring does not close or does not enclose a valid
polygon (D118).

### `ContourRole` (engine roles — open vocabulary)

The engine knows only three roles: `unknown`, `outer`, `inner` (MAP.md D47,
"roles out of core"; process roles belong to snapbend, D88).
**It is not a closed universe**: anyone can assign a role the engine does not know (`hole`,
`frame`, `title_block`, `section`, …). It goes through `normalize_role()` — cleaned
into a slug `[a-z0-9_-]` ≤ 64 chars — and topo preserves it without raising; in
the output the DXF adapter writes it by default on a layer **named after the slug**,
grey (`unknown` → `Trash`, red), unless the caller chooses otherwise
(`topo_dxf.to_dxf(layers=..., role_styles=...)`, D128). `role_str(role)` gives the string value whether the role is a
constant or a slug (MAP.md D27 / D31).

**`topo.normalize_role(value) -> str`** and **`topo.is_structural_role(role) ->
bool`** are public (MAP.md D30). `is_structural_role` (the engine's
predicate, only `outer`/`inner`) is what `heal()` uses by default if you do not
pass `is_structural=...` — see `heal()` above. A consumer that marks the geometry **before
`heal`**: keeps the references to the `Edge`s of `doc.edges`, sets
`edge.role = topo.normalize_role("frame")` — it stays out of the graph by
default (no predicate recognises it as structural), the marked geometry
ends up in `loose` with its role intact and the output writes it on the layer
`frame`. This is the hook used by `snapdraw` for frame and title block.

### `non_contour_candidates`

```python
topo.non_contour_candidates(doc: Document, *, tolerance=None) -> list[Edge]
```

Edges of `doc.edges` that the topological criterion of `heal()` would exclude from the
contour graph (chains between two distinct branching nodes, and not on the border
of the outer face of their connected component, MAP.md D111, D131) — **without saying what they are**. `heal()` by itself
assigns no meaning to these edges: it just excludes them, they stay in
`loose` with the role they had. A consumer interprets them (snapbend
`detect_flat`: straight, endpoints on the outer contour → `"bending"`).

A consumer that wants
an interpretation of its own (the border of a raised feature seen in plan is not
a bend) calls `non_contour_candidates(doc)` to get the same list
of candidates that `heal()` would use, without duplicating the criterion, and decides
for itself how to mark them — then assigns `edge.role` on the returned `Edge`s (they are
references into `doc.edges`, mutating them is reflected there) **before** calling
`heal()` (see `ContourRole` above, MAP.md D55).

| parameter | meaning |
|---|---|
| `tolerance` | if `None`, taken from `doc.source_meta["tolerance"]` — same fallback as `heal()`. |

It works on `doc.edges` as they are, **before** `heal()` merges overlapping/co-circular
segments and closes tiny gaps (its first internal steps,
D50/D52): on a drawing with duplicates or gaps below tolerance the result may
differ slightly from what `heal()` would exclude in the end. This is not a
problem for the intended use — deciding `edge.role` before `heal()` — because
the final word on what stays in the graph is said by `heal()` itself anyway.

```python
for edge in topo.non_contour_candidates(doc):
    if <your logic decides it is the border of a raised feature>:
        edge.role = topo.normalize_role("flange_up")

result = topo.heal(doc).faces()   # "flange_up" is already out of the graph, "bending" never guessed
```

---

## 8. The complete flow, in order

```python
import topo, topo_dxf

# 1. open — the adapter is the only one that reads a format
doc = topo_dxf.load_dxf("pezzo.dxf", tolerance=0.5)

# 2. validate the input (optional but recommended)
check = topo.validate_document(doc)
if not check.is_valid:
    raise SystemExit(check.errors)

# 3. topology
result = topo.heal(doc, label="P-1024").faces()
# 4. (optional) a process reading, outside topo — e.g. snapbend:
#   from snapbend.flat import detect_flat
#   detect_flat(result, "all")

# 5. ALWAYS check before rendering
if not result.is_valid:
    raise SystemExit(result.errors)

# 6a. render — one document with all the parts
topo_dxf.to_dxf(result, doc).saveas("pezzo_healed.dxf")

# 6b. or render — one file per part
for part in topo.split(result):
    topo_dxf.to_dxf(part, doc).saveas(f"output/{part.clusters[0].label}.dxf")

# 7. the facts as JSON
topo.save_json(result, "pezzo.json")
```

If something does not add up on a real file: `topo_dxf.inspect_file("pezzo.dxf")`.

---

## 9. `topo_dxf` — the DXF adapter

```python
import topo, topo_dxf          # pip install g-topo[dxf]
```

A topo consumer like any other, in the same distribution: it reads DXF/DWG
into a `Document`, writes a `Result` into an `ezdxf` `Drawing`. It uses only the public
names of topo (D125, D129); without `ezdxf` installed, `import topo_dxf`
says which extra is missing. Layers and colours are the caller's choices; what the
caller does not say is this adapter's default.

### `load_dxf`

```python
topo_dxf.load_dxf(
    path,
    *, upgrade=False,
    explode_inserts=True,
    flatten_z=True,
    verbose=False,
    tolerance=0.05,
    role_rules=(),
    skip_layers=(),                   # layer names, or a function name -> bool
) -> Document
```

The only point where `ezdxf` is used to **read**. It opens a `.dxf` or `.dwg`,
audits it, brings it to R2010 if legacy, explodes the `INSERT`s, sanitises (OCS, Z≠0),
translates the entities into pure `Edge`s and the texts into `Text`. After this
function the source `ezdxf` document disappears.

| parameter | meaning |
|---|---|
| `path` | path of the `.dxf` or `.dwg`. For `.dwg` see the **DWG** section below. |
| `upgrade` | forces the upgrade to R2010 even if not necessary. |
| `explode_inserts` | `True` (default): explodes the blocks into primitives. **Set `False` only if you want to ignore the blocks on purpose** — an unexploded `INSERT` is discarded and its geometry disappears. |
| `flatten_z` | brings entities with Z ≠ 0 back onto the plane. |
| `tolerance` | rounding tolerance of the topological nodes. It is saved in `source_meta` and read again by `heal()` if you do not pass it again. |
| `role_rules` | list of `RoleRule` — they assign the **role** to the `Edge`s already during translation. Evaluated in order, the first that matches wins, none → `unknown`. The name evaluated by `name`/`name_contains` is the layer; `dashed` and `color` look at the **effective** look (a `ByLayer` entity is resolved to the linetype/colour of its layer). The layer does not leave the adapter: the `Edge` carries only the role (MAP.md D63). See **`RoleRule`** below. |
| `skip_layers` | the layers whose geometry is skipped. A sequence matches by **exact name** (case ignored); a function `name -> bool` decides by itself, with the name as it is in the file: part of the name, a regex, an algorithm of your own (`skip_layers=lambda n: "quote" in n.lower()`, D176). By default `()`: every layer is read (D243). To read back a file written by topo without its `loose` and text layers, pass `skip_layers=topo_dxf.SKIP_LAYERS` (`Trash_old` is still read). The curves skipped are counted per layer in one `dxf-layer-skipped` warning in `doc.warnings` (D242). |

**Returns** a `Document`. The diagnostics on the raw file (audit, unexploded
INSERTs, Z≠0, duplicates removed, types that cannot be re-materialised in output) end up
in `doc.warnings`; `topo.validate_document(doc)` raises them again.

**What it reads.** Geometry: `LINE`, `ARC`, `CIRCLE`, `ELLIPSE`, `SPLINE`,
`LWPOLYLINE`, `POLYLINE` — every one becomes `Edge`s, and `heal()` decides what
closes. Texts: `TEXT`, `MTEXT`, `DIMENSION`, `LEADER`, `MULTILEADER`. Blocks:
`INSERT` exploded (`explode_inserts`). A `HATCH` with a pattern becomes the lines
of its pattern; a solid fill stays out. Files older than R2000 are upgraded to
R2010 (a note says so). Every other entity type is not in the `Document` and is
named in the `dxf-not-modeled` warning, never dropped in silence.

**Raises** `FileNotFoundError`, `EnvironmentError` (DWG without `ODA_PATH`),
`RuntimeError` (DWG conversion failed), or the read exceptions of `ezdxf`.

```python
doc = topo_dxf.load_dxf("pezzo.dxf", tolerance=0.5,
                     role_rules=topo.name_rules({"Piega": "bending", "MARK": "engrave"}))
for w in doc.warnings:
    print("loader:", w)
```

When the intent lies in the line style, or in a combination of
name and style:

```python
doc = topo_dxf.load_dxf("pezzo.dxf", role_rules=[
    topo.RoleRule("construction", name_contains="constr", dashed=True),
    topo.RoleRule("bending", dashed=True),
    topo.RoleRule("engrave", color="cyan"),
])
```

See `14_style_classification.py` for a complete example (one rule per
step, on a real file in `tests/examples/`).

#### DWG

**`topo` does not read DWG by itself, and neither does `ezdxf`.** DWG is a closed
format: the "DWG support" of `ezdxf` is the `odafc` addon, which is a wrapper around
**ODA File Converter** — it converts the `.dwg` into a temporary `.dxf` and `ezdxf`
reads that back. `topo` uses exactly this (`topo_dxf/loader.py`).

To open a `.dwg` you therefore need:

1. **ODA File Converter** installed — free download:
   <https://www.opendesign.com/guestfiles/oda_file_converter>
2. `topo` must find the executable. Two ways:
   - environment variable **`ODA_PATH`** = *full path of the executable*
     (not the folder — if ODA is in `ODAFileConverter X.Y.Z\`, the path must
     include `\ODAFileConverter.exe`);
   - or `ODAFileConverter` reachable from the system `PATH`.

Setting `ODA_PATH`:

| OS | command |
|---|---|
| Windows, permanent | `setx ODA_PATH "C:\Program Files\ODA\ODAFileConverter X.Y.Z\ODAFileConverter.exe"` — then **reopen the terminal** |
| Windows, session only (PowerShell) | `$env:ODA_PATH = "C:\...\ODAFileConverter.exe"` |
| Windows, GUI | Settings → *Edit the system environment variables* → *Environment Variables…* → *New* |
| Linux / macOS, permanent | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` in `~/.bashrc` or `~/.zshrc`, then reopen the shell |
| Linux / macOS, session only | `export ODA_PATH="/opt/ODAFileConverter/ODAFileConverter"` |

Reference guides for environment variables:
[Windows](https://learn.microsoft.com/windows/win32/procthread/environment-variables) ·
[Linux/macOS (`export`)](https://www.gnu.org/software/bash/manual/bash.html#Environment).

If everything is missing, `load_dxf` on a `.dwg` raises `EnvironmentError` with the link and
this same guide in the message.

---


### `document_from_msp`

```python
topo_dxf.document_from_msp(
    msp,
    *, tolerance=0.05,
    role_rules=(),
    source_path="",
    skip_layers=(),
) -> Document
```

Builds a `Document` from an `ezdxf` `modelspace` that is **already open**. Useful for
tests or for hand-generated geometry. It does **not** do audit / upgrade / sanitize: the `msp`
is assumed to be ready already. `role_rules` and `skip_layers` work as in `load_dxf()` — see above.

```python
import ezdxf
doc_ez = ezdxf.new("R2010"); msp = doc_ez.modelspace()
msp.add_line((0, 0), (100, 0)); msp.add_line((100, 0), (100, 50))
# ...
document = topo_dxf.document_from_msp(msp, tolerance=0.5)
```

### `to_dxf`

```python
topo_dxf.to_dxf(
    result: Result,
    source_doc: Document = None,
    *, filter_cluster=None,
    include_texts=True,
    include_loose=True,
    text_layer="Annotation",
    role_styles: dict[str, RoleStyle] = None,
    layers: dict[str, str | Callable[[object], str]] = None,
    allow_invalid: bool = True,
    exclude_types: set[str] = None,
) -> ezdxf.document.Drawing
```

Materialises the model into a **new DXF document** (R2010). It never re-reads
entities from the source: `source_doc` serves only to carry over the headers
(`$INSUNITS`, `$MEASUREMENT`). The texts come from `result.texts`.

| parameter | meaning |
|---|---|
| `filter_cluster` | `callable(Cluster) -> bool` — writes only the clusters that pass; `loose` and texts are all written. For one file per part, the part comes from `topo.split` (§3), which has already divided them. |
| `exclude_types` | set of `dxftype`s to remove from the document (e.g. `{"TEXT"}`). |
| `include_loose` | `True` (default): the curves of `result.loose` go on the layer of their role (`Trash` for `unknown`). Whoever opens the file must be able to see every entity of the starting drawing. |
| `allow_invalid` | `True` (default): an invalid `result` is written all the same (`loose` and texts), as `to_svg` does. `False` → `ValueError`: for the caller that hands the file to a machine (D83). |
| `layers` | where each role goes: `{role: "Name"}`, or `{role: function(element) -> name}` to split the entities of a role over several layers by looking at the element written (the `Contour`, the element of `cluster.overlay`, the curve of `loose` or the `Text`). A role you do not name stays at the adapter's default: `OuterContour`, `InnerContour`, `Trash` for `unknown`, the slug for every other role (D31, D128). |
| `role_styles` | how each role is drawn: `{role: RoleStyle}` (see below). It acts on the layer — everything is written BYLAYER — and on a layer shared by several roles the first one written wins. A role with a style has its layer even without entities. Underneath there is always topo's palette (`DEFAULT_ROLE_STYLES`): the map adds the caller's roles and changes only the fields it gives. |
| `text_layer` | the layer of the texts **without a role** (default `"Annotation"`). A text with a role goes on the layer of its role, like an edge (D127, D128). No text is ever discarded. |

The maps are the caller's and hold for its call: topo keeps none of them
(D128). A consumer publishes its own (`snapbend.flat.ROLE_STYLES`,
`snapbend.flat.LAYERS`) and whoever exports passes them, or composes them:

```python
# the frame (role "frame", assigned by a consumer such as snapdraw) in black, on "Cornice"
topo_dxf.to_dxf(result, doc,
            layers={"frame": "Cornice"},
            role_styles={"frame": topo.RoleStyle(color=(0, 0, 0))})

# the bends on two layers, according to direction (information carried by the element)
topo_dxf.to_dxf(result, doc, layers={"bending": lambda bend: "BendUp" if is_up(bend) else "BendDown"})   # is_up: the caller's
```

**The overlay** (D70, D90): it writes every collection of `cluster.overlay`,
without knowing any by name. Of an element it reads only `role` and
geometry: `item.contours` if present (each with `segments`/`styles` and
possibly a `role` of its own), otherwise the element itself. A contour is
written closed (LWPOLYLINE/CIRCLE) if it is a `ClosedCurve`, if the element
declares itself a void (`is_void`) or if its `segments` close a loop
(`topo.model.feature_closed`); otherwise as one entity per primitive
(LINE/ARC/SPLINE). The `role` of a contour wins over that
of the element only if it is not an engine role (`outer`/`inner`/`unknown`).
Without a role or without geometry it is skipped.

**Returns** an `ezdxf` `Drawing`. It is up to you to call `doc_out.saveas(...)`.

**Raises `ValueError`** only with `allow_invalid=False` and `result.is_valid`
`False`. The refusal is not the format's, it is the refusal of whoever hands the file to a machine:
that caller asks for it explicitly.

```python
topo_dxf.to_dxf(result, doc).saveas("guarda.dxf")                         # always
topo_dxf.to_dxf(result, doc, allow_invalid=False).saveas("macchina.dxf")  # only if valid
```

---

### `inspect_dxf` / `inspect_file`

```python
topo_dxf.inspect_dxf(path, *, entities=True, limit=40) -> None
```
**Level 1** — raw DXF entities: version, header, count by type and by
layer, detail of each entity. Does not touch `topo`.

```python
topo_dxf.inspect_file(path, *, tolerance=0.05, role_rules=(),
                   run_heal=True, entities=True, coords=False) -> None
```
Orchestrator: opens the file and prints the three levels in a row. `run_heal=False` to
stop at the `Document`. `role_rules` as in
`load_dxf()`.

```python
topo_dxf.inspect_file("pezzo.dxf", role_rules=topo.name_rules({"Piega": "bending"}))
topo_dxf.inspect_file("pezzo.dxf", role_rules=[topo.RoleRule("bending", dashed=True)])
```

### The default layers

topo has no layers (D123); these are the adapter's defaults, when the
caller does not pass `layers=`:

| name | value | |
|---|---|---|
| `topo_dxf.LAYER_OUTER` | `"OuterContour"` | role `outer` |
| `topo_dxf.LAYER_INNER` | `"InnerContour"` | role `inner` |
| `topo_dxf.TRASH_LAYER` | `"Trash"` | role `unknown` |
| `topo_dxf.LAYER_ANNOTATION` | `"Annotation"` | texts and dimensions without a role |
| `topo_dxf.DEFAULT_LAYERS` | `{role: layer}` | the three engine roles |
| `topo_dxf.SKIP_LAYERS` | `("Trash", "Annotation")` | the writer's `loose` and text layers: pass them as `skip_layers` to read a topo file back without them (D243) |

```python
topo_dxf.role_to_dxf_layer(role, element=None, *, layers: LayerMap = None) -> str
```

The layer of a role as `to_dxf` chooses it: the caller's map (a
name, or the function called with `element`), otherwise the default, otherwise
the slug of the role (D31). `LayerMap` is the type of that map:
`Mapping[str, str | Callable[[object], str]]`.

```python
topo_dxf.role_to_dxf_layer("hole", layers=snapbend.flat.LAYERS)   # "Hole"
topo_dxf.role_to_dxf_layer("frame")                               # "frame"
```

---

## 10. `topo_pdf` — the PDF adapter

```python
topo_pdf.load_pdf(path, snap_tolerance=0.15) -> list[Edge]     # pip install g-topo[pdf]
```

**Experimental** (MAP.md D10): opens a PDF, extracts the vector geometry
of each page, brings it to mm with the Cartesian Y axis and cleans it with a
snap of nearby nodes. Returns a list of `Edge`s, **not a `Document`**:
it cannot yet be passed to `topo.heal()`, and the API may change or disappear. Work
on the PDF resumes here (TODO.md, "Aperti minori").
