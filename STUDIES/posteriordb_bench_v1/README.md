# posteriordb benchmark v1 — default settings, four samplers, 17 posteriors

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`, committed at
`4020d29` before the first evidence cell), executed 2026-09-01 20:46–22:52
local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. All 204
cells (17 posteriors x 4 arms x 3 seeds) ran; every failure is recorded as a
cell. Full per-cell numbers: `artifacts/summary.json`; per-model tables:
`artifacts/results-table.md`; hashes: `CHECKSUMS.sha256`.

Arms (everything at its defaults, nothing tuned per model; 4 chains,
1,000/1,000, seeds 77101–77103): **owalnuts-da** (BridgeStan target,
Python-package default tuning `h0 = 0.1`, depth 8, 4 refinement levels,
`delta = 1`, dual averaging at 0.8, adapted diagonal), **owalnuts-paper**
(identical plus `PaperAdaptationConfig::default()`), **cmdstan** 2.39.0
(NUTS, `adapt_delta` 0.8, depth 10), **nutpie** 0.16.8 (BridgeStan backend).
Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on every reference
parameter, zero sampling divergences.

## Verdict

**The Appendix C warmup must not become the default.** Under the
preregistered rule (geometric mean of paper/DA min-bulk-ESS-per-gradient >= 1
and "at least as good" on every model) it fails on both counts:

| statistic (paper / da, seed medians, 12 models with both arms complete) | value |
|---|---:|
| geomean bulk ESS per gradient | **0.077** |
| geomean tail ESS per gradient | 0.061 |
| geomean bulk ESS per second | 0.067 |
| geomean total gradients | 0.624 |
| models where paper is "at least as good" | 4/12 (two of them are models where *both* arms fail every gate) |
| models where paper loses | 8/12 |
| cells passing all gates | paper **8/51**, da 26/51 |

Per model, the paper arm passes 3/3 seeds only on the noncentered eight schools
(where it is 0.95x the DA arm per gradient, 0.90x per second) and on
`garch11` (0.90x / 0.85x). On nine other models it collapsed: chains froze at
the start (`kidiq`, `earnings`, `diamonds`, `sblrc`, `nes2000`, `hmm_drive_0`,
`accel_gp`: exactly 128,000 target calls = 16 per transition, every retained
transition a refinement exhaustion, R-hat undefined), or one to three chains
froze (`mesquite`, `arK`, `hmm_example`, `lotka_volterra`: R-hat 1.5–9.4).

Mechanism (from the per-window `PaperAdaptationUpdate` telemetry in the raw
cells): with uniform(-2, 2) unconstrained starts the first slow window's
orbits span energy ranges of 10^3–10^16, so the K-quantile rule
`delta = Delta / max(1, q_0.95(K))` installs `delta ~ 0` at transition 74 and
never recovers (with `delta = 0` every leaf exhausts refinement, no orbit
completes, the unrefined-fraction statistic is `None`, and `h` stays at
0.1). This is the WP17 V3-A freeze mode reproduced on ordinary posteriors.
The rule needs a floor on `delta`, a burn-in before the first installation,
or CmdStan-style start retries before it can be offered as a default.

## Headline table (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3; `ESS/s` and `ESS/grad` use the wall with warmup
included and gradients over warmup + sampling; `div` = sampling divergences
summed over chains, per seed. Full table incl. tail ESS, walls, R-hat and
max |z| in `artifacts/results-table.md`.

| model | owalnuts-da gates / bulk ESS/s / ESS/grad x1e3 | owalnuts-paper | cmdstan | nutpie |
|---|---|---|---|---|
| eight_schools noncentered | 3/3 / 10,918 / 23.0 | 3/3 / 9,796 / 21.8 | 1/3 (div 0,1,1) / 14,306 / 32.5 | 0/3 (div 2,2,1) / 13,983 / 40.5 |
| eight_schools centered | 0/3 (R-hat 1.04, div 0,4,1) / 91 / 0.47 | 0/3 (div 10,2,27) | 0/3 (div 93,54,74) / 556 / 0.64 | 0/3 (div 20,40,57) / 154 / 1.60 |
| diamonds | 0/3 (R-hat 1.09; 3,590/4,000 depth-8 caps) / 1.3 / 0.02 | 0/3 frozen | **3/3** / 15.2 / 0.22 | 1/3 / 11.7 / 0.16 |
| earnings logearn_interaction | 0/3 (R-hat 1.13; depth caps) / 1.1 / 0.02 | 0/3 frozen | **3/3** / 89.7 / 0.78 | 2/3 / 78.3 / 0.88 |
| mesquite logvash | 3/3 / 1,116 / 2.83 | 0/3 | **3/3** / 4,748 / 3.84 | 3/3 / 2,007 / 4.26 |
| kidiq momhsiq | 3/3 / 661 / 2.67 | 0/3 frozen | **3/3** / 1,654 / 3.72 | 3/3 / 1,123 / 5.02 |
| sblrc blr | 0/3 (R-hat 1.31; one seed `gradient inf`) / 137 / 0.30 | 0/3 frozen | 2/3 / 4,032 / 6.98 | **3/3** / 6,704 / 15.5 |
| nes2000 | 3/3 / 192 / 2.40 | 0/3 frozen | 3/3 / 322 / 4.81 | **3/3** / 359 / 5.47 |
| arK | 3/3 / 172 / 7.77 | 1/3 | **3/3** / 2,342 / 10.6 | 3/3 / 284 / 11.2 |
| arma11 | error x3 (`log density NaN` treated as fatal) | error x3 | 2/3 / 5,185 / 45.0 | 2/3 / 3,653 / 143.5 |
| garch11 | 3/3 / 320 / 13.4 | 3/3 / 271 / 12.0 | **3/3** / 2,901 / 20.3 | 3/3 / 681 / 24.2 |
| gp_pois_regr | **2/3** / 180 / 0.64 | error x3 (`gradient NaN`) | 0/3 (div 4,24,13) / 781 / 1.09 | 0/3 (div 175,136,143) / 388 / 1.05 |
| hmm_example | 3/3 / 50 / 8.31 | 0/3 | **3/3** / 1,495 / 22.7 | 3/3 / 186 / 26.6 |
| hmm_drive_0 | 2/3 / 20 / 7.50 | 0/3 frozen | **3/3** / 976 / 59.7 | 2/3 (div 0,546,0) / 164 / 71.6 |
| one_comp_mm_elim_abs | 0/3 (R-hat 1.015, tail ESS 91) / 6.0 / 3.95 | 1/3 | 0/3 (div 3,8,46) / 23.7 / 5.43 | 0/3 (div 13,14,11; max abs z 5.9) / 24.2 / 19.4 |
| lotka_volterra | 1/3 (two seeds: start not evaluable) / 103 / 3.53 | 0/3 | **2/3** / 106 / 2.76 | 1/3 (div 417,0,423) / 32 / 1.36 |
| accel_gp (66-d) | 0/3 (R-hat 1.64; div 1000,0,0) / 1.4 / 0.01 | 0/3 frozen | 0/3 (div 60,202,44) / 56.6 / 0.23 | 0/3 (div 149,118,111) / 40.4 / 0.19 |

Cells passing all gates: cmdstan 34/51, nutpie 29/51, owalnuts-da 26/51,
owalnuts-paper 8/51. Models with 3/3 passes: cmdstan 9, nutpie 7,
owalnuts-da 7, owalnuts-paper 2.

Head-to-head (geometric mean of seed-median ratios over models complete on
both sides): owalnuts-da / cmdstan **0.32x** bulk ESS per gradient and
**0.11x** bulk ESS per second (14 models, 0 wins); owalnuts-da / nutpie
0.25x and 0.26x (14 models, 0 wins). The only model where oWALNUTS beats the
competitors is `gp_pois_regr`, on gates rather than throughput: both NUTS
implementations diverge there (4–175 per seed) while both oWALNUTS arms that
ran had zero divergences; the DA arm passes 2/3.

Agreement with the posteriordb reference: every healthy cell of every arm has
max |z| <= 3.3 (no `agreement_flag`); the only flagged cells are frozen paper
cells and one `one_comp` nutpie cell (|z| 5.9 with 13 divergences).

## What the results say about the kernel defaults

1. **Depth 8 plus a diagonal metric is the DA arm's binding constraint on
   correlated regressions.** On `diamonds` and `earnings` the adapted step
   collapses to 0.003 and 3,400–3,600 of 4,000 retained transitions stop at
   the depth cap; CmdStan at depth 10 spends 4x the gradients and passes.
   `sblrc` shows the same collapse (steps 0.0004–0.004, R-hat 1.3). Nothing
   about refinement is engaged (99% of retained leaves at level 0 everywhere),
   so on these targets oWALNUTS is NUTS with a shorter tree.
2. **Wall-time overhead is real and larger than the gradient-count gap.**
   Per gradient oWALNUTS-da is 0.32x CmdStan; per second 0.11x. On `arK`,
   `hmm_example`, `hmm_drive_0` and `one_comp` the DA arm's wall is 10–30x
   CmdStan's at similar gradient counts (e.g. `hmm_example`: 33 s vs 1.5 s for
   205k vs 101k gradients). The BridgeStan FFI path through the facade is much
   slower per call than CmdStan's in-process evaluation on these models; this
   is the next engineering target and is not a kernel property.
3. **BridgeStan error semantics differ from CmdStan's.** `StanTarget` treats a
   NaN log density or NaN/inf gradient as fatal; CmdStan and nutpie treat the
   same evaluation as a rejected proposal. That killed all six `arma11` cells,
   the three `gp_pois_regr` paper cells, one `sblrc` and one `accel_gp` cell.
   Likewise the harness draws one uniform(-2, 2) start per chain and fails if
   it is not evaluable (`lotka_volterra` seeds 77101 and 77103), where CmdStan
   retries up to 100 times. Both are fixable in the integration layer and both
   should be fixed before any rerun.
4. **P2 held in part**: CmdStan and nutpie diverge heavily on the centered
   eight schools; the DA arm had 0, 4 and 1 divergences and the paper arm 10,
   2 and 27 — fewer, but not zero, and no arm passes there. P1 was falsified
   (DA arm fails `sblrc`, `arma`, one `hmm_drive_0` seed). P3 held (paper arm
   used fewer gradients on 8/12 models, mostly by freezing). P4 held
   (CmdStan/nutpie 7–10x the DA arm's ESS per gradient on `diamonds`).

## Deviations and caveats

* The driver process was killed externally once, during the
  `lotka_volterra` DA cells; it was relaunched and the interrupted cell re-run
  from scratch (recorded in `PREREGISTRATION.md`). Cells are deterministic in
  their draws given the seed; only walls differ.
* `lotka_volterra` paper seed 77101 is recorded as `timeout`: the harness
  wrote its (error) result after 20 s but the process then hung at exit until
  the 45-minute cap (0 CPU; an exit-time deadlock in the model library, not a
  sampling cost). The classification was left as written by the driver.
* Walls: shared 16-thread machine with other agents active; all arms ran four
  parallel chains. oWALNUTS and nutpie walls exclude compilation; CmdStan's
  wall is around `CmdStanModel.sample` and includes process launch and CSV
  writing (0.15–0.5 s of overhead on the fast models), which favours the
  in-process samplers on those.
* Sampling-only ESS/s (proportional estimate) is in `summary.json`
  (`min_bulk_ess_per_second_sampling`); it does not change any ranking.
* Raw draws (`artifacts/draws/*.npz`, `*.raw.json`) are hashed in
  `CHECKSUMS.sha256` and not committed; the CmdStan CSVs
  (`artifacts/cmdstan-output/`) are neither hashed nor committed.

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan nutpie arviz cmdstanpy posteriordb numpy pandas xarray
git clone --depth 1 https://github.com/stan-dev/posteriordb   # commit 28f8d3d
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make .venv/Scripts/python run_posteriordb.py run      # ~2 h; resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py analyze
.venv/Scripts/python checksums.py
```

CmdStan 2.39.0 is expected at the path in `run_posteriordb.py` (`CMDSTAN_HOME`).
