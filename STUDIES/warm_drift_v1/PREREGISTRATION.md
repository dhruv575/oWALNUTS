# Preregistration: warm_drift_v1 (WP96)

Frozen 2026-10-26 on `wt/warm-drift` (base `main` `f4a01ba6`: the WP87 warm API, WP88 merged; the WP90
trap guard is not yet the default) before the first evidence cell. `protocol.json` is the
machine-readable copy and wins on any discrepancy. Ledger id `WP96-WARM-DRIFT-V1`. Predecessors:
WP84 (`STUDIES/online_sv_quote_v1`), WP88 (`STUDIES/online_sv_quote_v2`, whose gated reference and
2 % / 5 % quote rule are reused unchanged). Open question 22 of `wiki/open-questions.md`.

## Question

The warm continuation (`Sampler::run_warm`) never re-adapts: step and diagonal metric stay those of
the tick-0 fit. WP84 and WP88 saw no drift over 100 ticks. Over 2,000 ticks, and across a regime
change in the data-generating process, does the frozen metric degrade the sigma_next quote against
the 2 % / 5 % rule, and does a cheap periodic or drift-triggered re-adaptation fix it?

## Design decisions that differ from the task text, with reasons

1. **Fixed-lag window of N = 250 latents, not a growing model.** The growing model reaches
   dimension 2,253 at tick 2,000 (about 1 s per warm tick and about 4 min per reference tick from the
   WP88 N = 1,000 figures: 3–4 h on two lanes, over budget), and 1,000-plus old returns would dilute
   the regime change for hundreds of ticks. The fixed window keeps every tick at the WP88 N = 250
   cost (80 ms warm, 11 s reference) and makes the regime change fully visible: the window is
   entirely regime 2 from tick 1,250. The window remap is a harness `shift_window` built from
   `WarmChain`s with `WarmState::new` (the WP91 helper is not on main): the oldest latent is dropped,
   a new one appended at 0 with mass 1, and the first latent becomes
   z'_0 = rho z_0 + sqrt(1 - rho^2) z_1 so that the log-volatility path is preserved exactly
   (h'_i = h_{i+1}); masses: the first latent keeps the old first latent's mass (same role, the
   stationary start), the others shift with their coordinate; step sizes unchanged. `wp96 remapcheck`
   verifies the h-path identity before the freeze (disclosed below).
2. **One reference per stream, not per arm seed.** The reference is a function of the data only
   (two reference seeds would reproduce the same posterior to its 0.1 % floor), so the 162 fits the
   task's 41 x 2 x 2 would cost are spent on **every 25th tick** instead (81 ticks per stream, 40
   scored ticks per half per seed, 80 pooled), which makes the 95 % / 90 % rule less coarse than 20
   ticks per half would.
3. **The drift trigger uses the cost per transition, not the acceptance statistic.** `run_warm`
   runs retained transitions without acceptance capture, so `TransitionDiagnostics::acceptance_statistic()`
   is `None` on warm draws (the facade does not expose `RunConfig::with_acceptance_capture`, and the
   study makes no library change). The mean target evaluations per transition is what a frozen
   step/metric mismatch raises in both directions (refinement when the step is too coarse, longer
   trajectories when too fine) and is what sets the latency. Defined exactly below.
4. **Latency is reported, not part of the pass.** Every re-adaptation tick is also a scored tick
   (multiples of 25), so a 0.4 s condition inside the pass would fail the M = 100 arm on latency
   alone and hide the accuracy answer. Latency median, P99, max, the share under 0.4 s and the
   re-adaptation-tick latencies are reported with their own prediction.

## Model and data

The WP84 target unchanged (density code copied verbatim from the WP88 harness; checked against
`models/sv.stan` there to 1e-12): y_i ~ t_5(beta, exp(h_i/2)), noncentred AR(1) log-vol with
rho = 0.95 fixed, priors mu ~ N(2 log 0.005, 1), log sigma ~ N(log 0.2, 0.5), beta ~ N(0, 0.002),
z ~ N(0, 1). Dimension 3 + 250 = 253 at every tick.

Two 2,250-return streams (`simulate.py`, seed 96096, numpy `default_rng`), sharing one innovation
stream (2,251 standard normals for z, 2,250 t_5 innovations), plus the true h_2250 continuation:

* **shift** (`models/data-shift.json`): regime 1 for returns 0..1249: mu = 2 log 0.005 = -10.5966,
  sigma_h = 0.2, beta = 0 (the WP84 truth); **regime 2 from return index 1250**: mu = -9.5966
  (+1.0) and sigma_h = 0.4 (doubled); the AR(1) recursion continues from h_1249 with the new
  parameters. Return sd 0.0060 before, 0.0201 after.
* **control** (`models/data-control.json`): the same innovations, regime 1 throughout (sd 0.0074
  over the same late range).

Tick t (t = 1..2,000) conditions on returns [t, t + 250): the first regime-2 return enters at
**tick 1,001** and the window is entirely regime 2 from tick 1,250. The regime change is "at tick
1,000" in this sense. Tick 0 is the fit on returns [0, 250).

