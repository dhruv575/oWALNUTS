# funnel_tail_deficit_v1 (WP66): why is the default's funnel tail mass low, and does one setting fix it?

## Verdict

**Not supported. On fresh seeds the deficit does not replicate at the
preregistered threshold, and none of the three mechanisms is supported.** No
setting is recommended and no default changed.

- **Replication failed.** The shipped default gives a pooled
  P(omega < -5) of **0.0465 ± 0.0017** over 30 fresh seeds (4 x 2,000/20,000).
  That is 2.7 % below the exact 0.0478 at t = -0.76. The replication rule
  needs more than 1 s.e., so the deficit did not replicate.
  - The house z pattern did reproduce: mean z -0.39, 3/30 seeds below -2
    and none above +2, sd 1.42.
  - The upper tail P(omega > 5) is 2.4 % *high* (0.0489 ± 0.0008), so the
    lower-tail-specific prediction P2 failed.
- **The sanity arm shows no deficit at 4x the draws.** At 4 x 2,000/80,000
  over 10 seeds the pooled estimate is **0.0488 ± 0.0007**, +2.1 % (t +1.5).
  The first 20,000 draws of the same runs give 0.0477. The frozen rule
  classes this as INCONCLUSIVE: it is not within 1 s.e. of exact, and it sits
  above exact, not below.
- **Pooled over every default run at 20,000 draws.** WP53, WP66 and the S
  prefixes give 70 seeds at 0.0464 ± 0.0010 (-3.0 %, t -1.4); this
  aggregation is not preregistered. The "4–5 % deficit" of WP53 was in part
  a low draw. A residual of 0–4 % at 20,000 draws cannot be excluded, and
  nothing suggests a bias that persists with run length.
- **H1, step adaptation:** "signature present, not causal". `accept0.9`
  makes the step 33 % smaller (median 0.061 vs 0.091) and moves the pooled
  estimate by only +0.0006 ± 0.0024 (paired t 0.25). The neck's
  energy-acceptance proxy is 0.41 against 0.73 in the bulk, as the pipeline
  check had flagged, but per-chain tail mass does not track `h` (Spearman
  -0.08). It fails D2 (mean z -0.30).
- **H2, refinement ceiling:** NOT SUPPORTED. The ceiling *is* hit:
  - 12.8 % of deep-neck transitions (start omega < -7) select level 7 or
    exhaust.
  - The deficit does not grow with depth. The c = -8 relative error is
    -0.4 %, against -2.7 % at c = -5.
  - `levels10` removes the hits (exhaustions 756 -> 10, deep top+exhaust
    12.8 % -> 0.4 %) and **cuts retained divergences from 59 to 1**, at
    1.00x cost on both side targets.
  - It moves the tail mass the wrong way: 0.0453, paired -0.0012 ± 0.0007.
- **H3, U-turn rule:** "signature present, not causal". Under `endpoint` the
  pooled estimate is 0.0496 ± 0.0024, and **it passes D1–D4**: |error| 0.0018
  is within its s.e. 0.0024, mean z is -0.13, 2 seeds exceed |z| 2, and
  there is no library change.
  - It does not pass because it is more accurate: paired against the
    default it is +0.0031 ± 0.0032 (t 0.97). Its s.e. is 1.4x the default's
    because it mixes worse: median omega tail ESS 299 against 727, and
    0.79x the default's min ESS per gradient.
  - The depth signature holds, but in the opposite direction to the
    mechanism. The endpoint rule stops neck orbits *earlier* (neck mean depth
    1.49 against 2.55, 71 % U-turn stops at depth <= 3 against 29 %).
    `MomentumSum` does not truncate the neck.
  - It fails E1 (100-D Gaussian 0.900x) and E2 (pre-assessed; posteriordb
    record WP31/32). By the frozen labels it **removes the deficit, but is
    not a default candidate**.
- **D4 held for every arm.** `git diff a49df800 -- src Cargo.toml Cargo.lock`
  is empty and `kernel_fingerprint` passes 3/3 on the box build, because
  every arm is a builder setting.

All 210 cells ran with exit 0, no errors and no reruns. The study was
preregistered in `PREREGISTRATION.md` / `protocol.json`, committed in
`1979faca` with a disclosure added in `06442454`, both before the first
evidence cell.

