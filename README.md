# topo

**Deterministic 2D-geometry engine for technical drawings and CAD geometry.**

`topo` turns broken 2D geometry into a clean, lossless model — healed closed
contours, their containment hierarchy, the drawing's texts, and an open overlay
where a consumer attaches its own reading — and renders it back out. The model
is the product. **topo knows no file format**: it works on geometry and roles.
Files come in and go out through adapters, sibling packages in the same
distribution.

The distinctive part is the **healing**: curves that should meet but do not —
small gaps, doubles, overshoots, pieces drawn one by one — are reconnected into
closed contours, and nothing is silently dropped.

topo is **not a sheet-metal tool**. Sheet and plate manufacturing is where it
grew up and still its first consumer, not its boundary: the engine knows no
material, process or product. Reading a contour as "a hole to drill" or a line
as "a bend" is a consumer's interpretation (`snapbend` for sheet metal,
`snapdraw` for drawing notation), written on top through one open overlay
(`cluster.overlay`).

> Status: **alpha**. Used in production, but the API still moves. See `MAP.md` for the current design decisions.

> **Writing code against topo with an AI assistant?** Give it
> [`docs/LLM.md`](docs/LLM.md) too: every public name with its signature, in few
> tokens. This README is the overview; names outside the stable API live in
> `topo.experimental` and are always written with that prefix.

---

## Install

```bash
pip install -e .            # topo alone: geometry in, SVG / JSON / text out
pip install -e ".[dxf]"     # + topo_dxf: DXF and DWG files in, DXF out
pip install -e ".[pdf]"     # + topo_pdf: PDF in (experimental)
```

One distribution (`g-topo`), three importable packages:

| package    | what                                                          |
|------------|---------------------------------------------------------------|
| `topo`     | the engine: model, heal, the two readings, split, SVG / JSON / text |
| `topo_dxf` | file adapter: reads DXF and DWG, writes DXF. DWG needs the free [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) installed (`ODA_PATH`) |
| `topo_pdf` | file adapter: reads PDF (experimental)                        |

`topo` never imports an adapter, and an adapter uses only topo's public names —
a boundary the index check enforces (`scripts/gen_index.py --check`). What an
adapter reads and writes, and its options, are in `docs/API.md` (§9, §10).
Python ≥ 3.10.

---

## Quick start — geometry in hand

```python
import topo

fg = topo.geometry
doc = topo.load_segments(fg.rectangle(200, 100) + fg.circle(10))   # -> Document
net = topo.heal(doc)                                              # repaired once -> Network
result = net.faces()                                              # -> Result

if not result.is_valid:                          # no closed outer contour
    print(result.errors)

cluster = result.clusters[0]                     # one part: outer 200×100, one inner circle
print(cluster.outer.area, len(cluster.inners))
topo.save_json(result, "part.json")              # the model's facts
topo.experimental.save_svg(result, "part.svg")   # a picture of it
```

Builders return topo segments: `polygon(points)`, `rectangle`, `regular_polygon`,
`circle`, `ellipse`, `stadium` (with true arcs). Any other straight-sided shape is a `polygon`.

## From a file

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("part.dxf", tolerance=0.5)   # .dxf or .dwg -> Document
result = topo.heal(doc).faces()
topo_dxf.to_dxf(result, doc).saveas("part_healed.dxf")
```

After `load_dxf` everything works on the format-free `Document`; the adapter is
the only code that knows the file.

## Many parts in one drawing

```python
for part in topo.split(result):                 # one Result per part, no format
    name = part.clusters[0].label               # _P1, _P2, ... (heal(doc, label="x") gives x_P1; or namer=)
    topo.experimental.save_svg(part, f"output/{name}.svg")
