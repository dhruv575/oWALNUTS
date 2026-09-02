# paper_adaptation_robust_v1 — making the Appendix C warmup survive uniform starts

Status: executed 2026-09-01 on `wt/robustness` (kernel
`ALGORITHM_REVISION` unchanged from `posteriordb_bench_v1`; BridgeStan
models compiled for that study). Protocol: `PREREGISTRATION.md` (round 1
preregistered; rounds 2 and 3 are labelled amendments written after the
previous round and before their own cells). Cells: `artifacts/cells/`
(154 = 7 models x 11 arms x 2 seeds); table: `artifacts/results-table.md`;
decision: `artifacts/summary.json`. Driver: `src/main.rs`, `run.sh`.

## Question

`STUDIES/posteriordb_bench_v1` saw `PaperAdaptationConfig::default()` freeze
chains on 9 of 17 posteriors. Which additive guard(s) remove the freeze, and
does a guarded configuration reach 0.8x of dual averaging (min bulk ESS per
gradient, in-study `da` arm, seed medians) on the seven freeze models
`kidiq`, `sblrc`, `earnings`, `diamonds`, `nes2000`, `mesquite`,
`hmm_example` (4 chains, 1,000/1,000, seeds 77201/77202, `h0 = 0.1`,
depth 8, 4 refinement levels, `delta0 = 1`, adapted diagonal metric,
uniform(-2, 2) starts via `owalnuts::sampler::uniform_starts`)?

## What actually freezes the chains

The v1 reading ("the K-quantile rule installs `delta ~ 0` at transition
74") was the symptom, not the cause. The per-window telemetry of every
frozen cell here shows two mechanisms that act *before* any `delta` update:

1. **No statistic, no step update.** From a uniform(-2, 2) start at
   `h0 = 0.1` every leaf of the first transitions exhausts refinement even
   at `delta = 1` (the DA arm's adapted step on these models is 0.0004–0.07,
   and four refinement levels only reach `h0 / 16`). A transition that
   builds no leaf produces no unrefined-fraction statistic, so the paper
   `h` rule never moves; acceptance-driven dual averaging sees acceptance 0
   at the same transitions and shrinks the step. On `kidiq`, `sblrc`,
   `earnings`, `diamonds` this froze every chain of every round 1 arm from
   transition 0 (`h` stayed at 0.1, `delta` at 1 under `guarded`).
2. **The paper-mode step band.** With statistic 0 fed for such transitions
   (`with_exhausted_transitions_as_zero`), `h` falls to the band floor
   `h0 / PAPER_STEP_RELATIVE_BOUND = 1e-4` and on `sblrc`/`earnings`/one
   `kidiq` chain every leaf *still* exhausts there (energy error above the
   divergence threshold at micro-step 6e-6: the start sits where the
   gradient is enormous). Dual averaging has no such bound.

The `delta` guards (floor, deferral, metric gate, unhealthy-orbit exclusion,
trimming) are harmless and sometimes helpful (`hmm_example`: `guarded`
0.97x of DA where `paper` froze) but none of them touches either mechanism.

## Results (seed medians; `r` = min bulk ESS/gradient over the in-study `da` arm; `frozen` = cells of 2)

| model | da ESS/grad x1e3 (v1: arviz) | paper | floor | defer | guarded | guarded-trim | zero | floor-zero | guarded-zero | **zero-wide** | guarded-zero-wide |
|---|---:|---|---|---|---|---|---|---|---|---|---|
| kidiq | 1.22 (2.67) | frozen 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 1/2, r 1.06 | 1/2, r 1.08 | **0/2, r 1.18** | 0/2, r 1.08 |
| sblrc | 0.43 (0.30) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | **0/2, r 0.98** | 0/2, r 0.11 |
| earnings | 0.006 (0.015) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | **0/2, r 1.02** | 0/2, r 1.13 |
| diamonds | 0.039 (0.022) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 0/2, r 0.88 | 0/2, r 1.04 | **0/2, r 1.35** | 0/2, r 1.56 |
| nes2000 | 2.74 (2.40) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2, r 0.94 | 0/2, r 0.93 | 0/2, r 0.99 | **0/2, r 0.97** | 0/2, r 1.10 |
| mesquite | 3.22 (2.83) | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 0/2, r 0.96 | 0/2, r 0.96 | 0/2, r 1.12 | **0/2, r 0.92** | 0/2, r 1.12 |
| hmm_example | 9.75 (8.31) | 2/2 | 1/2 | 1/2 | 0/2, r 0.97 | 0/2, r 1.22 | 0/2, r 0.90 | 0/2, r 0.90 | 0/2, r 0.97 | **0/2, r 0.90** | 0/2, r 0.97 |

Full columns (tail ESS, R-hat, divergences, final `delta` and `h`, v1
numbers) in `artifacts/results-table.md`. Final `delta` of the robust arms
is 1.3–1.7 on every model (the K rule, once fed sane orbits, *raises*
`delta` from 1); final `h` matches the DA arm's to within 30%.

Decision table (`artifacts/summary.json`):

| arm | robust | models with r >= 0.8 | geomean r | clears the bar |
|---|---|---:|---:|---|
| paper | no | 0/7 | 0.055 | no |
| floor | no | 0/7 | 0.115 | no |
| defer | no | 0/7 | 0.111 | no |
| guarded | no | 1/7 | 0.128 | no |
| guarded-trim | no | 1/7 | 0.133 | no |
| zero | no | 3/7 | 0.348 | no |
| floor-zero | no | 4/7 | 0.688 | no |
| guarded-zero | no | 4/7 | 0.772 | no |
| **zero-wide** | **yes** | **7/7** | **1.036** | **yes** |
| guarded-zero-wide | yes | 6/7 (`sblrc` r 0.11) | 0.816 | no |

**`zero-wide`** = `PaperAdaptationConfig::default()` +
`with_exhausted_transitions_as_zero(true)` + `with_step_relative_bound(1e6)`
clears the preregistered bar: no frozen cell on any model and 0.90–1.35x
the DA arm's min bulk ESS per gradient everywhere (geometric mean 1.04,
fewer total gradients than DA on all seven models). It is applied as the new
default in the final commit of this branch (`PAPER_ADAPTATION_REVISION`
`v4`).

