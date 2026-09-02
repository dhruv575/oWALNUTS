# posteriordb benchmark v2 — the v1 protocol rerun on the fixed sampler, fresh seeds

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`, committed at
`cd184a5` before the first evidence cell), executed 2026-09-02 01:40–02:41
local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, paper
rule `walnutpie-paper-adaptation-kquantile-gamma-v4`. All 255 cells (17
posteriors x 5 arms x 3 seeds 78101–78103) are present; every failure is a
cell. Per-cell numbers: `artifacts/summary.json`; tables:
`artifacts/results-table.md`; hashes: `CHECKSUMS.sha256`.

Arms (everything at its defaults, nothing tuned per model; 4 chains,
1,000/1,000): **owalnuts-da** (`sampler::Sampler`, `Tuning::default()` =
`h0 0.5`, depth 10, 4 refinement levels, `delta 1`; `Metric::diagonal()`;
dual averaging at 0.8; `Init::uniform()` start retries; `ReplicatedStanTarget`
on a BridgeStan build without `STAN_THREADS`), **owalnuts-paper** (same,
`Adaptation::Paper(PaperAdaptationConfig::default())`, v4),
**owalnuts-stan-style** (same, `Adaptation::Custom(WarmupConfig::stan_style(0.8))`),
**cmdstan** 2.39.0 defaults, **nutpie** 0.16.8 defaults — the last two
exactly as v1. Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on every
reference parameter, zero sampling divergences.

## Verdict

**The v1 integration failures are gone; the breadth gap to CmdStan is not.**
Zero oWALNUTS cells were lost to a fatal NaN/inf evaluation or an unevaluable
start (v1: 12), the paper arm no longer freezes on the regressions (v1: nine
models; it now passes 29/51 against 8/51 and is 0.99x the DA arm per gradient
overall), depth 10 turns `diamonds` from 0/3 into 3/3 for every oWALNUTS arm
and `earnings` from 0/3 into 2/3, and with the non-`STAN_THREADS` build the
DA arm's wall per gradient is **0.77x CmdStan's** (v1: ~3x at equal counts)
and its ESS per second **1.11x nutpie's** (9 of 16 models won). But the
per-gradient efficiency against CmdStan did not move: 0.23x geometric mean
over all 17 models, 0.45x over the 15 models where no oWALNUTS chain
freezes, versus 0.32x over 14 models in v1. Two of the five preregistered
predictions held (P3 wall per gradient, P5 no fatal losses); P1 missed by one
cell (32 vs >= 33), P2 missed (0.23 vs >= 0.45), P4 failed (five frozen paper
cells, on `arma11` and `lotka_volterra`).

## Headline (cells passing all gates / geometric mean of seed-median ratios)

| arm | cells passing | models 3/3 | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-da | **32**/51 | 8 | 0.233 (17 models) | 0.307 | 0.771 | 0.230 (16) | **1.108** |
| owalnuts-paper | 29/51 | 7 | 0.232 | 0.305 | 0.771 | 0.229 | 1.104 |
| owalnuts-stan-style | **32**/51 | 8 | 0.319 | 0.450 | 0.767 | 0.238 | 1.125 |
| cmdstan | 35/51 | 10 | 1 | 1 | 1 | — | — |
| nutpie | 27/51 | 7 | — | — | — | 1 | 1 |

v1 for comparison: owalnuts-da 26/51, 0.32x CmdStan per gradient (14
models), 0.11x per second; owalnuts-paper 8/51; cmdstan 34/51; nutpie 29/51.
The head-to-head now covers all 17 models because no oWALNUTS cell errored;
the two models where oWALNUTS chains freeze (`arma11`: 0.0005x CmdStan;
`lotka_volterra`: 0.007x) dominate the geometric mean. Excluding them (post
hoc, for orientation only): DA 0.447x per gradient and 0.667x per second vs
CmdStan, stan-style 0.471x / 0.684x.

## Per-model table (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3; then bulk ESS/grad x1e3 (warmup included) and
bulk ESS/s (warmup included); `div` = sampling divergences per seed where
nonzero.

| model | owalnuts-da | owalnuts-paper | owalnuts-stan-style | cmdstan | nutpie |
|---|---|---|---|---|---|
| eight_schools noncentered | **3/3** / 26.4 / 76,910 | 3/3 / 26.2 / 74,742 | 3/3 / 23.9 / 68,010 | 1/3 (div 0,1,1) / 29.1 / 13,680 | 0/3 (div 5,3,6) / 34.5 / 14,030 |
| eight_schools centered | 0/3 (R-hat 1.03, div 2,0,1) / 0.56 / 1,284 | 0/3 (div 1,1,2) / 0.66 / 1,494 | 0/3 (div 9,3,5) / 0.48 / 760 | 0/3 (div 52,116,42) / 1.02 / 341 | 0/3 (div 73,23,20) / 1.27 / 125 |
| diamonds | **3/3** / 0.183 / 11.6 | 3/3 / 0.194 / 14.3 | 3/3 / 0.178 / 13.9 | 3/3 / 0.206 / 18.1 | 0/3 (R-hat 1.02) / 0.142 / 9.4 |
| earnings | 2/3 (one seed R-hat 1.09) / 0.175 / 14.2 | 2/3 (R-hat 1.53) / 0.192 / 15.5 | 0/3 (R-hat 1.03,1.03,1.54) / 0.345 / 38.2 | **3/3** / 0.796 / 55.7 | 3/3 / 0.994 / 58.4 |
| mesquite | 3/3 / 3.12 / 4,056 | 3/3 / 3.02 / 3,784 | 3/3 / 2.37 / 2,711 | **3/3** / 4.26 / 4,758 | 3/3 / 4.50 / 1,572 |
| kidiq | 3/3 / 2.21 / 767 | 1/3 (R-hat 1.49, 1.011) / 1.58 / 579 | 2/3 (R-hat 1.016) / 1.66 / 608 | **3/3** / 4.51 / 1,788 | 2/3 / 5.43 / 1,314 |
| sblrc | 1/3 (bulk ESS 366, 202) / 0.62 / 912 | 1/3 / 0.79 / 1,346 | 2/3 (R-hat 1.011) / 3.76 / 6,211 | 3/3 / 6.99 / 5,067 | **3/3** / 15.9 / 6,664 |
| nes2000 | 3/3 / 2.66 / 275 | 3/3 / 3.01 / 326 | 3/3 / 2.58 / 259 | 3/3 / 4.87 / 552 | **3/3** / 5.52 / 487 |
| arK | 3/3 / 7.83 / 1,726 | 3/3 / 7.07 / 1,580 | 3/3 / 8.52 / 1,891 | **3/3** / 10.6 / 2,041 | 3/3 / 11.2 / 271 |
| arma11 | 0/3 frozen chains / 0.033 / 15 | 0/3 frozen / 0.038 / 20 | 0/3 frozen / 0.025 / 13 | **2/3** / 73.6 / 17,941 | 2/3 (div 143,0,0) / 147 / 3,046 |
| garch11 | 3/3 / 11.4 / 2,771 | 3/3 / 14.8 / 3,481 | 3/3 / 10.4 / 2,302 | **3/3** / 21.6 / 3,767 | 3/3 / 25.9 / 612 |
| gp_pois_regr | 2/3 / 0.71 / 524 | 2/3 / 0.72 / 501 | **3/3** / 0.68 / 489 | 0/3 (div 9,9,16) / 0.93 / 774 | 0/3 (div 161,120,822) / 1.07 / 119 |
| hmm_example | 3/3 / 8.89 / 1,100 | 3/3 / 9.81 / 961 | 3/3 / 14.7 / 1,455 | **3/3** / 23.7 / 1,666 | 3/3 / 32.0 / 192 |
| hmm_drive_0 | 2/3 (R-hat 1.27) / 12.1 / 237 | 1/3 (R-hat 1.73; tail 344) / 8.1 / 152 | 2/3 (R-hat 1.43) / 6.9 / 108 | 2/3 (div 0,369,0) / 33.5 / 248 | 2/3 (div 0,60,0) / 94.1 / 266 |
| one_comp_mm_elim_abs | 0/3 (tail ESS 55–175) / 4.34 / 24.5 | 0/3 (tail 39–256) / 5.21 / 30.4 | 0/3 (tail 125–251) / 6.55 / 35.3 | 0/3 (div 13,9,9) / 10.2 / 57.1 | 0/3 (div 21,26,14) / 11.4 / 20.7 |
| lotka_volterra | 1/3 (frozen chain x2) / 0.025 / 0.2 | 1/3 (frozen x2) / 0.026 / 0.2 | 2/3 (one chain h=0, 1000 depth caps) / 3.07 / 89 | **3/3** / 3.64 / 177 | 0/3 (div 347; crashed on 78102, 78103 not run) / 0.13 / 1.1 |
| accel_gp (66-d) | 0/3 (R-hat 1.03–1.12) / 0.056 / 13.5 | 0/3 (R-hat 1.07–1.10) / 0.030 / 6.8 | 0/3 (R-hat 1.10–1.37) / 0.018 / 4.7 | 0/3 (div 14,63,102) / 0.283 / 76.7 | 0/3 (div 159,113,127) / 0.226 / 19.7 |

Agreement with the posteriordb reference: every healthy cell of every arm is
within max |z| 3.5; the flagged cells are the frozen `arma11` seed 78103
(all three arms, |z| 5.0), `one_comp` paper 78103 (|z| 4.6, tail ESS 256)
and one nutpie cell.

### Where oWALNUTS wins

* **Outright** (gates >=, higher ESS/gradient *and* ESS/s): `diamonds`
  against nutpie, every oWALNUTS arm (3/3 vs 0/3; nutpie R-hat 1.01–1.02).
  No outright win against CmdStan.
* **On gates**: noncentered eight schools (3/3 for every oWALNUTS arm with
  zero divergences; CmdStan 1/3, nutpie 0/3) and `gp_pois_regr` (stan-style
  3/3, DA/paper 2/3, zero divergences; CmdStan 0/3 with 9–16 divergences,
  nutpie 0/3 with 120–822). Neither is a throughput win: CmdStan's ESS per
  gradient is 1.1–1.3x higher on both.
* **On ESS per second against nutpie**: 9 of 16 models (nutpie's BridgeStan
  backend carries the `STAN_THREADS` cost this study removed on our side:
  arK 271 vs 1,726 ESS/s, hmm_example 192 vs 1,100, garch 612 vs 2,771).
  Against CmdStan, 2 of 17 (both eight-schools variants, where CmdStan's
  wall is process launch).

### What still fails, and why

1. **`arma11` (0/3, every oWALNUTS arm): chains frozen from the start.**
   With the same seed the same chains freeze in all three arms (seed 78101
   chain 0; 78102 chains 2–3; 78103 all four): `h` adapts to 0, every
   retained transition is a refinement exhaustion, and the target reports
   550–3,000 recoverable failures (v1 killed these cells outright on the
   fatal-NaN path, so the fix converted deaths into frozen chains). The
   starts passed `Init::uniform()`'s finite-density-and-gradient check, yet
   every leaf from them fails even as `h -> 0`. CmdStan passes 2/3 from the
   same initialisation rule. This is now a kernel-side start-region problem
   (WALNUTS treats a rejected leaf at every refinement level as an
   exhaustion and cannot move; NUTS's single-leaf reject-and-shrink does
   move), not an integration one.
2. **`lotka_volterra` (DA/paper 1/3): one chain per seed freezes at
   `h ~ 1e-5`** with ~1,000 recoverable failures (ODE solver failures in
   the tail: `integrate_ode_rk45 ... max_num_steps`, `initial state is
   inf`). The stan-style arm's initial-phase `delta = 1000` ramp survives
   78103 (2/3) but on 78102 one chain ends at `h = 0` with every transition
   at the depth cap. nutpie crashed in `nuts-rs` on 78102 ("failed to
   constrain the parameters of the draw"), which took the child process
   down before 78103 ran; both are recorded as `timeout_or_crash` (no
   rerun, per protocol).
3. **Correlated regressions at `delta = 1`: `sblrc` (DA 1/3), `earnings`
   (DA 2/3, stan-style 0/3), `kidiq` (paper 1/3).** The DA step collapses
   to 0.003 on `sblrc`/`earnings` (bulk ESS 200–370 on `sblrc`; 350–480
   depth-10 caps per seed on `earnings`); the stan-style arm's Stan initial
   step and metric prior give 6x the ESS/gradient on `sblrc` and 2x on
   `earnings` but leave R-hat at 1.03 on `earnings` (parity finding
   reproduced) — and on seed 78103 one `earnings` chain sticks (R-hat 1.5)
   in every arm, from the same start.
4. **`accel_gp`, centered eight schools, `one_comp`, `hmm_drive_0`: fail for
   every sampler**, ours by R-hat/ESS (the 66-d GP adapts to `h ~ 0.008`
   and reaches bulk ESS 30–140; `one_comp` tail ESS 55–256), CmdStan and
   nutpie by divergences. oWALNUTS has zero divergences on all four; on the
   centered eight schools it is again the only sampler with single-digit
   divergence counts (v1's P2 pattern).
5. **Efficiency on the healthy models is 0.4–0.9x CmdStan per gradient**
   with no exception (mesquite 0.73, kidiq 0.49, nes 0.55, arK 0.74, garch
   0.53, hmm_example 0.38–0.62, diamonds 0.89) — the kernel-side gap named
   in `adaptation_parity_v1`, unchanged here.

## Appendix C (paper arm) versus dual averaging

Under the v1 decision rule (geomean paper/DA min-bulk-ESS/gradient >= 1 and
at least as good on every model): geomean **0.995** over 17 models, at
least as good on 13/17, losing `kidiq` (1/3 vs 3/3), `sblrc`, `hmm_drive_0`
(1/3 vs 2/3) and `accel_gp` (0.53x). The v4 rule does what
`paper_adaptation_robust_v1` promised — no freeze that the DA arm does not
share, 0.9–1.3x DA per gradient on the regressions, fewer gradients on 9
models — but it is not better than dual averaging on this set and loses two
cells to single stuck chains (`kidiq` 78103 chain 4 at `h 0.018`,
`hmm_drive_0` 78101). The v1 verdict "not by default" stands, for a different
reason: parity, not collapse.

## Predictions

| | prediction | result |
|---|---|---|
| P1 | DA arm passes >= 33/51 | **32** — missed by one cell (v1: 26) |
| P2 | DA geomean ESS/gradient vs CmdStan >= 0.45 | **0.233** over 17 models; 0.447 over the 15 without a frozen chain (post hoc) — not held |
| P3 | DA wall per gradient <= 1.5x CmdStan | **0.771x** — held (v1 build was ~3x) |
| P4 | paper arm has no frozen cell | **5 frozen cells** (`arma11` x3, `lotka_volterra` x2), all shared with the DA arm — not held |
| P5 | zero oWALNUTS cells lost to fatal NaN or start failure | **0** — held (v1: 12) |

Ungated expectations: the stan-style arm is above DA on geomean
ESS/gradient (0.32x vs 0.23x CmdStan) with R-hat misses on `earnings` (all
seeds) and `kidiq` (one seed) — as expected; centered eight schools,
`accel_gp` and `one_comp` fail for every arm — as expected.

## v1 -> v2 (what each fix bought)

| arm | v1 cells | v2 cells | geomean ESS/grad v2/v1 | geomean ESS/s v2/v1 |
|---|---:|---:|---:|---:|
| owalnuts-da | 26 | 32 | 1.22 | **3.81** |
| owalnuts-paper | 8 | 29 | 13.9 | 55 |
| cmdstan | 34 | 35 | 1.10 | 1.11 |
| nutpie | 29 | 27 | 0.87 | 0.71 |

Per model (`artifacts/results-table.md`): depth 10 gives `diamonds` 8.2x
and `earnings` 12x ESS/gradient for the DA arm at 2.6–3x the gradients; the
build fix gives 7–22x ESS/s on the cheap-gradient models (arK 10x,
hmm_example 22x, eight schools 7x) at identical gradient counts; `sblrc` is
2.1x; `kidiq` and `garch` lose 15% (seed spread; `h0 = 0.5` vs 0.1 is the
only setting change there). `lotka_volterra` DA went from "start not
evaluable" errors to frozen chains (1/3 both times). CmdStan and nutpie
reproduce v1 within seed noise (nutpie's `lotka_volterra` crash and one
`kidiq` seed account for its two lost cells).

## Deviations and caveats

* No driver restart was needed (one continuous run, 61 minutes).
* nutpie `lotka_volterra` seed 78102 panicked inside `nuts-rs` and poisoned
  the sampler mutex, killing the child process; seed 78103 was therefore
  never attempted. Both are recorded as `timeout_or_crash` cells; per the
  protocol nothing was rerun.
* The v1 environment (venv, posteriordb checkout, compiled models) was gone
  with its worktree; everything was rebuilt from the same package versions
  (BridgeStan 2.9.0, nutpie 0.16.8, cmdstanpy 1.3.0, ArviZ 0.23.4,
  posteriordb `28f8d3d`), so no v1 library was reused.
* Walls: shared 16-thread machine with other agents active; CmdStan's wall
  includes process launch and CSV writing (favours the in-process samplers
  on the sub-second models); nutpie's BridgeStan backend is built with
  `STAN_THREADS` (its own requirement), which is most of its ESS/s deficit.
* Raw draws (`artifacts/draws/`) are hashed in `CHECKSUMS.sha256` and not
  committed; CmdStan CSVs are neither.

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan nutpie arviz cmdstanpy posteriordb numpy pandas xarray
git clone --depth 1 https://github.com/stan-dev/posteriordb   # commit 28f8d3d
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py run      # ~1 h; resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py analyze
.venv/Scripts/python checksums.py
```

CmdStan 2.39.0 is expected at `CMDSTAN_HOME` in `run_posteriordb.py`.
