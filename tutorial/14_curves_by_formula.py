"""
14_curves_by_formula.py — join two lines smoothly, and draw curves from a formula
==================================================================================

What you learn
    topo.geometry.blend(..., continuity=1)    a cubic that leaves one line and arrives on another, tangent to both
    topo.geometry.blend(..., continuity=2)    a quintic that also starts and ends with zero curvature
    topo.geometry.clothoid_corner(corner, in, out, a)   two clothoids that round a corner, curvature 0 at both ends
    topo.geometry.clothoid(a, length, ...)    the Euler spiral: curvature grows in step with the arc length
    topo.geometry.polynomial(coefficients, x_from, x_to)   the graph of y = c0 + c1·x + c2·x² + ...
    topo.geometry.involute(base_radius, end)  the path of the end of a string unwound from a circle
    segment.endpoints() / .derivative_at(t) / .t_range   what every curve answers

Two straight lines meet at a corner. Cutting the corner with an arc is tangent
(G1) but the curvature jumps from 0 to 1/r at the joint. Three smoother ways,
all joining the same two points P and Q:

    cubic blend      tangent to both lines (G1), curvature still jumps a little
    quintic blend    curvature is 0 at P and at Q too (G2)
    two clothoids    curvature 0 at P, grows linearly with the length, falls back to 0 at Q

clothoid_corner(corner, direction_in, direction_out, a) gives the two clothoids
at once. One clothoid of parameter `a` and length L turns by L² / (2a²); two of
them back to back turn by L² / a², so for a deflection D each piece is
L = a·sqrt(D) long. The chain starts on the first line and ends on the second,
both at the same distance T from the corner: T is where the lines must be cut.
`a` is your choice: a larger `a` is a gentler, longer transition.

The same lesson draws a cubic from its coefficients and an involute of a circle.

Open afterwards
    tutorial_output/14_curves_by_formula/curves.dxf: one layer per curve, turn
    them on one at a time. DXF has no clothoid nor involute: topo_dxf writes
    each as a cubic spline within 0.001 mm.

Try this
    change DEFLECTION_DEG and SPIRAL_A (try a negative deflection: the corner
    turns right), run again, and read how T and the curvature change.
"""
import _paths  # noqa: F401

import math

import topo
import topo_dxf
from topo.primitives import LineSeg

# --- CONFIG ------------------------------------------------------------------
DEFLECTION_DEG = 60.0        # how much the second line turns left of the first
SPIRAL_A = 40.0              # clothoid parameter: a² = radius · arc length
LEG = 120.0                  # length of each straight line from the corner
# -----------------------------------------------------------------------------

g = topo.geometry
deflection = math.radians(DEFLECTION_DEG)
u1 = (1.0, 0.0)                                           # direction of the first line, arriving at the corner
u2 = (math.cos(deflection), math.sin(deflection))         # direction of the second line, leaving the corner


def curvature(segment, t: float) -> float:
    """Signed curvature at parameter t, from the first derivative (central difference)."""
    lo, hi = segment.t_range
    h = (hi - lo) * 1e-5
    t = min(max(t, lo + h), hi - h)
    (x0, y0), (x1, y1), (x2, y2) = segment.derivative_at(t - h), segment.derivative_at(t), segment.derivative_at(t + h)
    ddx, ddy = (x2 - x0) / (2 * h), (y2 - y0) / (2 * h)
    return (x1 * ddy - y1 * ddx) / math.hypot(x1, y1) ** 3


# 1. the two clothoids, head to tail: they start at P on the first line and end at Q on the second
corner = (0.0, 0.0)
spiral_in, spiral_out = g.clothoid_corner(corner, u1, u2, SPIRAL_A)
P, Q = spiral_in.endpoints()[0], spiral_out.endpoints()[1]
tangent = math.dist(P, corner)                            # the same from the corner to Q
length = SPIRAL_A * math.sqrt(deflection)
print(f"clothoids: a={SPIRAL_A}, length {length:.2f} each, tangent distance T={tangent:.2f}")
print(f"  the two pieces meet within {math.dist(spiral_in.endpoints()[1], spiral_out.endpoints()[0]):.1e}")
print(f"  curvature at P {curvature(spiral_in, 0.0):.5f}, at the join {curvature(spiral_in, length):.5f} "
      f"(= length / a² = {length / SPIRAL_A ** 2:.5f})")

# 2. the same points P, Q joined by a cubic and by a quintic
cubic = g.blend(P, u1, Q, u2, continuity=1)[0]
quintic = g.blend(P, u1, Q, u2, continuity=2)[0]
for name, curve in (("cubic blend", cubic), ("quintic blend", quintic)):
    lo, hi = curve.t_range
    print(f"{name}: length {g.segment_length(curve):.2f}, curvature at P {curvature(curve, lo):.5f}, "
          f"in the middle {curvature(curve, (lo + hi) / 2):.5f}, at Q {curvature(curve, hi):.5f}")

# 3. curves from a formula
s_curve = g.polynomial((0.0, 0.0, 0.0, 1 / 400), -30.0, 30.0)[0]     # y = x³ / 400
unwound = g.involute(15.0, 2.5, center=(0.0, -80.0))[0]              # base circle r = 15, unwound up to t = 2.5 rad
print(f"y = x³/400 from -30 to 30: {type(s_curve).__name__} of degree {s_curve.degree}, length {g.segment_length(s_curve):.2f}")
print(f"involute of r=15 up to 2.5 rad: {type(unwound).__name__}, length {g.segment_length(unwound):.2f}")

# one layer per curve: roles are only layer names here
lines = [LineSeg((-LEG * u1[0], -LEG * u1[1]), P), LineSeg(Q, (LEG * u2[0], LEG * u2[1]))]
doc = topo.load_segments(lines, role="lines")
for role, curve in (("clothoids", spiral_in), ("clothoids", spiral_out), ("cubic", cubic), ("quintic", quintic),
                    ("polynomial", s_curve), ("involute", unwound)):
    doc.edges += topo.load_segments([curve], role=role).edges

result = topo.heal(doc).faces()
print(f"\nresult: valid={result.is_valid} (expected: nothing here closes a contour), "
      f"{len(result.loose)} loose curve(s), roles {sorted({c.role for c in result.loose})}")

path = _paths.out("14_curves_by_formula") / "curves.dxf"
topo_dxf.to_dxf(result).saveas(path)
print(f"written {path}")
