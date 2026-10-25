# Preregistration — metric_regularisation_scalefree_v1 (WP41)

Frozen 2026-10-24 before the first evidence cell, on branch
`wt/metric-regularisation` (from `main` at `3583d130`). `protocol.json` carries
the same content in machine form; its hash is in `CHECKSUMS.sha256` and in
`summary.json`. The only pre-freeze computation is `predict_scales.py`
(`artifacts/prediction-scales.json`): the posterior variance of every
unconstrained coordinate from the posteriordb **reference** draws and the
variance each rule would install from a perfectly measured final window. It
runs no sampler and is an input to the predictions, not evidence.

## Question

The shipped default `DiagonalMetricRegularization::Stan` installs
`(n/(n+5)) var_i + 1e-3 * 5/(n+5)` at each slow-window boundary (WP31/WP32,
adopted together with `UTurnRule::MomentumSum`). Its additive term is an
absolute constant, about 1e-5 at the final window (`n = 500`), so a target
whose coefficients all live at 1e-5 (`sblrc`) has its installed variance
nearly doubled, while a target at 1e4 is unregularised. WP27
(`step_collapse_v1`) named the unmeasured alternative: a **scale-free** rule
that shrinks toward the window's own median variance. Does it beat Stan's
rule on the 17-model posteriordb screen, and is it safe on Neal's funnel?

## Change under test (opt-in; existing variants and fingerprints unchanged)

Two new `DiagonalMetricRegularization` variants in `src/walnutpie.rs`
(`DiagonalVariance::regularized_mass`), reachable through
`sampler::Adaptation::Custom(WarmupConfig::...with_metric_regularization(..))`
and the Python binding (`"scale_free_median"`, `"scale_free_stan_median"`).
With `n` the window's draw count, `var_j` the window variances and
`m = median_j var_j` (mean of the two middle values in even dimension):

| arm | variant | installed variance | role |
|---|---|---|---|
| `da` | `Stan` (the shipped default, `Adaptation::default()`) | `(n/(n+5)) var_i + 1e-3 * 5/(n+5)` | reference |
| `sfmed` | `ScaleFreeMedian` | `(n/(n+5)) var_i + (5/(n+5)) * m` | **primary** (k = 5, Stan's weight; the task's rule) |
| `sfstan` | `ScaleFreeStanMedian` | `(n/(n+5)) var_i + 1e-3 * (5/(n+5)) * m` | secondary (Stan's rule with the unit replaced by `m`; identical to `Stan` when `m = 1`) |

Unmeasured coordinates: a coordinate whose window variance is zero is
installed at the anchor term alone (`(5/(n+5)) m`, resp. `1e-3 (5/(n+5)) m`),
i.e. relative to the other coordinates rather than at an absolute floor. If
`m` itself is not finite and positive (more than half the coordinates did not
move in the window), the anchor falls back to `m = 1` for that window, which
is `TowardUnit` for `sfmed` and exactly `Stan` for `sfstan`. The existing
`MIN_ADAPTATION_VARIANCE = 1e-12` clamp still applies. Unit test
`scale_free_metric_regularisations_match_the_formula_and_are_scale_free`
checks the formula, exact scale covariance (rescaling all coordinates by
1e-4 rescales the installed mass by 1e8) and both fallbacks. `cargo test`
(debug and release) is green, including `tests/kernel_fingerprint.rs`; the
kernel revision is unchanged (`...-v10`).

Why these two arms. `sfmed` is the WP27 candidate as stated (scale-free
`TowardUnit`). `sfstan` separates *scale-freeness* from *strength*: it keeps
Stan's 1e-3 relative weight, so it differs from `da` only where the median
variance is far from 1, and it is the arm that tests the unmeasured-coordinate
risk hardest (its anchor is ~1e-5 of the median). A geometric-mean anchor
was not chosen because on these models it sits within a factor of a few of
the median and would not separate a mechanism.

## Protocol

The `posteriordb_bench_v5` / `refinement_role_v1` protocol: 17 posteriors
(posteriordb `28f8d3d`), 4 chains x 1,000 warmup / 1,000 retained,
`Init::uniform()` starts (shared across arms per seed by construction),
`Metric::diagonal()`, `Tuning::default()`, `Limits::admit_worst_case()`, four
threads on a non-`STAN_THREADS` BridgeStan 2.9.0 build compiled in this
study, ArviZ 0.23.4 estimators, 2,700 s cell timeout. oWALNUTS only; CmdStan
v5 seed medians are cited for context, not rerun. **Seeds 4101001, 4101002,
4101003** (`git grep -w` found none before this freeze). Strictly
sequential: models in protocol order; within a model arms `da`, `sfmed`,
`sfstan`; within an arm seeds ascending; one sampling process at a time.
Then the funnel: arms in the same order, seeds ascending.

Gates per cell (house standard): rank R-hat <= 1.01, bulk and tail ESS >=
400 on every reference parameter, zero retained divergences, finite draws,
no sampler error. Efficiency: per cell the minimum over reference parameters
of bulk ESS / total target calls (warmup included); per model the seed
median; per arm the geometric mean over the 17 models of the per-model
ratio arm / `da`. The reference arm is the `da` arm run here on the same
seeds and starts.

Instrumentation (`src/main.rs`, `run_scalefree.py`): per chain the final
installed mass diagonal and every slow-window metric update (window,
transition, draw count, outcome, installed mass, step before); per cell the
ratio of installed variance (1 / mass) to the variance of the cell's retained
unconstrained draws, per coordinate and chain. The README tabulates it
per coordinate for `sblrc`, `earnings`, `kidiq`, `diamonds`.

Funnel side check (copied from `refinement_role_v1/protocol.json`): Neal's
10-D funnel at the sampler defaults with the arm's regularisation, 4 x 2,000
/ 20,000, starts `omega in {-3, -1, 1, 3}`, per-seed MCSE z of
`P(omega < -5)` against the exact 0.0478; gate `|z| <= 2` on every seed.

## Decision rule (frozen)

Recommend flipping `sampler::DEFAULT_METRIC_REGULARIZATION` to a scale-free
arm **iff** for that arm:

- **C1** geometric mean over the 17 models of the min-bulk-ESS-per-gradient
  ratio vs `da` >= **1.10**;
- **C2** no model's seed-median ratio below **0.85** (no carve-outs; a model
  without a ratio fails C1 and C2);
