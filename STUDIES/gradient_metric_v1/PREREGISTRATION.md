# WP71 `gradient_metric_v1`: preregistration

Frozen 2026-10-26 and committed before the first evidence cell.
`protocol.json` is the machine-readable copy and takes precedence if the two
disagree.

## Question

Does a gradient-informed diagonal metric estimator, added to the warmup as a
research flag, raise ESS per gradient on the 17 house posteriordb models
without losing gates?

**Why.** WP58 (`STUDIES/nutpie_per_gradient_gap_v1`) split the pooled
per-gradient gap to nutpie. The mass matrix accounts for 44 % of it on the
Python path and 60 % on the Rust path; warmup cost accounts for 44 %.
nutpie estimates its diagonal from both draw and gradient variances,
`sigma_i^2 = sqrt(var(x_i) / var(g_i))`. In v7, nutpie led oWALNUTS per
gradient most on the regressions and autoregressions: sblrc 2.82x, arma11
2.19x, kidiq 1.63x, earnings 1.47x, nes2000 1.37x, arK 1.31x.

## What is built

The library commit is `5cfbd199` on `wt/gradient-metric`, on top of main
`70e4c958`. It touches `src/walnutpie.rs` and adds `tests/gradient_metric.rs`.
It is a research flag and is not a default flip.

- **The flag.** `walnutpie::DiagonalMetricEstimator` has three values:
  `DrawVariance` (the default and the shipped rule), `GradientInformed` and
  `GradientInformedOverlap`. It is stored in
  `WarmupConfig::diagonal_metric_estimator`. The builder
  `with_diagonal_metric_estimator` sits behind the existing `research` Cargo
  feature, and the flag works on the diagonal driver only.
- **Flag off.** No gradient statistics are accumulated (the accumulator is
  `None`), so the warmup runs the shipped code path.
- **Rejected combinations.** Chain rescue, trapped-chain restart and the
  dense and structured facades return a configuration error.
- **Tests** (`tests/gradient_metric.rs`):
  - with the flag off, runs are bit-identical at the `RunConfig` level (one
    and four threads) and the `Sampler` level (`Adaptation::default()` versus
    `Custom` with `DrawVariance`);
  - on an independent Gaussian with standard deviations 0.01, 0.3, 1 and 50,
    both candidate estimators install masses within a factor [0.7, 1.4) of
    `1/s^2`;
  - runs are deterministic, and the thread count does not change draws;
  - the invalid combinations above are rejected.
- **Local checks.** The whole test suite passes with and without `research`,
  including `kernel_fingerprint`, and clippy reports no warnings under
  `-D warnings`.

## The estimator, exactly

Per chain, over each slow warmup window, the estimator uses the transitions at
which the shipped estimator already updates its Welford accumulator. At each
one it records:

- the selected position `x`, which is the chain state after the transition;
- the log-density gradient `g` at that same state. This is the selected
  state's cached gradient, so it costs no extra target evaluations.

Both are accumulated with Welford's algorithm in unconstrained coordinates.

**Estimate per coordinate.** At the window end, with window count `n`:

- `var_x_i = m2_x_i / (n − 1)` and `var_g_i = m2_g_i / (n − 1)`.
- `s_i = sqrt(var_x_i / var_g_i)` when both variances are finite and
  positive and the ratio is finite and positive.
- Otherwise, `s_i = var_x_i`, the shipped draw variance.

**Regularisation.** `s_i` replaces the draw variance in the configured
`DiagonalMetricRegularization`. In every arm here that is
`DEFAULT_METRIC_REGULARIZATION = Stan`, so:

`v_i = (n / (n + 5)) * s_i + 1e-3 * 5 / (n + 5)`

`v_i` is then floored at `MIN_ADAPTATION_VARIANCE` and inverted to the mass,
exactly as the shipped rule treats the draw variance. Installation is
unchanged: the dual-averaging stream restarts and the accumulators reset.
When `n < 2` there is no update, as shipped.

**The two candidates differ only in the statistics they use:**

- **`GradientInformed`** (primary arm `gradmetric`) uses the current slow
  window only.
- **`GradientInformedOverlap`** (secondary arm `gradmetric-overlap`) uses the
  exact Chan merge of the previous and current windows' (x, g) statistics,
  with `n` the merged count. The first slow window uses its own statistics.
  Consecutive estimates therefore overlap by one window, which is nutpie's
  overlapping-window idea placed inside the Stan schedule.

**Window schedule.** The schedule is unchanged:
`WarmupWindowConfig::default()`, Stan's 75 / 25-doubling / 50.

- At 1,000 warmup transitions the slow windows are 25, 50, 100, 200 and 500
  transitions long, covering transitions 75–924.
- At 2,000 they are 25, 50, 100, 200, 400 and 1,100.

Both schedules were confirmed by the smoke runs and are recorded per chain in
every cell.

**Not transplanted.** nutpie's own warmup schedule and its first-window
`1/|g|` initialisation are left out on purpose. This study isolates the
estimator.

## Arms

All arms run in one harness build: owalnuts with `research`.

- **`default`.** `Sampler::new()` defaults with `Adaptation::default()`.
- **`gradmetric`.** `Adaptation::Custom(...)` built from:
  - `WarmupConfig::new(0.8)`
  - `.with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)`
  - `.with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)`
  - `.with_diagonal_metric_estimator(GradientInformed)`

  Everything else is default. With `DrawVariance` in place of
  `GradientInformed`, this configuration is bit-identical to `default` (a
  library test).
- **`gradmetric-overlap`.** The same with `GradientInformedOverlap`. It is
  secondary and decides nothing.

## Blocks and seeds

