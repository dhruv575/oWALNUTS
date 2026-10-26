# WP75 `metric_autoselect_v1`: per-run dense / diagonal auto-selection

**Verdict: NOT PROPOSED as a default.** R1 and R3 fail; R2, R4, F and D hold.
That is exactly the preregistered prediction.

auto keeps most of the dense wins: geomean ESS per gradient is **2.30x the
diagonal** (the dense arm here is 2.92x), against a 1.5 bar. But auto passes
**39 gate cells against the diagonal's 44**, and **two models fall below
0.9x**:

- hmm_drive_0 at 0.09x;
- eight_schools_noncentered at 0.89x.

The flag stays research-only and off by default.

## What was tested

The library commit is `090eaa20`. It adds
`WarmupConfig::with_dense_auto_select(DenseAutoSelectConfig)`, behind
`research`, for the dense adaptive facade only.

**Before the switch.** In warmup slow windows 0 and 1, every chain installs
the diagonal only.

**The switch.** At the close of slow window 2 (transition 249) the chains
meet once and compute:

- `G = kappa_diag / kappa_dense`, the out-of-window whitening gain;
- the regularised estimate comes from window 1's pooled within-chain
  covariance, using Stan's rule;
- that estimate is then evaluated on window 2's covariance.

The run goes dense iff **G >= 5**. Windows 2, 3 and 4 then install one family,
so retained draws come from one metric.

**The threshold** was fixed from recorded data, not from this study's seeds:

1. WP48's reference geometry gives `k`, the population version of `G`.
2. WP51's observed dense/diag ratios were fitted against it:
   `ratio = 0.707 k^0.473`.
3. The fitted ratio reaches 1.5 at `k = 4.9`.

**Runs.**

- 17 house models x 3 seeds (757501–757503) x 3 arms: diag, dense, auto.
- Shape 4 x 1,000/1,000, with the v7 gates.
- Funnel at 10 seeds (757401–757410) x 3 arms at 4 x 2,000/20,000.
- All 183 cells completed, with no errors.
- They ran on AWS lane 3 under `taskset -c 8-11`, co-tenanted, so walls are
  not used. Dispatch was the WP65 `ReplicatedConcurrent` path with 4 replicas.
- The frozen design is in `PREREGISTRATION.md`, `protocol.json` and
  `artifacts/reference-prediction.json` (commit `a0bd292e`).

## Branch taken vs predicted

45 of 51 runs took the predicted branch (Pa: >= 45, holds). The decision was
identical across chains in every cell.

