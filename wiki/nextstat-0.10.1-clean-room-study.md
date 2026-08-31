# NextStat 0.10.1 clean-room transfer study

Status: exploratory research and preregistration, 2026-08-30. No NextStat
implementation source was inspected or copied. No oWALNUTS sampler source was
modified. This is an engineering license boundary, not legal advice.

## License and provenance boundary

NextStat 0.10.1 declares
`AGPL-3.0-or-later OR LicenseRef-Commercial` in its official PyPI metadata.
The assessed Windows wheel was isolated under the matched-competitor study;
SHA-256:
`0da71cfcac022902a659d4923d327737f6f84b0271908ff8fa19345a688ac588`.
oWALNUTS is MIT. Copying or translating expressive NextStat implementation
code into the MIT tree is therefore out of scope absent a commercial grant or
an explicit decision to satisfy AGPL obligations.

The clean-room input set is restricted to:

1. public NextStat documentation, PyPI metadata and advertised API behavior;
2. published mathematical papers and public Stan documentation;
3. black-box outputs from the isolated official wheel;
4. oWALNUTS's own implementation and MIT Walnutpie provenance.

Copyright does not protect statistical ideas, equations, or methods as such,
but it does protect expressive text and code. Consequently, an implementation
may be independently derived from the cited mathematics, with new naming,
structure and tests; prose, pseudocode, constants, tests, or control flow
specific to the AGPL implementation must not be transcribed. Patent clearance
is a separate question and was not established here.

Primary provenance:

* official package/version/license:
  <https://pypi.org/project/nextstat/0.10.1/>;
* public Bayesian/API description:
  <https://nextstat.io/docs/bayesian> and
  <https://nextstat.io/docs/python-api>;
* vendor's NUTS/progressive-sampling report:
  <https://nextstat.io/blog/nuts-progressive-sampling>;
