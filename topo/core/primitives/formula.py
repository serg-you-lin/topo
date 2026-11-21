"""
topo/core/primitives/formula.py
-------------------------------
`FormulaSeg` (D289): una curva data dalla sua formula, x(t) e y(t), per
quello che non ha una classe sua (evolvente, polinomio, cicloide, ...).
La formula è testo in una grammatica chiusa — numeri, t, parametri con nome,
+ − · / **, le funzioni di `_FUNCTIONS`, pi ed e — analizzata una volta e
rifiutata se esce dalla grammatica: nessun codice arbitrario. La derivata è
simbolica, dalla formula. Uno spostamento non riscrive la formula: è una mappa
affine sul punto (x(t), y(t)).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from .segments import (
    DEFAULT_TOLERANCE, MathSeg, Point, _check_factor, _point_to_segment_distance, _real,
)

# funzione -> derivata (come formula nella stessa grammatica, in `u`)
_FUNCTIONS: Dict[str, Tuple[Callable[[float], float], str]] = {
    "sin": (math.sin, "cos(u)"),
    "cos": (math.cos, "-sin(u)"),
    "tan": (math.tan, "1 / cos(u)**2"),
    "exp": (math.exp, "exp(u)"),
    "log": (math.log, "1 / u"),
    "sqrt": (math.sqrt, "1 / (2 * sqrt(u))"),
    "sinh": (math.sinh, "cosh(u)"),
    "cosh": (math.cosh, "sinh(u)"),
    "tanh": (math.tanh, "1 / cosh(u)**2"),
    "asin": (math.asin, "1 / sqrt(1 - u**2)"),
    "acos": (math.acos, "-1 / sqrt(1 - u**2)"),
    "atan": (math.atan, "1 / (1 + u**2)"),
}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_INITIAL_PIECES = 16      # tratti di partenza della discretizzazione adattiva
_MAX_DEPTH = 30           # dimezzamenti al più per tratto


def _parse(text: str, names: set) -> ast.expr:
    """L'albero della formula, se sta nella grammatica; ValueError altrimenti."""
    try:
        tree = ast.parse(text, mode="eval").body
    except SyntaxError as exc:
        raise ValueError(f"not a formula: {text!r}") from exc

    def check(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return
        if isinstance(node, ast.Name) and (node.id in names or node.id in _CONSTANTS):
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, _BINARY):
            check(node.left)
            check(node.right)
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            check(node.operand)
            return
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS
                and len(node.args) == 1 and not node.keywords):
            check(node.args[0])
            return
        raise ValueError(f"{ast.unparse(node)!r} is outside the formula grammar")

    check(tree)
    return tree


def _num(value: float) -> ast.expr:
    return ast.Constant(value)


def _depends(node: ast.expr) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "t" for n in ast.walk(node))


def _diff(node: ast.expr) -> ast.expr:
    """d(node)/dt, come albero nella stessa grammatica."""
    if not _depends(node):
        return _num(0)
    if isinstance(node, ast.Name):          # è t
        return _num(1)
    if isinstance(node, ast.UnaryOp):
        return ast.UnaryOp(node.op, _diff(node.operand))
    if isinstance(node, ast.Call):
        inner = node.args[0]
        outer = _parse(_FUNCTIONS[node.func.id][1], {"u"})
        outer = _Substitute({"u": inner}).visit(outer)
        return ast.BinOp(outer, ast.Mult(), _diff(inner))
    a, b = node.left, node.right
    da, db = _diff(a), _diff(b)
    if isinstance(node.op, (ast.Add, ast.Sub)):
        return ast.BinOp(da, node.op, db)
    if isinstance(node.op, ast.Mult):
        return ast.BinOp(ast.BinOp(da, ast.Mult(), b), ast.Add(), ast.BinOp(a, ast.Mult(), db))
    if isinstance(node.op, ast.Div):
        top = ast.BinOp(ast.BinOp(da, ast.Mult(), b), ast.Sub(), ast.BinOp(a, ast.Mult(), db))
        return ast.BinOp(top, ast.Div(), ast.BinOp(b, ast.Pow(), _num(2)))
    # potenza: esponente costante, oppure a**b = exp(b·log a)
    if not _depends(b):
        return ast.BinOp(ast.BinOp(b, ast.Mult(), ast.BinOp(a, ast.Pow(), ast.BinOp(b, ast.Sub(), _num(1)))),
                         ast.Mult(), da)
    log_a = ast.Call(ast.Name("log", ast.Load()), [a], [])
    inner = ast.BinOp(ast.BinOp(db, ast.Mult(), log_a), ast.Add(), ast.BinOp(b, ast.Mult(), ast.BinOp(da, ast.Div(), a)))
    return ast.BinOp(node, ast.Mult(), inner)


