# adaptive_delta_v1 (WP49) — can `delta` be adapted from the observed leaf-error distribution?

**Verdict: not supported — `NO_ADAPTIVE_DELTA_RULE_QUALIFIES`.** Neither rule
meets the frozen rule. `r1` (inverse tail quantile) gets **1.016x** the
default over 17 models (rule: 1.10x), with the centered eight schools at
0.61x. `r2` (refined-fraction target) gets **0.885x**, with `accel_gp` at
0.19x. The warmup-window leaf-error tail does not pick out the models where
`delta = 2` hurts. `r1` fell back to `delta = 1` on the four models where
the fixed-2 control gained most (noncentered and centered eight schools,
`garch11`, `one_comp`). It left `accel_gp` at 1.45, because that model's
warmup-window q0.99 is only 1.25, against 3.9 in the retained-draw trace. No
default changes.

Preregistered in `PREREGISTRATION.md` / `protocol.json` (commit `4ab85bc3`,
before the first evidence cell). The 204 posteriordb cells (17 models x 4
arms x 3 seeds, 94901–94903), the 48 funnel cells (12 seeds) and the 12
Eight Schools cells (each run 3 times, every rerun bit-identical) are all
present. There were no process errors and no reruns.

## The change under test (library, opt-in)

`WarmupConfig::with_adaptive_delta(AdaptiveDeltaConfig)`, with
`AdaptiveDeltaRule::{InverseQuantile, QuantileScaled}`. At every slow-window
end, `delta` is set from a quantile of the level-0 endpoint energy errors of
every leaf attempted in that window. These errors come from a new kernel
telemetry field, `MacroLeafOutcome::level_zero_energy_error`, which only
records the value and changes no arithmetic. The rule is clamped. It is
deferred until a metric has been installed at an earlier boundary, a window
with fewer than 100 leaves is skipped, and `delta` is frozen for retained
draws. The per-chain, per-window trajectory is in
`RunTelemetry::adaptive_delta_updates` and in every cell
(`adaptive_delta_trajectory`). The defaults and fingerprints are unchanged,
and `cargo test --release` is green (`artifacts/cargo-test.log`).

| arm | delta |
|---|---|
| `da` | 1 (shipped default) |
| `d2` | fixed 2 (control; rerun of WP34 `da-d2`) |
| `r1` | `clamp(1.8 / q0.99(|dH0|), 1, 2)`; the scale is calibrated so a standard Gaussian lands at about 1.8 |
| `r2` | `clamp(q0.985(|dH0|), 0.5, 2)`: the fixed point of a controller that holds 1.5 % of leaves refined |

Before freezing I noted that both of the task's candidate forms *increase*
`delta` where the tail is heavier. R1 was therefore frozen in inverse form
and R2 was kept as written. That observation was confirmed: `r2` lands the
light-tailed models at 0.5–0.9 and the heavy/moderate ones near 2.

## Results (seed medians; min bulk ESS per gradient, warmup included; ratio to `da`)

| arm | gates /51 | geomean (17) | geomean (14 healthy) | worst model | funnel: \|z\|<=2 on study seeds | funnel: gross-safe on study seeds | Eight Schools (secondary) |
|---|---:|---:|---:|---|---|---|---:|
| `da` | 39 | 1.000 | 1.000 | — | **no** (94902: z −4.21) | no (1/3) | 1.000 |
| `d2` | 43 | **1.141** | 1.099 | diamonds 0.90 | yes | no (1/3; 9 and 1 divergences) | 0.970 |
| `r1` | 40 | 1.016 | 1.047 | centered eight schools 0.61 | no (94903: z −2.04) | no (1/3) | 0.907 |
| `r2` | 40 | 0.885 | 0.962 | accel_gp 0.19; also gp_pois_regr 0.60, earnings 0.74 | yes | no (2/3) | 0.912 |

Decision rule (C1 geomean >= 1.10, C2 no model < 0.85, C3 gates >= `da`, C4
funnel |z| <= 2 on every study seed, C5 funnel gross safety on every study
seed):

