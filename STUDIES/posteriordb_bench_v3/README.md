# posteriordb benchmark v3 — the v2 protocol on the WP24 warmup default, fresh seeds

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`, committed at
`14cdb4b` before the first evidence cell), executed 2026-09-02 14:41–15:34
local on kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` with the
`sampler` default `DEFAULT_WARMUP_EXHAUSTION = AcceptUnlessDivergent` (WP24,
`STUDIES/freeze_mode_v1`). All 204 cells (17 posteriors x 4 arms x 3 seeds
79101–79103) are present; every failure is a cell. Per-cell numbers:
`artifacts/summary.json`; tables: `artifacts/results-table.md`; hashes:
`CHECKSUMS.sha256`.

Everything is v2 (`STUDIES/posteriordb_bench_v2`) except: the harness is
rebuilt against the current `src/` (so `Adaptation::DualAveraging` applies
the one-sided exhaustion rule to warmup transitions; retained transitions
keep the frozen `Stop` rule and the kernel revision is unchanged), the seeds
are fresh, the paper arm is dropped, and every model is compiled fresh
(the v2 libraries were in a removed worktree). Arms: **owalnuts-da**
(`Tuning::default()`: `h0 0.5`, depth 10, 4 levels, `delta 1`;
`Metric::diagonal()`; dual averaging 0.8; `Init::uniform()`;
`ReplicatedStanTarget` on a non-`STAN_THREADS` BridgeStan build),
**owalnuts-stan-style** (`Adaptation::Custom(WarmupConfig::stan_style(0.8))`,
used as given, i.e. still two-sided — the within-study control), **cmdstan**
2.39.0 defaults, **nutpie** 0.16.8 defaults. Gates: rank R-hat <= 1.01, bulk
and tail ESS >= 400 on every reference parameter, zero sampling divergences.

## Verdict

**The WP24 default does what it was built for and nothing else changed:
`arma11` goes from 0/3 to 2/3 and `lotka_volterra` from 1/3 to 3/3, the DA
arm passes 35/51 (v2 32; CmdStan 37), no oWALNUTS DA chain is frozen on any
model, and the models the rule does not touch reproduce v2 within seed
noise (v3/v2 ESS/gradient 0.85–1.32 on 11 of them) — except `hmm_drive_0`,
where two of three seeds land a chain in a second mode (v2: one of three),
and `sblrc`, which sits on the ESS gate at the collapsed DA step (0/3 vs
1/3).** The per-gradient geometric mean against CmdStan rises from 0.233x to
**0.344x** over all 17 models, short of the preregistered 0.40, and the two
regressions are the reason: excluding `hmm_drive_0` alone it is 0.452x,
excluding `sblrc` too 0.516x. Three of five predictions held (P1 gates, P2
`arma11`, P5 wall per gradient 0.75x); P3 (>= 0.40x per gradient) and P4
(no model below 0.8x v2) did not. The release gate for a breadth claim
(P1 + P3 + P5) is therefore still not met, now by the multimodal
`hmm_drive_0` seed draw and the `sblrc` step collapse rather than by frozen
chains.

## Headline (cells passing all gates / geometric mean of seed-median ratios)

| arm | cells passing | models 3/3 | ESS/grad vs CmdStan | ESS/s vs CmdStan | wall/grad vs CmdStan | ESS/grad vs nutpie | ESS/s vs nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-da | **35**/51 | 10 | **0.344** (17 models) | 0.492 | **0.751** | 0.296 (16) | **1.350** |
| owalnuts-stan-style | 29/51 | 6 | 0.346 | 0.462 | 0.792 | 0.308 | 1.309 |
| cmdstan | 37/51 | 11 | 1 | 1 | 1 | — | — |
| nutpie | 31/51 | 10 | — | — | — | 1 | 1 |

v2 for comparison: owalnuts-da 32/51, 0.233x CmdStan per gradient, 0.307x
per second, 0.771x wall per gradient, 1.108x nutpie per second;
owalnuts-stan-style 32/51, 0.319x; cmdstan 35/51; nutpie 27/51. Post hoc,
for orientation only: DA 0.452x CmdStan per gradient over the 16 models
without `hmm_drive_0` (0.65x per second), 0.516x over the 15 without
`hmm_drive_0` and `sblrc`; 0.334x over the 15 v2-healthy models (v2: 0.447x
on the same set — the `hmm_drive_0` and `sblrc` draws account for the whole
difference).

## Per-model table (seed medians of the per-cell minimum over reference parameters)

`gates` = seeds passing / 3 with the failing gate(s) in parentheses; then
bulk ESS/grad x1e3 (warmup included) and bulk ESS/s (warmup included);
`div` = sampling divergences per seed where nonzero; `frozen` = chains with
> 500 retained refinement exhaustions.

