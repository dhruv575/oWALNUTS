# WP71 `gradient_metric_v1`: gradient-informed diagonal metric

**Verdict: NOT SUPPORTED.** The rules R1, R2 and R3 fail; F and D hold.

nutpie's diagonal estimator, `sqrt(var(x_i) / var(g_i))`, was installed in
oWALNUTS's Stan-window warmup as a research flag. It does **not** raise ESS
per gradient on the house posteriordb set:

| | Result | Rule | Outcome |
|---|---|---|---|
| Geomean ratio vs default | **0.983** (0.844 without hmm_drive_0) | R1: >= 1.10 | fail |
| Passes | **40** vs 43 | R2: not lower | fail |
| Divergences | 3 new, all on eight_schools_centered | R3: none new | fail |

The predicted gainers, the correlated regressions, lost the most. On the
funnel the estimator is sound and better than default: P5 is 0.0480 ± 0.0026,
divergences fall from 9 to 5, and ESS per gradient is 1.57x. The flag stays
research-only and off by default. There is no default flip, and nothing
changes for users.

## What was tested

The library commit is `5cfbd199`. It adds `walnutpie::DiagonalMetricEstimator`
(`DrawVariance` by default, plus `GradientInformed` and
`GradientInformedOverlap`), with the builder behind `research`.

**How the estimate is formed.**

- At the end of each slow window, `s_i = sqrt(var_x_i / var_g_i)` replaces
  the draw variance in Stan's regularisation:
  `(n/(n+5)) s_i + 1e-3 * 5/(n+5)`. The result is then floored and inverted.
- `x` is the selected state and `g` is the gradient cached at that state, so
  the estimate costs no extra target calls.
- The window schedule is unchanged: 25, 50, 100, 200 and 500 transitions at
  1,000 warmup.
- The overlap variant merges the previous window's statistics with the
  current window's (Chan merge).

The full specification is in `PREREGISTRATION.md` and `protocol.json`, frozen
in `7cab386b` before any evidence cell.

**Runs.**

- 17 house models x 3 seeds (717501–717503) x 3 arms at 4 x 1,000/1,000,
  with the v7 gates.
- Funnel at 10 seeds (717401–717410) x 3 arms at 4 x 2,000/20,000.
- All 183 cells completed, with no errors or timeouts.
- They ran on AWS `owalnuts-bench` lane 3 under `taskset -c 8-11`, co-tenanted
  with other lanes. Walls are "pinned, co-tenanted" and are not used. ESS per
  gradient, pass counts and divergences are unaffected.
- Dispatch was the WP65 `ReplicatedConcurrent` path with 4 replicas.

## Results

**Overall.** Pass counts out of 51 were 43 (default), 40 (gradmetric) and 38
(overlap). The pooled warmup gradient share was 0.481 for default, 0.510 for
gradmetric and 0.503 for the overlap arm: warmup gets slightly more
expensive, not cheaper.

| model | pass d/g/o | ratio g | ratio o | final mass geomean g/d | gradients g/d | min bulk ESS g/d |
|---|---|---:|---:|---:|---:|---:|
| eight_schools_nc | 3/3/3 | 1.08 | 1.23 | 1.07 | 0.89 | 0.94 |
| eight_schools_c | 0/0/0 | 1.11 | 0.98 | 3.57 | 1.18 | 1.57 |
| diamonds | 3/2/2 | 0.85 | 0.89 | 3.36 | 0.47 | 0.37 |
| earnings | 3/3/2 | 0.80 | 0.79 | 11.1 | 0.81 | 0.63 |
| mesquite | 3/3/2 | 0.84 | 0.75 | 2.99 | 0.71 | 0.61 |
| kidiq | 3/3/3 | 0.76 | 0.77 | 3.10 | 0.83 | 0.63 |
| sblrc | 3/3/3 | 0.99 | 1.17 | 1.04 | 1.00 | 1.00 |
| nes2000 | 3/3/3 | 0.83 | 0.91 | 2.92 | 0.90 | 0.70 |
| arK | 3/3/3 | 0.71 | 0.78 | 2.57 | 0.93 | 0.67 |
| arma11 | 3/3/3 | 1.06 | 1.03 | 1.00 | 0.98 | 1.02 |
| garch11 | 3/3/3 | 0.89 | 0.84 | 1.58 | 0.88 | 0.78 |
| gp_pois_regr | 3/2/3 | 1.09 | 1.07 | 7.06 | 0.83 | 1.00 |
| hmm_example | 3/3/3 | 0.56 | 0.62 | 1.47 | 0.82 | 0.47 |
| hmm_drive_0 | 1/2/2 | 11.3 | 15.2 | 1.11 | 0.80 | 11.0 |
| one_comp | 3/1/0 | 0.47 | 0.50 | 1.39 | 0.97 | 0.42 |
| lotka_volterra | 3/3/3 | 0.88 | 0.88 | 2.71 | 0.72 | 0.61 |
| accel_gp | 0/0/0 | 0.94 | 0.99 | 8.78 | 0.80 | 0.67 |