It ran on the shared AWS box `owalnuts-bench`, lane 3, pinned
`taskset -c 8-11` with three other lanes active. Walls are "pinned,
co-tenanted": block A took 3 min 16 s for 120 cells, S 59 s and C 9 s. Wall
times are not used in any rule. Library `main` `a49df800`, kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, Rust 1.88.0 on Linux;
see `artifacts/environment.json`.

## Block A: 4 x 2,000/20,000, 30 fresh seeds (668101–668130); S: 4 x 2,000/80,000, 10 seeds (668201–668210)

| arm | pooled P5 ± s.e. | rel. error | upper P(>5) ± s.e. | P6 | omega var | \|z\|>2 | mean z | divergences | exhaustions | median h | min ESS / gradient | paired Δ vs default | D1 | D2 | D3 | D4 | label |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| `default` | 0.0465 ± 0.0017 | -2.7 % | 0.0489 ± 0.0008 | 0.0224 | 8.98 | 3 | -0.39 | 59 | 756 | 0.091 | 1.05e-4 | — | — | — | — | — | control |
| `accept0.9` (H1) | 0.0471 ± 0.0017 | -1.4 % | 0.0477 ± 0.0007 | 0.0223 | 8.91 | 1 | -0.30 | 26 | 385 | 0.061 | 0.90e-4 | +0.0006 ± 0.0024 | yes | **no** | yes | yes | does not remove |
| `levels10` (H2) | 0.0453 ± 0.0015 | -5.2 % | 0.0495 ± 0.0007 | 0.0218 | 8.95 | 4 | -0.51 | **1** | **10** | 0.091 | 1.06e-4 | -0.0012 ± 0.0007 | **no** | **no** | yes | yes | does not remove |
| `endpoint` (H3) | 0.0496 ± 0.0024 | +3.8 % | 0.0476 ± 0.0006 | 0.0235 | 9.07 | 2 | -0.13 | 37 | 635 | 0.111 | 0.83e-4 | +0.0031 ± 0.0032 | yes | yes | yes | yes | removes, not a default candidate (E1, E2 fail) |
| S: `default` 80k | 0.0488 ± 0.0007 | +2.1 % | 0.0473 ± 0.0005 | 0.0234 | 9.02 | 0 | +0.22 | 58 | 1,184 | 0.102 | 1.14e-4 | — | — | — | — | — | INCONCLUSIVE |

Exact values: P5 = P(>5) = 0.0478, P6 = 0.0228, variance 9.

Column notes:

- The s.e. is the between-seed s.e. (sd/√n).
- "Paired Δ" is the mean over seeds of P5(arm) − P5(default) with its s.e.
- "Min ESS / gradient" is the geomean over seeds, warmup included.
- The house z has an MCSE that correlates with the estimate (r = 0.63 in the
  default arm, as in WP53). Mean z therefore stays near -0.3 to -0.4 even
  when the pooled estimate is within 1 s.e. of exact, which makes D2 the
  hardest clause.

## Diagnostics: retained transitions by the starting state's omega (default arm, 2.4 M transitions)

| class | n | mean depth | U-turn stop at depth <= 3 | moved | energy-acceptance proxy | mean max \|dH\| | top level (7) | exhaust stops | divergences | gradients / transition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| bulk (>= -5) | 2,288,239 | 3.86 | 0.298 | 0.915 | 0.726 | 0.45 | 14 | 0 | 0 | 52 |
| neck [-7, -5) | 88,327 | 2.55 | 0.293 | 0.794 | 0.412 | 1.37 | 237 | 25 | 0 | 183 |
| deep (< -7) | 23,314 | 2.57 | 0.272 | 0.789 | 0.366 | 20.8 | 2,260 | 731 | **59** | 522 |

Readings:

- **Every retained divergence and 97 % of exhaustions start in the deep
  neck.** `levels10` removes nearly all of them: deep top+exhaust 0.4 %,
  1 divergence. It does this without changing the tail mass, so the
  divergences and exhaustions are not what makes the estimate low.
- **The neck is hard at the adapted step but is not truncated.** Moved
  fraction is 0.79, and the neck's U-turn-at-shallow-depth share equals the
  bulk's (0.293 vs 0.298). Raising the target to 0.9 shrinks `h` and halves
  deep exhaustions (731 -> 384) but leaves the neck's moved fraction and
  proxy where they were (0.806 / 0.412).
