# WP57 preregistration: where the time goes in a stalled `lotka_volterra` run

Frozen before the first evidence cell. Machine-readable copy: `protocol.json`
(that file governs where the two differ).

## Background

`hudson_lynx_hare-lotka_volterra` is an 8-parameter posterior whose
likelihood solves an ODE with `integrate_ode_rk45(..., 1e-5, 1e-3, 500)`.
It is the house model that most often fails on time rather than on
diagnostics:
- WP54, at the old `Init::uniform()` default: 4 of 13 seeds over 900 s, and
  3 more finished with R-hat 1.04–1.59. One slow chain used 1.58M gradients
  with a final step of 0.0046, against about 70k gradients and a step of 0.1
  for healthy chains.
- WP48 and WP51 lost lotka cells to 2,700 s timeouts.
- WP52 found starts down to -3e4 that collapse the step. Best-of-16 starts
  gave 17.1x on this model.

Nobody has measured where the time goes in a stalled run. Errors are
all-or-nothing (`Sampler::run` returns no telemetry on timeout), so this
study streams the telemetry out during the run.

## Questions

1. At the new defaults (`f097391c`), what fraction of 12 fresh seeds stall?
   Do `chain_warnings` (WP44) or the per-window telemetry identify the stalled
   chain early?
2. In a stalled chain, where do the gradients go? By warmup window, step,
   depth caps, refinement level, and per-gradient (ODE) cost.
3. Does a cheap opt-in mitigation remove the stalls without changing retained
   draws on normal runs?

## Instrument (harness `src/main.rs`, driver `run_study.py`)

- Every cell is one fresh process running the shipped sampler:
  - `Metric::diagonal()`, `Adaptation::default()`, `Tuning::default()`
    (RejectLeaf);
  - `Limits::admit_worst_case()`;
  - 4 chains x 1,000/1,000 on 4 threads;
  - `ReplicatedStanTarget`, construct seed 1.
- Starts come from `candidate_starts` with the arm's candidate count, exactly
  as `Sampler::run_with_init` chooses them.
- The run goes through `Sampler::run_with_comparison_observers` (observe-only).
  The observer records one row per chain per transition: stage, window, step,
  depth, stop reason, target calls, leaves, refinement attempts, selected
  level, divergence, selected log density, wall time, and wall time inside
  the target.
- A thin wrapper times every target call per thread. The calls of an
  unfinished transition are also recovered at the cap.
- The cap is the cooperative `Limits::timeout(1,200 s)`, with a 1,500 s
  process backstop.
- Smoke on the non-evidence seed 5709901 (`artifacts/smoke/smoke-summary.json`):
  - the observer route, plain `Sampler::run`, and the `Custom` route with a
    no-op cap of 10 all give the same draw hash, `69a776a9b9375f91`;
  - the cap-6 arm differs, as it must.
- Model library: copied from the dense-metric sibling build of the same
  posteriordb source (hashes in `protocol.json`). Reference draws: posteriordb
  `28f8d3d`.

## Arms

| arm | change from defaults |
|---|---|
| `defaults` | none: `Init::default()` = `Init::best_of(16)` |
| `best_of_64` | `Init::best_of(64)` |
| `depth6_initial` | `WarmupConfig::with_initial_phase_max_depth(6)`: tree depth at most 6 during the initial fast phase (transitions 0–74) only. This is a new research-only opt-in (commit `89c6fdf9`, default `None`, unit-tested). |
| `uniform` | `Init::uniform()`; targeted replication block only |

**Why these two mitigations.**
- (b) `best_of(64)` tests the one mechanism already measured on this model.
  WP52 tied lotka's failures to start quality: uniform starts at -3e4 led to
  step collapse, and best-of-16 starts at -1e3 to -3e2 did not. Going from 16
  to 64 candidates asks whether the residual stalls are the tail of the same
  start lottery. It costs about 190 extra gradients per run.
- (a) The initial-phase depth cap bounds what a chain can spend per
  transition while it is far from the typical set. A depth-10 orbit with
  refinement can cost about 10^3 to 10^5 gradients per transition; at depth 6
  the bound is 16x smaller. It acts only in the first 75 transitions, so
  everything from the first slow window on uses the shipped kernel.
- (c) A tighter initial-phase `max_error` was not chosen. Tightening `delta`
  raises the cost per leaf (more refinement levels per macro step) in exactly
  the phase that is slow. The only measurement in this direction on this model
  went the other way: WP40's NUTS initial phase, which *loosens* `delta` to
  the divergence threshold, gave lotka 1.52x
  (`STUDIES/warmup_gap_diag_v1`). It also cannot be bit-identical, because
  almost every initial-phase leaf has a local error below 1.

