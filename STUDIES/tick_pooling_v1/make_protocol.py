#!/usr/bin/env python3
"""Write protocol.json (the machine-readable preregistration of WP93 tick_pooling_v1)."""
import hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_SHA = hashlib.sha256((HERE / "models" / "data.json").read_bytes()).hexdigest()

N, TICKS = 250, 100
K_GRID = [5, 10, 20, 50, 200]
H_GRID = [1, 5, 10, 20]
ARM_SEEDS = [931201, 931202, 931203]
REF_SEED_BASE = 939460
TICK0_RETRY_STEP = 10

cells = []
cells.append(dict(id="ref-lo", arm="ref", N=N, ticks=list(range(0, 51)), lane=1))
cells.append(dict(id="ref-hi", arm="ref", N=N, ticks=list(range(51, 101)), lane=2))
lane_of = {}
for K in K_GRID:
    lane_of[(K, ARM_SEEDS[0])] = 1
    lane_of[(K, ARM_SEEDS[1])] = 2
for K in K_GRID:
    lane_of[(K, ARM_SEEDS[2])] = 1 if K in (5, 10, 20) else 2
order = [(K, ARM_SEEDS[0]) for K in K_GRID] + [(K, ARM_SEEDS[1]) for K in K_GRID] + [(K, ARM_SEEDS[2]) for K in K_GRID]
for K, s in order:
    cells.append(dict(id=f"warm{K}-s{s}", arm="warm", N=N, K=K, seed=s, ticks=TICKS, lane=lane_of[(K, s)]))

