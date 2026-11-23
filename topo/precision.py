"""
topo/precision.py
-----------------
Every fixed threshold of topo, in one place. Nothing else in the
package writes a threshold as a number: it imports it from here
(`tests/package/test_one_threshold.py` checks it). The values cannot be
reassigned: `topo.precision.SAME_POINT = 0.1` raises `AttributeError`.
A caller that needs another value for one operation passes it explicitly
(for gaps: `heal(doc, max_gap=...)`).

All lengths are millimetres.
"""

import sys
import types

# ---------------------------------------------------------------------------
# La soglia
# ---------------------------------------------------------------------------

# Two points closer than this are the same point: nodes, contacts, same
# line/circle, degenerate side, jumps in a contour, spline cutting. CHANGING IT
# changes the readings: larger, ends and curves up to that far apart become a
# single point (contours that close, short sides that vanish); smaller, ends
# written with few decimals stay detached (open contours without max_gap) and
# splines are cut finer (slower). Measured on the 631 drawings of tests/: below
# 0.001 the contacts on splines, today computed on their discretization, break
# the contours.
SAME_POINT = 1e-3
# It is also the sagitta of every curve's polygon: computation, drawing, texts.

# Arithmetic: the noise of the computations, not the drawing

# double noise: the margin of every threshold ("within" includes it); above that
# of a motion (~1e-11), below every contact threshold
FLOAT_NOISE = 1e-6

# Angles: not lengths

NEAR_FULL_ARC_MISSING_DEG = 2.0  # degrees: an arc missing more than this is not a circle
NEAR_FULL_ARC_HINT_DEG = 8.0     # degrees: up to here heal() warns that little is missing; a thread (~90°) never
ANGLE_BRACKET_DEG = 1.0        # degrees: around the angle found, the minimum-area box is searched (contour_shape)

# Fractions and ratios: not lengths

MARK_FRACTION = 0.05           # of the length of a stretch of dashed line
NEAR_GAP_FACTOR = 2.0          # a hole up to this multiple of max_gap "is nearly there"

# How a CAD writes a curve as points, and the PDF adapter

POINTS_NOISE = 0.02            # mm: how much the points of a curve written as points can be off (refit and rings): an assumption about the files, measured on regr_01, not derived
TESSELLATION_SIDE = 0.1        # mm: shorter sides may be points of a curve written as points (refit_tessellations)
TESSELLATION_RUN = 10          # short sides in a row: from this many up they are a curve written as points; below, the refit rounds corners
PDF_SNAP = 0.15                # mm: adattatore PDF sperimentale, congelato


class _Frozen(types.ModuleType):
    """The module is not reassigned: a threshold is changed only here, with a decision."""

    def __setattr__(self, name, value):
        raise AttributeError(f"topo.precision.{name} is fixed; pass a value to the call instead")

    def __delattr__(self, name):
        raise AttributeError(f"topo.precision.{name} is fixed")


sys.modules[__name__].__class__ = _Frozen
