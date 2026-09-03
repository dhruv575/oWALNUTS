# Joint default study — preregistration

Frozen before execution on 2026-09-03 (see `protocol.json`; its SHA-256 is
recorded in `artifacts/summary.json` and `CHECKSUMS.sha256`). Nothing in
this file or in `protocol.json` is edited after the first evidence cell
starts; deviations are appended under "Deviations" with a timestamp.

## Question

Three studies point at one change made of two parts:

* `STUDIES/kernel_gap_v1` (WP30): under CmdStan's matched step, metric and
  starts the default kernel is 0.77x reference NUTS's minimum bulk ESS per
  gradient on six healthy posteriors, entirely from leaves per orbit under
  the endpoint U-turn statistic (0.60x the reference's leaves, 41–69 % of
  orbits ended by the recursive endpoint check); `UTurnRule::MomentumSum`
  restores 0.90x, and the funnel tail mass is preserved under it at both
  tunings.
* `STUDIES/step_collapse_v1` (WP27): the default step collapse on `sblrc`
  and `earnings` is the unit-variance floor of
  `DiagonalMetricRegularization::TowardUnit`; `DiagonalMetricRegularization::Stan`
  removes it (`sblrc` 9.7x) but `earnings` loses its gate (R-hat 1.02): at
  the corrected metric the WALNUTS orbit is a third of NUTS's (49 vs 163
  leaves), which is the WP30 mechanism — the orbits shorten exactly when
  the metric is right.
* `STUDIES/uturn_default_v1` (WP26): `MomentumSum` alone, under the floored
  metric, is a wash (1.064x geomean, 0.78x worst model) and was not made
  the default.

**Should the `sampler` defaults become `UTurnRule::MomentumSum` and
`DiagonalMetricRegularization::Stan` together?** Measured on the
`posteriordb_bench_v3` protocol with fresh seeds, plus the funnel and Eight
Schools side checks of `uturn_default_v1`. The `wt/posteriordb-v4` run on
the same machine tests the regularisation alone against CmdStan and nutpie
and is not touched.

## Design

Four oWALNUTS arms, everything but the two options at the `sampler`
defaults at freeze (`Tuning::default()`: `h0 = 0.5`, depth 10, eight
refinement levels, `delta = 1`; `Adaptation::default()`: dual averaging
0.8 with the WP24 warmup exhaustion rule; adapted diagonal metric; cached
initial evaluation; `Init::uniform()` starts shared across arms per seed;
`Limits::admit_worst_case()`):

| arm | U-turn rule | diagonal-metric regularisation |
|---|---|---|
| `da` | `Endpoints` (default) | `TowardUnit` (default) |
| `rhosum` | `MomentumSum` | `TowardUnit` |
| `stanreg` | `Endpoints` | `Stan` |
| `joint` | `MomentumSum` | `Stan` |

The regularisation enters through
`Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(..))`,
which is exactly the `WarmupConfig` that `Adaptation::default()` builds
(`sampler.rs`, `Adaptation::warmup_config`) with one field changed; the
`TowardUnit` arms use `Adaptation::default()` itself.

Three evidence tracks:

1. **posteriordb** — the v3 protocol (17 posteriors at commit `28f8d3d`,
   4 chains, 1,000/1,000, `ReplicatedStanTarget` on a non-`STAN_THREADS`
   BridgeStan 2.9.0 build compiled fresh here, ArviZ 0.23.4 estimators, the
   v3 gates), the four arms, 17 x 4 x 3 = 204 cells. CmdStan and nutpie
   are not rerun; their v3 seed medians are cited. The decision statistic
   is the seed median of the minimum over reference parameters of bulk ESS
   per target call (start search + warmup + sampling), candidate over `da`,
   geometric mean over models.
2. **Funnel tail mass** — Neal's 10-D funnel, `P(omega < -5)` (exact
   0.0478), 4 x 2,000/20,000 from `omega in {-3, -1, 1, 3}`, under the
   paper tuning (`examples/funnel_kernel_options.rs`: Appendix C warmup,
   identity metric, `h = 0.1`, eight levels — the regularisation is inert
   there, so `stanreg` = `da` and `joint` = `rhosum` by construction) and
   the sampler defaults (`Tuning::default()` with eight levels since WP28,
   adapted diagonal, dual averaging 0.8), each arm, three seeds. The
   per-seed statistic is `z = (estimate − exact) / MCSE` of the indicator
   (`diagnostics::mcse_mean`, the `funnel_defaults_v1` statistic that set
   the current default); the WP26 batch-means z per seed and pooled over
   seeds are reported alongside (`kernel_gap_v1` found the batch-means
   s.e. underestimated).
