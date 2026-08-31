# Preregistration — invalid-evaluation parity v1 (kernel v10)

Frozen 2026-08-31 after commit `452befb` (kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`) and before any sampling
in this directory.

## What changed and what this study tests

WP2b found that a `TargetError::recoverable` result stopped the whole
transition (`StopReason::InvalidEvaluation`, counted as a divergence) whereas
upstream walnutpie maps a failed evaluation to `logp = -inf`, `grad = 0` and
simply refines the micro-step. Kernel `v10` adopts the upstream rule, proven
leaf-by-leaf by `oracle/walnutpie/f5bba365_invalid_leaves` (4,000 upstream
leaves, 343 touching the wall, 1e-11 agreement). This study checks the
consequences at the sampler level. It is a validation study, not a benchmark.

## Three sub-studies (each a frozen copy of an existing runner)

1. `truncated/` — 2-D `N(0, I)` restricted to `x_0 > 0` purely through
   recoverable errors. Fixed tuning (h=0.9, δ=0.5, 6 levels, depth 6), 4
   chains × 500/50,000, base seed 90031.
   Gates: every retained draw has `x_0 > 0`; zero retained invalid-evaluation
   stops and divergences; recoverable failures > 0 and equal to
   `zero_density_evaluations`; rank R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on
   `x_0`, `x_1`; |z| ≤ 3 for the four moments (`E[x_0] = sqrt(2/π)`,
   `Var[x_0] = 1 − 2/π`, `E[x_1] = 0`, `Var[x_1] = 1`) with MCSE from ESS.
   Prediction: all pass (a `v9`-style kernel would either make no moves near
   the wall or, with the old stop path, still be unbiased but with many
   no-op transitions).
2. `stock_watson/` — WP2b's arms F (fixed paper tuning) and A (Appendix C
   adaptation, paper-mode `v3` defaults) on the same simulated series
   (`data.json`, SHA-256 `df90ca84…a70b4`), **without** the finite-penalty /
   gradient-clipping / exponent-bound emulation: the target returns
   `TargetError::recoverable` naturally. Base seeds 90011 (F) and 90021 (A);
   4 chains × 500/2,000; 4 threads; same gates as WP2b.
   Predictions: retained invalid-evaluation stops = 0 in both arms
   (WP2b's recoverable-policy runs had 65–100% no-op transitions); recoverable
   failures > 0 and equal to `zero_density_evaluations`; arm A passes every
   gate as in WP2b; arm F's statistical gates pass as in WP2b, its
   energy-range headline may differ because interior wall points no longer
   enter the Hamiltonian extrema; bulk ESS per call within ±30% of WP2b for
   the same arm (A: 211/M calls, F: 104/M calls).
3. `funnel/` — WP6's arm F at the paper tuning (h=0.36, δ=0.21, 10 levels,
   depth 10) on `v10`, 4 chains × 2,000/20,000, base seed 90001.
   Gates: P(ω<−5) within ±0.012 of 0.0478, P(ω<−6) within ±0.008 of 0.0228,
   var(ω) ∈ [8.2, 9.8], zero retained divergences, R-hat ≤ 1.01, ESS ≥ 400.
   Prediction: passes; the funnel never returns a recoverable error at this
   tuning, so `v10` must reproduce `v9`'s unbiased result.

## Amendment 1 (before any sampling)

The truncated runner's first invocation failed admission
(`ResourceLimit: target-evaluation bound exceeds its resource limit`) because
depth 6 × 6 levels × 4 × 50,500 transitions exceeds the conservative 113M
preflight ceiling; zero target callbacks were made. The runner now uses
`preflight_chains_with_target_budget` / `sample_chains_with_target_budget`
with the exact worst-case bound as admission limit and a 1e9 runtime callback
cap, exactly as the funnel and Stock–Watson runners do. Tuning, draws and
seeds are unchanged.

## Amendment 2 (post-hoc, after the preregistered arms were interpreted)

The preregistered truncated arm passed every gate but its two `x_0` moments
sat at +2.41 and +2.23 standard errors with the same sign. To distinguish
sampling variation from a bias, a **post-hoc, non-evidence** replicate was
run on fresh base seed 90041 with identical tuning and draws
(`truncated/protocol-posthoc-T2.json`, artifact `truncated/artifacts/T2.json`,
summary `summary-T2.json`). To run it the truncated runner gained a
`PROTOCOL_FILE` environment-variable override (default unchanged) and
`analyze.py` an optional artifact-name argument; the preregistered artifact
`T.json` was produced before either change and is untouched. Result: `x_0`
mean z −0.12, variance z −0.11; the offset did not replicate.

## Deviations policy

Any deviation from the above is recorded in this file before the affected
artifact is interpreted. Artifacts are create-only; the runners refuse to
overwrite. Seeds 90001–90034 were checked against every ledger and study in
the repository before freezing and are consumed once.
