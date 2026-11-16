# Texts in topo

What topo keeps of a drawing's texts, what it leaves to the consumer, and how
the DXF adapter fills the model. The field-by-field card is in `API.md`
(`Text`); the reasons are in `MAP.md` (D138, D254–D261).

## 1. What a `Text` is

A string laid in the plane, and nothing more (D257). One type for every text
(D138): whether it is a note, a dimension, a callout or a title is a reading of
whoever uses the drawing, even when the source format says so. The source's
entity type is not in the model (D256).

| field | meaning |
|---|---|
| `position` | the anchor point of the string |
| `halign`, `valign` | where `position` lies on the string: `left`/`center`/`right` × `baseline`/`bottom`/`center`/`top`. One meaning for every format; `left`/`baseline` when the source does not say (D256) |
| `text` | the string as drawn, edge spaces included: the anchor counts them (D261). A string of spaces alone is no text |
| `height`, `rotation`, `width_factor` | how the string is written |
| `role` | what it is for the consumer; topo never decides it (D127) |
| `cluster_ref` | the part that contains `position`, set by `anchor_texts` |
| `rendered` | the strokes, fills and strings the source draws together with the string (below) |

What topo does **not** keep (D259):

- what a source claims its drawing means: the measured points of a dimension,
  its measure, the polyline a callout points to, where an arrow lands;
- the text box: its size depends on a font topo does not have (D257).

Those are readings. A consumer rebuilds them from the geometry, the same way
from every format: "how far is this vertex from that one" is topo's geometry
(`topo.geometry`), "this line is a dimension line" is drawing convention
(snapdraw's).

## 2. `rendered`

`RenderedGeometry`: `strokes` (open polylines), `fills` (closed polylines),
`texts` (`RenderedText`: `content`, `position`, `height`, `rotation`,
`halign`, `valign`). It is the picture the source groups with a string, flattened
to points — for a DXF, a dimension's or a leader's own block. `to_dxf` rewrites
that picture instead of the string alone. Empty when the source does not group
anything.

A text with a picture takes `position`, `halign`/`valign`, `height` and
`rotation` from its first string, in source order (D260): `position` is where
the string reads, as for every other text, so containment and a consumer see
the same thing from every format.

`rendered` stays in the model until 1.0. In a 1.x it moves to the consumer,
with deprecation (D175): grouping strokes with a string is a reading too.

## 3. Texts and geometry

- A callout with no string of its own is geometry, not a `Text` (D258): its
  line is a curve, its arrowhead a filled area.
- A filled area (an arrowhead, a solid fill) reaches the model as its closed
  boundary with `EdgeStyle.filled` (D255), never as a text.
- A callout's string is often a separate `Text` beside the curves: joining them
  is a reading.

## 4. Linking texts to parts

```python
result = topo.heal(doc).faces()
topo.anchor_texts(result)          # sets cluster_ref on result.texts
```

`cluster_ref` is the index of the cluster whose outer contour contains
`position` (with `snap_distance` > 0, also the nearest within that distance).
`split` gives each part the texts it contains, and a text no part contains to
the nearest one: none duplicated, none lost (D124).

## 5. The DXF adapter (`topo_dxf`)

Read by `load_dxf` before the ezdxf audit, which deletes a dimension whose
block is missing:

| source | becomes |
|---|---|
| `TEXT` | one `Text`. Anchor: the insert point for left/baseline, else the alignment point (group 11); `ALIGNED`/`FIT` → center/baseline at the midpoint of the two points |
| `MTEXT` | one `Text` at its insert point; attachment 1–9 → `halign`/`valign` (MTEXT has no baseline: its bottom line is `bottom`). Formatting codes are removed, the string keeps its line breaks and spaces |
| `DIMENSION` | one `Text` with its block as `rendered`. `text` is the string shown: an override with `<>` replaced by the number the block draws (alone, or the first one inside a string such as `R5` that the override does not write itself); topo computes no number (D263). `measures`: what it measures, from the definition points, with or without a block (D264). `%%c`, `%%d`, `%%p` → `Ø`, `°`, `±`. With no block (as QCAD writes them): the file's string with `<>` left open (`R<>`, `<>`), center/center on the text midpoint (group 11), `rendered` empty, a `dxf-dimension-no-block` warning (D262, D264) |
| `LEADER`, `MULTILEADER` with a string | one `Text` with its block as `rendered` |
| `LEADER`, `MULTILEADER` without a string | exploded to curves and filled areas (D258) |
| texts inside a block | with `explode_inserts=True` (the default) they surface as texts, attributes included; with `False` the INSERT is ignored and a warning says so |

The same string at the same point is read once (texts found before and after
exploding blocks).

Written by `to_dxf`: a one-line string → `TEXT` with its alignment; more lines
→ `MTEXT` with its attachment and `\W` for the width factor; a text with a
picture → its `rendered` strokes, fills and strings; a text with a role → the
layer of its role, else `text_layer`.

## 6. Known limits

Open in `TODO.md` (homologation between adapters):

- `to_dxf` writes a non-left `TEXT` with its insert point (group 10) equal to
  its alignment point. A viewer that draws from group 10 misplaces it; the
  source's own value needs font metrics topo does not have.
- Dimension arrowheads in `rendered.fills` are written back as hollow closed
  polylines.
- An angular dimension of drw_0024 reads `90~`.
