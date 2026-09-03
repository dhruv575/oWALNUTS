# posteriordb benchmark v4 — the v3 protocol on the eight-level default, with a Stan-regularisation arm, fresh seeds

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`, committed at
`74ad37d` before the first evidence cell), executed 2026-09-02 20:32–21:26
local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` with
`sampler::Tuning::default()` at **eight** refinement levels (WP28). **The
driver died after 187 of 204 cells** (see Deviations): the 17 missing cells
(`lotka_volterra` cmdstan 83102–83103 and nutpie 83101–83103; all twelve
`accel_gp` cells) are recorded as *not run* and were not relaunched — the
study is superseded by WP32 (`posteriordb_bench_v5`, which validated the
joint `MomentumSum` + Stan-regularisation defaults). This README finalises
v4 for the record on the cells present. Per-cell numbers:
`artifacts/summary.json`; tables: `artifacts/results-table.md`; hashes:
`CHECKSUMS.sha256`.

Everything is v3 (`STUDIES/posteriordb_bench_v3`) except: the harness is
rebuilt against the current `src/` (`Tuning::default()` now `h0 0.5`, depth
10, **8 levels**, `delta 1`; every oWALNUTS cell records
`max_refinement_levels: 8`), the seeds are fresh (83101–83103), the
stan-style control is replaced by **owalnuts-da-stanreg** (the sampler's
default dual-averaging warmup plus `DiagonalMetricRegularization::Stan`, the
`reg` arm of `STUDIES/step_collapse_v1`, via
`Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::Stan))`),
and every model is compiled fresh. Arms: **owalnuts-da**, **owalnuts-da-stanreg**,
**cmdstan** 2.39.0 defaults, **nutpie** 0.16.8 defaults. Gates: rank R-hat
<= 1.01, bulk and tail ESS >= 400 on every reference parameter, zero
sampling divergences.

## Verdict

**(1) The eight-level default is free on this set.** The refinement levels
the v3 default could not select (5–8) were chosen by 0.000 % of retained
transitions on 15 of 16 measured models and 0.5 % on the centered eight
schools; refinement of any level engages on 0.3–8 % of retained
transitions everywhere except the centered eight schools (25–29 %). On the
13 models without a seed-pathological draw the DA arm reproduces v3 at a
geomean v4/v3 ESS/gradient of **0.999** (CmdStan's own v4/v3 on the same
models: 0.952) and against CmdStan on the 12 non-pathological models it is
**0.515x** (v3 on the same models: 0.498x). The DA arm passes **39/48**
cells (v3 35/51; 12 models 3/3) at **0.694x** CmdStan's wall per gradient.

**(2) The Stan regularisation alone is not a default.** It does what
`step_collapse_v1` measured — `sblrc` **7.8x** per gradient, `h` 0.10 in
place of 0.004, 3/3 gates from 0/3 — and its geomean over DA is 1.158x, but
it fails the preregistered rule on all three clauses: `earnings` 0.35x and
`diamonds` 0.71x (< 0.8x), and **five models lose gates** (`earnings` 3/3
-> 0/3, `kidiq` 3/3 -> 0/3, `diamonds` 3/3 -> 2/3, `hmm_drive_0` 3/3 ->
2/3, `one_comp` 1/3 -> 0/3): 33 cells against DA's 39. The losses are all
R-hat 1.012–1.145 at 0.1–0.5x the gradients — the corrected metric puts the
step at CmdStan's, and the endpoint-U-turn orbit is then too short to mix
(`step_collapse_v1` finding 1, now on `kidiq` and `diamonds` as well as
`earnings`). That is the kernel-side gap the joint `MomentumSum` +
regularisation candidate of WP32 addresses; this study is the evidence that
the metric fix cannot ship without the orbit fix.

