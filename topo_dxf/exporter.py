"""
topo_dxf/exporter.py
--------------------
Exports pure geometric primitives (LineSeg, CircleSeg, BSplineSeg) in DXF
format. The only file that touches ezdxf for write-back.
"""

from __future__ import annotations

from topo.precision import FLOAT_NOISE
import math
from typing import List, Optional, Tuple

from topo.primitives import (LineSeg, BSplineSeg, CircleSeg, ClothoidSeg, EllipseSeg, FormulaSeg, HyperbolaSeg, ParabolaSeg,
                             segment_endpoints)
from topo.model import EdgeStyle

_STANDARD_LINETYPES = frozenset({"BYLAYER", "BYBLOCK", "CONTINUOUS"})


# --- Raw appearance (linetype/colour) ---

def ensure_linetype(
    doc,
    name: str,
    pattern: Optional[Tuple[float, ...]] = None,
    description: str = "",
) -> Optional[str]:
    """Ensure the linetype `name` exists in `doc` and return its name; None if
    nobody can tell its shape. Order: already in the document → `pattern` given
    by the caller (captured from the source, wins) → ezdxf standard table by name.
    What to do with None is the caller's call."""
    if name.upper() in _STANDARD_LINETYPES or name in doc.linetypes:
        return name
    if pattern:
        doc.linetypes.add(name, pattern=list(pattern), description=description)
        return name
    from ezdxf.tools.standards import linetypes as standard_linetypes

    for lt_name, desc, std_pattern in standard_linetypes():
        if lt_name.upper() == name.upper():
            doc.linetypes.new(lt_name, dxfattribs={"description": desc, "pattern": std_pattern})
            return lt_name
    return None


def dxf_pattern(dash: Optional[Tuple[float, ...]]) -> Optional[Tuple[float, ...]]:
    """topo's stroke (signed marks) as the pattern of the DXF table, which opens
    with the total length."""
    if not dash:
        return None
    return (sum(abs(e) for e in dash), *dash)


def _style_attribs(doc, layer: str, style: Optional[EdgeStyle] = None) -> dict:
    """dxfattribs for an output entity: layer + the source's linetype, if known. The
    colour stays ALWAYS BYLAYER (256) — loose curves too: the colour is decided by
    the role, on the layer (the caller's map or the default of `layers.py`), never
    the source's, possibly different. Only the stroke appearance
    (continuous/dashed/...) is restored faithfully."""
    attribs = {"layer": layer, "color": 256}
    if style is None:
        return attribs

    # Unknown shape: fall back on the layer's stroke — the source did not carry it,
    # it is nobody's error.
    name = style.linetype or "BYLAYER"
    linetype = None if doc is None else ensure_linetype(
        doc, name, dxf_pattern(style.dash), style.linetype_desc or "")
    if linetype is not None and linetype.upper() != "BYLAYER":
        attribs["linetype"] = linetype

    return attribs


# --- CircleSeg → DXF bulge ---

def arc_seg_to_bulge(arc: CircleSeg) -> float:
    # The swept angle depends on the direction: for a CW arc the real stretch is
    # start_angle → end_angle walked clockwise, NOT the complement to 2π.
    # CircleSeg._sweep() is the only place of this computation — reusing it here
    # avoids an inverted arc (ccw=False, produced by segments_from_loop when the
    # loop is oriented CCW) being written with the bulge of the complementary arc,
    # that is "upside down".
    sweep = arc._sweep()
    if sweep <= 1e-12:
        sweep = 2 * math.pi
    bulge = math.tan(sweep / 4.0)
    if not arc.ccw:
        bulge = -bulge
    return bulge


def _seg_end_point(seg) -> Optional[tuple]:
    if isinstance(seg, LineSeg):
        return (seg.end[0], seg.end[1])
    if (isinstance(seg, CircleSeg) and not seg.full):
        return segment_endpoints(seg)[1]
    return None


# an end farther from the next than the double noise is a jump: the same 1e-6 mm as FLOAT_NOISE in topo, which is not public
JUMP = FLOAT_NOISE


def _joined(a, b) -> bool:
    return math.dist(a, b) <= JUMP


