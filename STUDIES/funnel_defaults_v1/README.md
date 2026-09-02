# funnel_defaults_v1 — the sampler defaults on Neal's funnel (WP28)

Evidence class: preregistered grid (`PREREGISTRATION.md`, `protocol.json`,
committed `ef62362` before the first evidence cell), fresh seeds
82101–82103, executed 2026-09-02 on kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, paper adaptation `v4`,
`Sampler` at its 0.2.0 defaults plus one override per arm. No kernel source
was modified; the decision is applied to `sampler::Tuning::default()` in the
labelled final commit.

## Question and answer

The README's funnel claim (tail mass 0.0474 vs exact 0.0478) is measured at
the paper's tuning or under Appendix C from `h = 0.1` with eight levels.
`STUDIES/freeze_mode_v1` measured the *sampler defaults* (`h0 = 0.5`, depth
10, **four** refinement levels, `delta = 1`, dual averaging 0.8, adapted
diagonal) and got half the exact mass. This study asks which cheap change to
the defaults, if any, makes `Sampler::new()` unbiased on the funnel without
losing throughput on ordinary targets.

**Answer: eight refinement levels.** `max_refinement_levels` 4 -> 8 puts
`P(omega < -5)` within `|z| <= 2` of 0.0478 on all three seeds (0.0412,
0.0346, 0.0897 against 0.0203, 0.0242, 0.0625 at four levels), cuts retained
refinement exhaustions from 2,933 to 113 and divergences from 54 to 8 over
the three seeds, at 1.08x the funnel's retained target calls, **1.05x** the
defaults' ESS per call on the noncentered Eight Schools and **1.00x** on the
100-D Gaussian (two of three Gaussian seeds are call-for-call identical: the
levels are a cap that those targets never reach). It is the preregistered
choice under rule 3.

The four-level default fails because dual averaging on the funnel adapts `h`
to 0.01–0.2 and the neck needs micro steps below `h / 16`: every leaf that
reaches it exhausts, the two-sided rule ends the orbit, and the chain rarely
enters. Eight levels (`h / 256`) reach it.

## Funnel grid