- **Per seed, not per transition.** Of the five lowest default seeds (P5
  0.028–0.035, z down to -4.3), four contain a slow chain: 668106, 668130,
  668115 and 668112, each with a chain at `h` <= 0.023 and 5–38 neck entries,
  against about 87 per chain on average, and with retained quarters that
  never visit the neck. The fifth, 668111, is uniformly low across its four
  chains at ordinary `h`. This is the per-chain step collapse WP28
  described. Its effect is variance
  (Spearman of chain P5 with `h` is -0.08 over 120 chains) and silent
  under-visits, not a stationary bias. This reading is post hoc.

Full tables (tail profiles for c = ±1..±10, level histograms, per-chain
statistics and per-seed values) are in `artifacts/results-table.md`.

## Block C: cost on ordinary targets (4 x 1,000/1,000, 10 seeds 668301–668310, E1)

| target | `accept0.9` | `levels10` | `endpoint` |
|---|---:|---:|---:|
| noncentred Eight Schools | 0.849x | 1.000x (draw-identical) | 0.981x |
| 100-D Gaussian | 1.215x | 1.000x (draw-identical) | **0.900x** |

Each value is the geomean over seeds of the paired ratio of min bulk ESS per
gradient against `default`. All 80 cells are house-healthy with zero
divergences. `levels10` never engages there: no transition reaches level 7.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | default pooled P5 in [0.0440, 0.0475], mean z in [-0.6, -0.1] | 0.0465, -0.39 | **held** |
| P2 | upper tail P(>5) within 1 s.e. of exact | 0.0489 ± 0.0008 (+1.4 s.e.) | **failed** |
| P3 | deep top+exhaust < 1 %, `levels10` within 1 paired s.e. | 12.8 %; -0.0012 ± 0.0007 | **failed** (the ceiling is hit, and lifting it lowers the estimate) |
| P4 | `accept0.9` median `h` 20–50 % smaller | 33 % smaller | **held** |
| P5 | `endpoint` within 1 paired s.e. | +0.0031 ± 0.0032 | **held** |
| P6 | no candidate passes D1–D4 | `endpoint` passes | **failed** |
| P7 | S INCONCLUSIVE or FINITE-RUN | INCONCLUSIVE | **held** |

## What this means

1. **No setting needs to change for funnel tail mass.** The deficit that
   motivated the study is about 3 % ± 2 % at 20,000 draws over 70 default
   seeds and +2 % ± 1.4 % at 80,000. None of the three setting changes moves
   it by a paired amount distinguishable from zero. `endpoint` "passes" only
   on a wider s.e. and is a known posteriordb loss.
2. **The low-z pattern is real but is a per-seed phenomenon.** One seed in
   ten has a slow chain that under-visits the neck silently, and the MCSE z
   exaggerates such seeds. This is the per-seed gate problem WP53 described,
   and it argues again for pooled, many-seed funnel checks over per-seed |z|.
3. **Side finding: `levels10` is free on these targets and removes funnel
   divergences** (59 -> 1, exhaustions 756 -> 10, 1.00x on Eight Schools and
   the Gaussian, draw-identical there). It is not a tail-mass fix, so this
   study's rule cannot recommend it. Funnel divergences are a gate input,
   though, so it is a lead for a separate preregistered posteriordb study.

## Caveats

- 30 seeds at 20,000 draws give a between-seed s.e. of about 3.5 % of the
  exact value. A deficit below about 4 % cannot be resolved per arm, and
  that was known at the freeze.
- The S arm has 10 seeds. Its between-seed sd (0.0021) is half its mean MCSE
  (0.0043). That is unexpected (chi-square p ≈ 0.01, post hoc), so the
  80,000-draw MCSE may be conservative.
- The energy-acceptance proxy uses each orbit's maximum |dH|, not Stan's
  acceptance statistic, which the sampler records only in warmup.
- E2 was pre-assessed from the ledger at the freeze. No posteriordb cell was
  run in this study.
- The pooled 70-seed figure, the per-seed skew, the slow-chain reading and
  the S MCSE remark are not preregistered.

## Reproduce

On the box, every step is run pinned with `taskset -c 8-11`:

```bash
cd STUDIES/funnel_tail_deficit_v1
cargo build --release -j4
python3 run_study.py run A && python3 run_study.py run S && python3 run_study.py run C
python3 run_study.py analyze      # reads artifacts/environment.json for D4
python3 checksums.py
```

The box driver is reproduced in `artifacts/run_all.sh`. It builds, runs
`cargo test --release --test kernel_fingerprint` at the repository root,
writes `environment.json`, then runs blocks A, S and C and the analysis.
