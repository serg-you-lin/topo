# topo — architecture

This document explains *how it is built inside* and *why*. For practical use of
the API see [`API.md`](API.md).

---

## The idea in one sentence

`topo` is a **topological reconstruction engine** that knows no file
format: geometry and roles, never layers. Formats come in and go out through adapters, sibling packages in the same
distribution (`topo_dxf`, `topo_pdf`). It takes noisy 2D geometry and produces a
consistent, lossless geometric model: closed contours, containment hierarchy,
texts, and an open overlay where a consumer writes its own reading. It
assigns no meaning: saying what a contour or a line means is an
interpretation, and it belongs to the consumers.

DXF is only the first implemented format, and it lives outside topo: `topo`
imports neither `ezdxf` nor an adapter, and installs without them (`pip install g-topo`;
`g-topo[dxf]` brings `topo_dxf` with `ezdxf`). The core works on pure geometric primitives, never on the entity types of a source.

---

## The principle: the product is the model

```
                                  ┌──────────────┐
  DXF / DWG ── topo_dxf ─────────►│              ├── topo_dxf ──► DXF (to_dxf)
  PDF ──────── topo_pdf (exper.) ►│    Result    ├──────────────► JSON (to_json, save_json)
  geometry ─── load_segments ────►│  the model   ├──────────────► view model (to_view_model)
                                  │              ├──────────────► SVG (to_svg, save_svg)
                                  └──────┬───────┘
                                         └── split ──► one Result per part, then any of the renderers
```

The `Result` is **the product**. Every `to_*` is a renderer of the model.
`to_dxf` **never re-reads the source file** — it draws from the model. This is
why `to_svg` produces the exact same image without a line of
new code in the core.

Practical consequence: **nothing is lost**. Everything is imported — annotations, auxiliary lines, garbage.
So that `topo` loses
nothing, the model is rich enough to hold even what it has not classified:

- reconstructed closed geometry → outer and inner contours, and the features a reading adds
- every curve that is no cluster's contour → `result.loose`
  (pure segments, format-independent; `cluster_ref` says which cluster
  contains it). What it is, a consumer decides, and moves it into
  `cluster.overlay` with `result.promote`
- texts → `result.texts` (`Text`, a single type: the string laid in the
  plane and, when the source groups one, the picture drawn with it as
  primitives; what a text measures is a reading). See `TEXTS.md`

The entity types that `topo` does not model (`HATCH`, `IMAGE`, `TABLE`, `3DFACE`,
`XLINE`…) stay out, but `load_dxf` emits a warning listing them — no
silent loss.

---

## The structure

One distribution (`g-topo`), three importable packages at the repo root
:

```
topo/             THE ENGINE — no format, no ezdxf / PyMuPDF
topo_dxf/         DXF/DWG ADAPTER                      (knows ezdxf; extra [dxf])
│                     a consumer of topo: public names only, never topo.core
├── loader.py         load_dxf, document_from_msp       (+ adapter, parser, sanitize,
│                                                         text_extractor, mtext)
├── writer.py         to_dxf                            (+ exporter: segments → entities)
├── layers.py         the default layers, SKIP_LAYERS, role_to_dxf_layer
└── inspect.py        inspect_dxf, inspect_file
topo_pdf/         PDF ADAPTER — experimental, frozen (knows fitz; extra [pdf])
```

Inside `topo/`:

