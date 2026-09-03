# U-turn-rule default v1 — should `UTurnRule::MomentumSum` be the `sampler` default?

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`, committed at
`2095491` before the first evidence cell), executed 2026-09-02 19:34–20:18
local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` with the
0.2.0 `sampler` defaults (`h0 0.5`, depth 10, four levels, `delta 1`, dual
averaging 0.8, WP24 warmup exhaustion rule, adapted diagonal metric,
initial-evaluation cache). All 153 posteriordb cells (17 posteriors x 3 arms
x seeds 80101–80103), 18 funnel cells and 9 Eight Schools cells are present;
no cell errored. Per-cell numbers: `artifacts/summary.json`; tables:
`artifacts/results-table.md`; hashes: `CHECKSUMS.sha256`.

The arms differ in one thing, the kernel's no-U-turn predicate:
**owalnuts-da** = `UTurnRule::Endpoints` (the current default),
**owalnuts-da-rhosum** = `UTurnRule::MomentumSum` (Stan's criterion on the
summed leaf momenta with the 2.21+ cross checks, the candidate from
`STUDIES/kernel_efficiency_v1`), **owalnuts-da-cross** =
`UTurnRule::EndpointsWithCross` (reported only). CmdStan is not rerun; its
`STUDIES/posteriordb_bench_v3` seed medians are the cited reference.

## Verdict

**Keep `UTurnRule::Endpoints`. `MomentumSum` is not the default for 0.2.0.**
Three of the four preregistered criteria fail:

| criterion | value | threshold | held |
|---|---|---|---|
| C1 geomean min-bulk-ESS/gradient ratio rhosum / endpoints over 17 models | **1.064** | >= 1.10 | no |
| C2 no model below 0.85x | **0.78** (centered eight schools), 0.80 (diamonds), 0.846 (gp_pois_regr) | >= 0.85 | no |
| C3 funnel tail-mass \|z\| under both tunings | paper **+1.03**; sampler defaults **−3.39** (endpoints control −11.24) | <= 2 | no (defaults) |
| C4 Eight Schools strict-track ESS/call ratio | **1.077** | >= 0.9 | yes |

The momentum-sum rule is a per-model coin with a small positive bias, not a
uniform gain: it is 1.18–2.14x on six models (kidiq 1.37, garch 1.27, nes
1.18, one_comp 1.38, hmm_drive_0 1.26, lotka_volterra 2.14) and 0.78–0.93x on
seven (centered eight schools 0.78, diamonds 0.80, gp_pois_regr 0.85,
noncentered eight schools 0.88, arma11 0.90, arK 0.91, earnings 0.93), with
mesquite, hmm_example, sblrc and accel_gp within ±10 %. The geometric mean,
1.064x, is inside the ±10 % seed spread of the minimum-ESS statistic; the
sampling-only figure is 1.018x. It passes one cell fewer (37 vs 38 of 51):
it loses `earnings` 80103 and `gp_pois_regr` 80101 to R-hat 1.012–1.013
and `hmm_drive_0` 80103 to a second-mode chain, and gains `accel_gp` 80103
and `lotka_volterra` 80101. The Gaussian picture of `kernel_efficiency_v1`
(+35 % on an isotropic target, neutral elsewhere) does not transfer to the
posteriordb set: gradient counts go *up* on the near-isotropic models
(garch 1.26x, nes 1.09x, arK 1.03x — the rule ends orbits later there,
not earlier) and *down* on the depth-capped ones (diamonds 0.73x, earnings
0.73x), where the shorter orbits cost more minimum ESS than they save
(diamonds min bulk ESS 502–597 vs 871–902). The per-gradient gap to CmdStan
on the healthy models is therefore not the U-turn rule.

## Headline

| arm | cells passing | geomean ratio to endpoints (min bulk ESS/grad) | min model ratio | grads ratio | ESS/s ratio | vs CmdStan (v3, cited) |
|---|---:|---:|---|---:|---:|---:|
| owalnuts-da (`Endpoints`) | **38**/51 | 1 | — | 1 | 1 | 0.434 |
| owalnuts-da-rhosum (`MomentumSum`) | 37/51 | **1.064** | 0.78 | 1.071 | 1.025 | 0.462 |
| owalnuts-da-cross (`EndpointsWithCross`) | 37/51 | 0.811 | 0.26 | 0.957 | 0.764 | 0.352 |

