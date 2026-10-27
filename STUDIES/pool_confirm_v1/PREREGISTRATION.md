# Preregistration: pool_confirm_v1 (WP97)

Frozen on `wt/pool-confirm` (base `main` `d34a00eb`: the WP87 warm API, the WP90 trapped-chain guard as the sampler default since
`8cb33fbf`, the WP91 warm session; no library change in this study) before the first evidence cell. `protocol.json` is the
machine-readable copy and wins on any discrepancy. Ledger id `WP97-POOL-CONFIRM-V1`. Predecessors: WP84 (`online_sv_quote_v1`,
the model, the data generator, the post-hoc quote-error rule), WP88 (`online_sv_quote_v2`, the library warm path, the gated
reference, the 2 % / 5 % rule, the real BTC series; K = 200 passes on simulated data at 78 ms and fails on real at 83 %), WP93
(`tick_pooling_v1`: as-is pooling fails at every K and H because the reference's own P50 moves 3.4 % per tick; post hoc, not
preregistered, the likelihood-reweighted pool with per-lag weight normalisation reached the rule at K = 20, H = 20 and at
K = 50, H >= 10 on simulated data). This study is that post hoc's preregistered confirmation, with the real series included.

## Question

Does the WP93 post-hoc estimator (`posthoc/pf_lagnorm.py`: the pool of the last H ticks' warm draws, each stale tick's draws
re-propagated through the AR(1) and reweighted by the likelihood of the returns received since, importance weights normalised
within each lag group, lag groups mixed by exponential time weights) meet the WP88 quote rule at K in {20, 50, 200}
transitions per chain per tick on the WP84 simulated series AND on the real BTC-perpetual bar-close series, against a gated
reference at every tick, on three fresh seeds per dataset? Primary answer: the smallest K at which some H in {10, 20} passes on
BOTH datasets, with that configuration's latency (library call + pooling arithmetic) per dataset.

## Model, data, stream

