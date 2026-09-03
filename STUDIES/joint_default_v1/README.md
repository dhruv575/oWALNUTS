# joint_default_v1 — should the `sampler` defaults become `UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan` together? (WP31)

Status: preregistered decision study (`PREREGISTRATION.md`, `protocol.json`,
committed at `d2382b2` before the first evidence cell), executed 2026-09-03
11:27–14:11 local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`
with the 0.2.0 `sampler` defaults (`h0 0.5`, depth 10, eight refinement
levels, `delta 1`, dual averaging 0.8, WP24 warmup exhaustion rule, adapted
diagonal metric, initial-evaluation cache). All 204 posteriordb cells (17
posteriors x 4 arms x seeds 86101–86103), 24 funnel cells and 12 Eight
Schools cells are present; no cell errored or timed out. Per-cell numbers:
`artifacts/summary.json`; tables: `artifacts/results-table.md`; hashes:
`CHECKSUMS.sha256`. Driver: `run_joint.py`; binaries `src/main.rs`
(posteriordb cell), `src/bin/funnel.rs`, `src/bin/eight_schools.rs`; the
four arms are defined once in `src/arms.rs`.

The arms differ in two kernel/warmup options and nothing else:

| arm | `KernelOptions::u_turn` | diagonal-metric regularisation |
|---|---|---|
| `da` | `Endpoints` (current default) | `TowardUnit` (current default) |
| `rhosum` | `MomentumSum` | `TowardUnit` |
| `stanreg` | `Endpoints` | `Stan` |
| `joint` | `MomentumSum` | `Stan` — **the decided candidate** |

CmdStan 2.39.0 and nutpie are not rerun; their `STUDIES/posteriordb_bench_v3`
seed medians are the cited reference. The machine was shared with the
`wt/posteriordb-v4` run throughout: ESS per gradient is the metric, walls
are upper bounds.

## Verdict

**The preregistered rule is not met; the defaults stay.** Four of the five
criteria hold, most by a wide margin; C2 fails on two models:

| criterion | value | threshold | held |
|---|---|---|---|
| C1 geomean min-bulk-ESS/gradient `joint / da` over 17 models | **1.508** | >= 1.15 | yes |
| C2 no model below 0.85x | **0.005** (`hmm_drive_0`), 0.79 (centered eight schools) | >= 0.85 | **no** |
| C3 cells passing all gates | **41** vs `da` 35 (of 51) | >= 35 | yes |
| C4 funnel tail-mass \|z\| <= 2 on every seed, both tunings | paper +0.68, +0.61, +0.05; defaults −0.06, +0.81, −1.16 | <= 2 | yes |
| C5 Eight Schools strict-track ESS/call `joint / da` | **1.294** | >= 0.9 | yes |

Predictions: P1 (>= 1.2x on the five healthy regressions) held on four —
`earnings` 3.69, `kidiq` 1.98, `sblrc` 9.12, `nes2000` 1.50 — and missed on
`mesquite` (1.12); P2 (`earnings` gate recovered) held: `da` 1/3, `stanreg`
0/3, `joint` 3/3; P3 (`sblrc` >= 5x) held: 9.12.

The two C2 failures are the two models the rule was not written for and
that every arm fails: `hmm_drive_0` is the v3 mode lottery (a chain lands
in the second HMM mode during the first warmup transitions; which seeds do
so depends on the arm because the arm changes those transitions — `da`
drew one such seed of three, `rhosum` two, `stanreg` one, `joint` two; the
per-seed `joint / da` ratios are 0.00, 1.38, 0.60 and the seed median of
the two second-mode cells is the 0.005), and the centered eight schools
fails every gate in every arm on every seed (min bulk ESS 41–138 on `tau`,
R-hat 1.02–1.17), where `joint` has the highest ESS and lowest R-hat of the
four arms but at 1.5x the gradients. The rule said "no model below 0.85"
with no carve-out, `uturn_default_v1` preregistered the same rule with
"pathologies enter the geomean as they fall", and it is applied as
written. What the study establishes, and what it does not, are below.

## Headline

| arm | cells passed | geomean ratio to `da` (min bulk ESS/grad) | min model ratio | models < 0.85 | models > 1.15 | grads ratio | vs CmdStan (v3, cited) | vs nutpie (v3, cited) |
|---|---:|---:|---|---|---|---:|---:|---:|
| `da` | 35 / 51 | 1 | — | — | — | 1 | 0.317 | 0.359 |
| `rhosum` | 35 / 51 | 1.116 | 0.02 (`hmm_drive_0`) | centered 0.34, diamonds 0.76, gp_pois_regr 0.75, sblrc 0.84, hmm_drive_0 | earnings 1.50, kidiq 1.48, garch 1.22, one_comp 2.89, lotka_volterra, accel_gp 4.58 | 1.056 | 0.353 | 0.312 |
| `stanreg` | 33 / 51 | 1.257 | 0.08 (`earnings`) | noncentered 0.82, centered 0.53, earnings 0.08 | sblrc 5.52, arma11 1.83, hmm_example 1.54, hmm_drive_0 1.37, one_comp 1.34, lotka_volterra, accel_gp 1.34 | 0.734 | 0.398 | 0.358 |
| **`joint`** | **41 / 51** | **1.508** | 0.005 (`hmm_drive_0`) | centered 0.79, hmm_drive_0 | earnings 3.69, kidiq 1.98, sblrc 9.12, nes2000 1.50, arma11 2.26, garch 1.16, hmm_example 1.87, one_comp 2.16, lotka_volterra, accel_gp 3.35 | 0.960 | **0.477** | **0.424** |

`joint` passes six cells more than the default — `earnings` 86101/86103,
`sblrc` all three, `lotka_volterra` 86102, `one_comp` 86103 — and loses
one (`hmm_drive_0` 86101, the mode draw). Against CmdStan's cited v3
medians the default arm is at 0.317x and `joint` at 0.477x; on the healthy
regressions `joint` is at 0.81x (`earnings`), 0.93x (`kidiq`), 0.81x
(`sblrc`), 0.88x (`nes2000`), 0.99x (`mesquite`) of CmdStan per gradient,
against the default's 0.22 / 0.47 / 0.09 / 0.58 / 0.88.

## Per-model (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3 for `da` / `rhosum` / `stanreg` / `joint`;
ESS/grad = min bulk ESS per target call x1e3 (warmup included); per-seed
ratios are cell by cell on shared starts. Full rows with walls, gradients,
depth caps and final steps: `artifacts/results-table.md`.

| model | gates | `da` ESS/grad | `rhosum` / da | `stanreg` / da | **`joint` / da** | joint per seed | grads joint / da | da vs CmdStan | joint vs CmdStan |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| eight_schools noncentered | 3/3/3/3 | 28.9 | 0.91 | 0.82 | **1.04** | 1.11, 1.04, 0.96 | 1.06 | 0.86 | 0.89 |
| eight_schools centered | 0/0/0/0 | 0.561 | 0.34 | 0.53 | **0.79** | 0.79, 0.38, 0.78 | 1.51 | 0.52 | 0.41 |
| diamonds | 3/1/3/3 | 0.178 | 0.76 | 0.91 | **0.94** | 1.52, 0.82, 0.94 | 1.28 | 0.81 | 0.76 |
| earnings | 1/3/0/3 | 0.166 | 1.50 | 0.08 | **3.69** | 4.19, 2.91, 3.78 | 0.43 | 0.22 | 0.81 |
| mesquite | 3/3/3/3 | 3.02 | 1.05 | 1.04 | **1.12** | 1.06, 1.19, 1.23 | 1.15 | 0.88 | 0.99 |
| kidiq | 3/3/2/3 | 2.12 | 1.48 | 0.97 | **1.98** | 1.78, 1.98, 1.99 | 1.04 | 0.47 | 0.93 |
| sblrc | 0/0/3/3 | 0.581 | 0.84 | 5.52 | **9.12** | 8.20, 8.60, 18.66 | 0.25 | 0.09 | 0.81 |
| nes2000 | 3/3/2/3 | 2.88 | 1.02 | 0.88 | **1.50** | 1.44, 1.61, 2.09 | 0.99 | 0.58 | 0.88 |
| arK | 3/3/3/3 | 7.68 | 0.99 | 1.05 | **1.07** | 1.06, 1.07, 1.08 | 1.13 | 0.74 | 0.79 |
| arma11 | 3/3/3/3 | 4.78 | 1.01 | 1.83 | **2.26** | 2.55, 2.85, 2.20 | 0.94 | 0.07 | 0.15 |
| garch11 | 3/3/3/3 | 15.8 | 1.22 | 0.98 | **1.16** | 1.06, 1.26, 1.18 | 1.33 | 0.76 | 0.88 |
| gp_pois_regr | 3/3/2/3 | 0.791 | 0.75 | 0.86 | **0.98** | 0.91, 1.04, 1.04 | 1.06 | 0.74 | 0.72 |
| hmm_example | 3/3/3/3 | 9.16 | 0.96 | 1.54 | **1.87** | 2.10, 1.25, 1.93 | 0.64 | 0.44 | 0.82 |
| hmm_drive_0 | 2/1/2/1 | 19.1 | 0.02 | 1.37 | **0.005** | 0.00, 1.38, 0.60 | 0.85 | 0.30 | 0.00 |
| one_comp_mm_elim_abs | 1/2/0/2 | 5.08 | 2.89 | 1.34 | **2.16** | 7.98, 0.97, 2.16 | 1.30 | 0.40 | 0.85 |
| lotka_volterra | 1/1/1/2 | 0.037 | 59.6 | 49.1 | **72.1** | 0.80, 80.81, 1.02 | 1.07 | 0.01 | 0.77 |
| accel_gp (66-d) | 0/0/0/0 | 0.026 | 4.58 | 1.34 | **3.35** | 2.15, 2.50, 3.87 | 1.68 | 0.13 | 0.42 |

Reading the table:

* **The two options are one finding, and the interaction is the result.**
  `rhosum` alone is 1.12x (the WP26 wash again, on fresh seeds: 1.06x
  there); `stanreg` alone is 1.26x but loses two cells; together they are
  1.51x and gain six. On `earnings` the interaction is a sign flip:
  `stanreg` alone is **0.08x** and 0/3 (min bulk ESS 7–68, R-hat
  1.06–1.64), `joint` is **3.69x** and 3/3 (min bulk ESS 1,007–1,086,
  R-hat 1.004–1.005, zero depth caps against the default's 203–645).
* **Why `stanreg` alone collapses on `earnings`, mechanically.** The
  installed mass tells it: every `stanreg` cell installs a maximum mass of
  9.5e4–9.8e4 on `earnings` — the `Stan` floor `1e-3 x 5/(n+5)` = 1e-5 in
  variance, i.e. the window saw *no* movement on that coordinate — while
  every `joint` cell installs 5.8e3–6.2e3, which is CmdStan's own inverse
  metric for those coefficients (1.6e-4, `step_collapse_v1` §1a). Under
  the endpoint U-turn statistic at the corrected metric the orbits are
  short (WP30: 40 leaves against NUTS's 158) and the chain barely moves in
  the stiff coefficient directions, so the windowed variance collapses
  onto the floor, the metric overshoots by 1e2 and one chain per seed ends
  at `h` 0.10–0.21 while the others sit at 0.006–0.02 (R-hat 1.4–1.6). The
  momentum-sum orbits move far enough for the window to measure the
  variance, and the metric lands where CmdStan's does. `step_collapse_v1`
  saw the milder version of this (`reg` min bulk ESS 164–179, R-hat 1.02)
  at four refinement levels; at eight the floored metric is worse because
  the finer micro-steps let the mis-scaled chain keep accepting.
* **`sblrc` is the metric fix** (`stanreg` 5.5x, `joint` 9.1x, `h` 0.003
  -> 0.10–0.12 = CmdStan's), **`kidiq` / `nes2000` are the U-turn fix
  once the metric is right** (`rhosum` alone 1.48 / 1.02, `stanreg` alone
  0.97 / 0.88, `joint` 1.98 / 1.50), **`arma11` is the unit floor on the
  healthy chains** (`h` 0.10 -> 0.70–0.80, `stanreg` 1.83, `joint` 2.26;
  `step_collapse_v1` §1b predicted 2.9x), **`hmm_example`** 1.87x at 0.64x
  the gradients, **`mesquite` / `arK` / `garch11`** 1.07–1.16x (already
  near CmdStan; `joint` reaches 0.79–0.99x of it).
* **Where `joint` is below 1.** Centered eight schools 0.79 (fails
  everywhere; more ESS at 1.5x the gradients), `diamonds` 0.94 (1.5x the
  min bulk ESS at 1.28x the gradients — the depth-10 caps fall from
  791–1,012 per cell to 313–905, but not to zero, and `h` stays at 0.003
  because `diamonds` is not a floor case), `gp_pois_regr` 0.98,
  `hmm_drive_0` (the mode draw; on the seed where both arms stay in the
  main mode the ratio is 1.38).
* **`lotka_volterra`** 86103 starts on the `rk45` boundary in every arm
  (one chain frozen at `h` 1e-5 to 7e-4 with 409–862 retained exhaustions,
  26–45 minutes per cell, min bulk ESS 7); on 86102 the default draws a
  chain at R-hat 1.31 (min bulk ESS 10) that `rhosum`, `stanreg` and
  `joint` do not, hence the 80x. `one_comp` 86101: `da` at min bulk ESS 91
  (R-hat 1.045), `joint` 955.
* **The default arm reproduces v3** within seed noise on the models where
  nothing is seed-pathological (0.93–1.15 on twelve of them; geomean 0.92);
  `arma11` 0.34x (all four chains healthy at `h` 0.10 here, v3's median
  seed had a larger step), `hmm_drive_0` 68x (v3 drew second-mode chains
  on two seeds, here one), `lotka_volterra` 0.01x (two bad seeds of three
  here, one in v3), `accel_gp` 0.38x, `one_comp` 0.56x, centered eight
  schools 2.4x — all fail-everywhere or mode-lottery cells.

## Funnel tail mass `P(omega < -5)` (exact 0.0478), 4 x 2,000 / 20,000 per seed

`z` per seed uses the MCSE of the indicator (the `funnel_defaults_v1`
statistic, the gate); the batch-means z (`uturn_default_v1`'s statistic)
per seed and pooled is in `artifacts/results-table.md`. At the paper tuning
the metric is the identity, so `stanreg` = `da` and `joint` = `rhosum`
bit for bit (verified: identical cells).

| tuning | arm | per-seed estimate (z) | all \|z\| <= 2 | omega bulk ESS / R-hat per seed | target calls (3 seeds) | divergences | retained exhaustions |
|---|---|---|---|---|---:|---|---|
| paper | `da` (= `stanreg`) | 0.0539 (+0.77), 0.0405 (−1.12), 0.0439 (−0.65) | yes | 584 / 1.012, 754 / 1.006, 650 / 1.006 | 6,730,195 | 0, 0, 0 | 2, 0, 0 |
| paper | `rhosum` (= `joint`) | 0.0524 (+0.68), 0.0526 (+0.61), 0.0482 (+0.05) | yes | 544 / 1.005, 662 / 1.005, 669 / 1.007 | 7,667,150 | 0, 0, 0 | 1, 1, 1 |
| defaults | `da` | 0.1046 (+1.55), 0.0594 (+1.02), 0.0431 (−0.46) | yes | 111 / 1.044, 314 / 1.007, 245 / 1.035 | 9,320,947 | 2, 9, 4 | 11, 49, 74 |
| defaults | `rhosum` | 0.0403 (−1.21), 0.0467 (−0.12), 0.0404 (−1.24) | yes | 444 / 1.013, 418 / 1.007, 690 / 1.002 | 12,292,077 | 0, 9, 0 | 1, 91, 5 |
| defaults | `stanreg` | 0.0455 (−0.20), 0.0558 (+0.66), 0.0678 (+1.36) | yes | 220 / 1.026, 270 / 1.014, 345 / 1.010 | 8,126,099 | 0, 4, 0 | 4, 62, 6 |
| defaults | **`joint`** | 0.0474 (−0.06), 0.0549 (+0.81), 0.0393 (−1.16) | **yes** | 357 / 1.010, 618 / 1.003, 408 / 1.004 | 13,268,242 | **0, 0, 0** | 39, 9, 2 |

C4 holds for `joint` at both tunings; at the sampler defaults it is the
only arm with zero retained divergences on every seed and it has the
best `omega` R-hat (1.003–1.010 against the default's 1.007–1.044; the WP28
"unbiased, not efficient" caveat is smaller under `joint`: `omega` bulk ESS
357–618 per 80,000 draws against 111–314). The default arm's 86101 cell
(0.1046, MCSE-z +1.55, batch-means z +2.97, one chain at `h` 0.05 that
spent its run in the neck) is the per-chain step-collapse mode WP28
described; it passes the MCSE gate and fails the batch-means one, which is
why the gate statistic was fixed in advance. The funnel costs `joint` 1.4x
the default's target calls.

## Eight Schools strict track (`eight_schools_v9_rebench_v1` settings, three seeds x three repetitions)

| arm | calls per seed | min bulk ESS | max R-hat | geomean min bulk ESS/call | ratio to `da` | all healthy |
|---|---|---|---|---:|---:|---|
| `da` | 117,727 / 122,738 / 117,205 | 1,819 / 2,124 / 1,808 | <= 1.0022 | 0.01603 | 1 | yes |
| `rhosum` | 120,273 / 122,260 / 119,063 | 2,479 / 2,584 / 2,744 | <= 1.0047 | 0.02157 | 1.346 | yes |
| `stanreg` | 111,836 / 110,234 / 107,848 | 1,851 / 2,215 / 1,756 | <= 1.0031 | 0.01756 | 1.095 | yes |
| **`joint`** | 118,104 / 118,125 / 123,901 | 2,477 / 2,594 / 2,402 | <= 1.0035 | 0.02075 | **1.294** | yes |

Draws were bit-identical across repetitions in every cell. The default arm
reproduces the v9 / WP26 figure (0.01695–0.01762 there; 0.01603 here at
seed spread). C5 holds with margin.

## What this decides

1. **No default flip.** C2 fails as written (`hmm_drive_0` 0.005, centered
   eight schools 0.79), so `Tuning::default()` keeps `UTurnRule::Endpoints`
   and `Adaptation::default()` keeps `DiagonalMetricRegularization::TowardUnit`.
   No kernel, sampler or test source changes in this study.
2. **The joint option is the recommended opt-in for ordinary posteriors**,
   documented in the README as one `Tuning` + one `Adaptation` call:
   `Tuning::new().kernel_options(KernelOptions { u_turn: UTurnRule::MomentumSum, ..Default::default() })`
   with
   `Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::Stan))`.
   It is 1.51x the default per gradient over the 17 models, 41 vs 35 gates,
   funnel-safe at both tunings, 1.29x on the Eight Schools strict track,
   and takes the healthy regressions from 0.09–0.58x of CmdStan to
   0.81–0.99x. The two options should be used together: the regularisation
   alone is 0.08x on `earnings`.
3. **The rule, not the evidence, blocked the flip**, and the rule was right
   to be applied. Both C2 failures are cells no arm passes: the centered
   eight schools fails every gate in every arm on every seed, and
   `hmm_drive_0`'s second-mode draw is a start property that the arm
   perturbs in either direction (WP26 saw `rhosum` draw one where `da` did
   not; here `joint` drew two and `da` one). A rule that cannot distinguish
   a regression from a coin toss on a fail-everywhere cell is the wrong
   rule for this decision, but it was the preregistered one. The next
   decision on this pair should preregister C2 over the models whose
   default arm passes at least one gate, or over seed-paired cells with
   the same mode assignment, and should be a fresh run — nothing in this
   study is reused for it.
4. **Two smaller findings.** (a) The `Stan` regularisation under the
   endpoint U-turn rule is not merely "loses the earnings gate" (WP27) but
   unstable at eight levels: the floored-variance feedback (short orbits
   -> window sees no movement -> 1e-5 floor -> metric 1e2 too wide -> one
   chain at 10x the others' step) makes `stanreg` alone worse than the
   default there, 0/3 at R-hat up to 1.64; it should not be recommended
   alone. (b) `diamonds` at depth 10 is still capped under every arm
   (313–1,012 per cell) at `h` 0.003; its per-gradient figure is within
   0.76–0.94 of the default in every arm and it is not a metric-floor
   case — the next item on it is the depth cap itself.

## Deviations and caveats

* No driver restart; one continuous run (11:27–14:11 local), posteriordb
  cells first, then the funnel and Eight Schools checks in protocol order.
* `lotka_volterra` 86103 took 1,565–2,638 s per cell (four cells, a frozen
  `rk45`-boundary chain in every arm; `stanreg`'s 2,638 s is 62 s under
  the 2,700 s timeout) — a result, not a deviation.
* Walls: shared machine with the `wt/posteriordb-v4` run (CmdStan, nutpie,
  BridgeStan compiles) active throughout; wall per gradient and ESS/s are
  reported and not gated. `joint`'s geomean ESS/s ratio to `da` is 1.56.
* Compiled models, the venv, the posteriordb checkout and raw draws are not
  committed (`.gitignore`); raw draws are hashed in `CHECKSUMS.sha256`.
* Before freezing, the harness was smoke-tested on the noncentered eight
  schools with seed 1 through the cell binary for all four arms (shared
  starts, arms differing only in `u_turn` / `metric_regularization`,
  outputs deleted), the funnel binary once per tuning and the Eight
  Schools binary once, all to scratch paths (deleted).
* Seeds: 86101–86103 (the 85101–85103 suggested in the task were consumed
  by `STUDIES/funnel_bias_fix_v1`).

## Reproduce

```
cd STUDIES/joint_default_v1
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_joint.py build     # 17 BridgeStan compiles, ~7 min
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_joint.py run                       # 204 cells, ~2 h 45 min on the shared machine (2 h of it lotka_volterra 86103); resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_joint.py checks                    # funnel + Eight Schools, ~10 s
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_joint.py analyze
.venv/Scripts/python checksums.py
```
