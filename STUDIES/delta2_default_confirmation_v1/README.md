# delta2_default_confirmation_v1 (WP63): delta = 2 does not become the default

## Verdict

**The frozen rule failed, so no flip.** The library is unchanged. Four of the
six conditions failed:

| id | condition | needed | measured | result |
|---|---|---|---|---|
| R1 | paired geomean, delta2 / default min-bulk-ESS per gradient, 17 models × 4 seeds | ≥ 1.08 | **0.896** | fail |
| R2 | leave-one-seed-out minimum | ≥ 1.00 | **0.860**; LOSO values 0.874, 0.985, 0.871, 0.860 | fail |
| R3 | gates, A+B (76 cells per arm) | delta2 ≥ default − 1 | delta2 **62**, default 61 | pass |
| R4 | passing delta2 cells with \|z\| > 4 | none | **one**: `accel_gp` seed 630604, `sdgp_1`, z = 5.07, R-hat 1.005, no divergences | fail |
| R5 | funnel pooled P(ω < −5), 12 seeds | not lower than default by more than 1 SE | delta2 0.0484 ± 0.0026, default 0.0502 ± 0.0029; difference −0.0018, SE of difference 0.0039 | pass |
| R6 | funnel divergences | ≤ 1.5 × default | delta2 **26**, default 5 (5.2×) | fail |

The earlier 1.07× (WP34) and 1.14× (WP49, 3 seeds) gains did not replicate on
four fresh seeds. On well-behaved models delta2 is neutral:

- the median model ratio is 1.027;
- the geomean over the 12 models that are stable in both arms is 1.033;
- the geomean over pairs where both cells pass is 1.019.

The overall geomean is set by a few multimodal or hard models where single
seeds swing in both directions:

| model | ratio | per-seed ratios | notes |
|---|---|---|---|
| `hmm_drive_0` | 0.172 | 0.69, **0.003**, 0.83, 0.83 | Seed 630602, delta2: one chain sat in the second mode, 63 log-density units low (R-hat 1.53). `chain_warnings` named it, three lines. The default cell at that seed was clean. |
| `eight_schools_centered` | 0.357 | | Fails the gates in both arms. delta2 had divergences in 2 of 4 cells; the default had none. |
| `one_comp` | 0.736 | | Gates 1/4 vs 3/4. |
| `accel_gp` | 1.594 | 0.42, 0.16, 3.23, 29.3 | |
| `gp_pois_regr` | 1.460 | | Gates 4/4 vs 2/4. |

Gates are a wash at 62 vs 61. The funnel tail mass agrees between the arms
and both are within about 1 SE of the exact 0.0478. Funnel divergences differ:

- delta2: 26, concentrated in seeds 630631 (12) and 630621 (7);
- default: 5;
- WP53 over 30 seeds: 37 vs 43, so 26 vs 5 sits against that and the
  divergence comparison is noisy at 12 seeds.

Predictions:

| id | prediction | result |
|---|---|---|
| P1 | geomean in [1.05, 1.15] | **failed** (0.896) |
| P2 | LOSO min ≥ 1.0 | **failed** (0.860) |
| P3 | gates within 1 | **held** (62 vs 61) |
| P4 | funnel tail within 1 SE | **held** (−0.0018 vs SE 0.0039) |
| P5 | funnel divergences within 1.5× | **failed** (5.2×) |

**Recommendation:** keep delta = 1. Even without the multimodal models,
delta2 is about 1.02–1.03×, which is below the 1.08 threshold and inside seed
noise. Further delta work is not worth a default slot.

## Design

The study was frozen at `df964429` before the first cell (see
`PREREGISTRATION.md` and `protocol.json`). It ran at main **`33a8e39d`**, whose
sampler and defaults are those of `f097391c`:

- best-of-16 starts;
- `RejectLeaf`;
- no rescue.

The arms are:

- `default`: `Sampler::new()` with only the run shape and `admit_worst_case`
  set.
- `delta2`: the same plus `.tuning(Tuning::default().max_error(2.0))`. Each
  cell records `final_max_error` (1.0 or 2.0) and the full `Tuning` it used.

The blocks are:

- **A:** the 17 WP34/WP49 house models at 4 × 1,000/1,000, seeds
  630601–630604, paired by seed.
- **B:** `accel_gp` and `hmm_drive_0` on seeds 630611–630614.
- **C:** Neal's 10-D funnel at 4 × 2,000/20,000 on the same 12 seeds,
  630621–630632, in both arms. It uses the WP53 binary.

Cells ran strictly sequentially, one sampling process at a time with four
threads, from 10:15 to 11:57. There were 152 posteriordb cells and 24 funnel
cells. No cell errored and nothing was rerun. Smoke tests used seeds
630691–630693 in a scratch directory before the freeze.

## Results

Full tables are in `artifacts/results-table.md` and machine-readable results
in `artifacts/summary.json`.

Per-seed geomeans over the 17 models:

| seed | geomean |
|---|---|
| 630601 | 0.966 |
| 630602 | 0.675 |
| 630603 | 0.976 |
| 630604 | 1.014 |

Seed 630602 is dominated by the `hmm_drive_0` second-mode chain (ratio 0.003)
and `accel_gp` (0.16).

Models that are gate-healthy in both arms and stable (12 of 17) have ratios
from 0.88 (`earnings`) to 1.16 (`kidiq`). They split 9 above 1.0 and 3 below.

## Anomalies

- **Passing cell with |z| = 5.07 on `sdgp_1`.** The delta2 `accel_gp` seed
  630604 cell passed every gate with R-hat 1.005 and min bulk ESS 996. It is
  also the 29× ratio. The default at the same seed failed its gates.
  `accel_gp` remains the model where passing gates do not guarantee accuracy.
- **`hmm_drive_0` second mode under delta2, seed 630602.** This is the same
  phenomenon WP52 and WP61 recorded under the default on other seeds. One seed
  of one arm says nothing about which delta hides modes more often.
- **Diamonds wall time.** Diamonds took 46 minutes of block A's 92, about
  6.7 M gradients per cell. Walls are contended and are not evidence.

## Files

- `PREREGISTRATION.md`, `protocol.json`: the frozen design.
- `src/main.rs`: the posteriordb harness, derived from v7.
- `src/bin/funnel.rs`: the WP53 funnel binary.
- `run_study.py`: the driver (`run`, `analyze`).
- `artifacts/cells/`: per-cell metrics.
- `artifacts/funnel/`: per-seed funnel output.
- `artifacts/run-log.txt`, `measured_on.json`, `summary.json`,
  `results-table.md`.
- `CHECKSUMS.sha256`. The checksums cover the uncommitted draws in
  `artifacts/draws/`, which are gitignored.
- Models (gitignored) are copied from `STUDIES/posteriordb_bench_v7/models`.