class _Substitute(ast.NodeTransformer):
    def __init__(self, values: Dict[str, ast.expr]):
        self.values = values

    def visit_Name(self, node):
        return self.values.get(node.id, node)


def _compile(node: ast.expr):
    return compile(ast.fix_missing_locations(ast.Expression(node)), "<formula>", "eval")


@dataclass
class FormulaSeg(MathSeg):
    """
    A curve given by its formula: P(s) = A·(x(s), y(s)) + b, with `x` and `y`
    formulas in `s` written with the variable `t` (numbers, `params` by name,
    + - * / **, sin cos tan exp log sqrt sinh cosh tanh asin acos atan, pi, e).
    `s` runs from `start_param` to `end_param` (either way round). `affine`
    is (a, b, c, d, e, f): x' = a·x + b·y + e, y' = c·x + d·y + f — how a
    motion is kept without rewriting the formula. `t` (of `MathSeg`) is the
    parameter walked from the start, t in [0, |end_param − start_param|].
    The derivative is exact (symbolic); the polygon is adaptive on the true
    curve, not by proof.
    """
    x: str
    y: str
    start_param: float
    end_param: float
    params: Tuple[Tuple[str, float], ...] = field(default=(), kw_only=True)
    affine: Tuple[float, float, float, float, float, float] = field(default=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0), kw_only=True)
    _code: tuple = field(default=(), init=False, repr=False, compare=False)

    def __post_init__(self):
        if isinstance(self.params, dict):
            self.params = tuple(sorted(self.params.items()))
        self.params = tuple((str(k), _real(v)) for k, v in self.params)
        self.start_param, self.end_param = _real(self.start_param), _real(self.end_param)
        self.affine = tuple(_real(v) for v in self.affine)
        a, b, c, d, _, _ = self.affine
        if a * d - b * c == 0:
            raise ValueError("degenerate formula curve: the affine map flattens the plane")
        names = {"t"} | {k for k, _ in self.params}
        x, y = _parse(self.x, names), _parse(self.y, names)
        self._code = (_compile(x), _compile(y), _compile(_diff(x)), _compile(_diff(y)))
        p0, p1 = self.endpoints()
        if not all(map(math.isfinite, p0 + p1)):
            raise ValueError(f"the formula is not defined at the ends of [{self.start_param}, {self.end_param}]")

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_code"}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.__post_init__()

    def _env(self, s: float) -> dict:
        env = {"__builtins__": {}, **_CONSTANTS, **{k: f for k, (f, _) in _FUNCTIONS.items()}, **dict(self.params)}
        env["t"] = s
        return env

    def _raw(self, s: float) -> Point:
        env = self._env(s)
        return eval(self._code[0], env), eval(self._code[1], env)

    def _map(self, p: Point, translate: bool = True) -> Point:
        a, b, c, d, e, f = self.affine
        x, y = p
        return (a * x + b * y + (e if translate else 0.0), c * x + d * y + (f if translate else 0.0))

    def _sign(self) -> float:
        return 1.0 if self.end_param >= self.start_param else -1.0

    @property
    def t_range(self) -> Tuple[float, float]:
        return (0.0, abs(self.end_param - self.start_param))

    def _at(self, s: float) -> Point:
        return self._map(self._raw(s))

    def point_at(self, t: float) -> Point:
        return self._at(self.start_param + self._sign() * t)

    def derivative_at(self, t: float) -> Point:
        env = self._env(self.start_param + self._sign() * t)
        dx, dy = eval(self._code[2], env), eval(self._code[3], env)
        mx, my = self._map((dx, dy), translate=False)
        return (self._sign() * mx, self._sign() * my)

    def endpoints(self) -> Tuple[Point, Point]:
        return self._at(self.start_param), self._at(self.end_param)

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """Adattiva sulla curva vera: un tratto si dimezza finché tre suoi punti
        interni stanno entro `tolerance` dalla corda. Non per dimostrazione:
        una formula qualunque non dà un limite a |P''|."""
        out = [self.point_at(0.0)]
        total = self.t_range[1]

        def split(a: float, b: float, pa: Point, pb: Point, depth: int):
            inner = [self.point_at(a + (b - a) * k / 4) for k in (1, 2, 3)]
            if depth < _MAX_DEPTH and max(_point_to_segment_distance(q, pa, pb) for q in inner) > tolerance:
                m = (a + b) / 2
                split(a, m, pa, inner[1], depth + 1)
                split(m, b, inner[1], pb, depth + 1)
            else:
                out.append(pb)

        ts = [total * k / _INITIAL_PIECES for k in range(_INITIAL_PIECES + 1)]
        for a, b in zip(ts, ts[1:]):
            split(a, b, self.point_at(a), self.point_at(b), 0)
        return out

    def to_bspline(self, *, tolerance: float = DEFAULT_TOLERANCE):
        """A cubic B-spline within `tolerance` of the curve, through its two
        ends: an approximation (a formula has no exact spline in general), for a
        format that cannot hold a formula."""
        from ..geometry.points import approximate_bspline   # geometry sta sopra primitives
        from .segments import BSplineSeg
        control, knots = approximate_bspline(self.discretize(tolerance=tolerance / 2), 3, tolerance / 2)
        return BSplineSeg(degree=3, control_points=[tuple(p) for p in control], knots=list(knots))

    def _moved(self, a: float, b: float, c: float, d: float, e: float, f: float) -> "FormulaSeg":
        """La stessa formula con la mappa (a b; c d) + (e, f) applicata dopo quella di prima."""
        a0, b0, c0, d0, e0, f0 = self.affine
        affine = (a * a0 + b * c0, a * b0 + b * d0, c * a0 + d * c0, c * b0 + d * d0,
                  a * e0 + b * f0 + e, c * e0 + d * f0 + f)
        return FormulaSeg(self.x, self.y, self.start_param, self.end_param, params=self.params, affine=affine)

    def reversed(self) -> "FormulaSeg":
        return FormulaSeg(self.x, self.y, self.end_param, self.start_param, params=self.params, affine=self.affine)

    def rotated(self, angle: float, *, origin: Point = (0.0, 0.0)) -> "FormulaSeg":
        c, s = math.cos(angle), math.sin(angle)
        ox, oy = origin
        return self._moved(c, -s, s, c, ox - c * ox + s * oy, oy - s * ox - c * oy)

    def translated(self, dx: float, dy: float) -> "FormulaSeg":
        return self._moved(1.0, 0.0, 0.0, 1.0, dx, dy)

    def mirrored(self, *, origin: Point = (0.0, 0.0), angle: float = 0.0) -> "FormulaSeg":
        c, s = math.cos(2 * angle), math.sin(2 * angle)
        ox, oy = origin
        return self._moved(c, s, s, -c, ox - c * ox - s * oy, oy - s * ox + c * oy)

    def scaled(self, factor: float, *, origin: Point = (0.0, 0.0)) -> "FormulaSeg":
        k = _check_factor(factor)
        ox, oy = origin
        return self._moved(k, 0.0, 0.0, k, ox - k * ox, oy - k * oy)