```

`split` is a decision on the model: which parts (`min_area`), their names
(`namer`), which loose curves and texts travel with each (the part that
contains them, or the nearest). An adapter then writes each part in its format.

## Two readings of one healed network

`heal()` repairs the geometry once (nodes, doubles, gaps up to `max_gap`) and
returns a `Network`; a reading of it gives a `Result`.

- `faces()` reads from the inside: which loops close, which lies inside which.
  For separate flat outlines.
- `outlines()` reads from the outside: curves that touch form a group, the outer
  contour of each group is the outer face of its planar network, and every outer
  contour not inside another is a cluster with only its `outer` (what lies inside
  goes to `loose`). For a drawing of several views.

```python
result = topo.heal(doc, max_gap=0.5).outlines()
for cluster in result.clusters:              # one view (or part) per outline
    print(cluster.outer.area)
```

`max_gap` (default `tolerance`) is the widest gap closed. The readings are
recipes over public steps: `heal()`'s steps are exported one by one in
`topo.experimental` (`topo.experimental.split_labeled`,
`topo.experimental.close_free_gaps`, `topo.experimental.face_loops`,
`topo.experimental.build_hierarchy`, ...), so a consumer can compose its own
order — see `docs/API.md` (the steps of `heal()`).

## Shapes: what a contour is, not what it is for

topo names geometry, never its use. A circle is a circle; what it is for is a
consumer's reading (D68, D91).

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = topo.geometry.contour_shape(inner)     # circle / ellipse / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # circles sharing a center, smallest first (singletons included)
    for group in topo.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentric:", group.center, group.diameters)

# arcs concentric to a circle and larger: sweep, radius ratio
# (an open arc closes nothing, so it is in result.loose)
arcs = [s for c in result.loose for s in c.segments if isinstance(s, topo.primitives.ArcSeg)]
for found in topo.geometry.arcs_around((10, 20), 2.5, arcs, tolerance=0.1):
    print(found.sweep, found.radius_ratio)
```

No thresholds of meaning inside: what an arc of a given sweep means is decided
by the consumer.

---

## The pipeline

```
an adapter (a file)       ──►  Document   (edges + texts)
topo.load_segments(segs)  ──►  Document   geometry in hand
                          │
                          ▼
topo.heal(doc)  ──►  Network     repaired once: nodes, doubles, gaps
                          │
                          ▼   .faces() / .outlines()
                       Result      closed contours, outer / inner containment tree
                          │
                          ▼
  (a consumer's reading)          written to cluster.overlay
                          │
                          ▼
   topo.split(result)                       ──►  list[Result] one per part, no format
   topo.save_json(result, path)                  the model's facts as JSON
   topo.experimental.to_svg(result)         ──►  SVG string   for a UI / report (outside the 1.0 stable API, D133)
   topo.experimental.to_view_model(result)  ──►  dict (full geometry) for an external renderer (outside the 1.0 stable API)
   an adapter                               ──►  a file
```

Every renderer draws from the same model, never from the source file, so they
all show the same picture.

## What a `Result` holds

```
Result      clusters: list[Cluster]   loose: list (curves that are no cluster's contour)
            texts   is_valid   errors   warnings   notes
            reading ("faces" / "outlines")   tolerance   max_gap
            source_file   source_format   cluster_count
Cluster     outer: Contour   inners: list[Contour]   label   overlay (a consumer's reading)
            area   bbox
Contour     segments (LineSeg / ArcSeg / CircleSeg / EllipseSeg / BSplineSeg)   role
            area   bbox   centroid   points   depth   parent   contains(...)
```

Shapes are asked of the geometry, not stored: `topo.geometry.contour_shape(contour)`.
Full cards in `docs/API.md` (`Result`, `Cluster`, `Contour`).

---

## Inspecting

```python
topo.inspect_document(doc)          # what the input is: edges, primitives, node graph
topo.inspect_result(result)         # what topo made: clusters, outer/inner, overlay, loose curves
```

Everything prints to stdout. Use it when something does not come out right and
you need to see where in the chain it breaks. An adapter can add a level of its
own for the raw file (`docs/API.md`).

---

## What topo promises, and its limits