- **P: posteriordb.**
  - 17 house models x 3 seeds x 3 arms at 4 x 1,000/1,000. That is 51 cells
    per arm.
  - The harness is WP68's v7 cell plus metric-update telemetry, run on the
    WP65-qualified Linux replicated BridgeStan dispatch (4 replicas).
  - The v7 gates apply: rank R-hat <= 1.01, bulk and tail ESS >= 400,
    0 retained divergences, finite draws, no error.
  - Gradients are all target calls: start search, warmup and sampling.
- **F: funnel sanity arm.**
  - 10 seeds x 3 arms at 4 x 2,000/20,000.
  - The harness is WP68's funnel (Neal 10-D, house starts).
- **Seeds.** P uses 717501–717503 and F uses 717401–717410. A `git grep -nowE`
  over the repository and the sibling worktrees' protocols found no hit. The
  neighbouring 7101xx and 7171xx/7173xx ranges have hits and were avoided.
  The box lanes are checked before the first cell.
- **Run order.** P runs first: models in house order, then seeds ascending,
  then arms in the order default, gradmetric, overlap. F runs second.
  - Cells run strictly sequentially, one process per cell, with a 2,700 s
    timeout.
  - An errored or timed-out cell is a failed cell. Cells are never rerun.

## Decision rules (primary arm `gradmetric`)

- **R1.** The geomean over models of the ratio (median over seeds of min bulk
  ESS per gradient, gradmetric) / (the same for default) is **>= 1.10**. Only
  models whose 3 seeds are status ok in both arms count, as in v7.
- **R2.** The gradmetric pass count is at least the default pass count, out
  of 51.
- **R3. No new divergences.** For every model, gradmetric's retained
  divergences summed over its 3 seeds are no more than default's.
- **F.** `|pooled P5(gradmetric) − 0.0477903522728147| <= 1 x` its
  between-seed s.e. over 10 seeds.
  - This is the coordinator's threshold. A correct sampler fails it about
    32 % of the time; that is recorded as a known property and the rule is
    not softened.
- **D. Flag-off integrity on the box.**
  - `git diff 70e4c958` of `src/`, `tests/`, `Cargo.toml` and `Cargo.lock`
    touches only `src/walnutpie.rs` and `tests/gradient_metric.rs`.
  - `kernel_fingerprint` passes with and without `research`.
  - `tests/gradient_metric.rs` passes, including the flag-off bit-identity
    test.

**Verdict.** SUPPORTED if R1, R2, R3, F and D all hold; otherwise NOT
SUPPORTED, naming the failed clauses. Either way the flag stays research-only
and off by default. There is no default flip here. The overlap arm is
evaluated against the same rules and only reported.

## Reported, not decided

- **Warmup gradient share.** This is warmup target calls / total target
  calls, per arm, per model and pooled. The default arm gives the "before"
  value and the candidates give the "after".
- **Per model.** Pass counts, ratios, divergences, max R-hat, final step size
  and failed gates.
- **Funnel.** Divergences, exhaustions, omega tail ESS, and the final masses
  of omega and x.

## Predictions

- **R1–R3.** The coordinator's predictions: geomean >= 1.10, pass count not
  lower, 0 new divergences.
- **Pa.** The predicted gainers have a higher geomean ratio than the other 13
  models. The gainers are the correlated linear regressions where nutpie led
  by at least 1.3x in v7: sblrc, kidiq, earnings and nes2000.
  - **Reasoning.** For a Gaussian posterior with covariance S, the estimate
    `sqrt(var x_i / var g_i)` equals `sqrt(S_ii / (S^-1)_ii)`. That is the
    geometric mean of the marginal and conditional variances, which
    shortens the trajectories that correlated coefficients force.
- **Pb.** At least 3 of those 4 are among the 6 models with the largest
  ratio.
- **Pc.** The pooled warmup gradient share is lower with gradmetric.
- **Pd.** The pooled warmup gradient share changes by less than 5 percentage
  points. The reasoning is that most of WP58's warmup-cost gap comes from the
  schedule, not the estimator.
- **Pe.** The overlap geomean ratio is within 5 % of the primary's.
- **Pf.** Any model that loses passes under gradmetric is gp_pois_regr or
  lotka_volterra, where WP58's nutpie-metric transplant lost gates.
- **Pg.** On the funnel, gradmetric's retained divergences are no more than
  default's.

## Machine and discipline

- **Machine.** AWS `owalnuts-bench`, lane 3.
  - Every build and cell runs under `taskset -c 8-11` with
    `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`.
  - Files live under `~/lanes/gradient_metric_v1/` only.
  - Other lanes are active, so walls are "pinned, co-tenanted" and are not
    used in any rule. ESS per gradient, pass counts and divergences are
    unaffected.
- **Inputs.**
  - BridgeStan is 2.9.0 built from source.
  - posteriordb is `28f8d3d`, read directly.
  - Python is `~/venv`, read-only: bridgestan 2.9.0 and ArviZ 0.23.4.
- **Disclosed non-evidence runs.**
  - Three local smoke runs of the funnel harness, all gradmetric on seed
    990671. Two short ones (about 0.1 s each) confirmed the window schedule.
    One 2,000/20,000 cell went through `run_study.py` with the artifacts
    redirected to scratch, to exercise the driver and the analysis (P5
    0.0424, 0 divergences).
  - On the box: the BridgeStan compile, and pipeline checks on seed 990671.
    These are one eight_schools_noncentered cell per arm plus a
    plain-feature default cell (to compare draws hashes), and one funnel
    cell per arm.
  - None of these outputs are committed.
- **Deviations.** Any deviation goes to `AMENDMENTS.md` before it takes
  effect.
