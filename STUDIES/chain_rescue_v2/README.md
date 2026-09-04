# chain_rescue_v2 — WP36

Status: **pre-evidence harness implemented; conformance passed; no evidence
launched**.

`PREREGISTRATION.md`, `protocol.json`, and the superseding exact-tie correction
in `AMENDMENT-1.md` are frozen. The baseline is `17f1d97`; the harness was
implemented after core commits through `abbc519`.

The three study arms are always explicit custom warmup configurations:

- `observe` uses `ChainRescueConfig::observe_only()`;
- `current` uses `ChainRescueConfig::restart_from_best()`;
- `two_hit` uses `ChainRescueConfig::two_hit()`.

No arm inherits `DEFAULT_CHAIN_RESCUE`. All three preserve the amended source
tie rule (larger step, larger median log density, then higher chain index).

## Process and data contract

Each planned cell is one fresh child. Before spawning it, `run_rescue.py`
atomically creates an immutable launch marker. A marker or process record
forbids a rerun. The child records heartbeats around process start, load,
initialization, sampling, atomic result publication, drop, and completion.
The parent durably records stdout, stderr, timeout state, all signed/unsigned/
hex return-code forms, raw file state and hash, heartbeat validation, and
schema validation. A nonzero exit after a complete raw result is still a
process fault. A clean child that durably reports a sampler error is a valid
failing observation.

Successful raw cells include all retained unconstrained draws, every
preregistered rescue-boundary field, exact initial-position hashes, installed
position hashes, every action, final metric/tuning/diagnostic hashes, and full
work totals. Analysis uses BridgeStan to create constrained draws on every
reference parameter, saves both representations in ignored NPZ files, and
records their durable hashes in per-cell JSON.

The analysis implements the ArviZ 0.23.4 gates, type-7 reference transforms,
observe-defined stable-separated origins, raw versus credited gates, triplet
exclusions, exact sign tests, nuisance/failure scores, funnel analysis,
zero-action identity, efficiency ratios, all predictions, and the frozen
mechanical decision. `results-table.md` lists all 288 cells and
`parameters-table.md` lists every scalar reference result.

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
cargo build --release --manifest-path STUDIES/chain_rescue_v2/Cargo.toml
& 'C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\.venv\Scripts\python.exe' `
  STUDIES/chain_rescue_v2/run_rescue.py verify
```

## Commands

```text
run_rescue.py verify       # read-only environment/protocol verification
run_rescue.py conformance  # fixed non-evidence observe-vs-disabled fixture
run_rescue.py run          # launches all 288 evidence cells exactly once
run_rescue.py analyze      # reconstructs the frozen analysis without sampling
```

The deterministic non-evidence fixture passed. Its durable result is
`artifacts/conformance/observe-vs-disabled.json`: observe and rescue-disabled
execution were identical in retained draw bytes, work counters, final
adaptation hashes, retained diagnostics, and non-rescue telemetry, with zero
forbidden observe outcomes. None of the 12 registered evidence seeds has been
launched.
