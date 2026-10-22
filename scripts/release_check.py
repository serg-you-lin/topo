"""
scripts/release_check.py
------------------------
Dice se topo è *1.0-ready* (MAP.md D148): esce 0 solo se ogni controllo
passa, e per quelli che non passano stampa cosa manca.

Perché esiste: "si può pubblicare la 1.0 in qualunque momento" deve essere un
comando, non un'impressione. Da quando esce 0, ogni commit su `main` lo tiene
a 0; un cambiamento che non ci riesce sta su un branch.

I controlli, ognuno legato a un punto del cancello in `TODO.md`:

1. **suite** — `pytest`: zero failed, zero error, zero xfailed, zero xpassed
   (G7: un fallimento atteso è un debito, non un test verde). Gli skip non
   bocciano: oggi sono test di proprietà che non si applicano a un input; i
   disegni mancanti, l'altra causa di skip, li conta il controllo 4.
2. **indice** — `gen_index.py --check`: `docs/INDEX.md` aggiornato e regola
   di dipendenza rispettata.
3. **nomi** — `audit_names.py --strict`: niente dati cliente nei file
   tracciati.
   **history** — `audit_names.py --history --strict`: niente neanche nei
   commit vecchi (G10). Stampa solo il numero: i sospetti si leggono
   lanciando il comando a mano, non finiscono nel referto.
4. **fixture** — `audit_fixtures.py --strict`: ogni disegno che la suite usa
   è in git, così un clone pulito gira gli stessi test.
5. **docstring** — i nomi pubblici (`__all__` di `topo`, `topo.geometry`,
   `topo_dxf`) hanno una docstring propria, in inglese (D144, G9).
   Euristica: parole funzionali italiane; un falso positivo si corregge qui.

Uso (da qualsiasi cartella)::

    python scripts/release_check.py             # tutti i controlli
    python scripts/release_check.py --no-suite  # tutti tranne pytest (~90 s)
"""

import _paths  # noqa: F401

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class Check:
    """Esito di un controllo: passato o no, e le righe che dicono cosa manca."""
    name: str
    gate: str
    passed: bool
    details: list[str] = field(default_factory=list)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _tail(text: str, n: int = 15) -> list[str]:
    return [r for r in text.strip().splitlines()[-n:] if r.strip()]


# ---------------------------------------------------------------------------
# 1. suite

_COUNT = re.compile(r"(\d+) (failed|passed|skipped|xfailed|xpassed|errors?)\b")
_BLOCKING = ("failed", "error", "errors", "xfailed", "xpassed")


def check_suite() -> Check:
    proc = _run("-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfExX")
    lines = proc.stdout.strip().splitlines()
    summary = lines[-1] if lines else ""
    counts = {kind: int(n) for n, kind in _COUNT.findall(summary)}
    bad = {k: v for k, v in counts.items() if k in _BLOCKING and v}
    details = [summary.strip("= ")]
    # le righe di -rfExX: FAILED / ERROR / XFAIL / XPASS, una per test
    details += [r for r in lines
                if r.startswith(("FAILED", "ERROR", "XFAIL", "XPASS"))]
    if not counts:
        details += _tail(proc.stdout + proc.stderr)
    return Check("suite", "G7", bool(counts) and not bad, details)


# ---------------------------------------------------------------------------
# 2-4. gli script che esistono già

def check_script(name: str, gate: str, *args: str) -> Check:
    proc = _run(*args)
    ok = proc.returncode == 0
    return Check(name, gate, ok, [] if ok else _tail(proc.stdout + proc.stderr))


def check_history() -> Check:
    proc = _run("scripts/audit_names.py", "--history", "--strict")
    ok = proc.returncode == 0
    last = _tail(proc.stdout, 1)
    return Check("history", "G10", ok, [] if ok else last + [
        "dettaglio: python scripts/audit_names.py --history"])


# ---------------------------------------------------------------------------
# 5. docstring dei nomi pubblici

