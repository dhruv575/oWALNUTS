# WP51 — dense-default confirmation (`dense_metric_confirmation_v1`)

## Verdict

**Not supported: the frozen flip rule fails, so the dense facade keeps its
current warmup defaults and the three WP48 fixes stay opt-in.** The
candidate (`PerTransition` seeding + `Stan` regularisation + symmetrised
precision) passes 40/51 gate cells against the diagonal default's 43/51 (the
rule needs >= 42), and `gp_pois_regr` drops from 3/3 to 0/3. It passes the
other two conditions with a wide margin: geomean **3.21x** the diagonal's
min-bulk-ESS per gradient over all 17 models (rule >= 1.5), and funnel z of
-1.03, -1.36 and +0.96.

The number that matters is **40 vs 43 gates**. On per-gradient efficiency
the candidate is far ahead of both the shipped dense path (0.055x the
diagonal, 12/51) and the diagonal (3.21x; `diamonds` 98.7x).

| condition (frozen) | value | holds |
|---|---|---|
| candidate / diag geomean >= 1.5 | 3.212 (17 models, none excluded) | yes |
| candidate gates >= diag gates - 1 | 40 vs 43 | **no** |
| funnel \|z\| <= 2 every seed | -1.03, -1.36, +0.96 | yes |
| no model 3/3 under diag and 0/3 under the candidate | `gp_pois_regr` 3/3 -> 0/3 | **no** |

No library code was changed. `Metric::dense()` still gives `Legacy` seeding,
`MeanVarianceShrinkage` and an unsymmetrised precision. The three opt-ins
remain available through `Adaptation::Custom(WarmupConfig::new(0.8)? ...)`,
as in WP48. This study makes no recommendation.

**Coordinator decision, made after this result and outside the frozen rule:**
the dense facade's `WarmupConfig` defaults were changed to the candidate
pipeline as an engineering decision. The basis was candidate versus the old
dense defaults (40/51 vs 12/51 gates, 3.21x vs 0.055x of the diagonal) and
the fact that two of the old behaviours are defects. The record above is
unchanged (see `CHANGELOG.md`, "Changed").

## What was tested

Preregistration: `PREREGISTRATION.md` and `protocol.json`, frozen and committed
at `3fe6e435` before the first evidence cell. The protocol SHA-256 is
`ebcc367e…5c4f` (also in `artifacts/summary.json`).

- 17 posteriordb models (`28f8d3d`, the v6/WP48 set) x 3 arms x seeds
  151301–151303. Each cell is 4 chains x 1,000/1,000 with 4 threads,
  `Tuning::default()`, `Init::uniform()` and `Limits::admit_worst_case()`.
  Gates are house: rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained
  divergences, no error. A cell times out at 2,700 s, and timeouts count as
  failures.
- Arms: `owalnuts-diag` (shipped default); `owalnuts-dense-legacy`
  (`Metric::dense()` with today's dense warmup defaults stated explicitly);
  `owalnuts-dense-candidate` (the same with `PerTransition` + `Stan` +
  `with_dense_symmetrized_precision(true)`). A non-evidence `funnel selfcheck`
  (seed 1) confirmed that `Metric::dense()` + `Adaptation::default()` on this
  library is bit-identical to `dense-legacy`.
- Order: phase 1 ran diag then candidate per model. The funnel followed (diag,
  candidate; 4 x 2,000/20,000, exact tail mass 0.0478). Phase 2 ran legacy and
  is reported only. Everything was strictly sequential, and nothing was rerun.
- Library: `main` at `3924b090`. The later `main` commit `d8c3cef3` (zeroing
  the BridgeStan gradient buffer on Windows direct replicas) does not affect
  the default owned-worker path these cells use.
- The BridgeStan libraries (`models/`, uncommitted) were copied from the WP48
  build of the same sources, `C:\dev\owalnuts-wt\dense-metric\...\models`. The
  posteriordb checkout is the sibling one in `posteriordb-breadth`, referenced
  read-only.

## Evidence (seed medians; full table `artifacts/results-table.md`)

Ratios are min-bulk-ESS per gradient against `owalnuts-diag`, and gates are out of 3.

| model | diag gates | candidate ratio (gates) | legacy ratio (gates) |
|---|---|---|---|
| eight_schools_noncentered | 3 | 0.92 (3) | 0.07 (1) |
| eight_schools_centered | 0 | 1.52 (0) | 0.01 (0) |
| **diamonds** | 3 | **98.67 (3)** | 0.40 (0) |
| earnings | 3 | 4.46 (3) | 0.01 (0) |
| mesquite | 3 | 15.31 (3) | 0.01 (1) |
| kidiq | 3 | 5.43 (3) | 0.00 (0) |
| sblrc | 3 | 0.93 (3) | 0.03 (0) |
| nes2000 | 3 | 15.51 (3) | 0.54 (2) |
| arK | 3 | 7.58 (3) | 1.15 (2) |
| arma11 | 3 | 1.01 (3) | 0.00 (1) |
| garch11 | 3 | 1.77 (3) | 0.30 (1) |
| **gp_pois_regr** | 3 | 1.73 (**0**) | 0.54 (2) |
| hmm_example | 3 | 2.28 (3) | 0.33 (2) |
| hmm_drive_0 | 3 | 1.07 (3) | 0.00 (0; 1 error) |
| one_comp | 1 | 1.88 (2) | 0.26 (0) |
| lotka_volterra | 2 (1 timeout) | 13.95 (2) | 0.04 (0) |
| accel_gp | 1 | 0.38 (0) | 0.04 (0) |
| **geomean / total** | **43** | **3.212 / 40** | **0.055 / 12** |

Where the candidate loses gates:

- **`gp_pois_regr` (3 -> 0).** The candidate is 1.73x per gradient, but it
  uses 0.33M gradients per run against the diagonal's 1.2M (step 0.15 vs
  0.03). At a fixed 1,000 draws it ends with min bulk ESS 341–433 and tail
  ESS 133–297, against 726–907 / 504–1,068. R-hat on `rho` is
  1.010–1.015. The failing parameter is the GP length-scale `rho` (and
  `alpha`), not a correlated linear block: the whitened `kappa` is 3–4 (diag
  ~550), so the metric is good and the hyperparameter mixes slowly anyway.
  WP48 saw the same model at 2/3 under `dense-stan` and the post-hoc stan-sym
  arm.
