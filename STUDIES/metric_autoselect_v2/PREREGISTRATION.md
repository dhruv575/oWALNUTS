# WP79 `metric_autoselect_v2`: preregistration

Frozen before the first evidence cell. `protocol.json` is the machine-readable
version and wins on any difference.

## Question

WP75 found two problems with per-run dense / diagonal auto-selection:

1. Its diagonal branch was the dense driver with diagonal installs. It was not
   the diagonal arm, and it lost gates there (hmm_drive_0 0.09x,
   eight_schools_nc 0.89x).
2. Its window-whitening statistic G had two failures:
   - it chose dense on the GP posteriors, where dense loses gates;
   - it missed earnings (in-run G 0.02-1.5, reference 49).

WP79 fixes these as two separately predicted changes, behind one research flag:
`DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5)`, diagonal facade only.

## Change A: the diagonal branch is the diagonal driver

**How the run works**

- Every chain runs the unflagged default diagonal run (the flag is removed from
  the per-chain config).
- A passive observer reads each selected position and gradient in slow
  windows 1 and 2. It draws no randomness and makes no target calls.
- At the close of window 2 (transition 249) the chains decide.
- **Diagonal branch:** the same runs continue to the end.
- **Dense branch:** each chain is handed to the dense adaptive driver. It
  installs the Stan dense precision of that chain's window-2 draws, then runs
  windows 3-4 densely.

**Frozen rule R5:** 100 % of diagonal-branch auto cells (posteriordb and
funnel) are bit-identical to the diag arm on the same seed, in draws hash and
gradient count.

**Predictions**

- **A1:** R5 holds.
- **A2:** every all-diagonal model is exactly 1.000x with identical passes.
  This means WP75's two R3 failures disappear.
- **A3:** F's outcome is the diag arm's own outcome, because the P5 values are
  identical.

## Change B: the Hessian-fit statistic and GP guard

**The statistic.** Over windows 1+2 (600 pooled draws), take the pooled
within-chain covariance of (x, g). Then:

- B = C_gx C_xx^-1;
- linearity = min_i R^2_i of the fit g ~ x;
- P = -sym(B);
- G_H = kappa_diag / kappa_dense of P^-1, under Stan-regularised whitening.

**The rule.** Dense iff all three hold:

- P is SPD;
- G_H >= 5 (WP75's threshold; G_H is the population version of WP48's k);
- linearity >= 0.5.

**Calibration.** The bound comes from WP75's recorded draws:
`artifacts/calibration.json`, made by `calibrate.py`.

- The GP posteriors never exceed 0.163: gp_pois_regr median 0.104, accel_gp
  median 0.096 (and its P is never SPD).
- Every dense winner is at least 0.80. That includes mesquite 0.81 and
  diamonds 0.994.

**Why the GP posteriors trip the guard.** Their gradients are far from linear
in position: the curvature changes across the posterior through exp(f) and
K(rho, alpha)^-1. In gp_pois_regr, 12 of 13 coordinates have R^2 < 0.5. The
regressions, by contrast, are near-Gaussian.

**Why earnings failed in WP75, and how the fix works.** Under the diagonal
warmup, the windows of a posterior with |corr| about 1 are non-stationary, so
window 1 does not whiten window 2. The Hessian fit does not need stationarity,
because g = -P(x - mu) holds wherever the chain is. The calibrated G_H for
earnings is 140.

**Predictions**

- **Pa:** at least 48 of 51 runs take the branch in `predicted_branch`.
  - Dense: diamonds, earnings, mesquite, kidiq, nes2000, arK, hmm_example,
    lotka_volterra.
  - Diag: the other 9 models.
- **B1:** gp_pois_regr and accel_gp are diag on 6/6 runs.
- **B2:** earnings and kidiq are dense on 6/6.
- **B3:** diamonds and mesquite are dense on 6/6.
- **B4:** the funnel is diag on 10/10.
- **B5:** WP75's G, recorded in the same runs, is below 5 on at least 2 of 3
  earnings seeds.

## Design and rules

**Design** (the same as WP75 otherwise):

- 17 house models x 3 fresh seeds (797501-797503) x diag / dense / auto, at
  4 x 1,000/1,000, with ReplicatedConcurrent dispatch and v7 gates.
- Funnel at 10 seeds (797401-797410) x 3 arms, at 2,000/20,000.
- Lane 3, `taskset -c 8-11`. No reruns.

**Rules:**

- **R1:** auto passes >= diag passes.
- **R2:** geomean auto/diag >= 1.5.
- **R3:** no model below 0.9x.
- **R4:** no new divergences.
- **F:** funnel P5 within 1 s.e.
- **R5:** bit identity, as above.
- **D:** diff scoped, fingerprint with and without research, and both
  auto-select test files pass.

**PROPOSE** (for a default-flip confirmation) iff every rule holds.

**Predicted outcome:**

- every rule holds, with geomean about 2.7 (range 2.0-3.5);
- F is A3's coin, about 68 %;
- predicted verdict: PROPOSE, conditional on F.
