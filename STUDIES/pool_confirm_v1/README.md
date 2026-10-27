# WP97: confirmation of likelihood-reweighted tick pooling

**K = 200 transitions per chain, with an exponential pool of 10 or 20 ticks,
passes the frozen predictive-scale rule on both fixed datasets. No smaller K
qualifies on both.** At H = 10, the simulated series passes 300/300 scheduled
seed/tick pairs and the real series 294/300, at median library-plus-pooling
component times of 79.7 ms and 306.2 ms. H = 20 passes 300/300 and 296/300,
at 84.0 ms and 311.3 ms.

Pooling improves the real-series accuracy at K = 200: the unpooled control passes
only 261/300 (87.0%). It does not establish the hoped-for reduction to K = 20 or
50 across both series. In particular, real K = 50/H = 20 reaches 283/300,
two observations short of the unchanged 285/300 requirement. Sim K = 50/H = 20
has 294/300 successful ticks but fails the drift criterion.

These are P50/P95 quantiles of the **next-period Student-t scale**
`exp(h_next/2)`. The historical protocol calls its accuracy criterion the
"quote rule". They are not executable spreads, return quantiles, inventory
limits, or a profitability result. Student-t(5) conditional return variance is
`(5/3) * exp(h_next)`; predictive returns also integrate location and return noise.

## Frozen experiment

The study confirms WP93's post-hoc per-lag-normalized likelihood-reweighting
estimator, with exponential lag weights as primary and uniform weights secondary.
Each stale cohort is propagated through the AR(1) latent process and weighted by
the intervening observed returns. Weights are normalized within each cohort
before the lag weights mix cohorts. The newest cohort uses the current warm draws.

The target, priors and data match the WP84/WP88/WP93 price-only stochastic-volatility
model: rho = 0.95, Student-t nu = 5, N = 250 initial returns, then 100 added returns.
The latent history therefore grows from 250 to 350. There are three new sampler
seeds per dataset, K in {20, 50, 200}, H in {10, 20}, and an unpooled H = 1 control.
The same already-inspected simulated and real BTC-PERPETUAL bar-close streams are
used; fresh sampler seeds test Monte Carlo reproducibility on those streams.

The full preregistration is [PREREGISTRATION.md](PREREGISTRATION.md), with the
machine-readable authority in [protocol.json](protocol.json). A tick passes when
P50 relative error is at most 2%, P95 relative error at most 5%, the frozen
reference-based stuck-chain census is clear, and library call plus declared
pooling arithmetic takes less than 0.4 s. A configuration also requires at least
285/300 ticks pooled, at least 90/100 in every seed, and signed-P50 drift within
0.5 percentage points in every seed. Missing/failed observations remain failures.

## Primary results

All rows below use exponential pooling. "Pass" includes the drift requirement,
not only the displayed successful-tick count. Times are medians of seed medians,
matching the original analyzer.

| K | H | Sim successful ticks | Real successful ticks | Sim / real component time (ms) | Sim / real complete rule |
|---|---|---|---|---|---|
| 20 | 10 | 259/300 (86.3%) | 216/300 (72.0%) | 8.6 / 31.8 | fail / fail |
| 20 | 20 | 279/300 (93.0%) | 236/300 (78.7%) | 10.1 / 33.3 | fail / fail |
| 50 | 10 | 292/300 (97.3%) | 261/300 (87.0%) | 20.2 / 80.3 | pass / fail |
| 50 | 20 | 294/300 (98.0%) | 283/300 (94.3%) | 22.3 / 82.2 | fail / fail |
| 200 | 10 | 300/300 (100%) | 294/300 (98.0%) | 79.7 / 306.2 | **pass / pass** |
| 200 | 20 | 300/300 (100%) | 296/300 (98.7%) | 84.0 / 311.3 | **pass / pass** |

At K = 200/H = 10, per-seed successful ticks are 100/100/100 on sim and
99/97/98 on real. Maximum absolute per-seed drift is 0.158 pp and 0.438 pp.
At H = 20 they are 100/100/100 and 99/99/98, with drift bounded by 0.120 pp
and 0.274 pp. The worst-seed P95 component times are 177.6/353.6 ms at H = 10
and 182.7/358.7 ms at H = 20 (sim/real).

