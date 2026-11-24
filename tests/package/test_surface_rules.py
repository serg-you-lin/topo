"""
tests/package/test_surface_rules.py

Guardian of the shape rules of the public surface that can be checked by machine.

Rule 1 — data by position, options by name only. Every public callable
(functions, constructors, methods of `topo`, `topo.geometry`,
`topo.primitives`, `topo.model`, `topo_dxf`) declares here its positional
parameters, which are all data. A new name or parameter fails the test until
someone decides whether it is data (adds it here) or an option (goes after
`*`). The earlier pass missed three methods and two functions because it only
looked at parameters with a default and not at the methods: this test looks at
all of them. `topo.experimental` is outside the promise.
"""

import enum
import inspect
import re
import unittest

import topo
import topo_dxf

MODULES = {
    "topo": topo,
    "topo.geometry": topo.geometry,
    "topo.primitives": topo.primitives,
    "topo.model": topo.model,
    "topo_dxf": topo_dxf,
}

# the positional parameters of every public callable: all data. Whoever is not
# here has none (or only `self`/`cls`).
DATA = {
    'topo.load_geometry': ('entities',),
    'topo.load_segments': ('segments',),
    'topo.validate_document': ('doc',),
    'topo.validate_result': ('result',),
    'topo.heal': ('doc',),
    'topo.split': ('result',),
    'topo.anchor_texts': ('result',),
    'topo.to_json': ('result',),
    'topo.save_json': ('result', 'path'),
    'topo.to_shapely': ('item',),
    'topo.inspect_document': ('doc',),
    'topo.inspect_result': ('result',),
    'topo.Result': ('clusters',),
    'topo.Result.promote': ('curves', 'cluster', 'name'),
    'topo.Cluster': ('outer',),
    'topo.Cluster.features': ('name',),
    'topo.Contour': ('role', 'segments'),
    'topo.Contour.from_segments': ('segments', 'role'),
    'topo.Contour.contains': ('point',),
    'topo.Document': ('edges',),
    'topo.Text': ('position', 'text'),
    'topo.MeasuredDistance': ('first', 'second', 'line_at', 'direction'),
    'topo.MeasuredRadius': ('center', 'on_circle'),
    'topo.MeasuredDiameter': ('on_circle', 'opposite'),
    'topo.MeasuredAngle': ('first_leg', 'second_leg', 'arc_at'),
    'topo.Overlay': ('_store',),
    'topo.Diagnostic': ('code', 'message'),
    'topo.Overlay.attach': ('name', 'items'),
    'topo.Overlay.add': ('name', 'item'),
    'topo.Overlay.get': ('name', 'default'),
    'topo.normalize_role': ('value',),
    'topo.is_structural_role': ('role',),
    'topo.RoleRule': ('role',),
    'topo.RoleRule.matches': ('name',),
    'topo.name_rules': ('mapping',),
    'topo.non_contour_candidates': ('doc',),
    'topo.geometry.polygon': ('points',),
    'topo.geometry.rectangle': ('length', 'width'),
    'topo.geometry.regular_polygon': ('sides', 'radius'),
    'topo.geometry.circle': ('radius',),
    'topo.geometry.ellipse': ('length', 'width'),
    'topo.geometry.stadium': ('length', 'width'),
    'topo.geometry.contour_shape': ('item',),
    'topo.geometry.ContourShape': ('kind', 'center', 'length', 'width', 'angle', 'sides'),
    'topo.geometry.concentric_groups': ('items',),
    'topo.geometry.ConcentricGroup': ('center', 'items', 'shapes'),
    'topo.geometry.arcs_around': ('center', 'radius', 'arcs'),
    'topo.geometry.ArcAround': ('arc', 'sweep', 'radius_ratio'),
    'topo.geometry.splits_contour': ('contour', 'start', 'end'),
    'topo.geometry.bridged_runs': ('segments', 'bridges'),
    'topo.geometry.CollinearRun': ('start', 'end', 'members'),
    'topo.geometry.dash_line': ('start', 'end', 'head', 'tail'),
    'topo.geometry.group_collinear_lines': ('lines',),
    'topo.geometry.segment_length': ('segment',),
    'topo.geometry.length_inside': ('segment', 'bounds'),
    'topo.geometry.track_points': ('segments',),
    'topo.geometry.point_on_contour': ('segments', 'point'),
    'topo.geometry.ContourPoint': ('point', 'kind', 'segments', 'turn_deg', 'concave'),
    'topo.geometry.nearest_point': ('segments', 'point'),
    'topo.geometry.gap': ('a', 'b'),
    'topo.geometry.Gap': ('distance', 'on_a', 'on_b'),
    'topo.geometry.cut_by': ('segment', 'region'),
    'topo.geometry.contour_minus': ('contour', 'region'),
    'topo.geometry.contour_union': ('contour', 'other'),
    'topo.geometry.intersections': ('a', 'b'),
    'topo.geometry.covered_rectangles': ('items',),
    'topo.geometry.CoveredRectangle': ('bbox', 'items'),
    'topo.geometry.spanning_lines': ('bounds', 'items'),
    'topo.geometry.sides_on_border': ('bounds', 'border'),
    'topo.geometry.axis_aligned_share': ('segments',),
    'topo.geometry.axis_lines': ('items',),
    'topo.geometry.AxisLine': ('item', 'lo', 'hi', 'at'),
    'topo.primitives.MathSeg.point_at': ('t',),
    'topo.primitives.MathSeg.derivative_at': ('t',),
    'topo.primitives.MathSeg.rotated': ('angle',),
    'topo.primitives.MathSeg.translated': ('dx', 'dy'),
    'topo.primitives.MathSeg.scaled': ('factor',),
    'topo.primitives.LineSeg.point_at': ('t',),
    'topo.primitives.LineSeg.derivative_at': ('t',),
    'topo.primitives.CircleSeg.point_at': ('t',),
    'topo.primitives.CircleSeg.derivative_at': ('t',),
    'topo.primitives.BSplineSeg.point_at': ('t',),
    'topo.primitives.BSplineSeg.derivative_at': ('t',),
    'topo.primitives.EllipseSeg.point_at': ('t',),
    'topo.primitives.EllipseSeg.derivative_at': ('t',),
    'topo.primitives.ParabolaSeg': ('vertex', 'focus', 'start_param', 'end_param'),
    'topo.primitives.HyperbolaSeg': ('center', 'major_axis', 'ratio', 'start_param', 'end_param'),
    'topo.primitives.ParabolaSeg.point_at': ('t',),
    'topo.primitives.ParabolaSeg.derivative_at': ('t',),
    'topo.primitives.ParabolaSeg.rotated': ('angle',),
    'topo.primitives.ParabolaSeg.translated': ('dx', 'dy'),
    'topo.primitives.ParabolaSeg.scaled': ('factor',),
    'topo.primitives.HyperbolaSeg.point_at': ('t',),
    'topo.primitives.HyperbolaSeg.derivative_at': ('t',),
    'topo.primitives.HyperbolaSeg.rotated': ('angle',),
    'topo.primitives.HyperbolaSeg.translated': ('dx', 'dy'),
    'topo.primitives.HyperbolaSeg.scaled': ('factor',),
    'topo.primitives.FormulaSeg': ('x', 'y', 'start_param', 'end_param'),
    'topo.primitives.FormulaSeg.point_at': ('t',),
    'topo.primitives.FormulaSeg.derivative_at': ('t',),
    'topo.primitives.FormulaSeg.rotated': ('angle',),
    'topo.primitives.FormulaSeg.translated': ('dx', 'dy'),
    'topo.primitives.FormulaSeg.scaled': ('factor',),
    'topo.primitives.ClothoidSeg': ('origin', 'angle', 'a', 'start_param', 'end_param'),
    'topo.primitives.ClothoidSeg.point_at': ('t',),
    'topo.primitives.ClothoidSeg.derivative_at': ('t',),
    'topo.primitives.ClothoidSeg.curvature_at': ('t',),
    'topo.primitives.ClothoidSeg.rotated': ('angle',),
    'topo.primitives.ClothoidSeg.translated': ('dx', 'dy'),
    'topo.primitives.ClothoidSeg.scaled': ('factor',),
    'topo.geometry.triangle': ('a', 'b', 'c'),
    'topo.geometry.right_triangle': ('leg_a', 'leg_b'),
    'topo.geometry.blend': ('start', 'start_direction', 'end', 'end_direction'),
    'topo.geometry.polynomial': ('coefficients', 'x_from', 'x_to'),
    'topo.geometry.involute': ('base_radius', 'end'),
    'topo.geometry.clothoid': ('a', 'length'),
    'topo.primitives.LineSeg': ('start', 'end'),
    'topo.primitives.LineSeg.rotated': ('angle',),
    'topo.primitives.LineSeg.translated': ('dx', 'dy'),
    'topo.primitives.LineSeg.scaled': ('factor',),
    'topo.primitives.CircleSeg': ('center', 'radius', 'start_angle', 'end_angle', 'ccw'),
    'topo.primitives.CircleSeg.rotated': ('angle',),
    'topo.primitives.CircleSeg.translated': ('dx', 'dy'),
    'topo.primitives.CircleSeg.scaled': ('factor',),
    'topo.primitives.CircleSeg.from_ends': ('start', 'end', 'sweep'),
    'topo.primitives.BSplineSeg': ('degree', 'control_points', 'knots', 'weights'),
    'topo.primitives.BSplineSeg.rotated': ('angle',),
    'topo.primitives.BSplineSeg.translated': ('dx', 'dy'),
    'topo.primitives.BSplineSeg.scaled': ('factor',),
    'topo.primitives.EllipseSeg': ('center', 'major_axis', 'ratio', 'start_param', 'end_param', 'ccw'),
    'topo.primitives.EllipseSeg.rotated': ('angle',),
    'topo.primitives.EllipseSeg.translated': ('dx', 'dy'),
    'topo.primitives.EllipseSeg.scaled': ('factor',),
    'topo.primitives.sub_segment': ('seg', 'a', 'b', 'via'),
    'topo.model.RenderedText': ('content', 'position'),
    'topo.model.Curve': ('role',),
    'topo.model.ClosedCurve': ('role', 'segments'),
    'topo.model.ClosedCurve.contains': ('point',),
    'topo.model.OpenCurve': ('role', 'segments'),
    'topo.model.role_style': ('role',),
    'topo.model.feature_closed': ('contour', 'item'),
    'topo.model.role_str': ('role',),
    'topo.model.feature_role': ('contour', 'item_role'),
    'topo.model.resolve_role': ('rules', 'name', 'style'),
    'topo.model.Edge': ('role', 'start', 'end', 'segment'),
    'topo.model.Edge.of': ('segment', 'role'),
    'topo_dxf.load_dxf': ('path',),
    'topo_dxf.document_from_msp': ('msp',),
    'topo_dxf.to_dxf': ('result',),
    'topo_dxf.inspect_dxf': ('path',),
    'topo_dxf.inspect_file': ('path',),
    'topo_dxf.role_to_dxf_layer': ('role', 'element'),
}