def _head_to_tail_runs(segments: list) -> List[list]:
    """`segments` split where one does not start exactly at the end of the previous:
    every run is a chain with no jumps."""
    runs: List[list] = []
    for seg in segments:
        if runs and _joined(segment_endpoints(runs[-1][-1])[1], segment_endpoints(seg)[0]):
            runs[-1].append(seg)
        else:
            runs.append([seg])
    return runs


def segments_to_pts_with_bulge(segments: list) -> list:
    pts = []
    for seg in segments:
        if isinstance(seg, LineSeg):
            pts.append((seg.start[0], seg.start[1], 0.0, 0.0, 0.0))
        elif (isinstance(seg, CircleSeg) and not seg.full):
            start = segment_endpoints(seg)[0]
            pts.append((start[0], start[1], 0.0, 0.0, arc_seg_to_bulge(seg)))
    return pts


# --- Write-back — the only point that touches ezdxf for closed shapes ---

def _add_spline(spline: BSplineSeg, msp, layer: str,
                 style: Optional[EdgeStyle] = None) -> object:
    """Materialize a BSplineSeg as a native SPLINE, rebuilt from the primitive
    (control points / knots / weights / degree) — not a copy of the source
    entity, the same curve re-expressed. Same treatment as the single closed spline."""
    attribs = _style_attribs(msp.doc, layer, style)
    entity = msp.add_spline(dxfattribs=attribs)
    entity.dxf.degree = int(spline.degree)

    cps3d = [(float(x), float(y), 0.0) for x, y in spline.control_points]
    entity.control_points = cps3d

    if spline.knots:
        entity.knots = [float(k) for k in spline.knots]
    if spline.weights:
        entity.weights = [float(w) for w in spline.weights]
    flags = 0
    if spline.closed:    flags |= 1
    if spline.periodic:  flags |= 2
    if spline.weights:   flags |= 4
    entity.dxf.flags = flags

    return entity


def _add_ellipse(ellipse: EllipseSeg, msp, layer: str,
                  style: Optional[EdgeStyle] = None) -> object:
    """Materialize an EllipseSeg as a native ELLIPSE — never a spline: topo does not
    convert an exact conic into an approximation (same principle as "never
    discretize a spline on output").

    In DXF an ELLIPSE is always walked CCW from `start_param` to `end_param` (no
    direction flag in the format): a CW EllipseSeg covers the same locus read CCW
    from `end_param` to `start_param` — the same swap already used for CircleSeg
    in `write_native_segments`."""
    if ellipse.ccw:
        sp, ep = ellipse.start_param, ellipse.end_param
    else:
        sp, ep = ellipse.end_param, ellipse.start_param
    attribs = _style_attribs(msp.doc, layer, style)
    return msp.add_ellipse(
        center=ellipse.center,
        major_axis=(ellipse.major_axis[0], ellipse.major_axis[1], 0.0),
        ratio=ellipse.ratio,
        start_param=sp,
        end_param=ep,
        dxfattribs=attribs,
    )


def _as_dxf(segments: List) -> List:
    """DXF has no parabolas, hyperbolas, formulas or clothoids: parabola and
    hyperbola as their exact rational quadratic spline; formula and clothoid as a
    cubic spline within SAME_POINT, approximated (`to_bspline`)."""
    return [s.to_bspline() if isinstance(s, (ParabolaSeg, HyperbolaSeg, FormulaSeg, ClothoidSeg)) else s
            for s in segments]