The endpoint arm reproduces v3 (`owalnuts-da`, seeds 79101–79103) within
seed noise on the models where nothing is seed-pathological: v1/v3 ESS per
gradient 0.89–1.17 on 13 of them (E4 held), the centered eight schools 1.52
(fails every arm in every version), `hmm_drive_0` 91.7x (v3 drew
second-mode chains on two seeds, these seeds drew none for the endpoint
arm — the `MomentumSum` arm drew one on 80103, R-hat 1.20) and
`lotka_volterra` 0.25x (80103 starts on the `rk45` boundary, one chain
frozen at `h = 3e-5` with 863 exhaustions in both arms; 80101 has one chain
at `h = 0.011` in both). The 38/51 and 0.434x against CmdStan are the same
sampler as v3's 35/51 and 0.344x with a different `hmm_drive_0` /
`lotka_volterra` seed draw, which is the v3 finding about those two models.

## Per-model (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3 for endpoints / rhosum / cross; ESS/grad = min
bulk ESS per target call x1e3 (warmup included); the per-seed ratios are
cell by cell on shared starts.

| model | gates | endpoints ESS/grad | rhosum ESS/grad | **rhosum / endpoints** | per seed | cross / endpoints | grads rhosum / endpoints |
|---|---|---:|---:|---:|---|---:|---:|
| eight_schools noncentered | 3/3/3 | 32.0 | 28.3 | **0.88** | 1.31, 0.87, 0.83 | 0.93 | 1.00 |
| eight_schools centered | 0/0/0 | 0.351 | 0.275 | **0.78** | 0.21, 2.61, 1.13 | 0.61 | 1.23 |
| diamonds | 3/3/3 | 0.174 | 0.140 | **0.80** | 0.79, 0.82, 0.89 | 0.96 | 0.73 |
| earnings | 3/2/3 | 0.208 | 0.193 | **0.93** | 0.98, 1.11, 0.91 | 0.99 | 0.73 |
| mesquite | 3/3/3 | 3.00 | 3.08 | **1.03** | 1.06, 1.00, 1.11 | 1.01 | 1.02 |
| kidiq | 3/3/3 | 2.03 | 2.79 | **1.37** | 1.43, 1.30, 1.12 | 1.04 | 1.01 |
| sblrc | 0/0/0 | 0.484 | 0.478 | **0.99** | 1.98, 0.82, 0.99 | 0.98 | 0.90 |
| nes2000 | 3/3/3 | 2.53 | 2.98 | **1.18** | 1.29, 1.29, 1.09 | 0.96 | 1.09 |
| arK | 3/3/3 | 8.55 | 7.80 | **0.91** | 0.91, 0.99, 0.84 | 0.96 | 1.03 |
| arma11 | 3/3/3 | 13.8 | 12.4 | **0.90** | 1.01, 0.97, 0.90 | 1.02 | 0.99 |
| garch11 | 3/3/3 | 14.7 | 18.6 | **1.27** | 1.26, 1.06, 1.43 | 1.06 | 1.26 |
| gp_pois_regr | 3/2/3 | 0.813 | 0.687 | **0.85** | 0.36, 1.17, 0.85 | 0.88 | 1.16 |
| hmm_example | 3/3/3 | 9.92 | 9.52 | **0.96** | 0.95, 1.00, 0.94 | 0.94 | 0.92 |
| hmm_drive_0 | 3/2/2 | 25.8 | 32.4 | **1.26** | 1.23, 1.38, 0.01 | 0.61 | 0.99 |
| one_comp_mm_elim_abs | 1/1/1 | 8.11 | 11.2 | **1.38** | 2.57, 1.11, 0.98 | 1.16 | 1.19 |
| lotka_volterra | 1/2/1 | 0.814 | 1.74 | **2.14** | 2.14, 1.06, 0.99 | 0.26 | 1.31 |
| accel_gp (66-d) | 0/1/0 | 0.062 | 0.068 | **1.09** | 5.17, 0.74, 3.22 | 0.34 | 2.35 |

Reading the table:

* **Where it gains, it gains ESS rather than saving gradients.** kidiq
  (min bulk ESS 1.41x at 1.01x gradients), garch (1.61x ESS at 1.26x
  gradients), nes (1.27x at 1.09x), one_comp (1.71x at 1.19x), accel_gp
  (2.26x ESS at 2.35x gradients: the momentum-sum orbits on the 66-d GP
  run to depth 9–10 on 55–70 % of transitions against 7–28 % for the
  endpoint rule, and 80103 passes all gates at R-hat 1.008 where the
  endpoint arm is at 1.04–1.16). The rule ends orbits *later* on these
  targets, the opposite of the isotropic-Gaussian mechanism of
  `kernel_efficiency_v1` (E1 partly held, E2 not held).