4 chains x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`, adapted
diagonal metric, 4 threads. `z` uses the ArviZ MCSE of the indicator
(`sd / sqrt(ESS_mean)`); seed medians elsewhere; health counts are sums over
the three seeds.

| arm | P(omega<-5) per seed (z) | all abs(z) <= 2 | var(omega) | bulk/tail ESS omega | bulk/tail ESS x1 | div / exhaust / depth-cap | retained calls (x defaults) | wall s | final h (chain mean) | final delta |
|---|---|---|---|---|---|---|---|---|---|---|
| `defaults` | 0.0203 (-3.52), 0.0242 (-3.75), 0.0625 (+0.30) | no | 7.90 | 143 / 225 | 76365 / 4246 | 54 / 2933 / 561 | 3,943,228 (1.00x) | 0.8 | 0.074 | 1.000 |
| **`levels8`** | 0.0412 (-0.34), 0.0346 (-1.43), 0.0897 (+1.00) | **yes** | 8.58 | 102 / 93 | 75011 / 4334 | 8 / 113 / 365 | 4,240,606 (1.08x) | 0.8 | 0.088 | 1.000 |
| `delta0.5` | 0.0403 (-0.65), 0.0126 (-6.04), 0.0206 (-3.50) | no | 7.47 | 259 / 248 | 58299 / 3641 | 268 / 11416 / 55 | 2,407,740 (0.61x) | 0.6 | 0.144 | 0.500 |
| `delta0.25` | 0.0081 (-8.85), 0.0212 (-3.45), 0.0348 (-1.33) | no | 7.58 | 393 / 348 | 59906 / 4649 | 19 / 12109 / 51 | 2,373,133 (0.60x) | 0.4 | 0.115 | 0.250 |
| `levels8+delta0.5` | 0.0376 (-1.88), 0.0397 (-0.80), 0.0413 (-0.68) | **yes** | 8.33 | 257 / 427 | 66515 / 3621 | 0 / 157 / 987 | 2,901,466 (0.74x) | 0.5 | 0.115 | 0.500 |
| `paper-4` | 0.0195 (-5.33), 0.0213 (-4.03), 0.0337 (-2.01) | no | 8.17 | 364 / 539 | 80937 / 4863 | 106 / 4436 / 172 | 2,225,555 (0.56x) | 0.5 | 0.130 | 1.459 |
| `paper-8` | 0.0432 (-0.53), 0.0459 (-0.18), 0.0293 (-2.72) | no | 8.61 | 338 / 509 | 78779 / 4793 | 0 / 4 / 157 | 2,695,442 (0.68x) | 0.5 | 0.113 | 1.460 |
| `stan-style` | 0.0255 (-3.65), 0.0182 (-7.35), **cell errored** | no | 8.03 | 254 / 327 | 42646 / 3166 | 2134 / 9039 / 83 | 2,179,277 (0.55x) | 0.5 | 0.156 | 1.000 |
| `nuts-1` (control) | 0.0058 (-11.76), 0.0000 (no draw below -5), 0.0000 | no | 5.09 | 190 / 53 | 43751 / 5032 | 5 / 78469 / 163 | 1,617,955 (0.41x) | 0.4 | 0.177 | 1.000 |

Per-chain tail mass and final `h` are in `artifacts/cells/funnel-*.json`.
Two things the pooled numbers hide:

* **Per-chain step collapse persists at eight levels.** In `levels8` one
  chain per seed adapts to `h` = 0.007–0.019 (the others 0.04–0.18); such a
  chain either never leaves the neck (seed 82103 chain 2: tail mass 0.163)
  or never enters it (82101 chain 3: 0.000). The pooled estimate is right
  and the `omega` R-hat is 1.027 / 1.011 / 1.037 (four levels: 1.042 /
  1.008 / 1.059), i.e. the chains still disagree beyond the 1.01 gate on two
  seeds, and the `omega` bulk ESS is ~100 per 80,000 draws. Eight levels fix
  the *bias*; they do not make the funnel *mix well* under dual averaging.
  `levels8+delta0.5` is the better funnel sampler (R-hat 1.005 / 1.017 /
  1.015, zero divergences, 0.74x the calls) but costs 21 % on the Gaussian,
  which the preregistered rule does not allow for a default.
* **Lowering `delta` alone makes the bias worse** (P4 held, more strongly
  than predicted): at four levels `delta = 0.5` and `0.25` raise retained
  exhaustions to 11,000–12,000 (the finest micro step is unchanged and the
  tighter test fails it more often) and the tail is short on two seeds each.

## Cost cells

Noncentered Eight Schools (strict-track density and starts) and a 100-D
standard Gaussian from `Init::uniform()`, 4 chains x 1,000 / 1,000, sampler
defaults plus the arm's override. The cost figure is mean bulk ESS over
coordinates per retained target call, seed median, as a ratio to `defaults`.

| arm | Eight Schools mean bulk ESS | retained calls | ESS/call (x defaults) | Gaussian mean bulk ESS | retained calls | ESS/call (x defaults) |
|---|---|---|---|---|---|---|
| `defaults` | 3514 | 31,948 | 0.1100 (1.00x) | 5238 | 28,552 | 0.1870 (1.00x) |
| **`levels8`** | 3386 | 28,590 | 0.1157 (**1.05x**) | 5238 | 28,552 | 0.1870 (**1.00x**) |
| `delta0.5` | 3295 | 33,183 | 0.0998 (0.91x) | 4643 | 31,867 | 0.1457 (0.78x) |
| `delta0.25` | 2885 | 40,188 | 0.0714 (0.65x) | 3606 | 55,962 | 0.0663 (0.35x) |
| `levels8+delta0.5` | 3244 | 31,718 | 0.1005 (0.91x) | 4635 | 32,397 | 0.1474 (0.79x) |
| `paper-4` | 3441 | 26,991 | 0.1274 (1.16x) | 5287 | 63,384 | 0.0767 (0.41x) |
| `paper-8` | 3233 | 26,865 | 0.1203 (1.09x) | 5412 | 74,616 | 0.0725 (0.39x) |
| `stan-style` | 3155 | 29,896 | 0.1035 (0.94x) | 6715 | 60,032 | 0.1151 (0.62x) |
| `nuts-1` | 3257 | 25,862 | 0.1260 (1.15x) | 5487 | 27,978 | 0.1961 (1.05x) |

Every cost cell has zero retained divergences, exhaustions and depth caps
except `nuts-1` (2,087 exhaustions and 4 divergences on Eight Schools, 21
exhaustions on the Gaussian). Full tables: `artifacts/results-table.md`;
machine-readable: `artifacts/summary.json`.

## Predictions

* P1 (defaults biased low on >= 2 seeds, hundreds of exhaustions): **held**
  (z −3.52, −3.75; 452 / 1,097 / 1,384 exhaustions).
* P2 (`nuts-1` biased low everywhere, thousands of exhaustions): **held**
  (two seeds with no draw below −5 at all; 15,916–34,122 exhaustions).
* P3 (`levels8` removes most exhaustions and is within |z| <= 2): **held**.
* P4 (`delta` alone helps less than levels and costs on the Gaussian):
  **held**, and it hurts the funnel rather than merely helping less.
* P5 (`paper-8` unbiased, `paper-4` not, paper costs >= 10 % on the
  Gaussian): **partly held** — `paper-4` is biased and paper mode costs
  0.39–0.41x on the Gaussian (it settles at `delta` 1.3–2.0 and `h` 0.1–0.2
  there, far below dual averaging's step); but `paper-8` from `h0 = 0.5`
  missed on one seed (0.0293, z −2.72, one chain at `h = 0.011`), unlike
  `paper_funnel_adaptive_v2` from `h0 = 0.1` with identity metric.
* P6 (`levels8` free on the cost targets): **held**.
* P7 (`stan-style` biased): **held**, and worse than predicted: seed 82102
  had 2,132 retained divergences, and seed 82103 **errored** — the preset's
  initial fast phase runs at `delta = 1000`, a chain left the region where
  the hand-written density is finite (`sum x^2` overflowed), the target
  returned a nonfinite value on the non-recoverable path and `run` failed.
  The examples' funnel target only maps the `exp(-omega)` overflow to the
  recoverable error; this cell is reported as a failure of the arm, not
  rerun.

## Decision

Rule 3 of the preregistration: unbiased arms `levels8` and
`levels8+delta0.5`; of those only `levels8` is at >= 0.9x on both cost
targets; **`levels8` is the new `Tuning::default()`**
(`max_refinement_levels = 8`, everything else unchanged). Applied in the
labelled final commit with `tests/sampler_api.rs`, the README defaults table
and quick start, CHANGELOG 0.2.0 Changed, `wiki/release-0.2.0.md` and the
Python package default. `tests/kernel_fingerprint.rs` (which pins
`walnutpie::KernelTuning::default()`, not the sampler default) is untouched.

Recorded, not chosen: `levels8+delta0.5` for a user who wants the funnel to
mix rather than merely be unbiased at the defaults; the README says so.

## Reproduce

```sh
cd STUDIES/funnel_defaults_v1
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=../../target-study-funnel-defaults cargo build --release
sh run_grid.sh                      # 81 cells, sequential, ~2 minutes; skips existing cells
../../target-study-funnel-defaults/release/funnel-defaults-v1 summarize artifacts/cells artifacts/summary.json artifacts/results-table.md
sha256sum -c CHECKSUMS.sha256
```

Draws are not stored (the cells hold every reported statistic). The grid was
run once, strictly sequentially, on the machine that ran WP24 and WP25; the
wall figures are indicative only (4 threads).
