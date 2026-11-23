"""
topo_dxf/sanitize.py
--------------------
Fixes corrupted DXF data before any geometric processing.

This module works on raw ezdxf entities — it does not know the core. The
caller is responsible for opening the document and passing msp. The functions
work in place and print messages for each fix applied.

Public functions:
    sanitize — runs all the sanitizers in sequence
"""

from topo.precision import FLOAT_NOISE
from ezdxf import upright as _upright
from topo.model import Diagnostic

_FLATTENABLE_TYPES = frozenset({'LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'ELLIPSE'})


def normalize_ocs(msp, verbose: bool = False) -> None:
    """Normalize the extrusion vector of all the OCS entities in the modelspace.
    Converts (0,0,-1) → (0,0,1) without altering the geometry in WCS."""
    _upright.upright_all(msp)
    if verbose:
        print("[sanitize] normalize_ocs: extrusion vectors normalized")


def flatten_z(msp, verbose: bool = False) -> int:
    """Bring to 0 all the Z != 0 coordinates for LINE, ARC, CIRCLE, LWPOLYLINE and
    ELLIPSE.

    Returns the number of entities fixed — the caller decides whether to print it
    or put it in the Document's warnings channel."""
    fixed = 0
    skipped_types = set()

    for entity in msp:
        t = entity.dxftype()
        if t not in _FLATTENABLE_TYPES:
            skipped_types.add(t)
            continue

        if t == 'LINE':
            changed = False
            if entity.dxf.start.z != 0.0:
                entity.dxf.start = (entity.dxf.start.x, entity.dxf.start.y, 0.0)
                changed = True
            if entity.dxf.end.z != 0.0:
                entity.dxf.end = (entity.dxf.end.x, entity.dxf.end.y, 0.0)
                changed = True
            if changed:
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LINE Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t in ('ARC', 'CIRCLE'):
            if entity.dxf.center.z != 0.0:
                entity.dxf.center = (entity.dxf.center.x, entity.dxf.center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] {t} Z!=0 corretta su layer '{entity.dxf.layer}'")

        elif t == 'LWPOLYLINE':
            elev = entity.dxf.get('elevation', 0.0)
            if elev != 0.0:
                entity.dxf.elevation = 0.0
                fixed += 1
                if verbose:
                    print(f"  [sanitize] LWPOLYLINE elevation={elev:.3f} → 0 su layer '{entity.dxf.layer}'")

        elif t == 'ELLIPSE':
            center = entity.dxf.center
            if center.z != 0.0:
                entity.dxf.center = (center.x, center.y, 0.0)
                fixed += 1
                if verbose:
                    print(f"  [sanitize] ELLIPSE Z!=0 corretta su layer '{entity.dxf.layer}'")

    if skipped_types and verbose:
        print(f"[sanitize] flatten_z: tipi ignorati — {sorted(skipped_types)}")

    return fixed


def sanitize(msp, flatten_z_flag: bool = True, verbose: bool = False) -> int:
    """Run all the sanitizers in sequence on the received modelspace. The caller is
    responsible for opening and saving the document.

    Args:
        msp:            ezdxf modelspace
        flatten_z_flag: if True, runs flatten_z
        verbose:        if True, prints detail for every entity fixed

    Returns the number of entities with Z != 0 brought onto the plane (0 if
    flatten_z_flag is False)."""
    normalize_ocs(msp, verbose=verbose)
    if flatten_z_flag:
        return flatten_z(msp, verbose=verbose)
    return 0

def _explode_inserts(msp, sink: list = None) -> int:
    """Explode all the INSERTs (blocks) in the modelspace into primitive entities.
    Returns the number of INSERTs exploded.

    If `sink` is a list, explosion failures are added to it instead of being printed."""
    inserts = list(msp.query('INSERT'))
    if not inserts:
        return 0

    failed = []
    for insert in inserts:
        try:
            insert.explode()
        except Exception as ex:
            failed.append(str(ex))
    _explode_failed(sink, "INSERT", failed)

    return len(inserts)


def _explode_hatches(msp, sink: list = None, tolerance: float = FLOAT_NOISE) -> int:
    """Replace every pattern HATCH with the LINEs of its pattern, cut on the border,
    with the HATCH's layer/colour/linetype. A solid fill has no lines: it stays
    and ends in the warnings. Returns the HATCHes exploded.

    A border saved in pieces (open paths, sides out of order) is put back into
    closed rings with the file's sides only. `tolerance` is almost zero: inside a
    HATCH the shared ends are written equal, and the node tolerance would make a
    side as short as it ambiguous."""
    from ezdxf.render.hatching import hatch_entity

    hatches = [h for h in msp.query("HATCH") if not h.dxf.solid_fill]
    failed = []
    open_left = []
    for hatch in hatches:
        attribs = {
            k: hatch.dxf.get(k)
            for k in ("layer", "color", "linetype", "true_color")
            if hatch.dxf.hasattr(k)
        }
        try:
            rings = None
            if _boundary_in_pieces(hatch, tolerance):
                rings = _boundary_rings(hatch, tolerance)
                if rings is None:
                    open_left.append(hatch.dxf.get("pattern_name", "?"))
            if rings is None:
                # ezdxf's jiggle_origin moves the pattern origin at random: the lines must be
                # those of the file, the same at every reading
                segments = list(hatch_entity(hatch, jiggle_origin=False))
            else:
                segments = list(_pattern_lines(hatch, rings))
        except Exception as ex:
            failed.append(str(ex))
            continue
        for start, end in segments:
            msp.add_line(start, end, dxfattribs=attribs)
        msp.delete_entity(hatch)
    _explode_failed(sink, "HATCH", failed)
    if open_left and sink is not None:
        sink.append(Diagnostic(
            "dxf-hatch-open-boundary",
            f"{len(open_left)} HATCH with a boundary that does not close, each piece closed on its own chord",
            notes=[f"pattern {name}" for name in open_left[:5]]))
    return len(hatches)


def _explode_leaders(msp, sink: list = None) -> int:
    """Explode into its entities every LEADER/MULTILEADER with no string of its own:
    the leader line and the tip are geometry like an exploded block, and putting
    an arrow and the nearby letter together is a reading. Block tips come out as
    INSERTs and are exploded here. Returns the callouts exploded."""
    from .text_extractor import carries_string

    leaders = [e for e in msp.query("LEADER MULTILEADER") if not carries_string(e)]
    failed = []
    for leader in leaders:
        try:
            parts = list(leader.explode())
        except Exception as ex:
            failed.append(str(ex))
            continue
        for part in parts:
            if part.dxftype() == "INSERT":
                try:
                    part.explode()
                except Exception as ex:
                    failed.append(str(ex))
    _explode_failed(sink, "LEADER", failed)
    return len(leaders)


def _explode_fills(msp, sink: list = None) -> set:
    """Replace every filled area with its border in normal entities: SOLID and TRACE
    with their sides, a solid HATCH with the sides of its border, a polyline with
    width with the outline it draws. Returns the handles of the new entities:
    their sides are `EdgeStyle.filled`.

    The border of a HATCH comes out side by side, as it is in the file (the same
    principle as the pattern HATCH): the joins are made by topo's graph from the
    ends, and a border saved in pieces is never closed on a chord."""
    from .text_extractor import _solid_points

    filled: set = set()
    failed = []

    def attribs_of(entity, ocs=True) -> dict:
        out = {k: entity.dxf.get(k) for k in ("layer", "color", "linetype", "true_color")
               if entity.dxf.hasattr(k)}
        if ocs:
            for k in ("extrusion", "elevation"):
                if entity.dxf.hasattr(k):
                    out[k] = entity.dxf.get(k)
        return out

    def keep(entity) -> None:
        filled.add(entity.dxf.handle)

    for solid in list(msp.query("SOLID TRACE")):
        pts = _solid_points(solid)
        if len(pts) >= 3:
            attribs = attribs_of(solid)
            z = solid.dxf.vtx0[2] if solid.dxf.hasattr("vtx0") else 0.0
            attribs.pop("elevation", None)
            keep(msp.add_lwpolyline(pts, close=True, dxfattribs={**attribs, "elevation": z}))
            msp.delete_entity(solid)

    for hatch in [h for h in msp.query("HATCH") if h.dxf.solid_fill]:
        try:
            made = _hatch_boundary_entities(msp, hatch, attribs_of(hatch, ocs=False))
        except Exception as ex:
            failed.append(str(ex))
            continue
        for entity in made:
            keep(entity)
        msp.delete_entity(hatch)

    for poly in [p for p in msp.query("LWPOLYLINE POLYLINE") if _has_width(p)]:
        try:
            from ezdxf.render.trace import TraceBuilder
            ocs = poly.ocs()
            elevation = poly.dxf.get("elevation", 0.0) if poly.dxftype() == "LWPOLYLINE" else 0.0
            if hasattr(elevation, "__len__"):
                elevation = elevation[2]
            outlines = list(TraceBuilder.from_polyline(poly).polygons_wcs(ocs, elevation))
        except Exception as ex:
            failed.append(str(ex))
            continue
        attribs = attribs_of(poly, ocs=False)
        for outline in outlines:
            keep(msp.add_lwpolyline([(v.x, v.y) for v in outline], close=True, dxfattribs=attribs))
        msp.delete_entity(poly)

    _explode_failed(sink, "filled area", failed)
    return filled


def _has_width(poly) -> bool:
    """A polyline drawn with a width (constant or per vertex)."""
    if poly.dxftype() == "LWPOLYLINE":
        if (poly.dxf.get("const_width", 0) or 0) > 0:
            return True
        return any((w or 0) > 0 for *_, sw, ew, _b in poly.get_points("xyseb") for w in (sw, ew))
    if (poly.dxf.get("default_start_width", 0) or 0) > 0 or (poly.dxf.get("default_end_width", 0) or 0) > 0:
        return True
    return any((v.dxf.get("start_width", 0) or 0) > 0 or (v.dxf.get("end_width", 0) or 0) > 0
               for v in poly.vertices)


def _hatch_boundary_entities(msp, hatch, attribs: dict) -> list:
    """The sides of a HATCH border as modelspace entities, one per side: LINE, ARC,
    ELLIPSE, SPLINE; a polyline path as a closed LWPOLYLINE. Clockwise arcs and
    ellipses ezdxf already turned counter-clockwise at load: they come out exact."""
    from ezdxf.lldxf.const import BOUNDARY_PATH_TEXTBOX
    from ezdxf.math import OCS, Vec3

    extrusion = Vec3(hatch.dxf.get("extrusion", (0, 0, 1)))
    ocs = OCS(extrusion)
    elevation = Vec3(hatch.dxf.get("elevation", (0, 0, 0))).z

    def wcs(p) -> Vec3:
        return ocs.to_wcs(Vec3(p[0], p[1], elevation))

    made = []
    for path in hatch.paths.rendering_paths(hatch.dxf.hatch_style):
        if path.path_type_flags & BOUNDARY_PATH_TEXTBOX:
            continue
        if not hasattr(path, "edges"):
            points = [(v[0], v[1], v[2] if len(v) > 2 else 0.0) for v in path.vertices]
            made.append(msp.add_lwpolyline(points, format="xyb", close=True,
                                           dxfattribs={**attribs, "extrusion": extrusion,
                                                       "elevation": elevation}))
            continue
        for edge in path.edges:
            kind = edge.type.name
            if kind == "LINE":
                made.append(msp.add_line(wcs(edge.start), wcs(edge.end), dxfattribs=attribs))
            elif kind == "ARC":
                made.append(msp.add_arc(
                    (edge.center[0], edge.center[1], elevation), edge.radius,
                    edge.start_angle, edge.end_angle,
                    dxfattribs={**attribs, "extrusion": extrusion}))
            elif kind == "ELLIPSE":
                tool = edge.construction_tool()
                made.append(msp.add_ellipse(
                    wcs(tool.center), ocs.to_wcs(tool.major_axis), tool.ratio,
                    tool.start_param, tool.end_param, dxfattribs=attribs))
            elif kind == "SPLINE":
                if edge.control_points:
                    spline = msp.add_open_spline([wcs(p) for p in edge.control_points],
                                                 degree=edge.degree, knots=list(edge.knot_values),
                                                 dxfattribs=attribs)
                    if edge.weights:
                        spline.weights = list(edge.weights)
                else:
                    spline = msp.add_spline([wcs(p) for p in edge.fit_points], degree=edge.degree,
                                            dxfattribs=attribs)
                made.append(spline)
    return made


def _edge_ends(edge):
    """The two ends of a side of an EdgePath, as Vec2."""
    from ezdxf.math import Vec2
    if edge.type.name == "LINE":
        return Vec2(edge.start), Vec2(edge.end)
    return Vec2(edge.start_point), Vec2(edge.end_point)


def _boundary_in_pieces(hatch, tolerance: float) -> bool:
    """The border has an EdgePath whose sides do not go head-to-tail until they return to the first."""
    for path in hatch.paths.rendering_paths(hatch.dxf.hatch_style):
        if not hasattr(path, "edges") or not path.edges:
            continue
        ends = [_edge_ends(e) for e in path.edges]
        for (_, a), (b, _) in zip(ends, ends[1:] + ends[:1]):
            if not a.isclose(b, abs_tol=tolerance):
                return True
    return False


def _boundary_rings(hatch, tolerance: float):
    """The sides of the border of `hatch` chained into closed rings (ezdxf `Path`),
    in both directions; polyline paths stay as they are. None if a side does not
    close or an end has more than one continuation: then nothing is chosen."""
    from ezdxf.lldxf.const import BOUNDARY_PATH_TEXTBOX
    from ezdxf.path import from_hatch_boundary_path

    rings, pieces = [], []
    for path in hatch.paths.rendering_paths(hatch.dxf.hatch_style):
        if path.path_type_flags & BOUNDARY_PATH_TEXTBOX:
            continue
        if not hasattr(path, "edges"):
            rings.extend(sp for sp in from_hatch_boundary_path(path).sub_paths() if len(sp))
            continue
        pieces.extend(_edge_piece(e) for e in path.edges)

    while pieces:
        ring = pieces.pop(0)
        while not ring.start.isclose(ring.end, abs_tol=tolerance):
            nexts = [i for i, q in enumerate(pieces)
                     if ring.end.isclose(q.start, abs_tol=tolerance)
                     or ring.end.isclose(q.end, abs_tol=tolerance)]
            if len(nexts) != 1:
                return None
            q = pieces.pop(nexts[0])
            if not ring.end.isclose(q.start, abs_tol=tolerance):
                q = q.reversed()
            ring.append_path(q)
        ring.close()
        rings.append(ring)
    return rings


def _edge_piece(edge):
    """A side of an EdgePath as an open `Path`, from its start to its end."""
    from ezdxf.entities.boundary_paths import EdgePath
    from ezdxf.path import Command, Path, from_hatch_boundary_path

    if edge.type.name == "LINE":
        piece = Path(edge.start)
        piece.line_to(edge.end)
        return piece
    one = EdgePath()
    one.edges.append(edge)
    # ezdxf closes every path by returning to the start: that side is not the file's
    closed = from_hatch_boundary_path(one)
    piece = Path(closed.start)
    for cmd in list(closed.commands())[:-1]:
        if cmd.type == Command.LINE_TO:
            piece.line_to(cmd.end)
        elif cmd.type == Command.CURVE3_TO:
            piece.curve3_to(cmd.end, cmd.ctrl)
        elif cmd.type == Command.CURVE4_TO:
            piece.curve4_to(cmd.end, cmd.ctrl1, cmd.ctrl2)
    return piece


def _pattern_lines(hatch, rings):
    """The pattern lines of `hatch` inside `rings`, like `hatch_entity` (without jiggle)."""
    from ezdxf.math import Vec3
    from ezdxf.render.hatching import hatch_paths, pattern_baselines

    ocs = hatch.ocs()
    elevation = hatch.dxf.elevation.z
    for baseline in pattern_baselines(hatch, jiggle_origin=False):
        for line in hatch_paths(baseline, rings):
            for s, e in baseline.pattern_renderer(line.distance).render(line.start, line.end):
                if ocs.transform:
                    yield ocs.to_wcs((s.x, s.y, elevation)), ocs.to_wcs((e.x, e.y, elevation))
                else:
                    yield Vec3(s), Vec3(e)


def _explode_failed(sink, dxftype: str, failed: list) -> None:
    """One `Diagnostic` per type with all the failed explosions; without `sink` it prints it."""
    if not failed:
        return
    msg = Diagnostic("dxf-explode-failed", f"{len(failed)} {dxftype} could not be exploded, left out",
                     notes=failed[:5])
    if sink is not None:
        sink.append(msg)
    else:
        print(msg)


# Exact copies: two DXF entities with the same geometry are a copy, the first is
# kept. The key is computed from the native format and the comparison is the
# adapter's (an adapter uses only topo's public names).
#   extract_keyed_entities — msp → List[(key, entity)]
#   delete_entities        — deletes entities from the msp
#   deduplicate            — extract + comparison + delete → int

from typing import Any, Hashable, Iterable, List, Optional, Tuple


# --- Geometric key per DXF type ---

def _key_for(entity) -> Optional[Hashable]:
    """Return a hashable key that uniquely identifies the entity's geometry,
    independent of the DXF handle. Returns None for unhandled types or on error."""
    t     = entity.dxftype()
    layer = entity.dxf.get('layer', '0')

    try:
        if t == 'LINE':
            s   = (round(entity.dxf.start.x, 2), round(entity.dxf.start.y, 2))
            e   = (round(entity.dxf.end.x,   2), round(entity.dxf.end.y,   2))
            pts = tuple(sorted([s, e]))          # canonical order: A→B == B→A
            return (t, layer, pts)

        if t in ('LWPOLYLINE', 'POLYLINE'):
            pts = tuple(
                (round(p[0], 2), round(p[1], 2))
                for p in entity.get_points()
            )
            return (t, layer, pts)

        if t == 'CIRCLE':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius, 2))

        if t == 'ARC':
            c = entity.dxf.center
            return (t, layer,
                    round(c.x, 2), round(c.y, 2),
                    round(entity.dxf.radius,      2),
                    round(entity.dxf.start_angle, 1),
                    round(entity.dxf.end_angle,   1))

    except Exception:
        return None

    return None


