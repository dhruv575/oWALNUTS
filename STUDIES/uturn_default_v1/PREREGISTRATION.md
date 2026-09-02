# U-turn-rule default study — preregistration

Frozen before execution on 2026-09-02 (see `protocol.json`; its SHA-256 is
recorded in `artifacts/summary.json` and `CHECKSUMS.sha256`). Nothing in
this file or in `protocol.json` is edited after the first evidence cell
starts; deviations are appended under "Deviations" with a timestamp.

## Question

`STUDIES/kernel_efficiency_v1` traced most of the per-gradient gap between
oWALNUTS-as-NUTS and reference NUTS on isotropic targets to the endpoint
U-turn statistic (`rho_end . M^-1 (q_end - q_start)` at the two extremes of
the merged span), which builds orbits 3–4 leaves longer than Stan's
momentum-sum criterion for no ESS gain: `UTurnRule::MomentumSum` took the
100-D Gaussian from 0.81x to 1.09x reference NUTS, was within seed noise on a
50-D correlated Gaussian (1.07x) and on Eight Schools (0.86x vs 0.91x, inside
the ±10 % seed spread), and preserved the funnel tail mass at the paper
tuning on one seed. It is opt-in
(`Tuning::new().kernel_options(KernelOptions { u_turn: UTurnRule::MomentumSum, .. })`).
**Should it be the `sampler` default for 0.2.0?** — measured on the
posteriordb breadth protocol where the current default sits at 0.344x
CmdStan's minimum bulk ESS per gradient (`STUDIES/posteriordb_bench_v3`).

## Design

Three evidence tracks, all with the U-turn rule as the only difference
between arms:

1. **posteriordb** — the v3 protocol (17 posteriors at commit `28f8d3d`,
   4 chains, 1,000/1,000, `Tuning::default()`, `Metric::diagonal()`,
   `Adaptation::default()` with the WP24 warmup rule, `Init::uniform()`
   starts shared across arms per seed, `Limits::admit_worst_case()`,
   `ReplicatedStanTarget` on a non-`STAN_THREADS` BridgeStan 2.9.0 build,
   ArviZ 0.23.4 estimators, the v3 gates) restricted to oWALNUTS arms:
   `owalnuts-da` (`UTurnRule::Endpoints`, the current default),
   `owalnuts-da-rhosum` (`MomentumSum`), `owalnuts-da-cross`
   (`EndpointsWithCross`, reported only). CmdStan and nutpie are not rerun;
   the v3 CmdStan seed medians are cited as the reference. 17 x 3 x 3 = 153
   cells. Every model is compiled fresh with the v3 toolchain and flags.
2. **Funnel tail mass** — Neal's 10-D funnel, `P(omega < -5)` (exact
   0.0478), 4 x 2,000/20,000 from `omega in {-3, -1, 1, 3}`, under both the
   paper tuning (`examples/funnel_kernel_options.rs`: Appendix C warmup,
   identity metric, `h = 0.1`, eight levels) and the sampler defaults
   (`freeze_mode_v1`'s `checks funnel` protocol), each rule, three seeds;
   the statistic is the seed-pooled estimate with a batch-means s.e. over
   480 batches of 500 (`src/bin/funnel.rs`). `freeze_mode_v1` measured the
   endpoint rule at the defaults at z = −1.70 (one seed, s.e. 0.014), so
   the endpoint control is run alongside and reported.
3. **Eight Schools strict track** — `eight_schools_v9_rebench_v1` settings
   verbatim (`h = 0.3`, depth 8, eight levels, `delta = 1`, acceptance 0.95,
   4 x 1,000/1,000, threads 1, `walnutpie` facade so no initial-evaluation
   cache, three timing repetitions with bit-identical draws), each rule,
   three seeds; statistic = min over the six v38 functionals of bulk
   ESS per callback, geometric mean over seeds (`src/bin/eight_schools.rs`).

Seeds 80101, 80102, 80103 for every track (grep of `wiki/`, `STUDIES/`,
`src/`, `tests/`, `examples/` before freezing: no occurrence as a seed).

## Preregistered decision rule

Flip `sampler::Tuning::default()` to `UTurnRule::MomentumSum` **if and only
if all four hold**:

* **C1** geometric mean over the 17 models of the seed-median
  min-bulk-ESS/gradient ratio `owalnuts-da-rhosum / owalnuts-da` >= 1.10;
* **C2** no model has that ratio below 0.85;
* **C3** the pooled funnel tail-mass z for `MomentumSum` is within ±2 of
  0.0478 under both the paper tuning and the sampler defaults;
* **C4** Eight Schools strict-track geomean min-bulk-ESS/call ratio
  `rhosum / endpoints` >= 0.9.

Otherwise the default stays `Endpoints` and the README says why. The cross
arm, gate counts, walls and the v3 reproduction (`owalnuts-da` here versus
v3's `owalnuts-da`) are reported, not gated. Expectations (not gated): the
largest gains on the models the adapted diagonal metric makes nearly
isotropic (arK, garch11, mesquite, hmm_example, kidiq, nes); gradient counts
down 5–25 % there and within ±5 % on the depth-capped models
(earnings, sblrc, accel_gp); `hmm_drive_0`'s second mode and `sblrc`'s step
collapse recur in every arm on some seeds and enter the geomean as they
fall; `owalnuts-da` reproduces v3 within seed noise (0.8–1.25x on the
healthy models).

If the decision passes, the flip is a separate labelled final commit that
changes `Tuning::default()` only (`walnutpie::KernelOptions::default()`,
`RunConfig` and `tests/kernel_fingerprint.rs` are untouched) and updates
`tests/sampler_api.rs`, the README defaults table, the CHANGELOG 0.2.0
Changed section and `wiki/release-0.2.0.md`.

## Reporting

`artifacts/summary.json`, `artifacts/results-table.md`, `README.md`
(verdict), `LEDGER-ENTRY.md` (WP26-UTURN-DEFAULT-V1), `CHECKSUMS.sha256`
(raw draws hashed, not committed). Failures are results; no cell is rerun;
nothing is tuned after seeing results. A driver crash is relaunched and the
interrupted cell re-run from scratch (seeded), logged below.

Before freezing, the harness was smoke-tested on one model with seed 1
(not a study seed; output deleted) to confirm the arms differ only in the
recorded `u_turn` and that the binaries run; the Eight Schools binary was
run once to a scratch path (deleted).

## Load caveat

Shared 16-thread machine (Intel Core Ultra 7 255H, Windows 11); other agents
may run during execution. Walls are upper bounds; ESS per gradient is the
machine-independent primary figure.

## Deviations

(none at freeze)
