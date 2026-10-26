# Preregistration: tick_pooling_v1 (WP93)

Frozen on `wt/tick-pooling` (base `main` `6dae32bd`: the WP87 warm-continuation API, the WP90 trapped-chain guard as
default; no library change in this study) before the first evidence cell. `protocol.json` is the machine-readable copy
and wins on any discrepancy. Ledger id `WP93-TICK-POOLING-V1`. Predecessors: WP84 (`STUDIES/online_sv_quote_v1`, the
model, the data generator and the post-hoc quote-error rule), WP88 (`STUDIES/online_sv_quote_v2`, the library warm path,
the gated reference, the 2 % / 5 % rule, K in {50, 100, 200}: K = 200 passes on this series at 78 ms, K = 50 fails at 55 %).

## Question

In an online loop the posterior is refreshed every tick. If the quote is computed from a POOL of the warm draws of the
last H ticks (uniformly or with exponential decay), can K transitions per chain per tick fall far below 200 while the
quote still meets the WP88 rule (|P50 sigma_next error| <= 2 % and |P95 error| <= 5 % against a gated 4 x 20,000-draw
reference on >= 95 % of ticks pooled and >= 90 % per seed, no drift)? Primary answer: the smallest K at which some
(H, weighting, variant) passes, and that K's latency. Open-questions item 22(b) asked for "pooled chains" as a candidate
accuracy bar; this is the pooled-ticks version of it.

## Model, data, stream

The WP84 target unchanged (`rust/src/main.rs`; the density code is byte-for-byte the WP88 harness code, which was checked
against `models/sv.stan` through BridgeStan before WP88's freeze, lp offset spread <= 1.8e-12, gradient relative error
<= 2.1e-14): y_i ~ t_5(beta, exp(h_i/2)), non-centred AR(1) log-vol with rho = 0.95 fixed, priors mu ~ N(2 log 0.005, 1),
log sigma ~ N(log 0.2, 0.5), beta ~ N(0, 0.002), z ~ N(0, 1), dimension 3 + n. Data: `models/data.json`, the WP84
simulated series (seed 84084, 1,100 returns + truth h), byte-identical to `online_sv_quote_v1/models/data.json` and
`online_sv_quote_v2/models/data-sim.json` (sha256 `9c183c8a…dcf5c8`, recorded in `protocol.json`). N = 250, 100 ticks of
one return each: tick t conditions on the first N + t returns; the return that arrives at tick t is `y[N + t - 1]`
(0-indexed). Simulated data only (WP88 showed the real BTC series needs K > 200 even without pooling; it is out of scope).

## Quantities

h_next = mu + rho (h_last - mu) + sigma eps with the WP84/WP88 common eps stream (`default_rng(840000 + tick)`, shape
(4, 20000), row = chain index, column = draw index), sigma_next = exp(h_next / 2). Gated: P50 (half-spread) and P95 (risk
quote). Reported: P5, mean, the arm's own quantile MCSE of P50 / P95 and bulk ESS / R-hat of h_next at H = 1 (arviz
0.23.4), the weight ESS of the pf pools, the fraction of pooled draws inside the reference 90 % interval of h_next.
**Quantile definition (new, applies to every arm and to the reference):** weighted quantile by linear interpolation of
the midpoint CDF (sorted x_i with normalised weights w_i, c_i = sum_{k<=i} w_k - w_i / 2, q(p) = interp(p, c, x), clamped
at the ends); with uniform weights this is Hyndman-Fan type 5. WP88 used `np.quantile` (type 7); at 80,000 reference
draws the two differ by < 1e-4 relative, at 20 draws (K = 5, H = 1) the choice matters and type 5 is the one that extends
to weights, so it is used throughout.

## Reference and gate (WP88's, unchanged)

Per tick 0..100, oWALNUTS at defaults, 4 x 2,000/20,000, best-of-16 starts, `Limits::admit_worst_case` and
`max_result_bytes_unchecked(2 GiB)`. Gate: chains named by a `WarmupStep` or `SampledLogDensity` chain warning are
dropped; the tick passes iff >= 3 chains remain and the rank R-hat of h_next over the remaining chains <= 1.01. A tick
failing the gate runs once more at the next preregistered seed (attempt a at tick t: `939460 * 1000 + t + 200 a`,
a in {0, 1}); the second attempt is part of the cell, not a rerun. A tick failing both is unscored and counts as a FAILED
tick for every configuration scored there. Expected floor (WP88 on this series): relative MCSE of P50 0.08 % median /
0.11 % max, P95 0.19 % / 0.27 %.

**Adjustment from the task's design, with the reason.** The task asked for the reference at tick 0 and every 10th tick
(11 scored ticks per seed, 33 pooled). A 95 % pooled / 90 % per-seed rule on 33 ticks is decided by a single miss
(32/33 = 97 %, 31/33 = 94 %), and the drift windows would hold 3 ticks each. The reference at every tick costs 101 x ~11 s
= 19 lane-minutes on this box (WP88 ran exactly this cell in 18 min), which is inside the one-hour budget, and it makes the
scored set the WP88 one (300 ticks, 30/31-tick drift windows), so the pooled numbers are directly comparable with WP88's
H = 1 numbers. The reference is therefore at every tick 0..100, split for scheduling only into cell `ref-lo` (ticks
0-50, lane 1) and `ref-hi` (ticks 51-100, lane 2); the seed rule does not depend on the split.