- **`accel_gp` (1 -> 0).** Diag passed seed 151303 (R-hat 1.0091, bulk
  784). The candidate is 0.38x per gradient, with R-hat 1.046–1.061 and bulk
  ESS 52–95 at `kappa` 20–30. This repeats WP48's post-hoc finding: a good
  linear metric does not fix `accel_gp`. WP48 measured 1.34x on other
  seeds; here it is 0.38x.
- **`one_comp` (1 -> 2)** is the candidate's only gain.
- `lotka_volterra`: diag seed 151302 timed out (counted as a failure), and
  candidate seed 151301 has one stuck chain (R-hat 1.59). Each arm has 2/3.

Mechanism on `diamonds`: diag step 0.0036, 10 % depth caps, `kappa` 2.7e5.
The candidate reaches step 0.278 with zero caps, `kappa` 17.6, no ridge and
no Cholesky failures. Legacy has step 0.013, 2.6 % caps, `kappa` 6.3e5,
24–41 failed factorisations per cell and a 0.01 ridge. These are WP48's
findings 4 and 6 again, on fresh seeds.

**Funnel**: diag z -0.30, -1.38, -0.35 with 0 divergences; candidate z
-1.03, -1.36, +0.96 with 0, 1 and 1 retained divergences (omega bulk ESS
601–639, R-hat <= 1.0124).

Walls are contended and decide nothing. The contended ESS/s geomean is
candidate 3.58x and legacy 0.073x.

## Predictions

| prediction | result |
|---|---|
| P1 candidate / diag geomean >= 2.0 | **held** (3.21) |
| P2 `diamonds` >= 20x | **held** (98.7x) |
| P3 `accel_gp` 0/3 in every arm | **failed** (diag 1/3: seed 151303 passed) |
| P4 candidate gates >= diag gates | **failed** (40 vs 43) |
| P5 candidate funnel \|z\| <= 2 and divergences <= 2x diag | **failed** on the divergence clause (z held on all seeds; candidate 2 vs diag 0 divergences) |
| P6 (secondary) legacy geomean <= 0.5 and gates < diag | **held** (0.055, 12 vs 43) |

## What follows

- **Decision under the frozen rule:** no flip. `src/walnutpie.rs`,
  `tests/kernel_fingerprint.rs` (it does not cover the dense facade) and the
  README are unchanged, and there is no CHANGELOG entry. `Metric::dense()`
  stays undocumented as a recommended setting.
- The negative is recorded in `wiki/negative-results.md`. The facts a later
  study would have to face: (a) the failure is a 3-gate deficit concentrated
  on two GP-hyperparameter posteriors, where the candidate needs fewer
  gradients per draw than the diagonal yet mixes the hyperparameter no better
  per draw; (b) on the other 12 models where diag passes 3/3, the candidate
  also passes 3/3 and is never below 0.92x.
- The shipped dense defaults are measured, once again, at 0.055x the diagonal
  with 12/51 gates (WP48: 0.082x, 17/51). They stay as they are under this
  rule.

## Deviations and anomalies

- None in the protocol: all 153 oWALNUTS cells and 6 funnel cells ran in the
  frozen order. Non-ok cells (not rerun): diag `lotka_volterra` 151302
  timed out (2,700 s; WP48 saw the same stall on another seed), and legacy
  `hmm_drive_0` 151302 errored ("kernel attempted a nonfinite target
  position (chain 3, transition 0)").
- Pre-freeze non-evidence work (seed 1): the selfcheck, one
  `eight_schools_noncentered` cell per arm and one candidate funnel cell, all
  written outside the study and discarded.
- The machine was less contended than in WP48 (`diamonds` diag 466–632 s vs
  648–1,119 s).

## Reproduce

```powershell
cd STUDIES/dense_metric_confirmation_v1
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
# copy <posterior>_model.so, .data.json, .stan of the 17 models into models/ (WP48 build)
$env:RUSTUP_TOOLCHAIN='1.88.0-x86_64-pc-windows-gnu'; cargo build --release
.\target\release\funnel.exe selfcheck
.venv\Scripts\python.exe run_confirm.py run
.venv\Scripts\python.exe run_confirm.py analyze
.venv\Scripts\python.exe checksums.py
```

Raw draws (`artifacts/draws/`) are uncommitted and checksummed.