## Caveats

* "Robust" is the preregistered definition (no chain with more than half
  its retained transitions in refinement exhaustion, R-hat defined). Three
  cells of `zero-wide` (`kidiq` 77201, `sblrc` 77202, both `earnings`
  seeds) have R-hat 1.6–1.8 with min ESS 6–7, and so do the corresponding
  `da` cells (`kidiq` 77201 R-hat 1.57, `earnings` 1.63–1.77): one chain
  per cell adapts its step to 5e-4–7e-4 and spends the run at the depth
  cap. This is a shared dual-averaging failure from these particular starts,
  not a paper-rule one, and the ratio is computed like for like. On
  `earnings`/`diamonds` both arms are depth-8 limited as in v1.
* `guarded-zero-wide` differs from `zero-wide` only by the `delta` guards and
  loses on `sblrc` (seed 77201: min ESS 32 vs 419, R-hat 1.09 vs 1.02): the
  deferred first installation left `delta = 1` through the window where the
  step was still tiny; not pursued further.
* Two seeds; the v1 numbers in parentheses use arviz over constrained
  reference parameters and are orientation only.
* Predictions: P1 held (`paper` froze everywhere, `mesquite`/`hmm_example`
  partially), P2/P3 held trivially (both froze), P4 failed (`guarded` was
  robust on one model, not five), P5 held (`zero` still froze; `floor-zero`
  and `guarded-zero` reduced but did not remove freezes: the step band was
  the remaining cause), P6 held (both round 3 arms robust; the
  `guarded-zero-wide` miss was on `sblrc`, one of the three named models).

## Reproduce

```
export POSTERIORDB_MODELS=<dir with <model>_model.so and <model>.data.json from posteriordb_bench_v1>
bash run.sh            # ~25 min; resumable; ARMS="..." selects arms
```