* **Where it loses, it saves gradients and loses more ESS.** diamonds and
  earnings (both at `h ~ 0.003` with 200–750 depth-10 caps per cell) run
  0.73x the gradients (caps halve: diamonds 754 -> 374–515) but the
  minimum bulk ESS falls to 0.57x / 0.68x and R-hat rises to 1.008–1.012
  (`earnings` 80103 fails at 1.012). gp_pois_regr 80101: min bulk ESS 364
  against 865, R-hat 1.013. On the noncentered eight schools, arK, arma11
  and hmm_example the loss is 4–12 % at equal gradients, the
  `kernel_efficiency_v1` Eight Schools direction (0.86x vs 0.91x there).
* **The centered eight schools** (fails every arm) is 0.78x on the median
  with per-seed 0.21 / 2.61 / 1.13: its retained transitions exhaust
  (0–30 per chain under `MomentumSum`, nine of twelve chains, against
  0–24 on five of twelve), and the min-ESS
  statistic is on `tau` at 39–181 in both arms.
* **`hmm_drive_0` 80103** under `MomentumSum` lands chain 3 in the second
  HMM mode (`h = 0.079`, R-hat 1.20, min bulk ESS 16 on `phi[2]`), from a
  start the endpoint rule leaves in the main mode. Same seed, same start,
  different orbit: the mode draw is a property of the first warmup
  transitions, and the rule changes them.
* **`lotka_volterra` 80101** is 2.14x because the endpoint arm's chain 0
  ends warmup at `h = 0.011` (min bulk ESS 226, R-hat 1.036) while the
  momentum-sum chain 0 from the same start reaches `h = 0.012` but mixes
  (638, R-hat 1.003); 80103's frozen chain is identical in both.
* **`EndpointsWithCross`** is 0.811x overall and collapses on
  `lotka_volterra` (0.26), `accel_gp` (0.34), `hmm_drive_0` (0.61) and the
  centered eight schools (0.61): the cross checks on the endpoint statistic
  cut orbits short on the hard models. Confirmed not a candidate.

## Funnel tail mass (`P(omega < -5)`, exact 0.0478; 4 x 2,000 / 20,000 per seed, pooled over three seeds)

| tuning | rule | estimate | s.e. | **z** | per-seed z | target calls | omega bulk ESS / call x1e3 | retained exhaustions per seed |
|---|---|---:|---:|---:|---|---:|---:|---|
| paper (Appendix C, identity metric, `h 0.1`, 8 levels) | endpoints | 0.0521 | 0.0047 | **+0.90** | +0.03, −0.24, +1.57 | 7,159,772 | 0.237 | 0, 0, 5 |
| paper | rhosum | 0.0520 | 0.0040 | **+1.03** | +1.78, −1.10, +0.79 | 6,918,105 | 0.270 | 25, 4, 3 |
| paper | cross | 0.0453 | 0.0038 | −0.66 | −0.92, −0.44, +0.19 | 6,145,186 | 0.303 | 0, 0, 19 |
| sampler defaults (`Tuning::default()`, diagonal, DA 0.8) | endpoints | 0.0171 | 0.0027 | **−11.24** | −11.57, −6.01, −4.47 | 8,353,504 | 0.100 | 2,232, 362, 1,948 |
| sampler defaults | rhosum | 0.0313 | 0.0049 | **−3.39** | −3.91, −5.73, +0.02 | 11,470,693 | 0.102 | 2,153, 1,215, 782 |
| sampler defaults | cross | 0.0396 | 0.0068 | −1.19 | −3.54, +0.01, −0.00 | 5,705,991 | 0.113 | 1,755, 2,940, 2,764 |

At the paper tuning every rule preserves the tail mass (|z| <= 1.03), and
`MomentumSum` does it at 0.97x the calls with 1.14x the `omega` ESS per
call (the single-seed 1.14x *more* calls of `kernel_efficiency_v1` was
seed noise). At the sampler defaults **the tail mass is lost under every
rule, and worst under the current default**: the endpoint rule's pooled
estimate is 0.0171 (z −11.2), the momentum sum's 0.0313 (z −3.4). This is
the `freeze_mode_v1` funnel at four levels and `h0 = 0.5` with three seeds
instead of one — its single-seed z = −1.70 at s.e. 0.014 was underpowered,
not unbiased — and it is a property of the sampler defaults (four levels,
1,000–2,900 retained exhaustions per seed, 3–355 divergences), not of the
U-turn rule. C3 fails by its letter at the defaults, with the candidate
less biased than the default it would replace; the bias itself is a
separate finding for the default tuning on funnels (recorded in
`freeze_mode_v1` as "poor from these starts", now measured as biased).

## Eight Schools strict track (`eight_schools_v9_rebench_v1` settings, three seeds, three repetitions each)