## Quantities, reference, accuracy (WP88 unchanged except the eps seed base)

h_next = mu + rho (h_last - mu) + sigma eps with eps from `default_rng(9600000 + tick)`, shape
(4, 20000), row = chain index; sigma_next = exp(h_next / 2). Gated: P50 (half-spread) and P95
(risk quote). Reported: P5, mean, the arm's own quantile MCSE of P50 / P95 (arviz), bulk ESS and
R-hat of h_next, divergences, the fraction of draws inside the reference 90 % interval, coverage of
the true h_next by the arm's 90 % interval.

**Reference.** At tick t in {0, 25, 50, ..., 2000} (81 per stream), oWALNUTS at defaults on the
tick's window, 4 x 2,000/20,000, best-of-16 starts, `Limits::admit_worst_case` and
`max_result_bytes_unchecked(2 GiB)`. **Gate** (WP88): chains named by a `WarmupStep` or
`SampledLogDensity` warning are dropped; the tick passes iff >= 3 chains remain and the rank R-hat
of h_next over them <= 1.01; a failing tick runs once more at the next preregistered seed (attempt a
at tick t: `seed_base * 10000 + t + 5000 a`, a in {0, 1}; bases 969450 shift, 969500 control). A
tick failing both attempts is unscored and counts as FAILED for every arm scored there.

**Stuck chain** (WP84 census rule): a chain whose median log_sigma is more than 1.0 from the gated
reference's median, or whose median h_last is more than 2.0 away.

**Tick pass.** |P50 error| <= 2 % AND |P95 error| <= 5 % AND no stuck chain. Scored ticks: half 1 =
{25, ..., 1000} (40 per seed), half 2 = {1025, ..., 2000} (40 per seed); tick 0 scored separately.

**Half pass.** Per (arm, stream, half): pooled over the two seeds >= 95 % of the 80 scored ticks pass
(>= 76) AND every seed >= 90 % (>= 36/40). **Arm pass on a stream** = both halves pass.

**Drift (reported, with its bound flag; not gated).** Per (arm, stream, seed, half): mean signed P50
error over the half's last 10 scored ticks minus its first 10; bound 0.5 pp. With a per-tick P50
error sd of about 0.9 % at K = 200 the statistic's sd is about 0.4 pp, so the bound is a flag, not a
gate.

**Latency.** Wall per tick from new-target construction (including `shift_window` and, when due,
the re-adaptation) to `run_warm` returned and `warm_state()` taken; writing draws excluded.
Reported over all 2,000 ticks: median, P99, max, share under 0.4 s, the median over half 1 and
half 2, the median and max over re-adaptation ticks.

## Arms (K = 200 transitions per chain, 4 chains, the WP88 passing configuration)

Tick 0: 4 x 1,000/1,000 at defaults, best-of-16 starts, `Posterior::warm_state()`, chain gate as in
WP88 (flagged chains dropped; fewer than 2 left = the cell fails, a result). Per tick: the window
target, `shift_window`, the policy's re-adaptation if due, `Sampler::run_warm` with `draws(200)`,
seed `seed * 1_000_003 + 16 * tick` (chain c on `+ c`); the result's `warm_state()` is the next
state. Draws are written at the reference ticks only (compact: 81 x 9.6 KB per cell).

* **frozen**: never re-adapt.
* **m100**: re-adapt at every tick t with t % 100 == 0 (20 per cell; the first after the shift at
  tick 1,100).
* **m500**: re-adapt at ticks 500, 1,000, 1,500, 2,000 (the first after the shift at 1,500).
* **trig**: re-adapt when the cost trigger fires.

