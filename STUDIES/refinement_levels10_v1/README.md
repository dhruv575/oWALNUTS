# refinement_levels10_v1 (WP68): is ten refinement levels a safe default?

## Verdict

**NOT QUALIFIED as a default change.** The funnel clauses F1 and F2 pass, and
so does build integrity (D). Both posteriordb clauses fail:

- **P1 (pass count may not drop):** 42/51 for `levels10` against 44/51 for
  `default`.
- **P2 (geomean ESS-per-gradient ratio, `levels10` / `default`, >= 0.95):**
  0.824.

No default was changed. The candidate stays behind the study-only Cargo
feature `candidate-levels10`, which is off by default.

- **(a) Funnel, 30 fresh seeds at 4 x 2,000/20,000.** Ten levels remove the
  funnel's divergences and exhaustions without moving the tail mass.

  | | `default` | `levels10` |
  |---|---:|---:|
  | retained divergences | 268 | **0** |
  | divergence-free seeds | 19/30 | 30/30 |
  | retained exhaustions | 1,204 | 1 |
  | pooled P(omega < -5) | 0.0512 ± 0.0017 | 0.0504 ± 0.0016 |
  | median omega tail ESS | 668 | 646 (0.97x) |
  | min ESS per gradient | — | 1.01x the default |

  The paired difference in P5 is −0.0008 ± 0.0008 (t −1.01), and 9/30 cells
  are bit-identical. F1 holds (0 <= 268). F2 holds: |0.0504 − 0.0478| =
  0.0026 is within 2 s.e., 0.0031.
