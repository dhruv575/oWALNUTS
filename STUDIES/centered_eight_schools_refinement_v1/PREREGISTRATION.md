# WP82 preregistration: refinement spend on the centred eight schools

Frozen before any evidence cell. `protocol.json` is the machine-readable form and wins on any
discrepancy. Ledger id `WP82-CENTERED-EIGHT-SCHOOLS-REFINEMENT-V1`, as assigned by the coordinator.

## Question

`eight_schools_centered` is oWALNUTS's worst per-gradient cell against CmdStan: 0.39x over 18
seeds (WP72, median of paired ratios, min bulk ESS per total gradient). WP80 found part of the
reason. About 30 % of its retained transitions are refined, a refined macro leaf costs about 4.3
gradients, and refinement spend (B4) is 1.38 there and about 0 elsewhere.

This study asks two things:

1. **Where** does the refinement happen, and is the adapted step set by the bulk?
2. Can one of three research candidates lift the cell to >= 0.60x CmdStan **without** costing the
   funnel or five other house models?

No default changes in any outcome.

## What is already known

- **WP42:** `delta = 0.5` costs 0.936x over posteriordb. Refinement is almost all at level 1 on
  16 of 17 models.
- **WP49:** warmup-time adaptive `delta` rules do not qualify. Their worst model was this one
  (0.61x).
- **WP53 / WP66 / WP68:** the default funnel tail is unbiased at 80,000 draws (0.0478 ± 0.0010).
  Ten refinement levels remove funnel divergences but fail posteriordb (0.824).
- **WP73 / WP77:** warmup length and the initial fast phase are not the lever.
- **WP27 (`step_collapse_v1`):** Stan's acceptance statistic alone did not move `sblrc`'s step.
  The metric floor was the cause there.
- **The kernel:** a macro leaf is integrated with `2^k` micro-steps of `h / 2^k` at level `k`. The
  first level whose endpoint error is <= `delta = 1` is accepted, up to eight levels (max depth
  10), and every coarser reverse level must fail. Dual averaging (target 0.8) is driven by the
  transition mean of `exp(-|H_end - H_start|)` of each leaf's **coarsest** attempt, uniformly
  over leaves. A refined leaf therefore enters with a value below `exp(-1)`, but only once,
  whatever it cost.

## Environment (disclosed)

- **Lane:** lane 2 of the shared c7a.4xlarge box, cores 4-7, `taskset -c 4-7` on every process,
  with other lanes active. Walls are pinned, co-tenanted and not used.
- **oWALNUTS:** BridgeStan 2.9.0 without `STAN_THREADS`, `ReplicatedStanTarget` with four
  replicas (WP65-qualified).
- **CmdStan:** 2.39.0 at defaults.
- **Binaries:** the six BridgeStan libraries and CmdStan executables were copied from this lane's
  WP77 copy of the WP73 build. Their sha256 values were checked against WP73's build manifest
  (12 checked, 0 mismatches).
- **Library:** `wt/centered-refine` at main `aa7160bd` plus library commit `70343cdf`. That commit
  adds the default-off research variant `DualAveragingAcceptance::CostWeightedCoarseEndpoint`,
  with `tests/cost_weighted_acceptance.rs`. The variant is bit-identical to the default statistic
  when every leaf costs the same (pinned with one refinement level). Defaults, `ALGORITHM_REVISION`
  and the kernel fingerprints are unchanged.

## Design

- **Seeds:** 6 fresh seeds 821821–821826 (the regression block uses the first 3), and 10 fresh
  funnel seeds 821901–821910, all grep-verified unused.
- **Run shape:** 4 chains x 1,000 warmup / 1,000 draws.

| phase | cells | content |
|---|---:|---|
| T | — | `kernel_fingerprint` (flags off), `stable_metric_stop`, `cost_weighted_acceptance` at the frozen commit (clause K5) |
| E | 24 | telemetry: `eight_schools_centered` and `eight_schools_noncentered` x 6 seeds x {default, CmdStan} |
| C | 18 | `eight_schools_centered` x 6 seeds x {`costda`, `stanacc`, `levels2`} |
| R | 60 | `eight_schools_noncentered`, `sblrc`, `arK`, `gp_pois_regr`, `hmm_example` x 3 seeds x {default, 3 candidates} (the 3 non-centred default cells are phase E's and are reused) |
| F | 40 | Neal's funnel, 10 seeds x {default, 3 candidates}, 4 x 2,000 warmup / 20,000 draws (WP73's shape) |

