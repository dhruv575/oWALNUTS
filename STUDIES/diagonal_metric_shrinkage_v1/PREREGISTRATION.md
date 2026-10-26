# Diagonal metric shrinkage (WP81): preregistration

Frozen before the first evidence cell. The machine-readable form is
`protocol.json`.

## Question

WP80 found one consistent mechanism behind nutpie's per-gradient lead: a
smaller effective oWALNUTS step (B1). On sblrc, oWALNUTS's installed
inverse mass is about 11x the posterior variance on the betas and about 1x
on sigma, with a raw step of 0.10 against nutpie's 0.66 (diamonds: 0.0035
against 0.062). This study asks two things:

1. **Descriptive.** Does the installed metric over-state the posterior
   variance on a subset of coordinates of the house 17, where nutpie's does
   not?
2. **Decision.** Does a regularisation that removes the over-statement meet
   the frozen rule?

## What the code does (read before designing)

- **The default rule.** At each slow-window boundary the shipped default,
  `DiagonalMetricRegularization::Stan` (`sampler::DEFAULT_METRIC_REGULARIZATION`,
  `src/walnutpie.rs` `DiagonalVariance::regularized_mass`), installs

      (n/(n+5)) var_i + 1e-3 * 5/(n+5)

  This is Stan's rule exactly. `n` is the window's draw count, as in Stan's
  `windowed_variance_estimator`. So "Stan's rule with the correct n" is
  already the default, and it is not a candidate.
- **Why sblrc over-states.** The absolute `1e-3 * 5/(n+5)`, about 1e-5 for a
  500-draw window, dominates variances near 1e-6 (WP41 measured
  9.8–11.9x).
- **What WP41 already tested** (`STUDIES/metric_regularisation_scalefree_v1`).
  It tested shrinkage toward the window's median variance (`ScaleFreeMedian`,
  `ScaleFreeStanMedian`) and found it not supported:
  - kidiq lost 0.61x, because a median anchor is not scale-free within a
    two-scale model;
  - there were funnel failures.
  
  The coordinator's example "toward the window's median variance" is
  therefore not repeated.
- **nutpie.** nutpie installs a gradient-informed diagonal,
  sqrt(var(x)/var(grad)), with no 1e-3 prior. WP71 tested that estimator in
  oWALNUTS.

## Candidates (research-only, `--features research`, commit `f52537a1`)

Both keep Stan's rule unchanged for any window whose variances are all at
least 1e-3. They lower the absolute anchor only where it would dominate.

| arm | installed variance |
|---|---|
| `owalnuts` (default) | `(n/(n+5)) var_i + (5/(n+5)) 1e-3` |
| `owalnuts-lowanchor` (`StanLowAnchor`) | `(n/(n+5)) var_i + (5/(n+5)) min(1e-3, v_min)`, where `v_min` is the smallest finite positive window variance |
| `owalnuts-coordcap` (`StanCoordinateCap`) | `(n/(n+5)) var_i + (5/(n+5)) min(1e-3, var_i)`, so a coordinate below 1e-3 is installed at its own variance |

A coordinate whose window variance is not finite and positive keeps 1e-3
under both rules (the WP31 frozen-coordinate guard).

Testing:

- The unit test `wp81_low_anchor_and_coordinate_cap_match_the_formula`
  checks both formulas and the identity with Stan on wide windows.
- The default and the existing variants compute bit-identically through a
  shared helper.
- `tests/kernel_fingerprint.rs` passes with the feature off and on, both
  locally and on the box (`artifacts/fingerprint-test.txt`).

## Design

- **Models and seeds.** v7's house 17 x fresh seeds 810101–810103. Arms run
  in this order: `owalnuts`, `owalnuts-lowanchor`, `owalnuts-coordcap`,
  `nutpie`.
- **Cells.** 4 x 1,000 / 1,000. oWALNUTS runs through `ReplicatedStanTarget`
  (4 replicas). v7 cell code and gates; one child per cell; sequential; no
  reruns. That gives 204 cells.
- **Stored per cell.** The final mass diagonal and step per chain for
  oWALNUTS; `mass_matrix_inv`, step and unconstrained draws for nutpie.