```
topo/
├── core/         pure geometric ENGINE                (zero format)
│   ├── primitives/   one module per primitive, named for what it is:
│   │                 mathseg.py (MathSeg, the mother), line.py, spline.py,
│   │                 conics.py (Conic, Ellipse, Circle, Parabola, Hyperbola + the
│   │                 arc grid), formula.py, clothoid.py; motion.py (moving a point),
│   │                 polyline.py (the chord check), trim.py (sub_segment)
│   ├── topology/     edge.py, node graph, loop search;
│   │                 noding.py (planar network), outer_face.py (outer face),
│   │                 touching.py (groups of edges that touch)
│   ├── base/         THE FOUNDATIONS OF EVERY READING: prepare.py (nodes decided
│   │                 once, normalization), cleanup.py, merge.py, refit.py,
│   │                 gaps.py, hierarchy.py — heal, the readings and every caller
│   │                 recipe start from here
│   ├── readings/     THE READINGS: network.py (the repair and `Network`),
│   │                 heal.py (`heal()`), faces.py (`faces()`), outline.py
│   │                 (`outlines()`) and their own steps (heal_steps.py,
│   │                 outer_scan.py) — each reading chooses only
│   │                 how it looks for the contour
│   ├── geometry/     THE GEOMETRY, `topo.geometry`: facts with geometric names
│   │                 — shape, concentric (concentric circles, arcs around), lines
│   │                 (chords, collinear rows), axis (covered rectangles) — and the
│   │                 building blocks measure / numeric / points / intersections;
│   │                 fitting.py: primitives from a sequence of points (simplify_points),
│   │                 shapely_polygons.py: the shapely polygon of a list of curves
│   ├── geometry_input.py load_geometry / load_segments — pure geometry, not a
│   │                 format: an input of topo, not an adapter
│
├── model/        THE topo DOMAIN                     (pure dataclasses, no shapely types)
│   ├── document.py   Document
│   ├── result.py     Result — `promote()` moves curves from `loose` to
│   │                 `cluster.overlay`, never in two places
│   ├── cluster.py    Cluster — the container, `overlay` is a consumer's
│   │                 overlay (vocabulary open by name)
│   ├── overlay.py    Overlay — the overlay container
│   ├── curve.py      Curve → ClosedCurve / OpenCurve
│   ├── contour.py
│   ├── text.py       Text — the source's texts
│   ├── diagnostic.py Diagnostic — a warning: what, where, why, how to fix
│   ├── style.py      EdgeStyle — what the source says about a curve's look
│   ├── role_rule.py  RoleRule — source facts → role
│   └── role.py       ContourRole = only UNKNOWN/OUTER/INNER — the minimum
│                      the engine uses. No consumer role here
│                      ("roles out of core")
│
├── tools/        optional STAGES on a Document/Result (the caller chooses which and in what order)
│   ├── anchor.py         anchor_texts()         — anchors texts to clusters
│   ├── non_contour.py    non_contour_candidates() — the same non-contour criterion
│   │                     as heal(), exposed to decide `edge.role`
│   │                     BEFORE heal() — works on Document
│   ├── rotate.py         rotate_*() (experimental)
│   ├── split.py          split() — one Result per part, plus what no part contains; no format
│   └── strips.py         facing_boundaries(), link(), unconnected_regions(), open_boundaries()
│
├── io/           RENDERERS of the model with no format dependencies
│   ├── svg.py        to_svg(), save_svg()  (outside the stable 1.0)
│   ├── view_model.py to_view_model()  (outside the stable 1.0)
│   └── json_export.py to_json / save_json (geometry only)
│
├── rules/        domain RULES                          (validation)
├── inspect.py    inspection: inspect_document, inspect_result (the file
│                 level belongs to the adapter: topo_dxf.inspect_dxf)
└── experimental.py  everything used with no promise of stability: heal/faces/outlines
                  steps, viewer, rotate_*, simplify_points,
                  strips
```

`pipeline/` does not exist: the three different things it would hold are kept apart —
`heal` (now in `core/`), the optional stages (`tools/`) and the renderers
(`to_dxf`, in `topo_dxf`; `split`, in `tools/`). `heal` is not the engine's single act: `heal()` repairs the
geometry once and returns a `Network`; the two readings,
`faces()` and `outlines()`, compose the same core ingredients in different
ways and fill the same model. The product is the model, not one of the
two readings.

**Dependency rule** (checked by `scripts/gen_index.py --check`,
in `pyproject.toml`):

- `topo` never imports `ezdxf`, `fitz`/`pymupdf`, `topo_dxf`, `topo_pdf`:
  it does not know the adapters exist. A test also proves it at
  runtime: `import topo`, `heal`, `split` in a process where ezdxf and PyMuPDF
  cannot be imported.
- an adapter does not import `topo.core`/`tools`/`io`/`rules`, nor the other
  adapter: only the public names (`topo`, `topo.model`, `topo.primitives`). Whatever an adapter finds it needs to take from inside is a missing
  public name.
- inside `topo`, `core` and `model` never import `tools` or `io`.
  Should `model/` ever need to annotate a type that lives in `tools/`, it does
  so only under `TYPE_CHECKING` — zero imports at runtime,
  `from __future__ import annotations` turns the annotation into a lazy string.

The core does not know where the geometry comes from. Moving an adapter to a repo of its own,
one day, is moving a folder: the boundary is already clean.

---

## The flow, step by step

### 1. `topo_dxf.load_dxf` → `Document`