| model | owalnuts-da | owalnuts-stan-style | cmdstan | nutpie |
|---|---|---|---|---|
| eight_schools noncentered | **3/3** / 29.1 / 61,764 | 3/3 / 25.8 / 59,376 | 2/3 (div 2,0,0) / 33.8 / 13,486 | 0/3 (div 2,3,2) / 39.1 / 9,482 |
| eight_schools centered | 0/3 (div 9,3,9; R-hat 1.09) / 0.231 / 482 | 0/3 (div 1,4,0; R-hat 1.06) / 0.451 / 897 | 0/3 (div 31,62,70) / 1.07 / 607 | 0/3 (div 25,28,48) / 0.901 / 279 |
| diamonds | **3/3** / 0.156 / 11 | 2/3 (R-hat 1.013) / 0.173 / 13 | **3/3** / 0.219 / 18 | 1/3 (R-hat 1.014; bulk 317) / 0.194 / 14 |
| earnings | **3/3** / 0.177 / 18 | 0/3 (R-hat 1.02–1.03; bulk 179–209) / 0.477 / 38 | **3/3** / 0.756 / 78 | 3/3 / 0.903 / 72 |
| mesquite | 3/3 / 3.03 / 3,490 | 3/3 / 2.94 / 2,577 | **3/3** / 3.43 / 2,942 | 3/3 / 4.34 / 1,333 |
| kidiq | 3/3 / 2.16 / 667 | 1/3 (R-hat 1.011–1.013) / 2.26 / 751 | **3/3** / 4.50 / 1,225 | 3/3 / 6.12 / 1,133 |
| sblrc | 0/3 (bulk ESS 205–280; R-hat 1.014–1.036) / 0.413 / 490 | 2/3 (tail 362) / 4.21 / 6,355 | 3/3 / 6.58 / 4,421 | **3/3** / 13.7 / 4,488 |
| nes2000 | 3/3 / 2.50 / 249 | 3/3 / 2.75 / 231 | 3/3 / 4.92 / 464 | **3/3** / 5.70 / 442 |
| arK | 3/3 / 7.75 / 1,519 | 3/3 / 7.78 / 1,561 | **3/3** / 10.4 / 1,567 | 3/3 / 11.4 / 219 |
| arma11 | **2/3** (79103: one chain at h 5e-8, R-hat 1.60) / 14.0 / 5,351 | 0/3 (frozen x3; div 3000,2000,2000) / 0.021 / 6 | 2/3 (R-hat 1.59 on one seed) / 72.0 / 13,240 | **3/3** / 133 / 2,017 |
| garch11 | 3/3 / 15.0 / 3,185 | 2/3 (R-hat 1.011) / 14.7 / 2,764 | **3/3** / 20.9 / 2,804 | 3/3 / 25.8 / 465 |
| gp_pois_regr | 2/3 (tail 394) / 0.731 / 403 | **3/3** / 0.812 / 398 | 0/3 (div 3,7,9) / 1.07 / 533 | 0/3 (div 130,177,145) / 0.883 / 213 |
| hmm_example | 3/3 / 9.77 / 896 | 3/3 / 16.8 / 1,493 | **3/3** / 20.9 / 1,442 | 3/3 / 27.7 / 129 |
| hmm_drive_0 | 1/3 (R-hat 1.12, 1.31: one chain in a second mode) / 0.281 / 5 | 2/3 (R-hat 1.012) / 16.3 / 237 | **3/3** / 64.6 / 795 | 3/3 / 67.0 / 123 |
| one_comp_mm_elim_abs | 0/3 (tail ESS 368–390; R-hat 1.011) / 9.08 / 41 | 1/3 (R-hat 1.04; bulk 139) / 6.45 / 30 | 0/3 (div 4,6,7; tail 184) / 12.8 / 45 | 0/3 (div 28,268,12) / 4.66 / 5 |
| lotka_volterra | **3/3** / 3.31 / 77 | 1/3 (frozen x1 on 79103; R-hat 1.012 on 79102) / 1.89 / 43 | **3/3** / 3.48 / 82 | 0/3 (crashed on 79101; 79102–79103 not run) / — / — |
| accel_gp (66-d) | 0/3 (R-hat 1.06–1.09; bulk 33–95) / 0.069 / 11 | 0/3 (R-hat 1.18) / 0.019 / 2 | 0/3 (div 91,78,42) / 0.210 / 37 | 0/3 (div 102,123,123) / 0.194 / 10 |

Agreement with the posteriordb reference: every cell of every arm is within
max |z| 4 except one `one_comp` cell per arm (all four samplers, |z| 4.0–4.6,
the model where every sampler has tail ESS < 400) and one CmdStan centered
eight schools cell; no oWALNUTS cell is flagged on a model it passes.