- **Funnel.** Neal's funnel, three oWALNUTS arms x ten fresh seeds
  (810111–810120), with v7's funnel protocol.
- **Reference variances.** posteriordb reference draws are mapped to the
  unconstrained scale with BridgeStan `param_unconstrain` (no sampling).

## Part 1: descriptive

For each coordinate, the ratio is the median over chains of the installed
inverse mass, divided by the variance of the cell's own retained
unconstrained draws. It is also divided by the reference variance where one
exists. Per model, each coordinate's ratio is the median over seeds. The
table reports the min, the max, and the number of coordinates outside
[0.5, 2], with the adapted step.

- **D1 (coordinator).** On each WP80 step-gap model (sblrc, hmm_drive_0,
  eight_schools_centered, diamonds), the default has at least one
  coordinate outside [0.5, 2] and nutpie has none.
- **D1b (this study, from WP41).** The default has at least 5 coordinates
  outside on sblrc and at least 1 on diamonds. Every coordinate is inside
  on hmm_drive_0 and eight_schools_centered, whose step gap is not the
  regularisation.

## Part 2: the frozen rule (each candidate against the default, same seeds)

| | criterion |
|---|---|
| R1 | cells passing the v7 gates not lower than the default (/51) |
| R2 | WP72-form (c) headline, min bulk ESS per gradient candidate / default: per-model median over seeds, a model entering with 3 of 3 paired ok seeds; geomean **>= 1.10** |
| R3 | median over models of the per-model ratio **>= 1.05** |
| R4 | leave-one-model-out geomean minimum **>= 1.00** |
| R5 | no new divergences: no (model, seed) where the candidate has retained divergences and the default none |
| R6 | funnel: the mean of the 10 per-seed P(omega < -5) within 1 s.e. (sd/sqrt 10) of 0.0478 |
| R7 | kernel fingerprint test passing with the flags off |

A candidate meets the rule only if R1–R7 all hold. **No default flip in
this study**, whatever the outcome. The seed bootstrap (rng seed 81) is
reported only.

## Predictions

- **C1, C2.** Both candidates fail R2 and R3. They change only models with
  window variances below 1e-3. WP41's sblrc gain of about 2x is worth about
  1.04 over 17 models.
- **C3.** Both reach at least 1.5x on sblrc.
- **C4.** Each is bit-identical to the default on at least 24 of 51 cells.
- **C5.** R1, R5 and R6 hold for both.
- **Expectation.** Neither candidate meets the rule; the verdict is "not
  supported, keep Stan".

## Platform

AWS c7a.4xlarge, lane 1: `taskset -c 0-3` with `RAYON_NUM_THREADS=4` and
`OMP_NUM_THREADS=1`. Walls are **"pinned, co-tenanted"** and enter no
criterion. Pass counts and ESS per gradient are unaffected by co-tenancy.

## Execution rules and disclosures

- **Freeze.** `PREREGISTRATION.md` and `protocol.json` are committed before
  any evidence cell. The driver refuses cells otherwise.
- **Smoke test.** It ran before the freeze, at non-evidence seed 11, into
  scratch output that is not committed. It was written after the
  predictions above, which are unchanged. It covered:
  - one sblrc cell per arm;
  - one funnel `coordcap` run (P 0.0471, z −0.10);
  - the part-1 code.
- **What the smoke test showed.** The default reproduced WP80's seed-11 cell
  exactly (147,611 gradients). On sblrc at seed 11:

  | | ratios (betas; sigma) | step | ESS/grad vs default |
  |---|---|---|---|
  | default | 9.8–12.0x; 1.03 | 0.093 | — |
  | `lowanchor` | about 1.0 | about 0.34 | about 1.8x |
  | `coordcap` | about 1.0 | about 0.33 | about 1.8x |
  | nutpie | about 0.41–0.49x; 0.91 | 0.65 | — |

  nutpie's beta ratios are outside the band, so D1 looks likely to fail on
  sblrc. D1 is left as the coordinator stated it.
- **Run rules.** Failures are results. There are no reruns and no tuning.
  Raw draws and telemetry are checksummed and not committed.