# declared exceptions: an option by position for a known protocol
DECLARED_EXCEPTIONS = {
    ("topo.Overlay.get", "default"),   # the dict.get protocol
    ("topo.geometry.Gap", "distance"),  # a field of the result of gap(), not an option
}

# a parameter with this name is an option, always: a safety net for when
# someone adds to DATA without thinking
OPTION_NAME = re.compile(r"(^|_)(tol|tolerance|distance|eps|epsilon|decimals|indent)$"
                         r"|^(min|max|include|allow|snap|keep)_")


def _positional(fn) -> tuple:
    return tuple(p.name for p in inspect.signature(fn).parameters.values()
                 if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                 and p.name not in ("self", "cls"))


def public_callables():
    """(name, callable) for every public function, class and method."""
    seen = set()
    for prefix, module in MODULES.items():
        for name in module.__all__:
            obj = getattr(module, name)
            if inspect.ismodule(obj) or id(obj) in seen:
                continue
            if not getattr(obj, "__module__", "").startswith(("topo", "topo_dxf")):
                continue
            seen.add(id(obj))
            key = f"{prefix}.{name}"
            if inspect.isclass(obj):
                if issubclass(obj, enum.Enum):
                    continue
                yield key, obj
                # what a public class takes from a private base is part of its own surface
                own = {}
                for base in reversed(obj.__mro__):
                    if base is obj or base.__name__.startswith("_"):
                        own.update(vars(base))
                for attr, value in own.items():
                    if attr.startswith("_"):
                        continue
                    fn = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
                    if inspect.isfunction(fn):
                        yield f"{key}.{attr}", fn
            elif callable(obj):
                yield key, obj


class TestOptionsByName(unittest.TestCase):
    """Rule 1."""

    def test_declared_positionals(self):
        wrong = []
        for key, fn in public_callables():
            got, declared = _positional(fn), DATA.get(key, ())
            if got != declared:
                wrong.append(f"{key}: positionals {got}, declared {declared}")
        self.assertEqual(wrong, [], "\n" + "\n".join(wrong))

    def test_no_declared_name_vanished(self):
        live = {key for key, _ in public_callables()}
        self.assertEqual(sorted(set(DATA) - live), [])

    def test_an_option_name_is_not_data(self):
        wrong = [(key, name) for key, names in DATA.items() for name in names
                 if OPTION_NAME.search(name) and (key, name) not in DECLARED_EXCEPTIONS]
        self.assertEqual(wrong, [])

    def test_exceptions_still_true(self):
        for key, name in DECLARED_EXCEPTIONS:
            self.assertIn(name, DATA.get(key, ()), key)
