"""
topo/core/primitives/formula.py
-------------------------------
`FormulaSeg`: a curve given by its formula, x(t) and y(t), for what has no
class of its own (involute, polynomial, cycloid, ...). The formula is text in
a closed grammar — numbers, t, named parameters, + − · / **, the functions of
`_FUNCTIONS`, pi and e — parsed once and rejected if it leaves the grammar: no
arbitrary code. The derivative is symbolic, from the formula. A move does not
rewrite the formula: it is an affine map on the point (x(t), y(t)).
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from .mathseg import DEFAULT_TOLERANCE, Algebra, MathSeg, Point, _real
from .motion import _check_factor
from .polyline import _point_to_segment_distance

# function -> derivative (a formula in the same grammar, in `u`)
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
_INITIAL_PIECES = 16      # starting pieces of the adaptive discretization
_MAX_DEPTH = 30           # at most this many halvings per piece


def _parse(text: str, names: set) -> ast.expr:
    """The formula's tree if it is in the grammar; ValueError otherwise."""
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
    """d(node)/dt, as a tree in the same grammar."""
    if not _depends(node):
        return _num(0)
    if isinstance(node, ast.Name):
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
    # power: constant exponent, or a**b = exp(b·log a)
    if not _depends(b):
        return ast.BinOp(ast.BinOp(b, ast.Mult(), ast.BinOp(a, ast.Pow(), ast.BinOp(b, ast.Sub(), _num(1)))),
                         ast.Mult(), da)
    log_a = ast.Call(ast.Name("log", ast.Load()), [a], [])
    inner = ast.BinOp(ast.BinOp(db, ast.Mult(), log_a), ast.Add(), ast.BinOp(b, ast.Mult(), ast.BinOp(da, ast.Div(), a)))
    return ast.BinOp(node, ast.Mult(), inner)


_ORDER = ("polynomial", "rational", "transcendental")


def _algebra(node: ast.expr, env: dict) -> Algebra:
    """What the tree proves: polynomial in t (+ − · and integer powers ≥ 0),
    fraction of polynomials (also / and negative integer powers), otherwise
    transcendental — here meaning "no rational form proved": cos(t), sin(t) is
    a circle, rational, but the tree does not prove it."""
    if not _depends(node):
        return "polynomial"
    if isinstance(node, ast.Name):
        return "polynomial"
    if isinstance(node, ast.UnaryOp):
        return _algebra(node.operand, env)
    if isinstance(node, ast.Call):
        return "transcendental"
    left = _algebra(node.left, env)
    if isinstance(node.op, ast.Pow):
        if _depends(node.right):
            return "transcendental"
        n = eval(_compile(node.right), env)
        if not float(n).is_integer():
            return "transcendental"
        return left if n >= 0 else max(left, "rational", key=_ORDER.index)
    right = _algebra(node.right, env)
    worst = max(left, right, key=_ORDER.index)
    if isinstance(node.op, ast.Div) and _depends(node.right):
        return max(worst, "rational", key=_ORDER.index)
    return worst


Interval = Tuple[float, float]
_WHOLE: Interval = (-math.inf, math.inf)


def _span(*values: float) -> Interval:
    """The smallest interval containing the values; a NaN (∞ · 0, ∞ − ∞) says
    nothing, so the whole line."""
    if any(math.isnan(v) for v in values):
        return _WHOLE
    return min(values), max(values)


def _hits(lo: float, hi: float, start: float, period: float) -> bool:
    """[lo, hi] contains a point start + k·period."""
    return math.floor((hi - start) / period) >= math.ceil((lo - start) / period)


def _call_interval(name: str, lo: float, hi: float) -> Interval:
    """The image of [lo, hi] under the function `name`: values at the ends, plus
    the interior maxima and minima (sin, cos, cosh); outside the domain, the whole line."""
    if math.isnan(lo) or math.isnan(hi):
        return _WHOLE
    if name in ("sin", "cos"):
        if not hi - lo < 2 * math.pi:       # also with an infinite end
            return -1.0, 1.0
        f = math.sin if name == "sin" else math.cos
        top = math.pi / 2 if name == "sin" else 0.0
        out_lo, out_hi = _span(f(lo), f(hi))
        if _hits(lo, hi, top, 2 * math.pi):
            out_hi = 1.0
        if _hits(lo, hi, top + math.pi, 2 * math.pi):
            out_lo = -1.0
        return out_lo, out_hi
    if name == "tan":
        if not hi - lo < math.pi or _hits(lo, hi, math.pi / 2, math.pi):
            return _WHOLE
        return math.tan(lo), math.tan(hi)
    if name == "cosh":
        near, far = (0.0 if lo <= 0 <= hi else min(abs(lo), abs(hi))), max(abs(lo), abs(hi))
        return _grow(math.cosh, near), _grow(math.cosh, far)
    if name in ("log", "sqrt") and hi <= 0 or name in ("asin", "acos") and (hi < -1 or lo > 1):
        return _WHOLE
    if name == "log":
        return (math.log(lo) if lo > 0 else -math.inf), math.log(hi)
    if name == "sqrt":
        return math.sqrt(max(lo, 0.0)), math.sqrt(hi)
    if name in ("asin", "acos"):
        a, b = math.asin(max(lo, -1.0)), math.asin(min(hi, 1.0))
        return (a, b) if name == "asin" else (math.pi / 2 - b, math.pi / 2 - a)
    f = _FUNCTIONS[name][0]                 # exp, sinh, tanh, atan: increasing
    return _grow(f, lo), _grow(f, hi)


