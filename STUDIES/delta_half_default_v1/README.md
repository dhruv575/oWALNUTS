# delta_half_default_v1 (WP42): is `delta = 0.5` free at eight levels?

Preregistered in `PREREGISTRATION.md` / `protocol.json` (committed `e403bb88`
before the first evidence cell). Seeds 942101–942103; 17 posteriordb
posteriors x 3 arms x 3 seeds = 153 cells, all present, all `status ok`;
9 funnel cells; 9 Eight Schools cells. Run 2026-10-24 on `wt/delta-half`
(base `3583d130`), kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`.

## Verdict: not supported, `delta = 1` stays the default

**No arm meets the rule.** `delta = 0.5` buys the funnel efficiency it was
expected to buy (**1.385x** the default's minimum bulk ESS per gradient, all
`|z| <= 0.86`) but costs on ordinary posteriors: geomean **0.936x** over the 17
models (rule 0.95), **seven** models below 0.85x (`accel_gp` 0.22, `hmm_drive_0`
0.61, `arK` 0.70, `kidiq` 0.76, `mesquite` 0.77, `hmm_example` 0.79,
`one_comp` 0.79), and **38 vs 41** gated cells. The 0.936 is flattered by
one seed lottery (`lotka_volterra` 7.94x, from 103x on seed 942103 where the
`d1` cell's chains disagreed and min ESS was 7); over the 14 models that pass
or nearly pass the gates in every arm (excluding `lotka_volterra`, `accel_gp`
and the centered eight schools) `d05` is **0.861x**. `delta = 0.75` is close to free on those 14 models (**0.995x**) but
its funnel gain is only **1.142x** (rule 1.3), and over all 17 it is 0.864x
with 40 gates.

| arm | R1 geomean (17) | R2 min model | R3 gates | R4 funnel z | R5 funnel ESS/grad | rule |
|---|---|---|---|---|---|---|
| `d1` (default) | 1.000 | — | 41/51 | +0.90, +1.75, +0.76 | 1.000 | — |
| `d075` | 0.864 (fail) | 0.24 `lotka_volterra` (fail) | 40 (fail) | +0.89, +0.87, +0.38 (pass) | 1.142 (fail) | **not met** |
| `d05` | 0.936 (fail) | 0.22 `accel_gp` (fail) | 38 (fail) | −0.62, −0.00, −0.86 (pass) | 1.385 (pass) | **not met** |

Descriptive (not in the rule): geomean over the 14 non-pathological models
`d075` 0.995x, `d05` 0.861x; Eight Schools strict track `d075` 0.956x,
`d05` 0.891x.

## What lower `delta` does on ordinary posteriors

* **Refinement engages more, but stays shallow.** Median refined-leaf
  fraction 0.0019 (`d1`) → 0.0054 (`d075`) → 0.0217 (`d05`); nearly all of it
  at level 1 (max level built 1–2 on 16 of 17 models in every arm; the
  centered eight schools reached 4 at `d1` and 5 at `d05`).
* **The cost is the reverse-coarser stop, not the extra micro steps.** Median
  fraction of retained transitions ending in a reverse-coarser stop 0.025 →
  0.075 → **0.166**. Total gradients go *down* (geomean 0.97x and 0.94x;
  `accel_gp` 0.62x, `gp_pois_regr` 0.85x) because orbits end earlier, and ESS
  falls faster than gradients. This is the WP34/WP39 mechanism: on a smooth
  leaf-error population a tighter `delta` turns more leaves into
  refinement-plus-reverse-check events, and the reverse check truncates.
* **The step does not move.** Adapted `h` 1.008x (`d075`) and 1.014x (`d05`)
  of `d1`, geomean over models.
* **Losses land on the smooth models**, not on the stiff ones that were
  predicted: `hmm_drive_0`, `arK`, `kidiq`, `mesquite`, `hmm_example`,
  `one_comp` (0.61–0.79). `gp_pois_regr` (1.08x ESS/gradient; but 1/3 gates
  against 3/3), the noncentered eight schools (0.97x) and `diamonds` (0.97x)
  were roughly neutral; `arma11` gained (1.21x). `accel_gp` fails the gates in
  every arm, but its loss looks real (min ESS 66–453 at `d1`, 95–116 at `d075`,
  17–71 at `d05`; the model where refinement does real work, as with
  `delta = 2` in WP34). `lotka_volterra` is a seed lottery (min ESS about 7 on
  one or two seeds of every arm, with 999–1,998 exhaustions from a frozen
  chain) whose ratios (0.24x, 7.94x) carry no signal. R2 fails on six models
  at `d05` even without these two.
* **Health**: retained exhaustions zero on 15 of 17 models in every arm (only
  the centered eight schools and `lotka_volterra`); depth caps only on
  `diamonds` (1,629 / 979 / 1,338) plus one cap on `accel_gp` at `d075`;
  retained divergences 1 / 4 / 0.

## Funnel (the number this study exists for)

4 x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`. Efficiency = minimum
over the ten coordinates of bulk ESS (always `omega`) per target call,
warmup included, geomean over seeds.

| arm | P(omega<-5) per seed (z) | omega R-hat | min ESS/call x1e3 | ratio | final h range | div / exh / caps (3 seeds) |
|---|---|---|---:|---:|---|---|
| `d1` | 0.0552 (+0.90), 0.0624 (+1.75), 0.0545 (+0.76) | 1.003, 1.003, 1.003 | 0.1166 | 1.000 | 0.032–0.153 | 8 / 119 / 152 |
| `d075` | 0.0551 (+0.89), 0.0549 (+0.87), 0.0505 (+0.38) | 1.004, 1.007, 1.010 | 0.1331 | 1.142 | 0.042–0.217 | 6 / 88 / 79 |
| `d05` | 0.0438 (−0.62), 0.0478 (−0.00), 0.0432 (−0.86) | 1.006, 1.001, 1.010 | 0.1615 | 1.385 | 0.091–0.222 | 6 / 222 / 40 |