- **C3** cells passing all gates >= `da`'s;
- **C4** funnel `|z| <= 2` on every seed.

If both qualify, the higher C1. Otherwise recommend keeping `Stan`; the new
variants stay opt-in. The study recommends; it does not change the default.
Every cell is reported; no reruns; failures are results; nothing is tuned
after seeing results.

## Predictions (with numbers, before any cell)

Pre-freeze scale input (`artifacts/prediction-scales.json`, reference draws, a
perfectly measured final window of `n = 500`; max over coordinates of the
installed / posterior variance):

| model | dim | median var | min var | max var | `da` | `sfmed` | `sfstan` |
|---|---:|---:|---:|---:|---:|---:|---:|
| eight_schools_centered | 10 | 22.9 | 1.38 | 31.5 | 0.99 | 1.15 | 0.99 |
| diamonds | 26 | 4.6e-05 | 3.1e-06 | 0.108 | **4.22** | 1.14 | 0.99 |
| earnings | 5 | 4.3e-04 | 1.7e-04 | 1.58 | 1.05 | 1.01 | 0.99 |
| mesquite | 7 | 0.052 | 0.013 | 0.103 | 0.99 | 1.03 | 0.99 |
| kidiq | 4 | 2.46 | 1.2e-03 | 34.3 | 1.00 | **22** | 1.01 |
| sblrc | 6 | 1.0e-06 | 9.6e-07 | 5.3e-03 | **11.3** | 1.00 | 0.99 |
| nes2000 | 10 | 0.056 | 1.1e-03 | 0.544 | 1.00 | 1.51 | 0.99 |
| arK | 7 | 5.0e-03 | 1.2e-04 | 8.7e-03 | 1.08 | 1.42 | 0.99 |
| arma11 | 4 | 1.6e-03 | 1.3e-04 | 3.6e-03 | 1.07 | 1.11 | 0.99 |
| garch11 | 4 | 0.239 | 0.015 | 1.70 | 0.99 | 1.14 | 0.99 |
| hmm_example | 4 | 0.052 | 1.9e-03 | 0.116 | 1.00 | 1.26 | 0.99 |
| hmm_drive_0 | 6 | 0.037 | 3.1e-03 | 0.208 | 0.99 | 1.11 | 0.99 |
| one_comp | 4 | 0.057 | 0.010 | 2.04 | 0.99 | 1.05 | 0.99 |
| lotka_volterra | 8 | 0.017 | 7.4e-03 | 0.028 | 0.99 | 1.01 | 0.99 |
| accel_gp | 66 | 0.668 | 0.058 | 254 | 0.99 | 1.10 | 0.99 |

