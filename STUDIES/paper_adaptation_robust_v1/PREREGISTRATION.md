# paper_adaptation_robust_v1 — preregistration

Status: FROZEN BEFORE EXECUTION (this file and `src/main.rs` are committed
before the first cell runs; results are appended in a later commit and
nothing in this section is edited afterwards).

## Question

`STUDIES/posteriordb_bench_v1` found the JMLR Appendix C warmup
(`PaperAdaptationConfig::default()`) freezing chains on 9 of 17 posteriors:
from uniform(-2, 2) starts the initial fast phase's orbits span energy ranges
of 10^3–10^16, the K-quantile rule installs `delta ~ 0` at transition 74, every
leaf then exhausts refinement and the chain never recovers (exactly 16 target
calls per retained transition, R-hat undefined). This study asks whether the
additive guards added to `PaperAdaptationConfig` in this branch remove the
freeze without giving up efficiency against dual averaging, and whether one
guarded configuration should become `PaperAdaptationConfig::default()`.

## Fixed protocol

* Kernel: the worktree `wt/robustness` at the commit that adds this file
  (`ALGORITHM_REVISION` unchanged from v1; the guards are additive and off by
  default, verified by the unchanged `tests/kernel_fingerprint.rs`).
* Target: `owalnuts_bridgestan::StanTarget` on the BridgeStan libraries
  compiled for v1 (`STUDIES/posteriordb_bench_v1/models`, Stan 2.39.0,
  `STAN_THREADS=true`), located through the `POSTERIORDB_MODELS` environment
  variable. Nonfinite evaluations are recoverable (this branch's BridgeStan
  fix); starts use the new `owalnuts::sampler::uniform_starts` rule
  (uniform(-2, 2), retried until finite, seeded by the cell seed) so that
  every arm of a cell shares its four starts.
* Models (the seven named in the task; all froze or partly froze in v1):
  `kidiq-kidscore_momhsiq`, `sblrc-blr`, `earnings-logearn_interaction`,
  `diamonds-diamonds`, `nes2000-nes`, `mesquite-logmesquite_logvash`,
  `hmm_example-hmm_example`.
* 4 chains, 1,000 warmup + 1,000 retained transitions, 4 threads, v1's
  Python-package default tuning (`h0 = 0.1`, depth 8, one minimum micro-step,
  4 refinement levels, `delta0 = 1`, divergence threshold 1000), adapted
  diagonal metric from the identity.
* Seeds: 77201 and 77202 (unused anywhere in the repository; checked with
  `grep -rn 7720`).
* Arms (nothing tuned per model):

  | arm | configuration |
  |---|---|
  | `da` | dual averaging at acceptance 0.8 (v1's `owalnuts-da`) |
  | `paper` | `PaperAdaptationConfig::default()` (v1's `owalnuts-paper`; expected to freeze) |
  | `floor` | default + `with_min_max_error(0.05)` |
  | `defer` | default + `with_first_update_after(150)` + `with_metric_update_required(true)` |
  | `guarded` | `floor` + `defer` + `with_unhealthy_orbits_excluded(true)` |
  | `guarded-trim` | `guarded` + `with_trim_fraction(0.1)` |

  With 1,000 warmup transitions the update points are transitions 74 (end of
  the fast phase), 99, 149, 249, 449 and 949; `first_update_after(150)`
  therefore defers the first two and the metric requirement defers the
  first slow-window boundary (99) as well.
* Run order: models in the listed order, arms in the listed order, seeds
  ascending, strictly sequential; one process per cell; every cell is
  reported, failures included; no reruns.

## Estimands (per cell, computed in Rust by `owalnuts::diagnostics`,
over the unconstrained coordinates)

* `frozen`: any chain whose retained refinement-exhaustion stops exceed half
  its retained transitions, or whose R-hat is undefined on any coordinate.
* `min_bulk_ess`, `min_tail_ess`, `max_rhat`: min/max over coordinates of
  the arviz-style bulk ESS, tail ESS and rank R-hat.
* `gradients`: total target calls (warmup + retained, four chains).
* `bulk_ess_per_gradient = min_bulk_ess / gradients`.
* `final_delta`, `final_h`: median over chains of the frozen `max_error` and
  step size; per-window `PaperAdaptationUpdate` telemetry is stored raw.
* `divergences`: retained divergences summed over chains.

Per model the cell statistics are summarised by the median over the two
seeds; `r = bulk_ess_per_gradient(arm) / bulk_ess_per_gradient(da)` uses the
in-study `da` arm (same estimator, same starts, same machine). The v1
`owalnuts-da` numbers (min over *constrained reference* parameters via arviz)
are printed alongside for orientation only.

## Decision rule

A configuration is **robust** if it freezes on no (model, seed) cell.

A configuration **clears the bar** if it is robust and `r >= 0.8` on every
one of the seven models.

If at least one candidate clears the bar, the one with the fewest guards
(order: `floor`, `defer`, `guarded`, `guarded-trim`) becomes
`PaperAdaptationConfig::default()` in a final, separately labelled commit
(fingerprint tests that pinned the old paper defaults are updated; the v10
dual-averaging fingerprints are untouched). Otherwise the default stays as
it is and the report says which models fail and how.

## Predictions

* P1: `paper` freezes on every model except `mesquite` and `hmm_example`,
  where it freezes on at least one chain (as in v1).
* P2: `floor` alone does not freeze but is well below `da` on the
  regressions (a floor of 0.05 still installs a very small `delta` at
  transition 74 and refinement stays heavy for the rest of warmup).
* P3: `defer` alone still freezes on some models: the slow windows from
  uniform starts can still contain the fall into the typical set.
* P4: `guarded` is robust and within 0.8x of `da` on at least five of the
  seven models; `guarded-trim` is not distinguishable from `guarded`.

## Round 2 amendment (written after round 1, before any round 2 cell)

Round 1 (commit with the round 1 artifacts) showed a second freeze mechanism
that none of the preregistered guards touches: on `sblrc`, `diamonds`,
`earnings` and one `mesquite` chain every leaf of the very first transitions
exhausts refinement at the initial step `h0 = 0.1` even with `delta = 1`
(the DA arm's adapted step on these models is 0.0004–0.003, and four
refinement levels only reach `h0 / 16`). A transition that builds no leaf
produces no unrefined-fraction statistic, so the paper `h` rule never
updates and `h` stays at 0.1 for the whole warmup; acceptance-driven dual
averaging sees acceptance zero at the same transitions and shrinks the step.
`guarded` therefore froze with `delta` still at 1 on those models.

Added guard: `with_exhausted_transitions_as_zero(true)` feeds unrefined
fraction 0 for a transition that built no leaf (all attempted leaves
exhausted refinement). Round 2 arms, same models, seeds, protocol and
estimands as round 1:

| arm | configuration |
|---|---|
| `zero` | default + `with_exhausted_transitions_as_zero(true)` |
| `floor-zero` | `floor` + zero |
| `guarded-zero` | `guarded` + zero (floor 0.05, defer 150 + metric, unhealthy excluded) |

Decision rule unchanged (robust on every cell and `r >= 0.8` on every
model against the in-study `da` arm); candidate order for the default is
now `floor`, `defer`, `guarded`, `guarded-trim`, `zero`, `floor-zero`,
`guarded-zero`. Prediction P5: `zero` alone still freezes (the `delta ~ 0`
installation at transition 74 remains), `floor-zero` and `guarded-zero` do
not freeze; whether they reach 0.8x of `da` on the regressions is open.
