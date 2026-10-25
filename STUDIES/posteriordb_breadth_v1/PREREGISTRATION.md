# posteriordb breadth v1 — preregistration (WP46)

Frozen 2026-10-24 before the first evidence cell. The machine-readable copy is
`protocol.json`; the selection is reproduced by `select_posteriors.py`
(`artifacts/selection.json`). Source under test: `main` at `3583d130`, the
shipped 0.2.0 defaults. Seeds 461461, 461462, 461463 were verified unused by
`git grep -w` over every tracked file and over the sibling worktrees' study
protocols before this freeze.

## Question

Six posteriordb runs (v1–v6) used the same 17 posteriors, and every default
change since v1 was tuned or validated against them. What failure modes does
the shipped default have on posteriordb posteriors it has never seen, and
which open questions do they belong to?

This is an out-of-sample characterisation. It decides no default.

## What is under test

`owalnuts::sampler::Sampler` with nothing overridden: `Tuning::default()`
(h0 0.5, depth 10, eight refinement levels, delta 1, `MomentumSum`),
`Metric::diagonal()` with Stan regularisation, `Adaptation::default()`
(dual averaging at 0.8, `AcceptUnlessDivergent` warmup exhaustion rule,
**no chain rescue** since WP36), `Init::uniform()`,
`Limits::admit_worst_case()`. Note that v6's 45/51 was measured with
`restart_from_best` on; the shipped default no longer has it.

The BridgeStan target is `ReplicatedStanTarget` with four requested replicas.
On Windows this is one owned worker that serialises every native call
(`bridgestan_owned_worker_v1`), so the four chains share one gradient thread.
Walls are contended twice over (ten agents on 16 cores, plus the serialised
worker). They are labelled and are not evidence.

## Availability finding (before selection)

At posteriordb `28f8d3d` only 47 of 147 posteriors have reference draws.
Removing the 17 leaves 30, and 22 of those are ARM-book linear regressions in
five dataset families. **No reference-draw posterior exists for
survival/censoring, ordinal regression, GLMMs or hierarchical logistic
models, hierarchical models with hundreds of parameters, or ARMA/GARCH
variants beyond the three already used.** The only new reference-draw
structures are an ordered two-component mixture, an ill-conditioned
regression (`kilpisjarvi`, reference |corr| 1.0000), a Gaussian-likelihood
GP, a normal-emission HMM with simplex and ordered parameters, and an
independent-beta BLR.

## Selection (frozen rule, applied before any sampling)

**Reference tier (14 posteriors, 42 cells).** The difficulty proxy is the
condition number of the reference draws' correlation matrix, computed from
posteriordb reference information only. Take (a) every eligible posterior
that is the only eligible member of its dataset family, and (b) from each
multi-member family the two highest-condition members if the family has at
least four eligible members, else the single highest. Result, in run order:
`low_dim_gauss_mix`, `kilpisjarvi`, `gp_regr`, `hmm_drive_1`, `sblri-blr`,
`logearn_logheight_male`, `logearn_height_male`, `kidscore_interaction`,
`kidscore_mom_work`, `kidscore_interaction_c2`, `logmesquite_logvas`,
`mesquite`, `nes1996`, `nes1980`.

**Gates-only tier (5 posteriors, 15 cells, supplementary).** Because the
requested families have no reference draws, one posterior per absent family
that compiles here is added, chosen by family before any sampling:
`seeds_centered` (hierarchical logistic, centred, 21 groups),
`GLMM_Poisson` (Poisson GLMM, 40 random effects, box-bounded uniform
priors), `radon_all-radon_hierarchical_intercept_centered` (386 groups,
391 parameters), `sat-hier_2pl` (hierarchical IRT, Cholesky correlation,
about 670 parameters), `science_irt-grsm_latent_reg_irt` (ordinal
rating-scale IRT, about 400 parameters). These get the gates and the
telemetry but no z statistic and no reference-draw disagreement class. They
run after the complete reference tier, so a slow gates-only cell cannot cost
reference-tier evidence.

Every selected model was compiled with BridgeStan before this freeze
(`artifacts/compile-status.json`); compilation is not evidence. A harness
smoke test ran one seed on the already-used Eight Schools pair with seed 1,
outside the study artifacts.

## Protocol

- oWALNUTS only, shipped defaults, 4 chains x 1,000 warmup / 1,000 retained,
  four threads, seeds 461461–461463, strictly sequential in the listed order;
- 2,700-second cell timeout (v6);
- gates (house standard): rank R-hat <= 1.01, bulk and tail ESS >= 400 on
  every gate parameter, zero retained divergences, finite draws, no sampler
  error; ArviZ 0.23.4 estimators;
- reference tier: z of every reference parameter's mean against the
  posteriordb reference draws, `z = (mean - mean_ref) / sqrt(mcse^2 +
  mcse_ref^2)`, flag max |z| > 4 (v6 P2);
- per-cell telemetry: per-chain final step and warmup step trace, depth-cap
  fraction, refined-leaf fraction, divergences, refinement exhaustions,
  invalid / zero-density / non-finite evaluations, stop histogram, metric
  installed-over-empirical variance, cross-chain disagreement, per-chain
  displacement from the reference, gradients, contended wall;
- no CmdStan or nutpie reruns; v5/v6 artifacts are cited where relevant.

## Failure taxonomy

Every failing cell and every borderline passing cell (R-hat > 1.005, minimum
ESS < 600, or max |z| > 3) gets mechanical labels from frozen telemetry rules
(`protocol.json` → `taxonomy.mechanical_classifier`): process error; start
lottery (cross-chain disagreement > 0.5 sd with R-hat failure and the outlying
chain at worse energy) or multimodality (same disagreement without the
energy gap); depth cap (> 5 % capped); step collapse (a chain's step < 0.2 x
the median); metric floor (installed variance > 2 x the retained variance on
a coordinate whose variance is < 1e-4); constraint boundary (> 0.1 % invalid
evaluations or any invalid stop); divergence; reference-draw disagreement
(|z| > 4 while chains agree); unclassified slow mixing. The README then gives
one paragraph per flagged cell, and a table mapping each to
`wiki/open-questions.md` items or to a new class.

## Predictions (frozen)

- **P1** The reference tier passes **32 of 42** cells (76 %), about 12
  points below v6's 45/51 (88 %) on the tuned set; interval 28–36. The rate
  is below 45/51.
- **P2** At least one cell fails on each of `kilpisjarvi` (depth cap),
  `hmm_drive_1` (start lottery or multimodality),
  `logearn_logheight_male` (depth cap), `kidscore_interaction` (depth cap or
  slow mixing), and the gates-only `seeds_centered` (divergence); every other
  model passes 3/3.
- **P3** The gates-only tier passes 10 of 15 cells; interval 7–13.
- **P4** No passing reference-tier cell has max |z| > 4.
- **P5** All 57 cells complete with status ok (no process error or timeout).
- **P6** The most frequent primary mechanism among failing reference-tier
  cells is the depth cap.

## Decision rule

No default change follows from this study. Its outputs are the taxonomy, a
prioritised list of new problems, and a recommended five-posterior candidate
set for a future v7 breadth benchmark chosen by the frozen rule in
`protocol.json` (`decision`): posteriors with a failing or borderline cell,
new failure classes first, then by open-question rank, then fewest passing
seeds, at most one per dataset family, filled from the gates-only tier if
fewer than five qualify.

## Rules

Report all cells; no result-driven reruns; failures are results; no tuning
after seeing results. A crashed driver may be relaunched and only an
interrupted cell with no completed artifact rerun from scratch, recorded as a
deviation.