def write_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> Optional[object]:
    """Materialize a list of pure segments on msp.

    - CircleSeg → CIRCLE
    - EllipseSeg → native ELLIPSE
    - single BSplineSeg → native SPLINE
    - BSplineSeg mixed with lines/arcs → native SPLINEs + open LWPOLYLINEs
      sharing the endpoints (the closed loop is given by the set of entities, we
      never discretize the spline into a polyline). Returns the list of entities
      created.
    - LineSeg / CircleSeg → LWPOLYLINE (or POLYLINE2D for R12)

    `styles` (aligned to `segments`, optional) carries the source's raw linetype:
    a structural contour (outer/inner/hole) is already classified geometry, so the
    colour always stays BYLAYER (the role's semantic colour, on the layer) — only
    the linetype is restored, taken from the first segment as representative of
    the whole contour (a real cutting contour never mixes different dashings).

    Returns the entity created (or the list, for mixed contours), or None if there
    is nothing to write."""
    segments = _as_dxf(segments)
    if not segments:
        return None

    style = styles[0] if styles else None

    if len(segments) == 1 and (isinstance(segments[0], CircleSeg) and segments[0].full):
        circle = segments[0]
        return msp.add_circle(
            center=circle.center,
            radius=circle.radius,
            dxfattribs=_style_attribs(msp.doc, layer, style),
        )

    if len(segments) == 1 and isinstance(segments[0], EllipseSeg) and not isinstance(segments[0], CircleSeg):
        return _add_ellipse(segments[0], msp, layer, style)

    if len(segments) == 1 and isinstance(segments[0], BSplineSeg):
        return _add_spline(segments[0], msp, layer, style)

    if any(isinstance(s, (BSplineSeg, EllipseSeg)) and not isinstance(s, CircleSeg) for s in segments):
        # Mixed contour: no single DXF entity can hold a spline/ellipse and a polyline
        # together. It is materialized as several native entities (SPLINE/ELLIPSE + open
        # LWPOLYLINEs) with coincident endpoints — the reload graph sews the loop.
        # Never discretize.
        created = write_open_segments(segments, msp, layer, styles)
        return created or None

    runs = _head_to_tail_runs(segments)
    if len(runs) > 1 or not _joined(segment_endpoints(segments[-1])[1], segment_endpoints(segments[0])[0]):
        # a jump: closed, the polyline would draw a side over the hole and the DXF would
        # show a contour the Result does not have
        return [_add_open_run(run, msp, layer, style) for run in runs]

    pts = segments_to_pts_with_bulge(segments)
    if not pts:
        return None

    attribs = _style_attribs(msp.doc, layer, style)
    is_r12 = msp.doc is not None and msp.doc.dxfversion < "AC1015"
    if is_r12:
        pline = msp.add_polyline2d(
            [(p[0], p[1]) for p in pts],
            dxfattribs=attribs,
        )
        for vertex, pt in zip(pline.vertices, pts):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        pline.close(True)
        return pline
    else:
        return msp.add_lwpolyline(
            pts,
            format="xyseb",
            dxfattribs=attribs,
            close=True,
        )


def _add_open_run(run: list, msp, layer: str, style: Optional[EdgeStyle] = None) -> object:
    """A chain of LineSeg/CircleSeg as an open polyline: the vertices are the starts
    plus the end of the last, so every end stays where it is."""
    pts = segments_to_pts_with_bulge(run)
    end = _seg_end_point(run[-1])
    pts.append((end[0], end[1], 0.0, 0.0, 0.0))
    attribs = _style_attribs(msp.doc, layer, style)
    if msp.doc is not None and msp.doc.dxfversion < "AC1015":
        pline = msp.add_polyline2d([(p[0], p[1]) for p in pts], dxfattribs=attribs)
        for vertex, pt in zip(pline.vertices, pts):
            if pt[4] != 0.0:
                vertex.dxf.bulge = pt[4]
        return pline
    return msp.add_lwpolyline(pts, format="xyseb", dxfattribs=attribs, close=False)


# --- Write-back — engravings (engrave / marking) ---