### Where oWALNUTS wins

* **Outright** (gates >=, higher ESS/gradient *and* ESS/s): `one_comp`
  against nutpie (0/3 both; 2x per gradient, 8x per second). None against
  CmdStan (0 of 17 models won on ESS/gradient; 3 on ESS/s — both eight
  schools variants and garch/mesquite by wall, where CmdStan's wall is
  process launch).
* **On gates against CmdStan**: noncentered eight schools (3/3 vs 2/3, zero
  divergences) and `gp_pois_regr` (DA 2/3, stan-style 3/3 vs 0/3 with
  divergences); against nutpie also `diamonds` (3/3 vs 1/3) and
  `lotka_volterra` (3/3 vs crash).
* **On ESS per second against nutpie**: 10 of 16 models (geomean 1.35x),
  the `STAN_THREADS` cost on nutpie's BridgeStan backend as in v2.

### What the WP24 rule changed

1. **`arma11`: 0/3 -> 2/3, no frozen chain.** Every chain that would have
   pinned escapes during warmup (114–455 warmup divergences per cell are the
   one-sided slides; zero retained exhaustions; final steps 0.09–0.13 on 11
   of 12 chains); min bulk ESS 1,468 and 1,633 on the two passing seeds,
   14.0 x1e-3 ESS/gradient against v2's 0.033 (424x). The failing seed
   79103 is a new mode: chain 3 escapes the pin (it moves; zero
   exhaustions, so it is not "frozen" by the study definition) but ends
   warmup at `h = 5e-8` with 794 of its 1,000 retained orbits at the depth
   cap and 2,162 recoverable failures — a crawl through the overflow wall,
   the `lotka_volterra` 78102 mode of `freeze_mode_v1` on this model. The
   stan-style control, two-sided as in v2, freezes 7 of 12 chains exactly as
   the v2 seeds did (final steps 1e-20 to 1e-63), so the recovery is the
   rule and not the seeds. CmdStan itself fails one seed here (R-hat 1.59).
2. **`lotka_volterra`: 1/3 -> 3/3** (min bulk ESS 898–1,133, 0.95x CmdStan
   per gradient, 0.94x per second). No 79xxx seed drew a start on the
   `rk45` failure boundary for the DA arm; the stan-style arm did on 79103
   (one chain at `h = 5e-4`, 1,000 exhaustions — the only frozen oWALNUTS
   cell outside `arma11`).
3. **Everything else within seed noise**, as the rule's construction
   predicts (it changes nothing where no warmup leaf exhausts): v3/v2 DA
   ESS/gradient ratios arK 0.99, diamonds 0.85, earnings 1.01, noncentered
   eight schools 1.10, garch 1.32, gp_pois_regr 1.04, hmm_example 1.10,
   kidiq 0.98, mesquite 0.97, nes 0.94, accel_gp 1.23, one_comp 2.09
   (tail-ESS bound), centered eight schools 0.41 (fails everywhere; bulk
   ESS 36–60 vs 23–161, the one model where retained leaves exhaust).
   CmdStan's own v3/v2 ratios span 0.74–1.93 on the same models.

### What regressed, and why it is not the rule

* **`hmm_drive_0` (DA 2/3 -> 1/3, ESS/gradient 12.1 -> 0.281 x1e-3, 0.02x
  v2).** On 79101 and 79103 one chain of four sits in a second mode of the
  two-state HMM (R-hat 1.12 and 1.31; min bulk ESS 26 and 10 on
  `phi`/`lambda`) — v2 had the same on one seed (78103, R-hat 1.27). The
  cells are otherwise healthy: zero exhaustions in warmup or sampling,
  final steps 0.27–0.44, gradient counts 89–94k identical to v2; the rule
  had nothing to act on. The stan-style control went the other way on the
  same starts (v2 2/3 -> v3 3/3 after its own R-hat 1.43 seed in v2), and
  CmdStan's ratio here is 1.93 — this model's seed-median is a coin flip on
  which mode the four uniform(-2, 2) starts fall into, and it is the
  entire P3 miss (0.344 -> 0.452 without it).
* **`sblrc` (DA 1/3 -> 0/3, 0.67x v2).** The DA step collapses to 0.003 on
  every chain in both versions (v2 finding 3); bulk ESS 205–280 against v2's
  202–425, straddling the 400 gate; the stan-style arm at `h ~ 0.1` passes
  2/3 in both versions. A kernel/adaptation problem recorded in v2, not a
  warmup-rule effect.
* **Centered eight schools 0.41x v2**: fails every arm in both versions
  (bulk ESS 23–161 in v2, 36–60 here); listed by the P4 rule, not a gate
  change.

### What still fails for everyone

