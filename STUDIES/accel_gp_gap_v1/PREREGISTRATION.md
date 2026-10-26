# WP70 preregistration: the accel_gp ESS-per-gradient gap

Frozen before any cell. `protocol.json` is the machine-readable form and wins on any
discrepancy. Ledger id `WP70-ACCEL-GP-GAP-V1`. WP70 was assigned by the coordinator (WP68 and
WP69 are lanes 3 and 4).

## Question

Why is oWALNUTS's min bulk ESS per gradient on `mcycle_gp-accel_gp` about 0.35x CmdStan's, the
worst fixed-16 cell in posteriordb v7 (WP56) and its seed extension (WP62)? This is open
questions 9 and 11 and the `accel_gp` item under 16 in `wiki/open-questions.md`.

## What is already known (read before this freeze)

- **v7 and the seed extension (Windows):**
  - oWALNUTS: 0/6 gates (tail ESS 49–298, R-hat 1.011–1.033), 2.3–2.9 M gradients, zero
    max-depth stops. In chain 0, 35–92 % of retained transitions stop on `reverse_coarser_accepted`.
  - CmdStan: 0/6 gates (55–339 divergences), 5.1–6.0 M gradients, depth-10 caps on 800–2,700 of
    4,000 retained transitions.
  - Adapted steps are similar: oWALNUTS 0.0057–0.0107, CmdStan 0.0049–0.0086.
- **Already tried, all worse than the default on accel_gp:**
  - dense metric: 0.38x CmdStan (WP48/51);
  - `delta = 2`: 0.68x the default (WP34);
  - the zero-weight reverse-coarser policies: 0.61x / 0.70x (WP39/39B);
  - acceptance targets 0.85 and 0.9: 0.52–0.65x the default, on two seeds (WP40).

  WP40 also found that a 5–20 % larger step halves the worst-parameter ESS.

## Environment (disclosed)

- **Lane:** lane 2 of the shared c7a.4xlarge box (cores 4-7, `taskset -c 4-7` on every process),
  with three other lanes active. **Walls are pinned, co-tenanted and not used.** ESS per gradient,
  gates and diagnostics do not depend on co-tenancy.
- **oWALNUTS:** runs through BridgeStan 2.9.0 (library without `STAN_THREADS`) with
  `ReplicatedStanTarget`, four replicas. This is the dispatch WP65 qualified on this host.