| rule | calls per seed | min bulk ESS | min tail ESS | max R-hat | min bulk ESS/call (geomean) | ratio | all healthy |
|---|---|---|---|---|---:|---:|---|
| endpoints | 111,326 / 110,317 / 110,148 | 1,897 / 2,006 / 1,853 | 1,631 / 1,713 / 1,496 | <= 1.0032 | 0.01734 | 1 | yes |
| rhosum | 122,779 / 124,077 / 121,902 | 2,561 / 2,510 / 1,881 | 1,716 / 1,802 / 1,261 | <= 1.0028 | 0.01867 | **1.077** | yes |
| cross | 104,561 / 118,326 / 108,171 | 1,800 / 1,509 / 2,171 | 1,432 / 1,496 / 1,506 | <= 1.0021 | 0.01639 | 0.945 | yes |

Draws were bit-identical across repetitions in every cell. The endpoint
rule reproduces the v9 fresh-seed figure (0.01695–0.01762 there). C4 held:
`MomentumSum` is 1.08x per call at this tuning (11 % more calls, 1.2x the
bulk ESS), consistent with the 0.86–0.91x-within-noise reading of
`kernel_efficiency_v1`. The strict track is not the posteriordb noncentered
cell (0.88x): different tuning (`h 0.3`, depth 8, eight levels, acceptance
0.95, fixed starts), different statistic.

## Preregistered criteria and expectations

C1 not held (1.064 < 1.10); C2 not held (0.78, 0.80, 0.846 < 0.85); C3 held
at the paper tuning (+1.03), not held at the sampler defaults (−3.39;
control −11.24); C4 held (1.077). E1 (gains on the near-isotropic models)
partly held: kidiq, garch, nes gained, arK, mesquite, hmm_example did not.
E2 (5–25 % fewer gradients there, ±5 % on the depth-capped models) not
held: gradients rose 1–26 % on the isotropic models and fell 27 % on
diamonds and earnings. E3 (hmm_drive_0 / sblrc pathologies in every arm)
held for sblrc (0/3 everywhere at `h = 0.003`) and for hmm_drive_0 on one
rhosum seed only. E4 (endpoint arm reproduces v3 within seed noise) held on
the healthy models.

## What this decides

1. `UTurnRule::MomentumSum` stays opt-in. It is a legitimate option (Stan's
   criterion; +8 % on the Eight Schools strict track, +18–38 % on kidiq,
   garch, nes, one_comp; funnel-safe at the paper tuning) but it is not a
   uniform improvement, it costs 7–22 % on the noncentered eight schools,
   arK, arma11, diamonds and gp_pois_regr, and it passes no more gates.
   The README's "neutral elsewhere" is corrected to this table.
2. The 0.5–0.9x per-gradient gap to CmdStan on the healthy posteriordb
   models is not the U-turn rule: swapping to Stan's rule moves the geomean
   from 0.434x to 0.462x of CmdStan (cited v3 medians). The remaining
   candidates are the ones `posteriordb_bench_v3` named — the dual-averaging
   step collapse on `sblrc` / `earnings` / `diamonds` (0.003 with hundreds
   of depth-10 caps, where the stan-style preset gets 2–10x) and the
   refinement rejections where refinement engages.
3. The sampler-default funnel is biased under every U-turn rule (z −3 to
   −11 pooled over three seeds). `freeze_mode_v1`'s single-seed −1.7 was
   not a pass; it was noise. This is a finding about `Tuning::default()`
   on funnels (four levels, `h0 = 0.5`, dual averaging) and belongs in the
   README's honest-picture section; the paper tuning remains the
   documented funnel configuration.

## Deviations and caveats

* No driver restart; one continuous run (19:34–20:18 local), posteriordb
  cells first, then the funnel and Eight Schools checks in protocol order.
* The `EndpointsWithCross` arm ran on all 17 models (it was "if cheap":
  it is one extra endpoint dot product per check).
* Walls: shared 16-thread machine with other agents active; wall per
  gradient and ESS/s are reported but not gated. The Eight Schools walls
  (0.051–0.065 s) are on the same machine as v9's 0.117–0.161 s and are not
  comparable to them.
* Compiled models, the venv, the posteriordb checkout and raw draws are not
  committed (`.gitignore`); raw draws are hashed in `CHECKSUMS.sha256`.
* Before freezing, the harness was smoke-tested on the noncentered eight
  schools with seed 1 through the driver (all three arms, outputs deleted)
  and the Eight Schools binary once to a scratch path.

## Reproduce

```
cd STUDIES/uturn_default_v1
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --depth 1 https://github.com/stan-dev/posteriordb   # commit 28f8d3d
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_uturn.py run      # ~45 min; resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_uturn.py checks                     # funnel + Eight Schools, ~1 min
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_uturn.py analyze
.venv/Scripts/python checksums.py
```