**Re-adaptation** (`m100`, `m500`, `trig`): `Sampler::run` with `warmup(200)`, `draws(1)`, chains =
the carried chains, from the chains' current (remapped) positions, `Metric::Diagonal { adapt: true,
initial }` with `initial` the element-wise geometric mean of the carried per-chain mass diagonals
(the API takes one initial diagonal for all chains), the default dual averaging (0.8), seed
`tick_seed + 8` (chains on +8..+11). Its `warm_state()` (last draw, adapted step, adapted mass per
chain) replaces the carried state, except that a chain named by a `WarmupStep` / `SampledLogDensity`
warning keeps its pre-re-adaptation state (per-chain fallback, counted); a run error leaves the
state unchanged (counted). The K-draw refresh then runs from the new state at the same tick, so a
re-adaptation tick's wall contains both. Warmup 200 under the default window policy is 75 initial,
slow windows 25 + 50, 50 terminal.

**Cost trigger** (`trig`). Per tick, C_t = mean of `target_evaluations()` over the tick's chains x
200 transitions, U_t = fraction of those transitions with `position_changed() == false`. With a the
tick of the latest adaptation (0 = the tick-0 fit): baseline = mean C over ticks a+1..a+20; trailing
= mean C (and U) over ticks t-20..t-1. Armed at tick t once t - 1 >= a + 40 (re-adaptations at
least 41 ticks apart); fires when trailing C > 1.5 x baseline C, or trailing U > 0.05. Evaluated at
the start of tick t, before its refresh; a firing re-adapts at tick t. Every tick records C_t, U_t,
the mean depth, the mean step ratio (2^-level of the selected refinement level), the mean maximum
absolute energy error and, for `trig`, the baseline, trailing value, ratio and firing flag.

## Decision rule

The README may say **"the frozen warm path holds for 2,000 ticks and across a regime change"** only
if the `frozen` arm passes both halves on both streams (every seed >= 90 %, pooled >= 95 %).
Otherwise the README names the re-adaptation policy (or policies) that passes both halves on both
streams, with its latency median and P99; if none passes, it says so and reports the largest pass
share per half.

## Cells, order, budget

18 cells: per stream one reference cell (81 ticks) and 8 warm cells (4 policies x seeds 960101,
960102, 2,000 ticks each). Lane 3 (cores 8–11) runs the shift stream: `ref-shift`, then
`warm-frozen-shift-s960101`, `warm-m100-…`, `warm-m500-…`, `warm-trig-…`, then the same four for
seed 960102. Lane 4 (cores 12–15) runs the control stream in the same order. Cells run sequentially
within a lane, the two lanes in parallel; a started cell is never rerun; failures are results.
Seeds 960101, 960102, 969450, 969500 were grep-verified unused on main; 96096 (given by the task)
occurs only as a float substring in two artifacts; diagnostic seeds 99096x are smoke-only.

Budget, from the WP88 walls on this box: reference 81 x ~12 s x 2 = 32 min; warm cells 2,000 x
~80 ms + tick 0 + re-adaptations = 3–4 min each, 16 cells = 60 min; about 95 lane-minutes, about
1 h wall on two lanes after the build, under a 2 h cap. Raw draws: 81 x 9.6 KB per warm cell and
78 MB per reference cell (checksummed, not committed).

## Predictions (written before any evidence cell)

* **P1 frozen.** Passes both halves on the control stream (pooled >= 95 %, both seeds). On the
  shift stream it passes half 1 and **fails half 2** with a pooled pass share of 60–90 %, the P95
  bar failing more often than the P50 bar; its own MCSE of P50 in half 2 is 1.2–2.0 % (half 1:
  0.9 %); its cost ratio C in ticks 1,250–2,000 is 1.3–3x the ticks 1–20 baseline and its half-2
  median latency 1.3–2.5x its half-1 median. No stuck chain (the frozen kernel is a valid MCMC
  transition; the loss is efficiency, not bias).
* **P2 m100.** Passes both halves on both streams. Median latency 75–95 ms, P99 0.4–1.0 s
  (under 1 s), the 20 re-adaptation ticks 0.3–0.9 s each; 0–2 re-adaptations fall back a flagged
  chain over the 80 re-adaptations.
* **P3 m500.** Passes half 1 on both streams and half 2 on the control; **fails half 2 on the shift
  stream** (pooled 70–92 %), because its 19 scored ticks 1,025–1,475 run on the regime-1 metric.
* **P4 trig.** On the shift stream the trigger fires first at a tick in 1,030–1,200 on both seeds
  (the window needs tens of regime-2 returns before the cost moves), then 0–2 more times before
  tick 2,000; on the control stream 0–2 firings per seed over 2,000 ticks. Half 2 on the shift
  stream: pooled 85–97 % (a coin flip on the rule: the ticks between 1,001 and the firing run on
  the frozen metric). P99 latency under 1 s.
* **P5 reference gate.** 0–4 of the 162 ticks drop a flagged chain, 0–1 need the second seed,
  0 fail both. Floor: relative MCSE of P50 median 0.07–0.12 % in half 1 on both streams; on the
  shift stream half 2 the P95 floor is larger (0.3–0.6 %), still 8x under the tolerance. Median
  wall 9–14 s.
* **P6 drift flag.** Within 0.5 pp on >= 26 of the 32 (policy, stream, seed, half) windows; the
  misses without a common sign across seeds.
* **P7 tick 0.** 16/16 tick-0 fits clean (no flagged chain), accurate at tick 0 on >= 15/16.

## Pre-freeze disclosures (not evidence)

(filled in after the smoke, before the freeze commit)

## Execution

Lanes 3 and 4 of the shared c7a.4xlarge (`LANES.md`), `taskset`-pinned, `RAYON_NUM_THREADS=4`,
`OMP_NUM_THREADS=1`, co-tenanted with WP93 on cores 0–7 (shared L3 and memory bandwidth): walls are
"pinned, co-tenanted"; accuracy, ESS and gradient counts are unaffected. Box: Rust 1.88.0, arviz
0.23.4, numpy 2.5.4. Study crate clippy-clean with `-D warnings` on 1.88 (Windows gnu) before the
freeze. No laptop timing is used anywhere.
