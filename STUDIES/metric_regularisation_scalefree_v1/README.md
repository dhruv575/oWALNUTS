# metric_regularisation_scalefree_v1 — does shrinking toward the window's median variance beat Stan's regularisation? (WP41)

Status: preregistered decision study (`PREREGISTRATION.md`, `protocol.json`,
committed at `d83518dc` before the first evidence cell), executed
2026-10-24 on branch `wt/metric-regularisation`: 153 posteriordb cells
17:48–21:28 local in strict model / arm / seed order, then nine funnel cells
21:31. Every cell completed (`status: ok`); nothing was rerun. Kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` (unchanged). Per-cell
numbers: `artifacts/cells/`, `artifacts/summary.json`; full tables:
`artifacts/results-table.md`; hashes: `CHECKSUMS.sha256`. Walls were
measured on a 16-core machine shared with nine other agents and are
contended upper bounds; every number used below is a gradient count, an ESS,
an R-hat or a z.

## Verdict

**Not supported. Keep `DiagonalMetricRegularization::Stan`.** Neither
scale-free arm meets the frozen rule. The primary arm (`sfmed`, shrink toward
the median with Stan's weight) is at parity, **1.007x** the default per
gradient over 17 models. It fails C2 (`kidiq` 0.61x) and C4: the funnel has
`z = -3.02` on one seed. The secondary arm (`sfstan`, Stan's rule with the
unit replaced by the median) is at **0.949x** and fails C2 (centred eight
schools 0.51x, `arma11` 0.65x). It passes the funnel z gate but has 15, 4
and 1 retained funnel divergences where the default has 0, 0 and 0.

| criterion | `sfmed` (primary) | `sfstan` (secondary) | threshold |
|---|---|---|---|
| C1 geomean min-bulk-ESS/gradient vs `da`, 17 models | **1.007** | **0.949** | >= 1.10 |
| C2 lowest model ratio | **0.61** `kidiq` (also centred 0.76, `arma11` 0.76) | **0.51** centred eight schools (also `arma11` 0.65, `accel_gp` 0.76) | >= 0.85 |
| C3 cells passing all gates | 42 vs `da` 41 (held) | 42 vs 41 (held) | >= `da` |
| C4 funnel MCSE z per seed | -0.78, -1.28, **-3.02** | +0.72, +0.44, +1.13 (held) | \|z\| <= 2 |

What the study does establish is a mechanism, not a default:

1. **Stan's absolute prior still over-states small-scale posteriors by up
   to 12x.** On `sblrc` the five coefficient variances are ~1.0e-6. Stan's
   `9.9e-6` installs 9.8–11.9x the posterior variance, in every chain
   (`da` installed 1.07e-5..1.12e-5). Both scale-free rules install
   0.98–1.06x. The step goes from 0.10 to 0.33–0.36, and ESS per gradient
   rises **2.06x** (`sfmed`) and **1.61x** (`sfstan`) at 0.72x the
   gradients. `sblrc` goes from 2/3 to 3/3 gates and from 0.84x to 1.72x
   CmdStan's cited v5 figure. On `diamonds` Stan installs 4.27x on one
   coordinate and 1.2–1.6x on fourteen. Both scale-free arms install about
   1.0x, but ESS moves only 1.17x / 1.03x because `diamonds` is
   depth-capped at `h` ~0.0035 in every arm. WP27 said CmdStan's
   `1.07e-5` inverse metric on `sblrc` "is the posterior variance". It is
   in fact the Stan-regularised value of a ~1.0e-6 posterior variance, and
   CmdStan carries the same 11x over-statement.
2. **A median anchor is not scale-free *within* a model.** `kidiq`'s
   unconstrained variances are 33, 5.0, 0.0035 and 0.0012. The
   even-dimension median is about 2.5, so `sfmed` installs 0.026–0.029 on
   the two small coordinates, **7.9x and 21.6x** their posterior variance
   (predicted 7.6x and 22x). The step halves (0.097 to 0.047) and ESS per
   gradient falls to 0.61x. Any model whose coordinates split into two
   scale groups has this problem. A k = 5 shrink toward a central value
   amounts to `TowardUnit` with a different unit.
3. **Without an absolute floor, Stan's weight is effectively no
   regularisation at all**, and that costs robustness, not efficiency.
   `sfstan`'s anchor is ~1e-5 of the median. It matches `sfmed` on `sblrc`
   and `diamonds` and the default elsewhere. Where it differs, the warmup
   noise reaches the metric: it is the only arm with retained funnel
   divergences, and one `earnings` chain installs 3.6x on a coordinate.
   Its 17-model geomean is below 1.

The decision-relevant summary is this. The over-statement that the
scale-free rules remove is real, but it pays only on `sblrc`, and
`diamonds` is depth-capped anyway. `sfmed` gives the gain back on
two-scale models (`kidiq`). `sfstan` gives it back in seed noise, with
funnel divergences on top. Outside the five lottery and fail-everywhere
cells, the 12-model geomeans are 1.032 (`sfmed`) and 1.014 (`sfstan`).

## Arms (`src/arms.rs`; everything else is the shipped `sampler` default)

| arm | `DiagonalMetricRegularization` | installed variance (`m` = median of the window variances) |
|---|---|---|
| `da` | `Stan`, via `Adaptation::default()` | `(n/(n+5)) var_i + 1e-3 * 5/(n+5)` |
| `sfmed` | `ScaleFreeMedian` (new, opt-in) | `(n/(n+5)) var_i + (5/(n+5)) * m` |
| `sfstan` | `ScaleFreeStanMedian` (new, opt-in) | `(n/(n+5)) var_i + 1e-3 * (5/(n+5)) * m` |

Both new rules fall back to `m = 1` when the median is not finite and
positive. Unit test
`scale_free_metric_regularisations_match_the_formula_and_are_scale_free` in
`src/walnutpie.rs` checks the formula, exact scale covariance and the
fallbacks. `cargo test` (debug and release) is green with the kernel
fingerprints unchanged.

## Per model (seed medians; ratio = arm / `da` of min bulk ESS per gradient)

| model | gates da/sfmed/sfstan | da ESS/grad x1e3 | sfmed / da (per seed) | sfstan / da (per seed) | h da / sfmed / sfstan |
|---|---|---:|---|---|---|
| eight_schools noncentered | 3/3/3 | 30.0 | 1.03 (0.94, 1.03, 0.99) | 1.00 (1.07, 1.00, 0.80) | 0.49 / 0.47 / 0.46 |
| eight_schools centered | 0/0/0 | 0.435 | 0.76 (0.48, 0.49, 2.48) | 0.51 (0.46, 0.65, 1.66) | 0.20 / 0.16 / 0.20 |
| diamonds | 3/3/3 | 0.164 | 1.17 (1.30, 0.81, 1.26) | 1.03 (0.95, 0.77, 1.22) | 0.0033 / 0.0036 / 0.0034 |
| earnings | 3/3/3 | 0.677 | 0.98 (0.84, 0.96, 0.99) | 0.91 (0.80, 0.83, 0.93) | 0.015 / 0.016 / 0.015 |
| mesquite | 3/3/3 | 3.03 | 1.17 (1.13, 1.17, 1.19) | 1.24 (1.27, 1.24, 0.97) | 0.079 / 0.079 / 0.081 |
| kidiq | 3/3/3 | 4.08 | **0.61** (0.62, 0.56, 0.54) | 0.96 (0.90, 0.88, 1.15) | 0.097 / **0.047** / 0.098 |
| sblrc | 2/3/3 | 5.51 | **2.06** (2.06, 1.83, 1.54) | **1.61** (1.43, 1.75, 1.76) | 0.10 / **0.36** / **0.33** |
| nes2000 | 3/3/3 | 4.16 | 1.02 (0.86, 0.99, 1.03) | 1.05 (0.76, 1.05, 1.07) | 0.082 / 0.078 / 0.075 |
| arK | 3/3/3 | 8.84 | 1.00 (1.02, 0.82, 1.01) | 0.95 (0.95, 0.91, 0.94) | 0.11 / 0.12 / 0.12 |
| arma11 | 3/3/3 | 18.5 | 0.76 (0.76, 1.14, 1.30) | 0.65 (0.65, 1.13, 1.21) | 0.72 / 0.67 / 0.69 |
| garch11 | 3/3/3 | 18.4 | 0.90 (1.12, 0.93, 0.78) | 0.96 (1.10, 0.98, 0.83) | 0.31 / 0.34 / 0.32 |
| gp_pois_regr | 2/3/3 | 0.639 | 1.19 (1.19, 1.18, 1.77) | 1.18 (1.19, 1.08, 1.63) | 0.026 / 0.027 / 0.026 |
| hmm_example | 3/3/3 | 18.4 | 1.01 (1.01, 1.04, 1.06) | 0.88 (0.76, 1.05, 1.06) | 0.31 / 0.28 / 0.32 |
| hmm_drive_0 | 3/3/3 | 34.8 | 1.15 (1.04, 1.12, 1.71) | 1.05 (0.95, 0.86, 1.33) | 0.62 / 0.60 / 0.61 |
| one_comp | 2/1/1 | 11.4 | 0.98 (0.55, 0.98, 1.48) | 0.96 (0.84, 0.96, 0.70) | 0.37 / 0.39 / 0.40 |
| lotka_volterra | 2/2/2 | 2.71 | 1.05 (9.79, 1.09, 0.90) | 0.90 (17.5, 0.90, 1.02) | 0.098 / 0.11 / 0.11 |
| accel_gp | 0/0/0 | 0.150 | 0.86 (0.18, 1.25, 1.28) | 0.76 (0.71, 0.74, 1.76) | 0.0081 / 0.0081 / 0.0091 |

Reading the C2 failures. `kidiq` under `sfmed` is mechanistic: all three
seeds sit at 0.54–0.62. The other three are seed-lottery cells under the
house "ratio of seed medians" statistic:

- **`arma11`**: the per-seed ratios are 0.76, 1.14, 1.30 for `sfmed` and
  0.65, 1.13, 1.21 for `sfstan`. Gradients per cell range 55k to 385k with
  the warmup slide from the uniform start, and on seed 4101001 one chain per
  scale-free arm ends warmup at `h` 0.22 / 0.066 while its siblings are at
  0.7.
- **Centred eight schools** fails every gate in every arm.
- **`accel_gp`** fails every gate in every arm.

No carve-out is applied. Gates: `sfmed` and `sfstan` gain `sblrc` 4101001
(R-hat 1.012 under `da`) and `gp_pois_regr`, and lose `one_comp` (2/3 to
1/3).

## Installed metric (the mechanism; `artifacts/results-table.md` has every coordinate)

Installed variance (1 / mass) over the variance of the same cell's retained
unconstrained draws, median over 12 chains, min..max over coordinates:

| model | `da` | `sfmed` | `sfstan` |
|---|---|---|---|
| sblrc (6) | 0.98..**11.9** | 0.97..1.06 | 0.98..1.00 |
| diamonds (26) | 0.99..**4.27** | 0.95..1.08 | 0.90..1.07 |
| kidiq (4) | 0.94..1.06 | 1.03..**21.6** | 0.96..1.03 |
| earnings (5) | 1.02..1.10 | 0.93..1.07 | 0.92..0.98 |
| nes2000 (10) | 0.94..1.06 | 0.93..1.54 | 0.91..1.09 |
| arK (7) | 0.92..1.03 | 0.96..1.38 | 0.88..1.02 |
| gp_pois_regr (13) | 0.79..1.12 | 1.00..1.38 | 0.85..1.10 |

These match the pre-freeze computation from the reference draws
(`artifacts/prediction-scales.json`) to within seed noise on every
coordinate. `earnings` no longer has a measurement problem under
`MomentumSum`. On `earnings`, every coordinate in every `da` and `sfmed` chain is within
0.78–1.79x of its posterior variance. No coordinate is installed at the
anchor alone, which is the WP31 failure, so the "unmeasured coordinate"
case did not arise on this screen.

## Funnel (`P(omega < -5)`, exact 0.0478; 4 x 2,000 / 20,000 per seed)

| arm | z per seed (MCSE; batch-means) | omega bulk ESS / R-hat | retained divergences | retained exhaustions | target calls (3 seeds) |
|---|---|---|---|---|---:|
| `da` | -0.20, -0.59, -0.54 (-0.23, -0.71, -0.60) | 342/1.014, 362/1.015, 578/1.006 | 0, 0, 0 | 2, 35, 18 | 13.3M |
| `sfmed` | -0.78, -1.28, **-3.02** (-0.83, -1.37, -3.65) | 554/1.008, 564/1.008, 465/1.006 | 0, 2, 0 | 2, 30, 1 | 14.6M |
| `sfstan` | +0.72, +0.44, +1.13 (+0.80, +0.52, +1.65) | 447/1.014, 315/1.016, 277/1.019 | **15, 4, 1** | 100, 51, 7 | 15.8M |

The `sfmed` 4101003 failure is the WP28 per-chain step mode. Two chains
end warmup at `h` 0.0086 and 0.018 with 219 and 188 depth caps, and the
first spends its run outside the neck (its own tail fraction is 0.006). The
default shows the same mode on 4101001 (one chain at `h` 0.0082, 86 caps)
without leaving the gate. The installed funnel metrics barely differ
between arms. The median anchor adds `(5/505) * m` ≈ 0.1–2 to an `omega`
variance of 5–9, so three seeds cannot separate "the arm moves the
lottery" from "the arm causes the mode". Under the frozen rule it is a
failure either way.

## Predictions

| | prediction | result |
|---|---|---|
| P1 | `sfmed` geomean 1.00 (0.88–1.10), fails C1 | **held**: 1.007 |
| P2 | `sfmed` `kidiq` 0.5x (0.3–0.8), installed/posterior 7.6x and 22x, fails C2 | **held**: 0.61x; 7.9x and 21.6x |
| P3 | `sblrc` `da` installed/posterior >= 5x, scale-free 0.8–1.3x, ratio 2.5x (1.5–4) both arms, `h` >= 1.5x | **held**: 9.8–11.9x vs 0.97–1.06x; 2.06x and 1.61x; `h` 3.4x and 3.2x |
| P4 | `sfstan` geomean 1.065 (0.98–1.15); `kidiq`, `earnings`, `arma11`, `arK`, `nes2000` within 0.85–1.15 | **failed**: 0.949; `arma11` 0.65 (seed lottery, see above) |
| P5 | `diamonds`: `da` up to 4.2x, scale-free ~1.0–1.1x, ratio 1.1x (0.85–1.5) | **held**: 4.27x vs 0.90–1.08x; 1.17x and 1.03x |
| P6 | `sfmed` `nes2000` 0.9, `arK` 0.9, `hmm_example` 0.95, other healthy models within 0.85–1.1 | **partly**: 1.02, 1.00, 1.01 inside their intervals; `mesquite` 1.17, `gp_pois_regr` 1.19, `arma11` 0.76 outside the band |
| P7 | `earnings` >= 2/3 gates under both arms; every coordinate within 0.5–2x in every chain | **half**: 3/3 and 3/3; `sfmed` 0.79–1.67 held; `sfstan` one chain at 3.6x |
| P8 | funnel \|z\| <= 2 on every seed for all arms | **failed**: `sfmed` 4101003 z -3.02 |
| P9 | cells passing `da` 42 +- 4, `sfmed` da-3..da+1, `sfstan` da +- 2 | **held**: 41, 42, 42 |
| P10 | no arm meets the rule; keep `Stan` | **held** |

## Recommendation

- Keep `sampler::DEFAULT_METRIC_REGULARIZATION = Stan`. Ship
  `ScaleFreeMedian` and `ScaleFreeStanMedian` as opt-in variants, documented
  with this study as the warning. `ScaleFreeMedian` is the right choice
  only when every coordinate sits at a common small scale, as in `sblrc`
  (a regression with standardised-away tiny coefficients), where it is
  2.1x. It is wrong for two-scale targets such as `kidiq`.
- The finding worth carrying forward is item 1 of the verdict: Stan's
  `1e-3 * 5/(n+5)` term over-states posterior variances below ~1e-5. A rule
  that kept an absolute floor but sized it to the scale of the *smallest*
  well-measured coordinates (for example `min(1e-3, c * m_low)`) would keep
  `sblrc`'s 2x without `kidiq`'s loss. It is a new hypothesis and would
  need its own preregistration.
- Wiki: the WP27 open question in `wiki/findings/mass-metric.md` is closed.
  Also correct the statement that CmdStan's `1.07e-5` on `sblrc` is the
  posterior variance.

## Reproduce

```bash
cd STUDIES/metric_regularisation_scalefree_v1
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb.git posteriordb
git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release --locked
.venv/Scripts/python.exe run_scalefree.py build
.venv/Scripts/python.exe predict_scales.py      # pre-freeze input, not evidence
.venv/Scripts/python.exe run_scalefree.py run
.venv/Scripts/python.exe run_scalefree.py checks
.venv/Scripts/python.exe run_scalefree.py analyze
.venv/Scripts/python.exe checksums.py
```

Raw draws (`artifacts/draws/*.npz`, 102 MB) are checksummed but not
committed. Cell metrics with the installed metric per chain and window,
logs, the summary and the tables are committed.
