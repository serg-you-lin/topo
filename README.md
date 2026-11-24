# topo

**Deterministic 2D geometry engine: it repairs vector geometry and reads its structure — closed contours, what lies inside what, what is connected.**

Vector geometry rarely arrives clean. Curves that should meet stop a hair short
or run past each other, the same curve comes twice, a circle arrives as fifty
short segments. Before you can ask *what is the area of this shape* or *which
shape lies inside which*, the curves have to be stitched back together.

`topo` does that. It **heals** a set of curves — reconnects them into closed
contours, and nothing is silently dropped — then tells you their structure:
which contours close, which lies inside which, what is connected to what. Same
input, same answer, every run.

The result is a clean, lossless model: healed contours, their containment
hierarchy, the texts that came with the geometry, and an open overlay where your
code attaches its own meaning. It renders out to JSON or SVG, and back to the
source format through an adapter. **topo knows no file format and no trade**: it
works on curves, whatever produced them — a file, another library, your own
code. Adapters for files ship in the same distribution; today DXF/DWG in, DXF out.

topo was born reading technical drawings, and CAD files are still its largest
test corpus; the engine itself knows only curves, contours and containment.

> **Status: pre-1.0.** The public API is being frozen for 1.0. From 1.0 on,
> public names do not break: a change arrives as a new form, the old one keeps
> working with a `FutureWarning` for two minor versions, then goes.
> `topo.experimental` and the PDF adapter carry no such promise.

> **Writing code against topo with an AI assistant?** Give it
> [`docs/LLM.md`](docs/LLM.md) too: every public name with its signature, in few
> tokens. This README is the overview; names outside the stable API live in
> `topo.experimental` and are always written with that prefix.

---

## Install

```bash
pip install g-topo              # topo alone: geometry in, SVG / JSON out
pip install "g-topo[dxf]"       # + topo_dxf: DXF and DWG files in, DXF out
pip install "g-topo[pdf]"       # + topo_pdf: PDF in (experimental; PyMuPDF is AGPL, see License)
```

Python ≥ 3.10. To work on topo itself: clone the repository and
`pip install -e ".[dev]"`.

One distribution (`g-topo`), three importable packages:

| package    | what                                                          |
|------------|---------------------------------------------------------------|
| `topo`     | the engine: model, heal, the two readings, split, SVG / JSON / text |
| `topo_dxf` | file adapter: reads DXF and DWG, writes DXF. DWG needs the free [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) installed (`ODA_PATH`) |
| `topo_pdf` | file adapter: reads PDF (experimental)                        |

`topo` never imports an adapter, and an adapter uses only topo's public names —
a boundary the index check enforces (`scripts/gen_index.py --check`). What an
adapter reads and writes, and its options, are in `docs/API.md` (§9, §10).

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

cluster = result.clusters[0]                     # outer 200×100 with one circle inside
print(cluster.outer.area, len(cluster.inners))
topo.save_json(result, "shape.json")             # the model's facts
topo.experimental.save_svg(result, "shape.svg")  # a picture of it
```

Builders return topo segments: `polygon(points)`, `rectangle`, `regular_polygon`,
`circle`, `ellipse`, `stadium` (with true arcs). Any other straight-sided shape is a `polygon`.

## From a file

```python
import topo, topo_dxf

doc = topo_dxf.load_dxf("input.dxf")                 # .dxf or .dwg -> Document
result = topo.heal(doc, max_gap=0.5).faces()      # close gaps up to 0.5 mm
topo_dxf.to_dxf(result, doc).saveas("input_healed.dxf")
```

After `load_dxf` everything works on the format-free `Document`; the adapter is
the only code that knows the file.

## Many separate shapes in one input

A cluster is one outer contour with everything inside it. `split` gives each
cluster a `Result` of its own:

```python
for piece in topo.split(result):                # one Result per cluster, no format
    name = piece.clusters[0].label              # _P1, _P2, ... (heal(doc, label="x") gives x_P1; or namer=)
    topo.experimental.save_svg(piece, f"output/{name}.svg")
