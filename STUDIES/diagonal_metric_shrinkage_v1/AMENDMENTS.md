# Code changes against the reused code (WP81)

**Library (`f52537a1`, research-only).** Two variants are added:
`DiagonalMetricRegularization::StanLowAnchor` and `StanCoordinateCap`,
under `#[cfg(feature = "research")]`. The prior term of every rule moves
into one helper, `diagonal_prior_terms`, with the same operations in the
same order. The default and the existing variants compute bit-identically,
and the kernel fingerprints are unchanged with the feature off and on. A
unit test covers both formulas.

**Harness.** `src/main.rs` is WP80's `src/bin/telemetry.rs` (v7's
`main.rs` plus per-transition output) with three changes:

- the arms `lowanchor` and `coordcap` come from `src/arms.rs`, as
  `Adaptation::Custom` with only the regularisation switched (WP41's
  pattern);
- the arm's regularisation is recorded in the cell's `defaults`;
- the binary is named `posteriordb-cell`.

`src/bin/funnel.rs` is v7's with an arm argument. The crate enables
`owalnuts/research`.

**Driver.** `run_shrinkage.py` is WP80's `run_telemetry.py` with these
changes:

- the arms, models (house 17), seeds and commit come from `protocol.json`;
- oWALNUTS telemetry is reduced to per-chain mass, step and work (no
  per-transition arrays);
- nutpie telemetry is reduced to `mass_matrix_inv`, step, depth, n_steps
  and unconstrained draws;
- new commands: `funnel` (three arms x ten seeds) and `refscales`
  (reference draws through `param_unconstrain`).

The cell code, gates and metrics are unchanged.

**New files.** `analyze_shrinkage.py`, `run_lane.sh`, `build_harness.sh`
(builds both binaries and runs the fingerprint test off and on),
`checksums.py` and `.gitignore`.

## Amendments after the freeze

None so far.