- **(b) posteriordb, 17 house models x 3 fresh seeds at 4 x 1,000/1,000.**
  The pass count is 44 for `default` and 42 for `levels10`. Only **13/51
  cells are bit-identical** (prediction: >= 25). Those 13 are every cell of
  `eight_schools_noncentered`, `mesquite`, `garch11` and `one_comp`, plus one
  `hmm_example` seed.
  - **Why the arms diverge.** The default arm has refinement-exhaustion
    stops in 33 of 51 cells (140 warmup transitions and 25 retained ones),
    mostly in early warmup. It selects level 7, the top of eight, in 40
    cells. Under the warmup rule `AcceptUnlessDivergent`, an exhausted leaf
    can also continue at level 7 instead of stopping, and with ten levels
    that leaf refines further. From that transition on the two builds follow different
    trajectories, so on 13 of the 17 models the arms are effectively
    independent runs on shared seeds.
  - **Where the two lost passes come from.**
    - `hmm_drive_0`: 2/3 for `default` against 1/3 for `levels10`. This is
      the known second-mode lottery (WP60). In both of the failed
      `levels10` cells, `chain_warnings` names one chain about 30–63 nats
      below the others; the failed `default` cell shows the same.
    - `sblrc`: 3/3 against 2/3. One `levels10` cell has R-hat 1.0105
      against the 1.01 gate.
  - **Why the geomean is 0.824.** It is driven by `hmm_drive_0` at 0.034
    (the trapped chain's ESS) and `accel_gp` at 0.47 (0/3 in both arms).
    Against them, `eight_schools_centered` is 3.64 (0/3 in both). Excluding
    `hmm_drive_0`, the geomean over the other 16 models is **1.007**; this
    figure is not preregistered.
  - Largest passing |z| is 4.20 in both arms, on the same bit-identical
    `one_comp` cell.
- **(c) Descriptive, `default` at 4 x 2,000/80,000, 30 seeds.** The pooled
  P5 is **0.0478 ± 0.0010** (t +0.06), exact. This closes WP66's residual
  question: there is no tail-mass bias at the defaults. At this length the
  default still has 1,241 retained divergences, and only 7/30 seeds are
  divergence-free.
- **D (build integrity) held** on the box:
  - With the feature off, the library diff against `5af9903e` is the
    constant, its use in `Tuning::default()`, the feature entry and the
    feature test, and nothing else.
  - `kernel_fingerprint` passes.
  - The feature test passes in both builds.

The study was preregistered in `PREREGISTRATION.md` and `protocol.json`
before any evidence cell: commit `b34bdf60` as WP67, renumbered to WP68 in
`938470bf` on the coordinator's correction.

**One deviation, recorded in `AMENDMENTS.md` before re-execution.** Run 1
of block P failed all 102 cells at model load, before any sampling, in both
arms. The cause was a driver environment-variable rename that came with the
renumbering. Block P was rerun once on the same seeds. The void run-1 cells
are kept in `artifacts/void-P-run1/`. In the rerun, all 102 cells completed.

All cells ran on the shared AWS box, lane 3, pinned with `taskset -c 8-11`,
with other lanes active, so wall times are pinned and co-tenanted. Times: F
took 1.5 min for 60 cells, P run 2 took 14 min for 102 cells, and L took
3 min for 30 cells. Library `wt/funnel-tail` `938470bf`; kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`; Rust 1.88.0 on Linux;
BridgeStan 2.9.0 built from source (no `STAN_THREADS`) with concurrent
replicas.

## Rules and predictions

| | clause | observed | held |
|---|---|---|---|
| F1 | funnel divergences `levels10` <= `default` | 0 vs 268 | **yes** |
| F2 | \|P5 − exact\| <= 2 s.e. | 0.0026 vs 0.0031 | **yes** |
| P1 | pass count not lower | 42 vs 44 | **no** |
| P2 | geomean ESS/gradient >= 0.95 | 0.824 (17 models) | **no** |
| D | build integrity | all three checks | **yes** |
| Fa | divergences fall >= 10x | 268 -> 0 | held |
| Fb | P5 unchanged within 1 paired s.e. | −0.0008 ± 0.0008 (t −1.01) | failed, narrowly |
| Fc | tail-ESS ratio in [0.9, 1.1] | 0.97 | held |
| Fd | exhaustions fall >= 10x | 1,204 -> 1 | held |
| Pa | >= 25/51 bit-identical | 13/51 | failed |
| Pb | geomean in [0.97, 1.03] | 0.824 | failed |
| Pc | equal pass counts | 44 vs 42 | failed |
| Ld | L within 1.5 s.e. of exact | t +0.06 | held |

The per-model table, the funnel per-seed table and the full rule and
prediction JSON are in `artifacts/results-table.md` and
`artifacts/summary.json`.

## What this means

1. **On the funnel, ten levels are a clear improvement.** Divergences drop to
   zero on every seed, the cost per gradient is unchanged and the tail mass
   is unaffected. This replicates WP66's 59 -> 1 on fresh seeds.
2. **On posteriordb, the frozen rule cannot see that at 3 seeds.** The
   prediction that most cells would be bit-identical was wrong: early-warmup
   exhaustion at the initial step is common, so the arms decorrelate and the
   comparison inherits the seed noise WP62 measured, about ±0.1 on a
   three-seed geomean. The two losses sit on known lotteries, the
   `hmm_drive_0` second mode and an R-hat 0.0005 over the gate. The
   post-hoc 1.007 without `hmm_drive_0` suggests no real cost, but under
   the frozen rule this is a failure, and it stands.
3. **A flip would not move `ALGORITHM_REVISION` or the kernel fingerprints.**
   Both pin `walnutpie::KernelTuning`, as with the `MomentumSum`,
   `RejectLeaf` and best-of-16 flips. It would change sampler draws, Python
   `DEFAULTS`, the README table and CHANGELOG, and roughly 4x the admission
   bound.
4. **Next step, if the funnel gain is wanted as a default.** A posteriordb
   confirmation needs enough seeds to resolve 0.95 when the arms decorrelate:
   per WP62, at least six and preferably about ten. It should gate
   `hmm_drive_0` by its hidden-mode count rather than its ESS ratio. Until
   then, `Tuning::default().max_refinement_levels(10)` is the documented
   opt-in for funnel-like targets.

## Caveats

- Three posteriordb seeds, as preregistered. This is the known weakness of
  three-seed per-gradient figures (WP62).
- The block P rerun is a deviation, but the failure was symmetric and
  happened before any sampling.
- The figure excluding `hmm_drive_0` and the attribution of the losses are
  post hoc.
- Unconstrained and constrained posteriordb draws (68 MB) stay on the box.
  `artifacts/draws-manifest.sha256` lists their hashes.

## Reproduce

On the box, with the lane's `env.sh` sourced (it is in `artifacts/box-logs/`)
and everything pinned with `taskset -c 8-11`:

```bash
cd STUDIES/refinement_levels10_v1
cargo build --release -j4
cargo build --release -j4 --features levels10 --target-dir target-levels10
python3 run_study.py prepare                       # BRIDGESTAN, WP68_MODELS, WP68_DRAWS from env.sh
python3 run_study.py run F && python3 run_study.py run P && python3 run_study.py run L
python3 run_study.py analyze && python3 checksums.py
```

`artifacts/box-logs/run_all.sh` and `run_P2.sh` are the exact drivers. They
include the integrity checks that write `environment.json`.
