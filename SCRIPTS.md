# Scripts — the maintenance tools

To learn topo, start from [`tutorial/`](tutorial/README.md): numbered lessons,
each run from the `CONFIG` block at its top.

`scripts/` keeps the tools that look after the repository. The first line of
each is `import _paths` (`scripts/_paths.py`): it moves to the repo root, so a
path is the same wherever the script is started from.

| script | what it does |
|---|---|
| `gen_index.py` | writes `docs/INDEX.md`; `--check` exits 1 if it is stale or the dependency rule is broken |
| `release_check.py` | exits 0 only when topo is *1.0-ready* |
| `check_map_shrink.py` | checks the local decision log and to-do list against the full text they were shortened from |
| `audit_fixtures.py` | the files the suite uses without having them in git |
| `audit_names.py` | searches the tracked files for names that identify a client |
| `21_sweep_invariants.py` | the suite's invariants on a folder of files the repo does not have; report written outside the repo |