Cells run one process at a time, model-major, then arm, then seed. The regression models were
fixed here: the non-centred twin; `sblrc` (largest step gap in WP80); `arK` and `gp_pois_regr`
(step-sensitive, refinement-free); `hmm_example` (third in WP80's gap ranking).

## The candidates (all behind research or opt-in flags, all off by default)

| arm | setting | idea |
|---|---|---|
| `costda` | `WarmupConfig::with_dual_averaging_acceptance(CostWeightedCoarseEndpoint)` (new) | Each leaf's coarse value is weighted by its target evaluations. A refined leaf then counts in proportion to what it cost, so the step adapts to the refinement spend. |
| `stanacc` | `with_dual_averaging_acceptance(MeanTrajectoryAcceptance)` (existing) | Stan's `accept_stat__`, `min(1, exp(H_0 - H_leaf))` against the transition's initial Hamiltonian. The step sees the trajectory-level error that accumulates through the neck. |
| `levels2` | `Tuning::max_refinement_levels(2)` (existing; default 8) | At most one halving. A leaf over `delta` at both levels ends the orbit (exhaustion, retained rule `Stop`). Warmup is under the sampler's warmup exhaustion rule. |

**Not chosen:** a larger `delta` in the first slow window only. The step and metric that sampling
uses are set in the later windows, WP49's window-wise `delta` rules did not qualify, and WP42's
`delta` changes cost posteriordb.

## Telemetry (phase E; also recorded for every candidate cell)

Per retained transition the harness records:

- target evaluations, depth, stop and step;
- the selected refinement level (the highest level of any built leaf), refinement attempts, and
  leaves attempted and built;
- the maximum absolute energy error, and whether the transition diverged.

Per warmup transition it records the step-adaptation statistic and the selected level. Each cell
also records a built-leaf histogram by level.

Summaries per cell (stored in the cell JSON):

- **Refinement:** the level histogram; the refined fraction (selected level >= 1); the refined
  gradient share; and gradients per refined and per unrefined transition.
- **Location:** retained transition `t >= 1` starts at draw `t - 1`. Each transition is placed by
  that draw's constrained log tau, in quartiles of the cell's own pooled log-tau draws; Q1 is the
  funnel neck. Per quartile: transitions, refined fraction, gradients per transition and depth.
  Also the fraction of refined transitions that start in Q1.
- **Step:** the final adapted step per chain, against CmdStan's adapted `stepsize__` (median over
  chains per seed, ratio per seed, median over seeds).
- **Acceptance:** for oWALNUTS, the mean adaptation statistic over warmup transitions 950–999 (the
  facade does not capture retained acceptance). For CmdStan, `accept_stat__` over the retained
  draws and over warmup draws 950–999.
- **CmdStan:** `n_leapfrog__`, `accept_stat__`, `treedepth__` and `divergent__` per log-tau
  quartile, on its own draws.

## Predictions (telemetry; descriptive, no decision depends on them)

| id | prediction |
|---|---|
| P1 | On the centred model, >= 50 % of refined transitions start in log-tau Q1, and the refined fraction in Q1 is >= 2x that in Q4. |
| P2 | The oWALNUTS / CmdStan adapted-step ratio is >= 1.0: the step is set by the bulk, not shrunk everywhere. |
| P3 | Refined transitions take >= 40 % of retained gradients, and oWALNUTS's gradients-per-transition Q1/Q4 ratio exceeds CmdStan's `n_leapfrog` Q1/Q4 ratio: the neck is paid for in refinement. |
| P4 | On the non-centred twin, < 5 % of retained transitions are refined. |

## Rule (a candidate qualifies only if all hold)

| clause | condition |
|---|---|
| K1 | On `eight_schools_centered`, the median over the 6 seeds (>= 5 paired ok) of candidate / CmdStan min bulk ESS per **total** gradient is >= 0.60 (WP72 form). |
| K2 | Gates held on the centred model: the candidate's gate passes over the 6 seeds are >= the default's, and its retained divergences summed over the 6 cells are <= the default's. |
| K3 | Funnel, 10 seeds x 4 x 2,000/20,000: \|mean P(omega < -5) − 0.0478\| <= between-seed s.e. |
| K4 | No regression on the 5 models x 3 seeds: gate passes >= the default's, and the geomean over models of the per-model median paired ratio (candidate / default, per total gradient; 3 of 3 paired ok) is >= 0.95. |
| K5 | Phase T passes: `kernel_fingerprint` with flags off, `stable_metric_stop`, `cost_weighted_acceptance`. |

