# tests/package/test_one_threshold.py
"""Una soglia sola (D268): ogni soglia di lunghezza di topo è `SAME_POINT`,
salvo le eccezioni elencate qui, ognuna col suo perché.

Si guardano le costanti a livello di modulo con un valore numerico e i valori
di default dei parametri che sono soglie (tol, eps, gap, reach, snap, margin,
sagitta). Le guardie dell'aritmetica scritte nei confronti (`< 1e-12`) non
sono soglie del disegno e non si guardano (D196)."""

import ast
import unittest

from tests.paths import PROJECT_ROOT

PACKAGES = ("topo", "topo_dxf", "topo_pdf")
THRESHOLD_PARAM = ("tol", "eps", "gap", "reach", "snap", "margin", "sagitta")

# (file, nome): perché non è SAME_POINT
EXCEPTIONS = {
    ("topo/core/geometry/measure.py", "SAME_POINT"): "è la soglia",
    ("topo_pdf/geometry_adapter.py", "PT_TO_MM"): "conversione di unità, non una soglia",
    # aritmetica, non geometria del disegno
    ("topo/core/geometry/measure.py", "FLOAT_NOISE"): "rumore dei double, il margine di ogni soglia (D183)",
    ("topo/core/geometry/intersections.py", "_SAME_POINT"): "due radici dello stesso calcolo, rumore numerico",
    ("topo/core/topology/noding.py", "_EPS"): "guardia contro una divisione per zero",
    ("topo/core/readings/outer_scan.py", "_EPS"): "guardia contro una divisione per zero",
    ("topo/core/primitives/segments.py", "_GRID_SNAP"): "guardia numerica della discretizzazione",
    ("topo/core/geometry/points.py", "DEFAULT_DUPLICATE_TOLERANCE"): "punti uguali al rumore dei double",
    ("topo/core/geometry/lines.py", "COLLINEAR_ANGLE_TOLERANCE"): "un angolo, non una lunghezza",
    ("topo/core/base/normalizer.py", "_SAME_DIRECTION"): "un angolo (seno), non una lunghezza",
    ("topo/core/geometry/regions.py", "TANGENT_TOLERANCE"): "un angolo, non una lunghezza",
    ("topo/core/geometry/shape.py", "ANGLE_TOLERANCE_DEG"): "un angolo, non una lunghezza",
    ("topo/core/primitives/fitting.py", "DEFAULT_CORNER_TURN_DEG"): "un angolo, non una lunghezza",
    # frazioni e conteggi
    ("topo/core/geometry/shape.py", "SHAPE_TOLERANCE"): "una frazione della dimensione del contorno",
    ("topo/core/geometry/measure.py", "CIRCULAR_BBOX_ASPECT_TOLERANCE"): "un rapporto di lati",
    ("topo/core/geometry/axis.py", "SIDE_COVERAGE"): "una frazione di un lato",
    ("topo/model/style.py", "_MARK_REL_TOL"): "una frazione della lunghezza di un tratto",
    ("topo/core/readings/network.py", "_NEAR_GAP_REACH"): "un multiplo di max_gap (D227)",
    ("topo/core/base/hierarchy.py", "MIN_CONTOUR_AREA"): "un'area in mm²; da misurare (TODO, D268)",
    # discretizzazione: quanto un poligono si scosta dalla curva, non chi tocca chi
    ("topo/core/primitives/segments.py", "DEFAULT_TOLERANCE"): "sagitta dei poligoni; le decisioni si rifiniscono sulle curve (D145, D200)",
    ("topo/core/primitives/polygon_builder.py", "tolerance"): "sagitta dei poligoni",
    ("topo/core/geometry/intersections.py", "CURVE_TOLERANCE"): "sagitta per incrociare spline ed ellissi",
    ("topo/core/geometry/regions.py", "_POLYGON_TOLERANCE"): "sagitta per i test dentro/fuori",
    ("topo/io/svg.py", "tolerance"): "sagitta del disegno SVG",
    ("topo/io/view_model.py", "tolerance"): "sagitta del disegno",
    ("topo_dxf/text_extractor.py", "_ARC_SAGITTA"): "sagitta di un testo su arco",
    ("topo/core/base/normalizer.py", "tolerance"): "anello scritto a punti → cerchio (D236); da misurare (TODO, D268)",
    # scrittori e adattatori
    ("topo_dxf/exporter.py", "JUMP"): "lo scrittore mostra ogni salto del Result; quelli entro SAME_POINT li chiude già close_contour_jumps",
    ("topo_dxf/sanitize.py", "tolerance"): "bordo di un HATCH ricucito al rumore dei double (D253)",
    ("topo_pdf/loader.py", "snap_tolerance"): "adattatore PDF sperimentale, congelato (D10)",
    ("topo_pdf/sanitize.py", "snap_tolerance"): "adattatore PDF sperimentale, congelato (D10)",
    # fatti geometrici pubblici con la loro tolleranza, non misurati (TODO, D268)
    ("topo/core/geometry/lines.py", "COLLINEAR_TOLERANCE"): "default di un fatto pubblico; da misurare (TODO, D268)",
    ("topo/core/geometry/shape.py", "CONCENTRIC_TOLERANCE"): "default di un fatto pubblico; da misurare (TODO, D268)",
    ("topo/core/topology/non_contour_edges.py", "tolerance"): "da misurare (TODO, D268)",
    ("topo/core/geometry/axis.py", "AXIS_EPS"): "tratto orizzontale/verticale di un foglio; da misurare (TODO, D268)",
    ("topo/core/geometry/axis.py", "CLUSTER_TOLERANCE"): "coordinate uguali su un foglio; da misurare (TODO, D268)",
    ("topo/core/topology/outer_face.py", "DIRECTION_SAMPLE"): "dove si legge una direzione, non chi tocca chi",
}


def _is_number(node) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp):
        return _is_number(node.operand)
    if isinstance(node, ast.BinOp):
        return _is_number(node.left) and _is_number(node.right)
    return False


def _value(node) -> float:
    return eval(compile(ast.Expression(node), "<soglia>", "eval"))


def thresholds() -> list:
    """[(file, nome, valore)]: le soglie scritte come numero decimale, fuori da SAME_POINT."""
    out = []
    for package in PACKAGES:
        for path in sorted((PROJECT_ROOT / package).rglob("*.py")):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None \
                        and _is_number(node.value) and isinstance(_value(node.value), float):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    out += [(rel, t.id, _value(node.value)) for t in targets
                            if isinstance(t, ast.Name) and t.id.lstrip("_").isupper()]
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = node.args.args + node.args.kwonlyargs
                    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + node.args.defaults \
                        + node.args.kw_defaults
                    out += [(rel, arg.arg, _value(default)) for arg, default in zip(args, defaults)
                            if default is not None and _is_number(default) and _value(default) > 0
                            and any(k in arg.arg.lower() for k in THRESHOLD_PARAM)]
    return out


class TestOneThreshold(unittest.TestCase):

    def test_ogni_soglia_e_same_point_o_una_eccezione_scritta(self):
        unknown = sorted({(f, n, v) for f, n, v in thresholds() if (f, n) not in EXCEPTIONS})
        self.assertEqual(unknown, [], "\nsoglie nuove: usare topo.geometry.SAME_POINT, "
                                      "o scrivere qui l'eccezione col suo perché (D268)")

    def test_le_eccezioni_esistono_ancora(self):
        found = {(f, n) for f, n, _ in thresholds()}
        self.assertEqual(sorted(set(EXCEPTIONS) - found), [], "eccezione senza più la sua soglia: toglierla")


if __name__ == "__main__":
    unittest.main()