- **Faithful**: every contour lies within `tolerance` of the source geometry, both ways.
- **Complete**: every curve is a cluster's contour or in `result.loose`; nothing is
  silently dropped.
- **Deterministic**: the same input gives the same result, every run. The same
  geometry moved or rotated is *not* promised to give the same result: a yes/no
  rule on a measured number has an edge, and the rounding of a rotation can push
  a value across it. Why, for any reader: [`docs/LIMITS.md`](docs/LIMITS.md).
- A gap wider than `max_gap` is not closed: the curves stay in `loose`.
- If no closed outer contour can be formed, `result.is_valid` is `False`.
  Renderers still draw what is there, so you can see what topo understood; a
  caller feeding a machine passes `allow_invalid=False` and gets `ValueError`
  instead. `topo.split` always raises: one result per part means nothing without parts.
- **Advice is experimental.** A warning is a `topo.Diagnostic`: what happened
  (`code`, `message`), where (`points`) and why (`notes`) are stable. The call it
  suggests to fix it (`help`, `param`, `value`) is experimental: it can be wrong
  on a case it was not measured on, and it can change in a minor. Read it, judge
  it, never apply it blindly.

**Known defects of the healing**, to be fixed in 1.x — what you can meet today:

- *Near-copy warning on real corners.* A short line with both ends within
  `tolerance` of a longer one is reported as a near-copy even when the two meet
  at a real corner (45–90°); its advice then suggests a merge that would open
  the contour. The geometry itself is read right.
- *Self-crossing curve.* One curve that crosses itself is not cut at its own
  crossing: `outlines()` reads the whole ring as one contour (e.g. a square with
  a curl gives the ring's signed area, not the square plus a lobe in `loose`).
- *A node on another closed curve.* Two simple closed curves where a vertex of
  one lies exactly on the other's boundary: `outlines()` gives the first and puts
  the second in `loose`.
- *A circle drawn as many short lines with a tiny opening.* It is refitted into
  one open curve whose two ends are never treated as a gap, so it stays in
  `loose` (about 20 in 750 random cases, opening 0.02–0.03 at `tolerance` 0.1).
- *An end that overshoots by a few thousandths.* Where one curve passes another
  by ~0.003, the meeting is closed by a new short line, with a warning, instead
  of trimming the end onto the other curve.
- *A very short piece* (< 0.01) with both ends on one node is welded away, with
  a warning.
- *Merging inside `outlines()`.* It still merges nearly collinear or concentric
  pieces (within 1e-3); the readings will stop merging once a public merge
  function exists.
- *Two nearly coincident closed curves* (the same circle drawn twice, 0.05
  apart at `tolerance` 0.1) come out as two clusters, valid, with no warning.
- *Edges excluded from the graph.* With a custom `is_structural` that accepts
  every role, edges set aside as non-contour can end up in no output at all —
  an exception to *complete* above.
- *Time.* Drawings made of long chains of very short strokes cost about twice
  as much to heal; spline discretization is the largest single cost of
  `outlines()`; two large sheets of views measured over 300 s.
- *Texts linked to geometry* (`topo.experimental`) miss some links a reader
  would draw.

---

## Documentation

- **[`docs/LLM.md`](docs/LLM.md)** — a dense, token-minimal reference for an AI
  agent writing code against topo: same ground as `API.md`. Give this one to an LLM.
- **[`docs/API.md`](docs/API.md)** — every public function: signature, what it
  takes, returns, mutates, when it raises. With copyable examples. The adapters too.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — how it is built and why:
  the layers, the flow, "the model is the product".
- **[`docs/LIMITS.md`](docs/LIMITS.md)** — what topo cannot promise, and why.
- **`MAP.md`** — the design decisions, in chronological order.
- **`SCRIPTS.md`** — the numbered scripts in `scripts/`, one per stage of the pipeline.

---

## License

All rights reserved — see [`LICENSE`](LICENSE). Copyright (c) 2026 Federico
Sidraschi. This is not open source; if you'd like to try or use it, get in
touch: smia4punto6@gmail.com.
