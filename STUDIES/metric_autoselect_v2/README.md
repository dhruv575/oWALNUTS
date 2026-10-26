# WP79 `metric_autoselect_v2`: per-run dense / diagonal auto-selection, round two

**Verdict: PROPOSE for a default-flip confirmation.** Every preregistered rule
holds: R1, R2, R3, R4, R5, F and D. The flag stays research-only. The flip is
the coordinator's call.

One preregistered prediction failed. The Hessian-fit statistic did **not**
fix earnings: earnings and kidiq took the diagonal branch on 6 of 6 runs
(prediction B2 failed).

## What changed (library commit `cac8c704`)

**A. The diagonal branch is the diagonal driver.**

- The run executes the unflagged diagonal run, with a passive (x, g) observer.
- At the close of window 2, a diagonal decision simply continues that run.
- A dense decision hands each chain to the dense adaptive driver.

**B. The decision uses a Hessian-fit statistic.** The gradients from windows
1 and 2 are regressed on the positions. The rule takes the dense branch iff
all three hold:

- the fitted precision P is SPD;
- the whitening gain G_H >= 5;
- min_i R^2 >= 0.5.

The 0.5 bound was fixed in advance from WP75's recorded draws
(`artifacts/calibration.json`). There, the GP posteriors stay at or below
0.163 and every dense winner is at or above 0.80.

## Rules

| rule | result | held |
|---|---|---|
| R1 passes | auto 44 vs diag 44 | yes |
| R2 geomean auto/diag | 2.20 | yes |
| R3 no model < 0.9x | none below | yes |
| R4 new divergences | none | yes |
| R5 bit identity | 43/43 diagonal-branch cells (33 P + 10 F) identical | yes |
| F funnel P5 | 0.0482 ± 0.0019 (exact 0.0478) | yes |
| D flag-off integrity | diff scoped, fingerprints, both auto-select test files, full suites | yes |

The dense arm reproduces WP51 at a geomean of 2.99x.

## Branch taken vs predicted: 45 of 51 (Pa, which needed 48, fails)

**Dense, as predicted, 3 of 3 seeds each:** diamonds, mesquite, nes2000, arK,
hmm_example and lotka_volterra. Their auto/diag ratios run from 2.5x to 36.9x.

**Diagonal, as predicted:** the other nine models. This includes the GP guard
on gp_pois_regr and accel_gp, 6 of 6 (B1 holds; WP75 had sent both dense).
The linearity of gp_pois_regr was 0.11-0.14.

gp_pois_regr shows why the guard matters. On these seeds dense passed 1 of 3,
while auto (diagonal branch) passed 3 of 3.

**Misses:** earnings and kidiq went diagonal on all six runs.

- Their in-run linearity was 0.002-0.32, against 0.99 on retained draws.
- G_H was undefined on 4 of the 6 runs.

The warmup windows 1 and 2 of these near-degenerate posteriors fail the
linear fit too. They are not just non-stationary, as WP75 had assumed. The
likeliest reason is that early-warmup draws sit far from the mode, in a
non-Gaussian region. Ill-conditioning of C_xx (|corr| about 1) may also
contribute.

The earnings miss is therefore **accepted, not fixed**. It costs earnings
about 7x and kidiq about 7x (the dense/diag ratio), but costs no gates.

## Reading

- Change A worked exactly: no diagonal-branch run can lose to the diagonal
  arm.
- Change B separates the GP posteriors from the regressions but is
  conservative on the most correlated models.
- The geomean is 2.20 rather than the predicted 2.7, because of the earnings
  and kidiq misses.

## Files

- **Design and calibration:** `protocol.json`, `PREREGISTRATION.md` (frozen
  at `aa2af6a6`; a threshold-key harness fix landed before any evidence
  cell, `6f888207`), and `calibrate.py`.
- **Harness:** `run_study.py`, `src/bin/*.rs` and `box/*.sh`.
- **Results:** `artifacts/` (cells, `summary.json`, `results-table.md`,
  `environment.json`, `box-logs/`, draws manifest) and `CHECKSUMS.sha256`.

Walls are pinned, co-tenanted, and not used.
