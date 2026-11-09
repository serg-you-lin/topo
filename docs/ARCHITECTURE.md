# topo — architecture

This document explains *how it is built inside* and *why*. For practical use of
the API see [`API.md`](API.md).

---

## The idea in one sentence

`topo` is not a DXF library. It is a **topological reconstruction engine**
that knows no file format: geometry and roles, never layers (MAP.md
D123). Formats come in and go out through adapters, sibling packages in the same
distribution (`topo_dxf`, `topo_pdf`). It takes noisy 2D geometry and produces a
consistent, lossless geometric model: closed contours, containment hierarchy,
texts, and an open overlay where a consumer writes its own reading. It
knows no trade: saying what a contour or a line means is an
interpretation, and it belongs to the consumers (MAP.md D88).

DXF is only the first implemented format, and it lives outside topo: `topo`
imports neither `ezdxf` nor an adapter, and installs without them (`pip install g-topo`;
`g-topo[dxf]` brings `topo_dxf` with `ezdxf`). The core does not know what an arc or a
spline is as a CAD entity — it works on pure geometric primitives.

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

Practical consequence: **nothing is lost**. Everything is imported — dimensions, centerlines, garbage.
So that `topo` loses
nothing, the model is rich enough to hold even what it has not classified:

- reconstructed closed geometry → parts / inner contours / features (if a reading adds them)
- every curve that is no cluster's contour → `result.loose`
  (pure segments, format-independent; `cluster_ref` says which cluster
  contains it, D137). What it is, a consumer decides, and moves it into
  `cluster.overlay` with `result.promote` (D173)
- texts → `result.texts` (`Text`, a single type, D138: the string, the
  polyline it points to, the points between which the number was measured, and
  the image drawn around it as primitives)

The entity types that `topo` does not model (`HATCH`, `IMAGE`, `TABLE`, `3DFACE`,
`XLINE`…) stay out, but `load_dxf` emits a warning listing them — no
silent loss.

---

## The structure

One distribution (`g-topo`), three importable packages at the repo root
(MAP.md D124, D129):

