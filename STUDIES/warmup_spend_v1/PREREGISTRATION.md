# WP73 preregistration: warmup gradient spend against CmdStan and nutpie, and three research schedules

Frozen before any cell. `protocol.json` is the machine-readable form and wins on any
discrepancy. Ledger id `WP73-WARMUP-SPEND-V1`. WP73 was assigned by the coordinator (WP71 and
WP72 are lanes 3 and 1).

## Question

WP58 attributed the remaining per-gradient gap to nutpie to two causes:

- warmup gradient spend;
- the gradient-informed metric.

Lane 3 (WP71) tests the metric. This study takes the spend. It has two parts:

1. **Descriptive.** How much of its gradient budget does oWALNUTS spend before the first
   retained draw, and in which warmup phase, against CmdStan and nutpie on the 17 house models?
2. **Candidates.** Does any of three research warmup schedules buy at least 1.10x min bulk ESS
   per total gradient without losing a gate?

## What is already known (read before this freeze)

- **WP58.** Warmup cost was 44 % of the pooled log gap to nutpie. It came from:
  - `hier`, 83 %: oWALNUTS spent 72 % of its gradients in warmup, nutpie 49 %;
  - `gauss100`, 16 %;
  - `eight`, 1 %.

  These are PyMC models, and none is a posteriordb house model. On the three house models WP58
  ran (eight_schools_noncentered, gp_pois_regr, lotka_volterra), oWALNUTS's warmup shares were
  within 0.02 of nutpie's.
- **WP40** (older defaults, Windows, unpreregistered). oWALNUTS's warmup gradients were 1.56x
  CmdStan's on 14 healthy models. Per transition, against CmdStan:
  - initial fast phase 2.07x;
  - slow windows 1.14–1.27x;
  - terminal window 1.01x.

  Four warmup levers (an initial step search, plain NUTS leaves in the initial phase, a skipped or
  floored crash statistic, a bounded descent) did not reach 1.10x without losing on the GP models.
- **WP64**, current defaults on this host, from the committed cells before this freeze. Median
  over the 17 house models:
  - oWALNUTS − CmdStan warmup share **0.024**, ranging from −0.157 (`eight_schools_centered`) to
    +0.066 (`sblrc`);
  - oWALNUTS − nutpie 0.011.

  At v7's defaults the spend gap to CmdStan on the house set is therefore small.

## The three schedules (read from `src/` at the frozen commit, and from the competitors)

| | oWALNUTS default (`walnutpie::warmup_schedule`, `WarmupConfig`) | CmdStan 2.39.0 | nutpie 0.16.8 |
|---|---|---|---|
| windows | 75 / 25, 50, 100, 200, 500 / 50: initial buffer 75, base window 25 doubling, last window extended, terminal buffer 50 | the same: `init_buffer` 75, `window` 25, `term_buffer` 50 | no Stan windows. The diagonal is updated from two overlapping estimators that swap every 10 draws early (`early_window_switch_freq`) and every 80 later (`mass_matrix_switch_freq`), with a final step-size-only stretch. The early and final fractions are not readable from the 0.16.8 settings object, so this study records where the stored mass matrix stops changing. |
| metric | Welford variance per slow window, Stan's regularisation `(n/(n+5)) var + 1e-3 (5/(n+5))`, installed at the window's close | the same estimator and regularisation | `sqrt(var(x)/var(grad))` (`use_grad_based_mass_matrix`) |
| step adaptation | dual averaging, `gamma` 0.05, `t0` 10, `kappa` 0.75, target 0.8 on the current coarse-endpoint acceptance; start `h0` 0.5 with `mu = ln(10 h0)`, **no initial step search** | the same constants on the mean tree acceptance; `init_stepsize` from `eps` 1 at the start | dual averaging, target 0.8, `initial_step` 0.1, `step_size_jitter` 0.1 |
| at each metric update | restart dual averaging from the current step with **`mu = ln(h)`**, **no step search** | `init_stepsize` again, then restart with `mu = ln(10 eps)` | — |
| end of warmup | `exp(log_step_bar)`, fixed thereafter | the same | — |
| default length | 1,000 | 1,000 | **400** (`num_tune`); 1,000 here (v7) |

The spend levers this suggests:

- the initial fast phase, which WP40 found at 2.07x CmdStan's cost per transition;
- the length of the slow windows, where the last window (500 transitions) is half the warmup;
- the total warmup length (nutpie's default is 400).

The restart reference and the step search were measured in WP40 and `adaptation_parity_v1` and
are not candidates here.

## Environment (disclosed)

- **Lane:** lane 2 of the shared c7a.4xlarge box (cores 4-7, `taskset -c 4-7` on every
  process), with three other lanes active. **Walls are pinned, co-tenanted and not used.**
  Gradients, ESS and gates do not depend on co-tenancy.
- **oWALNUTS:** BridgeStan 2.9.0 (no `STAN_THREADS`) with `ReplicatedStanTarget`, four replicas.
  This is the dispatch WP65 qualified.
- **CmdStan:** 2.39.0 at cmdstanpy defaults.
- **nutpie:** 0.16.8 with v7's call plus `store_mass_matrix=True` (a stored statistic, not a
  sampling setting), on a `STAN_THREADS` library built in the lane by the make call
  `bridgestan.compile_model` makes.
- **Library:** `ed573c67`, which is local main `705c0b53` plus one library commit. That commit
  adds the research-only, default-off `WarmupConfig::with_stable_metric_stop` (candidate C3)
  and its tests.

## Design

- **Seeds:** fresh, grep-verified unused. 730731–730733 for posteriordb, 730801–730810 for the
  funnel. Every run is 4 chains x 1,000/1,000.
- **Phase T:** `cargo test --release --test kernel_fingerprint` and `--test
  stable_metric_stop` in the lane clone at the frozen commit (rule clause R4).
- **Phase A (descriptive):** for each of the 17 house models, oWALNUTS defaults, CmdStan and
  nutpie x 3 seeds.
- **Phase B (candidates):** for each candidate, the 17 models x 3 seeds.
- **Phase F (funnel sanity):** 10 seeds x {default, C1, C2, C3}, 4 x 2,000/20,000, with WP66's
  funnel binary.

Every (model, arm, seed) runs in its own child process, strictly sequentially.

## Descriptive measures and predictions

Recorded per cell:

- **Warmup share:** 1 − sampling gradients / total gradients. oWALNUTS's total includes the
  best-of-16 start search; the share without it is reported too.
- **Gradients per transition by phase:**
  - oWALNUTS by each chain's own schedule;
  - CmdStan by Stan's identical schedule;
  - all three arms in fixed bins [0, 75, 100, 150, 250, 450, 950, 1000);
  - nutpie also in its own two phases, split at the last change of the stored mass matrix.
- **Sampling gradients per transition**, and the adapted step trace.

| id | prediction |
|---|---|
| P1 | the median over the 17 models of (oWALNUTS − CmdStan seed-median warmup share) is in [0.00, 0.05] (WP64: 0.024) |
| P2 | on the house models WP58 measured (eight_schools_noncentered, gp_pois_regr, lotka_volterra), oWALNUTS's share exceeds CmdStan's by a margin in [0.00, 0.05] on each. oWALNUTS − nutpie on the three is reported (WP58: within 0.02). WP58's large warmup component sits on PyMC models outside the house set. |
| P3 | the median over models of the oWALNUTS / CmdStan gradients per transition in the initial fast phase is >= 1.5 (WP40: 2.07) |
| P4 | the median over models and the five slow windows of that ratio is in [1.0, 1.3] (WP40: 1.14–1.27) |

## Candidates (research flags only, no default flip)

| id | arm | setting | follows from | prediction |
|---|---|---|---|---|
| C1 | `owalnuts-init25` | `with_windows(WarmupWindowConfig::new(25, 25, 50))`: initial fast phase 25 instead of 75, so the first metric arrives 50 transitions sooner (25 / 25, 50, 100, 200, 550 / 50) | WP40's 2.07x initial phase | R2 fails (geomean 0.97–1.05); R1, R3 and R4 hold |
| C2 | `owalnuts-half` | half the warmup with the same window rule (500: 75 / 25, 50, 100, 200 / 50). The last metric window closes at 450 instead of 950. | the 500-transition last window; nutpie's 400 default | R2 holds (1.15–1.35; total gradients about 0.75x) and R1 fails (at least one gate lost among accel_gp, gp_pois_regr, one_comp and hmm_drive_0); R3 and R4 hold |
| C3 | `owalnuts-stablestop` | the new `StableMetricStop::new(3, 0.9, ln 1.5, ln 1.5)`, a warmup budget that ends adaptation once the metric and step have stabilised. At the close of window 3 (transition 449), if 90 % of the coordinates' variances are within a factor 1.5 of window 2's, and the averaged step of window 3's stream is within a factor 1.5 of window 2's, the remaining slow window is dropped and warmup ends after the 50-transition terminal buffer (500). Otherwise the default schedule runs. On the funnel, window 4 (849, ending at 900) is checked too. | C2's cost saving, but only where adaptation has converged | stops early on a minority of chains; R2 fails (1.00–1.10); R1, R3 (no funnel chain stops) and R4 hold |

