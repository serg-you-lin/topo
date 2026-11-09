# Numbered scripts — the API playground

A series of standalone scripts in `scripts/`, one per area of `topo.__all__`.
Each has a `CONFIG` block at the top (INPUT, tolerance, NAME_ROLES) and runs
with no arguments:

```
python scripts/00_inspect.py
```

Default inputs point to `tests/examples/`. Outputs go to
`pipeline_output/` (ignored by git).

**Paths — one way only.** The first line of every script is `import _paths`
(see `scripts/_paths.py`, which is not part of the package): it calls `os.chdir()` to the repo root, so
from the command line, from VS Code's Run button or from a terminal opened in
another folder the behaviour is identical. In the `CONFIG` block you write the
raw path and nothing else:

```python
import _paths  # noqa: F401

INPUT  = r"tests/examples/Multifeature.dxf"   # relative → resolved from the repo
INPUT  = r"C:\job\client_drawing.dxf"         # absolute → used as is
OUTDIR = r"pipeline_output"                   # written to <repo>/pipeline_output
```

| # | script | topo functions | what it shows |
|---|--------|----------------|---------------|
| 00 | `00_inspect.py` | `topo_dxf.inspect_file`, `topo_dxf.inspect_dxf`, `inspect_document`, `inspect_result` | the 3-level inspector — the first tool to use on a file that does not add up |
| 01 | `01_load_and_validate.py` | `topo_dxf.load_dxf`, `topo_dxf.document_from_msp`, `validate_document` | open a file → `Document`; validate the input |
| 02 | `02_heal.py` | `heal`, `validate_result` | topology reconstruction → parts, outer/inner tree (no holes) |
| 05 | `05_to_dxf.py` | `topo_dxf.to_dxf` | render the model into a new DXF; `filter_cluster`, `include_trash` |
| 06 | `06_split.py` | `split` + `topo_dxf.to_dxf` | one `Result` per part (pure, format-free), then one DXF each; `namer`, `exclude_types` |
| 07 | `07_split_to_files.py` | `heal` → `split` → `to_dxf` | the full multi-part pipeline on disk |
| 09 | `09_export.py` | `to_json`, `save_json(extra=)` | the Result's facts as JSON, geometry only (D230) |
| 11 | `11_batch_heal.py` | `topo_dxf.load_dxf` + `heal` + `topo_dxf.to_dxf` | heal every DXF in a folder → `X_healed.dxf` + `.json` alongside |
| 12 | `12_to_svg.py` | `to_view_model`, `to_svg`, `save_svg` | JSON for an external renderer + SVG of the model |
| 14 | `14_style_classification.py` | `RoleRule`, `name_rules`, `load_dxf(role_rules=...)` | assign the role from name, hatching, colour or a combination (D63) |
| 16 | `16_strips_on_fixture.py` | `tools.strips` (experimental) | four strips between a disc and the empty region containing it; the policy lives in the script (D134, D142) |
| 17 | `17_rotate_to_longest_outer.py` | `rotate_to_longest` (outside `__all__`, D46), `tools.rotate.longest_structural_segment` | rotate an already healed `Result` so the longest side of the outer is horizontal |
| 18 | `18_outer_scan.py` | `core.readings.outer_scan.outer_candidate_edges` (not exported) | outer-boundary candidates by ray casting — the idea the island reading grew from, no longer used by `outlines()` |
| 20 | `20_outlines.py` | `heal(...).outlines()`, `experimental.read_outlines` | the contour reading (`outlines()`) on every drawing in `tests/examples/islands`, one DXF layer per decision |
| 21 | `21_sweep_invariants.py` | `heal` (`faces()`, `outlines()`), `tests/invariants.py` | the suite's invariants on a folder of drawings the repo does not have (a drawing whose content the repo already holds is skipped), each drawing in a separate process with a time limit; report written outside the repo |

`11_batch_heal.py` accepts a folder as an argument (`python
scripts/11_batch_heal.py path/`) and `--tol`; with no arguments it processes
`tests/examples/`. It skips files already named `*_healed`.

The domain types (`Result`, `Cluster`, `Contour`, `Document`,
`Text`) are shown inline inside the scripts.
