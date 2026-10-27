# WP96 archived analytic scale-CDF diagnostic plan

2026-10-27. Written and committed before computing this supplemental diagnostic's
outcomes. WP96's original failed verdict is already known. This is a post-hoc
explanation/precision diagnostic, not a qualification, rerun or altered decision.
No new sampler work, remote compute or source-artifact mutation.

## Complete fixed selection

- All original scored ticks, excluding tick zero: 25,50,...,2000.
- Both streams (shift then control), original four policies (frozen,m100,m500,trig),
  both original seeds (960101,960102), K=200 per chain.
- 160 distinct reference origins and 1,280 warm rows. No new tick selection,
  discarded failure, replacement seed or thinning.
- Preserve recorded reference kept-chain selection and warm carried-chain/noise
  row mapping exactly as WP96's original analyzer. Compact files contain
  mu,log_sigma,h_last; no beta or full-return calculation is possible from them.

## Estimators and comparisons

Use the analytic mixture scale CDF and log-coordinate Brent inversion already
validated in the bounded WP88 diagnostic. Same raw posterior draws underlie both
estimators. Preserve original innovation seeds and NumPy quantile interpolation.

Report three distinct comparisons at every row:

1. Original noise-added warm quantiles against original noise-added reference:
   reproduction of original errors and accuracy/stuck-chain clauses.
2. Original noise-added warm quantiles against analytic-CDF reference.
3. Analytic-CDF warm quantiles against analytic-CDF reference.

The last two isolate the warm-estimator effect with a common reference; the first
preserves the original qualification record. Retain original reference status,
kept/flagged chains, seed/attempt and predictive Rhat; warm chain identities,
divergences, adaptation flag and timing; original stuck-chain flags; and original
2% P50/5% P95 indicator. The stuck-chain diagnostic uses medians of log_sigma and
h_last, so it is unaffected by predictive marginalization.

Summarize by policy, stream, half and seed, retaining all 40 scheduled rows per
seed/half (80 pooled). Report each estimator's signed bias, absolute errors, both
endpoint MCSEs, within-band counts and the descriptive 95%-pooled/90%-per-seed
indicator. These counterfactual indicators cannot change WP96's frozen verdict.
Missing/bad files or timeout rows remain in denominators and are never imputed.

## Numerical checks and uncertainty

Run analytic one-component/identical-component fixtures before loading archive
draws. For each mixture require finite positive innovation scales, expected raw
shape, no duplicate tick records, monotone CDF on a fixed grid, valid brackets
and root residual <=1e-10. Use all recorded compact draws; no subsampling.

Reference and warm analytic-quantile MCSE: ArviZ chain-aware mean MCSE of each
draw's CDF contribution divided by the mixture scale density at the root.
Original noisy-quantile MCSE: ArviZ quantile MCSE, following WP96. Warm-chain MCSE
is an asymptotic diagnostic, especially at K=200; it cannot prove independence,
remove warm-start bias, or establish an automatic stopping policy. Signed error
averaged across dependent ticks is descriptive, not an iid significance test.

All arms share finite-draw same-sampler references. Independent-sampler validation
is not supplied here. Store reference uncertainty with each origin and link every
warm row to it; do not confuse reference precision with model correctness.

## Resources and provenance

Five-minute local computation ceiling. Process stream then increasing tick, then
policy, then seed. Check budget before each origin/row and inside root evaluation;
preserve budget-exhausted rows. No qualification timing from this laptop. Report
local analysis time and per-origin processing time separately from stored sampler
timing. Preserve source/plan/protocol/analyzer/log/raw-file hashes and package
versions; verify input hashes after the analysis. Original artifacts remain
read-only. If an archived original per-tick report exists, check its errors and
accuracy flags against comparison 1 and retain any mismatch as a failure.

The next decision is whether removing innovation-simulation noise explains a
material portion of the finite-precision failures, before spending compute on
larger K. A favorable post-hoc result still needs a separately frozen experiment.
