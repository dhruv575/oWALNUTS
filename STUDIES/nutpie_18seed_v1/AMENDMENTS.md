# Code changes against the reused code (WP76)

`run_nutpie18.py` is WP64's portable copy of v7's `run_posteriordb.py`. Its
nutpie cell code (`nutpie_model`, `run_nutpie`, `metrics`, `failure`,
`write_cell`, `save_draws`, the reference and gate-parameter rules) is
unchanged. The changes:

- **N-1. Models and seeds.** The models are the fixed 16 from this study's
  `protocol.json`. The seeds are the 18 Linux seeds (`seeds.all`). v7's
  protocol still supplies the gates, timeout and reference rule.
- **N-2. One child process per (model, seed).** v7 used one child per
  (model, all seeds). The child is killed at 2,700 + 600 s, and a missing
  cell is recorded as `timeout_or_crash`, as in v7. The `cell` command takes
  an optional seed.
- **N-3. Commands.** `run` runs only the nutpie arm. The v7 funnel side
  check, the v7 analysis and the `checks` / `analyze` commands are removed;
  the analysis is the new `analyze_nutpie18.py`. `COMMIT` is `None`,
  because no oWALNUTS cell is run.
- **N-4. Artifacts and docstring.** Artifacts go to `artifacts/`, and the
  docstring is updated.

New files: `analyze_nutpie18.py`, `run_lane.sh`, `checksums.py` (file list)
and `.gitignore`.

## Amendments after the freeze

None. All 288 cells ran as frozen at `c7e39bb2`; no rerun, no amendment.
