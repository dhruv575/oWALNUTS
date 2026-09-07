# Step size and warmup adaptation: what worked and what did not

## State of knowledge

The shipped sampler adapts its macro step with Stan-style dual averaging on the
`CurrentCoarseEndpoint` statistic (the mean of `exp(-|dH|)` over the coarsest
attempt of every built leaf), target acceptance 0.8, a Stan-like 75/25/50
warmup schedule, no initial step search, `h0 = 0.5`, and Stan's one-sided
exhaustion rule for warmup transitions only. Every alternative that was
measured either froze chains (the paper's K-quantile rule from bad starts),
was a wash (the paper rule after its v4 robustness fix), or bought warmup
gradients on smooth models by ending at a larger step that the stiff target
models cannot afford (WP40). The one adaptation change that did flip a default
was not a step rule at all: the metric regularisation floor (WP27) and the
warmup-only one-sided exhaustion rule (WP24). The remaining per-gradient gap
to CmdStan on healthy models is warmup, and it is caused by the statistic's
reaction to a single failed refined leaf. Evidence for every statement here is
in the [ledger](../research-ledger-2026-08-31.md).

## Timeline of evidence

- **Programme 2026-08-31, item 4.** The beta replaced the paper's Appendix C
  warmup with dual averaging on the coarsest-level endpoint energy error. Neal
  funnel v3 diagnostics measured that statistic's correlation with
  accepted-trajectory acceptance at only 0.31 to 0.44. An adapter that shrinks
  `h` until the coarse step passes on its own was flagged as defeating the
  point of WALNUTS and confounding every metric experiment run under it.
- **WP1.** Appendix C implemented as an opt-in `WarmupConfig` mode: K-quantile
  delta rule (`delta = Delta / q_K(p_a)`, defaults `Delta = 2`, `p_a = 0.95`)
  and an `h` rule tracking the unrefined fraction toward `Gamma = 0.8`.
- **WP7** (`STUDIES/paper_funnel_adaptive_v1`). Both adaptive arms unbiased
  and health clean on the funnel from a conservative start, but the default
  recommendation rule was met only narrowly (bulk ESS/call 0.82x fixed paper
  tuning) and per-window `h` swung 10 to 30x because dual averaging restarted
  at every delta installation. Final `h` spread 2.38x (A2) and 3.86x (AD).
- **WP2b** (`STUDIES/paper_stock_watson_reproduction_v1`). The Gamma rule
  counted zero-leaf transitions as unrefined and drove `h` to the 1e6 bound
  under all-invalid transitions (defect 2).
- **WP9** (`STUDIES/paper_funnel_adaptive_v2`). Continuing dual averaging
  through delta installs passes every gate in both families: A2-R `h` spread
  1.21x, 1.41x/1.61x F9 bulk/tail ESS per call. The cumulative statistic was
  falsified (`h` spread 26 to 95x, 178 to 12,974 depth caps). Unrefined
  fraction now over built leaves only; leaf-less transitions contribute no
  update; paper step bounded to 1e3x the initial step. `ContinueThroughLocalErrorInstall`
  became the paper-mode default (`v3`, commit `8cadd94`).
- **WP17** (`STUDIES/canonical_v3_scale_noncentered_v1`). V2-A (Appendix C on
  the real T=1000 target) passed all gates on both healthy fixtures with
  1.02 to 1.20x ESS/call over dual averaging, single seed each.
- **WP22** (`STUDIES/posteriordb_bench_v1`). Appendix C at package defaults
  failed the preregistered rule: geomean paper/DA min-bulk-ESS per gradient
  0.077 over 12 models; 8/51 gates vs DA 26/51. From uniform(-2, 2) starts the
  first window's orbit energy ranges were 1e3 to 1e16, the K-quantile rule
  installed `delta ~ 0` at transition 74 and never recovered on nine models.
- **WP23** (`STUDIES/posteriordb_bench_v2`). The v4 robust rule removed the
  freeze but was parity with DA: geomean 0.995, at least as good on 13/17,
  loses `kidiq`, `sblrc`, `hmm_drive_0`, `accel_gp`. Not a default. The
  `stan_style(0.8)` preset scored 32/51 gates, 0.319x CmdStan per gradient.
- **WP24** (`STUDIES/freeze_mode_v1`). Frozen `arma11` chains start at log
  density -4.5e19 to -1.8e115; every downhill leapfrog has an astronomically
  negative energy error that WALNUTS' two-sided `|H_end - H_start| <= delta`
  turns into an exhaustion at the initial leaf, and the coarse statistic (0)
  drives `h` to 1e-20 to 1e-68 where `q + h v == q`. CmdStan escapes through
  its one-sided `H - H_0 > 1000`. `ExhaustionRule::AcceptUnlessDivergent` in
  warmup only: `arma11` 0 frozen of 12, `lotka_volterra` two of three seeds
  pass. Retained-phase acceptance of exhausted leaves loses the funnel neck
  (z -7.2), so the rule is warmup-only.
- **WP25** (`STUDIES/posteriordb_bench_v3`). Confirmation: zero frozen DA
  chains on 51 cells, `arma11` 0/3 to 2/3 (424x per gradient), `lotka_volterra`
  1/3 to 3/3; the two-sided stan-style control froze 7 of 12 chains. The
  remaining `arma11` failure is a crawl at `h ~ 1e-8` after the escape.
- **WP27** (`STUDIES/step_collapse_v1`). The `sblrc`/`earnings` step collapse
  is not the step rule. The `v10` regularisation floors every variance at
  0.0099; `sblrc` coefficients have posterior variance 1.07e-5, so the metric
  was 1,000x too wide and dual averaging correctly held `h` at 0.003 with its
  statistic exactly on 0.80. Stan's statistic, Stan's `init_stepsize` at every
  window, the delta ramp, `mu = ln 10h`, a step floor at half the search
  result and 4x/10x shrink bounds all left `h` at 0.003 to 0.007. Only
  `DiagonalMetricRegularization::Stan` gave `h` 0.10 to 0.12 and 9x per
  gradient. A step floor pins sliding `arma11` chains (negative control held).
- **WP28** (`STUDIES/funnel_defaults_v1`). At the sampler defaults one chain
  per seed adapts to `h` 0.007 to 0.019 on the funnel and either never leaves
  or never enters the neck; pooled tail mass right, `omega` R-hat 1.01 to
  1.04. Unbiased, not efficient.
- **WP32** (`STUDIES/posteriordb_bench_v5`). The same funnel caveat: one chain
  on seed 87103 at `h` 0.0013 with 933 depth caps.
- **WP34** (`STUDIES/refinement_role_v1`). Geomean adapted `h` / CmdStan step
  1.000 over 17 models (0.87 to 1.12 on the healthy fourteen). Every
  step-raising arm lost per gradient: `da06` 0.834x, `paper06` 0.604x,
  `stanacc` 0.670x.
- **WP40** (`STUDIES/warmup_gap_diag_v1`, instrumentation, not preregistered).
  On the 14 CmdStan-healthy models warmup gradients are 1.56x CmdStan's while
  sampling gradients per effective sample are about 1.05x. Per window: the
  initial fast phase 2.07x (24 percent of the excess), slow windows 1.14 to
  1.27x, terminal window 1.01x. Two mechanisms and four levers; see below.

## The warmup gap (WP40)

**Step crashes.** A single-leaf orbit that ends in a reverse-coarser rejection
feeds dual averaging a statistic of 0.02 to 0.36, which cuts the step 3 to 10x
in one iteration; recovery takes 5 to 10 depth-10 orbits of 1,023 gradients.
These crashes occur on every model at a nearly uniform rate (2.6 to 5.8
percent of warmup transitions, 21 to 46 per chain, median statistic about
0.2, targets and controls alike), so they do not discriminate stiff models.
They are a uniform downward bias of about 10 percent on the adapted step.

**Initial-phase overshoot.** From `h0 = 0.5` with an identity metric the first
dual-averaging iterates climb to `h` of 1 to 6 because fully refined leaves
still report an acceptable statistic; each of the first 3 to 4 transitions
costs about 1,146 gradients (eight refinement levels per leaf), then the step
overshoots down to about 0.006 and pays depth-10 orbits until it recovers.

Arm ratios to the shipped defaults (seed medians of min bulk ESS per
gradient, warmup included; targets are both eight schools, `gp_pois_regr`,
`accel_gp`):

| arm | seeds | geomean 17 | targets | controls | warmup grads | adapted step | worst |
|---|---|---:|---:|---:|---:|---:|---|
| `beyond-warmup` (untruncated orbits in warmup) | 92101 | 0.823 | 0.654 | 0.883 | 1.113 | 1.125 | 0.23 |
| `adaptsel-warmup` | 92101 | 0.913 | 0.806 | 0.949 | 1.169 | 1.021 | 0.44 |
| `stan-search` (Stan doubling step search) | 92101 | 0.882 | 0.748 | 0.927 | 0.987 | 0.972 | 0.43 |
| `skip` (single-leaf crash contributes no statistic) | 92101, 92102 | 1.021 | 0.817 | 1.093 | 0.905 | 1.095 | 0.63 `gp_pois_regr` |
| `descent2` (log step falls at most ln 2 per iteration) | 92101, 92102 | 0.726 | 0.541 | 0.795 | 1.296 | 1.053 | 0.15 `accel_gp`; `arma11` R-hat 1.26 |
| `skip+descent2` | 92101, 92102 | 0.740 | 0.641 | 0.773 | 1.179 | 1.133 | 0.16 |
| `initnuts` (initial phase without refinement) | 92101, 92102 | 0.933 | 0.614 | 1.061 | 0.963 | 0.997 | 0.24 `accel_gp` |
| `initnuts+skip` | 92101, 92102 | 1.051 | 0.783 | 1.151 | 0.863 | 1.094 | 0.48 `accel_gp` |

The warmup-only orbit policies remove every crash and still raise warmup
gradients 11 to 17 percent. Stan's doubling search helps the three models
whose initial phase was the overshoot (`hmm_drive_0`, `hmm_example`, `arK`)
and installs a near-zero step on `arma11`, `kidiq` and `accel_gp`. The NUTS
initial phase fixes `lotka_volterra` (1.52x) and breaks `accel_gp` (0.24x).
Every arm that saves warmup gradients ends at a larger step and loses on the
four targets. The bar (1.10x geomean with no model below 0.90x) was not met.

## What worked

| change | study | result | why |
|---|---|---|---|
| `AcceptUnlessDivergent` exhaustion rule, warmup only | WP24, WP25 | `arma11` 0 frozen of 12; zero frozen chains on 51 cells; no cost elsewhere | Stan's one-sided test lets a chain ride downhill from an astronomically bad start; the two-sided WALNUTS test made every such leaf an exhaustion |
| Continue dual averaging through delta installs (paper mode `v3`) | WP9 | `h` spread 1.21x, 1.41x/1.61x F9 ESS per call | Restarting dual averaging at each delta install was the cause of chain-specific `h` in WP7 |
| Unrefined fraction over built leaves only, bounded paper step | WP9 | All-invalid transitions no longer drive `h` to 1e6 | Fixes WP2b defect 2 |
| `DiagonalMetricRegularization::Stan` (with `MomentumSum`) | WP27, WP31, WP32 | `sblrc` `h` 0.003 to 0.10 to 0.12, 9x to 13.9x per gradient | The step "collapse" was the metric floor, not the step rule |
| Appendix C v4 robust rule | WP23 | No frozen paper cells; 29/51 gates (v1 8) | Delta floor and delayed first installation stop the `delta ~ 0` freeze |

## What did not work

| change | study | result | why |
|---|---|---|---|
| Appendix C as the default warmup (v1 rule) | WP22 | 0.077x DA per gradient; froze nine models | Orbit energy ranges 1e3 to 1e16 from uniform starts install `delta ~ 0` |
| Appendix C v4 as the default | WP23 | 0.995x DA; loses `kidiq`, `sblrc`, `hmm_drive_0`, `accel_gp` | Parity, not a gain |
| Cumulative unrefined statistic | WP9 | `h` spread 26 to 95x, hundreds to thousands of depth caps | Dual averaging integrates a lagged running mean as a persistent offset |
| Accepting exhausted leaves in retained draws | WP24 | Funnel neck lost (z -7.2) | The one-sided rule biases the funnel tail outside warmup |
| WP24 rule with Stan's statistic or preset | WP24 | Chains re-freeze | The coarse statistic, not the rule alone, is needed for the escape |
| Stan's statistic, init step search per window, delta ramp, `mu = ln 10h`, step floors, shrink bounds | WP27 | `h` unchanged at 0.003 to 0.007 on `sblrc` | The collapse was the metric floor |
| `stan_style(0.8)` preset | WP23, WP25, WP28 | 32 then 29 gates; two-sided control froze 7/12 chains; funnel biased with 2,132 divergences and an errored cell | Two-sided leaf test and `delta = 1000` fast phase |
| Higher target acceptance / step-raising arms | WP34 | 0.60 to 0.83x per gradient | The adapted step already equals Stan's; the leaf-error distribution is one smooth population |
| Warmup-only untruncated orbits | WP40 | 0.82 to 0.91x; warmup gradients up 11 to 17 percent | Longer orbits cost more than the crashes they prevent |
| Stan doubling initial step search | WP40 | 0.88x; near-zero step on `arma11`, `kidiq`, `accel_gp` | Helps only where the initial-phase overshoot was the problem |
| Skip single-leaf crash statistic | WP40 | 1.02x overall, 0.82x on targets | Adapted step ends about 10 percent larger; GP models lose |
| Per-iteration descent bound | WP40 | 0.73x; `arma11` R-hat 1.26 | Keeps the step high through the divergence region |
| NUTS initial phase (+ skip) | WP40 | 0.93x (1.05x with skip); `accel_gp` 0.24x to 0.48x | Refinement carried the initial phase on the GP targets |

## Current default

`Adaptation::DualAveraging { target: 0.8 }`, equal to
`WarmupConfig::new(0.8).with_mass_adaptation(true).with_metric_regularization(DEFAULT_METRIC_REGULARIZATION).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)`:
dual averaging on `CurrentCoarseEndpoint`, `h0 = 0.5`, no initial step
search, Stan's regularisation, `AcceptUnlessDivergent` in warmup only,
retained rule `Stop`, no chain rescue. Paper mode (`v4`,
`ContinueThroughLocalErrorInstall`) is a documented opt-in with `Delta` as its
single knob. The WP40 options (`with_warmup_reverse_coarser_policy`,
`with_skip_single_leaf_reverse_coarser_statistic`,
`with_dual_averaging_max_descent`) and `InitialStepSearchConfig::stan()` are
research-only, off by default, and bit-identical when off.

## Open questions

- A dual-averaging statistic that separates "one refined leaf failed" from
  "the step is too large" without ending at a larger step. The skip arm shows
  about 1.09x is available on the controls; the design must keep the hard cut
  where it protects the stiff targets. Kernel-level, needs a preregistration
  with fresh seeds and the four targets as the deciding class.
- Whether the target models' preference for a smaller step is better served
  by a higher acceptance target than by crash noise (a sweep of `skip` with
  targets 0.85 and 0.9 was launched after WP40; not yet scored).
- The per-chain funnel step collapse at the defaults (one chain per seed at
  `h ~ 0.01`, WP28/WP32), the same mode as the `arma11` post-escape crawl.
- The initial-phase overshoot from `h0 = 0.5` on an identity metric: no arm
  fixed it without breaking a target.