# parole funzionali di una lingua che nell'altra non compaiono; "l'", "dell'",
# ... sono le elisioni. Una docstring non è inglese se non ha nessuna parola
# funzionale inglese (una frase inglese ne ha sempre una: "Rettangolo centrato
# in `center`" ne ha zero di entrambe) o se ne ha più italiane che inglesi. I
# nomi di codice fra backtick non contano per nessuna delle due.
_ITALIAN = re.compile(
    r"\b(il|lo|gli|di|da|della|dello|delle|degli|del|dei|dal|dalla|nel|"
    r"nella|nei|alla|al|sul|sulla|tra|fra|che|per|non|una|uno|sono|è|con|"
    r"ogni|senza|quando|oppure|questo|questa|già|più|cioè|perché|ma|se)\b"
    r"|\b(l|dell|nell|all|un|sull|dall)'",
    re.IGNORECASE)
_ENGLISH = re.compile(
    r"\b(the|of|and|is|are|an|to|returns?|with|for|from|that|this|each|or|"
    r"by|it|its|not|when|which)\b",
    re.IGNORECASE)
_CODE = re.compile(r"`[^`]*`")


def not_english(doc: str) -> bool:
    prose = _CODE.sub(" ", doc)
    english = len(_ENGLISH.findall(prose))
    return english == 0 or len(_ITALIAN.findall(prose)) > english

# docstring che Python scrive da solo: per noi è come non averla
_AUTO_DOC = ("An enumeration.",)


def _own_doc(obj: object) -> str | None:
    if isinstance(obj, type):
        doc = obj.__dict__.get("__doc__")
        # @dataclass senza docstring si inventa "Nome(campo: tipo, ...)"
        if doc and doc.startswith(obj.__name__ + "("):
            return None
    else:
        doc = getattr(obj, "__doc__", None)
    return None if not doc or doc.strip() in _AUTO_DOC else doc


def public_docstring_problems() -> list[str]:
    """Una riga per ogni nome pubblico senza docstring o con docstring non inglese."""
    import topo
    import topo_dxf

    problems: list[str] = []
    for label, module in (("topo", topo), ("topo.geometry", topo.geometry),
                          ("topo_dxf", topo_dxf)):
        for name in module.__all__:
            obj = getattr(module, name)
            # costanti e moduli: la docstring sarebbe quella del tipo
            if not (callable(obj) or isinstance(obj, type)) \
                    or isinstance(obj, Enum):
                continue
            doc = _own_doc(obj)
            if doc is None:
                problems.append(f"{label}.{name}: senza docstring")
            elif not_english(doc):
                problems.append(f"{label}.{name}: non in inglese")
    return problems


def check_docstrings() -> Check:
    problems = public_docstring_problems()
    return Check("docstring", "G9", not problems,
                 [f"{len(problems)} nomi pubblici da sistemare"] + problems
                 if problems else [])


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="topo è 1.0-ready? (D148)")
    parser.add_argument("--no-suite", action="store_true",
                        help="salta pytest (il controllo lento)")
    args = parser.parse_args(argv)

    checks: list[Check] = []
    if not args.no_suite:
        checks.append(check_suite())
    checks += [
        check_script("indice", "-", "scripts/gen_index.py", "--check"),
        check_script("nomi", "-", "scripts/audit_names.py", "--strict"),
        check_history(),
        check_script("fixture", "-", "scripts/audit_fixtures.py", "--strict"),
        check_docstrings(),
    ]

    for c in checks:
        print(f"{'OK ' if c.passed else 'NO '} {c.name:10} (cancello {c.gate})")
        for row in c.details:
            print(f"      {row}")

    ready = all(c.passed for c in checks)
    if ready and args.no_suite:
        print("\nverde senza la suite: rilancia senza --no-suite per dirlo.")
        return 1
    print("\n1.0-ready." if ready else
          "\nnon ancora 1.0-ready: il cancello è in TODO.md (D148).")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
