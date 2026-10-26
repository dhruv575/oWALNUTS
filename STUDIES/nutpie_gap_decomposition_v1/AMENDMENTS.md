# Code changes against the reused code (WP80)

`run_telemetry.py` is WP76's `run_nutpie18.py` (WP64's portable copy of v7's
`run_posteriordb.py`). The cell code (`run_owalnuts`, `nutpie_model`,
`run_nutpie`, `metrics`, `failure`, `write_cell`, `save_draws`, the
reference and gate-parameter rules) is unchanged except for storage:

- **T-1. Models, seeds, commit.** The telemetry models and seeds come from
  `protocol.json` (`telemetry`). `COMMIT` is c5c60122 (WP72's commit under
  test), so `amendment_commit()` checks the source tree again.
- **T-2. oWALNUTS telemetry.** The harness is the new `telemetry` binary:
  v7's `src/main.rs` plus `per_transition()`, which writes per-transition
  arrays for retained and warmup transitions. Sampling calls are unchanged.
  After the cell, the driver saves the per-chain telemetry, final mass
  diagonal, final step and work totals to `artifacts/telemetry/*.json.gz`.
- **T-3. nutpie telemetry.** `nutpie.sample(..., store_mass_matrix=True,
  store_unconstrained=True)`. Both are storage flags. Every numeric
  sample_stats variable, retained and warmup, is saved to
  `artifacts/telemetry/*-nutpie-*.npz`.
- **T-4. Commands.** `run` runs oWALNUTS then nutpie per model, with one
  child per cell (WP76's orchestration).

New files: `src/bin/telemetry.rs`, the `[[bin]] telemetry` entry in
`Cargo.toml`, `analyze_gap.py`, `run_lane.sh`, `build_harness.sh`,
`checksums.py` and `.gitignore`. `src/main.rs`, `src/bin/funnel.rs` and
`Cargo.lock` are byte-identical to v7's.

## Amendments after the freeze

None so far.
