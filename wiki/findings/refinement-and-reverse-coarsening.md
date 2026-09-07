# Refinement, delta, and the reverse-coarsening check

## State of knowledge

Refinement is what makes WALNUTS exact on targets with localised stiffness,
and eight refinement levels are the difference between a biased and an
unbiased funnel tail at the sampler defaults. On the posteriordb set it does
almost nothing: the adapted macro step already equals Stan's step, refinement
engages on about 0.2 % of leaves, and the leaf-error distribution is one
smooth population with no stiff tail to absorb, so every arm that raised the
step to give refinement work lost per gradient. Where oWALNUTS is furthest
behind CmdStan the cost is the reverse-coarsening check ending orbits, not
the refinement gradients. Three preregistered attempts to make that check
cheaper or to carry the orbit past it (order, zero-weight continuation with
and without the step confound) all failed their rules, and the
truncation line is closed. Every default on this axis is `delta = 1`, eight
levels, `StopOrbit`, finest-to-coarsest.

## Timeline of evidence

- **WP2** (`STUDIES/paper_funnel_reproduction_v1`, 2026-08-31). At the
  paper's fixed tuning on Neal's funnel, retained stops were 34.8 %
  reverse-coarser-accepted, with reverse-coarser stops at 31–42 % even for
  positive omega where the mean selected level was below 0.5. The kernel was
  also biased (twice the correct neck mass), which WP6 traced to the
  acceptance statistic (`max_j |H(z_j) − H(z_0)|` over the whole path instead
  of the endpoint) and fixed in kernel v9 against a 4,000-leaf upstream
  oracle. WP10 (kernel v10) made recoverable target failures refine through
  as upstream does.
- **WP28** (`STUDIES/funnel_defaults_v1`, 2026-09-02). The 0.2.0 sampler
  defaults (four levels, `h0 = 0.5`) halved the funnel tail mass (z −3.5 and
  −3.75 on two seeds, 2,933 retained exhaustions). `levels8` was within
  |z| <= 2 on every seed at 1.08x the funnel calls, 1.05x Eight Schools ESS
  per call and 1.00x on a 100-D Gaussian (call-for-call identical on two
  seeds). Lower `delta` alone (0.5, 0.25) made the four-level bias worse.
  Eight levels became `Tuning::default()`. Caveat: one chain per seed still
  adapts to `h` 0.007–0.019 and never enters or leaves the neck; unbiased,
  not efficient.
- **WP29** (`STUDIES/posteriordb_bench_v4`, 2026-09-02). Levels 5–8 were
  selected by 0.000 of retained transitions on 15 of 16 measured models and
  0.005 on the centered eight schools; DA v4/v3 ESS per gradient 0.999
  geomean on the thirteen models without a seed-pathological draw. Eight
  levels are free.
- **WP34** (`STUDIES/refinement_role_v1`, 2026-09-03/04). Geomean adapted
  `h` over CmdStan's step 1.000 (0.87–1.12 on the healthy models); median
  refined-leaf fraction 0.0022; gradients per built leaf 1.00–1.09; one
  smooth error population with q99/q50 of |dH| about 10 everywhere,
  `P(|dH| > 1)` 0.4–6 % at `h`, 28–62 % at 2h. Every step-raising arm lost
  per gradient (`da06` 0.834x, `paper06` 0.604x, `stanacc` 0.670x). The near
  miss was `delta = 2` at the shipped step: 1.070x over 17, 1.077x healthy,
  the same 42 gates, but `accel_gp` 0.68x against the 0.85 clause. The four
  models furthest behind CmdStan (noncentered eight schools 0.75x,
  `gp_pois_regr` 0.75x, centered eight schools, `accel_gp` 0.47x) have the
  highest reverse-coarser stop fractions (10 %, 20 %, 21 %, 54 %).
- **WP37A** (`STUDIES/delta2_sidechecks_v1`, 2026-09-04). Fixed `delta = 2`
  versus 1 on the analytic funnel, strict Eight Schools and a 100-D
  Gaussian: pooled funnel accuracy passed, Eight Schools 1.048x and Gaussian
  1.017x, but F3 (gross safety: only 6/12 fixed2 seeds divergence-free) and
  F4 (absolute healthy-count minimum) failed. `FIXED2_NOT_QUALIFIED_FOR_ADAPTIVE_TO_2`.
- **WP37B** (`STUDIES/reverse_coarsening_order_v1`, 2026-09-04).
  Coarsest-to-finest reverse-check order at fixed `delta = 1`, 84 cells.
  Paused at cell 72 when the state-space target failed fatally on the
  incumbent arm (a target error classification, `sspd_target_fatal_diag_v1`),
  leaving 11 cells unlaunched. Descriptively over the 36 complete paired
  blocks the candidate made more reverse calls (5,161,651 versus 4,754,676,
  ratio 1.086) with gated kernel calls 1.007x. Verdict
  `KEEP_FINEST_TO_COARSEST`.