The DXF adapter, the only code that reads `ezdxf`; a `Document` can also come
from `topo.load_segments`/`load_geometry` (geometry in hand, no format).
In order:

1. if `.dwg` → conversion via ODA File Converter
2. `readfile`
3. `audit` (texts are extracted **before**: the ezdxf auditor
   deletes dimensions that reference a missing geometry block)
4. upgrade to R2010 if the file is legacy (R12/R13/R14)
5. explode of `INSERT`s (default `True` — an unexploded block makes its
   geometry disappear)
6. sanitize: OCS normalization, flattening of Z ≠ 0, deduplication
7. translation: each entity → one or more `Edge`s; each text/dimension → one
   `Text`. Every layer is read; a caller reading back a file written by topo
   can skip the writer's `loose` and text layers with `skip_layers=SKIP_LAYERS`

After this function the source `ezdxf` object **disappears**. Everything else
works on the `Document`.

### 2. `heal` → `Network`, `faces()` → `Result` (topology)

The hard step. It works on `doc.edges`, zero `ezdxf`. Two phases: `heal()`
repairs and gives a `Network` (steps 0–1); `faces()` reads it (steps 2–6). Every
step is a function, exposed in `topo.experimental`; the repair
warnings live on the network. A consumer (snapdraw) composes the
same steps as it needs.

The repair is **one for every reading** (`readings/network.py`):
one fixed threshold, `SAME_POINT` for nodes, and one parameter, `max_gap` for gaps (default none closed),
and `Network` carries them together with `source_file` and `label`. The foundations are
**the same for every reading** (`core/base/`): `faces()`,
`outlines()` and any recipe go through the same functions, with the same
rules; a reading chooses only how it looks for the contour. The only point where
the two readings read the same fact differently is a named parameter:
`split_at_crossings(cut_crossings=...)`, because a crossing between two curves that
continue is a broken input or a mark for `faces()` and a contact for
`outlines()`: the network keeps the crossings as data (`crossings`), the
cut is made by the reading that asks for it.

0. **prepare** (`prepare`): non-structural roles set aside (`split_labeled`: the hook point for a
   consumer that marks the geometry before `heal`, and
   `topo.non_contour_candidates(doc)` exposes the step 3 criterion), then the
   nodes decided once: from the real points of the segments, endpoints within
   `SAME_POINT` are a single node, by proximity, never by grid cell

1. **normalize** (`normalize`): curves written as points refitted into primitives,
lines and arcs drawn in pieces merged, `LineSeg`
   under `SAME_POINT` welded, nearly complete arcs closed into a circle
   (gap within `max_gap` and at most 2° missing), then the gaps: every
   free endpoint closes on the nearest point of the network within `max_gap` — another
   endpoint (meeting or segment, each endpoint at most one gap) or the point
   where its curve, extended, meets another edge; never with a cross
   bridge; on a tie, none. Every comparison with
   `max_gap` includes it up to noise (`reach`)
2. **planar network** (`split_at_crossings`): every contact decided once on the
   true curves; for `faces()` the contacts where an end touches
   something cut, not the crossings
3. **non-contour** (`non_contour_pieces`): the chains through degree-2 nodes
   (`Graph.chains`) between two distinct branching nodes, which the boundary
   of the outer face of their component does not walk exactly once (a
   chord, a bridge), are not contour — they leave, whole. `faces()` does not
   decide what they are: a consumer decides, in its own way
4. **faces** (`face_loops`): the outer-face walk taken on each side
   of each edge gives all the faces; the bounded ones, split into simple loops
   (two lobes touching at a point are two loops), are the contours.
   No choice depends on edge order or on the reference. A
   side cut by a contact returns the file's segment if the loop
   walks all its pieces (`NodedEdges.whole`)
5. **loop → curve** (`structural_loops`, `loops_to_curves`): a loop with an
   edge of non-structural role is not a contour; a loop with no area (or a
   micro-circle) takes nothing, and its edges go whole into `loose`
; `loose` has a single rule, `loose_curves`
6. **hierarchy** (`build_hierarchy`): which loop contains which → containment
   tree `outer` / `inner`. `faces()` stops here: it gives **no**
   meaning to the inner contours — every contained loop is a `Contour`
   in `cluster.inners`.

