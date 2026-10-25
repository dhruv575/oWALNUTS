# Preregistration — dense_metric_posteriordb_v1 (WP48)

Frozen 2026-10-24 before the first evidence cell. `protocol.json` carries the
same content in machine form; its SHA-256 is written into `summary.json` and
`CHECKSUMS.sha256`. Nothing here was chosen after seeing a sampling cell of
this study. The only pre-freeze computations are (a) a code reading of the
dense path, (b) a non-evidence self-check on the funnel (seed 1, 200 + 200
draws) proving that the `Adaptation::Custom` construction is bit-identical to
`Adaptation::default()` on the dense metric, (c) the geometry of the
posteriordb **reference** draws (`artifacts/reference-geometry.json`,
`run_dense.py prepare`), which are public data, not sampler output, and (d)
harness smoke tests on the non-evidence seed 1 (artifacts discarded):
`eight_schools_noncentered` and `arma11` for diag, literal dense and
(legacy-seeded) dense-stan, which exposed findings 4 and 5 below, and
`eight_schools_noncentered` for the two fresh-seeded dense arms after the
fix. They informed the two fixes and the decision to add the `dense-seeded`
arm and nothing else (no threshold, prediction or rule was set from them).

## Question

`Metric::dense()` exists in `src/sampler.rs` but has never been benchmarked on
posteriordb. Three open items point at correlated posteriors: `diamonds` is
depth-10-capped in every sampler at h 0.003–0.005 (open question 2), `accel_gp`
is 0.47x CmdStan with an unmeasured slow-coordinate metric (open questions 1
and 9), and `gp_pois_regr` is step-sensitive. Does an adapted dense metric fix
these, what does it cost on the other 14 models (d^2 adaptation statistics and
an O(d^2) leapfrog), and can a WHEN-TO-USE rule be written from the dimension
and a cheap correlation statistic?

## What the code reading found (before freezing)

1. **The dense kernel is exactly metric-aware.** `sample_dense_fixed` runs the
   unchanged kernel on `DenseCoordinates`, i.e. in `z = L^T q` with `M = L L^T`
   (M = momentum covariance = target precision) and an identity metric. Drift,
   energy and the `MomentumSum` U-turn (`rho . p` with the identity) in `z` are
   exactly the dense-metric quantities `rho^T M^{-1} p` in `q`. The gradient is
   mapped by `L^{-1}` (`solve_lower`), positions by `L^{-T}` (`solve_upper`).
   No defect.
