# Adaptation parity v1 — preregistration

Frozen 2026-09-01 before the first evidence cell. The machine-readable copy
is `protocol.json`; where they disagree, `protocol.json` wins.

## Question

The posteriordb benchmark v1 (`STUDIES/posteriordb_bench_v1`) put the
`owalnuts-da` arm at a geometric-mean 0.32x CmdStan's minimum bulk ESS per
gradient over 14 models with zero wins. Reading the warmup code against
Stan's shows four differences in the adaptation and one in the tree cap:

1. **Acceptance statistic.** Dual averaging drives
   `DualAveragingAcceptance::CurrentCoarseEndpoint`, the leaf-wise
   `exp(-|H_end - H_start|)` of the coarsest attempt. Stan drives
   `accept_stat__`, the mean over the attempted leaves of
   `min(1, exp(H_0 - H_leaf))` against the trajectory's initial energy.
2. **Initial step.** No initial-step heuristic runs by default; `h_0` is used
   as given. Stan runs `init_stepsize` (double/halve one leapfrog until the
   acceptance crosses the target) at the start and after every metric update.
3. **Metric regularisation.** The diagonal estimate is
   `(n/(n+5)) var + 5/(n+5)` (shrunk toward unit variance). Stan uses
   `(n/(n+5)) var + 1e-3 (5/(n+5))`.
4. **Restart reference.** After a metric update dual averaging restarts with
   `mu = ln(h)`; Stan restarts with `mu = ln(10 h)`.
5. **Depth.** Package default depth 8; Stan's is 10.

Already identical: the window schedule (75 / 25, 50, 100, ... / 50 with the
15 % / 75 % / 10 % short-warmup fallback), the dual-averaging constants
(`gamma = 0.05`, `t_0 = 10`, `kappa = 0.75`, `mu = ln(10 h_0)` at the start).

## Design

* Models (9, all with reference draws and compiled BridgeStan libraries from
  v1): `eight_schools_noncentered`, `mesquite`, `kidiq`, `nes2000`,
  `sblrc-blr`, `diamonds`, `earnings`, `arK`, `garch11`.
* Configurations (9): `base` (the v1 `owalnuts-da` arm), each change alone
  (`traj`, `init`, `reg`, `mu10`, `depth10`), the four warmup changes together
  at depth 8 (`warmup4`), all five (`all`), and `all+h1` (the heuristic seeded
  from `h_0 = 1`, Stan's default, instead of 0.1).
* 4 chains, 1,000 warmup, 1,000 retained, seeds 81101 and 81102 (unused in
  any earlier study), 4 threads, uniform(-2, 2) starts as in v1.
* Metrics via the v1 driver (ArviZ on BridgeStan-constrained draws over the
  posteriordb reference columns): minimum bulk and tail ESS, rank R-hat, min
  bulk ESS per gradient (gradients over warmup + sampling), depth-cap rate,
  final step, divergences, agreement z. `owalnuts::diagnostics` on the
  unconstrained draws recorded as a secondary check. The CmdStan reference
  is the v1 seed-median (seeds 77101–77103), not re-run.
* Refinement-level histograms of the selected level over retained and warmup
  transitions, per cell.

## Decision rule

Choose the configuration with the highest geometric mean over the nine models
of `config / base` min-bulk-ESS-per-gradient (seed medians) subject to no
model below 0.9x base. That configuration becomes the `sampler::Sampler`
default. If no configuration satisfies the constraint, report the best
geomean and name the violations; the default flips only if every violation
is on a model where `base` fails the gates. `walnutpie::RunConfig` and
`WarmupConfig::default()` stay frozen as the v10 legacy either way.

## Predictions

* P1: `reg` alone recovers `diamonds` and `earnings` (final step > 0.01,
  depth-cap rate < 0.5).
* P2: `traj` alone changes the adapted step on every model but is not
  sufficient on `diamonds`/`earnings`.
* P3: `all` reaches >= 0.6x CmdStan geomean ESS per gradient on the nine.
* P4: a refinement level above zero is selected on < 5 % of retained
  transitions in every configuration.

## Rules

All cells are reported; failures are results; no reruns, no tuning after
seeing results. Any deviation is appended below.

## Deviations

(none yet)
