# WP67 `refinement_levels10_v1`: preregistration

Frozen 2026-10-26 and committed before the first evidence cell.
`protocol.json` is the machine-readable copy and takes precedence if the two
disagree.

**WP number.** This study uses **WP67** on the coordinator's instruction. Lanes
1, 2 and 4 hold WP64, WP65 and WP68, and WP67 avoids a collision.

## Question

Is a default of ten refinement levels (finest micro step `h/512`) a safe
change to `sampler::Tuning::default()`, which currently has eight (`h/128`)?

The motivation is WP66 (`STUDIES/funnel_tail_deficit_v1`). There,
`max_refinement_levels(10)` cut the funnel's retained divergences from 59 to 1
and its exhaustions from 756 to 10 over 30 seeds. The tail mass did not
improve (paired −0.0012 ± 0.0007). On Eight Schools and a 100-D Gaussian the
cells were draw-identical.

## What is built

The candidate is implemented behind a Cargo feature in `wt/funnel-tail`
(commit `13fd02f6`). It is not a default flip.

- The feature `candidate-levels10` (off by default) sets
  `sampler::DEFAULT_MAX_REFINEMENT_LEVELS` to 10 instead of 8.
  `Tuning::default()` uses that constant.
- `tests/sampler_api.rs::default_refinement_levels_follow_the_candidate_feature`
  pins the constant at 8 with the feature off and at 10 with it on. It also
  checks that `Tuning::default()` equals `Tuning::default().max_refinement_levels(n)`.
- With the feature off, the library is `main` plus a public constant whose
  value is 8. Draws do not change.

**The arms are builds of one harness source.**

- `default` is the plain build in `target/release`.
- `levels10` is built with `--features levels10`, which maps to
  `owalnuts/candidate-levels10`, in `target-levels10/release`.
- Both run `Sampler::new()` with untouched defaults.
- Each binary refuses an arm whose level count differs from its build's.

## A flip, ALGORITHM_REVISION and the fingerprints

The coordinator's brief asked me to note that a flip would bump
`ALGORITHM_REVISION` and the kernel fingerprint tests. By the project's own
precedent it would not.

- `ALGORITHM_REVISION` names the frozen replay kernel, `KernelTuning::default()`.
  The tests in `tests/kernel_fingerprint.rs` pin runs built from explicit
  `KernelTuning::new(..)` values. Neither reads `sampler::Tuning::default()`.
- The `MomentumSum` (WP31/32), `RejectLeaf` (WP54) and best-of-16 (WP52)
  sampler-default flips changed neither.

A flip *would* change several things:

- the draws of every seed whose run exhausts eight levels;
- Python `DEFAULTS`, which is read from Rust;
- the README defaults table, the `Tuning` docs and `CHANGELOG`;
- `Sampler::worst_case_target_evaluations`, which grows about 4x and matters
  for `admit_conservative()` users and tests.

If the coordinator wants the revision string bumped anyway, that is a policy
choice made outside this study.

## Machine

AWS EC2 c7a.4xlarge `owalnuts-bench`, lane 3.

- Every build and cell runs under `taskset -c 8-11`, with
  `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`.
- Files live only under `~/lanes/refinement_levels10_v1/`.
- Three other lanes are active and share L3 and memory bandwidth, so wall
  times are "pinned, co-tenanted" and no rule uses them.
- ESS per gradient, pass counts and divergence counts are unaffected by the
  co-tenancy.
- BridgeStan 2.9.0 is built from source in the lane directory with makefile
  defaults (no `STAN_THREADS`).
- The `~/venv` Python environment (bridgestan 2.9.0, ArviZ 0.23.4) and
  `~/infra/posteriordb` (`28f8d3d`) are used read-only. Their files are read
  directly; the posteriordb package is not used.

## Blocks (strictly sequential, one process per cell, never rerun)

