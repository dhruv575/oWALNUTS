# warmup_gap_diag_v1 (WP40-WARMUP-GAP) — where the per-gradient gap to CmdStan on smooth models comes from, and four warmup levers that do not close it

Instrumentation study, **not preregistered**, run 2026-09-05 on `main`
(baseline `53a4ef2`, the WP39B result). It is a diagnosis plus an exploratory
sweep of research-only warmup options; nothing here qualifies a default
change and no seed used here may be reused by a later decision study.

## Question

After WP39B closed the reverse-coarsening line, the remaining gap on
CmdStan-healthy posteriordb models was: sampling-only ESS per gradient
0.95x CmdStan, warmup-included 0.735x. Where do the extra gradients go, and
does any warmup-side change recover them?

## Diagnosis (per-transition warmup telemetry, `src/main.rs`, 17 models x 4 chains x 1,000/1,000, seed 92101)

- Warmup gradients are **1.56x CmdStan's** on the 14 healthy models, against
  sampling gradients per effective sample of about 1.05x. Warmup is the gap.
- Per window, pooled: the initial fast phase (75 transitions) is **2.07x**
  CmdStan (24 % of the excess); the slow mass windows are 1.14–1.27x (kernel
  level: 5–8 % more leaves per transition and an 8 % smaller adapted step);
  the terminal fast window is 1.01x.
- **Step-crash mechanism.** A single-leaf orbit that ends in a
  reverse-coarser rejection feeds dual averaging a statistic of 0.02–0.36
  (the mean of `exp(-|dH|)` over the coarsest attempt of one leaf), which
  cuts the step 3–10x in one iteration; recovery takes 5–10 depth-10 orbits
  of 1,023 gradients each. The `crash` column in the tables counts these per
  chain: 21–46 per chain on every model under the shipped defaults.
- **Initial-phase pathology.** From `h0 = 0.5` with an identity metric,
  dual averaging's first iterates climb to `h` of 1–6 because fully refined
  leaves still report an acceptable statistic; each of the first 3–4
  transitions then costs about 1,146 gradients (eight refinement levels per
  leaf), after which dual averaging overshoots down to about 0.006 and pays
  1,023-gradient depth-10 orbits until it recovers.

## Arms (research-only `WarmupConfig` options, all off by default)

| arm | option |
|---|---|
| `beyond-warmup` | `with_warmup_reverse_coarser_policy(ZeroWeightBeyond)` (warmup only) |
| `adaptsel-warmup` | `with_warmup_reverse_coarser_policy(ZeroWeightBeyondAdaptSelected)` |
| `stan-search` | `with_initial_step_search(InitialStepSearchConfig::stan())` |
| `skip` | `with_skip_single_leaf_reverse_coarser_statistic(true)`: a single-leaf orbit ending in a reverse-coarser rejection contributes no dual-averaging statistic |
| `descent2`, `descent1.5` | `with_dual_averaging_max_descent(f)`: the log step may fall at most `ln f` per iteration |
| `initnuts` | `with_initial_phase_max_error(1000.0)`: the initial fast phase runs without refinement (plain NUTS leaves) |

## Result: none of the levers meets the bar (geomean >= 1.10x with no model < 0.90x)

Seed medians of min bulk ESS per gradient (warmup included), ratio to the
shipped defaults; `targets` = both eight schools, `gp_pois_regr`,
`accel_gp`; full tables in `artifacts/sweep{1,2,3}-table.txt`.

| arm | seeds | geomean 17 | targets | controls | warmup grads | adapted step | worst |
|---|---|---:|---:|---:|---:|---:|---|
| `beyond-warmup` | 92101 | 0.823 | 0.654 | 0.883 | 1.113 | 1.125 | 0.23 |
| `adaptsel-warmup` | 92101 | 0.913 | 0.806 | 0.949 | 1.169 | 1.021 | 0.44 |
| `stan-search` | 92101 | 0.882 | 0.748 | 0.927 | 0.987 | 0.972 | 0.43 |
| `skip` | 92101, 92102 | **1.021** | 0.817 | 1.093 | 0.905 | 1.095 | 0.63 `gp_pois_regr` |
| `descent2` | 92101, 92102 | 0.726 | 0.541 | 0.795 | 1.296 | 1.053 | 0.15 `accel_gp`; `arma11` R-hat 1.26 |
| `skip+descent2` | 92101, 92102 | 0.740 | 0.641 | 0.773 | 1.179 | 1.133 | 0.16 |
| `initnuts` | 92101, 92102 | 0.933 | 0.614 | 1.061 | 0.963 | 0.997 | 0.24 `accel_gp` |
| `initnuts+skip` | 92101, 92102 | **1.051** | 0.783 | **1.151** | 0.863 | 1.094 | 0.48 `accel_gp` |