## Warm arm (the library path)

Tick-0 fit at defaults (4 x 1,000/1,000, best-of-16 starts) at the cell seed, **gated**: if a chain is named by a
`WarmupStep` / `SampledLogDensity` warning (a trapped chain), the fit is repeated once at the next preregistered seed
(cell seed + 10); the last attempt's flagged chains are dropped from the carried state (WP88 rule), fewer than 2 chains
left = the cell fails (a result). Then `Posterior::warm_state()`, and per tick `WarmState::extend_to(3 + n, 0.0, 1.0)`
and `Sampler::run_warm` with `draws(K)`, seed `seed * 1_000_003 + 16 * tick` (chain c on seed + c), threads 4,
`Limits::admit_worst_case`; the result's `warm_state()` is the next state; no re-adaptation. K in {5, 10, 20, 50, 200},
seeds 931201-931203, 100 ticks. Every tick's draws are stored as f32 `[chain][draw][4]` = mu, log_sigma, beta, h_last
(the pooling and the re-propagation need only these).

## Pooling (analysis-side, `analyze.py`)

At tick t the pool holds the draws of ticks max(1, t - H + 1) .. t (all kept chains, all K draws per chain); tick 0 (the
1,000-draw full fit) is never pooled; for t < H the pool is shorter (the online cold start) and those ticks are scored
like any other; the pass share over ticks >= 20 (every pool full) is reported as well. H in {1, 5, 10, 20}. Weightings:
uniform (w_j = 1) and exponential with half-life H / 2 (w_j = 2^(-j / (H/2)) for a draw of lag j = t - s ticks); at H = 1
they coincide. Three variants of what a stale draw stands for:

* **asis** — the pooled draw from tick s = t - j is used AS IS: its h_next (a draw of h_{N+s+1} under the tick-s
  posterior) stands in for h_{N+t+1}. The coordinate is j steps stale and ignores the j returns received since. This is
  the task's primary estimator.
* **prop** — the stale draw's last latent h_{N+s} is re-propagated through the AR(1) j + 1 steps with fresh noise
  (`default_rng(851000 + t)`, one stream per tick, lags in increasing order): a draw of h_{N+t+1} under the tick-s
  posterior's (j+1)-step predictive. Still ignores the j new returns. (The task's "re-propagate" variant.)
* **pf** — as prop, but the propagated path h_{N+s+1..N+t} is weighted by the likelihood of the j new returns
  `y[N+s .. N+t-1]` (t_5(beta, exp(h/2)) densities): a bootstrap particle-filter step whose particles are the stale draws
  (exact in expectation; weight degeneracy is its failure mode). The time weight multiplies the likelihood weight; weights
  are normalised within the pool; the weight ESS is reported. Added because the lag analysis below says asis cannot work
  on this series, and the question deserves an estimator that uses the stale draws correctly; it costs nothing to run.

120 configurations (5 K x 4 H x 2 weightings x 3 variants; the H = 1 pairs coincide), each scored on the same 300 ticks.
The analysis-side cost of the pooled quantile (numpy, per H and variant) is timed per tick and reported, not gated.

## Accuracy, latency, drift, pass, decision

**Accuracy.** A scored tick passes iff |P50 error| <= 2 % AND |P95 error| <= 5 % against the gated reference AND no stuck
chain at the newest tick (WP84/WP88 census rule: a chain whose median log_sigma is > 1.0 from the reference's median, or
median h_last > 2.0 away) AND the library call of the newest tick took < 0.4 s. Scored ticks: 1..100 per seed, 300 pooled,
for every configuration; tick 0 scored separately and reported.

**Latency.** Wall per tick of the library call: from `Sv::new` (new target) through `extend_to` and `run_warm` to
`warm_state()` taken; draw-file writing excluded. Threshold 0.4 s; the shares under 10 / 50 / 100 ms are reported.

**Drift.** Per seed and configuration, mean signed P50 error over ticks >= 70 minus over ticks 1..30; bound 0.5 pp.

**Pass.** A configuration passes iff >= 285/300 pooled AND >= 90/100 in every seed AND drift within bound in every seed.

**Decision rule.** The README may say "K = <k> per tick with a pool of <H> ticks meets the quote rule" only for a
configuration that passes on all three seeds, naming its weighting and variant. The primary answer is the smallest K at
which some configuration passes, with that K's measured latency; the smallest passing K of the asis variant is reported
separately. Otherwise the README states the measured pass shares, latency and stale bias per (K, H).

