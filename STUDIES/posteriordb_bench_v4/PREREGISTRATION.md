# posteriordb benchmark v4 — preregistration

Frozen before execution on 2026-09-02 (see `protocol.json`; its SHA-256 is the
first line of `CHECKSUMS.sha256`). Nothing in this file or in `protocol.json`
is edited after the first evidence cell starts; deviations are appended under
"Deviations" with a timestamp.

## Question

`STUDIES/posteriordb_bench_v3` (seeds 79101–79103, WP25) measured the DA arm
at 35/51 gates, 0.344x CmdStan's bulk ESS per gradient over 17 models, 0.751x
CmdStan's wall per gradient and 1.35x nutpie's ESS per second, with
`Tuning::default()` at **four** refinement levels. Since then:

* `STUDIES/funnel_defaults_v1` (WP28) changed `Tuning::default()` to
  **eight** refinement levels — it removes the funnel tail bias and, on the
  noncentered Eight Schools and a 100-D Gaussian, the extra levels are a cap
  those targets never reach (1.05x and 1.00x ESS per call).
* `STUDIES/step_collapse_v1` (WP27) traced the `sblrc`/`earnings` step
  collapse to the default metric regularisation (`TowardUnit`, an additive
  floor of `5/(n+5)` ~ 0.01 on the variance) and found
  `DiagonalMetricRegularization::Stan` (floor 1e-5) gives 9.7x on `sblrc`
  and 1.9x on `earnings` — while `earnings` loses its gate (R-hat 1.02 at
  the corrected metric: the WALNUTS orbit is a third of NUTS's there). It
  stayed opt-in.
* `STUDIES/uturn_default_v1` (WP26) rejected `UTurnRule::MomentumSum` as the
  default (1.064x geomean, 0.78x worst model); `Endpoints` stays.

**Two questions.** (1) Does the eight-level default hold the v3 breadth
figures on the full protocol — is it, as predicted from the cost cells, free
on posteriors that are not funnels? (2) Measured on the full 17-model set
with fresh seeds and the competitors alongside, does the Stan regularisation
meet a default rule of "≥ 1.1x geomean over DA, no model < 0.8x, no gate
lost"?

## What is identical to v3

Model set (17 posteriordb posteriors, commit `28f8d3d`), 4 chains, 1,000
warmup, 1,000 retained, `Tuning::default()` (now `h0 = 0.5`, depth 10,
**8** refinement levels, `delta = 1`), `Metric::diagonal()`, dual averaging
at 0.8 with the WP24 warmup exhaustion rule, `Init::uniform()` starts drawn
through `sampler::uniform_starts` with the cell seed,
`Limits::admit_worst_case()`, `ReplicatedStanTarget` on a BridgeStan 2.9.0 /
Stan 2.39.0 library built **without** `STAN_THREADS`, CmdStan 2.39.0 via
cmdstanpy 1.3.0 defaults, nutpie 0.16.8 defaults, ArviZ 0.23.4 estimators,
gates (rank R-hat <= 1.01, bulk and tail ESS >= 400 on every reference
parameter, zero sampling divergences, finite draws, no sampler error),
metrics, 45-minute cell timeout, strictly sequential run order, the
frozen-chain definition, and the driver (`run_posteriordb.py`, edited only
for the arm list, the recorded refinement fraction, the stanreg-vs-DA and
v3-vs-v4 comparisons and the predictions).

## What differs

1. **The harness is rebuilt against the current `src/`** (main after the
   WP26/WP27/WP28 merges), so `Tuning::default()` has
   `max_refinement_levels = 8`. Before freezing, the rebuilt binary was
   smoke-tested on the noncentered eight schools with seed 1 (both oWALNUTS
   arms, outputs deleted): the cell metadata reports
   `max_refinement_levels: 8`, the DA arm records
   `metric_regularization: TowardUnit (default)` and the stanreg arm
   `metric_regularization: Stan`, both with the `AcceptUnlessDivergent`
   warmup rule and kernel revision `v10`.
2. **Seeds 83101, 83102, 83103** (grep of `STUDIES/`, `wiki/`, `src/`,
   `integrations/` on every branch before freezing: no occurrence as a
   seed; `exact_state_space_ground_truth_v1` uses 83001–83004).
3. **Arms**: `owalnuts-da` (current defaults), **`owalnuts-da-stanreg`**
   (`Adaptation::Custom(WarmupConfig::new(0.8)
   .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
   .with_metric_regularization(DiagonalMetricRegularization::Stan))` — the
   sampler's default warmup plus that one option, the `reg` arm of
   `step_collapse_v1`), `cmdstan`, `nutpie`. The v3 stan-style control is
   dropped. 17 x 4 x 3 = 204 cells.
4. **Recorded per oWALNUTS cell**: `refined_fraction` (fraction of the 4,000
   retained transitions whose selected refinement level is > 0, from the
   per-chain histogram the v3 harness already wrote) and
   `refined_beyond_level_4_fraction` (levels 5–8, which the v3 default could
   not select). Nothing else in the telemetry changed.
5. **Compiled models**: the v3 compiled libraries, venv and posteriordb
   checkout were in the removed v3 worktree; every model is compiled fresh
   with the same toolchain and flags. The `eight_schools_noncentered`
   library compiled for the smoke test is kept and reused (compilation is
   not a measurement).

## Preregistered analysis

1. Per-model table and head-to-head as v3 for both oWALNUTS arms against
   CmdStan and nutpie (geomean of seed-median ratios of min bulk
   ESS/gradient, ESS/s and wall per gradient over models complete on both
   sides; wins; outright wins).
2. stanreg-vs-DA table: per model, the seed-median ratio of min bulk
   ESS/gradient and ESS/s, gradients, final steps, gates on both; geomean
   over models with both medians, the minimum, the models below 0.8x, and
   the models where stanreg passes fewer seeds than DA ("gate lost").
3. v3-vs-v4 table: per model and arm the seed-median v4/v3 ratio of
   ESS/gradient and ESS/s (`owalnuts-da` vs v3 `owalnuts-da`;
   `owalnuts-da-stanreg` vs v3 `owalnuts-da`; cmdstan and nutpie vs
   themselves). The cmdstan and nutpie rows measure seed noise and machine
   load; the DA row measures the eight-level default plus seed noise.
4. Refined-fraction table per model for both oWALNUTS arms.
5. Predictions (`protocol.json`):
   * **P1** owalnuts-da passes all gates on >= 35 of 51 cells (v3: 35).
   * **P2** owalnuts-da geomean bulk ESS/gradient vs CmdStan over 17 models
     within 0.9–1.1x of v3's 0.344 (0.310–0.378): eight levels should be
     near-free here.
   * **P3** stanreg >= 2x DA on both `sblrc` and `earnings` ESS/gradient.
   * **P4** stanreg geomean >= 1.1x DA over the 17 models with no model
     below 0.8x.
   * **P5** owalnuts-da geomean wall per gradient <= 1.0x CmdStan (v3:
     0.751).
   Ungated expectations: the refined fraction at levels 5–8 is ~0 on every
   model except possibly the centered eight schools and `accel_gp`; `sblrc`
   under stanreg reaches `h ~ 0.1` and passes >= 2/3; `earnings` under
   stanreg loses its gate on at least one seed (R-hat > 1.01), so the
   default rule below fails on "no gate lost" even if P3 and P4 hold;
   `hmm_drive_0` and `lotka_volterra` remain seed-draw coin flips for every
   oWALNUTS arm; centered eight schools, `accel_gp`, `one_comp` fail for
   every arm.

**Default rule** (reported, not applied here): `DiagonalMetricRegularization::Stan`
becomes the default only if stanreg is >= 1.1x DA on the geomean, no model
is below 0.8x, and no model loses a gate.

## Reporting

`artifacts/summary.json`, `artifacts/results-table.md`, `README.md`
(verdict, prediction outcomes, per-model v3-vs-v4 regressions),
`LEDGER-ENTRY.md`, `CHECKSUMS.sha256` (raw draws hashed, not committed;
CmdStan CSVs neither hashed nor committed). Failures are results; no cell is
rerun; nothing is tuned after seeing results. A driver crash is relaunched
and the interrupted cell re-run from scratch (seeded), logged below.

## Load caveat

Shared 16-thread machine (Intel Core Ultra 7 255H, Windows 11); other agents
may run during execution. Walls are upper bounds; ESS per gradient is the
machine-independent primary figure.

## Deviations

(none at freeze)