The K = 50/H = 20 real miss is solely the pooled successful-tick count:
its seeds have 94/94/95 successes and all meet the drift limit. The corresponding
sim configuration misses drift on seed 971202: +0.593 pp against 0.5 pp.
Sim K = 50/H = 10 passes at 98/97/97 ticks, with largest drift +0.481 pp.
The K = 20/H = 20 simulated result does not reproduce WP93's exploratory pass:
it has 91/96/92 successful ticks and fails both the pooled share and drift.

The unpooled control reaches 33.7/57.7/95.3% on sim and 20.3/37.7/87.0% on real
at K = 20/50/200. Only sim K = 200 passes the complete rule. Uniform pooling
also passes both datasets at K = 200 and both H, but is a secondary result and
does not change the primary decision. At real K = 20/H = 20, uniform is 7.3 pp
worse than exponential, exceeding the prediction of a difference within 3 pp.

All scored warm ticks have zero recorded divergences and no stuck-chain census
flags. All configurations have zero slow ticks under the declared component
metric. There were no tick-0 retries; every warm cell carried all four chains.

Full per-configuration outcomes, signed biases, diagnostic MCSE, weight
concentration, latency tails and the frozen tolerance grid are in
[the original results table](artifacts/official/results-table.md) and
[summary.json](artifacts/official/summary.json). The grid's historical
"largest tolerance" field is actually the first acceptable pair in lexicographic
P50/P95 order; it is not a single ordered measure of overall accuracy.

## Reference reliability and interpretation

All 202 reference origins passed the original gate on their first attempt,
without a flagged or dropped chain. Maximum R-hat of the noise-added h_next
quantity is 1.00019. Median reference quantile MCSE is 0.085%/0.193% for sim
P50/P95 and 0.123%/0.278% for real. This is a reference comparison within the
same model, not empirical forecast calibration.

The separate [reference audit](artifacts/supplemental/reference-audit.json)
checks mu, log_sigma, beta and h_last before future Gaussian noise is added.
All 202 origins meet rank-Rhat <= 1.01 and bulk/tail ESS >= 400 on every stored
coordinate: maximum rank-Rhat is 1.000484, minimum bulk ESS 19,602 and minimum
tail ESS 33,011. There are zero retained reference divergences. Both full-chain
and retained-chain diagnostics are reported; they
coincide here because no chain was dropped. The supplemental audit never changes
the frozen verdict. It does not replace an independent sampler or density oracle.

Weight concentration improves with pooling, but `1/sum(w^2)` is not an
autocorrelation-adjusted MCMC sample size. At H = 20, median lag-19 weight
efficiency is 43-47% on sim and 21-26% on real. The four-chain split estimate of
pooled-P50 MCSE is also only a diagnostic: real K = 50/H = 20 has median 0.82%
yet fails the rule. Neither quantity is a validated online stopping criterion.

The reference-based stuck-chain census cannot itself be an online abstention
rule because the expensive reference is unavailable during ordinary updates.
Posterior overlap with a reference interval must not be interpreted as coverage
of realized future returns. The 300 seed/tick pairs reuse 100 data origins and
are dependent; they are not 300 independent market trials.

WP97 does not directly solve bounded-history operation. Its likelihood ratio
conditions on added returns. A sliding-window target also removes observations
and changes the initial-state representation; combining WP97 with WP96 requires
a justified removal/boundary treatment and validation. The four-field compact
draws do not generally contain all information needed for that correction.

## Timing and execution provenance

The prior agent completed only the diagnostic smoke. Recovery found a clean
draft remote checkout `ee32a28a` and no evidence cells. Original smoke sources,
raw data and logs were archived before any change, then copied locally and
verified against all 49 source-file hashes. The actual execution freeze is
`5aa256fb`, with durable launch wrappers added in `a355bae5` before sampling.
The protocol, library, Rust harness, driver and original analyzer stayed unchanged
from the draft; the existing executable was reused without a rebuild.