- `r1` fails C1, C2, C4 and C5.
- `r2` fails C1, C2 and C5.
- `d2`, the control, passes C1–C4 and fails only C5.

The default `da` fails C4 and C5 itself.

### Where delta landed (final `delta`, median over 12 chains; final-window quantile)

- **`r1`**
  - Light class: median 1.47 over models (1.35–1.69). Predicted 1.45–2.0; **held**.
  - Moderate class: 1.00. Predicted 1.0–1.5; **held**. Noncentered eight schools q0.99 6.8, `garch11` 2.2, `one_comp` 4.6, all at 1.00. The exception is `gp_pois_regr`, at 1.52 (q0.99 1.19).
  - Heavy class: 1.22. Predicted 1.0–1.1; **failed**. Centered eight schools q0.99 4.45, `delta` 1.00; `accel_gp` q0.99 **1.25**, `delta` **1.45**.
  - Funnel: 1.00. Predicted 1.0–1.5; held.
- **`r2`**
  - Light class: 0.87; `diamonds` and `earnings` sit at the 0.5 floor. Predicted 0.65–1.0; **held**.
  - Moderate class: 1.92. Predicted 1.0–2.0; held.
  - Heavy class: 1.28. Predicted 1.8–2.0; **failed**. `accel_gp` 0.56.
  - Funnel: 1.36. Predicted 1.2–2.0; held.

The informative failure is `accel_gp`. During warmup its leaf-error
distribution is light (q0.99 1.25, the same as `lotka_volterra` or `arK`). In
the WP34-style trace from retained draws it is the heaviest of the healthy
models (q0.99 3.9, `P(|dH| > 1)` 8 %). The heavy tail appears only once the
chains are in the typical set at the final step. A warmup-window statistic
therefore cannot see it. The moderate models whose tail *is* visible in
warmup (noncentered eight schools, `garch11`, `one_comp`) are the ones where
`delta = 2` helped or was neutral (1.20, 1.03, 0.99 under `d2`). So `r1`'s
fallback fires where it costs and stays off where it was meant to protect.

### Prediction scorecard (from `protocol.json`; mechanical)

- **Held (11 of 16 mechanical predictions):**
  - P1 `r1` light, moderate and funnel; `r2` light, moderate and funnel.
  - P2 `r1` geomean 1.016, in 1.00–1.08.
  - P2 `r2` 0.885, in 0.85–1.00.
  - P3 `r1` `accel_gp` 1.07, in 0.85–1.15.
  - P4: neither candidate meets the rule (two predictions).
- **Failed (5), plus the unscored P5:**
  - P1 `r1` heavy (1.22) and `r2` heavy (1.28).
  - P2 `d2` geomean 1.141, above the predicted 1.00–1.10.
  - P3 `d2` `accel_gp` 1.83 (predicted 0.55–0.90).
  - P3 `r2` `accel_gp` 0.19, below 0.55–0.90.
  - P5 is not mechanically scored. Its `r1` part (|z| <= 2 on the study seeds) failed narrowly (−2.04 on 94903). Its `d2`/`r2` divergence-spread part held for `d2` only: `d2` was divergence-free on 4/12 seeds against `da`'s 5/12, while `r2` was divergence-free on 7/12, more than `da`.

## The fixed-2 control on fresh seeds

`d2` is 1.141x with no model below 0.85, and `accel_gp` is **1.83x** (WP34:
0.68x). That reversal is seed noise, not a new effect:

- The `accel_gp` per-seed ratios are 1.45, 16.4 and 0.98: `da` seed 94902 had
  min bulk ESS 28.
- `hmm_drive_0` per-seed ratios are 0.72, 76.9 and 2.35: one `da` seed drew
  the second mode.
- Excluding those two models, `d2` is 1.067x, the same as WP34's 1.070x.

The WP34 `accel_gp` clause that disqualified fixed 2 is therefore itself a
3-seed lottery on a model that fails its gates in every arm (`da` 0/3, `d2`
2/3).

