# chain_rescue_v1 — warmup-time chain rescue: restart-from-best meets the preregistered flip rule, pooling does not (WP33)

Status: preregistered decision study (`PREREGISTRATION.md`, `protocol.json`,
committed at `8f6ef4c` before the implementation and before any cell),
executed 2026-09-03 16:09–18:01 local on branch `wt/chain-rescue`, kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` (unchanged; every
fingerprint holds), `sampler` at the post-WP31 defaults. All 72 posteriordb
cells (8 models x 3 arms x seeds 88101–88103) and the 9 funnel cells are
present; every failure is a cell. Per-cell numbers: `artifacts/summary.json`;
tables: `artifacts/results-table.md`; hashes: `CHECKSUMS.sha256`. Driver
`run_rescue.py`, harness `src/main.rs` (+ `src/arms.rs`), funnel
`src/bin/funnel.rs`.

## Question

After WP32, nearly every remaining oWALNUTS gate failure outside the two
fail-everywhere models is one chain out of four ruined by its start: a
second HMM mode (`hmm_drive_0`), the `arma11` overflow pin and crawl, the
`lotka_volterra` `rk45`-boundary freeze, the funnel neck. CmdStan and nutpie
run chains independently and have the same failures. Can warmup use the
other three chains to rescue the fourth, without touching the retained
draws and without biasing the posterior?

## Candidates

Both are opt-in through `WarmupConfig::with_chain_rescue(ChainRescueConfig)`
on the multi-chain diagonal driver, which now runs the chains window by
window on the Rayon pool (`ChainRun::start / advance / finish`; the plain
path is the same three calls back to back and is bit-identical) and meets
at the end of every slow metric window:

* **`restart`** (`ChainRescueConfig::restart_from_best()`): score every
  chain on the window just completed — its step after the boundary restart,
  the median and IQR of its selected states' log density. A chain is an
  outlier if its step is below 0.1x the chains' median step (**step rule**)
  or its median log density is more than 3 within-chain IQRs below the
  chains' median (**density rule**, one-sided). Each outlier is re-seeded
  from the largest-step non-outlier chain: one of that chain's window
  positions (drawn with the outlier's own RNG), its metric, step and dual
  averaging state; the cached evaluation is cleared. Nothing else changes.
* **`pool`** (`ChainRescueConfig::pool_at_boundaries()`): merge the chains'
  window Welford statistics exactly, regularise at the pooled count,
  install on every chain; the step becomes the median over chains and dual
  averaging restarts from it everywhere. No chain moves.

Every decision is a `ChainRescueUpdate` in `RunTelemetry::chain_rescues`.
Candidate C (start-quality retry) was preregistered as deferred and not run.

## Verdict

**`restart` meets the preregistered rule; `pool` does not.** On the 27
cells (24 posteriordb + 3 funnel) per arm:

| candidate | cells passed | `da` | C1 gain >= 3 | C2 min per-model ESS/grad ratio >= 0.9 | C3 new \|z\| > 3.5 | C4 funnel \|z\| <= 2 | flip |
|---|---:|---:|---|---|---|---|---|
| `restart` | **25** | 21 | **+4** | **1.00** (geomean 2.72) | none | +0.94, −0.77, −1.02 | **yes** |
| `pool` | 23 | 21 | +2 | 0.42 (`lotka_volterra`), 0.83 (`mesquite`) | none | +0.07, −0.51, +1.07 | no |

The default therefore changes: `sampler::DEFAULT_CHAIN_RESCUE =
ChainRescueConfig::restart_from_best()`, applied by
`Adaptation::DualAveraging` and `Adaptation::Paper` on the identity and
diagonal metrics with at least two chains (labelled final commit;
`tests/sampler_api.rs` pins it). `walnutpie::WarmupConfig::default()`,
`RunConfig` runs, the dense and structured facades, single-chain runs and
the kernel fingerprints are unchanged.

## Per model (seed medians; ESS/grad = min bulk ESS per target call x1e3)

| model | arm | gates | ESS/grad | vs `da` | min bulk ESS per seed | max R-hat per seed | max \|z\| per seed | rescued chains per seed |
|---|---|---|---:|---:|---|---|---|---|
| hmm_drive_0 | `da` | 2/3 | 19.5 | 1 | 13, 4180, 2355 | **1.230**, 1.002, 1.002 | 1.04, 1.61, 3.20 | — |
| | `restart` | 2/3 | 27.2 | 1.40 | 1277, 4289, 2289 | 1.007, 1.001, 1.002 | 2.32, 2.36, 1.93 | 2, 1, 1 |
| | `pool` | 3/3 | 18.6 | 0.95 | 3159, 3857, 3006 | 1.001, 1.002, 1.001 | 1.28, 1.94, 1.83 | pooled |
| arma11 | `da` | 2/3 | 1.11 | 1 | 3220, 1230, **7** | 1.001, 1.003, **1.598** | 0.52, 1.19, 1.16 | — |
| | `restart` | **3/3** | 19.5 | **17.6** | 3465, 3706, 3453 | 1.001, 1.001, 1.003 | 1.59, 0.99, 1.79 | 2, 2, 3 |
| | `pool` | 3/3 | 21.6 | 19.4 | 3961, 3822, 3644 | 1.001, 1.001, 1.002 | 0.95, 1.55, 1.21 | pooled |
| sblrc | `da` | 3/3 | 5.65 | 1 | 752, 905, 800 | 1.005, 1.004, 1.008 | 1.44, 0.99, 1.39 | — |
| | `restart` | 3/3 | 5.81 | 1.03 | 752, 905, 843 | 1.005, 1.004, 1.006 | 1.44, 0.99, 1.19 | 0, 0, 1 |
| | `pool` | 3/3 | 10.2 | 1.81 | 1185, 1379, 1284 | 1.004, 1.003, 1.004 | 2.37, 1.16, 1.52 | pooled |
| earnings | `da` | 3/3 | 0.600 | 1 | 1200, 1038, 745 | 1.003, 1.003, 1.006 | 0.82, 1.15, 0.99 | — |
| | `restart` | 3/3 | 0.608 | 1.01 | 1122, 1073, 745 | 1.002, 1.005, 1.006 | 0.89, 0.89, 0.99 | 1, 1, 0 |
| | `pool` | 2/3 | 0.704 | 1.17 | 1052, 921, 793 | 1.002, 1.004, **1.013** | 1.17, 0.85, 1.06 | pooled |
| lotka_volterra | `da` | **0/3** | 0.002 | 1 | **7, 7, 7** | **1.60, 1.60, 1.60** | 2.02, 1.17, 1.24 | — |
| | `restart` | **3/3** | 0.518 | **289** | 914, 1015, 996 | 1.004, 1.004, 1.003 | 1.42, 1.44, 1.45 | 2, 1, 3 |
| | `pool` | 0/3 | 0.001 | 0.42 | 7, 7, error | 1.58, 1.61, — | 1.78, 1.19, — | pooled |
| kidiq (control) | `da` | 3/3 | 3.94 | 1 | 1367, 1599, 1496 | 1.003, 1.005, 1.003 | 1.45, 2.62, 1.13 | — |
| | `restart` | 3/3 | 4.37 | 1.11 | 1367, 1579, 1467 | 1.003, 1.005, 1.004 | 1.45, 1.45, 0.63 | 0, 2, 1 |
| | `pool` | 3/3 | 3.75 | 0.95 | 1576, 1569, 1365 | 1.003, 1.004, 1.002 | 1.28, 2.45, 2.07 | pooled |
| mesquite (control) | `da` | 3/3 | 3.53 | 1 | 1435, 1284, 1320 | 1.002, 1.005, 1.003 | 2.33, 1.01, 1.90 | — |
| | `restart` | 3/3 | 3.53 | 1.00 | identical to `da` | | | 0, 0, 0 |
| | `pool` | 3/3 | 2.93 | 0.83 | 1135, 1604, 1078 | 1.004, 1.003, 1.004 | 1.06, 0.94, 0.87 | pooled |
| nes2000 (control) | `da` | 3/3 | 4.23 | 1 | 2040, 1827, 1723 | 1.002, 1.003, 1.002 | 1.43, 0.61, 2.23 | — |
| | `restart` | 3/3 | 4.23 | 1.00 | identical to `da` | | | 0, 0, 0 |
| | `pool` | 3/3 | 4.81 | 1.14 | 2105, 1825, 2052 | 1.003, 1.002, 1.002 | 1.91, 1.18, 1.53 | pooled |

Funnel (4 x 2,000 / 20,000; gate `|z| <= 2` and `omega` bulk ESS >= 400 and
R-hat <= 1.01):

| arm | seed | `P(omega < -5)` | z | `omega` ESS / R-hat | target calls | final steps | rescued | gate |
|---|---|---:|---:|---|---:|---|---|---|
| `da` | 88101 | 0.0570 | +0.94 | 463 / **1.012** | 3,756,644 | 0.068, 0.074, 0.144, 0.051 | — | fail (R-hat) |
| `da` | 88102 | 0.0434 | −0.77 | 745 / 1.009 | 3,321,318 | 0.098, 0.204, 0.151, 0.146 | — | pass |
| `da` | 88103 | 0.0417 | −0.83 | 591 / 1.007 | 4,618,881 | 0.023, 0.094, 0.154, 0.091 | — | pass |
| `restart` | 88101 | 0.0570 | +0.94 | 463 / 1.012 | 3,756,644 | identical to `da` | 0 | fail (R-hat) |
| `restart` | 88102 | 0.0434 | −0.77 | 745 / 1.009 | 3,321,318 | identical to `da` | 0 | pass |
| `restart` | 88103 | 0.0411 | −1.02 | 546 / 1.005 | 4,251,521 | 0.023, 0.094, 0.154, 0.118 | 1 (step, window 3) | pass |
| `pool` | 88101 | 0.0483 | +0.07 | 616 / 1.009 | 4,116,557 | 0.133, 0.126, 0.129, 0.031 | — | pass |
| `pool` | 88102 | 0.0433 | −0.51 | 555 / 1.003 | 4,801,591 | 0.039, 0.133, 0.131, 0.019 | — | pass |
| `pool` | 88103 | 0.0565 | +1.07 | 529 / 1.008 | 3,728,188 | 0.076, 0.034, 0.124, 0.137 | — | pass |

## What the rescues did (restart arm; every event is in `artifacts/results-table.md`)

23 chains were re-seeded over the 24 cells, 21 of them at the first slow
window boundary (transition 99) and two at the second (149); none later.

* **`lotka_volterra`** — the WP24 freeze on all three `da` seeds (one
  chain at `h` 1e-4–1e-3 with 840–998 retained exhaustions; 25, 3 and 13
  minutes per cell). `restart` caught the frozen chain by the step rule at
  transition 99 (`h` 5e-7 / 2e-5 against 0.01–0.02) or by density (median
  log density −1,717 / −4,406 against −188), plus one more chain at 149 on
  88103; every seed passes at min bulk ESS 914–1,015, and the three cells
  took 13 minutes against 40 (the 88101 cell 25 -> 5 min, 11.4M -> 1.8M
  target calls). Pooling never moves a chain and does nothing here: 0/3,
  and the 88103 cell's frozen-chain draws could not even be constrained
  (the ODE fails inside the transformed parameters: an `error` cell).
* **`arma11`** — the overflow pin. At transition 99 the pinned chains sit
  at `h` 1e-57–1e-9 with log densities of −1e10 to −1e119 (the `theta^400`
  region of WP27); the step rule moved two or three chains per seed onto
  the healthy chain's window. `da` escaped the pin on 88101/88102 and
  crawled on 88103 (R-hat 1.60, min bulk ESS 7, the CmdStan/nutpie failure
  of WP32); `restart` 3/3 at 0.30x the gradients, 17.6x per gradient.
* **`hmm_drive_0`** — the second-mode chain on 88101 (`da` R-hat 1.23,
  min bulk ESS 13) was caught by the density rule at transition 99 (median
  −2,009 and −1,963 against the mode's −1,880 range; two chains moved,
  source chain 0) and the cell has R-hat 1.007 — but the merged chain
  still mixes slowly (per-chain bulk ESS 123) and the cell misses the
  tail-ESS gate at **398.8**, so `restart` is 2/3 like `da`. Pooling passed
  the seed (3/3) without moving any chain; the pooled metric let the
  second-mode chain leave on its own.
* **`sblrc`, `earnings`** — one density rescue each at 99/149 on chains
  still descending (median log density −43,885 and −6,910 against the
  others), one step rescue on `earnings` 88102 (`h` 1e-4 -> 4.5e-3);
  ESS/gradient 1.01–1.03x, gates unchanged.
* **Controls** — `mesquite` and `nes2000`: no rescue fired and the draws
  are byte-identical to `da`. `kidiq`: the density rule fired on 88102
  (two chains, median log density −3,680 / −2,698 against −2,0xx) and
  88103 (one chain) at transition 99 — chains still in transit at the
  first boundary, which `da` would have converged on its own; the cells
  pass at 1.11x per gradient with max |z| unchanged (1.45 vs 1.45 median).
  **P1 failed** on the "at most one chain" clause; the "never after the
  second slow window" clause held everywhere.
* **Funnel** — `da` drew no neck-collapsed chain on these seeds (final
  steps within 2–7x); one step rescue on 88103 at window 3 (`h` 0.02 ->
  0.37) left the tail mass at z −1.02 and the ESS at 546. 88101 fails the
  gate on `omega` R-hat 1.012 for `da` and `restart` alike (no rescue
  fired, identical draws); pooling passes all three. **P2 failed** on the
  88101 R-hat, which no rescue addresses.

Reference agreement: no cell of any arm has |z| > 3.5; per-model medians
move by at most 0.7 (`hmm_drive_0` 1.61 -> 2.32, inside the 27-cell noise;
`da` itself has 3.20 on 88103). **P4 held.** **P3 held** (the density rule
fired on the second-mode chain at the first window; the cell passes
R-hat). **P5 failed** (`pool` 0.42x on `lotka_volterra`, 0.83x on
`mesquite`, 1.81x on `sblrc`; it did gain the `hmm_drive_0` and `arma11`
cells and lost `earnings` 88103). **P6 failed**: the rule was met, because
`da` drew the failure class on five of its 24 cells (three `lotka`, one
`arma11`, one `hmm`) rather than the one or two expected.

## Costs and caveats

* **Independence.** A chain the density rule merges into the others no
  longer carries its own mode into R-hat: on `hmm_drive_0` the rescue
  turned an R-hat of 1.23 into 1.007 by moving the chain, not by sampling
  the second mode. The posteriordb reference is unimodal there and the
  gates agree, but a user of a genuinely multimodal target must read
  `RunTelemetry::chain_rescues` (the harness JSON records every event) —
  a `LogDensity` rescue is the signal that R-hat has been made blind to
  something. The density rule also fires on chains that are merely late
  (kidiq, sblrc, earnings): harmless in effect, but it is a rescue that
  was not needed.
* **Cost when it does nothing.** A boundary with no outlier changes
  nothing; the run is the plain run (`mesquite`, `nes2000` byte-identical).
  The driver keeps the window's positions per chain (`window x dimension`
  doubles) and synchronises the chains at five boundaries: `sblrc` and
  `mesquite` walls are unchanged, `earnings` 68 s against 58 s over the
  three seeds on a machine shared with the CI build (walls are not gated).
* **Where it cannot help.** The funnel 88101 R-hat, the centered eight
  schools, `accel_gp`: not one-bad-chain failures. The rescued
  `hmm_drive_0` chain mixes slowly after the merge (tail ESS 399).
* **Pooling** is the wrong tool for a frozen chain (it never moves it) and
  changes every chain's metric: 0.83x on `mesquite`, an R-hat 1.013 on
  `earnings`; it remains opt-in.

## Deviations

* The driver process was killed twice by the tool harness that launched
  it (16:10:00 after `hmm_drive_0`/`da`/88103 had started; the funnel
  cells, which use only the compiled binary, ran to completion in between;
  and again after `lotka_volterra`/`restart`/88103 with no cell in
  flight). The interrupted cell was deleted and re-run from scratch
  (seeded; deterministic), the run relaunched detached, and the second
  launch's log appended to `artifacts/run-log.txt`. No cell was rerun for
  any other reason.
* The `wt/posteriordb-v4` worktree whose compiled models the protocol
  named was removed during the study; the eight models were recompiled
  here with the same BridgeStan 2.9.0 / flags (no `STAN_THREADS`) from the
  posteriordb checkout at `28f8d3d`, in a fresh venv (Python 3.11,
  bridgestan 2.9.0, arviz 0.23.4).
* The machine ran the crate's CI (clippy, tests) during part of the run;
  ESS per gradient is the gated metric, walls are reported.

## Reproduce

```
cd STUDIES/chain_rescue_v1
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_rescue.py prepare
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_rescue.py run       # 72 cells, ~1 h 40 min (lotka_volterra dominates)
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_rescue.py checks    # 9 funnel cells
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_rescue.py analyze
.venv/Scripts/python checksums.py
```
