"""
21_sweep_invariants.py — le invarianti della suite su una cartella di disegni
============================================================================

Le promesse che la suite controlla sui disegni del repo (tests/invariants.py,
D143, D158), provate su disegni che il repo non ha: ogni DXF della cartella,
letto con `heal()` e con `outlines()` (due letture, mai in fila), che il
repo non contenga già (stesso contenuto). Per ogni lettura:

    raises      la lettura non solleva
    polygon     ogni outer e inner è una forma semplice di area positiva
    dropped     ogni pezzo d'ingresso sta in un'uscita (entro la tolleranza)
    out once    nessun tratto di `loose` corre lungo un contorno (D137)
    scrambled   rimescolato, ruotato, lontano e specchiato: stessi contorni

Ogni disegno gira in un processo a parte con un tempo massimo: un disegno
che si pianta o fa cadere l'interprete diventa una riga del rapporto, non
ferma la passata. Fuori dalla suite: si lancia a mano. Il rapporto va in
OUTDIR, fuori dal repo (i nomi dei file possono essere del cliente).

    python scripts/21_sweep_invariants.py <cartella> <outdir> [--skip testo ...]
"""

import _paths  # noqa: F401  — chdir alla radice del repo

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(_paths.ROOT))

HEAL_TOLERANCE = 0.5     # come tests/unit/core/test_heal_invariants.py
MAX_GAP = 0.5            # come tests/unit/core/test_island_invariants.py
TIMEOUT = 300            # secondi per disegno, tutte e due le letture