def write_native_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> List[object]:
    """Materialize open segments as NATIVE geometry, one DXF entity per primitive —
    never LWPOLYLINE, not even for a run of contiguous lines/arcs. It is how an
    overlay element that is not a closed contour is drawn: a bend, an engraving.

      - LineSeg    → LINE
      - CircleSeg  → ARC
      - BSplineSeg → native SPLINE (never discretized)
      - CircleSeg  → CIRCLE
      - EllipseSeg → native ELLIPSE (never discretized to a spline)

    The source's linetype (`styles`, aligned to `segments`) is restored for every
    primitive. The colour stays BYLAYER.

    Returns the list of entities created."""
    segments = _as_dxf(segments)
    created: List[object] = []
    styles = styles or []

    for i, seg in enumerate(segments or []):
        style = styles[i] if i < len(styles) else None
        attribs = _style_attribs(msp.doc, layer, style)

        if isinstance(seg, LineSeg):
            created.append(msp.add_line(seg.start, seg.end, dxfattribs=attribs))
        elif (isinstance(seg, CircleSeg) and not seg.full):
            # In DXF an ARC is always walked CCW from start_angle to end_angle. A CW
            # CircleSeg covers the same locus if read CCW from end_angle to start_angle:
            # just swap the angles.
            if seg.ccw:
                sa, ea = seg.start_angle, seg.end_angle
            else:
                sa, ea = seg.end_angle, seg.start_angle
            created.append(msp.add_arc(
                center=seg.center,
                radius=seg.radius,
                start_angle=math.degrees(sa),
                end_angle=math.degrees(ea),
                dxfattribs=attribs,
            ))
        elif (isinstance(seg, CircleSeg) and seg.full):
            created.append(msp.add_circle(
                center=seg.center, radius=seg.radius, dxfattribs=attribs,
            ))
        elif isinstance(seg, EllipseSeg):
            created.append(_add_ellipse(seg, msp, layer, style))
        elif isinstance(seg, BSplineSeg):
            created.append(_add_spline(seg, msp, layer, style))

    return created


# --- Write-back — OPEN traces (loose curves, profile fragments, centerlines, ...) ---

def write_open_segments(segments: List, msp, layer: str, styles: Optional[List] = None) -> List[object]:
    """Materialize a list of pure segments as OPEN geometry on msp.

    Unlike `write_segments` it does not close the contour: it serves for the
    entities the pipeline leaves unclassified (`result.loose`), where closing the
    loop would falsify the shape, and as fallback of `write_segments` for mixed
    spline+line contours. Every segment stays faithful:

      - LineSeg / CircleSeg → an open LWPOLYLINE with bulge
      - BSplineSeg        → native SPLINE (one per spline)
      - CircleSeg        → CIRCLE
      - EllipseSeg       → native ELLIPSE

    The linetype (`styles`, aligned to `segments`) is always restored — a run of
    consecutive LineSeg/CircleSeg becomes a single LWPOLYLINE, so it takes the
    style of the run's first segment as representative. The colour always stays
    BYLAYER, loose curves included: that geometry has no classified role, but the
    red of `Trash` is still a layer decision, not a colour to restore entity by entity.

    Returns the list of entities created (empty if there is nothing to write)."""
    segments = _as_dxf(segments)
    if not segments:
        return []

    styles = styles or []
    created: List[object] = []
    poly_run: List = []
    poly_run_style: Optional[EdgeStyle] = None

    def _flush_poly_run():
        if not poly_run:
            return
        pts = segments_to_pts_with_bulge(poly_run)
        if pts:
            end = _seg_end_point(poly_run[-1])
            if end is not None:
                pts.append((end[0], end[1], 0.0, 0.0, 0.0))
            attribs = _style_attribs(msp.doc, layer, poly_run_style)
            created.append(msp.add_lwpolyline(
                pts,
                format="xyseb",
                dxfattribs=attribs,
                close=False,
            ))
        poly_run.clear()

    for i, seg in enumerate(segments):
        style = styles[i] if i < len(styles) else None
        if isinstance(seg, LineSeg) or (isinstance(seg, CircleSeg) and not seg.full):
            if poly_run and not _joined(_seg_end_point(poly_run[-1]), segment_endpoints(seg)[0]):
                _flush_poly_run()   # a jump is not covered by a vertex
            if not poly_run:
                poly_run_style = style
            poly_run.append(seg)
            continue
        _flush_poly_run()
        attribs = _style_attribs(msp.doc, layer, style)
        if (isinstance(seg, CircleSeg) and seg.full):
            created.append(msp.add_circle(
                center=seg.center, radius=seg.radius,
                dxfattribs=attribs,
            ))
        elif isinstance(seg, EllipseSeg):
            created.append(_add_ellipse(seg, msp, layer, style))
        elif isinstance(seg, BSplineSeg):
            created.append(_add_spline(seg, msp, layer, style))

    _flush_poly_run()
    return created