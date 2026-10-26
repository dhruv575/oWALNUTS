# Preregistration: online_sv_quote_v2 (WP88)

Frozen 2026-10-26 on `wt/online-sv-v2` (base `main` `5027bc1e`, which carries the WP87 warm-continuation
API) before the first evidence cell. `protocol.json` is the machine-readable copy and wins on any
discrepancy. Ledger id `WP88-ONLINE-SV-QUOTE-V2`. Predecessor: WP84 (`STUDIES/online_sv_quote_v1`),
whose post-hoc report (`online_sv_quote_v1/posthoc/README.md`) proposed the accuracy rule used here.

## Question

Can oWALNUTS's warm continuation, now a library call (`Sampler::run_warm` on a `WarmState`
extended by one coordinate per tick), be called a real-time quote refresh on a stochastic-volatility
model fed one return per tick? "Real-time" is decided by a quote-error rule against a gated
reference, at K in {50, 100, 200} transitions per chain, at N = 250 and N = 1,000 on the WP84
simulated series, and at N = 250 on an archived real BTC-perpetual return series.

## Changes from WP84

1. The warm arm is the library API, not harness code: tick-0 fit at defaults, `Posterior::warm_state()`,
   per tick `WarmState::extend_to(3 + n, 0.0, 1.0)` and `Sampler::run_warm` with `draws(K)`; the result's
   `warm_state()` is the next state. No re-adaptation. Chain gate on the tick-0 fit: chains named by a
   `WarmupStep` / `SampledLogDensity` warning are dropped from the carried state (fewer than 2 left =
   the cell fails, a result). The per-tick seed is `seed * 1_000_003 + 16 * tick`, so chain `c` runs on
   `seed + c`, the WP84 chain seeds.
2. Accuracy is the quote-error rule: sigma_next = exp(h_next / 2); a tick passes if |P50 relative
   error| <= 2 % and |P95 relative error| <= 5 % against the gated reference, with no stuck chain.
3. The reference is gated (below).
4. The reference runs at tick 0 and at every tick (sim N = 250), every 2nd tick (real N = 250) and
   every 5th tick (sim N = 1,000); the warm arms run every tick for 100 ticks.
5. The full-refit baselines run 20 ticks only and are scored at the reference ticks within them.
6. The N = 1,000 reference uses `Limits::max_result_bytes_unchecked(2 GiB)`, no thinning (both N).
7. K in {50, 100, 200}; 8. three seeds; 9. two datasets; 10. three parallel queues; 11. a Python
   `owalnuts.sample_warm` extra; 12. a bit-identity check of `run_warm` against the WP84 harness
   construction on this model (disclosed below).

## Model and data

The WP84 target unchanged (`rust/src/main.rs`, same density code): y_i ~ t_5(beta, exp(h_i/2)),
noncentred AR(1) log-vol with rho = 0.95 fixed, priors mu ~ N(2 log 0.005, 1), log sigma ~ N(log 0.2,
0.5), beta ~ N(0, 0.002), z ~ N(0, 1). Dimension 3 + n.

* **sim**: `models/data-sim.json`, byte-identical to WP84's `models/data.json` (`simulate.py`, seed
  84084, 1,100 returns, truth h). N in {250, 1000}.
