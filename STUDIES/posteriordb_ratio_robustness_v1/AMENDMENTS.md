# Code changes against the reused code (WP72)

These changes were written before the freeze and are part of the
preregistration. The harness crate (`Cargo.toml`, `Cargo.lock`, `src/main.rs`,
`src/bin/funnel.rs`) is **byte-identical** to `STUDIES/posteriordb_bench_v7`.
Only the `posteriordb-bench-v7` binary is built.

`run_robustness.py` is WP64's portable `run_extension.py`, which is WP62's
driver with v7's cell code. The changes:

- **R-1.** Seeds come from this study's `protocol.json` (`seeds.new`, the 12
  seeds 720701–720712). Models, gates, timeout and arm order are still read
  from `posteriordb_bench_v7_seed_extension/protocol.json`.
- **R-2.** The commit is `protocol.json` `commit.full` (`c5c60122`).
- **R-3.** Artifacts go to `artifacts/`, not `artifacts/ext/`.
- **R-4.** The WP62 analysis section and the `analyze` command are removed.
  The 18-seed analysis is the new `analyze_robustness.py`.
- **R-5.** The docstring is updated.

Cell metrics, arms, gates, the commit guard, the preregistration guard and
the machine record are unchanged from WP64.

Copied with only the study path changed: `build_harness.sh` (from WP64) and
`checksums.py` (file list). New: `run_lane.sh`, `analyze_robustness.py`,
`.gitignore`.

## Amendments after the freeze

None. All 384 cells ran as frozen at `0e42b648`; no rerun, no amendment.