def _grow(f: Callable[[float], float], x: float) -> float:
    """f(x) for an increasing function that beyond the doubles goes to infinity with the sign of x."""
    try:
        return f(x)
    except OverflowError:
        return math.copysign(math.inf, x)


def _power_interval(base: Interval, n: float) -> Interval:
    """[lo, hi] ** n with a constant exponent."""
    lo, hi = base
    if n == 0:
        return 1.0, 1.0
    if math.isinf(n) or math.isnan(n):
        return _WHOLE
    if float(n).is_integer():
        k = int(n)
        if k < 0:
            return _divide((1.0, 1.0), _power_interval(base, -k))
        if k % 2 == 1:
            return _span(_pow(lo, k), _pow(hi, k))
        if lo <= 0 <= hi:
            return 0.0, max(_pow(lo, k), _pow(hi, k))
        return _span(_pow(lo, k), _pow(hi, k))
    if hi < 0:
        return _WHOLE
    lo = max(lo, 0.0)
    if n < 0:
        return (_pow(hi, n) if hi > 0 else math.inf), (_pow(lo, n) if lo > 0 else math.inf)
    return _pow(lo, n), _pow(hi, n)


def _pow(x: float, n: float) -> float:
    """x ** n (x ≥ 0 if n is not an integer); beyond the doubles, infinity with the right sign."""
    try:
        return x ** n
    except OverflowError:
        return math.inf if x > 0 or float(n).is_integer() and int(n) % 2 == 0 else -math.inf


def _divide(a: Interval, b: Interval) -> Interval:
    if b[0] <= 0 <= b[1]:
        return _WHOLE
    return _span(*(x / y for x in a for y in b))


def _enclose(node: ast.expr, env: Dict[str, Interval]) -> Interval:
    """An interval containing every value of the tree when the variables lie in
    their `env` intervals (interval arithmetic: wide, never narrow; double
    rounding aside, below FLOAT_NOISE)."""
    if isinstance(node, ast.Constant):
        return float(node.value), float(node.value)
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        return _CONSTANTS[node.id], _CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp):
        lo, hi = _enclose(node.operand, env)
        return (-hi, -lo) if isinstance(node.op, ast.USub) else (lo, hi)
    if isinstance(node, ast.Call):
        return _call_interval(node.func.id, *_enclose(node.args[0], env))
    a, b = _enclose(node.left, env), _enclose(node.right, env)
    if isinstance(node.op, ast.Add):
        return _span(a[0] + b[0], a[1] + b[1])
    if isinstance(node.op, ast.Sub):
        return _span(a[0] - b[1], a[1] - b[0])
    if isinstance(node.op, ast.Mult):
        return _span(*(x * y for x in a for y in b))
    if isinstance(node.op, ast.Div):
        return _divide(a, b)
    if b[0] == b[1]:
        return _power_interval(a, b[0])
    # a**b = exp(b·log a)
    log_a = _call_interval("log", *a)
    return _call_interval("exp", *_span(*(x * y for x in log_a for y in b)))


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
    _trees: tuple = field(default=(), init=False, repr=False, compare=False)

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
        self._trees = (x, y)
        p0, p1 = self.endpoints()
        if not all(map(math.isfinite, p0 + p1)):
            raise ValueError(f"the formula is not defined at the ends of [{self.start_param}, {self.end_param}]")

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k not in ("_code", "_trees")}

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

    @property
    def algebra(self) -> Algebra:
        """Read from the formula's tree (`_algebra`): the worse of x and y; the
        affine map does not change the class."""
        names = {"t"} | {k for k, _ in self.params}
        env = self._env(0.0)
        return max((_algebra(_parse(text, names), env) for text in (self.x, self.y)), key=_ORDER.index)

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

    def _box(self, t0: float, t1: float) -> List[Point]:
        """The four corners of a parallelogram containing the curve for t in
        [t0, t1]: the box of x and y from interval arithmetic, carried by the
        affine map. The curve lies in their hull. Empty if the interval is not
        finite (a pole, a domain exceeded)."""
        s0, s1 = sorted((self.start_param + self._sign() * t0, self.start_param + self._sign() * t1))
        env = {"t": (s0, s1), **{k: (v, v) for k, v in self.params}}
        (xa, xb), (ya, yb) = (_enclose(tree, env) for tree in self._trees)
        if not all(map(math.isfinite, (xa, xb, ya, yb))):
            return []                       # no bound on this piece: halve it
        return [self._map(p) for p in ((xa, ya), (xb, ya), (xb, yb), (xa, yb))]

    def discretize(self, *, tolerance: float = DEFAULT_TOLERANCE) -> List[Point]:
        """Adaptive on the true curve: a piece is halved until three of its inner
        points are within `tolerance` of the chord. Not by proof: an arbitrary
        formula gives no bound on |P''|."""
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
        from ..geometry.spline_fit import approximate_bspline   # geometry sits above primitives
        from .spline import BSplineSeg
        control, knots = approximate_bspline(self.discretize(tolerance=tolerance / 2), 3, tolerance / 2)
        return BSplineSeg(degree=3, control_points=[tuple(p) for p in control], knots=list(knots))

    def _moved(self, a: float, b: float, c: float, d: float, e: float, f: float) -> "FormulaSeg":
        """The same formula with the map (a b; c d) + (e, f) applied after the previous one."""
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
