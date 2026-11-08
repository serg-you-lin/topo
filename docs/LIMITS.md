# What topo cannot promise, and why

topo is built to read the same file the same way every time: the same bytes
in give the same result out. What it **cannot** promise is that the same *geometry* gives the same
result wherever it sits: rotated, moved far from the origin, mirrored, written
in another order. This page says why, in the simplest words we have. It is not
a defect of topo; it holds for any program that decides yes or no on a measured
number (MAP.md D215).

## 1. A yes/no rule has an edge

To repair a drawing topo has to decide, again and again, yes or no:

- is this gap small enough to close? (gap ≤ tolerance)
- are these two ends the same point? (distance ≤ a threshold)
- is this arc almost a full circle? (missing angle ≤ 2°)

Every rule like this has an edge: a number just below it says yes, a number
just above it says no. With the edge at 0.5 mm, a gap of 0.49999999999999 mm
closes and one of 0.50000000000001 mm does not.

## 2. Moving a drawing changes its numbers by a tiny amount

A computer keeps a coordinate with about 16 significant digits. It writes 0.5
exactly; but a gap is not read, it is computed from the coordinates (cosines,
sines, square roots), and every step rounds to the nearest number the computer
can write: sometimes a hair above, sometimes a hair below. On a part around
1000 mm from the origin the error is about 0.00000000000008 mm.

A gap of 0.5 mm, 1000 mm from the origin, rotated and measured again:

| rotation | the gap measures | with the edge at 0.5 |
|---|---|---|
| none | 0.5 | closes |
| 20° | 0.49999999999992 | closes |
| 45° | 0.50000000000008 | does not close |

The drawing is the same; the answer is not. (topo puts the edge a millionth of a
mm further, at 0.500001, so all three above close; but a gap that measures
exactly 0.500001 has the same problem: see section 3.)

## 3. Moving the edge does not help

"Then compare with ± 0.00000001." That moves the edge to 0.50000001 mm, and a
gap of exactly that width has the same problem. Any rule with a yes and a no
has a place where one turns into the other, and the rounding of a motion can
push a number across it. No amount of digits, and no language (C, Rust, Python
all use the same 64-bit numbers, IEEE 754), removes the edge.

The same happens when points are grouped: A is near B, B is near C, but A is
far from C. Whether the three become one point is a yes/no decision, and it has
its own edge.

## 4. What can be done: few edges, not none

How often this happens depends on how many edges there are.

- **A rounding grid has an edge everywhere.** Rounding every point to 0.001 mm
  puts an edge every thousandth of a millimetre: two ends 0.0004 mm apart fall
  in the same cell or in two neighbouring cells depending on where the drawing
  sits. This happens on ordinary drawings, all the time.
- **A distance rule has one edge per threshold.** Two ends are the same point
  when they are closer than the threshold, measured as a distance, which a
  motion does not change. The answer flips only for a value within about
  0.00000000000001 mm of the threshold. How often that happens in real
  drawings is not measured; it is never zero.

This is why topo left the grid for distance (MAP.md D216): a node is the true
point, and two ends are one node when they are close enough.

## 5. What this means for a user

- Same file, same result: this is how topo is built (no randomness, no
  dependence on hash order) and what its tests check. A file where it fails is
  a bug to report.
- Same geometry anywhere, same result: not promised. Any drawing can have a
  value at an edge, and no program can promise otherwise.
- When a decision falls at an edge the difference can be visible: a gap closed
  in one position stays open in the other, and a contour that exists in one
  reading can be missing in the other.
