# chain_rescue_v2 — WP36

Status: **complete; all 288 evidence cells launched exactly once; final
mechanical decision `no_rescue`**.

`PREREGISTRATION.md`, `protocol.json`, and the superseding clarifications in
`AMENDMENT-1.md`, `AMENDMENT-2.md`, and `AMENDMENT-3.md` are frozen. The
baseline is `17f1d97`; the harness was implemented after core commits through
`abbc519`.

The three study arms are always explicit custom warmup configurations:

- `observe` uses `ChainRescueConfig::observe_only()`;
- `current` uses `ChainRescueConfig::restart_from_best()`;
- `two_hit` uses `ChainRescueConfig::two_hit()`.

No arm inherits `DEFAULT_CHAIN_RESCUE`. All three preserve the amended source
tie rule (larger step, larger median log density, then higher chain index).

## Process and data contract

Each planned cell is one fresh child. Before spawning it, `run_rescue.py`
exclusively creates an immutable launch marker with create-new semantics. A
marker or process record forbids a rerun, including across concurrent
orchestrators. A process record without its authenticated marker is invalid.
The child records heartbeats around process start, load,
initialization, sampling, atomic result publication, drop, and completion.
The parent durably records stdout, stderr, timeout state, all signed/unsigned/
hex return-code forms, raw file state and hash, heartbeat validation, and
schema validation. A nonzero exit after a complete raw result is still a
process fault. A clean child that durably reports a sampler error is a valid
failing observation. Initialization errors have known zero rescue history;
run-stage errors record unknown telemetry and conservatively fail rescue
safety under Amendment 2.

Successful raw cells include all retained unconstrained draws, every
preregistered rescue-boundary field, exact initial-position hashes, installed
position hashes, every action, final metric/tuning/diagnostic hashes, and full
work totals. The raw schedule is exported from sampler metadata and validation
requires exactly all five scheduled boundaries at warmup 1,000 or all six at
warmup 2,000 for every chain; monotone but truncated telemetry is invalid.
Analysis uses BridgeStan to create constrained draws on every
reference parameter, saves both representations in ignored NPZ files, and
records their durable hashes in per-cell JSON.

The constrained NPZ/hash covers every BridgeStan constrained parameter, not
only the reference subset. Unconstrained and constrained names, shapes, and
name hashes are recorded. Funnel records and hashes all ten dimensions in both
coordinate labels.

The analysis implements the ArviZ 0.23.4 gates, type-7 reference transforms,
observe-defined stable-separated origins mapped independently by chain index
and initial hash, raw versus credited gates, triplet
exclusions, exact sign tests, nuisance/failure scores, funnel analysis,
zero-action identity, efficiency ratios, all predictions, and the frozen
mechanical decision. `results-table.md` lists all 288 cells and
`parameters-table.md` lists every scalar reference result.

## Final verdict

The registered completeness gate failed with 281 process-valid cells, seven
process faults, and six invalid triplets. `two_hit` reduced nuisance actions
but did not satisfy the registered nuisance sample-size, efficacy, funnel,
origin-safety, or efficiency requirements. No-fire passed. Independently
adjudicated predictions were P1–P5 false, P6 true, P7 false, and P8 true.
The frozen mechanical decision is **`no_rescue`**.

The original as-executed analysis is preserved in commit `b8aee0f`.
`POST-RUN-CORRECTION.md` records derived-reporting corrections, and
`LEDGER-ENTRY.md` is the final concise study record. No cell was rerun for
those corrections.

Funnel `two_hit` tail-z and half-pass requirements scan every process-valid
candidate cell, even when a sibling invalidates the triplet. The full gate is
exactly omega R-hat, omega bulk ESS, zero divergences, finite draws, and no
sampler error; tail z is separate and tail ESS is report-only. Paired-arm
full-gate count comparisons remain restricted to valid triplets. Any action
whose observe-origin metadata cannot be mapped by that chain's initial hash is
reported separately as `origin_safety_unknown`. It blocks `two_hit`'s
zero-origin safety gate, but is not `origin_overwritten`, does not remove
overwrite-based diagnostic credit, and is not a `current` fallback red line.

## External read-only assets

By default, the harness uses the existing WP35 directory:

`C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6`

It does not copy or modify those files. Paths are configurable:

- `WP36_ASSETS`
- `WP36_MODEL_DIR`
- `WP36_POSTERIORDB_PATH`
- `WP36_BIN_DIR`
- `WP36_CELL_TIMEOUT_SECONDS`

Use the WP35 virtual environment for Python/ArviZ/BridgeStan:

```powershell
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' `
  STUDIES/chain_rescue_v2/run_rescue.py verify
```

## Commands

```text
run_rescue.py verify          # prepared-worktree full-exe/input/conformance auth
run_rescue.py verify-rebuild  # fresh-build PE-section equivalence, no overwrite
run_rescue.py run             # launches all 288 evidence cells exactly once
run_rescue.py analyze         # reconstructs the frozen analysis without sampling
```

`prepare-provenance` and `conformance` are curator-only publication commands.
They use create-new output and refuse once the current immutable indexes
exist. They are not regeneration commands. Any future source or protocol
change requires a new study/version and new versioned manifests/conformance;
committed artifacts must never be overwritten.

## Clean-checkout reproduction

1. Check out the publication revision containing the immutable provenance and
   conformance indexes. Do not check out only the recorded implementation
   commit. The selected provenance index authenticates that implementation
   source commit/tree from within the complete publication revision.
   `current-post-run.json` is the active provenance index; prior immutable
   indexes remain historical records.
2. Check out posteriordb commit
   `28f8d3d6e975315f42aa274a8399f21e07a43b30` cleanly. Set
   `WP36_POSTERIORDB_PATH` to that checkout.
3. Set `WP36_MODEL_DIR` to a directory containing the seven logical
   `<posterior>__<model>_model.so` and `.data.json` pairs. The existing
   read-only WP35 model directory is accepted. For independent preparation,
   build those exact posteriordb models/data with BridgeStan 2.9.0 and retain
   the manifest filenames; verification authenticates each logical file by
   size/SHA-256, independent of absolute path.
4. Use Python 3.11.16 with ArviZ 0.23.4, NumPy 2.4.6, SciPy 1.17.1, pandas
   3.0.5, xarray 2026.7.0, xarray-einstats 0.9.1, BridgeStan 2.9.0, and
   posteriordb 0.2.0.
5. Run the Rust/Python tests, then `verify-rebuild`. It performs an isolated
   GNU Rust 1.88 release build at a fresh path and checks every PE section
   against the immutable build manifest without changing any artifact.

`verify-rebuild` proves equivalent fresh-build code even when path-dependent PE
metadata makes the complete executable hash differ. It does not authorize that
new executable for evidence. `verify` separately authenticates the prepared
launch worktree's complete executable bytes, logical external inputs, source,
and current immutable conformance artifact. `run` calls `verify` and refuses
evidence unless all prepared-worktree hashes and the hit-path PASS match.

Every versioned conformance JSON is immutable; its index authenticates the one
bound to the audited Rust binary source and build manifest. The selected
The post-run provenance index separately authenticates the corrected analysis
source and its reuse of those unchanged binaries. Earlier fixtures and indexes
remain untouched historical artifacts.
