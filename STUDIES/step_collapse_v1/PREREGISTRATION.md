# step_collapse_v1 — preregistration of the remedy table

Written after the diagnosis (README section 1, developed on the
`posteriordb_bench_v3` seeds 79101–79103 of `sblrc`, `earnings` and
`arma11`) and before any cell of the table below was run. The diagnosis
runs (`artifacts/telemetry/`, `artifacts/sweep-sblrc/`, `artifacts/sweep-arma/`,
`artifacts/cmdstan/`) are exploratory and not part of the table.

## Cells

Models (BridgeStan 2.9.0 builds of the posteriordb `28f8d3d` programs, no
`STAN_THREADS`): `sblrc-blr`, `earnings-logearn_interaction`,
`diamonds-diamonds` (the three models whose default step collapsed in v1/v3),
`arma-arma11` (the post-escape crawl model), `kidiq-kidscore_momhsiq`,
`mesquite-logmesquite_logvash`, `nes2000-nes` (controls). Seeds **80101,
80102** (unused by any earlier study). Every cell: `Sampler` defaults
(`h0 0.5`, depth 10, four levels, `delta 1`, adapted diagonal metric from the
identity, dual averaging at 0.8, the WP24 warmup exhaustion rule), 4 chains x
1,000 warmup + 1,000 retained, `Init::uniform()` starts (the same for every
arm of a seed), plus the arm's options through `Adaptation::Custom`. Driver:
`src/main.rs`; CmdStan 2.39.0 defaults from the same constrained starts and
seed: `cmdstan_trace.py`.

Metrics: minimum over unconstrained coordinates of the rank-normalised bulk
ESS (`owalnuts::diagnostics`; CmdStan: ArviZ bulk ESS over its constrained
parameters — rank-based, so invariant under the monotone constraining
transforms) per gradient (warmup + sampling), max rank R-hat, min tail ESS,
sampling divergences, per-chain final `h`, per-chain retained depth-cap rate.
Gates as in v3 (R-hat <= 1.01, bulk and tail ESS >= 400, zero sampling
divergences). Seed median of the two seeds is the per-model number; "beyond
seed noise" means outside the spread of the arm's own two seeds.

## Arms

| arm | what | status |
|---|---|---|
| `baseline` | `Adaptation::default()` (the v3 `owalnuts-da` cell) | existing |
| **`reg`** | `DiagonalMetricRegularization::Stan`: `(n/(n+5)) var + 1e-3 (5/(n+5))` instead of the `TowardUnit` `+ 5/(n+5)` | existing option, the diagnosis's candidate |
| `reg+ramp` | `reg` with `delta = 1000` in the initial fast phase | existing |
| `reg+research` | `reg` with Stan's `init_stepsize` before warmup and after every metric update | existing |
| `mean-accept` | dual averaging on Stan's `accept_stat__` (`MeanTrajectoryAcceptance`) with the WP24 rule | existing |
| `ramp` | `delta = 1000` in the initial phase only | existing |
| `research` | Stan's `init_stepsize` at the start and at every window boundary | existing |
| `research+floor-rel:0.5` | the re-search plus a floor of half the latest search result on the adapted step (`WarmupConfig::with_step_floor_relative_to_search`, new) | new, opt-in |
| `shrink:10` | the adapted step never falls below a tenth of the step its dual-averaging stream started from (`WarmupConfig::with_max_window_shrink`, new) | new, opt-in; expected negative control on `arma11` |
| `stan-style` | `WarmupConfig::stan_style(0.8)` with the WP24 rule (the v3 `owalnuts-stan-style` arm was two-sided) | existing |
| `cmdstan` | CmdStan 2.39.0 defaults from the same starts | reference |

Not run, with the reason:

* *Restart every chain from the best chain at the last slow window.* The
  diagnosis (README 1b) shows the `arma11` 79103 chain 3 crawl is a start
  that CmdStan itself cannot leave in 1,000 iterations from the same point
  (final `h` 1.7e-6, 832 depth-cap draws, R-hat 1.6 — the same numbers as
  oWALNUTS to within a factor 30 in `h`); the only remedy for it is a
  cross-chain intervention that changes the independent-chains contract of
  `Sampler::run`, which is outside a warmup-rule study. Recorded as a
  follow-up.
* *A delta ramp for (b).* Measured in the diagnosis sweep: bit-identical
  `arma11` chain 3 (the energies on the wall exceed 1,000 either way).

## Predictions

* **P1 (mechanism).** `reg` raises the seed-median min bulk ESS per gradient
  of `sblrc` and `earnings` by >= 3x over `baseline` and of `diamonds` by
  >= 1.0x, and its final steps on those models are within 0.5–2x CmdStan's
  from the same starts. `mean-accept`, `ramp`, `research` and
  `research+floor-rel:0.5` leave the final `h` of `sblrc` and `earnings`
  within 2x of `baseline` (they do not touch the metric).
* **P2 (controls).** No control model (`kidiq`, `mesquite`, `nes2000`) is
  below 0.9x `baseline` under `reg` beyond seed noise.
* **P3 (parity).** `reg` reaches >= 0.5x CmdStan per gradient on `sblrc`
  and `earnings`; `reg+research` and `stan-style` are within 0.7–1.4x of
  `reg` on every model (the metric, not the step rules, is the difference).
* **P4 (negative control).** `shrink:10` freezes at least one `arma11`
  chain on at least one seed (a floored step cannot slide out of the wall).
* **P5 (arma11).** `reg` has no frozen chain on `arma11` (the slide rule is
  untouched); a seed passes under `reg` whenever it passes under
  `baseline`.

## Default-flip rule

`DiagonalMetricRegularization::Stan` becomes the diagonal-metric default of
`Adaptation::DualAveraging` and `Adaptation::Paper` (the `sampler`
facade only; `walnutpie::WarmupConfig::default()` and the kernel revision are
unchanged so `tests/kernel_fingerprint.rs` is untouched) if P1's `reg` clause
holds on all three collapsing models, P2 holds, and P5 holds. If a control
loses more than 10 % beyond seed noise the option stays opt-in and the README
recommends it for regressions.
