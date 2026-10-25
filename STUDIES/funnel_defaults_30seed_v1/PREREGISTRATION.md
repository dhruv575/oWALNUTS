# WP53 `funnel_defaults_30seed_v1` — preregistration

Frozen 2026-10-25, committed before the first evidence cell. `protocol.json`
is the machine-readable copy and wins on any discrepancy.

## Why

The house funnel side check (Neal's 10-D funnel at sampler defaults, 4 x
2,000 warmup / 20,000 retained, starts omega in {-3,-1,1,3}, exact
P(omega < -5) = 0.0478, gate |z| <= 2; `STUDIES/posteriordb_bench_v6/PREREGISTRATION.md`)
has only ever been run on 3 seeds per study. WP49 ran the shipped default on
12 seeds and saw z = -4.21 on one (94902) and 5/12 gross-safe seeds; fixed
`delta = 2` gave 1.141x ESS/gradient over the 17 posteriordb models but 34 vs
11 funnel divergences. WP42 found `delta = 0.5` helps the funnel (1.385x) but
costs 0.936x over the 17. Nobody has measured whether the shipped default's
tail estimate is calibrated at a sample size that separates "fine" from
"biased by 1 sigma".

## Library under test

Branch `wt/funnel-defaults`, fast-forwarded to `main` `e89f54b9` before the
build (on the coordinator's instruction), so the build includes `f097391c`
(`Init::default()` = `best_of(16)`; `NonfinitePositionPolicy::RejectLeaf`
default). The funnel check passes explicit house starts, so the Init default
does not enter; RejectLeaf is live and its rejection counts are recorded per
chain. Kernel revision `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`.
No library change.

## Arms (differ only in `delta` = `Tuning::max_error`)

| arm | builder |
|---|---|
| `default` | `Tuning::default()` (delta 1, shipped) |
| `delta2` | `Tuning::default().max_error(2.0)` |
| `delta0.5` | `Tuning::default().max_error(0.5)` |

All other settings are the shipped defaults: `Adaptation::default()`,
`Metric::diagonal()`, `Limits::admit_worst_case()`, four chains, four threads.
Binary: `src/bin/funnel.rs`, the funnel density and z statistic of
`STUDIES/init_rule_v1/src/bin/funnel.rs` / `STUDIES/adaptive_delta_v1`, with
the arm, budget, all-coordinate ESS/R-hat, end-of-warmup steps and
`Posterior::chain_warnings()` added.

## Seeds

30 fresh seeds 530101–530130. `git grep -lwE '5301(0[1-9]|[12][0-9]|30)'` over
every tracked file of `e89f54b9` (artifacts included): no hit. Regex over the
2,019 `protocol.json`/`PREREGISTRATION.md` files of every worktree and of
`C:\dev\owalnuts\STUDIES`: no hit.

## Cells (strictly sequential, one process each, never rerun)

- **Block A (core, decides R1/R2)**: 4 x 2,000/20,000, arms `default`,
  `delta2`, seeds ascending, within a seed `default` then `delta2`. 60 cells.
- **Block B (companion)**: 4 x 1,000/1,000, arms `default`, `delta2`,
  `delta0.5`, seeds ascending, in that arm order. 90 cells. Coordinator scope
  rule: block B runs only if block A finishes within 2.5 h of the freeze;
  otherwise it is recorded as not run.

Per cell: tail-mass z (MCSE), P(<-6) z, batch-means z, omega variance,
divergences, depth caps, exhaustions, invalid stops, nonfinite rejections,
min bulk / tail ESS and max R-hat over all 10 coordinates, gradients,
end-of-warmup step per chain, `chain_warnings`. An errored cell counts as
|z| > 2 and not gross-safe.

## Calibration tests (per arm, 30 block-A z values)

Exceedance k = #{|z| > 2} with the exact binomial tail P(X >= k | 30, 0.0455);
mean z with mean x sqrt(30) ~ N(0,1); sd (n-1) with the two-sided chi-square
variance test (29 df); one-sample KS against N(0,1). "Consistent with N(0,1)"
= all three p-values (mean, variance, KS) >= 0.05. Text histogram, unit bins
on [-5, 5].

## Predictions (written before any evidence cell)

- **P1** default |z| > 2 exceedance over 30 seeds in 2–6 seeds (5–20 %).
- **P2** default mean z in [-0.4, 0.4] and sd in [0.7, 1.4].
- **P3** delta2 exceedance <= default's + 2 seeds.
- **P4** delta2 block-A total retained divergences <= 3 x default's (if
  default has 0, held iff delta2 has 0).
- **P5** at 1,000/1,000 (block B totals): `delta0.5` strictly fewest
  divergences, `delta2` strictly most.

## Decision rules (frozen)

- **R1** If default's block-A exceedance exceeds 20 % (k > 6/30) or
  |mean z| > 0.5, the headline is a calibration failure of the shipped
  default, with the direction of bias.
- **R2** Recommend `delta = 2` as a default candidate for a posteriordb
  confirmation iff (a) its block-A exceedance <= default's + 2, (b) its
  |mean z| <= 0.5, and (c) its pooled block-A retained divergence rate
  (total divergences / (30 x 4 x 20,000)) < 0.1 %.
- **No default flip** in this study under any outcome.

## Disclosed pre-freeze runs (non-evidence)

Default 2,000/20,000 on WP49 seed 94902 reproduced WP49's cell exactly (z
-4.21, 3,233,034 calls), before and after the merge of main; delta2 on 94902
(z -0.09, pre-merge); default and delta0.5 1,000/1,000 on seed 5 (pipeline).
Uncommitted, in the session scratchpad. The WP49 and WP42 results were known
when the predictions (the task's) were written.