2. **The shipped dense regularisation is not Stan's.** `DenseCovariance::
   precision_candidate` shrinks with `s = clamp(d / (n + d), 0.05, 0.8)`:
   off-diagonals times `1 - s`, each variance to `(1 - s) var_i + s * mean_j
   var_j`, then escalates a ridge until the squared Cholesky-pivot ratio of the
   covariance is `<= 1e6`. Stan uses `(n / (n + 5)) Sigma + 1e-3 (5 / (n + 5)) I`.
   The shipped rule's diagonal target is the *mean* variance, so it is not
   scale-free: any coordinate (or eigendirection) with variance far below the
   mean is floored near `s * mean var` — the same failure class as the `v10`
   diagonal floor that WP27 diagnosed (`sblrc` 1,000x too wide). The `1e6`
   condition cap on the raw covariance additionally floors problems whose
   covariance is legitimately ill-conditioned by scale alone.
3. **Overheads.** Every gradient pays two dense triangular solves (`d^2` flops)
   and two heap allocations. Dense warmup calls `sample_dense_fixed` once per
   transition (a fresh kernel call with one retained draw), which re-evaluates
   the start (about one extra gradient per warmup transition) and clones the
   configuration; the diagonal path has a cached initial evaluation. Dense
   adaptation is per chain (no pooling) and rejects chain rescue (the default
   has none since WP36). A window needs `max(d + 1, 20)` draws, so for `d >= 25`
   the first 25-draw window installs nothing, and for `accel_gp` (`d = 66`) the
   first two windows install nothing.
4. **Dense adaptive warmup reuses one RNG stream for every warmup transition
   (found by the seed-1 smoke test, then confirmed in the code).** Each warmup
   transition is a separate kernel call seeded
   `splitmix64(seed ^ transition ^ segment_index)`, and `segment_index` is
   incremented once per transition from 0, so `transition == segment_index`
   and the seed is `splitmix64(seed)` at every warmup transition: the same
   initial momentum and tree-direction stream from a moving position. Warmup
   is then a deterministic map, not a Markov chain with fresh randomness, and
   each window's covariance is estimated from that orbit. Smoke test: whitened
   `kappa` 184 (eight schools noncentered) and 170 (`arma11`) against 2.2 and
   1.8 for the diagonal. Retained draws use a different seed and are a valid
   Markov chain at whatever metric was installed. Remedy, **opt-in**:
   `walnutpie::DenseWarmupSeeding::PerTransition`
   (`WarmupConfig::with_dense_warmup_seeding`; default `Legacy` reproduces
   every existing run), seed `splitmix64(splitmix64(seed) ^ (t + 1) *
   0x9e3779b97f4a7c15)`. With it the smoke-test `kappa` is 2.1.
5. **`Metric::dense()` could not run a default-length sampler run.** Under the
   default `Limits::admit_worst_case()` the run is admitted against its exact
   worst case, but the dense driver's inner fixed-dense call for the retained
   phase re-checks the *conservative* ceiling (113M evaluations), which 1,000
   retained draws at depth 10 / eight levels exceed, so every such run failed
   with "target-evaluation bound exceeds its resource limit (chain 0)". Fixed
   (not opt-in: admission only, draws unchanged, previously an error) by
   raising each chain's inner ceiling to the admitted one;
   `tests/sampler_api.rs::dense_metric_runs_default_length_under_worst_case_admission`.

Because finding 2 would make a negative result for the shipped estimator
uninformative about "an adapted dense metric", this study adds an **opt-in**
variant `walnutpie::DenseMetricRegularization::Stan` (`WarmupConfig::
with_dense_metric_regularization`; default `MeanVarianceShrinkage`, so every
existing run, the `walnutpie` facade and `tests/kernel_fingerprint.rs` are
unchanged). It applies Stan's formula with no condition cap; a ridge is added
only if factorisation fails. With findings 4 and 5 the arms separate the three
defects: the literal shipped `Metric::dense()` (only the admission fix, which
it needs to run at all), fresh seeding with the shipped shrinkage, and fresh
seeding with Stan's regularisation. `cargo test` passes with all three changes
(240 tests; `tests/kernel_fingerprint.rs` unchanged).

## Arms

| arm | configuration |
|---|---|
| `owalnuts-diag` | `Metric::diagonal()`, `Adaptation::default()` — the shipped default (Stan diagonal regularisation, `MomentumSum`, no chain rescue) |
| `owalnuts-dense` | `Metric::dense()`, `Adaptation::default()` — the shipped dense path literally (legacy seeding, mean-variance shrinkage), plus the admission fix |
| `owalnuts-dense-seeded` | `Metric::dense()`, `Adaptation::Custom(WarmupConfig::new(0.8)` + `DEFAULT_WARMUP_EXHAUSTION` + `DEFAULT_METRIC_REGULARIZATION` + `DenseWarmupSeeding::PerTransition)` — shipped shrinkage |
| `owalnuts-dense-stan` | as `owalnuts-dense-seeded` plus `DenseMetricRegularization::Stan` |
| `cmdstan-dense` (external reference, three target models only) | CmdStan 2.39.0 via cmdstanpy 1.3.0, defaults except `metric=dense_e` |

CmdStan `diag_e` is cited from `STUDIES/posteriordb_bench_v6` cells (seeds 90101–90103), not rerun.

## Protocol

- posteriordb `28f8d3d`, the 17 posteriors of `posteriordb_bench_v6` in its
  order; `Tuning::default()`, `Init::uniform()`, `Limits::admit_worst_case()`;
  4 chains x 1,000 warmup / 1,000 retained, 4 threads, BridgeStan 2.9.0
  `ReplicatedStanTarget` (no `STAN_THREADS`).
- Seeds 148101, 148102, 148103 (exact-word search over the repository outside
  the posteriordb checkout found no use; 148104 occurs as a count and is not
  used).
- Order: models in listed order; within a model arms diag, dense,
  dense-seeded, dense-stan;
  seeds ascending; strictly sequential. Then CmdStan dense_e on `diamonds`,
  `accel_gp`, `gp_pois_regr` (3 seeds, sequential). Then the funnel side check.
  Then the cost decomposition (not evidence cells).
- Gates (house standard, ArviZ 0.23.4): rank R-hat <= 1.01, bulk and tail ESS
  >= 400 on every reference parameter, zero retained divergences, finite draws,
  no sampler error. Efficiency: minimum bulk ESS over reference parameters per
  gradient (all target calls incl. warmup, start search excluded as in v6);
  per-model seed median; ratios dense / diag.
- Recorded per cell: final step per chain, depth-cap fraction, gradients
  (total and per chain), contended wall, every metric-update record, and the
  **whitened condition number** `kappa` = condition of `L^T Sigma_hat L`,
  where `Sigma_hat` is the pooled retained unconstrained covariance of that
  cell and `M = L L^T` the installed metric of each chain (diagonal mass, or
  the last installed dense precision); also the condition number of the
  installed metric itself.
- Predictor (computed on every diag cell): from the first 500 retained draws
  of each chain, pooled (2,000 draws, the same metric as the last slow window;
  the facade does not expose warmup draws, so this is the stand-in for "the
  last diagonal window"), the maximum absolute off-diagonal correlation of the
  unconstrained draws, `max|corr|`, and the correlation-matrix condition
  number. The rule uses the per-model seed median of `max|corr|` and `d`.
- Funnel side check: Neal's 10-D funnel, the v6 protocol (starts omega in
  {-3,-1,1,3}, 4 x 2,000 / 20,000), arms dense, dense-seeded and dense-stan,
  seeds as above.
- Cost decomposition (contended, minima over repetitions): (a) BridgeStan
  gradient cost per model, single replica, at 100 retained diag draws of seed
  148101; (b) sampler-side overhead per gradient for each arm at each model's
  dimension, on an iid Gaussian target, one chain, one thread, 1,000 + 1,000,
  minimum over five repetitions. Quiet-machine wall estimate per cell =
  max over chains of that chain's target calls x (gradient cost + arm
  overhead at d). These are estimates; contended walls are also reported and
  labelled.

## Decision rules (frozen)

**D1 — documentation.** For each target model (`diamonds`, `accel_gp`,
`gp_pois_regr`) and each dense arm separately, "dense is advised" iff the seed
median of dense min-bulk-ESS per gradient is >= 1.5x the diag arm's AND dense
passes at least as many of the three gate cells as diag. Documenting dense as
the advised setting for a model class follows for each target model that
passes. The study verdict for an arm is *supported* if all three pass, *mixed*
if one or two pass, *not supported* if none. The rule is applied to each of
`owalnuts-dense` (what a user gets today), `owalnuts-dense-seeded` (advice
conditional on adopting the seeding fix) and `owalnuts-dense-stan` (advice
conditional on adopting both opt-ins).

**D2 — auto rule.** Classify each of the 17 models for an arm: *winner* =
ratio >= 1.5 and gates >= diag; *loser* = ratio < 1.0 or gates < diag;
otherwise *neutral*. The preregistered predictor selects a model iff
`d <= D* = 100` and seed-median `max|corr| >= c* = 0.6`. An `auto` rule is
recommended iff the predictor selects every winner and no loser (neutrals may
fall either way) and there is at least one winner; evaluated separately for
each dense arm. `D* = 100` does not bind in
this set (max `d = 66`); it records that the O(d^2) leapfrog is unmeasured
beyond it.

**D3 — funnel.** Dense arms are harmless on the funnel iff |MCSE z| <= 2 on
every seed. Failure blocks any `auto` recommendation for that arm.

Reported, not gating: ESS/s ratios (contended and quiet estimate), kappa,
step, depth-cap fraction, CmdStan dense_e versus diag_e (v6).

## Predictions (numerical, per model)

The table's "dense" column is the prediction for **`owalnuts-dense-seeded`**
(shipped shrinkage, fresh seeds); it was written before finding 4 for the
shrinkage alone and is kept unchanged. The literal `owalnuts-dense` arm
(legacy seeding) has no formula: predicted ratio < 1.0 on at least 12 of the
17 models and gate passes <= diag on every model.

Basis: the posteriordb reference draws, unconstrained through BridgeStan
(`artifacts/reference-geometry.json`). For each model, `kappa` is the condition
number of the reference covariance in the whitened coordinates of the metric
each estimator would install from that covariance at `n = 500` (the last slow
window): Stan diagonal (the diag arm), the shipped dense rule, and Stan dense.
For near-Gaussian posteriors leapfrogs per U-turn scale as `sqrt(kappa)`, so
the predicted ESS-per-gradient ratio is `sqrt(kappa_diag / (kappa_dense * w))`
with `w = ((1 + sqrt(d/n)) / (1 - sqrt(d/n)))^2` the Wishart noise factor of a
dense estimate from `n` draws. Where the posterior is not near-Gaussian, or the
reference lacks the parameter block, the number is a judgement (basis column).
A per-model ratio prediction **holds** if the observed seed-median ratio is
within a factor 2 of it.

Reference geometry worth stating: `diamonds` has max |corr| only 0.89 but a
correlation-matrix condition number of 2.6e5 (collinearity among many
predictors, not one pair); the shipped dense rule leaves `kappa` 1,033 there
(Stan dense 11). On `earnings`, `kidiq` and `sblrc` the shipped rule's
mean-variance floor makes the installed metric *worse than the diagonal*
(`kappa` 2.1e5, 6.9e3, 273 against 1.3e4, 195, 64). On `sblrc` Stan's absolute
`1e-3 * 5/(n+5) = 1e-5` prior is of the order of the coefficient variances
(1e-5), so Stan dense (59) is no better than Stan diagonal (64).

| model | d | ref max abs corr | predicted dense / diag | predicted dense-stan / diag | basis |
|---|---:|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered | 10 | None | 1.0 | 1.0 | no parameter-block reference columns; noncentered posterior nearly independent |
| eight_schools-eight_schools_centered | 10 | 0.607 | 1.0 | 1.0 | funnel; a global linear metric cannot fix it; formula would say 2.6/3.8 |
| diamonds-diamonds | 26 | 0.888 | 9.9 | 94.62 | formula |
| earnings-logearn_interaction | 5 | 0.999 | 0.2 | 9.75 | formula |
| mesquite-logmesquite_logvash | 7 | 0.952 | 6.86 | 17.39 | formula |
| kidiq-kidscore_momhsiq | 4 | 0.946 | 0.14 | 10.97 | formula |
| sblrc-blr | 6 | 0.816 | 0.39 | 0.83 | formula |
| nes2000-nes | 10 | 0.784 | 2.61 | 14.8 | formula |
| arK-arK | 7 | 0.629 | 4.48 | 8.22 | formula |
| arma-arma11 | 4 | 0.26 | 0.85 | 1.06 | formula |
| garch-garch11 | 4 | 0.701 | 1.37 | 2.37 | formula |
| gp_pois_regr-gp_pois_regr | 13 | None | 1.2 | 1.3 | no parameter-block reference columns (f_tilde absent); noncentered GP, alpha/rho-f_tilde coupling is nonlinear |
| hmm_example-hmm_example | 4 | 0.894 | 1.08 | 3.48 | formula |
| bball_drive_event_0-hmm_drive_0 | 6 | 0.152 | 0.66 | 1.0 | formula; mode lottery decides gates |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | 0.636 | 0.93 | 1.82 | formula |
| hudson_lynx_hare-lotka_volterra | 8 | 0.955 | 5.34 | 12.59 | formula |
| mcycle_gp-accel_gp | 66 | 0.77 | 0.69 | 2.0 | formula says 0.69 / 12.3; the sdgp/lscale-to-zgp scale coupling is nonlinear, so dense-stan is tempered to 2.0 |

Frozen claims (P1–P8, machine form in `protocol.json`):

- **P1** geometric-mean ESS/gradient ratio versus diag over the 17 models:
  `owalnuts-dense-stan` >= 2.0 (formula about 4); `owalnuts-dense-seeded`
  between 0.6 and 1.5 (formula 1.22); literal `owalnuts-dense` <= 0.7.
- **P2** `owalnuts-dense-seeded` loses gate passes versus diag on
  `earnings`, `kidiq` and `sblrc`, and its installed `kappa` exceeds the diag
  arm's on those three.
- **P3** `diamonds`: diag depth-cap fraction >= 0.05 and step <= 0.006;
  `dense-stan` zero depth caps in at least 2 of 3 seeds and median step >= 0.05;
  dense-seeded median step between the two.
- **P4** D1: literal `owalnuts-dense` *not supported*; `owalnuts-dense-seeded`
  *mixed* (diamonds advised only); `owalnuts-dense-stan` *mixed* (diamonds and
  accel_gp advised, gp_pois_regr not).
- **P5** D2: no `auto` rule for either arm at `c* = 0.6`. For dense-stan the
  predicted false positive is `sblrc` (max |corr| 0.82, a loser by the floor
  mechanism above); for dense-seeded several (`earnings`, `kidiq`, `sblrc`,
  `accel_gp`); for the literal arm most selected models.
- **P6** funnel: dense-seeded and dense-stan |z| <= 2 on every seed; the
  literal arm is reported without a prediction.
- **P7** kernel overhead per gradient, dense minus diag (iid Gaussian, quiet
  minimum): <= 0.5 us at d <= 10 and <= 3 us at d = 66.
- **P8** CmdStan dense_e: on `diamonds` >= 20x the v6 CmdStan diag_e
  ESS/gradient; `owalnuts-dense-stan` between 0.6x and 1.2x CmdStan dense_e
  ESS/gradient on each target model where both pass all three gates.
- **P9** whitened `kappa` (median over chains, seed median): dense-stan below
  diag on every model whose reference `kappa_stan_diag_oracle >= 50` except
  `sblrc`; literal dense above diag on at least 12 of 17 models.


## Rules

Report every cell; no result-driven reruns; failures are results; no tuning
after seeing results. A process crash may be relaunched and only an interrupted
cell without a completed artifact may be rerun from scratch, with the deviation
recorded. Walls are measured on a shared machine (about ten agents on 16 cores)
and are not used to decide anything.