```

`split` is a decision on the model: which clusters (`min_area`), their names
(`namer`), which loose curves and texts travel with each (the cluster that
contains them, or the nearest). An adapter then writes each one in its format.

## Two readings of one healed network

`heal()` repairs the geometry once (nodes, doubles, gaps up to `max_gap`) and
returns a `Network`; a reading of it gives a `Result`.

- `faces()` reads from the inside: which loops close, which lies inside which.
  Each cluster is an outer contour with the contours nested in it.
- `outlines()` reads from the outside: curves that touch form a group, the outer
  contour of each group is the outer face of its planar network, and every outer
  contour not inside another is a cluster with only its `outer` (what lies inside
  goes to `loose`). Each cluster is the silhouette of one connected figure.
  Tuned today on drawings that show several views of one object.

These are the two readings built so far; others can be composed from the same
healed network (below).

```python
result = topo.heal(doc, max_gap=0.5).outlines()
for cluster in result.clusters:              # one connected figure per outline
    print(cluster.outer.area)
```

`max_gap` is the widest gap closed; without it no gap is closed, and every gap closed is listed in `notes`. The readings are
recipes over public steps: `heal()`'s steps are exported one by one in
`topo.experimental` (`topo.experimental.split_labeled`,
`topo.experimental.close_free_gaps`, `topo.experimental.face_loops`,
`topo.experimental.build_hierarchy`, ...), so a consumer can compose its own
order — see `docs/API.md` (the steps of `heal()`).

## Shapes: what a contour is, not what it is for

topo names geometry, never its use. A circle is a circle; what it is for is a
consumer's reading.

```python
for cluster in result.clusters:
    for inner in cluster.inners:
        shape = topo.geometry.contour_shape(inner)     # circle / ellipse / stadium / rectangle / polygon / other
        print(shape.kind, shape.center, shape.length, shape.width)

    # circles sharing a center, smallest first (singletons included)
    for group in topo.geometry.concentric_groups(cluster.inners, tolerance=0.1):
        if len(group.items) > 1:
            print("concentric:", group.center, group.diameters)