**Overall prediction:** no candidate qualifies, and the spend gap to CmdStan is small at the
current defaults.

C1 and C2 use existing public configuration (`WarmupConfig::with_windows`, the warmup length).
C3 is new library code, off by default. A C3 chain that stops at window 3 runs exactly the
transitions of the C2 run and is bit-identical to it; `tests/stable_metric_stop.rs` pins that,
and also pins that a never-firing rule and the `Custom` house warmup are bit-identical to
`Adaptation::default()`. The arms are defined once in `src/lib.rs` and shared by the harness and
the funnel binary.

## Frozen rule

A candidate qualifies as a research flag only if all four hold:

- **R1:** its gate passes over the 51 cells are >= the default's on the same seeds (v7 gates:
  rank R-hat <= 1.01, bulk and tail ESS >= 400, no retained divergence, finite draws, no
  error).
- **R2:** the geometric mean over the 17 models of (candidate / default seed-median min bulk
  ESS per total gradient, warmup included) is >= 1.10. It is taken over the models whose three
  seeds are ok on both arms, and any excluded models are listed.
- **R3:** funnel sanity. Over 10 seeds x 4 x 2,000/20,000, |mean over seeds of P(omega < -5) −
  0.0478| <= the between-seed s.e. (sd/√10), and every seed produces a cell. At 10 seeds this
  clause fails an unbiased sampler about 32 % of the time; that is the rule as assigned.
- **R4:** `cargo test --release --test kernel_fingerprint` passes in the lane clone at the frozen
  commit, with every research flag off.

An errored candidate cell fails its gates. Passing cells with max |z| > 4 are reported, not
gated. No default and no existing behaviour changes.

## Changes to the copied code

**`src/main.rs`** is the WP70 harness (itself WP65 / v7). Changes:

- the arms come from `src/lib.rs`;
- each chain is split at its own warmup length;
- warmup per-transition target evaluations, steps, depths and stops are recorded, along with
  the schedule, the work per warmup phase, the metric updates and the stable-metric checks;
- the WP70 retained arrays are reduced;
- the schema string.

**`src/bin/funnel.rs`** is WP66's funnel binary. Changes:

- the arms come from `src/lib.rs`, with the nominal warmup;
- each chain records its warmup length, its warmup and retained target calls, and its
  stable-metric checks.

**`run_spend.py`** is WP70's `run_gap.py`. The posteriordb, metric and gate code is verbatim, and
`run_nutpie` / `nutpie_model` are v7's (WP64's). Changes:

- the phases T, A, B and F;
- one child process per (model, arm, seed), where v7 used one per (model, arm), so that a crash
  loses one seed;
- the warmup-spend bookkeeping for all three samplers;
- nutpie's `store_mass_matrix=True`;
- the analysis of P1–P4 and R1–R4;
- the smoke overrides renamed `WP73_SMOKE_*`.

**`build_models.py`** is WP70's, for the 17 models, plus a `STAN_THREADS` tree for nutpie.

## Pre-freeze smoke run (disclosed)

The binaries and the driver were smoke-tested on the box in every arm, on a **non-study**
posterior (`kidiq-kidscore_momiq`) at seed 1, and on the funnel at seed 1 with 2,000/2,000.
Output went to `~/lanes/warmup_spend_v1/smoke/`, never to `artifacts/`. No code changed after
the smoke run. What it showed (non-evidence):

- all six arms and the four funnel arms ran;
- `stablestop` stopped 2 of 4 chains at transition 449 (warmup 500);
- `half` used 500 transitions per chain;
- on the funnel, `stablestop` was identical to `default`, because no chain was stable;
- nutpie exposes `n_steps`, `step_size` and `mass_matrix_inv` per warmup draw, and the stored
  mass matrix last changed at draw 849 of 1,000 on every chain.

## Rules

PREREGISTRATION.md and protocol.json are committed before the first cell.

- **Infrastructure:** builds, lane setup and the smoke run.
- **Execution:** phases T, A, B, F in order, one process at a time.
- **Reporting:** every cell is reported; failures and timeouts are results; no reruns and no
  tuning after seeing results.
- **Interruptions:** a cell with no artifact may be rerun once with the same seed, recorded as a
  deviation.
- **Amendments:** only for cells not yet run, committed before them.