The WP84 target unchanged (`rust/src/main.rs` is the WP93 harness with the binary renamed; the density code is byte-for-byte
the WP88 harness code, checked against `models/sv.stan` through BridgeStan before WP88's freeze): y_i ~ t_5(beta, exp(h_i/2)),
non-centred AR(1) log-vol with rho = 0.95 fixed, priors mu ~ N(2 log 0.005, 1), log sigma ~ N(log 0.2, 0.5), beta ~ N(0, 0.002),
z ~ N(0, 1), dimension 3 + n. Two datasets, both at N = 250 and 100 ticks of one return each (tick t conditions on the first
N + t returns; the return arriving at tick t is `y[N + t - 1]`, 0-indexed):

* **sim**: `models/data-sim.json`, the WP84 simulated series (seed 84084, 1,100 returns + truth h), byte-identical to
  `online_sv_quote_v1/models/data.json`, `online_sv_quote_v2/models/data-sim.json` and `tick_pooling_v1/models/data.json`
  (sha256 `9c183c8a…dcf5c8`).
* **real**: `models/data-real.json`, byte-identical to `online_sv_quote_v2/models/data-real.json` (sha256 `6ba1ba42…908487`):
  682 Deribit BTC-PERPETUAL 30-minute **bar-close** log returns reconstructed by WP88's `real_data.py` from the archived
  rolling windows of `market_uncertainty_v1` (`sv-historical-rolling-v1/evidence.zip`); the same priors, no rescaling, no
  truth h. As WP88 noted, the receipt-time midpoint series is not archived at length; the same licence caveat applies.

## Quantities

h_next = mu + rho (h_last - mu) + sigma eps with the WP84/WP88/WP93 common eps stream (`default_rng(840000 + tick)`, shape
(4, 20000), row = chain index, column = draw index; reused on purpose, it defines the quantity), sigma_next = exp(h_next / 2).
Gated: P50 (half-spread) and P95 (risk quote). Reported: P5, mean, the arm's own quantile MCSE of P50 / P95 and bulk ESS /
R-hat of h_next at H = 1 (arviz 0.23.4), the weight ESS of the pool and of every lag group, the chain-split own MCSE of the
pooled P50 (below), and the fraction of pooled weight inside the reference 90 % interval of h_next. Quantile definition
(WP93's, every arm and the reference): weighted quantile by linear interpolation of the midpoint CDF (sorted x_i with
normalised weights w_i, c_i = sum_{k<=i} w_k - w_i / 2, q(p) = interp(p, c, x), clamped at the ends; uniform weights =
Hyndman-Fan type 5).

## Reference and gate (WP88's, unchanged; every tick, both datasets)

Per tick 0..100 of each dataset, oWALNUTS at defaults, 4 x 2,000/20,000, best-of-16 starts, `Limits::admit_worst_case` and
`max_result_bytes_unchecked(2 GiB)`. Gate: chains named by a `WarmupStep` or `SampledLogDensity` chain warning are dropped;
the tick passes iff >= 3 chains remain and the rank R-hat of h_next over the remaining chains <= 1.01. A tick failing the
gate runs once more at the next preregistered seed (attempt a at tick t of dataset d: `seed_base[d] * 1000 + t + 200 a`,
a in {0, 1}; bases 979460 sim, 979500 real); the second attempt is part of the cell, not a rerun. A tick failing both is
unscored and counts as a FAILED tick for every configuration scored there. The reference depends on the data only, so one
reference per dataset serves the three seeds: 202 reference ticks (not 606). WP93 showed that a reference at every 10th
tick cannot resolve a 95 % / 90 % rule, so every tick is referenced on both datasets. Split for scheduling only into
`ref-<d>-lo` (ticks 0-50) and `ref-<d>-hi` (51-100); the seed rule does not depend on the split.

**The trapped-chain guard.** This is the first reference run with the WP90 guard as the sampler default: WP88's reference
(base `5027bc1e`) and WP93's (base `6dae32bd`, the docs commit immediately BEFORE the flip `8cb33fbf`) ran without it, so
WP93's preregistration misdescribed its base on this point and its 7 flagged ticks of 101 were unguarded. The count of
reference ticks with a flagged chain, second seeds and double failures is reported per dataset (P9).

## Warm arm (the library path, WP93 harness unchanged)

Tick-0 fit at defaults (4 x 1,000/1,000, best-of-16 starts) at the cell seed, gated: if a chain is named by a `WarmupStep` /
`SampledLogDensity` warning the fit is repeated once at seed + 10; the last attempt's flagged chains are dropped from the
carried state (WP88 rule), fewer than 2 chains left = the cell fails (a result). Then `Posterior::warm_state()`, and per tick
`WarmState::extend_to(3 + n, 0.0, 1.0)` and `Sampler::run_warm` with `draws(K)`, seed `seed * 1_000_003 + 16 * tick` (chain c
on seed + c), threads 4, `Limits::admit_worst_case`; the result's `warm_state()` is the next state; no re-adaptation. K in
{20, 50, 200}; seeds 971201-971203 (sim), 971301-971303 (real); 100 ticks. Every tick's draws are stored as little-endian f32
`[chain][draw][4]` = mu, log_sigma, beta, h_last (= h_{N+t}, the latent of the newest return). **These four are everything the
re-propagation needs**: the AR(1) is Markov in h and rho, nu are fixed, so earlier latents never enter; the z coordinates are
not stored (`WarmSession::refresh` would be bit-identical under its seed rule; `run_warm` is used as in WP88 / WP93).

## Estimators (analysis-side, `analyze.py`)

At tick t the pool holds the draws of ticks max(1, t - H + 1) .. t (all kept chains, all K draws per chain); tick 0 (the
1,000-draw full fit) is never pooled; for t < H the pool is shorter (the online cold start), those ticks are scored like any
other and the pass share over ticks >= 20 (every pool full) is reported as well.

* **Control: as-is, H = 1** (the WP88 / WP93 estimator): the newest tick's own h_next draws, uniform weights. At H = 1 every
  estimator coincides with it.
* **Under test: pf-lagnorm, H in {10, 20}** (WP93 `posthoc/pf_lagnorm.py` reproduced exactly). For lag j = t - s in 0..H-1
  the tick-s draws are particles (mu_i, sigma_i = exp(log_sigma_i), beta_i, h_i = h_{N+s}).
  - Lag 0: value = the tick-t h_next from the common eps stream; log-weight 0 (the exact current draws).
  - Lag j >= 1: fresh noise eps_{i,m} ~ N(0, 1), m = 0..j, from `default_rng(prop_seed_base[d] + t)` (one stream per tick;
    lag groups drawn in increasing j, each as `normal(size=(n_j, j + 1))`; bases 972000 sim, 973000 real). For m = 0..j-1:
    h_i <- mu_i + rho (h_i - mu_i) + sigma_i eps_{i,m}, then logw_i += log t_nu(y[N+s+m] - beta_i; 0, exp(h_i/2)) — the
    return that arrived at tick s + m + 1, so the j returns y[N+s .. N+t-1] received since the draw was made are all
    conditioned on. The value is h_next,i = mu_i + rho (h_i - mu_i) + sigma_i eps_{i,j} (a draw of h_{N+t+1}).
  - **Per-lag normalisation**: within lag group j the importance weights are self-normalised, v_i = exp(logw_i - max_j) /
    sum_j, so every group's total weight is set by its time weight and not by the product of j return densities (the WP93
    frozen `pf` error). Each v_i is multiplied by the time weight w_j: **exp** (primary) w_j = 2^(-j / (H/2)), half-life
    H/2; **uniform** (secondary, reported) w_j = 1. The pool concatenates the lag groups' values and weights, normalises,
    and the weighted quantile of sigma_next = exp(h_next/2) gives P50 and P95.
  - Weight ESS: per lag group 1 / sum(v_i^2) (reported as a fraction of the group's draws); per pool 1 / sum(w_i^2) of the
    pool-normalised weights.
  - **Chain-split own MCSE of the pooled P50** (no reference needed): the pooled P50 is recomputed from each kept chain's draws
    alone (same lags, importance weights normalised within that chain's lag group, same time weights); MCSE = sd over the C
    chains (ddof 1) / sqrt(C), relative to the pooled P50, median over ticks. At H = 1 the arviz quantile MCSE of WP88 / WP93
    is reported as well.

Configurations per (dataset, K): as-is H = 1, pf-lagnorm H in {10, 20} x {exp, uniform}: 5, so 30 in all, each scored on the
same 300 ticks of its dataset. The analysis-side pooling arithmetic (the re-propagation of the lags < H plus the weighting
and the weighted quantile, numpy) is timed per tick and configuration and **added to the library call for the latency rule**;
both parts are reported.

## Accuracy, latency, drift, pass, decision

**Accuracy.** A scored tick passes iff |P50 error| <= 2 % AND |P95 error| <= 5 % against the gated reference AND no stuck
chain at the newest tick (WP84/WP88 census rule: a chain whose median log_sigma is > 1.0 from the reference's median, or
median h_last > 2.0 away) AND library call + pooling arithmetic of the newest tick < 0.4 s. Scored ticks: 1..100 per seed, 300
pooled per dataset, for every configuration; tick 0 scored separately and reported.

**Latency.** Library call: wall per tick from `Sv::new` (new target) through `extend_to` and `run_warm` to `warm_state()`
taken; draw-file writing excluded. Pooling: the analysis-side arithmetic of the configuration. Threshold 0.4 s on the sum
(WP88's N = 250 threshold); the shares of library calls under 10 / 50 / 100 ms are reported.

**Drift.** Per seed and configuration, mean signed P50 error over ticks >= 70 minus over ticks 1..30; bound 0.5 pp.

**Pass.** A configuration (dataset, K, H, weighting) passes iff >= 285/300 pooled AND >= 90/100 in every seed AND drift within
bound in every seed.

**Largest tolerance met** (reported per configuration, WP88's definition): the first pair (ordered P50 then P95) on the grid
P50 in {1, 2, 5, 10} % x P95 in {2, 5, 10, 20} % with >= 95 % pooled and >= 90 % per seed (accuracy and stuck chain only; no
latency or drift condition).

**Decision rule.** The README may say "K = <k> per tick with a reweighted pool of <H> ticks meets the quote rule on simulated
and real returns in <ms>" only for a (K, H, exp) configuration that passes on all three seeds of BOTH datasets; <ms> is the
median library + pooling latency per dataset. The primary answer is the smallest such K and its H. Otherwise the README names,
per dataset, the largest tolerance met per (K, H) and the measured pass shares; a configuration passing on one dataset only is
reported as such and may not be named in the headline sentence. The uniform weighting is a reported secondary and cannot carry
the headline.

## Cells, lanes, budget

22 cells: 18 warm (`warm<K>-<d>-s<seed>`) and 4 reference halves. Lane 3 (cores 8-11): the nine sim warm cells (seed-major,
K = 20, 50, 200), then `ref-sim-lo`, then `ref-real-lo`. Lane 4 (cores 12-15): the nine real warm cells, then `ref-sim-hi`,
then `ref-real-hi`. Lanes run in parallel, cells sequentially within a lane in this order (`run_cells.py plan`); a started
cell is never rerun (an existing output directory is skipped); failures are results. Budget about 110 lane-minutes: references
202 ticks (sim 101 x ~18 s driver wall as WP93 = 30 min; real 101 x ~42 s from WP88's 35 s sampler wall + driver = 71 min),
warm cells 18 x 10-40 s = 6 min; lane 3 about 56 min, lane 4 about 55 min, about 1 h wall after the build; analysis about
5 min. (The task's budget assumed 606 reference ticks at 11 s; the reference is per dataset, not per seed.)

Seeds 971201-971203, 971301-971303 (arms), 971211-971213, 971311-971313 (tick-0 retries), 979460, 979500 (reference bases),
972000, 973000 (re-propagation noise bases) were grep-verified before the freeze (`git grep -w` over main): zero hits for every
base; the only hits for the arm and retry seeds are numeric substrings (`target_calls`, float fragments) inside CmdStan draw
JSONs of `sv_stuck_chains_v1` and `adaptive_delta_v1`, not seeds. Diagnostic smoke seeds 993970 / 993975 (reference bases),
993971 / 993972 (warm) are never scored.

Executed on lanes 3 and 4 of the shared c7a.4xlarge (16 dedicated cores, 32 GB), `taskset`-pinned, `RAYON_NUM_THREADS=4`,
`OMP_NUM_THREADS=1`, co-tenanted with WP94 on cores 0-7 and with each other (shared L3 and memory bandwidth): walls are
"pinned, co-tenanted"; accuracy and gradient counts are unaffected. Started only after WP96 released cores 8-15. Box: Rust
1.88.0, arviz 0.23.4, numpy 2.5.4.

## What was known before the freeze (and shapes the predictions)

WP93's post hoc on the simulated series (seeds 931201-931203, the same reference series): pf-lagnorm exp passed at K = 20,
H = 20 (95.3 %, seeds 96 / 97 / 93, wESS about 1,030), at K = 50, H = 10 and 20 (97.0 %), and at K = 200 everywhere (100 %);
uniform passed at K = 20, H = 20 (95.0 %) and at K = 50, H = 5 and 10 but missed one drift window at H = 20 (-0.52 pp).
Weight efficiency per lag group was 97 % at lag 1, 71 % at lag 9 and 45 % at lag 19 at every K. WP88 on the real series:
K = 200 as-is 83.3 % (seeds 90 / 78 / 82) with an own P50 MCSE of 1.25 % against 0.93 % on sim, the P95 biased low by
0.4 pp, the reference 35 s per tick with 2 of 51 ticks dropping a flagged chain and 1 needing the second seed. So the real
series needs about 1.8x the weight ESS of sim for the same precision, and the K = 20, H = 20 pool has about the ESS of the
K = 200 single tick that fails there.

## Predictions (written before any evidence cell)

* P1 H = 1 control reproduces WP88 / WP93: sim K = 200 passes (94-98 % pooled), K = 50 fails (48-60 %), K = 20 fails
  (25-45 %); real K = 200 fails (78-90 %), K = 50 (30-48 %), K = 20 (12-30 %).
* P2 sim, pf-lagnorm exp: K = 200 passes at H = 10 and 20 (99-100 %); K = 50 passes at both H (94-98 %; P(both pass) 0.7);
  K = 20 at H = 20 reaches 92-97 % (P(pass) 0.5) and at H = 10 fails (82-90 %).
* P3 real, pf-lagnorm exp: K = 200 passes at H = 10 and 20 (96-100 %); K = 50 at H = 20 reaches 92-97 % (P(pass) 0.4) and
  at H = 10 fails (86-93 %); K = 20 fails at both H (72-88 %).
* P4 The smallest K passing on BOTH datasets is 200 (P 0.6) or 50 (P 0.4); K = 20 does not pass both (P 0.9). If the
  headline sentence is allowed it reads K = 200 with H = 10 (sim 75-90 ms + pooling, real 280-340 ms + pooling) or K = 50
  with H = 20.
* P5 Uniform and exp pass shares within 3 points of each other on every (dataset, K, H); the uniform drift statistic is
  larger in magnitude than the exponential one on most seeds at H = 20.
* P6 Weight efficiency per lag group (sim, any K): lag 1 95-98 %, lag 9 65-75 %, lag 19 40-50 %; real lower by 5-15 points
  at lags >= 9; pool wESS at K = 20, H = 20 exp 900-1,100 on sim.
* P7 Latency medians (4 pinned cores, co-tenanted): library call sim K = 20 7-10 ms, K = 50 18-24, K = 200 75-90; real
  K = 20 28-40 ms, K = 50 70-95, K = 200 280-340; the pooling arithmetic at H = 20 is 1-10 ms at every K (< 15 ms at
  K = 200); library + pooling under 0.4 s on 100 % of ticks except real K = 200 (97-100 %).
* P8 Signed bias of pf-lagnorm: |signed mean P50 error| <= 0.3 % and |signed mean P95 error| <= 0.5 % at K = 200 on both
  datasets; drift within 0.5 pp on every seed of every passing configuration.
* P9 Gated reference under the guard default: 0-3 of 202 ticks drop a flagged chain (WP93: 7/101 unguarded on sim, WP88:
  2/51 unguarded on real), 0-1 need the second seed, 0 fail both; 0-2 of the 18 tick-0 fits need the retry.
* P10 Chain-split own MCSE of the pooled P50 (median over ticks): sim K = 20 H = 20 0.7-1.1 %, K = 50 H = 20 0.45-0.7 %,
  K = 200 H = 20 0.2-0.4 %; real 1.2-1.5x these; configurations pass once it is below about 1 %.

## Pre-freeze disclosures (not evidence)

Filled in before the freeze commit; see the freeze commit message for the hashes.

* Build: the study crate passes `cargo clippy --all-targets -- -D warnings` on 1.88 (Windows GNU) at the draft commit
  `ee32a28a`; built on the box (release, LTO, 52 s) under `nice -n 10`, 4 jobs, while WP96 still held cores 8-15.
* **Reproduction of the WP93 post hoc with this study's `analyze.py`** (laptop, reads only, WP93's raw draws and reference,
  WP93's seeds and its re-propagation noise base 851000 through a protocol copy): the pass shares reproduce WP93's
  `posthoc-pf-lagnorm.md` to the digit on every (K, H, weighting) in this study's grid (K = 20, H = 20: exp 95.3 %, seeds
  96 / 97 / 93, uniform 95.0 %; K = 50: H = 10 exp 97.0 %, uniform 95.7 %, H = 20 exp 97.0 %, uniform 97.3 % with the
  -0.52 pp drift miss; K = 200: 100 % at both H; as-is H = 1: 33.7 / 53.3 / 95.0 %), as do the drift statistics, the
  weight ESS (1,031 / 978 / 1,545 / 2,590 / 10,326) and the lag efficiency curve (97 % at lag 1, 70 % at lag 9, 46 % at
  lag 19), and the reference statistics (7 flagged ticks at 6, 11, 27, 29, 54, 64, 71). So the estimator under test is the
  WP93 post-hoc estimator exactly. New quantities on those data: the chain-split own MCSE of the pooled P50 is 0.81 % at
  K = 20, H = 20 exp (|P50 err| median 0.56 %), 0.50 % at K = 50, H = 20 (0.46 %), 0.25 % at K = 200, H = 20 (0.18 %) and
  2.45 / 1.57 / 0.83 % at H = 1 (K = 20 / 50 / 200); the largest tolerance met is 2 / 5 % at K = 20, H = 20 and 1 / 2 % at
  K = 200, H >= 10. The laptop's pooling arithmetic (not a benchmark) was 3.8 ms at K = 20, H = 20, 6.0 ms at K = 50 and
  16.8 ms at K = 200, H = 20; P7's "< 15 ms at K = 200" stands as written for the box.
* Smoke (`run_cells.py smoke`, diagnostic seeds, never scored): recorded below once run on the freed lane 3, before the first
  evidence cell.
