# posteriordb benchmark v5 — the post-hoc default change validated against CmdStan and nutpie on fresh seeds (WP32)

Status: preregistered validation (`PREREGISTRATION.md`, `protocol.json`,
committed at `b72af28` before the first evidence cell; the default change
itself is the parent commit `d2b9733`, labelled "DEFAULT CHANGE (post-hoc
after WP31)"), executed 2026-09-03 14:32–15:02 local on kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` with the flipped
`sampler` defaults: `Tuning::default()` with `UTurnRule::MomentumSum`
(`DEFAULT_U_TURN_RULE`), `Adaptation::default()` with
`DiagonalMetricRegularization::Stan` (`DEFAULT_METRIC_REGULARIZATION`),
plus the unchanged `h0 0.5`, depth 10, eight refinement levels, `delta 1`,
WP24 warmup exhaustion rule, adapted diagonal metric, cached initial
evaluation. All 153 cells (17 posteriors x 3 arms x seeds 87101–87103) and
the three funnel cells are present; every failure is a cell. Per-cell
numbers: `artifacts/summary.json`; tables: `artifacts/results-table.md`;
hashes: `CHECKSUMS.sha256`. Driver `run_posteriordb.py`, harness
`src/main.rs`, funnel `src/bin/funnel.rs`.

**What this study is.** `STUDIES/joint_default_v1` (WP31) preregistered a
flip rule for exactly this pair and did not meet it (C2, the per-model
floor, failed on `hmm_drive_0`'s arm-dependent second-mode draw and on the
centered eight schools, which no arm passes) while meeting the other four
criteria with margin. The flip was then decided **post hoc**, outside any
preregistered rule, and this run is the fresh-seed check against CmdStan
2.39.0 and nutpie 0.16.8 that the decision was made without. It measures
the decision; it does not make it. Protocol: `posteriordb_bench_v3`
verbatim (17 posteriors at `28f8d3d`, 4 x 1,000/1,000, gates rank R-hat <=
1.01, bulk and tail ESS >= 400 on every reference parameter, zero sampling
divergences, ArviZ 0.23.4 estimators, `Init::uniform()` starts, strictly
sequential run order), with the compiled models copied from the
`wt/posteriordb-v4` worktree (same toolchain and flags, no `STAN_THREADS`;
`accel_gp` compiled here).

## Verdict

**All five preregistered predictions held.** On the new defaults oWALNUTS
passes **42 of 51** cells against CmdStan's 36 and nutpie's 28 on the same
seeds (v3 on the old defaults: 35 / 37 / 31); it is at **0.82x CmdStan's
minimum bulk ESS per gradient** over the 16 models where CmdStan is
healthy (geometric mean of seed medians; v3: 0.34x over 17), and **1.07x
over all 17** because CmdStan and nutpie each lose two of three `arma11`
seeds to a chain that never leaves its start (WP27's crawl start; both are
at 0.2–0.3 x1e-3 ESS/gradient there against oWALNUTS's 14.3, a 71x ratio
that carries the geomean). Wall per gradient is 0.80x CmdStan's, ESS per
second 1.40x CmdStan's and **3.09x nutpie's**. The funnel tail mass at the
defaults is exact on every seed (z +1.02, −0.05, +0.93, zero divergences).
On the DA arm no model regressed below 0.8x its v3 value; ten are above
1.2x. The competitors' own v5/v3 ratios are the seed-noise control: CmdStan
0.65x (driven by `arma11` 0.003x and the centered eight schools 0.28x —
both bad-draw cells; 0.90–1.19x on the other fifteen), nutpie 0.74x.

| | prediction | value | held |
|---|---|---|---|
| P1 | DA passes >= 39 of 51 cells | **42** (CmdStan 36, nutpie 28) | yes |
| P2 | geomean min-bulk-ESS/gradient vs CmdStan >= 0.45 over 17 | **1.069** (0.822 without `arma11`) | yes |
| P3 | geomean min-bulk-ESS/s vs nutpie >= 1.5 | **3.085** (16 models) | yes |
| P4 | geomean wall per gradient <= 1.0x CmdStan | **0.801** | yes |
| P5 | funnel at the defaults \|z\| <= 2 on every seed | +1.02, −0.05, +0.93 | yes |