What the arms show:

- The warmup-only orbit policies remove every step crash but raise warmup
  gradients 11–17 %: the untruncated orbits are longer than the crashes they
  prevent.
- `skip` removes every crash, cuts warmup gradients 10 % and is 1.09x on the
  13 controls, but the adapted step ends about 10 % larger and the GP
  models, whose min-ESS coordinate is step-sensitive, lose (0.63, 0.81).
- The descent bound is harmful: it keeps the step high through the
  divergence region and `arma11` fails its R-hat gate.
- `initnuts` fixes the initial phase where it was pathological
  (`lotka_volterra` 1.52x, `hmm_drive_0` 1.15x, `nes2000` 1.17x) and is bad
  where refinement carried the initial phase (`accel_gp` 0.24x,
  `gp_pois_regr` 0.55x). Combined with `skip` it is the best arm, 1.15x on
  the controls, and still 0.78x on the targets.
- Stan's doubling step search helps the three models whose initial phase
  was the pathology above and breaks `arma11`, `kidiq` and `accel_gp` by
  installing a near-zero step.

Every arm that recovers warmup gradients does so by ending at a larger
step, and every such arm loses on the four target models. The warmup gap and
the target-model robustness lead come from the same behaviour: the shipped
statistic reacts to a single failed refined leaf by cutting the step hard.

## Addendum (2026-09-06): a higher acceptance target does not restore the targets (sweep4)

WP40's reading was that the target models prefer a smaller step per se, because the crash-driven step cut is uniform across models (2.6 to 5.8 % of warmup transitions on every model, crash statistic median about 0.2) rather than target-specific. If that were the whole story, pairing the `skip` statistic (no crashes) with a higher acceptance target (a smaller step by design) should keep the controls' gain and give the targets back their step. Sweep4 tested this: arms `t0.85`, `skip+t0.85`, `skip+t0.9`, `initnuts+skip+t0.85`, 17 models x 2 seeds (92101, 92102), scored against the sweep2 defaults (`artifacts/sweep4-table.txt`, `artifacts/screen1-table.txt`; `run_parallel.py` (four-wide tiered launcher)).

| arm | geomean vs default | targets | controls | sampling-only | warmup gradients | adapted step | worst model |
|---|---:|---:|---:|---:|---:|---:|---|
| `t0.85` | 0.958 | 1.032 | 0.936 | 0.936 | 1.151 | 0.906 | `accel_gp` 0.65 |
| `skip+t0.85` | 0.945 | 0.977 | 0.935 | 0.936 | 1.071 | 1.003 | `accel_gp` 0.62 |
| `skip+t0.9` | 0.904 | 0.906 | 0.903 | 0.929 | 1.214 | 0.858 | `accel_gp` 0.52 |
| `initnuts+skip+t0.85` | 0.937 | 0.754 | 1.001 | 0.887 | 1.025 | 0.969 | `accel_gp` 0.38 |

Not supported. A higher target buys back the step on average (`skip+t0.85` lands at 1.003x the shipped step) and still loses: `accel_gp` is 0.52 to 0.65x in every arm and `gp_pois_regr` is at best 1.17x (`t0.85` alone), so the targets' preference is not for a smaller step of the same kind. The centered eight schools gains 1.3 to 1.65x under any 0.85 target, and the three 0.85 arms without `initnuts` put `arma11` at R-hat 1.26, so the higher target also costs a gate on the escape model. The controls lose 6 to 10 % in every arm except the `initnuts` combination, where the targets fall to 0.75. Sampling-only efficiency is 0.89 to 0.94x in every arm: the higher target is paid during sampling on every model, and the crash removal does not compensate. The acceptance-target line is closed with the schedule levers; the open question is unchanged (a statistic that distinguishes one failed refined leaf from a too-large step), and no arm from this study is a preregistration candidate.

## Addendum 2 (2026-09-07): a floored crash statistic, and why the GP targets cannot be separated from the crash (screen1)