* **real**: `models/data-real.json`, 682 Deribit BTC-PERPETUAL 30-minute **bar-close** log returns from
  September, reconstructed by `real_data.py` from the 72 overlapping rolling windows archived in
  `STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-v1/evidence.zip` (consecutive windows
  overlap by 250 bars exactly; the reconstruction asserts it). The receipt-time **midpoint** series the
  task asked for is not archived at length (24 rows in `live-sv-production-smoke-v1`), so this is the
  closest loadable real series; the task's wording is kept in mind when reading the result. Same
  priors as sim; no rescaling (return sd 0.0029 against the prior centre 0.005; log sd^2 = -11.7 is
  1.1 prior sd from mu's prior mean). N = 250 only (682 < 1,100). No truth h, so truth coverage is not
  reported there. WP84 declined to reuse the Deribit receipts because no reuse licence is recorded;
  this study uses the already-archived derived returns at the user's request and records the same
  caveat.

Target check (`run_cells.py check`, BridgeStan 2.9.0 on the box, before the cells): the Rust density
matches `models/sv.stan` on both datasets, lp offset spread < 1e-8 and gradient relative error < 1e-8
at n = 250 and 1,001 (sim) and 250 and 350 (real). Result: pass, lp offset spread <= 1.8e-12 and gradient relative error <= 2.1e-14 on all four (n, dataset) pairs
(`work/target-check.json` on the box, copied to `artifacts/prefreeze/`).

## Stream and quantities

Tick t conditions on the first N + t returns. h_next = mu + rho (h_last - mu) + sigma eps with the
WP84 eps stream (`default_rng(840000 + tick)`, shape (4, 20000), row = chain index), sigma_next =
exp(h_next / 2). Gated: P50 (half-spread) and P95 (risk quote). Reported: P5, mean, the straddle
E[exp(h_next/2)] (Rao-Blackwellised), the arm's own quantile MCSE of P50/P95 (arviz 0.23.4), bulk
ESS and R-hat of h_next, divergences, the fraction of draws inside the reference 90 % interval, and
(sim) coverage of the true h by the arm's 90 % interval.

## Reference, gate, accuracy, latency, drift

**Reference.** Per tick, oWALNUTS at defaults, 4 x 2,000/20,000, best-of-16 starts,
`Limits::admit_worst_case` and `max_result_bytes_unchecked(2 GiB)`. **Gate**: chains named by a
`WarmupStep` or `SampledLogDensity` chain warning are dropped; the tick passes iff >= 3 chains remain
and the rank R-hat of h_next over the remaining chains <= 1.01. A tick failing the gate runs once more
with the next preregistered seed (attempt a at tick t: `seed_base * 1000 + t + 200 a`, a in {0, 1};
seed bases 889450 sim-N250, 890200 sim-N1000, 889500 real-N250). This second attempt is part of the
cell definition, not a rerun. A tick failing both attempts is unscored and counts as a FAILED tick for
every arm scored there. Expected floor (WP84 post hoc): relative MCSE of P50 0.08 % median / 0.29 %
worst, P95 0.20 % / 0.34 %, so the 2 % / 5 % tolerances are 7x / 15x the worst reference MCSE.

**Stuck chain** (every arm): a chain whose median log_sigma is more than 1.0 from the gated
reference's median, or whose median h_last is more than 2.0 away (WP84 post-hoc census rule;
reproduced the sampler's own flags 121/121 there). oWALNUTS flags are recorded as well.

**Accuracy.** A scored tick passes iff |P50 error| <= 2 % AND |P95 error| <= 5 % AND no stuck chain AND
wall under the latency threshold (0.4 s at N = 250, 2 s at N = 1,000). Scored ticks are the reference
ticks >= 1 within the arm's range: per seed 100 (sim-N250), 50 (real-N250), 20 (sim-N1000) for the
warm arms; 20 / 10 / 4 for the 20-tick refit baselines. The warm arm's tick 0 (the full fit) is scored
separately and reported. Latency is the wall per tick from new-target construction (including
`extend_to`) to draws in memory (`run_warm` returned and `warm_state()` taken); writing draws and the
quantile computation are excluded; the Stan arms include the data JSON, the process spawn and the
CSV read (CmdStan) or `with_data` (nutpie), compilation excluded. Latency statistics use all 100 (or
20) ticks; the pass share also at 0.1 s and 0.5 s is reported.

**Pass.** An arm passes at (K, dataset, N) iff the pass share is >= 95 % pooled over the three seeds
AND >= 90 % in every seed AND drift is within bound in every seed. In integers: sim-N250 >= 285/300
pooled and >= 90/100 per seed; real-N250 >= 143/150 and >= 45/50; sim-N1000 >= 57/60 and >= 18/20.

**Drift.** Per seed, mean signed P50 error over the late scored ticks (tick >= 70) minus over the
early ones (1 <= tick <= 30); bound 0.5 percentage points. Windows: 30/31 ticks (sim-N250), 15/16
(real), 6/7 (sim-N1000). With a per-tick P50 error sd of about 0.9 % (K = 200) to 1.8 % (K = 50)
the statistic's sd is about 0.23 % / 0.33 % / 0.5 % at K = 200, so the real and N = 1,000 drift
tests have less power; a miss there without a common sign across seeds is reported as
noise-compatible but still counts against the pass (the rule is mechanical).

**Decision rule.** The README may say "real-time quote refresh at K = k" only for a K that passes on
all seeds, both N (sim-N250, sim-N1000) and every dataset run (sim, real). Otherwise it states the
measured latency, accuracy and the largest tolerance met (first pair, ordered P50 then P95, on the
grid P50 in {1, 2, 5, 10} % x P95 in {2, 5, 10, 20} % with >= 95 % pooled and >= 90 % per seed, no
latency condition) per K, N and dataset.

## Arms and cells

* **warm** K in {50, 100, 200}, seeds 880101–880103, 100 ticks; 9 cells per dataset-N (27).
* **refit** oWALNUTS 4 x 1,000/1,000 defaults, best-of-16 starts, seed `seed * 1000 + tick`, 20
  ticks; reported as sampled and gated (flagged chains dropped, < 2 left = failed tick).
* **cmdstan** CmdStan 2.39.0 defaults via cmdstanpy 1.3.0, 4 parallel chains, 20 ticks (as sampled).
* **nutpie** 0.16.8 defaults, cores = 4, 20 ticks (as sampled).
* **pyextra** `owalnuts.sample_warm` (wheel built on the box from this branch) on a C-ABI translation
  of the same density (`models/sv_cabi.c`, checked against the Rust `eval` at 5 points, `from_cfunc`,
  threads = 4), sim N = 250, K = 200, seed 880101, 100 ticks; tick 0 via `owalnuts.sample` defaults.
  Reported only.
* **ref** three cells (sim-N250 101 ticks, real-N250 51, sim-N1000 21; 173 reference ticks).

58 cells in three queues (`protocol.json` order; `run_cells.py plan`): A on cores 4–7 (ref sim-N1000,
warm sim-N1000, refit sim-N1000, nutpie sim-N1000, refit sim-N250, cmdstan real-N250, refit
real-N250, nutpie real-N250), B on 8–11 (ref sim-N250, ref real-N250, cmdstan sim-N250, nutpie
sim-N250, pyextra), C on 12–15 (warm sim-N250, warm real-N250, cmdstan sim-N1000). Queues run in parallel,
cells sequentially within a queue; a started cell is never rerun; failures are results. Seeds
880101–880103, 889450, 890200, 889500 were grep-verified unused; 84084 is reused on purpose (the
same series as WP84).

## Budget

About 240 lane-minutes from WP84's walls on this box and the pre-freeze smoke: references 42
(sim-N250) + 20 (real) + 25 (sim-N1000, 21 ticks at the measured 69 s), warm 27 cells about 20,
oWALNUTS refits about 30, CmdStan about 90, nutpie about 8, pyextra 3. Queues A/B/C about 80 / 80 /
70 min: about 1.5 h wall. (The first draft planned 13 N = 1,000 reference ticks at an assumed 200 s;
the smoke tick's 69 s paid for every 5th tick instead, decided before the freeze.)

## Predictions (from the WP84 post-hoc numbers, written before any evidence cell)

* P1 sim-N250: K = 200 passes (pooled >= 95 %, every seed >= 90 %, drift within 0.5 pp on 3/3);
  K = 50 fails (pooled 70–80 %); K = 100 fails narrowly (85–95 % pooled).
* P2 sim-N1000: no K passes. K = 200 median latency 0.5–1.2 s, under 2 s on 65–90 % of ticks (fails
  on latency); K = 100 median 0.3–0.6 s, under 2 s on 85–97 %, accuracy 85–95 %; K = 50 under 2 s on
  >= 97 % but accuracy 70–80 %.
* P3 real-N250: same ordering; K = 200 passes with a smaller margin (92–98 %) or fails on one seed;
  K = 50 fails; stuck-chain ticks in the refit baselines more frequent than on sim.
* P4 latency medians (4 pinned cores): sim-N250 K = 50 15–30 ms, K = 100 30–60 ms, K = 200
  60–120 ms; sim-N1000 4–10x those; the 0.1 s share at sim-N250 >= 95 % for K = 50/100, 30–80 % for
  K = 200.
* P5 reference gate: 1–5 of the 173 reference ticks drop a flagged chain; 0–2 need the second seed;
  0 fail both.
* P6 refit baselines: stuck-chain ticks at sim-N250 oWALNUTS 2–8/60, CmdStan 4–12/60, nutpie 0–1/60;
  as-sampled accuracy share nutpie >= 95 %, oWALNUTS and CmdStan 85–95 % (gated oWALNUTS >= 95 %);
  none under 0.4 s at N = 250; nutpie median 1–1.5 s (N = 250), 4–6 s (N = 1,000).
* P7 Python path: median latency 1.0–2.0x the Rust warm200 cell of the same seed (70–200 ms),
  accuracy share within 5 points of it.
* P8 bit-identity holds on all 4 chains.

## Pre-freeze disclosures (not evidence)

* **Bit-identity on this model** (`wp88 bitcheck`, sim N = 250, K = 50, seed 880101, tick 1):
  `run_warm` vs one single-chain `Sampler` per chain with the carried start, step and fixed diagonal
  mass (new coordinate at 0, mass 1), `warmup(0)`, `Adaptation::None`, seed `base + c`: **identical on
  all 4 chains** (draws, diagnostics, effective seed, step, mass; `artifacts/prefreeze/bitcheck.json`;
  tick-0 fit 2.17 s, no flagged chain).
* **Full-size N = 1,000 reference tick** (sim, n = 1,000, diagnostic seed 990001, 4 x 2,000/20,000 with
  the 2 GiB result ceiling): **ran, status ok, 69.0 s wall**, 6.5 M gradient calls, no chain warning, no
  divergence (`artifacts/prefreeze/ref-N1000-smoke.json`); the result ceiling that refused WP84's
  N = 1,000 reference no longer binds.
* **Smoke** (2 ticks of warm, refit, nutpie, CmdStan and pyextra at diagnostic seeds 99xxxx, a 3-tick
  gated reference through the gate code path, `analyze.py` on them): every code path ran; the three
  smoke reference ticks passed the gate at attempt 0 (4 chains, R-hat <= 1.01); CmdStan printed its
  usual non-fatal `student_t_lpdf` scale warnings during warmup (as in WP84); `analyze.py` crashed
  in its table printer on groups with missing cells (`KeyError: 'drift'`), fixed before the freeze
  (pipeline only, no rule changed) and rerun on the smoke. No laptop timing is used anywhere.

## Execution

Queues A/B/C on cores 4–7 / 8–11 / 12–15 (lanes 2–4 of LANES.md) of the shared c7a.4xlarge,
`taskset`-pinned, `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1`, co-tenanted with lane 1 (WP89) and with
each other (shared L3 and memory bandwidth): walls are "pinned, co-tenanted"; accuracy and gradient
counts are unaffected. Box: Rust 1.88.0, CmdStan 2.39.0, nutpie 0.16.8, cmdstanpy 1.3.0, arviz
0.23.4, BridgeStan 2.9.0, numpy 2.5.4.
