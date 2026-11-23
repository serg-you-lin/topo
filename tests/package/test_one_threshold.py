# tests/package/test_one_threshold.py
"""Every fixed topo threshold is in `topo/precision.py` and is not reassigned.

The module-level constants with a numeric value are checked (even an
expression like `math.radians(2.0)`) and the decimal default values of the
parameters that are thresholds (`THRESHOLD_PARAM`: tol, gap, segment, angle,
…); and the integers that are counts (`COUNT_NAME`: samples, steps, depth,
minimum sides, …), constants or defaults, from 2 up. The names of `precision`
are a fixed list: adding or removing one is a decision (MAP), not a side
effect. The arithmetic guards written in comparisons (`< 1e-12`) are not
drawing thresholds and are not checked."""

import ast
import math
import unittest

from tests.paths import PROJECT_ROOT

PACKAGES = ("topo", "topo_dxf", "topo_pdf")
THRESHOLD_PARAM = ("tol", "eps", "gap", "reach", "snap", "margin", "sagitta", "segment", "angle",
                   "distance", "dist", "length", "radius", "area", "step", "ratio", "fraction",
                   "factor", "width", "limit", "threshold")
COUNT_NAME = ("samples", "steps", "depth", "terms", "pieces", "segments", "sides", "iter", "run", "start")

# the names of topo/precision.py
PRECISION_NAMES = {
    "ANGLE_BRACKET_DEG", "FLOAT_NOISE", "MARK_FRACTION",
    "NEAR_FULL_ARC_HINT_DEG", "NEAR_FULL_ARC_MISSING_DEG", "NEAR_GAP_FACTOR",
    "PDF_SNAP", "POINTS_NOISE", "SAME_POINT", "TESSELLATION_RUN", "TESSELLATION_SIDE",
}

# (file, name): numbers that are not thresholds, with the why
NOT_THRESHOLDS = {
    ("topo_pdf/geometry_adapter.py", "PT_TO_MM"): "conversione di unità",
    ("topo/core/primitives/clothoid.py", "_SERIES_UP_TO"):
        "dove Fresnel passa dalla serie alla frazione continua: esatte tutte e due, cambia solo la velocità (D290)",
    ("topo/core/topology/matching.py", "start"):
        "coppie vicine da cui parte l'accoppiamento: le escluse si aggiungono dopo, il risultato è esatto, cambia la velocità",
    ("topo_pdf/geometry_adapter.py", "num_segments"): "adattatore PDF sperimentale, congelato (D10)",
    ("topo/core/primitives/formula.py", "_INITIAL_PIECES"): "poligono adattivo di FormulaSeg, non per dimostrazione (D289)",
}

# caps of a converging method: the precision is given by the method, the cap only stops a case that does not converge
CONVERGENCE = {
    ("topo/core/primitives/trim.py", "_REFINE_STEPS"): "ricerca ternaria: (2/3)^60 ≈ 3e-11 della forchetta",
    ("topo/core/geometry/regions.py", "_ONTO_STEPS"): "Newton, si ferma prima a FLOAT_NOISE",
    ("topo/core/primitives/clothoid.py", "_MAX_TERMS"): "serie di Fresnel, si ferma prima al termine sotto l'epsilon",
    ("topo/core/primitives/formula.py", "_MAX_DEPTH"): "dimezzamenti di un tratto: 2^-30 del tratto",
}

# to be removed (TODO "Numbers of the primitives that escaped precision", points b and c): when the number disappears, test_le_eccezioni_esistono_ancora asks to remove the line
PENDING: dict = {}
EXCEPTIONS = {**NOT_THRESHOLDS, **CONVERGENCE, **PENDING}
PRECISION = "topo/precision.py"


def _is_number(node) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp):
        return _is_number(node.operand)
    if isinstance(node, ast.BinOp):
        return _is_number(node.left) and _is_number(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)             and isinstance(node.func.value, ast.Name) and node.func.value.id == "math":
        return bool(node.args) and all(_is_number(a) for a in node.args)
    return False


def _value(node) -> float:
    return eval(compile(ast.Expression(node), "<soglia>", "eval"), {"math": math})


def _counted(name: str, value) -> bool:
    """An integer from 2 up with a count name: samples, steps, depth, …"""
    return type(value) is int and value > 1 and any(k in name.lower() for k in COUNT_NAME)


def thresholds() -> list:
    """[(file, nome, valore)]: le soglie scritte come numero, decimale o conteggio."""
    out = []
    for package in PACKAGES:
        for path in sorted((PROJECT_ROOT / package).rglob("*.py")):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None \
                        and _is_number(node.value):
                    v = _value(node.value)
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    out += [(rel, t.id, v) for t in targets
                            if isinstance(t, ast.Name) and t.id.lstrip("_").isupper()
                            and (isinstance(v, float) or _counted(t.id, v))]
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = node.args.args + node.args.kwonlyargs
                    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + node.args.defaults \
                        + node.args.kw_defaults
                    out += [(rel, arg.arg, _value(default)) for arg, default in zip(args, defaults)
                            if default is not None and _is_number(default)
                            and ((isinstance(_value(default), float) and _value(default) > 0
                                  and any(k in arg.arg.lower() for k in THRESHOLD_PARAM))
                                 or _counted(arg.arg, _value(default)))]
    return out


class TestOneThreshold(unittest.TestCase):

    def test_ogni_soglia_sta_in_precision(self):
        found = sorted({(f, n, v) for f, n, v in thresholds()
                        if f != PRECISION and (f, n) not in EXCEPTIONS})
        self.assertEqual(found, [], "soglie scritte fuori da topo/precision.py: "
                                    "metterle lì, col loro perché (D269)")

    def test_le_eccezioni_esistono_ancora(self):
        found = {(f, n) for f, n, _ in thresholds()}
        self.assertEqual(sorted(set(EXCEPTIONS) - found), [], "eccezione senza più il suo numero: toglierla")

    def test_i_nomi_di_precision_sono_quelli_decisi(self):
        import topo.precision
        found = {n for n in vars(topo.precision) if n.isupper()
                 and type(getattr(topo.precision, n)) in (int, float)}
        self.assertEqual(sorted(found ^ PRECISION_NAMES), [],
                         "soglia aggiunta o tolta in precision: deciderlo in MAP e aggiornare l'elenco")

    def test_le_soglie_non_si_riassegnano(self):
        import topo
        with self.assertRaises(AttributeError):
            topo.precision.SAME_POINT = 0.1
        self.assertEqual(topo.precision.SAME_POINT, 1e-3)


if __name__ == "__main__":
    unittest.main()