The last statistic-side design: keep the single-leaf reverse-coarser transition in dual averaging but feed it `max(statistic, floor)` instead of the raw 0.02 to 0.36, so one failed refined leaf still pushes the step down and cannot cut it 3 to 10x in one update (`WarmupConfig::with_single_leaf_reverse_coarser_statistic_floor`, research-only, off by default, bit-identical when off). Floors 0.3, 0.5 and 0.8 were screened on the four targets plus five fast controls (`arK`, `arma11`, `kidiq`, `nes2000`, `sblrc`), seeds 92101 and 92102, four cells in parallel (`run_parallel.py`, about 20 minutes), against the sweep2 defaults (`artifacts/screen1-table.txt`).

| arm | geomean over 9 | targets | controls | sampling-only | warmup gradients | adapted step | worst |
|---|---:|---:|---:|---:|---:|---:|---|
| `floor0.3` | 0.947 | 0.908 | 0.979 | 0.984 | 0.991 | 1.035 | `accel_gp` 0.60 |
| `floor0.5` | 1.014 | 0.974 | 1.048 | 1.058 | 0.932 | 1.068 | `accel_gp` 0.63 |
| `floor0.8` | 0.879 | 0.710 | 1.043 | 0.928 | 0.897 | 1.166 | `accel_gp` 0.30 |

`floor0.5` is the best statistic-side arm measured in this study (controls 1.048 with `arK` 1.14, `nes2000` 1.10, `kidiq` 1.05, noncentered eight schools 1.10; warmup gradients down 7 %) and it is still far from the bar, because `gp_pois_regr` is 0.73 and `accel_gp` 0.63.

The per-seed cells show why no statistic can do better. On `gp_pois_regr` the shipped step is 0.026 to 0.029 and the worst-parameter bulk ESS is 887 and 994; every arm that ends at 0.029 to 0.031 lands at 554 to 625. On `accel_gp` the shipped step is 0.0079 to 0.0081 with worst-parameter ESS 475 to 658 and rank R-hat 1.01 to 1.02; every arm that ends at 0.0084 to 0.0099 lands at 39 to 492 with R-hat 1.01 to 1.075. A 5 to 20 % larger step halves to tenths the worst-parameter ESS on both GP models. The crashes therefore are not noise the targets tolerate: on these two models the acceptance-0.8 fixed point sits at a step that is too large for the slowest coordinate, and the crash-driven step cut is what puts the shipped sampler under it. Any statistic that removes the cut, floors it, or replaces it with a higher target (sweep4) moves both GP models onto the wrong side of that step, and the effect on `accel_gp` is amplified by a worst-parameter ESS that is itself unstable at two seeds (39 to 658).

Direction closed. The healthy-model warmup gap and the GP-target lead share one cause, and the only lever that separates them is per-model (the step the slowest coordinate needs), which is a metric question, not a step-statistic question. The floor option stays research-only alongside the others.

## Decision

No default change. The four `WarmupConfig` options stay research-only and
documented as measured-and-not-adopted. A decision study on
`initnuts+skip` restricted to the control class is not worth preregistering
at 1.15x with 0.78x on the targets; the next question is a step statistic
that distinguishes "one refined leaf failed" from "the step is too large"
without ending at a larger step, which is a kernel question and not a
warmup-schedule one.

## Files

`src/main.rs` (profiler: per-transition warmup checkpoints, diagnostics,
retained draws, call counts, arm parsing), `Cargo.toml`, `gen_sweep.py`
(writes a detached `.cmd` batch; env `ARMS`, `SEEDS`, `TAG`, `EXE`,
`SWEEP_ROOT`), `analyze_sweep.py <TAG> <arms,csv>` (ArviZ 0.23.4 bulk ESS
and rank R-hat, seed medians, geomeans), `artifacts/sweep1-table.txt`
(68 cells, seed 92101), `artifacts/sweep2-table.txt` (136 cells, two seeds),
`artifacts/sweep3-table.txt`, `artifacts/sweep4-table.txt` (68 new cells plus the sweep2 defaults, two
seeds). Raw per-cell JSON (draws and telemetry, about 1 GB) was not
committed. Models: BridgeStan libraries from `posteriordb_bench_v6`,
`Init::uniform()`, `Metric::diagonal()`, `Limits::admit_worst_case()`, four
threads.