| block | role | design | seeds | cells |
|---|---|---|---|---|
| **F** | (a) funnel; decides F1, F2 | WP66's funnel harness (changes listed in `protocol.json`), 4 x 2,000/20,000, `default` then `levels10` within each seed | 670101–670130 | 60 |
| **P** | (b) posteriordb; decides P1, P2 | the 17 house models, the v7 oWALNUTS cell harness (WP62's `main.rs`, changes listed), 4 x 1,000/1,000; order: model in house order, then seed, then `default` before `levels10` | 670301–670303 | 102 |
| **L** | (c) descriptive, no rule | the default only, funnel 4 x 2,000/80,000 | 670201–670230 | 30 |

- **Timeout.** Each cell has a 2,700 s timeout (v7's).
- **Failures.** An errored or timed-out cell counts as a failed cell. In the
  funnel it counts as |z| > 2. In posteriordb it counts as not passed, and its
  model drops out of the geomean under v7's all-three-seeds-ok rule.
- **Seed check.** I ran `git grep -nowE` over every tracked file of
  `5af9903e`. The only hit is 670129, as digits of the float 0.670129 in two
  `bridgestan_owned_worker_v1` artifacts. Numeric substrings of floats are
  excluded by `wiki/methods.md`. There are no hits in any sibling-worktree or
  box-lane protocol or preregistration.

### Gates and statistics (v7)

- **Gates.** Rank R-hat <= 1.01; bulk and tail ESS >= 400 on every posteriordb
  reference-draw column, with draws constrained through BridgeStan including
  transformed parameters; zero retained divergences; finite draws; no error.
- **Estimators.** ArviZ 0.23.4.
- **ESS per gradient.** Minimum bulk ESS divided by target calls, counting
  the start search, warmup and sampling.
- **Per-model ratio.** The median over the three seeds for `levels10`,
  divided by the same median for `default`. The geomean is taken over models
  whose three seeds are ok on both arms.
- **Bit identity.** A cell is bit-identical when all four chains'
  retained-draw FNV-1a hashes are equal across the two builds.
- **Funnel.** The house MCSE z of P(omega < −5). The pooled estimate is the
  mean over seeds, with a between-seed s.e. Seeds are paired across arms.

## Decision rules (frozen)

- **F1.** The funnel's total retained divergences under `levels10` are no
  higher than under `default`.
- **F2.** For `levels10`, |pooled P5 − 0.04779| <= 2 x its between-seed s.e.
- **P1.** The `levels10` posteriordb pass count is at least `default`'s, out
  of 51.
- **P2.** The geomean of the per-model ESS/gradient ratio (`levels10` over
  `default`) is >= 0.95.
- **D (build integrity), checked on the box.**
  - With the feature off, the library diff against `5af9903e` contains only
    the constant and the feature entry.
  - `kernel_fingerprint` passes.
  - The feature test passes in both builds.
- **Verdict.** The change is **SAFE** iff F1, F2, P1, P2 and D all hold. Even
  then the flip is the coordinator's to make; it is not applied here.
  Otherwise the verdict is **NOT QUALIFIED**, naming the failed clauses.
- **L** decides nothing.

## Predictions (written before any cell, including the pipeline check)

- **Fa.** Funnel divergences fall by an order of magnitude: the `levels10`
  total x 10 <= the `default` total. This is the coordinator's prediction from
  WP66.
- **Fb.** The funnel's pooled P5 is unchanged: |paired difference| <= 1
  paired s.e. This is also the coordinator's prediction from WP66.
- **Fc.** The median omega tail-ESS ratio is in [0.9, 1.1].
- **Fd.** Funnel retained exhaustions fall by an order of magnitude.
- **Pa.** At least 25 of the 51 posteriordb cells are bit-identical.
- **Pb.** The posteriordb geomean ratio is in [0.97, 1.03].
- **Pc.** The pass counts are equal.
- **Ld.** Block L's pooled P5 is within 1.5 between-seed s.e. of 0.0478.

## Disclosed non-evidence work before the freeze

These were run after the predictions above were written. Their outputs stay in
the lane scratch directory and are not committed.

- **Infrastructure.** The BridgeStan compile of the 17 models.
- **Pipeline checks on seed 990667.** One funnel cell per arm at
  2,000/20,000, and one `eight_schools_noncentered` posteriordb pair.