| model | predicted | taken (3 seeds) | G | pass diag/dense/auto | dense/diag | auto/diag |
|---|---|---|---|---|---:|---:|
| eight_schools_nc | diag | diag x3 | 0.7–1.0 | 3/3/3 | 0.98 | **0.89** |
| eight_schools_c | diag | diag x3 | 1.8–2.6 | 0/0/0 | 0.68 | 1.08 |
| diamonds | dense | dense x3 | ~4e3 | 3/3/3 | 65.3 | 37.7 |
| earnings | dense | **diag x3** | 0.02–1.5 | 3/3/3 | 5.12 | 1.02 |
| mesquite | dense | dense x3 | 111–231 | 3/3/3 | 18.1 | 13.3 |
| kidiq | dense | **diag**, dense, dense | 0.8 / 96 / 101 | 3/3/3 | 5.32 | 4.46 |
| sblrc | diag | diag x3 | 0.2–1.2 | 2/3/3 | 0.73 | 1.05 |
| nes2000 | dense | dense x3 | 120–172 | 3/3/3 | 14.5 | 12.3 |
| arK | dense | dense x3 | 50–56 | 3/3/3 | 7.58 | 6.12 |
| arma11 | diag | diag x3 | 1.0–1.2 | 3/3/3 | 0.97 | 0.97 |
| garch11 | diag | **dense, dense**, diag | 5.08 / 5.28 / 4.95 | 3/3/3 | 1.71 | 1.54 |
| gp_pois_regr | dense | dense x3 | 89–109 | 3/**0/1** | 1.21 | 1.15 |
| hmm_example | dense | dense x3 | 11–14 | 3/3/3 | 3.04 | 2.86 |
| hmm_drive_0 | diag | diag x3 | 0.6–0.8 | 3/2/**1** | 0.44 | **0.09** |
| one_comp | diag | diag x3 | 1.7–2.0 | 3/2/2 | 1.13 | 0.95 |
| lotka_volterra | dense | dense x3 | 7.5 / 141 / 98 | 3/3/**2** | 14.2 | 13.8 |
| accel_gp | dense | dense x3 | 6–12 | 0/0/0 | 1.08 | 1.36 |

## Rules

- **R1 fails.** The pass count is 39 against 44. Five cells were lost:
  - **gp_pois_regr, 2 cells (3/3 to 1/3).** auto took the dense branch, as
    predicted. Absolute ESS fell below 400 at a higher per-gradient rate,
    exactly as in WP51. The dense arm was 0/3.
  - **hmm_drive_0, 2 cells (3/3 to 1/3).** These were on the diagonal branch:
    one seed has R-hat 1.29 (the second-mode lottery) and one has tail ESS 86.
    The dense arm also lost one seed to R-hat 1.53.
  - **lotka_volterra, 1 cell.** One dense-branch seed had a stuck chain
    (R-hat 1.53, bulk ESS 7).
  - **one_comp, 1 cell.** It failed on tail ESS.
  - **sblrc gained 1 cell.**
- **R2 holds** at 2.297.
- **R3 fails** on hmm_drive_0 (0.09) and eight_schools_nc (0.89).
- **R4 holds.** Divergences were 1/1/1, all on eight_schools_centered.
- **F holds.** auto's funnel P5 is 0.0480 ± 0.0034. All 10 seeds took the
  diagonal branch (Pd holds), with 8 divergences against diag's 19. The dense
  arm had 141.
- **D holds.**
  - The library diff is scoped to `src/walnutpie.rs` and
    `tests/metric_autoselect.rs`.
  - `kernel_fingerprint` passes with and without `research`.
  - The flag-off bit-identity test passes.
  - The pipeline check found the plain-feature diag cell bit-identical to the
    research-build diag cell.

**Predictions.**

- **Pb holds:** the failed set is exactly {R1, R3}. The reasons differ from
  the ones predicted. accel_gp was predicted to fail R3 but came out 1.36x
  with every arm at 0/3. hmm_drive_0 and eight_schools_nc failed R3 instead.
- **Pc holds:** dense/diag is 2.92.

## Reading

**The statistic separates the correlated regressions from the rest. It cannot
see the GP posterior.**

- **Correct dense calls.** mesquite, nes2000, arK, diamonds, kidiq,
  hmm_example and lotka_volterra.
- **Correct diagonal calls.** The near-independent models (arma11, sblrc,
  hmm_drive_0, eight_schools_nc) and the funnel.

**Two failure modes.**

1. **gp_pois_regr.** The statistic picks dense (G about 100), and dense loses
   gates there. No window-whitening statistic separates it from mesquite.
2. **earnings and one kidiq seed.** auto went diagonal although the reference
   G is 49–115. Under a diagonal warmup, windows 1 and 2 of these extremely
   correlated posteriors (max |corr| about 1.0) are too poorly mixed for the
   window-1 estimate to whiten window 2. This cost earnings its 5x gain.

**The R3 and most of the R1 losses sit on the diagonal branch.** hmm_drive_0
is 3/3 under diag but 1/3 on auto's diagonal branch. That branch is the dense
driver with diagonal installs, so it is statistically, not bitwise, the diag
arm, and 3 seeds cannot separate a driver difference from the known
hmm_drive_0 lottery.

A version worth a follow-up would make the diagonal branch the diagonal
driver itself, so that "never lose a diagonal gate" holds by construction
there. It would also add a guard aimed specifically at GP posteriors.

## Files

- `protocol.json`, `PREREGISTRATION.md`, `artifacts/reference-prediction.json`:
  the frozen design.
- `run_study.py`, `src/bin/pdb.rs`, `src/bin/funnel.rs`, `box/*.sh`: the
  harness and drivers.
- `artifacts/`: the 183 cells in `cells/`, plus `summary.json`,
  `results-table.md`, `run-log.txt`, `environment.json` and `box-logs/`.
- `artifacts/draws-manifest.sha256`: hashes of the draws, which are not
  committed.
- `CHECKSUMS.sha256`.