# --- Public functions ---

def extract_keyed_entities(msp) -> List[Tuple[Hashable, Any]]:
    """Produce the list (key, entity) for all the msp entities. Entities of an
    unhandled type produce key=None and are ignored by _find_duplicates."""
    return [(_key_for(entity), entity) for entity in msp]


def delete_entities(refs: List[Any], msp) -> None:
    """Delete the entities from the msp in place."""
    for entity in refs:
        msp.delete_entity(entity)


def _find_duplicates(
    keyed_entities: Iterable[Tuple[Hashable, Any]],
) -> List[Any]:
    """Return the refs of the duplicate entities (second occurrence onwards).

    Parameters:
        keyed_entities : iterable of (key, ref) — the adapter produces the keys,
                         ref is opaque (the adapter knows how to delete it)

    Returns:
        List of refs to delete. The order reflects the input order."""
    seen:      set       = set()
    to_delete: List[Any] = []

    for key, ref in keyed_entities:
        if key is None:
            continue
        if key in seen:
            to_delete.append(ref)
        else:
            seen.add(key)

    return to_delete


def deduplicate(msp) -> int:
    """Shortcut: extract keys, find duplicates, delete them.

    Returns the number of entities deleted."""
    keyed    = extract_keyed_entities(msp)
    to_delete = _find_duplicates(keyed)
    delete_entities(to_delete, msp)
    return len(to_delete)