- **CmdStan:** 2.39.0 at cmdstanpy defaults.
- **Library:** source `d39efaad`, main at freeze (WP68's study-only `candidate-levels10` feature is off).

## Design

- **Arms and seeds:** 3 fresh seeds (700711–700713, grep-verified unused), 4 chains x
  1,000/1,000, v7 gates and v7 metrics code.
- **Phase 1:** accel_gp x {CmdStan, oWALNUTS defaults}, then the five controls
  (eight_schools_noncentered, kidiq_momhsiq, arK, gp_pois_regr, garch11) x oWALNUTS defaults.
  `diagnose` then evaluates D1–D3 mechanically.
- **Phase 2:** the three candidates, one per hypothesis, on accel_gp and the five controls. All
  three run whatever the diagnostics show. Each is judged by its own rule, and the diagnostic
  verdict for its hypothesis is printed beside it.

## Hypotheses, diagnostics, predictions

| | hypothesis | diagnostic (recorded per cell) | supported if | prediction |
|---|---|---|---|---|
| H1 | **orbit truncation**: retained orbits stop on a failed reverse check (StopOrbit) before a U-turn, so they integrate far shorter than CmdStan's trajectories and the slow coordinates random-walk | D1: retained `reverse_coarser_accepted` fraction; integration-time ratio (median leaves built x h) / (median `n_leapfrog` x eps) | RC >= 0.40 and ratio <= 0.60 | **supported** (RC about 0.6, ratio about 0.4) |
| H2 | **depth cap**: orbits are cut by `max_depth` 10 | D2: retained `maximum_depth` stop fraction | >= 0.05 | not supported (about 0) |
| H3 | **adaptation**: after 1,000 warmup transitions the diagonal metric is further from the posterior scales than CmdStan's | D3: q90 over unconstrained coordinates of \|ln(adapted variance / reference variance)\|, median over chains, ratio oWALNUTS / CmdStan. The reference variance is that of the posteriordb reference draws, unconstrained with BridgeStan. | >= 1.5 | not supported (about 1.1) |

Reported, not gated:

- adapted step ratio (predicted 1.0–1.4);
- CmdStan's mean `accept_stat__` (oWALNUTS records no acceptance statistic on retained transitions);
- warmup gradient share (predicted oWALNUTS >= CmdStan);
- gradients per retained transition;
- refined selected-leaf fraction and level histogram;
- stop counts and integration time by stop reason;
- CmdStan depth-cap fraction;
- the argmin-ESS parameter.

Baseline P0: oWALNUTS/CmdStan accel_gp ESS per gradient in [0.25, 0.55] (point 0.35); 0/3 gates
for both.

## Candidates (research flags only)

| candidate | follows from | setting | prediction |
|---|---|---|---|
| `cand-target095` | H1 | `Adaptation::DualAveraging { target_accept: 0.95 }`: a smaller step, so fewer leaves refine and fail the reverse check | fails R1 (about 0.4); probably fails R3b |
| `cand-depth12` | H2 | `Tuning::default().max_depth(12)` | fails R1 (0.9–1.1x the default); R3 holds |
| `cand-warmup2000` | H3 | 2,000 warmup transitions, 1,000 retained (warmup gradients count) | fails R1 (about 0.35); fails R3b |

**Frozen rule.** A candidate qualifies as a research flag only if all four clauses hold on the
three seeds:

- **R1:** accel_gp candidate / CmdStan min bulk ESS per gradient (seed medians) >= 0.75;
- **R2:** v7 gates held on accel_gp. The candidate's accel_gp passes must be >= the default's,
  and no passing candidate cell on any model may have max |z| > 4;
- **R3a:** control passes over 15 cells >= the default's. "Pass count unchanged" is read as
  "not lower";
- **R3b:** the geomean over the 5 controls of candidate / default ESS per gradient (seed
  medians) >= 0.95.

An errored candidate cell fails its gates and makes its ratio unevaluable. No default and no
library code changes. **Overall prediction:** H1 is the mechanism, and no candidate qualifies.

## Changes to the copied code

**`src/main.rs`** is the WP65 harness, itself the v7 harness plus a dispatch argument. Changes:

- the arms `target095`, `depth12` and `warmup2000`;
- the warmup length and the kernel tuning for the histograms follow the arm;
- per-retained-transition arrays: orbit states, target evaluations, depth, stop, acceptance
  statistic, selected level, max |dH|, step, leaves built;
- warmup transition evaluations;
- the schema string.

**`run_gap.py`** is the WP65 `run_bench.py`. The posteriordb, metric, gate and CmdStan-sampling
code is verbatim. Changes:

- the paths, arms, models and seeds of this protocol, and two phases;
- `run_owalnuts()` and `run_cmdstan()` additionally compute the D1–D3 and reported diagnostics,
  and save the per-transition arrays and the adapted inverse metrics;
- the reference unconstrained variance comes from the posteriordb reference draws;
- `diagnose()` and `analyze()` are new and evaluate the hypotheses and the rule;
- the smoke-test environment overrides are renamed `WP70_SMOKE_*`.

**`build_models.py`** is the WP65 script restricted to the nothreads build and CmdStan for these
six models.

## Pre-freeze smoke run (disclosed)

The binaries and driver were smoke-tested on the box on a **non-study** posterior,
`kidiq-kidscore_momiq`, at seed 1, in every arm. Output went to `~/lanes/accel_gp_gap_v1/smoke/`,
never to `artifacts/`. Two findings changed the diagnostics before the freeze; no threshold and
no prediction changed:

1. The integration time first used the merged `orbit_states` x h. That count excludes
   built-but-unmerged subtrees, and it gave an oWALNUTS/CmdStan ratio of 0.57 on that healthy
   model at equal gradients per transition. D1 therefore uses leaves built x h (the kernel's
   `trajectory_macro_length`, comparable to `n_leapfrog` x eps). The orbit-based figure is
   reported only.
2. oWALNUTS's `acceptance_statistic()` is `None` on retained transitions, so only CmdStan's
   acceptance is reported.

Also checked without sampling: the posteriordb accel_gp reference draws cover all 66
unconstrained coordinates. That is needed for D3.

## Rules

PREREGISTRATION.md and protocol.json are committed before the first cell.

- **Infrastructure:** builds and a smoke run on a non-study posterior with a non-evidence seed.
- **Execution:** phases run in order, one process at a time.
- **Reporting:** every cell is reported; failures and timeouts are results; no reruns; no
  tuning after seeing results.
- **Interruptions:** an interrupted cell with no artifact may be rerun once with the same seed,
  recorded as a deviation.
- **Amendments:** only for cells not yet run, committed before them.
