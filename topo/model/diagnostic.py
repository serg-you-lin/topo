"""
topo/model/diagnostic.py
------------------------
Un avviso di topo scritto come quelli del compilatore Rust (D227): cosa, dove,
perché non l'ha corretto, e la chiamata con la soglia che lo correggerebbe.
È una `str` (il testo per chi legge, umano o LLM) con i campi per chi
programma: le liste `warnings` restano liste di stringhe. Uno per tipo: il
testo mostra i primi punti, `points` li ha tutti.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

_SHOWN = 3   # punti scritti nel testo; gli altri solo in `points`


class Diagnostic(str):
    """
    A warning that says what topo found, where, why it left it, and how to fix it.

    One per kind of finding. It is a `str`: printing it gives a Rust-style message::

        warning[near-gap]: 33 gaps just over the tolerance, left open
          --> (196.052, 206.896)
          --> (190.308, 206.896)
          --> (12.400, 8.100)
          ... and 30 more in .points
          = note: 0.0502 to 0.0990 mm, tolerance 0.05
          = help: topo.heal(doc, max_gap=0.1) closes them all

    Fields for code: `code` (stable, kebab-case), `message`, `points` (every
    place to look, nearest first), `at` (the first of them, or None), `notes`,
    `help` (the call that fixes them), `param` and `value` (the threshold
    `help` sets and the smallest value that fixes all of them, or None).
    """

    code: str
    message: str
    points: Tuple[Tuple[float, float], ...]
    notes: Tuple[str, ...]
    help: str
    param: str
    value: Optional[float]

    def __new__(cls, code: str, message: str, *, points: Sequence[Tuple[float, float]] = (),
                notes: Sequence[str] = (), help: str = "", param: str = "",
                value: Optional[float] = None) -> "Diagnostic":
        points = tuple((float(p[0]), float(p[1])) for p in points)
        lines = [f"warning[{code}]: {message}"]
        lines += [f"  --> ({p[0]:.3f}, {p[1]:.3f})" for p in points[:_SHOWN]]
        if len(points) > _SHOWN:
            lines.append(f"  ... and {len(points) - _SHOWN} more in .points")
        lines += [f"  = note: {n}" for n in notes]
        if help:
            lines.append(f"  = help: {help}")
        self = super().__new__(cls, "\n".join(lines))
        self.code, self.message, self.points, self.notes, self.help = code, message, points, tuple(notes), help
        self.param, self.value = param, value
        return self

    @property
    def at(self) -> Optional[Tuple[float, float]]:
        """The first place to look, or None."""
        return self.points[0] if self.points else None

    def __reduce__(self):
        # copy/pickle: si ricostruisce dai campi, non dal testo
        return (_rebuild, (self.code, self.message, self.points, self.notes, self.help, self.param, self.value))


def _rebuild(code, message, points, notes, help, param, value) -> Diagnostic:
    return Diagnostic(code, message, points=points, notes=notes, help=help, param=param, value=value)