If **no** closed outer contour forms, the result is declared
**invalid** (`is_valid = False`) — like an empty modelspace. `topo_dxf.to_dxf` and
`to_svg` draw it all the same (everything in `loose`) to let you see what
topo understood; refusing it is the choice of a caller that delivers to a machine
(`allow_invalid=False`).

`validate_result` is called automatically at the end of `faces()`.

### 2b. `outlines()` → `Result` (reading by outlines)

The alternative to `faces()` for **projections** (several projections side by side,
projected 3D). `faces()` looks for the figure from the inside, by
connectivity: on a projection several nearly coincident edges converge
on the same nodes and there is no local signal to choose which one continues
as the contour. `outlines()` starts from a global fact, what lies outside. The
network is that of `heal()`:

1. **set aside** the `Edge`s with a decided, non-structural role, already done by
   `heal()`: this is how a consumer removes a border, a label box, enclosing
   circles; they go into `loose` with their role
2. **groups**: the edges that touch within `max_gap` (`touching_groups`):
   no notion of closure, hence no graph ambiguity. No distance
   between figures: that depended on how the input is laid out,
   which topo does not know
3. the nodes, the refitted tessellated chains and the gaps up to `max_gap` (never
   moving an endpoint more than that) are already those of the network: `outlines()`
   no longer repairs on its own
4. **planar network** of each group (`split_at_crossings`): every contact, decided once
   per pair on the true curves, becomes a node shared by all the
   edges it touches
5. **outer face** (`outer_face`): start from the leftmost point of the
   geometry, at each node turn as little as possible counterclockwise; an
   edge walked back and forth is a protrusion (axis, mark)
6. **interior**: no `inner`, everything else in `loose` with the
   `cluster_ref` of the cluster that contains it or that it touches. A group whose
   contour lies inside another's is not a cluster: it goes in `loose`

Same contract as `faces()`: a `Result`, a `Cluster` per contour, and
`split` and the renderers do not know which reading produced it. What a
contour is (a projection, a figure, a border) is decided by the caller.

### 3. a consumer's reading (outside topo)

What a contour or a curve means is a consumer's reading
: it makes it on top of the `Result` and attaches it to `cluster.overlay` — not to fixed cluster fields. topo knows
no name in the overlay: `cluster.features(name)` reads a collection by
name, `[]` if `overlay` is `None` or that name was not written. The renderers
draw each element from its `role` and its geometry, and the
net area removes the elements that declare themselves voids of the figure (`is_void`).

### 4. one Result per part — `split`

`topo.split(result)` decides nothing: it gives one `Result` per cluster, with the loose
curves and the texts that belong to it — a curve goes to the cluster of its `cluster_ref`,
a text to its `cluster_ref` or to the part whose outer contains it, on the primitives.
What no part contains comes back apart (`Split.loose`, `Split.texts`): assigning it to the
nearest part, to every part or to none is an interpretation, the caller's. No duplicate,
nothing lost. No format: every renderer takes a `Result`, so a part goes to DXF, SVG or
text in the same way.

### 5. render — `topo_dxf.to_dxf`

It builds a **new** `ezdxf` document (never the source) and writes into it the pure
segments of the model, each on the layer the caller chooses for its
role, or on the adapter's default (see the table in the README and
`API.md` §8). Fidelity rules:

- **splines** are re-emitted as native `SPLINE`s, rebuilt from control points
  / knots / weights / degree — **never discretized to a polyline**
- **the overlay**: a closed contour (a `ClosedCurve`, an `is_void` void,
  segments that close a loop — `model.feature_closed`) is written closed, the others as N
  native entities (`LINE`/`ARC`/`SPLINE`/`CIRCLE`), **never as `LWPOLYLINE`**
 — so an open curve attached by a consumer comes out
- **`loose`** is always written, on the layer of each curve's role (`Trash`
  for `unknown`)
- **texts** are all rewritten, those of the `Result` it receives (with
  their `rendered` image if they have one): in a per-part file, those
  `split` gave to the part

### 6. JSON export

`to_json` / `save_json` write `Result.to_dict()`: where the
geometry comes from (`source_format`), how it was read (`reading`,
`max_gap`), the warnings, and for each part the exact facts on the primitives (area,
perimeters, bbox, counts of `overlay`). No coordinates, nothing of a
process: any extra field, such as a material or a code, is added by the
consumer with `extra(cluster)`, which cannot replace a topo field.

---

## Two concepts that recur everywhere

### The tolerance

