# Negative results: what did not work, and why

Roughly half the preregistered studies decided against the hypothesis that
motivated them. This page lists them so nobody reruns them by accident. Each
entry names the study, states the result in one line, and gives the mechanism
where one was established. Details are in the
[ledger](research-ledger-2026-08-31.md) and the topic pages under
`findings/`.

## Claims that were true on the targets they were measured on and did not generalise

- **The 0.1 headline numbers** (WP22). Fastest on Eight Schools, exact on the
  funnel, 4x NumPyro on sspd-05: all true, and at package defaults the
  sampler lost to CmdStan on every posteriordb model and ran 10x slower per
  gradient. The 10x was a toolchain artefact; the per-gradient gap was real.
- **The v7 sspd-05 advantage of 5.4 to 7.3x** (WP14): retired; the matched
  figure is 4.03x wall at per-work parity.
- **Eight Schools "conservative minima" of 19,055 / 14,494 ESS/s** (WP8):
  they were medians; the minima were 8,634 / 5,949 on v7 and 12,830 / 10,346
  on v9.
- **The paper's Stock-Watson contrast** (WP2b): on a simulated series the
  paper's fixed tuning refines four to five halvings below h/8 on 86 % of
  transitions and the NUTS control is stable; the Figure 16 contrast is
  data-specific.

## Adaptation

- **Appendix C as the default warmup** (WP22, WP23). From uniform starts the
  K-quantile rule installs delta near 0 at transition 74 and never recovers;
  after the v4 robust rule it is at parity with dual averaging (0.995x) and
  not better.
- **The paper's (delta, h) pair from the paper's stated rule** (WP7). The
  delta rule's fixed point is a curve in (delta, h); the unrefined fraction
  is position dependent on the funnel, and the paper's own tuning does not
  satisfy Gamma = 0.8.
- **A cumulative unrefined statistic** (WP9). Dual averaging integrates a
  lagged running mean as a persistent offset; h spread 26 to 95x.
- **Step-side remedies for the sblrc/earnings collapse** (WP27). Stan's
  statistic, Stan's step search at every window, the delta ramp, mu = ln 10h,
  a floor at half the search result, a within-stream shrink bound: all left h
  at 0.003 to 0.007, because the cause was the metric floor.
- **A warmup step floor** (WP24, WP27): pins the sliding `arma11` chains that
  the one-sided rule is escaping.
- **Warmup-only untruncated orbits** (WP40): remove every step crash and
  raise warmup gradients 11 to 17 %.
- **Skipping the single-leaf reverse-coarser statistic** (WP40): 1.02x
  overall, 0.82x on the four target models, because the final step rises
  10 % and the GP models are step-sensitive.
- **A per-iteration descent bound on the log step** (WP40): 0.73x; keeps
  the step high through the divergence region, `arma11` R-hat 1.26.
- **A NUTS initial phase** (WP40): 0.93x; helps where the initial phase
  overshot (`lotka_volterra` 1.5x) and breaks `accel_gp` (0.24x).
- **Stan's doubling initial step search at the sampler defaults** (WP40):
  0.88x; installs a near-zero step on `arma11`, `kidiq`, `accel_gp`.
- **A higher acceptance target (0.85, 0.9) with the skip statistic** (WP40
  addendum): 0.90 to 0.96x; `accel_gp` 0.52 to 0.65x; the higher target is
  paid during sampling on every model (0.89 to 0.94x sampling-only).

## Kernel rules

- **`MomentumSum` alone as the default** (WP26): 1.064x geomean, worst
  0.78x. The correct reading came later (WP30): the gain is hidden by the
  unit-floored metric and appears with Stan regularisation.
- **Stan regularisation alone** (WP27, WP29): fixes `sblrc` and loses
  `earnings`, `kidiq`, `diamonds`, `hmm_drive_0`, `one_comp` gates, because
  endpoint U-turn orbits are too short at the corrected metric and the window
  variance re-floors.
- **`EndpointsWithCross`** (WP26, WP30): 0.69 to 0.81x.
- **Exact multinomial outer selection** (WP3-1): 0.57x the biased-progressive
  join on Eight Schools; self-retention 10.7 % against 0.4 %.
