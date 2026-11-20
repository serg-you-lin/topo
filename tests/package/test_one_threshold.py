# tests/package/test_one_threshold.py
"""Ogni soglia fissa di topo sta in `topo/precision.py` e non si riassegna (D268, D269).

Si guardano le costanti a livello di modulo con un valore numerico (anche
un'espressione come `math.radians(2.0)`) e i valori di default decimali dei
parametri che sono soglie (`THRESHOLD_PARAM`: tol, gap, segment, angle, …).
I nomi di `precision` sono un elenco fisso: aggiungerne o toglierne uno è una
decisione (MAP), non un effetto collaterale. Le guardie dell'aritmetica scritte nei confronti (`< 1e-12`) non
sono soglie del disegno e non si guardano (D196)."""

import ast
import math
import unittest

from tests.paths import PROJECT_ROOT

PACKAGES = ("topo", "topo_dxf", "topo_pdf")
THRESHOLD_PARAM = ("tol", "eps", "gap", "reach", "snap", "margin", "sagitta", "segment", "angle",
                   "distance", "dist", "length", "radius", "area", "step", "ratio", "fraction",
                   "factor", "width", "limit", "threshold")

# i nomi di topo/precision.py (D269, D275, D276, D277)
PRECISION_NAMES = {
    "ANGLE_BRACKET_DEG", "CORNER_TURN_DEG", "FLOAT_NOISE", "MARK_FRACTION",
    "NEAR_FULL_ARC_HINT_DEG", "NEAR_FULL_ARC_MISSING_DEG", "NEAR_GAP_FACTOR",
    "PDF_SNAP", "RING_TO_CIRCLE", "SAME_POINT", "TESSELLATION_SIDE",
}

# (file, nome): numeri che non sono soglie, col perché
NOT_THRESHOLDS = {
    ("topo_pdf/geometry_adapter.py", "PT_TO_MM"): "conversione di unità",
}
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
                            if default is not None and _is_number(default)
                            and isinstance(_value(default), float) and _value(default) > 0
                            and any(k in arg.arg.lower() for k in THRESHOLD_PARAM)]
    return out


class TestOneThreshold(unittest.TestCase):

    def test_ogni_soglia_sta_in_precision(self):
        found = sorted({(f, n, v) for f, n, v in thresholds()
                        if f != PRECISION and (f, n) not in NOT_THRESHOLDS})
        self.assertEqual(found, [], "soglie scritte fuori da topo/precision.py: "
                                    "metterle lì, col loro perché (D269)")

    def test_le_eccezioni_esistono_ancora(self):
        found = {(f, n) for f, n, _ in thresholds()}
        self.assertEqual(sorted(set(NOT_THRESHOLDS) - found), [], "eccezione senza più il suo numero: toglierla")

    def test_i_nomi_di_precision_sono_quelli_decisi(self):
        import topo.precision
        found = {n for n in vars(topo.precision) if n.isupper() and isinstance(getattr(topo.precision, n), float)}
        self.assertEqual(sorted(found ^ PRECISION_NAMES), [],
                         "soglia aggiunta o tolta in precision: deciderlo in MAP e aggiornare l'elenco")

    def test_le_soglie_non_si_riassegnano(self):
        import topo
        with self.assertRaises(AttributeError):
            topo.precision.SAME_POINT = 0.1
        self.assertEqual(topo.precision.SAME_POINT, 1e-3)


if __name__ == "__main__":
    unittest.main()