Fixed 2's real liability is the funnel. On the 12 seeds:

- Pooled accuracy is unchanged (P(<−5) 0.0452 vs 0.0451, P(<−6) 0.0209 vs 0.0215).
- |z| <= 2 on 12/12 seeds, against 11/12 for `da`.
- Retained divergences: **34** against 11, and only 4/12 divergence-free seeds against 5/12. This is the same signal as WP37A.

## Funnel (sampler defaults + arm rule; 4 x 2,000 / 20,000; 12 seeds; decisive on the first three)

| arm | \|z\|<=2 | gross-safe | divergence-free | WP37A-F4 healthy | divergences | exhaustions | pooled P(<−5) | target calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `da` | 11/12 | 5/12 | 5/12 | 0/12 | 11 | 234 | 0.0451 | 56.0 M |
| `d2` | 12/12 | 4/12 | 4/12 | 2/12 | 34 | 126 | 0.0452 | 67.0 M |
| `r1` | 10/12 | 8/12 | 8/12 | 2/12 | 4 | 137 | 0.0457 | 49.4 M |
| `r2` | 12/12 | 6/12 | 7/12 | 0/12 | 10 | 162 | 0.0497 | 56.8 M |

On the funnel `r1` stays at about 1 and is the safest arm descriptively: 4
divergences, 8/12 seeds gross-safe, and the fewest calls. But two of its 12
seeds have |z| > 2 (−2.04, −3.15), and `da` itself has one (−4.21). Per-seed
gross safety on all of three seeds is a bar the shipped default does not
clear (as in WP37A, where fixed 1 had divergences on 4/12 seeds). C5 is
therefore an extremely strict gate for any arm.

## Eight Schools strict track (secondary)

All 12 cells were healthy and all repetitions bit-identical. Relative to
`da`: `d2` 0.970x, `r1` 0.907x (`delta` 2 at target 0.95, because the tail is
light at the smaller step), `r2` 0.912x (`delta` 0.5).

## What this means

- A warmup-time quantile of the leaf-error distribution is the wrong
  instrument for choosing `delta` per target. The tail that matters for
  `accel_gp` is not present in warmup. Where the tail is visible, refinement
  at `delta = 1` was not worth its cost.
- The controller form (R2) does the opposite of what is wanted, by
  construction.
- Open-question item 4 can be closed as a warmup-statistic line. If `delta`
  is revisited, the evidence points at fixed 2 as the target, judged against
  a funnel safety criterion that the default itself can pass. Examples are
  pooled accuracy plus total divergences, not per-seed zero divergences.
  Seed-pathology-robust efficiency (more seeds on `accel_gp` and
  `hmm_drive_0`) is also needed, rather than another adaptive rule.

## Caveats

- Walls are contended (ten agents on 16 cores; `diamonds` cells took
  550–1,400 s against about 90 s uncontended). The evidence is gradients,
  ESS, R-hat and z.
- Pre-freeze smoke tests on non-evidence seed 5 (funnel `r1`/`r2`, one
  posteriordb cell) informed the funnel prediction only. They are disclosed
  in the preregistration.
- Raw posteriordb draws (`artifacts/draws/`) and the Eight Schools cell
  files with samples (`artifacts/eight_schools/`, 15 MB) are checksummed but
  not committed.

## Reproduce

```bash
cd STUDIES/adaptive_delta_v1
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb.git posteriordb && git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
PATH="$PATH:$HOME/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/tbb" .venv/Scripts/python.exe run_study.py run
.venv/Scripts/python.exe run_study.py checks
.venv/Scripts/python.exe run_study.py analyze
.venv/Scripts/python.exe checksums.py
```

Full tables: `artifacts/results-table.md`. Machine-readable:
`artifacts/summary.json`. Per-cell metrics, including the delta trajectories:
`artifacts/cells/`. Funnel cells: `artifacts/funnel/`. Logs:
`artifacts/{run-log,run-log.err,checks-log,analyze-log}.txt`. Gaussian
calibration: `artifacts/calibration.log`.
