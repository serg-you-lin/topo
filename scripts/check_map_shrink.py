"""scripts/check_map_shrink.py

Controllo meccanico dell'accorciamento di MAP.md e TODO.md (TODO.md, "MAP e
TODO corte"). Il riferimento è MAP.md com'era prima dell'accorciamento, letto
da git: nessuna decisione può sparire, nessun rimando può restare appeso.

    python scripts/check_map_shrink.py                       # errori → exit 1
    python scripts/check_map_shrink.py --archive docs/X.md   # verifica anche l'archivio

Controlla:
  1. ogni D## del riferimento ha ancora una voce in MAP.md (riga che inizia con D##);
  2. nessuna voce definita due volte;
  3. ogni D## citato in repo (md, py) esiste fra le voci di MAP.md;
  4. con --archive: ogni titolo D## del riferimento è nell'archivio, testo intero;
  5. (solo avvisi) righe totali e voci più lunghe di 5 righe.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_REF = "67fda38"  # ultimo commit con MAP.md intero
TARGET_LINES = 600
MAX_ENTRY_LINES = 5

# una voce: un titolo (#) o una voce di elenco (-, *, |) che inizia con D<n>
ENTRY_RE = re.compile(r"^(?:#{1,4}\s+|[-*|]\s+)(?:\*\*|~~)?D(\d+)\b")
HEADING_RE = re.compile(r"^#{2,4}\s+D(\d+)\b")
REF_RE = re.compile(r"\bD(\d{1,3})\b")
# numeri D di altre librerie, non di topo
FOREIGN_RE = re.compile(r"(snapdraw|snapbend|smoother|snapfence|pippo)\W{0,3}(?:MAP(?:\.md)?\W{0,3})?$", re.I)
SCAN_GLOBS = ("*.md", "docs/**/*.md", "topo/**/*.py", "topo_dxf/**/*.py",
              "topo_pdf/**/*.py", "tests/**/*.py", "scripts/**/*.py")


def baseline_text(ref: str) -> str:
    """MAP.md alla revisione `ref`."""
    out = subprocess.run(["git", "show", f"{ref}:MAP.md"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return out.stdout


def entries(lines: list[str], pattern: re.Pattern[str]) -> dict[int, list[int]]:
    """numero D → righe (1-based) dove è definita una voce."""
    found: dict[int, list[int]] = {}
    for i, line in enumerate(lines, 1):
        m = pattern.match(line)
        if m:
            found.setdefault(int(m.group(1)), []).append(i)
    return found


def scan_refs(defined: set[int]) -> list[str]:
    """rimandi D## in repo che non puntano a nessuna voce di MAP.md."""
    bad: list[str] = []
    seen: set[Path] = set()
    for glob in SCAN_GLOBS:
        for path in sorted(ROOT.glob(glob)):
            if path in seen or path.name == "INDEX.md" or not path.is_file():
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            for n_line, line in enumerate(text.splitlines(), 1):
                for m in REF_RE.finditer(line):
                    if FOREIGN_RE.search(line[: m.start()]):
                        continue
                    if int(m.group(1)) not in defined:
                        rel = path.relative_to(ROOT).as_posix()
                        bad.append(f"{rel}:{n_line}: D{m.group(1)}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=BASELINE_REF)
    ap.add_argument("--archive", type=Path)
    args = ap.parse_args()

    base_lines = baseline_text(args.ref).splitlines()
    base = entries(base_lines, HEADING_RE)
    cur_lines = (ROOT / "MAP.md").read_text(encoding="utf-8").splitlines()
    cur = entries(cur_lines, ENTRY_RE)
    errors: list[str] = []

    # 1. nessuna decisione sparita
    errors += [f"MAP.md: D{n} non ha più una voce" for n in sorted(set(base) - set(cur))]
    # 2. nessuna voce doppia (nel riferimento i doppioni erano già lì: li segnala a parte)
    errors += [f"MAP.md: D{n} definita più volte, righe {rows}"
               for n, rows in sorted(cur.items()) if len(rows) > 1]
    # 3. nessun rimando appeso
    errors += [f"rimando appeso {r}" for r in scan_refs(set(cur))]
    # 4. archivio completo
    if args.archive:
        arch = (ROOT / args.archive).read_text(encoding="utf-8")
        for n, rows in sorted(base.items()):
            for row in rows:
                if base_lines[row - 1] not in arch:
                    errors.append(f"{args.archive}: manca il titolo di D{n}")

    # 5. avvisi
    warnings: list[str] = []
    gaps = sorted(set(range(1, max(base) + 1)) - set(base))
    if gaps:
        warnings.append(f"riferimento: numeri mai usati {gaps}")
    dup_base = {n: r for n, r in base.items() if len(r) > 1}
    if dup_base:
        warnings.append(f"riferimento: già doppie {dup_base}")
    starts = sorted(r for rows in cur.values() for r in rows)
    for a, b in zip(starts, starts[1:] + [len(cur_lines) + 1]):
        body = [l for l in cur_lines[a - 1:b - 1] if l.strip() and not l.startswith("#")]
        if len(body) > MAX_ENTRY_LINES:
            warnings.append(f"MAP.md:{a}: voce di {len(body)} righe (> {MAX_ENTRY_LINES})")
    todo_n = len((ROOT / "TODO.md").read_text(encoding="utf-8").splitlines())

    for w in warnings[:15]:
        print("avviso:", w)
    if len(warnings) > 15:
        print(f"avviso: ... altri {len(warnings) - 15}")
    for e in errors:
        print("ERRORE:", e)
    print(f"MAP.md {len(cur_lines)} righe (obiettivo ≤ {TARGET_LINES}), "
          f"{len(cur)} voci su {len(base)} decisioni; TODO.md {todo_n} righe; "
          f"{len(errors)} errori")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