def _digest(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _known_digests() -> set:
    """Il contenuto di ogni DXF già sotto tests/ (tracciato o no)."""
    return {_digest(p) for p in Path("tests").rglob("*") if p.suffix.lower() == ".dxf"}


def _polygon_problems(result) -> list:
    from topo import to_shapely
    found = []
    for ci, cluster in enumerate(result.clusters):
        for name, contour in [("outer", cluster.outer)] + [(f"inner[{i}]", c) for i, c in enumerate(cluster.inners)]:
            poly = to_shapely(contour)
            if not poly.is_valid or poly.area <= 0:
                found.append(f"cluster[{ci}].{name} {tuple(round(v, 2) for v in poly.bounds)}")
    return found


def _check_reading(name: str, doc, read, distance: float, band: float) -> dict:
    """Le invarianti di una lettura: {controllo: [problemi]}, più tempo e conti."""
    from tests.invariants import along_contours, contours, scrambled, shape_differences, uncovered, unscrambled
    out = {"checks": {}}
    start = time.perf_counter()
    try:
        result = read(doc)
    except Exception as exc:  # noqa: BLE001  — una lettura che solleva è il difetto
        out["checks"]["raises"] = [f"{type(exc).__name__}: {exc}"]
        return out
    out["seconds"] = round(time.perf_counter() - start, 2)
    out["clusters"], out["loose"], out["is_valid"] = len(result.clusters), len(result.loose), result.is_valid
    checks = out["checks"]
    checks["polygon"] = _polygon_problems(result)
    lost = uncovered(doc, result, distance)
    checks["dropped"] = [f"{lost.length:.3f} mm vicino a {lost.representative_point()}"] if lost.length > band else []
    checks["out once"] = [f"{length:.2f} mm a {point}" for length, point in along_contours(result, doc)[:5]]
    try:
        again = read(scrambled(doc))
        outers, inners = contours(result)
        outers2, inners2 = ([unscrambled(p) for p in ps] for ps in contours(again))
        diff = []
        if len(again.clusters) != len(result.clusters):
            diff.append(f"isole {len(result.clusters)} -> {len(again.clusters)}")
        for what, a, b in (("outer", outers, outers2), ("inner", inners, inners2)):
            lost_shapes = shape_differences(a, b, band) + shape_differences(b, a, band)
            if lost_shapes:
                diff.append(f"{what} {len(a)} -> {len(b)}, cambiano {lost_shapes[:3]}")
        checks["scrambled"] = diff
    except Exception as exc:  # noqa: BLE001
        checks["scrambled"] = [f"solleva {type(exc).__name__}: {exc}"]
    return out


def check_one(path: Path) -> dict:
    """Le due letture di un disegno, con le loro invarianti."""
    import topo
    import topo_dxf
    from topo.core.topology.noding import GRAPH_EPSILON
    from topo.core.primitives.segments import DEFAULT_TOLERANCE
    report = {}
    try:
        heal_doc = topo_dxf.load_dxf(str(path), upgrade=True, explode_inserts=True, flatten_z=True,
                                     tolerance=HEAL_TOLERANCE)
        island_doc = topo_dxf.load_dxf(str(path))
    except Exception as exc:  # noqa: BLE001  — un file che non si apre non è un difetto di lettura
        return {"load": f"{type(exc).__name__}: {exc}"}
    report["edges"] = len(heal_doc.edges)
    report["heal"] = _check_reading("heal", heal_doc, lambda d: topo.heal(d, tolerance=HEAL_TOLERANCE).faces(),
                                    HEAL_TOLERANCE, 2 * DEFAULT_TOLERANCE)
    report["island"] = _check_reading("island", island_doc, lambda d: topo.heal(d, max_gap=MAX_GAP).outlines(),
                                      MAX_GAP, 2 * (DEFAULT_TOLERANCE + GRAPH_EPSILON))
    return report


def _failures(report: dict) -> list:
    if "load" in report:
        return []
    return [f"{reading}.{check}" for reading in ("heal", "island")
            for check, problems in report.get(reading, {}).get("checks", {}).items() if problems]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("outdir")
    parser.add_argument("--skip", nargs="*", default=[], help="salta i percorsi che contengono questi testi")
    parser.add_argument("--one", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.one:
        print(json.dumps(check_one(Path(args.one)), default=str))
        return
    folder, outdir = Path(args.folder).resolve(), Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    known, seen, todo = _known_digests(), set(), []
    for path in sorted(p for p in folder.rglob("*") if p.suffix.lower() == ".dxf"):
        rel = path.relative_to(folder).as_posix()
        if any(s in rel for s in args.skip) or "/.git/" in f"/{rel}":
            continue
        digest = _digest(path)
        if digest in known or digest in seen:
            continue
        seen.add(digest)
        todo.append((rel, path))
    print(f"{len(todo)} disegni da provare (nuovi per contenuto)", flush=True)
    reports, log = {}, open(outdir / "sweep.log", "w", encoding="utf-8")
    for i, (rel, path) in enumerate(todo, 1):
        start = time.perf_counter()
        try:
            run = subprocess.run([sys.executable, __file__, "x", "x", "--one", str(path)],
                                 capture_output=True, text=True, timeout=TIMEOUT)
            report = json.loads(run.stdout.strip().splitlines()[-1]) if run.returncode == 0 else \
                {"crash": f"exit {run.returncode}: {run.stderr.strip().splitlines()[-1:]}"}
        except subprocess.TimeoutExpired:
            report = {"crash": f"oltre {TIMEOUT} s"}
        report["wall"] = round(time.perf_counter() - start, 1)
        reports[rel] = report
        status = report.get("crash") or report.get("load") and f"non si apre: {report['load']}" \
            or (", ".join(_failures(report)) or "ok")
        line = f"[{i}/{len(todo)}] {rel} ({report['wall']} s): {status}"
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    (outdir / "sweep.json").write_text(json.dumps(reports, indent=1, default=str), encoding="utf-8")
    bad = [rel for rel, r in reports.items() if "crash" in r or _failures(r)]
    print(f"fatto: {len(bad)} di {len(reports)} con difetti; rapporto in {outdir}", flush=True)


if __name__ == "__main__":
    main()