- An errored candidate cell fails its gates and has no ratio.
- A qualifying candidate is **recommended for a posteriordb-wide confirmation**. Nothing is
  flipped here.
- Also reported:
  - K1 per sampling gradient, and a 10,000-resample seed bootstrap interval (rng seed 82);
  - the candidate vs the default on the centred model;
  - the default's own ratio vs CmdStan on both twins.

## Candidate predictions

| candidate | K1 | K2 | K3 | K4 | overall |
|---|---|---|---|---|---|
| `costda` | fails (about 0.45); step 0.7–0.9x the default, refined fraction about halves | holds | holds | holds | not qualified |
| `stanacc` | fails (0.45–0.55); step near CmdStan's | holds | holds | may fail (`sblrc`) | not qualified |
| `levels2` | fails (about 0.45) | holds | **fails** (truncated neck orbits) | holds | not qualified |

Overall I predict that no candidate qualifies.

## What a default change would mean (none is proposed here)

- **`costda` and `stanacc`:** facade adaptation defaults (the `WarmupConfig` acceptance statistic).
  Every adapted run's draws would change, but the kernel, `ALGORITHM_REVISION` and the kernel
  fingerprints (which build `WarmupConfig` directly) would not.
- **`levels2`:** would change `Tuning::default()`, and so the retained kernel.

## Changes to the copied code

- **`src/`:** WP77's (WP73's) `main.rs` and `bin/funnel.rs`, with:
  - this crate's arms;
  - the schema strings;
  - the extra per-transition arrays listed above (`main.rs` only).

  `src/lib.rs` has new arms in WP73's structure.
- **`run_refine.py`:** WP77's `run_confirm.py`, with:
  - phases E / C / R / F (and T) instead of A / F;
  - the `WP82_*` environment names and the lane path;
  - per-cell telemetry summaries for oWALNUTS and CmdStan;
  - per-draw CmdStan sampler columns and per-transition oWALNUTS arrays in the uncommitted `.npz`;
  - a new analysis (telemetry pooling, P1–P4, K1–K5).

  The posteriordb, metric, gate, oWALNUTS-cell, CmdStan-cell and funnel functions are WP77's.
- **`build_models.py`:** WP77's, restricted to the six models.

## Smoke run (disclosed)

Before the freeze, every arm and CmdStan was smoke-tested on the box on the **non-study**
`kidiq-kidscore_momiq` at seed 1, with the funnel at seed 1 for every arm. Output went to the
lane's `smoke/`, never to `artifacts/`. The telemetry summaries' log-tau path was exercised
locally on synthetic arrays (no model run).

Every arm ran, and no code changed after the smoke run. What it showed is disclosed because it was
seen before the freeze:

- **kidiq (all five arms passed):**
  - default: 237k gradients, min bulk ESS 959;
  - `costda`: 275k gradients, ESS 1,303;
  - `stanacc`: 638k gradients (warmup share 0.85), ESS 1,339;
  - `levels2`: 273k gradients, ESS 1,192;
  - CmdStan: 264k gradients, ESS 1,191.
- **Funnel seed 1:**
  - default: P5 0.0569;
  - `costda`: 0.0326;
  - `stanacc`: 0.0519;
  - `levels2`: 0.0000, with 38 divergences and no neck transitions. Its chains did not enter the
    neck.

The candidate set is unchanged. `levels2` stays as the registered test of the "cap refinement"
idea, and its K3 prediction (fails) was already written before the smoke run. A single seed does
not decide K3.

## Rules

PREREGISTRATION.md and protocol.json are committed before the first cell.

- **Execution:** phases T, E, C, R, F in order, one process at a time.
- **Reporting:** every cell is reported; failures and timeouts are results; no reruns and no
  tuning after seeing results.
- **Interruptions:** a cell with no artifact may be rerun once with the same seed, recorded as a
  deviation.
- **Amendments:** only for cells not yet run, committed before them.
