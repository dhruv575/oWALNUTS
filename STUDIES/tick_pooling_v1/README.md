# Tick pooling of warm draws (WP93): can K per tick fall below 200 if the quote pools the last H ticks?

Status: preregistered at `446d0caa` (freeze; draft `ae52d8a1`; pipeline-only amendment `56d49780` before any cell),
base `main` `6dae32bd`, no library change; executed 2026-10-26 23:52–00:29 UTC on the shared Linux box, lanes 1 and 2
(cores 0-3 / 4-7), pinned, co-tenanted. 17/17 cells exited 0; none rerun. Tables: `artifacts/results-table.md`;
machine-readable `artifacts/summary.json`, `artifacts/per-config.json`; post hoc `artifacts/posthoc-pf-lagnorm.md`.

## Verdict

**No pooled configuration meets the quote rule. The README may say "K = 200 per tick with a pool of 1 tick meets the
quote rule" and nothing smaller: that is WP88's no-pooling result (here 95.0 % pooled, exactly the 285/300 threshold;
seeds 98 / 96 / 91 %; drift within 0.37 pp; 77.6 ms median per tick).** Every H >= 5 configuration of the primary
(as-is) estimator fails at every K with a pass share of 10–32 %, and the share hardly depends on K (K = 5: 10–21 %,
K = 200: 11–32 %): the pools are bias-limited, not noise-limited. The reason is in the reference itself: the gated
reference's own P50 of sigma_next moves **3.4 % per tick (median; 27 % of ticks within 2 %)**, 9.4 % over 5 ticks and
10.1 % over 10, so a draw that is even one tick stale usually misses the 2 % half-spread tolerance. The premise of the
question ("the posterior moves little per tick") is false for this model at N = 250: one t_5 return moves the filtered
log-volatility by about 0.07. Exponential weighting beats uniform at every H >= 5 (by 2–7 points), as predicted, and
still fails. Re-propagating the stale latent through the AR(1) with fresh noise (`prop`) is worse: it inflates the spread
and biases the risk quote high by +3 % (H = 5) to +9 % (H = 20). The preregistered likelihood-reweighted variant (`pf`)
is unbiased (signed errors within 0.2 %, 0.90 of its mass inside the reference 90 % interval) but reached only 92 % at
K = 200 and 58 % at K = 50, because its weights were normalised across the whole pool and the lag-0 exact draws were
swamped (its weight ESS at H = 5 was below the H = 1 pool's 800 draws); see the post hoc below.

| K | lib ms median (p95) | H = 1 (= WP88) | best as-is pool (H, w) | best prop pool | best pf pool (frozen) | own MCSE P50 at H = 1 | rule |
|---|---|---|---|---|---|---|---|
| 5 | 2.2 (3.5) | 13.3 % | 20.7 % (10, exp) | 20.0 % (5, exp) | 10.0 % (10) | 7.52 % | FAIL at every H |
| 10 | 4.1 (5.1) | 19.0 % | 22.7 % (5, exp) | 22.0 % (5, exp) | 17.7 % (5) | 4.02 % | FAIL at every H |
| 20 | 7.9 (9.9) | 33.7 % | 27.0 % (5, exp) | 27.3 % (5, exp) | 28.7 % (10, exp) | 2.86 % | FAIL at every H |
| 50 | 19.4 (22.3) | 53.3 % | 29.7 % (5, exp) | 31.7 % (5, exp) | 57.7 % (5) | 1.79 % | FAIL at every H |
| 200 | 77.6 (101.0) | **95.0 %** (98 / 96 / 91) | 32.3 % (5, exp) | 34.3 % (5, exp) | 92.3 % (5, exp) | 0.89 % | **PASS at H = 1 only** |

Pass = |P50 err| <= 2 % and |P95 err| <= 5 % against the gated reference, no stuck chain, library call < 0.4 s, on
>= 95 % of 300 ticks pooled and >= 90 % per seed, drift within 0.5 pp per seed. Latency was never binding (100 % of ticks
under 0.4 s at every K; K <= 20 under 10 ms on >= 96 % of ticks); the analysis-side pooling step costs 0.03–2.6 ms.

### Stale-latent bias (K = 200 pools, the least Monte Carlo noise)

| H | weighting | as-is \|P50 err\| median | as-is signed P50 | as-is signed P95 | prop signed P95 | reference lag curve at j = H-1: \|P50 change\| median / within 2 % |
|---|---|---|---|---|---|---|
| 5 | uniform / exp | 3.78 % / 2.93 % | +0.61 % / +0.44 % | +1.08 % / +0.86 % | +3.17 % / +2.40 % | 7.5 % / 12 % (j = 4) |
| 10 | uniform / exp | 6.19 % / 5.08 % | +1.14 % / +0.88 % | +2.21 % / +1.85 % | +6.01 % / +4.84 % | 10.2 % / 11 % (j = 9) |
| 20 | uniform / exp | 7.34 % / 5.82 % | +1.42 % / +1.18 % | +3.30 % / +2.92 % | +9.21 % / +7.78 % | 14.5 % / 9 % (j = 19) |

The signed as-is bias is positive (the series' volatility fell over the 100 ticks, so stale draws sit high) and small
against the per-tick scatter: the pooled quote is wrong by 3–7 % on the median tick in either direction, because the
posterior wanders 3.4 % per tick around a slow trend. Full lag curve (j = 1..20) in `artifacts/results-table.md`.

### Honest README sentence

"On a 250-return stochastic-volatility model fed one return per tick, pooling the warm draws of the last 5–20 ticks as
they are does not let the per-tick transition count fall below 200: the posterior of next-period volatility moves 3.4 %
per tick (median), more than the 2 % half-spread tolerance, so stale draws bias the quote (10–32 % of ticks within
2 % / 5 % at every K), and only 4 x 200 transitions without pooling (78 ms on 4 pinned cores) meet the bar (95 % of
ticks). Post hoc, not preregistered: reweighting each stale tick's draws by the likelihood of the returns received since
(a particle-filter step costing 0.2–2.6 ms) would let 4 x 20 transitions with a 20-tick pool (7.9 ms) reach 95 %,
pending a preregistered confirmation (WP93)."

## Post hoc (not preregistered; does not change the verdict): `pf` with per-lag normalisation

`posthoc/pf_lagnorm.py` normalises the likelihood weights within each lag group (self-normalised importance sampling per
stale tick, then the time weights mix the groups; the lag-0 group is the exact current draws). Same ticks, reference and
rule, applied for information only (`artifacts/posthoc-pf-lagnorm.md`):

| K | H = 5 uniform / exp | H = 10 uniform / exp | H = 20 uniform / exp | wESS at H = 20 | would pass |
|---|---|---|---|---|---|
| 5 | 41.3 / 34.7 % | 57.0 / 58.3 % | 68.3 / 72.3 % | 256 / 263 | no |
| 10 | 54.0 / 53.7 % | 75.7 / 72.0 % | 78.7 / 83.7 % | 495 / 522 | no |
| 20 | 78.3 / 76.7 % | 87.7 / 85.7 % | **95.0 / 95.3 %** (96 / 96 / 93; drift within 0.42 pp) | 977 / 1031 | **yes at H = 20** |
| 50 | **96.0** / 94.3 % | **95.7 / 97.0 %** | 97.3 / **97.0 %** | 2390 / 2593 | yes at H = 5 (uniform), 10, 20 (exp; uniform misses one drift window at -0.52 pp) |
| 200 | 100 / 100 % | 100 / 100 % | 100 / 100 % | 9557 / 10323 | yes at every H (\|P50 err\| median 0.17–0.29 % against 0.61 % at H = 1) |

The importance weights are efficient: weight ESS per lag group is 97 % of its draws at lag 1, 82 % at lag 5, 67 % at
lag 10 and 45 % at lag 19 (the same at every K), so the j returns received since a draw was made do not destroy it,
they only need to be conditioned on. With that done, the pooled quote at K = 20, H = 20 has a weight ESS of about 1,000
(the K = 200 single-tick pool has 800 draws, ESS 1,005) and the same pass share; at K = 200, pooling 5–20 ticks brings
the half-spread error from 0.61 % to 0.2–0.3 %, close to the reference floor. K = 5 and K = 10 stay below 85 % even at
H = 20 (ESS 260–520). This is the candidate for the next preregistered study; it cannot be claimed from this one.

## What was run

* Model and data as WP84 / WP88 (same density code, the WP84 simulated series, seed 84084), N = 250, 100 ticks of one
  return each, three seeds (931201–931203).
* Warm arm = the library path: a gated tick-0 default fit (4 x 1,000/1,000; a trapped chain triggers one retry at the
  next seed, then flagged chains are dropped), `Posterior::warm_state()`, per tick `WarmState::extend_to(3 + n, 0.0, 1.0)`
  and `Sampler::run_warm` with `draws(K)`, K in {5, 10, 20, 50, 200}; every tick's draws (mu, log_sigma, beta, h_last)
  stored as f32.
* Gated reference at every tick 0..100 (4 x 2,000/20,000, the WP88 gate: flagged chains dropped, second seed below 3
  chains or R-hat(h_next) > 1.01), split over the two lanes for scheduling.
* Pooling (analysis-side): at tick t the pool holds the draws of the last H ticks (H in {1, 5, 10, 20}), uniform or
  exponential (half-life H/2) time weights, and three readings of a stale draw: **asis** (its own h_next, j ticks stale),
  **prop** (its last latent re-propagated j + 1 AR(1) steps with fresh noise), **pf** (prop, reweighted by the likelihood
  of the j returns received since; weights normalised across the pool). 120 configurations on the same 300 ticks.
* Rule (WP88's): sigma_next = exp(h_next/2); a tick passes if |P50 err| <= 2 % and |P95 err| <= 5 % vs the gated
  reference, no stuck chain, library call < 0.4 s; a configuration passes at >= 95 % of 300 ticks pooled, >= 90 % per
  seed, drift |late - early signed P50 error| <= 0.5 pp per seed. The README may name "K = k with a pool of H ticks" only
  for a configuration passing on all three seeds.

## Gated reference and tick-0 gates

| ticks | ok | second seed | ticks with a trapped chain dropped | min chains | max R-hat(h_next) | rel. MCSE P50 med / max | rel. MCSE P95 med / max | min ESS | sampler wall median / max | lane walls |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 101 | 0 | 7 (ticks 6, 11, 27, 29, 54, 64, 71) | 3 | 1.0003 | 0.08 % / 0.38 % | 0.20 % / 0.58 % | 3,301 | 10.8 s / 258 s | 28.6 + 34.2 min |

Every trapped reference chain was the WP89 signature (end-of-warmup step 1e-5 to 1e-10, log density 600 to 4,000 below
the other chains, R-hat 1.59 with that chain and <= 1.005 without), named by `WarmupStep` and `SampledLogDensity` on
7/7 ticks; dropping it left the floor at 0.08 % / 0.20 % (worst 0.38 % / 0.58 %, still 5x and 9x under the tolerances).
Seven of 101 is more than WP88's one of 101 on the same series (different seeds); the WP90 guard, default on this base,
did not prevent them. The driver wall per reference tick (18.1 s median) exceeds the sampler wall (10.8 s) by the
process spawn, the 1.3 MB draw file and the R-hat on 80,000 draws.

Tick-0 fits: seed 931202 hit a trapped chain at attempt 0 (chain 2, step 8.9e-10, log density -3,667 against +526,
17.0 s) and the retry at 931212 was clean (2.0 s); seeds 931201 and 931203 were clean at attempt 0 (2.1–2.2 s). All 15
cells carried 4 chains; no warm tick had a stuck chain or a divergence.

## Predictions

* P1 (H = 1 reproduces WP88) **held**: K = 200 95.0 % (95–98 predicted), K = 50 53.3 % (50–60), K = 20 33.7 % (25–45),
  K = 10 19.0 % (15–35), K = 5 13.3 % (5–25).
* P2 (as-is fails at every H >= 5, <= 45 %) **held** (max 32.3 %); the clause "|P95 err| median > 3 % at H >= 5" missed
  narrowly on the exponential H = 5 pools (2.86–2.96 %).
* P3 (exp beats uniform at every H >= 5, no as-is pass) **held** in direction on 15/15 (K, H) pairs; the margin was 2–7
  points, below the predicted 5–15.
* P4 (prop fails, P95 bias >= +3 % at H >= 10) **held** (+4.3 to +9.5 %).
* P5 (pf passes at K = 50, H >= 10; K = 20 H = 20 at 85–95 %) **missed**: the preregistered pf passed nowhere (K = 50
  best 57.7 %, K = 20 H = 20 21.3 %) because of the cross-pool normalisation; smallest passing K 200, as-is 200.
* P6 (latency) **held** except K = 20 at 7.9 ms against 8–14 ms; pooling step < 5 ms held (2.6 ms worst).
* P7 (as-is bias positive +0.5 to +1.5 % at H = 10 uniform; prop and pf |signed P50| < 0.5 % at K = 200) **partial**:
  as-is +0.83 to +1.37 % held; pf within 0.1 % held; prop +1.0 to +2.9 % missed.
* P8 (gate: 0–3 flagged reference ticks, 0–1 second seeds, 0 both; 0–2 tick-0 retries) **partial**: 7 flagged ticks
  (missed), 0 and 0 (held), 1 of 3 tick-0 seeds retried (held).
* P9 (drift within 0.5 pp on every passing configuration; some as-is H >= 10 exceed it) **held**: -0.15 / +0.30 /
  -0.37 pp at K = 200 H = 1; as-is H >= 10 at -0.5 to -3.7 pp on 28 of 30 seed-configurations.

## Reading

1. **Pooling as-is cannot work on a posterior that moves faster than the tolerance.** The scored quantity is a one-step
   forecast quantile conditioned on data up to the tick; it is a random walk with 3.4 % steps against a 2 % band. No
   weighting fixes a lag: at H = 5 the exponential weights (half-life 2.5) still give the lag-1 to lag-4 draws 70 % of
   the mass.
2. **The stale draws are not worthless, they are unconditioned.** Weighted by the likelihood of the returns received
   since, a draw keeps 97 % of its weight ESS after one tick and 45 % after 19 (post hoc), so the information in a
   20-tick pool is about 10x a single tick's. The frozen pf threw this away by normalising across the pool: the density
   of a return is about 70 per unit in these units, so the lag-j group's unnormalised weight scaled like 70^j and the
   oldest group dominated. That is an analysis error of this study, disclosed here, and the corrected estimator is post
   hoc.
3. **K = 200 at H = 1 passed by exactly one tick** (285/300): the K = 200 margin on this series is thin; WP88's 96.7 %
   with other seeds and the 0.89 % own MCSE say the same.
4. **The reference trapped a chain on 7 % of ticks** with the WP90 guard on by default; the gate handled every one.
5. **Latency is a flat cost curve**: 2.2 ms at K = 5 to 77.6 ms at K = 200, linear in K above 10, with a 2 ms floor
   (target construction, `extend_to`, four threads); the pooling arithmetic is below 3 ms even at 16,000 draws.

## Anomalies and amendments

* Amendment 1 (pipeline only, before any cell, `56d49780`): the lane driver crashed before its first cell because the
  checkout has no `artifacts/` directory; it now creates it. No cell, seed or rule changed.
* Reference walls were 28.6 and 34.2 lane-minutes against a budgeted 2 x 9.5: the sampler wall per tick matched WP88
  (10.8 s) but the driver overhead was 7 s per tick and one tick took 258 s (a trapped-chain warmup). Nothing rerun.
* The preregistered `pf` normalisation is wrong for mixing lag groups (Reading 2); the frozen tables are reported as
  frozen and the corrected variant is a labelled post hoc.
* Raw draws (`artifacts/cells/**/*.f32`, 135 MB) are checksummed but not committed.

## Rerun

On the box (see `box/`): `box/build.sh`, then `box/lane.sh 1` and `box/lane.sh 2` in parallel under `nohup`; then
`python analyze.py` (arviz 0.23.4, numpy; 26 s) rebuilds the tables from `artifacts/cells`, and
`python posthoc/pf_lagnorm.py` the post-hoc table.