* matched artifacts outside this repository:
  `C:\dev\polyscope\STUDIES\matched_competitor_eight_schools_v38\`
  (`nextstat-protocol.json`, `nextstat-results.json`,
  `NEXTSTAT-REPORT.md`, and the public-API harness);
* Hoffman and Gelman, *The No-U-Turn Sampler* (JMLR 2014):
  <https://jmlr.org/papers/v15/hoffman14a.html>;
* Betancourt, *A Conceptual Introduction to Hamiltonian Monte Carlo*,
  Appendix A.3.2 (2017/2018): <https://arxiv.org/abs/1701.02434>;
* Stan's public algorithm description:
  <https://mc-stan.org/docs/reference-manual/mcmc.html>;
* Xu et al., *Couplings for Multinomial Hamiltonian Monte Carlo* (AISTATS
  2021): <https://proceedings.mlr.press/v130/xu21i.html>;
* Robnik et al., *Faster parallel MCMC: Metropolis adjustment is best served
  warm* (LAPS, 2026): <https://arxiv.org/abs/2601.16696>.

## What “progressive sampling” and “LAPS” mean

They are different algorithms and must not be conflated.

For a completed old trajectory with total weight `W_old` and a newly built
subtree with weight `W_new`, Betancourt's biased progressive sampling selects
the new subtree candidate with

`p_new = min(1, W_new / W_old)`.

Within a recursively built subtree, ordinary multinomial merging instead uses

`p_new = W_new / (W_old + W_new)`.

The weights are sums of `exp(-H)` (equivalently a common-reference Hamiltonian
offset). Log weights should be accumulated with log-sum-exp. This independent
description follows Betancourt A.3.2 and the Stan manual, not NextStat code.
Bias toward the newly doubled half can reduce self-retention and induce useful
negative lag-one correlation while preserving the valid progressive
construction. It can also make mean ESS exceed the number of retained draws;
that is not an ESS bug. It need not improve tail, variance, or squared-
functional ESS, so those remain co-primary diagnostics.

oWALNUTS already has the mathematical distinction: recursive subspans use
normalized multinomial/Barker selection, while the outer doubling join uses
the old-versus-new Metropolis/progressive probability. Thus the transferable
NextStat clue is primarily a diagnostic and ablation target, not evidence that
oWALNUTS is missing progressive sampling.

LAPS is the Late-Adjusted Parallel Sampler from Robnik et al. (2026), not a
synonym for NUTS progressive selection. Its published design uses many parallel
chains, an initially unadjusted MCLMC phase, ensemble adaptation, and a later
Metropolis-adjusted exact phase. NextStat documents its `method="laps"` path as
a GPU MAMS/LAPS variant. The paper supplies an independently implementable
mathematical description, but LAPS is a distinct research program, depends on
large-chain parallelism, and is not the explanation for the measured
`sample_nuts` Eight Schools result.

## Measured clues from the matched artifacts

The frozen track used the built-in non-centered Eight Schools model, four
randomly initialized chains, 1,000 warmup and 1,000 retained draws, target
acceptance 0.95, depth 8, and an adapted diagonal metric. It is not strict:
the public API cannot impose the four frozen starts, expose the same
unconstrained density, or expose a compile-excluded kernel boundary.

Across the three frozen seeds:

* public-call wall was 0.0896--0.1131 s; fresh-process end-to-end was 1.5551 s;
* retained leapfrog totals were 54,184, 57,848 and 63,000; warmup totals were
  62,229--63,217;
* there were zero divergences and zero depth-8 stops;
* chain E-BFMI ranged 0.911--1.039 in the pilots (0.884--1.045 in the cold
  cell);
* minimum observed rates were 31,058.90 bulk ESS/s and 21,500.47 tail ESS/s.

The public wall advantage is decomposable but not attributable from these
artifacts alone. NextStat's own published Eight Schools table reports only
about 1.14x CmdStan ESS/leapfrog but about 2.03x ESS/s, implying about 1.78x
leapfrogs/s. That supports a mixture of sampler quality and implementation/
density throughput, not a pure selection-mechanism explanation.

### Post-hoc black-box mechanism probe

An exact rerun of frozen seed 130038102 was made through the same public API
only. It is exploratory, was not preregistered, and is not new benchmark
evidence.

* 3,475/4,000 transitions (86.875%) had depth 4 and 15 leapfrogs; 439 (10.975%)
  had depth 3/7 leapfrogs; 84 (2.1%) had depth 5; one each had depth 2 and 6.
  There was no depth-cap pressure.
* Final chain step sizes were 0.326, 0.301, 0.267 and 0.204. Retained leapfrog
  totals by chain were 13,128, 13,984, 14,512 and 16,224. This substantial
  chain spread survives the common target and supports measuring random-start/
  adaptation effects instead of assuming them away.
* E-BFMI was 0.948, 0.968, 1.039 and 0.998. Energy lag-one correlation was
  0.480--0.526, as expected because position persists between transitions;
  leapfrog-count lag-one correlation was only 0.005--0.073.
* Bulk ESS divided by 4,000 draws was: `mu` 1.317, `tau` 0.878,
  `mean(theta)` 1.563, `sd(theta)` 0.944, `theta_1` 1.239 and `theta_8`
  1.202. Tail ESS/draw was 0.608--0.848 and never exceeded one.
* Per-chain lag-one correlations were predominantly negative: `mean(theta)`
  -0.327 to -0.089, `mu` -0.315 to 0.062, `theta_1` -0.231 to 0.031,
  `theta_8` -0.138 to -0.010, `sd(theta)` -0.177 to -0.016, and `tau`
  -0.160 to 0.023. Lag two was small and usually positive. This is the direct
  mechanism for bulk ESS exceeding draws: alternating/anticorrelated retained
  values reduce the integrated autocorrelation sum.
* Squared-functional lag-one correlation was less negative and sometimes
  positive (for `mu`, -0.157 to 0.109). This agrees with the published warning
  that a selection rule favoring distant states can improve location ESS more
  than scale/variance ESS.
* Bulk ESS/leapfrog ranged 0.0607 (`tau`) to 0.1081 (`mean(theta)`);
  tail ESS/leapfrog ranged 0.0420--0.0586.
* Squared jump versus leapfrog-count correlations were only -0.009--0.074;
  functional value versus depth/leapfrogs was within about +/-0.066.
  Consequently the clue is candidate selection along mostly similar-length
  trajectories, not simply deeper trajectories or larger work per transition.

Random-start effects remain only partially identified. The retained chain
means were close enough for rank R-hat to pass, but the approximately 1.6x
range in final step size and 24% range in retained work show that public random
initialization can alter adaptation. No warmup states or explicit starts are
public, so this cannot be promoted to a strict causal estimate.

Model specialization is also unresolved. The built-in model may use
specialized native density/gradient code, while oWALNUTS's timing boundary is
different. The published 1.78x implied leapfrogs/s and the 1.14x ESS/leapfrog
ratio are the best current decomposition. They argue against attributing the
whole result either to Rust speed or to progressive selection.

## Ranked clean-room research plan

1. **Selection-mechanism ablation in oWALNUTS.** Add a test-only/versioned
   experimental switch between the existing outer biased-progressive join and
   normalized outer multinomial join. Keep dynamics, stop rule, metric,
   adaptation schedule, target calls and depth fixed. Persist candidate
   distance from transition start, old/new selection counts, self-retention,
   per-functional and squared-functional ACF/ESS, ESS/leapfrog, tail ESS and
   ESJD. This directly tests the claimed transferable mechanism.
2. **NextStat adaptation black box.** Freeze a small factorial public-API
   experiment on the identical built-in target: metric `unit` versus
   `diagonal`, and initialization `random` versus each available deterministic
   strategy. Use multiple fresh seeds; compare final step sizes, mass diagonal,
   work, depth, E-BFMI, per-functional ACF and ESS/leapfrog. Do not tune from
   results.
3. **Density-specialization qualification.** Before sampling, determine only
   from public API whether the exact non-centered target can be supplied as a
   generic callback with parameter names and diagnostics identical to the
   built-in model. If yes, freeze built-in-versus-generic calls with the same
   sampler settings; posterior agreement and leapfrog distributions test
   semantic parity, while wall/leapfrogs-per-second isolates density
   specialization. If no, record the factor as unidentified.
4. **Random-start sensitivity.** If an API version exposes explicit starts,
   use the existing four frozen unconstrained starts. Otherwise compare public
   strategies only and retain the non-strict label. Report between-chain
   dispersion of final step, mass, work and early retained means.
5. **Cross-model generality.** Repeat the selection ablation on isotropic and
   anisotropic Gaussians, Neal's funnel, Eight Schools, and the existing
   structured rank-two target. Require no regression in tail/squared-
   functional ESS or health; a location-only win is insufficient.
6. **LAPS only as a separate project.** Reproduce the paper from its equations
   and permissively licensed independent references, after a patent/license
   review and only if oWALNUTS wants a many-chain microcanonical sampler. Do
   not mix this with the NUTS selection ablation.

## Preregistered smallest ablation

Name: `outer-selection-bps-vs-multinomial-v1`.

Hypothesis: on the same trajectory, stopping and adaptation, the published
outer biased-progressive join lowers lag-one autocorrelation and raises
location bulk ESS/leapfrog relative to normalized outer multinomial selection,
without degrading health, tail ESS, or squared-functional ESS.

Design:

* two arms differing only in outer join probability:
  `min(1, W_new/W_old)` versus `W_new/(W_old+W_new)`;
* recursive subtree selection remains normalized multinomial in both arms;
* first run a deterministic Gaussian oracle proving stationary moments,
  reversibility/accounting invariants and identical leapfrog/depth/target-call
  traces under scripted direction and dynamics randomness;
* then use a bounded, fresh-seed Eight Schools pilot with identical starts,
  warmup, retained count, target acceptance, metric and maximum depth;
* analyze the six frozen functionals plus their squares;
* primary estimand: geometric mean ratio of bulk ESS/leapfrog over the six
  unsquared functionals;
* co-primary safety gates: zero new divergences/invalid evaluations, depth-cap
  rate not increased by more than 0.5 percentage points, minimum tail
  ESS/leapfrog ratio at least 0.95, and minimum squared-functional bulk
  ESS/leapfrog ratio at least 0.95;
* mechanism checks: lower initial-state retention, more negative lag-one ACF,
  similar depth/leapfrog distributions, and unchanged E-BFMI within
  descriptive Monte Carlo variation;
* success requires primary ratio >=1.10 and every safety gate. Otherwise make
  no general sampler change.

Because oWALNUTS already uses the biased-progressive outer join, the first
execution is a reverse ablation: it quantifies whether removing the mechanism
hurts. It cannot justify a source change unless current behavior fails the
oracles or a separately preregistered refinement beats it. No expensive
evidence run is authorized by this document.

## Independent selection derivation and implementation

For disjoint eligible old and new orbit sets `A` and `B`, define
`W_A = sum_{x in A} exp(-H(x))` and `W_B` analogously. Conditional candidate
draws inside each set have probabilities `exp(-H(x))/W_A` and
`exp(-H(x))/W_B`. Exact normalized outer selection chooses `B` with

`P(B | A union B) = W_B / (W_A + W_B)`,

so any eligible state `x` is selected with exactly
`exp(-H(x))/(W_A+W_B)`. The existing biased progressive rule instead proposes
the new-set candidate and accepts it with `min(1, W_B/W_A)`.

Both rules preserve the extended target when orbit construction and its
direction-reversal involution are symmetric. For the normalized rule, the
forward/reverse cross-set probability flux is proportional to
`W_A W_B/(W_A+W_B)` in either direction. For the progressive rule it is
`W_A min(1,W_B/W_A) = min(W_A,W_B)`, again symmetric under exchanging the two
sets. Within-set candidate selection contributes the same `exp(-H)` factor on
both sides. Momentum refresh and the volume-preserving reversible integrator
then marginalize this invariant extended transition back to the target in
position space. This argument requires eligibility and stopping to be
selection-independent; the implementation changes only the final outer
candidate coin and leaves recursive joins, dynamics, and stopping untouched.

Weights are never exponentiated before normalization. The implementation uses
`logaddexp(log W_A, log W_B)` and compares `log(U)` with either
`log W_B - logaddexp(...)` or `log W_B - log W_A`. Thus overflow is avoided,
underflow becomes a valid near-zero probability, and the progressive
probability automatically saturates at one when its log value is positive.

The research-only `RunConfig::with_research_outer_orbit_selection` switch now
selects `BiasedProgressive` or `ExactNormalizedMultinomial`. Its constructor
default remains biased progressive. The switch is target-agnostic and is
threaded through traced, untraced, cached, and uncached transition paths.

Validation completed before any evidence run:

* closed-form and 10,000-point categorical-frequency oracles for both rules;
* extreme-log-weight stability and exact one-uniform accounting;
* existing Gaussian leapfrog reversibility, Barker detailed-balance,
  stationarity, work/RNG, and sequential/parallel determinism suites;
* an explicit full-facade proof that the default and explicit biased policy
  are bit-identical;
* `cargo test`: 134 passed, 0 failed, 1 ignored (96 library, 38 public facade).

The bounded Eight Schools pilot was **not executed** in this implementation
pass. The preregistered evidence protocol requires frozen starts, seeds,
aggregation code, bulk/tail and squared-functional ESS estimators, and
posterior/health gates to exist as reviewable scripted artifacts before
sampling. Those artifacts were not present in the repository, and creating
only an ad-hoc sampler run would violate the freeze-before-sampling rule.
Consequently there is no efficiency ratio to report, the >=1.10 advancement
gate was not evaluated, and this ablation does not yet establish whether outer
selection explains any part of the NextStat gap.
