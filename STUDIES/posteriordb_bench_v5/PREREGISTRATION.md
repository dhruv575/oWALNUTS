# posteriordb benchmark v5 — preregistration (WP32)

Frozen 2026-09-03 before the first evidence cell; the protocol is
`protocol.json` (hashed in `CHECKSUMS.sha256` after the run). This study
validates a **post-hoc default change**, it does not decide it.

## What is being validated

The commit "DEFAULT CHANGE (post-hoc after WP31)" (the parent of the commit
that freezes this file) changed two `owalnuts::sampler` defaults:

| default | before | after |
|---|---|---|
| `Tuning::default()` U-turn rule (`KernelOptions::u_turn`) | `UTurnRule::Endpoints` (frozen `v10`) | `UTurnRule::MomentumSum` (`sampler::DEFAULT_U_TURN_RULE`) |
| diagonal-metric regularisation in `Adaptation::DualAveraging` / `Adaptation::Paper` | `DiagonalMetricRegularization::TowardUnit` (frozen `v10`) | `DiagonalMetricRegularization::Stan` (`sampler::DEFAULT_METRIC_REGULARIZATION`) |

`walnutpie::KernelOptions::default()`, `walnutpie::WarmupConfig::default()`,
`RunConfig`, `ALGORITHM_REVISION` and the kernel fingerprints are unchanged.

## Why post hoc

`STUDIES/joint_default_v1` (WP31, seeds 86101–86103) preregistered a flip
rule with five criteria for exactly this pair and met four: 1.508x geomean
min-bulk-ESS/gradient over the 17 posteriordb models, 41 vs 35 cells,
funnel |z| <= 2 on every seed at both tunings with zero divergences at the
defaults, Eight Schools 1.29x. It failed C2 ("no model below 0.85x") on
`hmm_drive_0` (0.005; the arm-dependent second-mode draw) and the centered
eight schools (0.79; 0/3 in every arm), so the study did not flip, as its
rule required. The coordinator then decided the flip on that evidence,
outside any preregistered rule. This run is the fresh-seed check against
CmdStan and nutpie that the decision was made without.

## Protocol

`STUDIES/posteriordb_bench_v3` verbatim: 17 posteriordb posteriors (commit
`28f8d3d`), 4 chains, 1,000 warmup / 1,000 retained, gates rank R-hat <=
1.01, bulk and tail ESS >= 400 on every reference parameter, zero sampling
divergences, ArviZ 0.23.4 estimators, `Init::uniform()` starts, cell
timeout 2,700 s, strictly sequential run order (models in protocol order;
arms `owalnuts-da`, `cmdstan`, `nutpie`; seeds ascending). Arms:

* `owalnuts-da`: the shipped defaults after the change — `Tuning::default()`
  (`h0 0.5`, depth 10, eight levels, `delta 1`, `MomentumSum`),
  `Metric::diagonal()`, `Adaptation::default()` (dual averaging 0.8, WP24
  warmup exhaustion rule, Stan regularisation), cached initial evaluation,
  `Limits::admit_worst_case()`, four threads, `ReplicatedStanTarget` on a
  non-`STAN_THREADS` BridgeStan 2.9.0 build. Nothing is overridden.
* `cmdstan` 2.39.0 defaults through cmdstanpy 1.3.0; `nutpie` 0.16.8
  defaults. Both rerun (WP31 cited the v3 medians instead).

Plus the funnel row: Neal's 10-D funnel, 4 x 2,000 / 20,000 at the sampler
defaults, `omega` starts {-3, -1, 1, 3}, three seeds, per-seed MCSE z of
`P(omega < -5)` against 0.0478 (the `funnel_defaults_v1` statistic).

Seeds 87101–87103 for both (verified unused). Compiled models and the
posteriordb checkout are copied from the `wt/posteriordb-v4` worktree (same
toolchain and flags; not modified there); `mcycle_gp-accel_gp` is compiled
here. Machine shared; walls are upper bounds.

## Predictions (fixed before the first cell)

| | prediction | reference |
|---|---|---|
| P1 | `owalnuts-da` passes all gates on **>= 39 of 51** cells | v3 default 35; WP31 joint 41; CmdStan 37, nutpie 31 in v3 |
| P2 | geomean min-bulk-ESS/gradient vs CmdStan **>= 0.45** over all 17 models | v3 default 0.344; WP31 joint vs the cited v3 CmdStan 0.477 |
| P3 | geomean min-bulk-ESS/s vs nutpie **>= 1.5** | v3 default 1.35; WP31 joint ESS/s 1.56x the default arm |
| P4 | geomean wall per gradient **<= 1.0x** CmdStan | v3 0.751 |
| P5 | funnel tail mass at the defaults, **\|z\| <= 2 on every seed** | WP31 joint at the defaults −0.06, +0.81, −1.16 |

Reported, not gated: v5/v3 per-model and geomean ratios for every arm (the
competitors are the seed-noise control), DA models below 0.8x or above 1.2x
v3, frozen cells, cells not ok, installed-mass ranges, final steps, depth
caps, outright wins.

## Rules

Report all cells; no reruns; failures are results; nothing is tuned after
seeing results; a driver crash is relaunched and the interrupted cell re-run
from scratch (seeded), recorded as a deviation. The study does not reverse
the default change on its own — the change is a documented post-hoc
decision — but the release notes must state next to the numbers which
predictions did not hold. If P1, P2 and P4 all hold, this run is the breadth
figure the 0.2.0 release notes cite for the defaults.