`accel_gp` (66-d GP: oWALNUTS R-hat 1.06–1.18 at `h ~ 0.008`; CmdStan and
nutpie 42–123 divergences), centered eight schools (oWALNUTS single-digit
divergences, R-hat 1.06–1.09; NUTS 25–70 divergences), `one_comp` (tail
ESS < 400 for every arm; CmdStan and nutpie also diverge). Efficiency on the
healthy models is 0.47–0.88x CmdStan per gradient (mesquite 0.88,
noncentered eight schools 0.86, arK 0.75, garch 0.72, diamonds 0.71,
gp_pois_regr 0.68, nes 0.51, kidiq 0.48, hmm_example 0.47), plus the
correlated regressions `earnings` (0.23x, 280–430 depth-10 caps per seed
at `h = 0.003`) and `sblrc` (0.06x): the kernel-side gap of
`adaptation_parity_v1`, unchanged.

## Predictions

| | prediction | result |
|---|---|---|
| P1 | DA arm passes >= 33/51 | **35** — held (v2 32) |
| P2 | DA `arma11` >= 2/3 | **2/3** — held (v2 0/3; 79103 crawls at h 5e-8) |
| P3 | DA geomean ESS/gradient vs CmdStan >= 0.40 over 17 | **0.344** — not held (v2 0.233; 0.452 without `hmm_drive_0`, post hoc) |
| P3b | >= 0.45 over 16 excluding `lotka_volterra` | **0.323** — not held (`lotka_volterra` is now 0.95x, so excluding it lowers the mean) |
| P4 | no model below 0.8x its v2 DA ESS/gradient | **not held**: `hmm_drive_0` 0.02x (second-mode chains on 2 seeds), `eight_schools_centered` 0.41x (fails everywhere), `sblrc` 0.67x (gate-straddling step collapse); the other 14 are 0.85–1.32x or improved |
| P5 | DA wall per gradient <= 1.0x CmdStan | **0.751x** — held (v2 0.771) |

Ungated expectations: `lotka_volterra` 3/3 (within the expected 1/3–3/3);
centered eight schools, `accel_gp`, `one_comp` fail for every arm — as
expected; stan-style freezes on `arma11` (7 of 12 chains) — as expected.

## v2 -> v3

| arm | v2 cells | v3 cells | geomean ESS/grad v3/v2 | geomean ESS/s v3/v2 |
|---|---:|---:|---:|---:|
| owalnuts-da | 32 | 35 | **1.51** | 1.41 |
| owalnuts-stan-style | 32 | 29 | 1.11 | 0.90 |
| cmdstan | 35 | 37 | 1.03 | 0.88 |
| nutpie | 27 | 31 | 0.89 | 0.81 |

The DA geomean gain is `arma11` (424x) and `lotka_volterra` (131x) against
`hmm_drive_0` (0.02x); the other 14 models are 0.41–2.09x with 11 inside
0.85–1.32x. CmdStan and nutpie reproduce v2 within seed noise (CmdStan
`hmm_drive_0` 1.93x, `accel_gp` 0.74x; nutpie gained `kidiq` and `arma11`
cells and lost `lotka_volterra` to the same `nuts-rs` panic as v2). The
stan-style arm lost cells to R-hat 1.011–1.013 misses (`diamonds`, `garch`,
two `kidiq` seeds) and to its `lotka_volterra` freeze, gaining `hmm_drive_0`
and `one_comp`.

## Deviations and caveats

* No driver restart was needed (one continuous run, 53 minutes).
* nutpie `lotka_volterra` seed 79101 panicked inside `nuts-rs` ("Failed to
  constrain the parameters of the draw", poisoned mutex) and killed the
  child process before 79102 and 79103 ran; all three are `timeout_or_crash`
  cells; per the protocol nothing was rerun.
* The v2 compiled models, venv and posteriordb checkout no longer existed;
  everything was rebuilt from the same package versions (BridgeStan 2.9.0,
  nutpie 0.16.8, cmdstanpy 1.3.0, ArviZ 0.23.4, posteriordb `28f8d3d`).
* Walls: shared 16-thread machine with other agents active; CmdStan's wall
  includes process launch and CSV writing; nutpie's BridgeStan backend is
  built with `STAN_THREADS`.
* Raw draws (`artifacts/draws/`) are hashed in `CHECKSUMS.sha256` and not
  committed; CmdStan CSVs are neither.

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 nutpie==0.16.8 arviz==0.23.4 cmdstanpy==1.3.0 posteriordb numpy pandas xarray
git clone --depth 1 https://github.com/stan-dev/posteriordb   # commit 28f8d3d
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py run      # ~1 h; resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_posteriordb.py analyze
.venv/Scripts/python checksums.py
```

CmdStan 2.39.0 is expected at `CMDSTAN_HOME` in `run_posteriordb.py`.