3. **Eight Schools strict track** — `eight_schools_v9_rebench_v1` settings
   verbatim (`h = 0.3`, depth 8, eight levels, `delta = 1`, acceptance
   0.95, `WarmupConfig::new(0.95).with_mass_adaptation(true)` plus the
   arm's regularisation, 4 x 1,000/1,000, threads 1, `walnutpie` facade so
   no initial-evaluation cache, three timing repetitions with bit-identical
   draws), each arm, three seeds; statistic = min over the six v38
   functionals of bulk ESS per callback, geometric mean over seeds.

Seeds 86101, 86102, 86103 for every track (`grep -w` of `wiki/`, every
study's `README.md`, `protocol.json`, `PREREGISTRATION.md`, drivers and
`src/`, and `src/`, `tests/`, `examples/` before freezing: no occurrence as
a seed; the 85101–85103 suggested in the task were consumed by
`STUDIES/funnel_bias_fix_v1` and were not used).

## Preregistered decision rule

Flip the sampler defaults to `MomentumSum` + `Stan` together **if and only
if all five hold for the `joint` arm**:

* **C1** geometric mean over the 17 models of the seed-median
  min-bulk-ESS/gradient ratio `joint / da` >= 1.15;
* **C2** no model has that ratio below 0.85;
* **C3** cells passing all gates: `joint` >= `da` (of 51);
* **C4** funnel tail-mass |z| <= 2 on every seed for `joint` under both
  the paper tuning and the sampler defaults;
* **C5** Eight Schools strict-track geomean min-bulk-ESS/call ratio
  `joint / da` >= 0.9.

Otherwise the defaults stay and the README says why. The `rhosum` and
`stanreg` arms attribute the joint effect and are reported, not decided;
walls and ESS/s are shared-machine upper bounds; the v3 reproduction of
`da` is reported.

Predictions (not gated):

* **P1** `joint` >= 1.2x `da` on each of the healthy regressions
  `earnings`, `kidiq`, `sblrc`, `mesquite`, `nes2000` (WP30: 0.77x -> 0.90x
  at the matched metric on four of them; WP27: the metric fix on the other
  two);
* **P2** the `earnings` gate is recovered: `joint` passes at least as many
  `earnings` seeds as `da` and more than `stanreg` alone (WP27's `reg` was
  0/2 at R-hat 1.02; WP30 lengthens the `earnings` orbit 40 -> 151 leaves
  at that metric);
* **P3** `sblrc` `joint / da` >= 5x (WP27: 9.7x on two seeds).

If the decision passes, the flip is a separate labelled final commit that
changes the sampler defaults only (`KernelOptions` inside
`Tuning::default()` and the regularisation inside
`Adaptation::warmup_config`; `walnutpie::KernelOptions::default()`,
`WarmupConfig::default()`, `RunConfig` and `tests/kernel_fingerprint.rs`
are untouched) and updates `tests/sampler_api.rs`, the README defaults
table, the CHANGELOG 0.2.0 Changed section and `wiki/release-0.2.0.md`.

## Reporting

`artifacts/summary.json`, `artifacts/results-table.md`, `README.md`
(verdict), `LEDGER-ENTRY.md` (WP31-JOINT-DEFAULT-V1), `CHECKSUMS.sha256`
(raw draws hashed, not committed). Failures are results; no cell is rerun;
nothing is tuned after seeing results. A driver crash is relaunched and the
interrupted cell re-run from scratch (seeded), logged below.

Before freezing, the harness was smoke-tested on the noncentered eight
schools with seed 1 (not a study seed; output deleted) through the cell
binary for all four arms, to confirm the arms differ only in the recorded
`u_turn` / `metric_regularization` and that the binaries run; the funnel
binary was run once per tuning and the Eight Schools binary once to
scratch paths (deleted).

## Load caveat

Shared 16-thread machine (Intel Core Ultra 7 255H, Windows 11); the
`wt/posteriordb-v4` run (CmdStan, nutpie and oWALNUTS cells) is active
during execution. Walls are upper bounds; ESS per gradient is the
machine-independent primary figure.

## Deviations

(none at freeze)
