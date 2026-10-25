# Preregistration — dense_metric_confirmation_v1 (WP51)

Frozen 2026-10-25 before the first evidence cell. `protocol.json` carries the
same content in machine form; its SHA-256 is written into `summary.json` and
`CHECKSUMS.sha256`. This is a **default-flip confirmation**: if the frozen rule
below passes, the dense facade's warmup defaults are changed; otherwise nothing
changes.

Pre-freeze computations (non-evidence, seed 1 only, artifacts discarded): the
`funnel selfcheck` (200 + 200 draws), which shows that `Metric::dense()` +
`Adaptation::default()` on the library used for the cells is bit-identical to
the explicit `dense-legacy` arm and differs from `dense-candidate`; one
`eight_schools_noncentered` cell per arm and one candidate funnel cell to check
that the harness writes and analyses cells. No threshold, prediction or rule
was set from them.

## Question

WP48 (`STUDIES/dense_metric_posteriordb_v1`) found three defects in the dense
adaptive warmup, each fixed by an opt-in: one RNG stream for every warmup
transition (`DenseWarmupSeeding::PerTransition`), a shrinkage toward the mean
variance that is not scale-free (`DenseMetricRegularization::Stan`), and a
64-eps symmetry check that turns the column-wise inverse of an ill-conditioned
covariance into a spurious absolute ridge
(`WarmupConfig::with_dense_symmetrized_precision(true)`). Seeding + Stan gave
2.59x the diagonal's geomean min-bulk-ESS/gradient (42/51 gates each); the
symmetrisation was found after the run and was tested only post hoc on three
models (`diamonds` 65.7x). The package of all three was never preregistered.

**Should the dense facade's internal warmup defaults become {PerTransition,
Stan, symmetrised precision}?** `Metric::dense()` itself stays opt-in relative
to the diagonal default; no automatic switch to dense is considered.

## Change under test

`walnutpie::WarmupConfig::default()` (and therefore `WarmupConfig::new`, which
`Adaptation::default()` builds on) dense fields: `dense_warmup_seeding`
`Legacy -> PerTransition`, `dense_metric_regularization`
`MeanVarianceShrinkage -> Stan`, `dense_symmetrize_precision` `false -> true`.
These fields are read only by the dense adaptive path; the diagonal, identity
and structured paths and every diagonal fingerprint are untouched by
construction.

## Arms

| arm | configuration |
|---|---|
| `owalnuts-diag` | `Metric::diagonal()` + `Adaptation::default()` — the shipped default |
| `owalnuts-dense-legacy` | `Metric::dense()` + `Adaptation::Custom(WarmupConfig::new(0.8)` + `DEFAULT_WARMUP_EXHAUSTION` + `DEFAULT_METRIC_REGULARIZATION` + `Legacy` + `MeanVarianceShrinkage` + no symmetrisation`)` — today's dense defaults, stated explicitly (bit-identical to `Metric::dense()` + `Adaptation::default()` before the flip) |
| `owalnuts-dense-candidate` | the same with `PerTransition` + `Stan` + `with_dense_symmetrized_precision(true)` — the candidate defaults |

Every arm is stated explicitly in the harness, so the cells do not depend on
the library defaults (built from `main` at `3924b090`).

## Protocol

- posteriordb `28f8d3d` (sibling checkout, read-only), the 17 posteriors of
  `posteriordb_bench_v6` / WP48 in that order; `Tuning::default()`,
  `Init::uniform()`, `Limits::admit_worst_case()`; 4 chains x 1,000 warmup /
  1,000 retained, 4 threads, BridgeStan 2.9.0 `ReplicatedStanTarget`.
  BridgeStan libraries copied from the WP48 build of the same sources.
- Seeds **151301, 151302, 151303** (exact-word search over `main` and every
  sibling worktree's study files found no use).
- Order, strictly sequential, one cell at a time: **phase 1** — models in
  listed order, within a model `owalnuts-diag` then `owalnuts-dense-candidate`,
  seeds ascending; **funnel** — diag seeds ascending, then candidate seeds
  ascending; **phase 2** — `owalnuts-dense-legacy` over the models in listed
  order. The legacy arm is reported but does not enter the rule; it runs last
  so that the decision arms are complete first.
- Cell timeout 2,700 s (as WP48). Timeouts and errors are gate failures. No
  cell is rerun; only a cell interrupted by a process crash without a written
  artifact may be rerun, and that would be recorded.
- Gates (house, ArviZ 0.23.4): rank R-hat <= 1.01, bulk and tail ESS >= 400
  on every reference parameter, zero retained divergences, finite draws, no
  sampler error.
- Statistic: per cell, min bulk ESS over reference parameters / all target
  calls (warmup included, start search excluded); per model, the median over
  the arm's ok cells; ratio arm / diag; summary the geometric mean of the
  per-model ratios over models where both arms have at least one ok cell
  (excluded models are listed; their failed cells still count as gate
  failures).
- Funnel side check (arms diag and candidate): Neal's 10-D funnel, starts
  `omega in {-3,-1,1,3}`, 4 x 2,000 / 20,000, `P(omega < -5)` exact 0.0478,
  ArviZ-style MCSE z; a funnel cell that errors fails.
- Recorded and reported, not gating: step, depth-cap fraction, whitened
  condition number `kappa`, last-window ridge, Cholesky failures, contended
  walls and ESS/s.

## Decision rule (frozen)

**Flip** the dense facade warmup defaults to {PerTransition, Stan, symmetrised
precision} **iff all four hold**:

1. candidate / diag geomean min-bulk-ESS-per-gradient ratio **>= 1.5**;
2. candidate gate passes (of 51) **>= diag gate passes - 1**;
3. candidate funnel **|z| <= 2 on every one of the three seeds**;
4. **no model** passes 3/3 under diag and 0/3 under the candidate.

If it passes: implement the flip in `src/walnutpie.rs`; if
`tests/kernel_fingerprint.rs` covers the dense facade, record the new dense
fingerprint (the diagonal default fingerprint must not change); `cargo test`;
CHANGELOG entry naming this study; a README section documenting
`Metric::dense()` for correlated near-Gaussian regressions with the measured
ratios and the statement that dense is never switched on automatically.
If it fails: leave the three opt-ins, document the negative, recommend nothing.

## Predictions

- **P1** candidate / diag geomean >= 2.0.
- **P2** `diamonds` candidate / diag ratio >= 20.
- **P3** `accel_gp` passes 0/3 gate cells in every arm.
- **P4** candidate gate passes >= diag gate passes.
- **P5** candidate funnel |z| <= 2 on all seeds, and total candidate retained
  funnel divergences (3 seeds) <= 2x the diag total.
- **P6** (secondary) legacy / diag geomean <= 0.5 and legacy gate passes <
  diag gate passes.

## Rules

Report every cell; failures are results; no reruns or tuning after seeing
results. Walls are measured on a shared machine (up to seven agents on 16
cores) and decide nothing.