## Headline (cells passing all gates / geometric mean of seed-median ratios)

| arm | cells passing | models 3/3 | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie | wall/grad vs nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-da (new defaults) | **42**/51 | **12** | **1.069** (17 models; 0.822 without `arma11`) | 1.401 | **0.801** | 0.841 (16) | **3.085** | 0.273 |
| cmdstan 2.39.0 | 36/51 | 10 | 1 | 1 | 1 | — | — | — |
| nutpie 0.16.8 | 28/51 | 8 | — | — | — | 1 | 1 | 1 |

v3 (old defaults, seeds 79101–79103) for comparison: owalnuts-da 35/51,
0.344x CmdStan per gradient, 0.492x per second, 0.751x wall per gradient,
1.350x nutpie per second; cmdstan 37/51; nutpie 31/51. The DA arm's v5/v3
geomean is **2.01x** per gradient (WP31 measured the pair at 1.51x on
seed-paired starts; the extra here is the `hmm_drive_0` and `sblrc` cells
that v3's seeds drew badly) at 1.02x the gradients and 2.31x the ESS per
second.

## Per model (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3 for DA / CmdStan / nutpie; ESS/grad = min bulk
ESS per target call x1e3 (warmup included). Ratios are DA / competitor;
`v5/v3` is the DA arm against its own v3 median. Full rows (walls, ESS/s,
tail ESS, divergences, max |z|) and per-seed final steps and depth caps:
`artifacts/results-table.md`.

| model | gates DA / CS / NP | DA ESS/grad | vs CmdStan | vs nutpie | ESS/s vs CmdStan | ESS/s vs nutpie | DA v5/v3 |
|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools noncentered | 3 / 3 / 0 | 24.7 | 0.75 | 0.58 | 3.99 | 3.95 | 0.85 |
| eight_schools centered | 0 / 0 / 0 | 0.349 | 1.18 | 0.34 | 5.53 | 1.90 | 1.51 |
| diamonds | 3 / 3 / 0 | 0.191 | 0.84 | 1.18 | 0.85 | 1.30 | 1.23 |
| earnings | 3 / 3 / 3 | 0.582 | 0.67 | 0.61 | 0.64 | 0.71 | **3.28** |
| mesquite | 3 / 3 / 3 | 3.60 | 0.90 | 0.85 | 1.08 | 2.65 | 1.19 |
| kidiq | 3 / 3 / 3 | 3.73 | 0.92 | 0.60 | 0.92 | 1.00 | **1.73** |
| sblrc | 3 / 2 / 3 | 5.75 | 0.87 | 0.37 | 2.29 | 1.38 | **13.9** |
| nes2000 | 3 / 3 / 3 | 4.24 | 0.85 | 0.72 | 0.85 | 0.89 | **1.70** |
| arK | 3 / 3 / 3 | 8.74 | 0.81 | 0.76 | 1.06 | 8.07 | 1.13 |
| arma11 | **3 / 1 / 1** | 14.3 | 71.1 | 51.4 | 52.1 | 341 | 1.02 |
| garch11 | 3 / 3 / 3 | 19.2 | 0.86 | 0.75 | 1.26 | 6.88 | 1.28 |
| gp_pois_regr | **3 / 0 / 0** | 0.751 | 0.75 | 1.54 | 0.72 | 2.82 | 1.03 |
| hmm_example | 3 / 3 / 3 | 15.5 | 0.73 | 0.55 | 0.81 | 8.58 | **1.59** |
| hmm_drive_0 | 2 / 2 / 3 | 37.6 | 0.94 | 0.40 | 0.95 | 1.95 | 134 |
| one_comp_mm_elim_abs | 1 / 1 / 0 | 10.1 | 0.95 | 0.46 | 1.04 | 1.73 | 1.12 |
| lotka_volterra | 3 / 3 / crash | 3.14 | 0.88 | — | 0.87 | — | 0.95 |
| accel_gp (66-d) | 0 / 0 / 0 | 0.118 | 0.47 | 0.71 | 0.38 | 1.93 | 1.71 |

Reading the table:

* **The regressions the old defaults lost are back.** `sblrc` 0/3 -> 3/3
  (step 0.003 -> 0.10–0.12, CmdStan's; the installed maximum mass is 9.2e4
  on every chain, i.e. the window measured the stiff coefficient), `earnings`
  3.3x per gradient at 0.31x the gradients with zero depth caps (installed
  mass 4.6e3–7.3e3, CmdStan's 1.6e-4 inverse metric), `kidiq` 1.7x,
  `nes2000` 1.7x, `hmm_example` 1.6x at 0.72x the gradients, `garch11`
  1.3x, `diamonds` 1.2x (still capped at depth 10 on 246–539 transitions
  per seed at `h` 0.003–0.005). On the healthy regressions the DA arm is
  now 0.67x (`earnings`), 0.92x (`kidiq`), 0.87x (`sblrc`), 0.85x
  (`nes2000`), 0.90x (`mesquite`) of CmdStan per gradient, against
  0.22 / 0.47 / 0.09 / 0.58 / 0.88 on the old defaults in v3.
* **Where oWALNUTS wins outright** (gates >= the competitor's, higher ESS
  per gradient and per second): against CmdStan on `arma11` (3/3 vs 1/3:
  CmdStan's 87101 and 87102 each carry a chain that never left its start —
  step size 0, min bulk ESS 7, R-hat 1.5; WP27 showed CmdStan cannot leave
  that start either) and the centered eight schools (both 0/3; oWALNUTS
  more ESS per gradient and per second with zero divergences against
  CmdStan's 43–280); against nutpie on `diamonds` (3/3 vs 0/3),
  `arma11` (nutpie's 87101/87102 stuck the same way, 477–515 divergences)
  and `gp_pois_regr` (3/3 vs 0/3, nutpie 142–755 divergences). Gate wins
  without a throughput win: the noncentered eight schools (3/3; nutpie
  0/3 with 1–3 divergences per seed; CmdStan 3/3 here, 2/3 in v3),
  `gp_pois_regr` against CmdStan (3/3 vs 0/3, CmdStan 6–22 divergences),
  `sblrc` against CmdStan (3/3 vs 2/3, one CmdStan seed at R-hat 1.010),
  `one_comp` against nutpie (1/3 vs 0/3). ESS per second is above
  CmdStan's on 8 of 17 models and above nutpie's on 14 of 16.
* **Where CmdStan is still ahead per gradient**: every healthy model, by
  0.67–0.95x (`earnings` 0.67, `hmm_example` 0.73, `gp_pois_regr` 0.75,
  noncentered eight schools 0.75, `arK` 0.81, `diamonds` 0.84, `nes2000`
  0.85, `garch11` 0.86, `sblrc` 0.87, `lotka_volterra` 0.88, `mesquite`
  0.90, `kidiq` 0.92, `hmm_drive_0` 0.94, `one_comp` 0.95), and `accel_gp`
  0.47 (fails everywhere; CmdStan at 37–80 divergences per seed). The
  residual is the WP30 decomposition: refinement's reverse-coarser stops
  and the remaining orbit-length gap. The all-17 geomean of 1.07 is not a
  per-gradient win on ordinary posteriors — it is `arma11`. Read 0.82x.
* **`hmm_drive_0`** drew one second-mode chain on 87102 (min bulk ESS 10,
  R-hat 1.35, no divergences; the other seeds pass at 4,000+ ESS); CmdStan
  drew one on 87101 (R-hat 1.22, 414 divergences); nutpie none. The mode
  lottery is a start property, as WP31 said, and it hit each NUTS
  implementation once here. **The centered eight schools** fails every arm
  on every seed (oWALNUTS min bulk ESS 63–133 at R-hat 1.03–1.06 with zero
  divergences; CmdStan 21–56 at 43–280 divergences; nutpie 6–168 at 13–175).
  **`one_comp`** is one seed each for oWALNUTS and CmdStan (oWALNUTS 87102
  R-hat 1.011, 87103 min bulk ESS 510 with tail 364; CmdStan 87101 R-hat
  1.11 with 146 divergences); nutpie 0/3 with 1–18 divergences and a max
  |z| of 6.7 on one seed. **nutpie on `lotka_volterra`** panics inside its
  own sampler on every seed ("Failed to constrain the parameters of the
  draw"), exactly as in v3; the three cells are recorded as
  `timeout_or_crash` and the nutpie head-to-head is over 16 models.
* **No frozen chain, no oWALNUTS cell errored, no depth cap outside
  `diamonds` and one `accel_gp` transition, zero retained divergences on
  every oWALNUTS cell.** `lotka_volterra` drew no `rk45`-boundary start on
  these seeds (7–26 s per cell).

## Funnel tail mass `P(omega < -5)` (exact 0.0478) at the sampler defaults, 4 x 2,000 / 20,000 per seed

| seed | estimate | MCSE z (gate) | batch-means z | `omega` bulk ESS / R-hat | target calls | divergences | retained exhaustions | final steps |
|---|---:|---:|---:|---|---:|---:|---:|---|
| 87101 | 0.0571 | +1.02 | +1.08 | 571 / 1.005 | 4,049,144 | 0 | 0 | 0.107, 0.048, 0.098, 0.146 |
| 87102 | 0.0474 | −0.05 | −0.05 | 639 / 1.006 | 3,466,793 | 0 | 7 | 0.065, 0.114, 0.073, 0.187 |
| 87103 | 0.0578 | +0.93 | +1.11 | 274 / 1.010 | 9,072,925 | 0 | 6 | 0.0013, 0.022, 0.044, 0.135 |
| pooled (batch means) | 0.0541 | — | +1.34 | | | | | |

P5 holds; the WP28 caveat stands in its WP31 form: 87103 adapted one chain
to `h` 0.0013 (933 depth caps, 2.2x the calls of the other seeds), so the
defaults are unbiased on the funnel, not efficient there. WP31's three
`joint` seeds at the defaults were −0.06, +0.81, −1.16.

## What this establishes

1. The post-hoc default change is validated on fresh seeds: every
   preregistered prediction held, the gate count is the highest of any
   oWALNUTS arm in any posteriordb study (42; WP31's joint arm 41 on its
   seeds) and above both competitors on the same seeds, ESS per second is
   above CmdStan's (1.40x) and nutpie's (3.09x), and the funnel is exact.
2. The per-gradient gap to CmdStan on ordinary posteriors is now
   0.67–0.95x per model (geomean 0.82x over the 16 CmdStan-healthy models),
   from 0.34x in v3. It is not closed: the remaining factor is the kernel
   (WP30), not warmup.
3. The all-17 geomean of 1.07x is an `arma11` artefact — CmdStan and
   nutpie each drew the crawl start on two seeds — and the release notes
   cite it with the 0.82x next to it, as the preregistration required for
   the honest figure.

## Deviations and caveats

* None in the run: one continuous strictly sequential pass (14:32–15:02),
  then the funnel row; no restart; no cell errored on the oWALNUTS side.
* The nutpie `lotka_volterra` crash is nutpie's, reproduced from v3.
* Walls: the machine was otherwise idle apart from the driver itself; the
  v3 walls were taken on a shared machine, so v5/v3 ESS-per-second ratios
  for all three arms (2.31 / 0.81 / 1.04) mix seed draws and load and are
  reported, not interpreted.
* Compiled models, venv, posteriordb checkout, raw draws and CmdStan CSVs
  are not committed (`.gitignore`); raw draws are hashed in
  `CHECKSUMS.sha256`. The BridgeStan `.so` and CmdStan executables for
  sixteen models are byte copies of the `wt/posteriordb-v4` builds
  (BridgeStan 2.9.0 / Stan 2.39.0 / CmdStan 2.39.0, no `STAN_THREADS`);
  `accel_gp` was compiled here with the same flags.
* Before freezing, the harness was smoke-tested on the noncentered eight
  schools with seed 1 (recorded options `MomentumSum` / `Stan` verified in
  the JSON) and the funnel binary with seed 1, both to scratch paths
  (deleted).

## Reproduce

```
cd STUDIES/posteriordb_bench_v5
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 cmdstanpy==1.3.0 nutpie==0.16.8 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py run      # 153 cells, ~30 min; compiles missing models; resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py checks                    # funnel row, ~3 s
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py analyze
.venv/Scripts/python checksums.py
```