Both detached lanes started 2026-10-27 at 16:36:31 UTC on cores 8-11 and 12-15
of the existing c7a.4xlarge. Lane 3 ended 17:23:27; lane 4 ended 17:34:39.
All 22 cells and both lane wrappers exited zero, no evidence cell was rerun,
and the final inventory contains all planned records and correctly sized draws.
Sampling took 58 min 8 s wall, below the two-hour lane deadlines.

All warm timing cells finished by 16:39:27. A separate precision diagnostic used
cores 0-7 from 16:54:21 to 17:23:55.720541, during WP97 references only. Its
quantile arithmetic ran on cores 0-3 from 17:24:29.616757 to 17:24:45.905198.
These workloads shared memory/cache and affect reference wall context; the host
is not described as exclusive. The first official pooling analysis then ran on
cores 8-11 from 17:36:06 to 17:36:42, with those workloads drained and build
preparation held. NumPy 2.5.4 and ArviZ 0.23.4 were retained. Supplemental audit
and archive work followed; later builds were allowed only after official timing.

The declared component metric sums separately measured library and pooling
times. The original analyzer precomputes newest-tick h_next innovations outside
`pool_s`; it also excludes diagnostics, file I/O and caller integration. Keep
these first timings as the frozen result; they are not a complete resident
predictive or AMM decision-loop benchmark. No sampler default or production API
was changed by this study.

## Predictions and next decision

- P1/P4/P7/P8/P9: control pattern, smallest joint K = 200, component latency,
  small K = 200 signed bias and healthy guarded references are supported.
- P2: K = 200 passes both H on sim; K = 50 passes only H = 10, with H = 20
  missing drift. K = 20/H = 20 lands in the predicted 92-97% range but fails.
- P3: K = 200 passes both H on real. K = 50/H = 20 lands at 94.3% within its
  predicted range but does not pass; K = 20 remains inadequate.
- P5: the within-3-pp claim fails, most clearly for real K = 20/H = 20.
- P6: sim weight efficiency is reproduced; real lag-19 degradation is larger
  than the predicted 5-15 pp reduction.
- P10: sim MCSE ranges are reproduced; the real/sim MCSE ratio exceeds 1.5
  for some configurations, and sub-1% median diagnostic MCSE does not ensure a pass.

Use K = 200/H = 10 or 20 as supported research configurations for these fixed
growing-history streams. Do not claim a jointly qualified K = 50, relax the
two-tick miss, or turn the per-lag pool directly into a sliding-window policy.
The next useful question is whether properly marginalized predictive functionals
reduce estimator noise and total update cost on fresh streams, with separate
reference reliability and predictive-validity checks.

## Artifacts and reproduction

- [LEDGER-ENTRY.md](LEDGER-ENTRY.md) is evidence entry E59.
- [Execution records](artifacts/execution/inventory-final.json) contain the
  complete inventory and raw-draw hashes; the first official outputs are under
  `artifacts/official`, not overwritten by supplemental work.
- [Snapshot reconciliation](artifacts/supplemental/snapshot-reconciliation.json)
  passes all 42 comparisons for the unchanged fixed real tick-2 reference and
  warm snapshots shared with the independent predictive-functional diagnostic.
- `CHECKSUMS.sha256` covers source, reports and all local raw artifacts. Raw `.f32`
  draws remain outside Git. The remote evidence archive is
  `/home/ubuntu/lanes/pool_confirm_v1/runs/evidence-20261027/final-artifacts.tar.gz`;
  a verified local copy is in `target/wp97-recovery/evidence-20261027/` of this
  worktree. Its SHA256 is
  `19a89ac0ac401e0700d3140e33e71637658d0cc791a52806dc3eaa38013de595`.
  All 2,278 archived files were verified after local extraction.
- Recovery and safe resumption details are in [RECOVERY.md](RECOVERY.md).

Read-only integrity check: `python audit_inventory.py artifacts/cells --hash-draws`.
Recompute analysis only into a new output directory and retain the original
official timing; use the pinned environment for comparable numerical diagnostics.
