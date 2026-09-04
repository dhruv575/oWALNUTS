# chain_rescue_v2 — WP36

Status: **pre-evidence review fixes implemented; evidence remains blocked
unless authenticated hit-path conformance passes; no evidence launched**.

`PREREGISTRATION.md`, `protocol.json`, and the superseding clarifications in
`AMENDMENT-1.md` and `AMENDMENT-2.md` are frozen. The baseline is `17f1d97`;
the harness was implemented after core commits through `abbc519`.

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
work totals. Analysis uses BridgeStan to create constrained draws on every
reference parameter, saves both representations in ignored NPZ files, and
records their durable hashes in per-cell JSON.

The constrained NPZ/hash covers every BridgeStan constrained parameter, not
only the reference subset. Unconstrained and constrained names, shapes, and
name hashes are recorded. Funnel records and hashes all ten dimensions in both
coordinate labels.

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
run_rescue.py prepare-provenance # one-time audited build/input manifests
run_rescue.py verify       # authenticate current files/manifests/conformance
run_rescue.py conformance  # fixed non-evidence observe-vs-disabled fixture
run_rescue.py run          # launches all 288 evidence cells exactly once
run_rescue.py analyze      # reconstructs the frozen analysis without sampling
```

## Clean-checkout preparation

1. Check out the harness implementation commit with a clean worktree.
2. Set the path variables above if the read-only WP35 assets are elsewhere.
3. Use the exact audited WP35 Python environment (Python 3.11.16, ArviZ
   0.23.4, NumPy 2.4.6, BridgeStan 2.9.0, posteriordb 0.2.0).
4. Run the Rust/Python tests.
5. Run `prepare-provenance` once. It freezes every model/data size and SHA-256,
   the clean posteriordb HEAD/tree, package versions, protocol/amendment
   hashes, audited source files, and GNU Rust 1.88 release executables. It also
   performs an isolated rebuild and compares full PE files or every PE section.
6. Run `conformance`; it archives the prior conformance result, exercises a
   deterministic observed-hit trap, and publishes a manifest-bound result.
7. Run `verify`.

`verify` is read-only authentication of the current source, inputs, release
executables, and current conformance artifact. It does not rerun or overwrite
the immutable archived conformance history. `run` calls the same verification
and refuses evidence unless the current authenticated artifact is a hit-path
PASS.

The earlier no-hit fixture result is retained as immutable conformance history.
None of the 12 registered evidence seeds has been launched.
