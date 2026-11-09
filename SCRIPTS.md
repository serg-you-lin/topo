# Script numerati — palestra dell'API

Serie di script standalone in `scripts/`, uno per area di `topo.__all__`.
Ognuno ha un blocco `CONFIG` in testa (INPUT, tolleranza, NAME_ROLES) e gira
senza argomenti:

```
python scripts/00_inspect.py
```

Gli input di default puntano a `tests/examples/`. Gli output vanno in
`pipeline_output/` (ignorato da git).

**Percorsi — un solo modo.** La prima riga di ogni script è `import _paths`
(vedi `scripts/_paths.py`): fa `os.chdir()` alla radice del repo (non fa parte del package), quindi da
riga di comando, dal pulsante Run di VS Code o da un terminale aperto in
un'altra cartella il comportamento è identico. Nel blocco `CONFIG` si scrive il
percorso grezzo e basta:

```python
import _paths  # noqa: F401

INPUT  = r"tests/examples/Multifeature.dxf"   # relativo → parte dal repo
INPUT  = r"C:\job\disegno_cliente.dxf"        # assoluto → usato com'è
OUTDIR = r"pipeline_output"                   # scritto in <repo>/pipeline_output
```

| # | script | funzioni topo | cosa mostra |
|---|--------|----------------|-------------|
| 00 | `00_inspect.py` | `topo_dxf.inspect_file`, `topo_dxf.inspect_dxf`, `inspect_document`, `inspect_result` | l'ispettore a 3 livelli — il primo strumento su un file che non torna |
| 01 | `01_load_and_validate.py` | `topo_dxf.load_dxf`, `topo_dxf.document_from_msp`, `validate_document` | aprire un file → `Document`; validare l'input |
| 02 | `02_heal.py` | `heal`, `validate_result` | ricostruzione topologia → parti, albero outer/inner (niente fori) |
| 05 | `05_to_dxf.py` | `topo_dxf.to_dxf` | render del modello in un DXF nuovo; `filter_cluster`, `include_trash` |
| 06 | `06_split.py` | `split` + `topo_dxf.to_dxf` | un `Result` per parte (puro, senza formato), poi un DXF ciascuno; `namer`, `exclude_types` |
| 07 | `07_split_to_files.py` | `heal` → `split` → `to_dxf` | pipeline multi-pezzo completa su disco |
| 09 | `09_export.py` | `to_json`, `save_json(extra=)` | i fatti del Result in JSON, solo geometria (D230) |
| 11 | `11_batch_heal.py` | `topo_dxf.load_dxf` + `heal` + `topo_dxf.to_dxf` | heal di tutti i DXF di una cartella → `X_healed.dxf` + `.json` a fianco |
| 12 | `12_to_svg.py` | `to_view_model`, `to_svg`, `save_svg` | JSON per un renderer esterno + SVG del modello |
| 14 | `14_style_classification.py` | `RoleRule`, `name_rules`, `load_dxf(role_rules=...)` | assegnare il ruolo da nome, tratteggio, colore o una combinazione (D63) |
| 16 | `16_strips_on_fixture.py` | `tools.strips` (sperimentale) | quattro strisce fra un disco e la regione vuota che lo contiene; la politica sta nello script (D134, D142) |
| 17 | `17_rotate_to_longest_outer.py` | `rotate_to_longest` (fuori da `__all__`, D46), `tools.rotate.longest_structural_segment` | ruota un `Result` già sano così il lato più lungo dell'outer è orizzontale |
| 18 | `18_outer_scan.py` | `core.readings.outer_scan.outer_candidate_edges` (non esportato) | candidati a bordo esterno per ray casting — idea da cui è nata la lettura per isole, oggi non usata da `outlines()` |
| 20 | `20_outlines.py` | `heal(...).outlines()`, `experimental.read_outlines` | lettura per contorni (`outlines()`) su tutti i disegni di `tests/examples/islands`, un layer DXF per decisione |
| 21 | `21_sweep_invariants.py` | `heal` (`faces()`, `outlines()`), `tests/invariants.py` | le invarianti della suite su una cartella di disegni che il repo non ha (stesso contenuto saltato), ogni disegno in un processo a parte con tempo massimo; rapporto fuori dal repo |

`11_batch_heal.py` accetta una cartella come argomento (`python
scripts/11_batch_heal.py path/`) e `--tol`; senza argomenti processa
`tests/examples/`. Salta i file già `*_healed`.

I tipi di dominio (`Result`, `Cluster`, `Contour`, `Document`,
`Text`) sono mostrati inline dentro gli script.
