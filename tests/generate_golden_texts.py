"""
generate_golden_texts.py
------------------------
Genera i golden file per il test di regressione sui testi (`topo.model.Text`,
D138, letti dall'adapter DXF). Snapshot di `topo_dxf.load_dxf(...).texts`
dopo heal() e anchor_texts(). Lo schema è quello di
`tests/real/test_golden_texts.text_dict`.

DXF sorgente: tests/data/*.dxf (quelli che contengono testi)
Golden JSON:  tests/data/golden/texts/

Runna UNA VOLTA quando sei soddisfatto della lettura corrente, e mai per far
passare un test senza aver prima verificato che l'output è giusto.

    python generate_golden_texts.py            # genera solo i mancanti
    python generate_golden_texts.py --force    # rigenera tutti
    python generate_golden_texts.py --only gamba_tavolo
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import ezdxf

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import topo
import topo_dxf
from topo.tools.anchor import anchor_texts
from tests.real.test_golden_texts import sort_key, text_dict

EXAMPLES_DIR = project_root / "tests" / "data"
GOLDEN_DIR = EXAMPLES_DIR / "golden" / "texts"
# I DXF sorgente vivono sotto tests/data/ o tests/data/golden/.
_SOURCE_DIRS = [EXAMPLES_DIR, EXAMPLES_DIR / "golden"]

_TEXT_DXF_TYPES = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER"}


def _has_texts(dxf_path: Path) -> bool:
    try:
        msp = ezdxf.readfile(dxf_path).modelspace()
    except Exception:
        return False
    return any(e.dxftype() in _TEXT_DXF_TYPES for e in msp)


def generate(force: bool = False, only: str = None) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    seen = set()
    for d in _SOURCE_DIRS:
        for f in sorted(d.glob("*.dxf")):
            if f.stem in seen or "_healed" in f.stem:
                continue
            seen.add(f.stem)
            candidates.append(f)
    dxf_files = [f for f in candidates if _has_texts(f)]
    if only:
        dxf_files = [f for f in dxf_files if f.stem == only]

    generated = skipped = failed = 0
    for dxf_path in dxf_files:
        golden_path = GOLDEN_DIR / f"{dxf_path.stem}.json"
        if golden_path.exists() and not force:
            print(f"  SKIP (esiste): {dxf_path.name}")
            skipped += 1
            continue
        try:
            doc = topo_dxf.load_dxf(dxf_path, explode_inserts=True, flatten_z=True,
                                 verbose=False)
            result = topo.heal(doc)
            anchor_texts(result)
            texts = result.texts if result.texts else doc.texts
            entries = sorted((text_dict(t) for t in texts), key=sort_key)
            golden = {
                "source_file": dxf_path.name,
                "text_count": len(entries),
                "by_source_kind": dict(Counter(e["source_kind"] for e in entries)),
                "cluster_count": result.cluster_count,
                "texts": entries,
            }
            golden_path.write_text(
                json.dumps(golden, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"  OK: {dxf_path.name} → {len(entries)} testi {golden['by_source_kind']}")
            generated += 1
        except Exception as ex:
            import traceback
            print(f"  ERRORE: {dxf_path.name} — {ex}")
            traceback.print_exc()
            failed += 1

    print(f"\nGenerati: {generated}  Skippati: {skipped}  Errori: {failed}")
    print(f"Golden in: {GOLDEN_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only", type=str, default=None)
    args = parser.parse_args()
    generate(force=args.force, only=args.only)