```
topo/             THE ENGINE — no format, no ezdxf / PyMuPDF
topo_dxf/         DXF/DWG ADAPTER                      (knows ezdxf; extra [dxf])
│                     a consumer of topo: public names only, never topo.core (D125)
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
│   ├── primitives/   LineSeg, ArcSeg, BSplineSeg, CircleSeg, EllipseSeg + discretization;
│   │                 fitting.py: primitives from a sequence of points (simplify_points)
│   ├── topology/     edge.py, node graph, loop search;
│   │                 noding.py (planar network), outer_face.py (outer face)
│   ├── base/         THE FOUNDATIONS OF EVERY READING (D187, D188): prepare.py (nodes decided
│   │                 once, normalization), cleanup.py, normalizer.py,
│   │                 gap_solver.py, hierarchy.py — heal, the readings and every caller
│   │                 recipe start from here
│   ├── readings/     THE READINGS: network.py (the repair and `Network`),
│   │                 heal.py (`heal()`), faces.py (`faces()`), outline.py
│   │                 (`outlines()`) and their own steps (heal_steps.py,
│   │                 touching.py, outer_scan.py) — each reading chooses only
│   │                 how it looks for the contour
│   ├── geometry/     THE GEOMETRY, `topo.geometry` (D95): facts with geometric names
│   │                 — shape (shape, concentric circles, arcs around), lines
│   │                 (chords, collinear rows), axis (covered rectangles) — and the
│   │                 building blocks measure / points / intersections
│   ├── geometry_input.py load_geometry / load_segments — pure geometry, not a
│   │                 format: an input of topo, not an adapter (D123, D125)
│
├── model/        THE topo DOMAIN                     (pure dataclasses, no shapely types — D166)
│   ├── document.py   Document
│   ├── result.py     Result — `promote()` moves curves from `loose` to
│   │                 `cluster.overlay`, never in two places (D137, D173)
│   ├── cluster.py    Cluster — the container, `overlay` is a consumer's
│   │                 overlay (vocabulary open by name — D44)
│   ├── overlay.py    Overlay — the overlay container (D44, D90)
│   ├── curve.py      Curve → ClosedCurve / OpenCurve
│   ├── contour.py
│   ├── text.py       Text — the source's texts (D138)
│   ├── diagnostic.py Diagnostic — a warning: what, where, why, how to fix
│   ├── style.py      EdgeStyle — what the source says about a curve's look
│   ├── role_rule.py  RoleRule — source facts → role
│   └── role.py       ContourRole = only UNKNOWN/OUTER/INNER — the minimum
│                      the engine uses. No consumer role here
│                      (D47, "roles out of core")
│
├── tools/        optional STAGES on a Document/Result (the caller chooses which and in what order)
│   ├── anchor.py         anchor_texts()         — anchors texts to clusters (anchor_elements experimental, D228)
│   ├── non_contour.py    non_contour_candidates() — the same non-contour criterion
│   │                     as heal() (D49), exposed to decide `edge.role`
│   │                     BEFORE heal() (D55) — works on Document
│   ├── rotate.py         rotate_*() (experimental, D46)
│   ├── split.py          split() — one Result per part, no format (D129)
│   └── strips.py         facing_boundaries(), link(), unconnected_regions(), open_boundaries() (D134, D142)
│
├── io/           RENDERERS of the model with no format dependencies
│   ├── svg.py        to_svg(), save_svg()  (outside the stable 1.0, D133)
│   ├── view_model.py to_view_model()  (outside the stable 1.0, D133)
│   └── exporter.py   to_json / save_json (geometry only, D230)
│
├── rules/        domain RULES                          (validation)
├── inspect.py    inspection: inspect_document, inspect_result (the file
│                 level belongs to the adapter: topo_dxf.inspect_dxf)
└── experimental.py  everything used with no promise of stability: heal/faces/outlines
                  steps, viewer, rotate_*, simplify_points,
                  strips (D175 C, D176)
```

`pipeline/` no longer exists (MAP.md D22): it put together three different things —
`heal` (now in `core/`), the optional stages (`tools/`) and the renderers
(`to_dxf`, later in `io/` and today in `topo_dxf`; `split`, today in `tools/`). D22 also said
that `heal` is "the engine's single act": that is no longer true (D58) — `heal()` repairs the
drawing once (D202) and returns a `Network`; the two readings,
`faces()` and `outlines()`, compose the same core ingredients in different
ways and fill the same model. The product is the model, not one of the
two readings.

**Dependency rule** (checked by `scripts/gen_index.py --check`,
in `pyproject.toml`):

- `topo` never imports `ezdxf`, `fitz`/`pymupdf`, `topo_dxf`, `topo_pdf`:
  it does not know the adapters exist (D123, D129). A test also proves it at
  runtime: `import topo`, `heal`, `split` in a process where ezdxf and PyMuPDF
  cannot be imported.
- an adapter does not import `topo.core`/`tools`/`io`/`rules`, nor the other
  adapter: only the public names (`topo`, `topo.model`, `topo.primitives`,
  D125). Whatever an adapter finds it needs to take from inside is a missing
  public name.
- inside `topo`, `core` and `model` never import `tools` or `io` (D44).
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
   `Text`. The layers the writer uses for `loose` and texts
   (`SKIP_LAYERS`) are skipped, so a file that already went through topo is read back
   clean (D129)

After this function the source `ezdxf` object **disappears**. Everything else
works on the `Document`.

### 2. `heal` → `Network`, `faces()` → `Result` (topology)

The hard step. It works on `doc.edges`, zero `ezdxf`. Two phases: `heal()`
repairs and gives a `Network` (steps 0–1); `faces()` reads it (steps 2–6). Every
step is a function (D62), exposed in `topo.experimental` (D176); the repair
warnings live on the network. A consumer (snapdraw) composes the
same steps as it needs.