- **Retained-phase acceptance of exhausted leaves** (WP24): loses the funnel
  neck (z -7) under either the one-sided or the two-sided rule.
- **Lower delta at four levels** (WP28): 11,000 to 12,000 exhaustions, worse
  bias.
- **Raising the macro step to let refinement work** (WP34): the leaf-error
  distribution is one smooth population; `P(|dH| > 1)` goes from 0.4 to 6 %
  at h to 28 to 62 % at 2h. Every step-raising arm loses.
- **Fixed delta 2** (WP34 near miss 1.070x; WP37A not qualified): `accel_gp`
  0.68x; funnel gross-safety on 6 of 12 seeds.
- **Coarsest-first reverse check order** (WP37B): paused after a target
  fault; descriptively 1.086x more reverse calls than the incumbent.
- **Carrying the orbit past a failed reverse check** (WP39, WP39B): 0.981x
  with the step confound, 0.878x without it, 0.908x on the targets at an
  identical fixed step. Pays only on the noncentered eight schools (1.2x).
  The WP34 truncation hypothesis is closed.
- **`RejectLeaf` for a non-finite proposed position** (WP38): exact and
  bit-identical elsewhere, but the registered health gate failed on the
  target itself for both arms.
- **Fixing the step from the first warmup transition** (WP39B fixed arms):
  2 to 8x warmup gradients and `arma11` never builds a leaf. Any fixed-step
  design must fix the step after the step search and first mass window.

## Chain rescue

- **Pooling at window boundaries** (WP33): 23 of 27, never moves a frozen
  chain, `lotka_volterra` 0.42x.
- **Two-consecutive-hit restart** (WP36): reduced nuisance restarts 35 to 14
  but failed sample size, efficacy, funnel and efficiency gates.
- **`restart_from_best` as the default** (WP33 yes, WP36 no): the density
  rule fires on merely late chains at the first boundary and overwrote
  mapped origins; the frozen classifier found zero HMM origins, so the
  mode-destruction risk could not be bounded.

## Metrics and parameterisations

- **Prior-precision path metric** (WP4): caps 92 to 93 % at T=1000; the
  level direction is the stiff one, not the slow one (the preregistered
  mechanism clause was wrong).
- **Any diagonal metric caps at T=1000** (WP4b): false; centered adapted
  diagonal passes sspd-11 at depth 8.
- **A stiff correct path block with globals free** (WP4b P2): worse than P;
  the residual is global to path scale coupling.
- **Per-window structured-metric refresh** (WP16): early windows at small
  steps underestimate a slow global's variance; installed precision entries
  near 2,000, oscillating boundary step searches.
- **Full scale non-centering of state-space innovations** (WP17): relocates
  the funnel to moderate and large sigma_x; NumPyro saturates depth 12.
- **The one-shot tridiagonalised metric on crypto SV at T of about 3,000**
  (WP19, WP21): windowed adapters get 1.5 to 2x more global ESS on the (a, s)
  ridge.
- **The path block at T=100** (WP14): no advantage.

## Platforms

- **Enzyme autodiff on Windows** (WP15a): nightly accepts `-Zautodiff` but
  ships no `libEnzyme`.
- **The `reverse` tape crate** (WP15a): 58 to 68x a hand gradient.
- **Resident DLLs plus joined Rayon workers as the Windows fix**
  (`bridgestan_lifetime_v1`): 8 of 180 children still fault.
- **`sspd-10` as a qualification fixture** (WP4b, WP17): no tested Euclidean
  sampler, NumPyro included, handles it; retired to a stress cell.

## Designs that were wrong, recorded so they are not repeated

- Comparing two arms that both fail (R-hat 1.5 to 2.2, ESS below 10) is
  uninformative, not a falsification (programme 2026-08-31).
- A health gate that both arms fail measures the target, not the policy
  (WP38). Use paired gates.
- Fixing the step from the first warmup transition (WP39B).
- A conjunctive "no model below 0.85x" clause with no carve-out for models
  that fail every arm decided WP31 on a mode lottery.
- Under-powered single-seed funnel z (WP24's z -1.70 at s.e. 0.014 hid a
  bias that three seeds showed at z -3 to -11 in WP26).