The per-chain step collapse that opened the question **did not reproduce at
`d1` on these seeds**: no chain ended below `h = 0.032` (WP28 saw one chain
per seed at 0.007–0.019) and every `omega` R-hat is 1.003. `d05` still raises
the smallest per-chain step about 3x (0.091 against 0.032) and has the
tightest tail estimates, which is where its 1.385x comes from; but the gain is
at the low end of what WP28 suggested (about 2.5x `omega` ESS per call), and
the default is not as badly off on fresh seeds as the open question assumed.

## Predictions

| prediction | result | held? |
|---|---|---|
| P1 refined fraction `d075` 0.003–0.008, `d05` 0.006–0.03 | 0.0054, 0.0217 | held |
| P1 rc-stop median `d075` 0.04–0.08, `d05` 0.06–0.15 | 0.075, **0.166** | `d075` held, `d05` failed (higher) |
| P1 `d1` max level <= 3 on >= 14 models | 16 of 17 | held |
| P1 `d05` at least one level deeper on >= 8 models | 4 models | failed |
| P2 `h` ratio 0.90–1.02 | 1.008, 1.014 | held |
| P3 `d05` geomean 0.75–0.92 | 0.936 (0.861 without the three lotteries) | failed as stated |
| P3 `d075` geomean 0.88–0.98 | 0.864 (0.995 without the three) | failed as stated |
| P3 largest losses on `accel_gp`, `gp_pois_regr`, noncentered 8s, `diamonds` | `accel_gp` 0.22 yes; others 0.97–1.08 | mostly failed: losses were on smooth models |
| P3 `d05` gradients overhead (`accel_gp` 1.15–1.6x, `gp_pois_regr` 1.1–1.4x, median 1.02–1.15x) | 0.62x, 0.85x, geomean 0.94x | failed: gradients fell (earlier orbit stops) |
| P4 gates within −4..+2 of `d1`; `d1` 42–45 | −1, −3; `d1` 41 | held; `d1` count failed by one |
| P4 exhaustions zero on >= 14 models, caps only `diamonds` | 15 of 17; `diamonds` (+1 `accel_gp` cap at `d075`) | held |
| P5 all `|z| <= 2` | max 1.75 | held |
| P5 funnel ESS `d05` 1.5–4x, `d075` 1.1–2.5x | 1.385, 1.142 | `d05` failed (low), `d075` held |
| P5 `d1` >= 2 seeds with a chain at `h < 0.02`; `d05` <= 1 | 0 and 0 | `d1` failed, `d05` held |
| P6 Eight Schools `d05` 0.85–0.95x, `d075` 0.92–1.0x | 0.891, 0.956 | held |
| P7 no arm qualifies; `d05` passes R4/R5, fails R1/R2 | as predicted | held |

## Recommendation

* Keep `delta = 1` in `Tuning::default()`. No library change.
* Keep `delta = 0.5` as the documented opt-in for funnel-like targets, with
  the measured price: about 1.4x funnel efficiency, about 0.86x on smooth
  posteriors, and more reverse-coarser stops (0.17 of transitions).
* Close open question 3 as a default-change line: lower fixed `delta` is
  not free at eight levels. What remains of it is the step-collapse
  phenomenon itself, which did not appear on three fresh seeds and should be
  characterised by frequency (more seeds at `d1`) before more interventions
  are designed around it. A target-adaptive `delta` (open question 4) would
  have to lower `delta` only where the leaf-error tail is local, since on the
  smooth models every tightening shows up as reverse-coarser truncation.

## Caveats

* Walls are **contended** (ten agents on 16 cores; `diamonds` cells took
  590–1,590 s against about 84 s in WP34). Wall numbers are recorded in the
  cells and not used. Gradients, ESS, R-hat and z are machine-independent.
* BridgeStan models were compiled in two parallel build processes (not
  evidence; built before the grid started). The only pre-freeze run was a
  funnel smoke test on seed 1, not kept.
* The Python environment is a fresh `uv` venv: bridgestan 2.9.0, arviz
  0.23.4, numpy 2.4.6, xarray 2026.9.0, posteriordb 0.2.0 (posteriordb data at
  `28f8d3d`), Python 3.11.16. CmdStan not rerun; the "vs CmdStan v5" column in
  `artifacts/results-table.md` is cited from `posteriordb_bench_v5`.
* `artifacts/eight_schools/*.json` (full draws, 12 MB) and `artifacts/draws/`
  are checksummed but not committed; `run_delta_half.py checks` regenerates the
  Eight Schools cells bit-identically (three repetitions per seed are
  hash-checked).

## Files

`artifacts/results-table.md` (every table, every cell), `artifacts/summary.json`
(per-cell metrics, decision statistics, funnel and Eight Schools per seed),
`artifacts/cells/` (153 cells), `artifacts/funnel/` (9), run logs.

## Reproduce

```sh
cd STUDIES/delta_half_default_v1
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb.git posteriordb
git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
.venv/Scripts/python.exe run_delta_half.py build
.venv/Scripts/python.exe run_delta_half.py checks
.venv/Scripts/python.exe run_delta_half.py run
.venv/Scripts/python.exe run_delta_half.py analyze
.venv/Scripts/python.exe checksums.py
```