**(3) The headline against CmdStan is not comparable to v3 by the letter.**
The DA geomean over the 15 models complete on both sides is **0.845x**
(P2's window was 0.310–0.378) because CmdStan crawled on two of three
`arma11` seeds (chain at `h` 5.8e-8 / 1.8e-7, 931–936 depth-10 draws,
R-hat 1.59, min bulk ESS 7 — the `step_collapse_v1` §1b start that neither
sampler can leave), which makes that one model a 1,296x ratio. Excluding
`arma11` the 14-model geomean is 0.500x (v3 on the same 14: 0.335x, the
difference being `hmm_drive_0`, where v3 drew second-mode chains on two
seeds and v4 drew none).

## Headline (cells passing all gates / geometric mean of seed-median ratios over models complete on both sides)

| arm | cells passing | models 3/3 | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-da | **39**/48 | 12 | **0.845** (15 models; 0.500 excl. `arma11`) | 1.235 (0.734) | **0.694** | 0.436 (15) | **1.672** |
| owalnuts-da-stanreg | 33/48 | 9 | 0.993 (0.558) | 1.486 | 0.693 | 0.512 | 2.012 |
| cmdstan | 34/46 | 10 | 1 | 1 | 1 | — | — |
| nutpie | 28/45 | 9 | — | — | — | 1 | 1 |

Cells run: oWALNUTS arms 48 of 51 each (`accel_gp` not run), cmdstan 46
(`accel_gp`, `lotka_volterra` 83102–83103 not run), nutpie 45 (`accel_gp`,
`lotka_volterra` not run). v3 for comparison: owalnuts-da 35/51, 0.344x
CmdStan per gradient, 0.492x per second, 0.751x wall per gradient, 1.350x
nutpie per second; cmdstan 37/51; nutpie 31/51.

## Per-model table (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / seeds run with the failing gate(s) in
parentheses; then bulk ESS/grad x1e3 (warmup included) and bulk ESS/s
(warmup included); `div` = sampling divergences per seed where nonzero.

| model | owalnuts-da | owalnuts-da-stanreg | cmdstan | nutpie |
|---|---|---|---|---|
| eight_schools noncentered | **3/3** / 31.5 / 53,866 | 3/3 / 26.8 / 52,334 | 1/3 (div 1,1,0) / 28.0 / 9,831 | 0/3 (div 2,3,5) / 39.6 / 8,091 |
| eight_schools centered | 0/3 (R-hat 1.07–1.09; div 0,0,1) / 0.168 / 341 | 0/3 (R-hat 1.03–1.12) / 0.153 / 299 | 0/3 (div 100,32,287; R-hat 1.54) / 0.622 / 205 | 0/3 (div 43,125,68) / 0.770 / 196 |
| diamonds | **3/3** / 0.180 / 10 | 2/3 (R-hat 1.034) / 0.129 / 9 | **3/3** / 0.211 / 18 | 0/3 (R-hat 1.011–1.017) / 0.173 / 14 |
| earnings | **3/3** / 0.212 / 16 | 0/3 (R-hat 1.02–1.14; bulk 26–162) / 0.074 / 5 | **3/3** / 0.864 / 88 | **3/3** / 0.965 / 81 |
| mesquite | 3/3 / 2.85 / 3,123 | 3/3 / 3.20 / 3,736 | **3/3** / 3.32 / 3,282 | 3/3 / 4.26 / 1,221 |
| kidiq | 3/3 / 2.41 / 703 | 0/3 (R-hat 1.012–1.019; bulk 316–561) / 2.27 / 699 | **3/3** / 4.07 / 1,304 | 3/3 / 5.66 / 1,173 |
| sblrc | 0/3 (bulk 278–343; R-hat 1.012–1.022) / 0.497 / 578 | **3/3** / 3.85 / 4,689 | 3/3 / 6.07 / 1,434 | **3/3** / 14.8 / 6,352 |
| nes2000 | 3/3 / 2.43 / 218 | 3/3 / 2.76 / 268 | 3/3 / 5.29 / 476 | **3/3** / 6.00 / 475 |
| arK | 3/3 / 7.97 / 1,390 | 3/3 / 7.66 / 1,200 | **3/3** / 11.8 / 1,562 | 3/3 / 11.6 / 190 |
| arma11 | **3/3** / 5.28 / 970 | **3/3** / 13.1 / 2,059 | 1/3 (crawl at h 6e-8, 2e-7; R-hat 1.59) / 0.004 / 1 | **3/3** / 163 / 2,763 |
| garch11 | 3/3 / 13.1 / 2,064 | 3/3 / 14.0 / 2,091 | **3/3** / 20.0 / 2,593 | 3/3 / 24.8 / 356 |
| gp_pois_regr | **3/3** / 0.898 / 337 | **3/3** / 0.766 / 299 | 1/3 (div 3,0,9) / 1.04 / 464 | 0/3 (div 153,141,195) / 0.511 / 116 |
| hmm_example | 3/3 / 8.41 / 566 | 3/3 / 14.7 / 1,027 | **3/3** / 20.5 / 1,096 | 3/3 / 26.9 / 126 |
| hmm_drive_0 | **3/3** / 23.5 / 367 | 2/3 (R-hat 1.105: one chain in a second mode) / 27.4 / 395 | **3/3** / 36.3 / 326 | 1/3 (R-hat 1.53; div 657) / 6.07 / 12 |
| one_comp_mm_elim_abs | 1/3 (R-hat 1.115; tail 232) / 7.11 / 30 | 0/3 (tail 186–342; R-hat 1.011) / 10.1 / 45 | 0/3 (div 3,10,32) / 14.2 / 57 | 0/3 (div 27,28,37) / 7.00 / 8 |
| lotka_volterra | 2/3 (83102: one chain frozen at h 3e-5, 996 exhaustions, R-hat 1.60) / 2.70 / 46 | 2/3 (83102: same chain at h 4e-3, 473 exhaustions, R-hat 1.60) / 2.51 / 38 | 1/1 (83102–83103 not run) / 3.80 / 93 | not run |
| accel_gp (66-d) | not run | not run | not run | not run |

Agreement with the posteriordb reference: no oWALNUTS cell is flagged
(max |z| <= 4 on all 96); CmdStan is flagged on centered eight schools
83102 (|z| 4.5 on `tau`) and `one_comp` 83101 (6.2 on `V_m`), nutpie on
centered eight schools 83101 (5.1) — all on cells that fail their gates.

### Where oWALNUTS wins

* **Outright** (gates >=, higher ESS/gradient *and* ESS/s) against CmdStan:
  noncentered eight schools (3/3 vs 1/3, 1.12x per gradient, 5.5x per
  second) and `arma11` (3/3 vs 1/3, by CmdStan's crawl). Against nutpie:
  `gp_pois_regr`, `hmm_drive_0`, `one_comp` (all three arms of the
  stanreg arm too).
* **On gates against CmdStan**: noncentered eight schools and
  `gp_pois_regr` (3/3 vs 1/3, zero divergences on both); against nutpie
  also `diamonds` (3/3 vs 0/3) and `hmm_drive_0` (3/3 vs 1/3).
* **On ESS per second against nutpie**: 9 of 15 models (geomean 1.67x; the
  `STAN_THREADS` cost on nutpie's BridgeStan backend as in v2/v3).

### The eight-level default (question 1)

| | v3 (4 levels) | v4 (8 levels) |
|---|---|---|
| DA cells passing | 35/51 | 39/48 |
| DA v4/v3 ESS/gradient, 13 models without a seed pathology | — | **0.999** (CmdStan's own: 0.952) |
| DA vs CmdStan, 12 non-pathological models | 0.498 | **0.515** |
| DA vs CmdStan, all complete models | 0.344 (17) | 0.845 (15); 0.500 excl. `arma11` (14; v3 on the same 14: 0.335) |
| retained transitions at level 5–8 | not selectable | 0.000 on 15 models; 0.005 on centered eight schools |

Per model, v4/v3 DA ESS/gradient: noncentered eight schools 1.08,
diamonds 1.16, earnings 1.19, mesquite 0.94, kidiq 1.11, sblrc 1.20, nes
0.97, arK 1.03, garch 0.87, gp_pois_regr 1.23, hmm_example 0.86, one_comp
0.78, centered eight schools 0.73 (fails everywhere; the one model where
levels 5–8 are used, on 0.5 % of transitions, and where refinement
exhaustions still occur: 0–3 per chain). The seed-pathological models:
`hmm_drive_0` 83.6x (v3 drew second-mode chains on two seeds, v4 on none —
the coin flip of the v3 README), `arma11` 0.38x (83103 chain 1 ends warmup
at `h = 0.016` and takes 750k gradients — slow, not frozen or crawling;
3/3 gates, v3 2/3) and `lotka_volterra` 0.82x (83102 chain 3 frozen on the
`rk45` boundary at `h = 3e-5`, 996 exhaustions — the `uturn_default_v1`
80103 mode; 2/3, v3 3/3). Zero warmup or retained refinement exhaustions
on every other model in every oWALNUTS cell. Prediction P2 fails by its
letter on `arma11` alone; the matched-set comparison is the v3 figure.

### The Stan regularisation (question 2)

`stanreg / da`, seed-median min bulk ESS per gradient, with the gradient
ratio and the final steps (first seed): **sblrc 7.76** (0.34x gradients;
`h` 0.10 vs 0.0037; 3/3 vs 0/3), **arma11 2.48** (`h` 0.7 vs 0.1 — the
unit floor was binding on the healthy chains, as `step_collapse_v1`
observed), hmm_example 1.75 (0.54x gradients), one_comp 1.42, hmm_drive_0
1.16, nes 1.14, mesquite 1.12, garch 1.07, arK 0.96, kidiq 0.94,
lotka_volterra 0.93, centered eight schools 0.91, noncentered eight
schools 0.85, gp_pois_regr 0.85, **diamonds 0.71** (83103 chain 3 at
`h = 0.0011`, R-hat 1.034), **earnings 0.35** (`h` 0.006–0.016 vs 0.003,
0.12x the gradients, zero depth caps against 317–380, and min bulk ESS
26–162 with R-hat 1.02–1.14: the chains disagree at the corrected step).
Geomean **1.158** (1.254 without `earnings`; 1.101 without `earnings` and
`sblrc`).

Gates lost (stanreg passes fewer seeds than DA): `earnings` 3 -> 0,
`kidiq` 3 -> 0 (R-hat 1.012–1.019, min bulk ESS 316–561, at 0.47x the
gradients and `h` 0.10 vs 0.06 — the `earnings` mechanism on a model
`step_collapse_v1` had passing 2/2 at 1.06x), `diamonds` 3 -> 2,
`hmm_drive_0` 3 -> 2 (83101 chain 2 in the second HMM mode from the same
start the DA arm keeps in the main mode; `uturn_default_v1` saw the same
for `MomentumSum`), `one_comp` 1 -> 0 (R-hat 1.011 on 83103). No model
gains a gate except `sblrc`. Against CmdStan the stanreg arm is 0.993x per
gradient over 15 models (0.558x excluding `arma11`), 0.09x on `earnings`
and 0.63x on `sblrc`.

**Default rule** (">= 1.1x geomean, no model < 0.8x, no gate lost"):
**not met** — 1.158 passes the first clause; `earnings` (0.35) and
`diamonds` (0.71) fail the second; five models fail the third. The
regularisation stays opt-in on its own. The joint candidate (Stan
regularisation with `MomentumSum`, whose longer orbits at a well-scaled
metric are the missing half) is what WP32 tested on v5.

### What still fails for everyone

Centered eight schools (oWALNUTS R-hat 1.03–1.12 at `h` 0.05–0.35 with
0–1 divergences; CmdStan and nutpie 32–287 divergences), `one_comp` (tail
ESS < 400 in every arm; CmdStan and nutpie diverge), `sblrc` for the DA
arm (the step collapse, unchanged), and `accel_gp` was not run. Efficiency
on the healthy models is 0.41–1.12x CmdStan per gradient (noncentered
eight schools 1.12, mesquite 0.86, gp_pois_regr 0.86, diamonds 0.85, arK
0.67, garch 0.65, hmm_drive_0 0.65, kidiq 0.59, one_comp 0.50, nes 0.46,
hmm_example 0.41), `earnings` 0.25x and `sblrc` 0.08x — the
`adaptation_parity_v1` gap, unchanged from v3 (v3: 0.47–0.88x).

## Predictions

| | prediction | result |
|---|---|---|
| P1 | DA arm passes >= 35/51 | **39** of the 48 cells run — held (v3 35) |
| P2 | DA geomean ESS/gradient vs CmdStan within 0.9–1.1x of v3's 0.344 | **0.845** over 15 models — not held by the letter; CmdStan's two `arma11` crawls (1,296x on that model) are the whole difference: 0.500 without `arma11` (v3 on the same 14 models 0.335, the gap being `hmm_drive_0`'s mode draw), **0.515 vs 0.498** on the 12 non-pathological models, DA v4/v3 **0.999** on the 13 models without a seed pathology |
| P3 | stanreg >= 2x DA on `sblrc` and `earnings` | `sblrc` **7.76** held; `earnings` **0.35** not held (step_collapse_v1 had 1.9x on other seeds; here the DA arm is at its best seeds, 0.212, and the stanreg chains disagree) |
| P4 | stanreg geomean >= 1.1x DA, no model < 0.8x | geomean **1.158** held; `earnings` 0.35 and `diamonds` 0.71 — not held |
| P5 | DA wall per gradient <= 1.0x CmdStan | **0.694** — held (v3 0.751) |
| rule | stanreg default: >= 1.1x, none < 0.8x, no gate lost | **not met** (1.158; two models < 0.8x; five gates lost, 33 vs 39 cells) |

Ungated expectations: refinement at levels 5–8 ~0 everywhere except the
centered eight schools (held; `accel_gp` not run); `sblrc` under stanreg
at `h ~ 0.1` and >= 2/3 (held, 3/3); `earnings` under stanreg loses a gate
(held, all three seeds); `hmm_drive_0` and `lotka_volterra` remain
seed-draw coin flips (held: DA drew no second mode on `hmm_drive_0`,
stanreg one; `lotka_volterra` 83102 froze a chain in both arms); centered
eight schools and `one_comp` fail for every arm (held).

## v3 -> v4

| arm | v3 cells | v4 cells | geomean ESS/grad v4/v3 | geomean ESS/s v4/v3 |
|---|---:|---:|---:|---:|
| owalnuts-da | 35/51 | 39/48 | 1.22 (16 models; 0.999 on the 13 without a seed pathology) | 1.00 |
| owalnuts-da-stanreg (vs v3 owalnuts-da) | 35/51 | 33/48 | 1.42 | 1.17 |
| cmdstan | 37/51 | 34/46 | 0.51 (`arma11` 0.00005x; 0.95 on the 13) | 0.43 |
| nutpie | 31/51 | 28/45 | 0.84 (`hmm_drive_0` 0.09x) | 0.84 |

CmdStan lost `arma11` (2/3 -> 1/3), noncentered eight schools (2/3 ->
1/3, single divergences) and `lotka_volterra` (not run); nutpie lost
`hmm_drive_0` (3/3 -> 1/3: a second-mode chain and 657 divergences on
83103) and `diamonds` (1/3 -> 0/3), gained nothing.

## Deviations and caveats

* **Driver death (2026-09-02 ~21:26–21:32 local).** The driver was
  launched from a background shell of the agent session; the last cell
  written is `lotka_volterra` cmdstan 83101 at 21:25:54. CmdStan 83102 was
  running (its chain 3 was on the `rk45` boundary, CSV still growing at
  21:32:24) when the launching shell was reported killed by the session
  tooling at ~21:32; by the next morning no driver process existed and no
  further cell had been written. Per the protocol a crash is relaunched
  and the interrupted cell re-run; that was **not done**: the study was
  superseded by WP32 (`posteriordb_bench_v5`, merged on main) before the
  relaunch, and the coordinator directed that v4 be finalised on the 187
  cells present. The 17 missing cells are shown as *not run* in
  `results-table.md` (cmdstan `lotka_volterra` therefore reports one
  seed). Every head-to-head geomean is over models complete on both sides,
  so `lotka_volterra` and `accel_gp` are outside every ratio; the cell
  counts are out of the cells run.
* The v3 compiled models, venv and posteriordb checkout no longer existed;
  everything was rebuilt from the same package versions (BridgeStan 2.9.0,
  nutpie 0.16.8, cmdstanpy 1.3.0, ArviZ 0.23.4, posteriordb `28f8d3d`).
* Walls: shared 16-thread machine with other agents active; CmdStan's wall
  includes process launch and CSV writing (`sblrc` CmdStan wall 3.2x v3 at
  the same gradients is machine load); nutpie's BridgeStan backend is
  built with `STAN_THREADS`. Total sampler wall over the 187 cells: 35
  minutes.
* Raw draws (`artifacts/draws/`) are hashed in `CHECKSUMS.sha256` and not
  committed; CmdStan CSVs are neither.

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 nutpie==0.16.8 arviz==0.23.4 cmdstanpy==1.3.0 posteriordb numpy pandas xarray
git clone --depth 1 https://github.com/stan-dev/posteriordb   # commit 28f8d3d
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py run      # ~1 h; resumable (would fill the 17 missing cells)
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py analyze
.venv/Scripts/python checksums.py
```

CmdStan 2.39.0 is expected at `CMDSTAN_HOME` in `run_posteriordb.py`.