The last three columns compare gradmetric with default, as medians over seeds.
Mass is inverse variance, so a mass ratio above 1 means the installed
variances are smaller. The `artifacts/results-table.md` table also has the
median ESS per gradient, divergences, R-hat, warmup share and step per arm.

- **Gainers.** 5 of 17 models gain. hmm_drive_0's 11x is the known
  second-mode lottery: default passes 1/3 seeds, and gradmetric's max R-hat is
  1.31. Without it the geomean is 0.844.
- **Lost passes.**
  - diamonds lost one on R-hat and bulk ESS.
  - gp_pois_regr lost one on R-hat and ESS.
  - one_comp lost two on R-hat and ESS.

**Funnel (P5 exact 0.0478).**

| arm | P5 ± s.e. | divergences | exhaustions | omega tail ESS | ESS/grad |
|---|---|---:|---:|---:|---:|
| default | 0.0528 ± 0.0027 | 9 | 310 | 704 | 9.7e-5 |
| gradmetric | 0.0480 ± 0.0026 | 5 | 164 | 810 | 1.5e-4 |
| overlap | 0.0476 ± 0.0030 | 4 | 106 | 774 | 1.4e-4 |

## Rules and predictions

**Rules for gradmetric.**

- R1 fails: 0.983.
- R2 fails: 40 < 43.
- R3 fails on eight_schools_centered (0 -> 3 divergences).
- F holds: the error is 0.0003, against an s.e. of 0.0026.
- D holds:
  - the library diff touches only `src/walnutpie.rs` and
    `tests/gradient_metric.rs`;
  - `kernel_fingerprint` passes with and without `research`;
  - the flag-off bit-identity test passes;
  - the pipeline check found a plain-feature default cell bit-identical to
    the research-build default cell.

**Overlap arm** (reported only): R1 fails at 1.025, R2 fails at 38, and R3 and
F hold.

**Predictions.**

- Pa fails: the predicted gainers' geomean is 0.84, against 1.03 for the
  other models.
- Pb fails: 1 of the 4 is in the top 6.
- Pc fails: the warmup share rises.
- Pd holds: the share changes by +2.9 points.
- Pe holds: the overlap arm is within 5 % of the primary.
- Pf fails: passes were also lost on diamonds and one_comp.
- Pg holds: funnel divergences are 5 <= 9. Pg was preregistered but left out
  of `run_study.py analyze`, so it is computed here from the funnel table.

## Why it loses: a reading of the data, not a test

`sqrt(S_ii / (S^-1)_ii)` is the geometric mean of the marginal and
conditional variances. It sits below the marginal variance whenever
coordinates are correlated.

On the correlated models the installed variances are 3–11x smaller (earnings
11x, accel_gp 9x, gp_pois_regr 7x, kidiq, nes2000 and diamonds about 3x).
Steps grow and gradients mostly fall to 0.7–0.9x (diamonds 0.47x). But min bulk ESS falls further, to
0.6–0.7x: trajectories in the rescaled space are too short to cross the
marginal scale. On the funnel, a smaller omega scale helps instead.

So nutpie's per-gradient lead on the regressions does not come from this
estimator inside Stan's windows. It more likely comes from nutpie's schedule
or the way the estimator and schedule interact, since WP58's whole-metric
transplant did gain.

## Files

- `protocol.json`, `PREREGISTRATION.md`: the frozen design.
- `run_study.py`, `src/bin/pdb.rs`, `src/bin/funnel.rs`, `box/*.sh`: the
  harness and drivers.
- `artifacts/`: the 183 cells in `cells/`, plus `summary.json`,
  `results-table.md`, `run-log.txt`, `environment.json` and `box-logs/`.
- `artifacts/draws-manifest.sha256`: hashes of the 153 posteriordb draw files.
  The draws themselves are not committed.
- `CHECKSUMS.sha256`.