```

No thresholds of meaning inside: what a shape means is decided by your code.
More geometric facts (gaps, nearest points, arcs around a center, intersections, …) are in
`topo.geometry`, listed in `docs/API.md`.

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
   topo.split(result)                       ──►  list[Result] one per cluster, no format
   topo.save_json(result, path)                  the model's facts as JSON
   topo.experimental.to_svg(result)         ──►  SVG string   for a UI / report (outside the 1.0 stable API)
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
Contour     segments (LineSeg / CircleSeg / EllipseSeg / BSplineSeg)   role
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

- **Millimetres**: every length, threshold and area is in mm. topo does not read the unit a file
  declares (it is often wrong): scale geometry in other units to mm before reading it.
- **Faithful**: every contour lies within `SAME_POINT` (0.001 mm) of the source
  geometry, both ways; where a gap was closed, within `max_gap`.
- **Complete**: every curve is a cluster's contour or in `result.loose`; nothing is
  silently dropped.
- **Deterministic**: the same input gives the same result, every run. The same
  geometry moved or rotated is *not* promised to give the same result: a yes/no
  rule on a measured number has an edge, and the rounding of a rotation can push
  a value across it. Why, for any reader: [`docs/LIMITS.md`](docs/LIMITS.md).
- A gap wider than `max_gap` is not closed: the curves stay in `loose`.
- If no closed outer contour can be formed, `result.is_valid` is `False`.
  Renderers still draw what is there, so you can see what topo understood; a
  caller that hands the output to other software passes `allow_invalid=False` and gets `ValueError`
  instead. `topo.split` always raises: one result per cluster means nothing without clusters.
- **Advice is experimental.** A warning is a `topo.Diagnostic`: what happened
  (`code`, `message`), where (`points`) and why (`notes`) are stable. The call it
  suggests to fix it (`help`, `param`, `value`) is experimental: it can be wrong
  on a case it was not measured on, and it can change in a minor. Read it, judge
  it, never apply it blindly.

**Known defects of the healing** — a wrong result you can meet today, to be
fixed in 1.x. Each was reproduced on the current code.

- *Self-crossing curve.* One curve that crosses itself is not cut at its own
  crossing: both readings return the whole ring as one contour (a square with a
  curl gives the ring's signed area, not the square plus a lobe in `loose`).
  The warning `self-crossing` says so.
- *A node on another closed curve.* Two simple closed curves where a vertex of
  one lies exactly on the other's boundary: `outlines()` gives the first and puts
  the second in `loose`; the warning `closed-touch` says so.
- *A circle drawn as many short lines with a tiny opening.* It is refitted into
  one open curve whose two ends are never treated as a gap, so it stays in
  `loose` instead of closing (about 6% of such rings in a random sample); the
  note `open-spline` reports it.
- *A curve written as points loses details under 0.02 mm.* Ten or more short
  lines in a row are refitted into lines, arcs, conics and splines within
  0.02 mm of their points; a corner or a hook smaller than that, even on
  exact points, can come out smoothed.
- *Edges excluded from the graph.* With a custom `is_structural` that accepts
  every role, `faces()` can deliver edges set aside as non-contour nowhere at
  all (no cluster, nothing in `loose`) — an exception to *complete* above. The
  warning `non-contour` counts them; `outlines()` delivers them.
- *Near-copy advice on real corners.* A short line with both ends within
  `SAME_POINT` of a longer one is reported as a near-copy even where the two meet
  at a real corner (45–90°), and its advice suggests a merge that would open the
  contour. The geometry is read right; only the advice is wrong.

**Behaviour by design**, worth knowing:

- *One threshold.* Two points closer than `topo.precision.SAME_POINT` (0.001 mm)
  are one point, everywhere in topo. Below 0.001 the contacts on splines still
  break contours: geometry whose points coincide only more coarsely needs `max_gap`.
- *Tiny pieces are welded.* A group of strokes within `SAME_POINT` is welded onto one
  node (note `welded`): a piece shorter than that cannot be told from a node.
- *A jump is closed, never moved.* Where one curve passes another by a few
  thousandths, the reading adds a short straight segment between the two ends
  (note `gap-closed`) instead of moving either curve: the input's own curves
  stay as they came. Trimming the end along itself onto the other curve, as at a
  crossing, is planned for 1.x.
- *`outlines()` joins pieces that continue each other* (collinear or on one
  circle, within 1e-3) into one curve; `faces()` keeps every piece as drawn.
  Both stay within `SAME_POINT` of the source.
- *Two closed curves that cross* (the same circle drawn twice, 0.05 apart) are
  two clusters and the result stays valid, with the warning `crossing`.
  Whether crossing contours should make a result invalid is not decided yet.

**Cost and experimental parts**

- Drawings made of long chains of very short strokes cost about twice as much
  to heal; spline discretization is the largest single cost of `outlines()`;
  two of the largest files in the test corpus measured over 300 s.
- Texts linked to geometry (`topo.experimental`) miss some links a reader would draw.

---

## Documentation

- **[`docs/LLM.md`](docs/LLM.md)** — a dense, token-minimal reference for an AI
  agent writing code against topo: same ground as `API.md`. Give this one to an LLM.
- **[`docs/API.md`](docs/API.md)** — every public function: signature, what it
  takes, returns, mutates, when it raises. With copyable examples. The adapters too.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — how it is built and why:
  the layers, the flow, "the model is the product".
- **[`docs/LIMITS.md`](docs/LIMITS.md)** — what topo cannot promise, and why.
- **[`tutorial/`](tutorial/README.md)** — numbered lessons, from a shape built in code to a folder of your own files.
- **`SCRIPTS.md`** — the maintenance tools in `scripts/`.

---

## License

[Apache License 2.0](LICENSE) — free to use, modify and distribute, in open or
closed software, commercial use included. Copyright 2026 Federico Sidraschi
(see [`NOTICE`](NOTICE)).

The optional PDF adapter (`g-topo[pdf]`) depends on PyMuPDF, which is licensed
under the AGPL-3.0 (or a commercial license from Artifex): installing that extra
brings its terms into your program. topo itself and the DXF adapter do not.

Questions, ideas, or using topo in your work: smia4punto6@gmail.com.