(`eight_schools_noncentered` and `gp_pois_regr` are skipped: their reference
draws do not carry the unconstrained parameters.) Two things follow before
any cell. First, Stan's absolute prior still over-states `sblrc`'s
coefficient variance ~11x and one `diamonds` coordinate ~4x: WP27's
statement that CmdStan's `1.07e-5` inverse metric on `sblrc` "is the
posterior variance" reads as the Stan-regularised value of a ~1.0e-6
posterior variance (`(500/505) 1.0e-6 + 9.9e-6 = 1.09e-5`). Second, the
median anchor is not scale-free *within* a model: on `kidiq` (two
coordinates at ~1e-3, two at 5-34) the even-dimension median is 2.46 and
`sfmed` over-states the small coordinates 8-22x, worse than `TowardUnit`.

- **P1** sfmed (primary) geomean vs da 1.00 (90% interval 0.88-1.10): fails C1
- **P2** sfmed on kidiq 0.5x (0.3-0.8x): kidiq's unconstrained posterior variances are 34, 4.9, 0.0037, 0.0012, the even-dimension median is 2.46 and the 5/(n+5) weight installs 0.024 on the two small coordinates (predicted installed/posterior 7.6x and 22x, measured median over chains >= 5x on the smallest coordinate, against da ~1.0x); sfmed fails C2 on kidiq
- **P3** sblrc: the posteriordb reference variance of the five coefficients is ~1.0e-6, so Stan's 9.9e-6 prior installs ~11x the posterior variance (measured da installed/posterior >= 5x on the coefficients; WP27's 'CmdStan's 1.07e-5 inverse metric is the posterior variance' was the Stan-regularised value, not the posterior). Both scale-free arms install 0.8-1.3x. sblrc ratio vs da 2.5x (1.5-4x) for both arms, median final step >= 1.5x da's
- **P4** sfstan (secondary) geomean vs da 1.065 (0.98-1.15); P(C1 >= 1.10) ~0.3; every model's predicted max installed/posterior <= 1.01 so outside sblrc and diamonds the ratios are seed noise around 1 (kidiq, earnings, arma11, arK, nes2000 within 0.85-1.15x)
- **P5** diamonds: da installs up to 4.2x the posterior variance on one coordinate and 1.2-1.5x on fourteen; both scale-free arms ~1.0-1.1x; ratio vs da 1.1x (0.85-1.5x) for both arms (depth-capped either way)
- **P6** sfmed other models: nes2000 0.9x (0.75-1.05; 1.5x inflation on its 0.0011 coordinate), arK 0.9x (0.75-1.05; 1.4x), hmm_example 0.95x (0.8-1.1); remaining healthy models within 0.85-1.1x; the lottery / fail-everywhere cells (hmm_drive_0, lotka_volterra, centered eight schools, accel_gp, one_comp) may fall anywhere
- **P7** earnings keeps >= 2/3 gates under both scale-free arms and every coordinate installs within 0.5-2x of its posterior variance in every chain (no coordinate installed at the anchor alone: MomentumSum orbits measure every coordinate)
- **P8** funnel |z| <= 2 on every seed for all three arms
- **P9** cells passing: da 42 +- 4 of 51; sfmed da - 3 to da + 1 (kidiq may lose gates, sblrc cannot gain: already 3/3 in v5); sfstan within da +- 2
- **P10** no arm meets the rule (probability ~0.85); recommendation keep DiagonalMetricRegularization::Stan; if an arm qualifies it is sfstan