**Stale-latent bias (reported).** (a) The reference lag curve: |P50_ref(t-j) / P50_ref(t) - 1| and the P95 analogue for
j = 1..20, median and P95 over ticks, signed mean, and the share within 2 % / 5 % (the staleness effect with no Monte Carlo
noise). (b) The signed mean P50 / P95 error per configuration. (c) The K = 200 pools, with the least Monte Carlo noise, as
the direct stale-bias estimate per (H, weighting, variant).

## Cells, lanes, budget

17 cells: `ref-lo`, `ref-hi`, 15 warm cells (`warm<K>-s<seed>`). Lane 1 (cores 0-3): ref-lo, then K = 5, 10, 20, 50, 200
at seed 931201, then K = 5, 10, 20 at 931203. Lane 2 (cores 4-7): ref-hi, then K = 5 … 200 at 931202, then K = 50, 200 at
931203. Lanes run in parallel, cells sequentially within a lane in this order (`run_cells.py plan`); a started cell is
never rerun (an existing output directory is skipped); failures are results. Budget about 25 lane-minutes (references
2 x 9.5 min, warm cells 15 x ~15 s), about 12 min wall after the build; analysis ~5 min. Seeds 931201-931203 (arms),
931211-931213 (tick-0 retries), 939460 (reference base), 851000 (re-propagation noise base) were grep-verified unused
before the freeze (the only hits for 931212 / 931213 are float substrings inside two CmdStan draw JSONs of
`sv_stuck_chains_v1`, not seeds); diagnostic smoke seeds 993901, 993902, 993960 are never scored.

Executed on lanes 1 and 2 of the shared c7a.4xlarge (16 dedicated cores, 32 GB), `taskset`-pinned, `RAYON_NUM_THREADS=4`,
`OMP_NUM_THREADS=1`, co-tenanted with WP96 on cores 8-15 (shared L3 and memory bandwidth): walls are "pinned,
co-tenanted"; accuracy and gradient counts are unaffected. Box: Rust 1.88.0, arviz 0.23.4, numpy 2.5.4.

## What was known before the freeze (and shapes the predictions)

A read-only pass over WP88's gated reference draws on this series (`ref-sim-N250`, 101 ticks, finished study) measured how
far the reference's own P50 / P95 of sigma_next at tick t - j is from tick t: lag 1 median |P50 change| 3.5 % (27 % of
ticks within 2 %), lag 5 9.2 %, lag 10 10.1 %, lag 20 15.9 %; P95 similar (lag 1 3.0 %, 84 % within 5 %; lag 5 8.3 %,
31 %). Uniform pools of 4,000 reference draws per tick over H ticks (no Monte Carlo noise worth mentioning) pass both
tolerances on 24 % (H = 5), 14 % (H = 10), 9 % (H = 20) of ticks; the exponential weighting lifts these to 33 / 23 /
14 %. The premise "the posterior moves little per tick" is false for this model at N = 250: one t_5 return moves the
filtered log-vol by about 0.07 (3.5 % in sigma), more than the P50 tolerance. The WP93 reference will re-measure this
curve with its own seeds (reported table), and the study is run anyway: the as-is result is then a measured negative
with the size of the bias, and the pf variant tests whether the stale draws can still be used.

## Predictions (written before any evidence cell)

* P1 H = 1 reproduces WP88: K = 200 passes (95-98 % pooled), K = 50 fails (50-60 %); K = 20 fails (25-45 %), K = 10
  (15-35 %), K = 5 (5-25 %).
* P2 asis pooling fails at every K for every H >= 5 (pooled pass share <= 45 %), with |P95 err| median > 3 % at H >= 5.
* P3 Exponential weighting beats uniform at every H >= 5 for asis (pass share higher by 5-15 points) but no asis pool passes.
* P4 prop fails at every (K, H >= 5): the (j+1)-step predictive reverts towards mu and inflates the spread; signed mean
  P95 error >= +3 % at H >= 10.
* P5 pf is the only pooling that can pass: K = 50 with H in {10, 20} passes; K = 20 with H = 20 reaches 85-95 % and
  fails; K = 5 and K = 10 fail at every H (< 85 %). Smallest passing K: 50 (pf, H >= 10); for asis, 200 (H = 1 only).
* P6 Latency medians (4 pinned cores): K = 5 2-6 ms, K = 10 4-9 ms, K = 20 8-14 ms, K = 50 18-24 ms, K = 200 75-90 ms;
  the pooling step < 5 ms per tick at H = 20.
* P7 Signed stale bias: asis pools have a positive mean P50 error (+0.5 to +1.5 % at H = 10 uniform; the series'
  volatility fell over the 100 ticks); prop and pf have |signed P50| < 0.5 % at K = 200.
* P8 Gate: 0-3 of 101 reference ticks drop a flagged chain, 0-1 need the second seed, 0 fail both; 0-2 of the 15 tick-0
  fits need the retry.
* P9 Drift within 0.5 pp on every seed for every passing configuration; some asis configurations at H >= 10 exceed it.

## Pre-freeze disclosures (not evidence)

PLACEHOLDER (filled before the freeze commit: build, smoke at diagnostic seeds through every code path, analysis on the
smoke output).
