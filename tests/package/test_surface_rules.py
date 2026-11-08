"""
tests/package/test_surface_rules.py

Guardiano delle regole di forma di D175 verificabili a macchina (G14 passo 3).

Regola 1 — i dati per posizione, le opzioni solo per nome (D176). Ogni
callable pubblico (funzioni, costruttori, metodi di `topo`, `topo.geometry`,
`topo.primitives`, `topo.model`, `topo_dxf`) dichiara qui i suoi parametri
posizionali, che sono tutti dati. Un nome o un parametro nuovo fa fallire il
test finché qualcuno non decide se è un dato (lo aggiunge qui) o
un'opzione (va dopo `*`). La passata di D176 si è persa tre metodi e due
funzioni perché guardava solo i parametri con default e non i metodi: questo
test li guarda tutti. `topo.experimental` è fuori dalla promessa (D175 C).
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

# i parametri posizionali di ogni callable pubblico: tutti dati. Chi non è
# qui non ne ha (o solo `self`/`cls`).
DATA = {
    'topo.load_geometry': ('entities',),
    'topo.load_segments': ('segments',),
    'topo.validate_document': ('doc',),
    'topo.validate_result': ('result',),
    'topo.heal': ('doc',),
    'topo.split': ('result',),
    'topo.inject': ('result',),
    'topo.anchor_texts': ('result',),
    'topo.pointer_target': ('result', 'text'),
    'topo.measured_references': ('result', 'text'),
    'topo.to_json': ('result',),
    'topo.save_json': ('result', 'path'),
    'topo.save_xml': ('result', 'path'),
    'topo.to_shapely': ('item',),
    'topo.build_metadata': ('cluster',),
    'topo.inspect_document': ('doc',),
    'topo.inspect_result': ('result',),
    'topo.Result': ('clusters',),
    'topo.Result.promote': ('curves', 'cluster', 'name'),
    'topo.Cluster': ('outer',),
    'topo.Cluster.features': ('name',),
    'topo.Contour': ('role', 'segments'),
    'topo.Contour.from_segments': ('segments', 'role'),
    'topo.Document': ('edges',),
    'topo.Text': ('position', 'text'),
    'topo.DetectedFeatures': ('_store',),
    'topo.Diagnostic': ('code', 'message'),
    'topo.DetectedFeatures.attach': ('name', 'items'),
    'topo.DetectedFeatures.add': ('name', 'item'),
    'topo.DetectedFeatures.get': ('name', 'default'),
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
    'topo.geometry.chord_angle_deg': ('a', 'b'),
    'topo.geometry.track_points': ('segments',),
    'topo.geometry.track_length': ('pts',),
    'topo.geometry.point_on_contour': ('segments', 'point'),
    'topo.geometry.ContourPoint': ('point', 'kind', 'segments', 'turn_deg', 'concave'),
    'topo.geometry.nearest_point': ('segments', 'point'),
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
    'topo.geometry.items_inside': ('bounds', 'items'),
    'topo.geometry.merge_intervals': ('intervals',),
    'topo.primitives.LineSeg': ('start', 'end'),
    'topo.primitives.LineSeg.rotated': ('angle',),
    'topo.primitives.LineSeg.translated': ('dx', 'dy'),
    'topo.primitives.LineSeg.scaled': ('factor',),
    'topo.primitives.ArcSeg': ('center', 'radius', 'start_angle', 'end_angle', 'ccw'),
    'topo.primitives.ArcSeg.rotated': ('angle',),
    'topo.primitives.ArcSeg.translated': ('dx', 'dy'),
    'topo.primitives.ArcSeg.scaled': ('factor',),
    'topo.primitives.ArcSeg.from_chord': ('start', 'end', 'bulge'),
    'topo.primitives.CircleSeg': ('center', 'radius'),
    'topo.primitives.CircleSeg.rotated': ('angle',),
    'topo.primitives.CircleSeg.translated': ('dx', 'dy'),
    'topo.primitives.CircleSeg.scaled': ('factor',),
    'topo.primitives.BSplineSeg': ('degree', 'control_points', 'knots', 'weights'),
    'topo.primitives.BSplineSeg.rotated': ('angle',),
    'topo.primitives.BSplineSeg.translated': ('dx', 'dy'),
    'topo.primitives.BSplineSeg.scaled': ('factor',),
    'topo.primitives.EllipseSeg': ('center', 'major_axis', 'ratio', 'start_param', 'end_param', 'ccw'),
    'topo.primitives.EllipseSeg.rotated': ('angle',),
    'topo.primitives.EllipseSeg.translated': ('dx', 'dy'),
    'topo.primitives.EllipseSeg.scaled': ('factor',),
    'topo.primitives.sub_segment': ('seg', 'a', 'b', 'via'),
    'topo.primitives.segment_endpoints': ('segment',),
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
    'topo_dxf.to_dxf': ('result', 'source_doc'),
    'topo_dxf.write_metadata_to_dxf': ('doc', 'cluster'),
    'topo_dxf.read_metadata_from_dxf': ('doc',),
    'topo_dxf.inspect_dxf': ('path',),
    'topo_dxf.inspect_file': ('path',),
    'topo_dxf.role_to_dxf_layer': ('role', 'element'),
}

# eccezioni dichiarate in D176: un'opzione per posizione per un protocollo noto
DECLARED_EXCEPTIONS = {
    ("topo.DetectedFeatures.get", "default"),   # il protocollo di dict.get
}

# un parametro con questo nome è un'opzione, sempre: rete di sicurezza per
# quando qualcuno aggiunge a DATA senza pensarci
OPTION_NAME = re.compile(r"(^|_)(tol|tolerance|distance|eps|epsilon|decimals|indent)$"
                         r"|^(min|max|include|allow|snap|keep)_")


def _positional(fn) -> tuple:
    return tuple(p.name for p in inspect.signature(fn).parameters.values()
                 if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                 and p.name not in ("self", "cls"))


def public_callables():
    """(nome, callable) per ogni funzione, classe e metodo pubblico."""
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
                for attr, value in vars(obj).items():
                    if attr.startswith("_"):
                        continue
                    fn = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
                    if inspect.isfunction(fn):
                        yield f"{key}.{attr}", fn
            elif callable(obj):
                yield key, obj


class TestOptionsByName(unittest.TestCase):
    """D175 regola 1, D176 punto 1."""

    def test_posizionali_dichiarati(self):
        wrong = []
        for key, fn in public_callables():
            got, declared = _positional(fn), DATA.get(key, ())
            if got != declared:
                wrong.append(f"{key}: posizionali {got}, dichiarati {declared}")
        self.assertEqual(wrong, [], "\n" + "\n".join(wrong))

    def test_nessun_nome_dichiarato_sparito(self):
        live = {key for key, _ in public_callables()}
        self.assertEqual(sorted(set(DATA) - live), [])

    def test_un_nome_da_opzione_non_e_un_dato(self):
        wrong = [(key, name) for key, names in DATA.items() for name in names
                 if OPTION_NAME.search(name) and (key, name) not in DECLARED_EXCEPTIONS]
        self.assertEqual(wrong, [])

    def test_eccezioni_ancora_vere(self):
        for key, name in DECLARED_EXCEPTIONS:
            self.assertIn(name, DATA.get(key, ()), key)