`topo.precision.SAME_POINT` (0.001) is the distance under which two ends are one
node — fixed, not a parameter; gaps are closed only by `max_gap`. It does **not** round nodes: an endpoint is its true point, no
grid; two ends become the same node by distance. Gap closing is `max_gap`'s job,
not this threshold's. It serves as:

1. **node by contact** (`split_at_crossings`): an endpoint that lies
   within `SAME_POINT` on another edge's curve is a node — not only
   endpoint-on-endpoint, also endpoint-on-curve (a true T contact), format-
   agnostic, independent of how the file was drawn. And two cuts
   within `SAME_POINT` of each other are the same node, not two: a line
   nearly tangent to an arc crosses in two mathematically distinct but very close
   roots (a near-tangency is numerically unstable: a
   minimal perturbation of the source data moves the crossing point a lot
   when the angle is small). Treating them as two nodes leaves a
   sliver between them that can split in two a face that was meant to stay
   one (the cause isolated and fixed at the root).
   Now the contact is decided once per pair and gives one
   shared node: node identity (T, two endpoints, missed tangency) is within
   `GRAPH_EPSILON` (= `SAME_POINT`), as the graph already did; merging meetings within it
   is done only for one same pair, because over the whole network it percolates.

A gap wider than `max_gap` is **not** closed — it is a choice, not a bug: if the
file has big gaps, either they are intended or the unit of measure is wrong. To close
them, pass a larger `max_gap`.

### The double track of features (role_rules / inference)

Every feature of a consumer is reachable by **two paths** (the
second is the consumer's):

- **`role_rules`**: the caller says "the lines of source group `A` have
  role `a`", or "the dashed ones with `constr` in the name have role `b`". The role is
  assigned at load, is **authoritative**, and is not questioned downstream
  (`source="labeled"`, `confidence=1.0`). The vocabulary of roles is open —
  it goes through `normalize_role` and it is not an error that topo (that is, the engine)
  does not know it. What happens in `heal` depends on `is_structural=...`
: without it, any consumer role stays out of the graph; with
  the consumer's predicate, the roles it declares structural stay
  INSIDE the graph (they close the contours), the others stay out.
  The output writes it on a DXF layer named after the slug (not
  `Trash` — it is not garbage), geometry intact.
  A rule combines neutral signals — source group name, dashing,
  color — all true together; rules are ordered and the first wins
. topo gives the mechanism, the content is written by the caller: no
  vocabulary of names lives in topo. The name stays in the adapter, the `Edge`
  receives only the role. Dashing and color are the **effective** ones: a
  `ByLayer` entity inherits the style from the layer that contains it, and `DxfAdapter`
  resolves it before handing over an `EdgeStyle`, which knows no words of a
  format: stroke as signed marks, color in RGB. "Dashed" means the pattern has
  at least one gap — a fact of the pattern, not of the linetype's name.
- **geometric inference**: the consumer recognizes the feature by its shape
  (`source="geometric"`, `confidence < 1.0`).

---

## Exact, or through the polygon

The primitive is the truth and the polygon a view. Today the view still
carries part of the computation; this is where, and with what guarantee:

| computation | how | guarantee |
|---|---|---|
| polygon of a circle, ellipse, parabola, hyperbola, clothoid | step from the curvature | every chord within `tolerance`, by formula |
| polygon of a spline | Bézier pieces halved on their control points | within `tolerance`, by proof |
| polygon of a `FormulaSeg` | adaptive | checked on samples, not proved |
| length, area | ∫ on the exact derivative | machine precision |
| line × line, line × circle, circle × circle, line × any conic | closed form | exact |
| conic × conic, anything × spline, formula, clothoid | polygons at `CURVE_TOLERANCE` | within `SAME_POINT` |
| trim (`sub_segment`) | exact sub-curve (angle, knot insertion) | exact, except the search of the parameter of the cut point |
| spline → arc / ellipse | the spline's points checked against the conic | on its polygon, not on the curve |

The direction: the missing intersection pairs in closed form or certified by the
control-point hulls, an intersection that carries its parameters, then the
polygon only for drawing and noding (planned after 1.0).

---

## What is NOT (yet) clean

Honesty about the state — the details and reasons are not repeated here:

- **`topo_pdf.load_pdf`** returns `list[Edge]` instead of a `Document` → it does not
  hook into `heal()`. Frozen.
- **DWG** goes through ODA File Converter, an external executable: `topo_dxf`
  calls it via `ezdxf`'s `odafc` addon.