The repair is **one for every reading** (`readings/network.py`, D202):
two numbers, `tolerance` for nodes and `max_gap` for gaps (default `tolerance`),
and `Network` carries them together with `source_file` and `label` (D204). The foundations are
**the same for every reading** (`core/base/`, D187, D189): `faces()`,
`outlines()` and any recipe go through the same functions, with the same
rules; a reading chooses only how it looks for the contour. The only point where
the two readings read the same fact differently is a named parameter:
`split_at_crossings(cut_crossings=...)`, because a crossing between two curves that
continue is a broken drawing or a mark for `faces()` (D132) and a contact for
`outlines()` (D101): the network keeps the crossings as data (`crossings`), the
cut is made by the reading that asks for it.

0. **prepare** (`prepare`): non-structural roles set aside (`split_labeled`, D30: the hook point for a
   consumer that marks the geometry before `heal`, and
   `topo.non_contour_candidates(doc)` exposes the step 3 criterion), then the
   nodes decided once: from the real points of the segments, endpoints within
   `GRAPH_EPSILON` are a single node, by proximity, never by grid cell
   (D180, D187)
1. **normalize** (`normalize`): curves written as points refitted into primitives
   (D60), lines and arcs drawn in pieces merged (D50, D52, D184), `LineSeg`
   under 0.05 mm welded (D56, D186), nearly complete arcs closed into a circle
   (gap within `tolerance` and at most 2° missing, D112), then the gaps: every
   free endpoint closes on the nearest point of the network within `tolerance` — another
   endpoint (meeting or segment, each endpoint at most one gap, D112) or the point
   where its curve, extended, meets another edge; never with a cross
   bridge; on a tie, none (D185, D189). Every comparison with a
   tolerance includes it up to noise (`reach`, D183)
2. **planar network** (`split_at_crossings`): every contact decided once on the
   true curves (D180); for `faces()` the contacts where an end touches
   something cut, not the crossings
3. **non-contour** (`non_contour_pieces`): the chains through degree-2 nodes
   (`Graph.chains`, D131) between two distinct branching nodes, which the boundary
   of the outer face of their component does not walk exactly once (a
   chord, a bridge), are not contour (D111) — they leave, whole. `faces()` does not
   decide what they are: a consumer decides, in its own way
4. **faces** (`face_loops`): the outer-face walk taken on each side
   of each edge gives all the faces; the bounded ones, split into simple loops
   (two lobes touching at a point are two loops), are the contours.
   No choice depends on edge order or on the reference (D189). A
   side cut by a contact returns the file's segment if the loop
   walks all its pieces (`NodedEdges.whole`, D143)
5. **loop → curve** (`structural_loops`, `loops_to_curves`): a loop with an
   edge of non-structural role is not a contour; a loop with no area (or a
   micro-circle) takes nothing, and its edges go whole into `loose`
   (D151); `loose` has a single rule, `loose_curves` (D162)
6. **hierarchy** (`build_hierarchy`): which loop contains which → containment
   tree `outer` / `inner`. `faces()` stops here: it gives **no**
   meaning to the inner contours (D15) — every contained loop is a `Contour`
   in `cluster.inners`.

If **no** closed outer contour forms, the result is declared
**invalid** (`is_valid = False`) — like an empty modelspace. `topo_dxf.to_dxf` and
`to_svg` draw it all the same (everything in `loose`) to let you see what
topo understood; refusing it is the choice of a caller that delivers to a machine
(`allow_invalid=False`, D83).

`validate_result` is called automatically at the end of `faces()`.

### 2b. `outlines()` → `Result` (reading by outlines)

The alternative to `faces()` for a drawing of **views** (several views on a sheet,
isometrics, projected 3D). `faces()` looks for the part from the inside, by
connectivity: on a projected view several nearly coincident edges converge
on the same nodes and there is no local signal to choose which one continues
as the contour. `outlines()` starts from a global fact, what lies outside. The
network is that of `heal()`:

1. **set aside** the `Edge`s with a decided, non-structural role, already done by
   `heal()` (D30): this is how a consumer removes frame, title block, magnification
   circles; they go into `loose` with their role (D203)
2. **groups**: the edges that touch within `max_gap` (`touching_groups`):
   no notion of closure, hence no graph ambiguity. No distance
   between views: that depended on how the drawing is laid out,
   which topo does not know (D99)
3. the nodes, the refitted tessellated chains and the gaps up to `max_gap` (never
   moving an endpoint more than that) are already those of the network: `outlines()`
   no longer repairs on its own (D202)
4. **planar network** of each group (`split_at_crossings`, D180): every contact, decided once
   per pair on the true curves, becomes a node shared by all the
   edges it touches
5. **outer face** (`outer_face`): start from the leftmost point of the
   geometry, at each node turn as little as possible counterclockwise; an
   edge walked back and forth is a protrusion (axis, mark)
6. **interior**: no `inner` (D161), everything else in `loose` with the
   `cluster_ref` of the cluster that contains it or that it touches. A group whose
   contour lies inside another's is not a cluster: it goes in `loose`

Same contract as `faces()`: a `Result`, a `Cluster` per contour, and
`split` and the renderers do not know which reading produced it. What a
contour is (view, part, frame) is decided by the caller (D21).

### 3. a consumer's reading (outside topo)

What a contour or a curve means is a consumer's reading
(MAP.md D88): it makes it on top of the `Result` and attaches it to `cluster.overlay` (D44) — not to fixed cluster fields. topo knows
no name in the overlay: `cluster.features(name)` reads a collection by
name, `[]` if `overlay` is `None` or that name was not written. The renderers
draw each element from its `role` and its geometry (D90), and the
net area removes the elements that declare themselves voids of the part (`is_void`).

### 4. one Result per part — `split`

`topo.split(result)` chooses the parts on the model (`min_area`, `namer`) and gives
one `Result` per part, with the loose curves and the texts that
belong to it: a curve goes to the cluster of its `cluster_ref`, a text
to the part that contains it; if none, to the nearest among all — no
duplicate, nothing lost (D124, D129). No format: every renderer takes a
`Result`, so a part goes to DXF, SVG or text in the same way.

### 5. render — `topo_dxf.to_dxf`

It builds a **new** `ezdxf` document (never the source) and writes into it the pure
segments of the model, each on the layer the caller chooses for its
role, or on the adapter's default (see the table in the README and
`API.md` §9). Fidelity rules:

- **splines** are re-emitted as native `SPLINE`s, rebuilt from control points
  / knots / weights / degree (D135) — **never discretized to a polyline**
- **the overlay**: a closed contour (a `ClosedCurve`, an `is_void` void,
  segments that close a loop — `model.feature_closed`) is written closed, the others as N
  native entities (`LINE`/`ARC`/`SPLINE`/`CIRCLE`), **never as `LWPOLYLINE`**
  (D90) — so an open curve attached by a consumer comes out
- **`loose`** is always written, on the layer of each curve's role (`Trash`
  for `unknown`)
- **texts** are all rewritten, those of the `Result` it receives (with
  their `rendered` image if they have one): in a per-part file, those
  `split` gave to the part

### 6. JSON export

`to_json` / `save_json` write `Result.to_dict()`: where the
geometry comes from (`source_format`), how it was read (`reading`, `tolerance`,
`max_gap`), the warnings, and for each part the exact facts on the primitives (area,
perimeters, bbox, counts of `overlay`). No coordinates, nothing of a
process (D230, D231): material, thickness or a part code are added by the
consumer with `extra(cluster)`, which cannot replace a topo field.

---

## Two concepts that recur everywhere

### The tolerance

`tolerance` (default 0.05, the goldens use 0.5) is the widest gap topo can
close. It does **not** round nodes: an endpoint is its true point, no
grid (MAP.md D216); two ends become the same node by distance. It serves in two ways:

1. **gap closing**: a free endpoint closes within `tolerance` on another
   endpoint or where its curve, extended, meets the network (D189)
2. **node by contact** (`split_at_crossings`, D101): an endpoint that lies
   within `tolerance` on another edge's curve is a node — not only
   endpoint-on-endpoint, also endpoint-on-curve (a true T contact), format-
   agnostic, independent of how the file was drawn. And two cuts
   within `tolerance` of each other are the same node, not two: a line
   nearly tangent to an arc crosses in two mathematically distinct but very close
   roots (a near-tangency is numerically unstable: a
   minimal perturbation of the source data moves the crossing point a lot
   when the angle is small). Treating them as two nodes leaves a
   sliver between them that can split in two a face that was meant to stay
   one (MAP.md D100, the cause isolated and fixed at the root by D101).
   With D180 the contact is decided once per pair and gives one
   shared node: node identity (T, two endpoints, missed tangency) is within
   `GRAPH_EPSILON`, as the graph already did; `tolerance` merges only the
   meetings of one same pair, because over the whole network it percolates (D101).

A gap 4× the tolerance is **not** closed — it is a choice, not a bug: if the
file has big holes, either they are intended or the unit of measure is wrong. Workaround:
raise `tolerance`.

### The double track of features (role_rules / inference)

Every feature of a consumer is reachable by **two paths** (the
second is the consumer's, D88):

- **`role_rules`**: the caller says "the lines of source group `A` have
  role `a`", or "the dashed ones with `constr` in the name have role `b`". The role is
  assigned at load, is **authoritative**, and is not questioned downstream
  (`source="labeled"`, `confidence=1.0`). The vocabulary of roles is open —
  it goes through `normalize_role` and it is not an error that topo (that is, the engine)
  does not know it. What happens in `heal` depends on `is_structural=...`
  (D47): without it, any consumer role stays out of the graph; with
  the consumer's predicate, the roles it declares structural stay
  INSIDE the graph (they close the part's contours), the others stay out.
  The output writes it on a DXF layer named after the slug (not
  `Trash` — it is not garbage), geometry intact (D27, D30, D31, D47).
  A rule combines neutral signals — source group name, dashing,
  color — all true together; rules are ordered and the first wins
  (D63). topo gives the mechanism, the content is written by the caller: no
  vocabulary of names lives in topo. The name stays in the adapter, the `Edge`
  receives only the role. Dashing and color are the **effective** ones: a
  `ByLayer` entity inherits the style from the layer that contains it, and `DxfAdapter`
  resolves it before handing over an `EdgeStyle`, which knows no words of a
  format (D126): stroke as signed marks, color in RGB. "Dashed" means the pattern has
  at least one gap — a fact of the pattern, not of the linetype's name.
- **geometric inference**: the consumer recognizes the feature by its shape
  (`source="geometric"`, `confidence < 1.0`).

---

## What is NOT (yet) clean

Honesty about the state — details and reasons are in `MAP.md` (section
"Closed decisions"), not repeated here:

- **`topo_pdf.load_pdf`** returns `list[Edge]` instead of a `Document` → it does not
  hook into `heal()`. Frozen (MAP.md D10); the work parked in the
  `forge-pdf-adapter` worktree is resumed here (TODO, "PDF da riprendere").
- **DWG** goes through ODA File Converter, an external executable: `topo_dxf`
  calls it via `ezdxf`'s `odafc` addon.
- **`faces()` with only labeled edges** (all with a non-structural role):
  no error, an invalid `Result` with no cluster and an **empty** `loose`,
  although the `set-aside` warning says the edges went to `loose` (TODO).

The whole history of the refactors already closed (bridge/shape removed, entity→primitive
dispatcher unified, `Edge` moved from `adapters/` to
`core/topology/`, etc.) is in the decision log — see `MAP.md`.