proto = dict(
    wp="WP93",
    ledger_id="WP93-TICK-POOLING-V1",
    base="main 6dae32bd (WP87 warm API, WP90 trapped-chain guard default); no library change",
    question="With the quote computed from a POOL of the warm draws of the last H ticks, can K transitions per chain per tick "
             "fall far below 200 while the quote still meets the WP88 2 % / 5 % rule against a gated reference?",
    model=dict(source="market_uncertainty_v1 sv_prototype Target, P=1 intercept, K=0 flow (WP84 target, density code unchanged from WP88)",
               rho=0.95, nu=5, coordinates="[mu, log_sigma, beta, z[n]]",
               priors="mu~N(2 log 0.005,1), log_sigma~N(log 0.2,0.5), beta~N(0,0.002), z~N(0,1)"),
    data=dict(file="models/data.json", sha256=DATA_SHA,
              source="WP84 simulate.py, seed 84084, 1,100 returns + truth h; byte-identical to online_sv_quote_v1/models/data.json "
                     "and online_sv_quote_v2/models/data-sim.json"),
    stream=dict(N=N, ticks=TICKS, obs_per_tick=1, posterior_at_tick_t="first N+t returns; tick t's new return is y[N+t-1] (0-indexed)"),
    quantities=dict(
        h_next="mu + rho (h_last - mu) + exp(log_sigma) eps, eps[c,j] = default_rng(eps_seed_base+tick).normal(size=(4,20000))[c,j] "
               "(chain index c of the arm or reference; the WP84/WP88 common stream)",
        eps_seed_base=840000,
        sigma_next="exp(h_next/2)",
        gated=["P50 (half-spread)", "P95 (risk quote)"],
        reported=["P5", "mean", "arm's own quantile MCSE (arviz) of P50/P95 at H = 1", "bulk ESS and R-hat of h_next at H = 1",
                  "weight ESS of the pf pool", "fraction of pooled h_next draws inside the reference 90 % interval"],
        quantile="weighted quantile by linear interpolation of the midpoint CDF (sorted values x_i with normalised weights w_i, "
                 "c_i = sum_{k<=i} w_k - w_i/2, q(p) = interp(p, c, x), clamped at the ends; uniform weights = Hyndman-Fan type 5); "
                 "used for every arm AND for the reference",
    ),
    reference=dict(
        arm="oWALNUTS defaults 4 x 2000/20000 per tick, best-of-16 starts, Limits::admit_worst_case + max_result_bytes_unchecked(2 GiB)",
        gate="drop chains named by a WarmupStep or SampledLogDensity chain warning; pass iff >= min_chains remain AND rank R-hat(h_next) "
             "over the remaining chains <= max_rhat (arviz 0.23.4) -- the WP88 gate unchanged",
        min_chains=3, max_rhat=1.01, attempts=2, attempt_seed_step=200, seed_base=REF_SEED_BASE,
        seed_rule="attempt a at tick t: seed_base*1000 + t + 200*a; attempt 1 only when attempt 0 fails the gate (part of the cell, not a rerun)",
        gate_failed="a tick failing both attempts is unscored and counts as a FAILED tick for every configuration scored there",
        ticks="0..100, every tick (adjusted from the task's 'every 10th tick': 11 scored ticks per seed cannot resolve a 95 % / 90 % rule, "
              "one miss decides; every tick costs 101 x ~11 s = 19 lane-minutes, within budget, and makes the scored set the WP88 one, 300 ticks)",
        split="cell ref-lo = ticks 0-50 on lane 1, cell ref-hi = ticks 51-100 on lane 2 (the same seed rule; the split is only scheduling)",
    ),
    arms=dict(
        warm="LIBRARY path: gated tick-0 default fit 4 x 1000/1000 (see tick0_gate), Posterior::warm_state(), then per tick "
             "WarmState::extend_to(3+n, 0.0, 1.0) and Sampler::run_warm with draws(K), seed = seed*1000003 + 16*tick (chain c on seed+c), "
             "threads 4, Limits::admit_worst_case; the result's warm_state() is the next state; no re-adaptation",
        K=K_GRID,
        seeds=ARM_SEEDS,
        tick0_gate=f"attempt 0 at the cell seed; if a chain is named by a WarmupStep/SampledLogDensity warning (a trapped chain), one more "
                   f"attempt at seed + {TICK0_RETRY_STEP}; the last attempt's flagged chains are dropped from the carried state (WP88 rule), "
                   f"fewer than 2 chains left = the cell fails (a result). The tick-0 fit is outside the latency statistics.",
        tick0_retry_seed_step=TICK0_RETRY_STEP,
        draws_stored="per tick [chain][draw][4] f32 = mu, log_sigma, beta, h_last (tick 0 too)",
    ),
    pooling=dict(
        H=H_GRID,
        pool="at tick t the pool holds the draws of ticks max(1, t-H+1)..t (all kept chains, all K draws per chain); tick 0 (the 1,000-draw "
             "full fit) is never pooled; for t < H the pool is shorter (the online cold start), these ticks are scored like any other and the "
             "pass share over ticks >= 20 (every pool full) is also reported",
        weighting=dict(uniform="w_j = 1", exp="w_j = 2^(-j / (H/2)) for a draw of lag j = t - s ticks (half-life H/2); at H = 1 both are the same"),
        variants=dict(
            asis="a pooled draw from tick s = t-j is used AS IS: its h_next (a draw of h_{N+s+1} under the tick-s posterior) stands in for "
                 "h_{N+t+1}; the coordinate is j steps stale and ignores the j returns received since",
            prop="the stale draw's last latent h_{N+s} is re-propagated through the AR(1) j+1 steps with fresh noise "
                 "(default_rng(prop_seed_base + t), one stream per tick, lags in increasing order), giving a draw of h_{N+t+1} under the "
                 "tick-s posterior's (j+1)-step predictive; still ignores the j new returns",
            pf="as prop, but the propagated path h_{N+s+1..N+t} is weighted by the likelihood of the j new returns y[N+s..N+t-1] "
               "(t_nu(beta, exp(h/2)) densities), i.e. a bootstrap particle-filter step from the stale draws; the time weight multiplies "
               "the likelihood weight; weights normalised within the pool; the weight ESS is reported",
        ),
        prop_seed_base=851000,
        configurations="K x H x weighting x variant = 5 x 4 x 2 x 3 = 120 (the H = 1 uniform/exp pairs coincide; at H = 1 all three variants "
                       "coincide up to the fresh noise of prop/pf); each is scored on the same 300 ticks",
    ),
    accuracy=dict(
        tolerance_p50=0.02, tolerance_p95=0.05,
        rule="a scored tick passes iff |P50 sigma_next rel. error| <= 0.02 AND |P95 rel. error| <= 0.05 vs the gated reference AND no stuck "
             "chain at the newest tick AND the library-call wall of the newest tick < threshold",
        stuck_chain="a chain of the newest tick's draws is stuck when the median of its log_sigma draws is > 1.0 from the gated reference's "
                    "median log_sigma, or the median of its h_last draws > 2.0 from the reference's median h_last (WP84/WP88 census rule)",
        scored_ticks="reference ticks 1..100 of every seed (100 per seed, 300 pooled) for every configuration; tick 0 scored separately",
        **{"pass": "a configuration (K, H, weighting, variant) passes iff its pass share is >= 0.95 pooled over the three seeds (>= 285/300) AND "
             ">= 0.90 in every seed (>= 90/100) AND drift is within bound in every seed"},
    ),
    latency=dict(
        definition="wall per tick of the library call: from Sv::new (new target) through WarmState::extend_to and Sampler::run_warm to "
                   "warm_state() taken; draw file writing excluded; the analysis-side pooling cost (numpy, per H and variant) is timed "
                   "and reported separately, not gated",
        threshold_s=0.4, also_reported_s=[0.01, 0.05, 0.1],
    ),
    drift=dict(statistic="per seed and configuration: mean signed P50 relative error over late scored ticks (tick >= 70) minus over early "
                         "scored ticks (1 <= tick <= 30)", bound=0.005, windows="30 early / 31 late ticks"),
    stale_bias=dict(
        reported="(a) reference lag curve: |P50_ref(t-j)/P50_ref(t) - 1| and the P95 analogue for j in 1..20, median and P95 over ticks and "
                 "the signed mean (the staleness effect with no Monte Carlo noise); (b) per configuration the signed mean P50 and P95 error "
                 "pooled over seeds; (c) the K = 200 pools (least MC noise) as the direct stale-bias estimate per (H, weighting, variant)"),
    decision_rule="The README may say 'K = <k> per tick with a pool of <H> ticks meets the quote rule' only for a configuration that passes on "
                  "all three seeds (the pass definition above), naming its weighting and variant; the primary answer is the smallest K at "
                  "which some (H, weighting, variant) passes, with that K's measured latency. Otherwise the README states the measured "
                  "pass shares, latency and stale bias per (K, H).",
    predictions=dict(
        P1="H = 1 reproduces WP88: K = 200 passes (95-98 % pooled), K = 50 fails (50-60 %); K = 20 fails (25-45 %), K = 10 (15-35 %), K = 5 (5-25 %)",
        P2="asis pooling fails at every K for every H >= 5 (pooled pass share <= 45 %): the gated reference's own P50 moves 3-4 % per tick "
           "(WP88 reference series, lag-1 median |change| 3.5 %, lag-5 9 %, lag-10 10 %), so stale draws miss the 2 % P50 bar more often than "
           "small-K noise does; the as-is pools are biased on P95 as well (|P95 err| median > 3 % at H >= 5)",
        P3="exponential weighting beats uniform at every H >= 5 for asis (higher pass share by 5-15 points) but no asis pool passes",
        P4="prop fails at every (K, H >= 5): the (j+1)-step predictive reverts towards mu and inflates the spread, so its P95 is biased high "
           "(signed mean P95 error >= +3 % at H >= 10)",
        P5="pf is the only pooling that can pass: K = 50 with H in {10, 20} passes (>= 95 % pooled, >= 90 % per seed); K = 20 with H = 20 "
           "reaches 85-95 % and fails; K = 5 and K = 10 fail at every H (< 85 %); the smallest passing K is therefore 50 (pf, H >= 10), "
           "and 200 for the as-is quote (H = 1)",
        P6="latency medians (4 pinned cores): K = 5 2-6 ms, K = 10 4-9 ms, K = 20 8-14 ms, K = 50 18-24 ms, K = 200 75-90 ms; "
           "the pooling step costs < 5 ms per tick at H = 20",
        P7="signed stale bias: asis pools have a positive mean P50 error (+0.5 to +1.5 % at H = 10 uniform; the series' volatility fell over the "
           "100 ticks), prop and pf have |signed P50| < 0.5 % at K = 200",
        P8="gate: 0-3 of 101 reference ticks drop a flagged chain, 0-1 need the second seed, 0 fail both; 0-2 of the 15 tick-0 fits need the retry",
        P9="drift: within 0.5 pp on every seed for every passing configuration; some H >= 10 asis configurations exceed it",
    ),
    budget="about 25 lane-minutes: references 2 x 9.5 min (51 + 50 ticks at ~11 s, WP88's wall), warm cells 15 x ~15 s; two lanes in "
           "parallel, about 12 min wall plus the build; analysis ~5 min on the box",
    software=dict(rust="1.88.0", arviz="0.23.4", numpy="box ~/venv"),
    execution="lanes 1 and 2 (cores 0-3 and 4-7) of the shared c7a.4xlarge, taskset-pinned, RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1, "
              "co-tenanted with WP96 on cores 8-15: walls are 'pinned, co-tenanted'; accuracy and gradient counts unaffected",
    discipline="two lanes run in parallel, cells sequential within a lane in protocol order; a started cell is never rerun (an existing "
               "output directory is skipped); failures are results; the reference's second attempt and the tick-0 retry are parts of the cell",
    cells=cells,
    seeds=dict(arms=ARM_SEEDS, tick0_retry=[s + TICK0_RETRY_STEP for s in ARM_SEEDS], reference_base=REF_SEED_BASE,
               prop_noise_base=851000, data=84084, diagnostic="99xxxx range for the pre-freeze smoke, never scored",
               verified="grep-verified unused before the freeze (see PREREGISTRATION.md)"),
)
(HERE / "protocol.json").write_text(json.dumps(proto, indent=1) + "\n", encoding="utf-8")
print("wrote protocol.json:", len(cells), "cells; data sha256", DATA_SHA[:16])