**Bit-identity by construction.**
- `best_of_64` can be identical only on a seed where all four chosen starts
  equal the best-of-16 starts. The 64 candidates of chain 0 begin with
  best-of-16's 16, but later chains draw from a shifted stream, so in practice
  it is never identical.
- `depth6_initial` can be identical only where no initial-phase transition of
  the defaults run exceeded depth 6. On the smoke seed, healthy chains
  reached depth 7, 8, 9 and 7 in the initial phase, so I expect the cap to
  bind on every seed. The decision rule therefore states its non-identity
  bar for both arms.

## Cells (strictly sequential, in this order; none rerun)

1. A: `defaults`, fresh seeds 5701101–5701112.
2. B: `best_of_64`, the same 12 seeds.
3. C: `depth6_initial`, the same 12 seeds.
4. T: `uniform` on 5403104, 5403107, 5403110, 148101. These are **declared
   targeted replications, not fresh**: the WP54 seeds that exceeded 900 s.

40 cells in all. The seeds were grepped across the repo and every worktree's
`STUDIES` before use; none had been used. Wall times are contended: sibling
agents share the machine. Gradients and the transition-level telemetry are
the primary evidence.

## Definitions

- **Stalled cell**: the run did not finish within 1,200 s, or it finished
  with wall > 900 s.
- **Stalled chain**: in a stalled cell, a chain that had not finished its
  2,000 transitions at the cap. If the cell finished, the chain(s) with more
  than 3x the median chain's gradients.
- **Slow chain** (descriptive): the same 3x rule in any completed cell.
- **Healthy chain**: a chain of a non-stalled `defaults` cell that is not a
  slow chain.
- **Windows**: Stan's schedule for 1,000 warmup transitions:

  | window | transitions |
  |---|---|
  | init | 0–74 |
  | S1 | 75–99 |
  | S2 | 100–149 |
  | S3 | 150–249 |
  | S4 | 250–449 |
  | S5 | 450–949 |
  | term | 950–999 |
  | sampling | 1000–1999 |

  The observed stage field is checked against this schedule. The work of an
  unfinished transition counts in the window that transition belongs to.
- **Per-gradient wall**: target-call wall time per call, from the wrapper
  (contended).
- **Early identification** can happen in two ways:
  - The WP44 step rule (end-of-window step < 0.1x the median over chains) or
    its log-density rule (median log density over the window below the
    chains' median by more than 3x the median within-chain IQR) flags the
    stalled chain. Both rules are evaluated at the end of S1 or S2, on the
    chains that reached it.
  - The stalled chain has not reached the end of S2 when the other chains
    have.

  Each is reported with the wall time at which it becomes known. The real
  `Summary::chain_warnings` exists only for runs that complete, and is
  reported for those.
- **Gates**, on the 8 posteriordb reference parameters:
  - rank R-hat <= 1.01;
  - bulk ESS >= 400 and tail ESS >= 400;
  - zero retained divergences;
  - finite draws;
  - max |z| <= 4, where z = (mean - ref) / sqrt(mcse^2 + ref mcse^2).

  A cell that did not complete fails every gate.

## Predictions (written before any evidence cell)

- **P1.** At defaults, at most 2 of 12 seeds stall.
- **P2.** Stalled chains spend more than 70 % of their gradients in S1 + S2.
  In those windows, more than 50 % of transitions stop at the depth cap of 10,
  and the median step is below 1e-3.
- **P3.** The per-gradient wall of a stalled chain is more than 2x the median
  per-gradient wall of healthy chains (ODE stiffness at bad parameters).
- **P4.** One mitigation arm has 0/12 stalls. It is bit-identical to
  defaults on every non-stalled seed where identity is possible by
  construction.
- **P5.** At least 3 of the 4 targeted `uniform` cells stall again.
- **P6.** In every stalled cell, the stalled chain is identified early (as
  defined above) before 25 % of the cell's wall.

My own expectation, for the record: P1 holds, and quite possibly 0/12
stall. If so, the mitigation arms cannot show a benefit, and the
characterisation (Q2) rests on the `uniform` block.

## Decision rule (frozen)

For each mitigation arm, all three conditions must hold:

- **R1.** 0 of 12 cells stall.
- **R2.** The number of cells passing every gate is at least the `defaults`
  count.
- **R3.** On every seed where `defaults` did not stall, the retained draws
  are bit-identical to `defaults` (draw hash), where that is possible by
  construction. Where it is not (see above), max |z| <= 3 on that seed, and
  R2 still applies.

**Recommend** the arm for a default-flip confirmation if and only if R1, R2
and R3 all hold. If both arms pass, prefer the one with more bit-identical
seeds; on a tie, the one with fewer total gradients over the 12 seeds. If
`defaults` itself never stalls, R1 is trivially met. An arm may still pass,
but the README must then say that this study gives no evidence of a benefit.

**No default is flipped in this study** (the brief), whatever the outcome.
