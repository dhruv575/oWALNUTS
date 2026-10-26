# Code changes against the reproduced studies (WP64)

These changes were written before the freeze and are part of the
preregistration. The harness crate (`Cargo.toml`, `Cargo.lock`, `src/main.rs`,
`src/bin/funnel.rs`) is **byte-identical** to `STUDIES/posteriordb_bench_v7`.
`run_posteriordb.py` is v7's driver and `run_extension.py` is WP62's driver,
each with only the changes below. Run `diff` against the originals to check.
None of the changes touches cell metrics, gates, arms, statistics or
analysis.

## Portability (A-P1 to A-P9)

- **A-P1. Protocols are read, not copied.** `run_posteriordb.py` and
  `prepare_competitors.py` load `../posteriordb_bench_v7/protocol.json`.
  `run_extension.py` loads `../posteriordb_bench_v7_seed_extension/protocol.json`.
  This study's `protocol.json` is loaded as `STUDY`, for the commits and the
  wall label only.
- **A-P2. Paths come from environment variables, with Linux defaults.**
  - `CMDSTAN_HOME` (default `~/infra/cmdstan/cmdstan-2.39.0`)
  - `POSTERIORDB_PATH` (default `~/infra/posteriordb/posterior_database`)
  - `BENCH_MODELS` (default `./models`)
  - `OWALNUTS_HARNESS` and `OWALNUTS_FUNNEL` (default
    `./target/release/posteriordb-bench-v7` and `funnel`, with `.exe` only on
    Windows)
  - `OWALNUTS_SOURCE_TREE` (the clean worktree the harness was built from)

  v7 had hard-coded Windows paths, and its posteriordb path was relative to
  its own study directory.
- **A-P3. Windows-only settings are skipped off Windows.** `MAKE=mingw32-make`
  is set only on Windows. `bridgestan.compile.windows_dll_path_setup()` is
  called only on Windows: once in `bridgestan_model` (both drivers) and once
  in `nutpie_model`.
- **A-P4. The commit guard.** v7 required a committed `AMENDMENT-1.json` and
  `git diff` of the study repository's library source against the commit.
  WP62 did the same without the amendment. Here, the guard requires three
  things: `OWALNUTS_SOURCE_TREE`'s `HEAD` equals the full commit hash from
  this study's `protocol.json` (`f097391c…` for v7 cells, `c5c60122…` for
  extension cells); its `src/`, `integrations/`, `tests/` and `Cargo.toml`
  are clean; and the harness binary exists. A second guard, `preregistered()`,
  refuses every cell of every arm (competitors included) unless
  `PREREGISTRATION.md` and `protocol.json` are committed and unmodified.
  v7's Phase 1 had no such check. The reason for the change: the study
  repository is at `main` (`a49df800`), not at either commit.
- **A-P5. Artifact directories.** v7 cells go to `artifacts/v7/` and
  extension cells to `artifacts/ext/`. The comparison goes to
  `artifacts/reproduction/`.
- **A-P6. The extension's pooled analysis reads Linux cells.**
  `run_extension.py`'s `V7_CELLS` points at this study's
  `artifacts/v7/cells`, not the Windows v7 cells. Its pooled six-seed figure
  is therefore all-Linux.
- **A-P7. The machine record.** `measured_on.json` additionally records the
  CPU affinity, `uname` and the harness sha256 of each run. Its `note` is
  the "pinned, co-tenanted" label from `protocol.json`. In the v7 summary,
  `source_commit_under_test` comes from `protocol.json` instead of
  `AMENDMENT-1.json`.
- **A-P8. `prepare_competitors.py` builds everything.** It copies nothing
  (`COPIED = ()`), uses no `.exe` suffix off Windows, and adds a third kind,
  `owalnuts`. That kind builds the oWALNUTS BridgeStan libraries into
  `models/` with the WP46/WP48 recipe that produced v7's copied libraries
  (`posteriordb_breadth_v1/run_breadth.py::prepare_bridgestan`):
  `bridgestan.compile_model(stan, make_args=[])` with no STAN_THREADS, and
  data written as `json.dumps(posterior.data.values())`.
- **A-P9. New files.**
  - `compare_windows.py` (the Linux-vs-Windows comparison and L1–L4)
  - `run_lane.sh` (environment, pinning and the phase sequence on the box)
  - `build_harness.sh` (the clean-worktree build per commit)
  - `.gitignore` (models, draws, CmdStan output, venv)

## Amendments after the freeze

None. All 312 sampling cells and the funnel row ran as frozen at `44546ec0`;
no cell was rerun and no amendment was needed.