- **WP39** (`STUDIES/reverse_coarser_policy_v1`, 2026-09-05).
  `ReverseCoarserPolicy::ZeroWeightBeyond` keeps the failed leaf's endpoint
  and everything beyond it at zero weight and lets the orbit run on; exact
  by construction and by test. Geomean 0.981x (rule 1.10), targets 0.904x
  (rule 1.15), `accel_gp` 0.612x. Prediction that the adapted step would stay
  within 5 % was falsified: `h` rose on 16 of 17 models by 3–30 % because
  the `CurrentCoarseEndpoint` statistic averages over every built leaf,
  zero-weight tail included, so dual averaging installed a larger step and
  then paid for 2–25x more refined leaves as zero-weight tails (57 % of
  `accel_gp`'s built leaves).
- **WP39B** (`STUDIES/reverse_coarser_policy_v2`, 2026-09-05).
  `ZeroWeightBeyondAdaptSelected` withholds the tail from the step
  statistic; adapted step 1.011x the shipped policy on average. Geomean
  0.878x, targets 0.703x, centered eight schools 0.347x. At an identical
  fixed step the untruncated orbit was 0.908x on the targets (noncentered
  eight schools 1.21x, the other three below 1). Two designs agree: past a
  failed reverse check the orbit is worth carrying only where the failure
  region is small. The fixed-step arms were themselves a poor design (step
  fixed from the first warmup transition, 2–8x warmup gradients, `arma11`
  never built a leaf) and are reported as such.
- **WP40** (`STUDIES/warmup_gap_diag_v1`, 2026-09-05). Per-transition
  warmup telemetry showed that a single-leaf orbit ending in a
  reverse-coarser rejection hands dual averaging a statistic of 0.02–0.36
  and cuts the step 3–10x, followed by 5–10 depth-10 recovery orbits. These
  crashes occur at a nearly uniform 3–6 % of warmup transitions on every
  model, targets and controls alike, so the reverse check shapes warmup cost
  everywhere and not only where stiffness is real.

## What worked

| change | study | result | why |
|---|---|---|---|
| Endpoint acceptance statistic (kernel v9) | WP6 `funnel_bias_fix_v1` | funnel tail exact (z −0.08 / −0.14), 4,000/4,000 oracle leaves | the path-wide statistic was not time-reversal symmetric, so non-reversible leaves were accepted |
| Recoverable failures refine through (kernel v10) | WP10 `invalid_evaluation_parity_v1` | 4,000/4,000 oracle; Stock–Watson 3.4 M recoverable evaluations with zero invalid stops | upstream semantics: `-inf` with zero gradient is a zero-density point, integration continues |
| Refinement levels 4 to 8 | WP28 `funnel_defaults_v1`, WP29 | funnel unbiased on every seed; 1.00–1.05x on ordinary targets; levels 5–8 never selected on posteriordb | the cap never engages where stiffness is uniform and is required where it is local |

## What did not work

| change | study | result | why |
|---|---|---|---|
| Lower `delta` (0.5, 0.25) at four levels | WP28 | bias worse, 11,000–12,000 exhaustions | tighter tolerance without enough levels exhausts instead of refining |
| Raising the step so refinement does work (`da06`, `paper06`, `stanacc`) | WP34 | 0.60–0.83x per gradient | the error distribution has no stiff subpopulation; a larger step moves the whole population |
| `delta = 2` at the shipped step | WP34 (1.070x), WP37A | near miss; funnel gross-safety F3/F4 failed | `accel_gp` 0.68x where refinement does real work; divergence seeds spread 6/12 |
| Coarsest-first reverse order | WP37B | paused; descriptive reverse calls 1.086x against the candidate | more reverse work on the completed targets; state-space target failed on the incumbent arm |
| `ZeroWeightBeyond` | WP39 | 0.981x, targets 0.904x, `accel_gp` 0.61x | the step statistic counted zero-weight leaves and dual averaging raised `h` 3–30 % |
| `ZeroWeightBeyondAdaptSelected` and fixed-step pairs | WP39B | 0.878x; fixed step 0.908x on targets | the zero-weight tail costs gradients wherever the failure region is large; only the noncentered eight schools gain (about 1.2x) |

## Current default

`delta = 1` (`max_error`), `max_refinement_levels = 8`,
`ReverseCoarserPolicy::StopOrbit`, finest-to-coarsest reverse checks,
`ExhaustionRule::AcceptUnlessDivergent` during warmup only and `Stop` for
retained draws (any accepting rule in the retained phase loses the funnel
neck, WP24). `ZeroWeightBeyond`, `ZeroWeightBeyondAdaptSelected` and the
order variant remain research-only behind the `research` feature. Every
kernel fingerprint is unchanged since v10. Evidence in the
[ledger](../research-ledger-2026-08-31.md).

## Open questions

- A target-adaptive `delta` that reaches 2 where the |dH| distribution
  allows it is not ruled out by WP37A, but no such rule is in the queue.
- The dual-averaging statistic's reaction to one failed refined leaf is the
  same behaviour that protects the stiff targets and that inflates warmup on
  the smooth ones (WP40). A statistic that separates "one refined leaf
  failed" from "the step is too large" without ending at a larger step is
  the open kernel design question.
- `accel_gp` (0.47x CmdStan in v5, 54 % reverse-coarser stops, 0.61–0.72x
  under every untruncated variant) should be treated as a model whose
  difficulty is not a truncation artefact.
- The funnel and Eight Schools side checks of WP34 were never run; any
  future `delta` flip must rerun them.
