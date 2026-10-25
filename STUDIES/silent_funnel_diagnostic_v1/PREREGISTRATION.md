# WP55 preregistration: a silent-funnel warning from existing telemetry

Frozen 2026-10-25 on `wt/silent-funnel` (base `3924b090`) before the first
evidence cell. Machine-readable version: `protocol.json` (it governs where the
two differ).

## Question

WP46 (`STUDIES/posteriordb_breadth_v1`) found the *silent funnel*: on
`seeds_data-seeds_centered_model` oWALNUTS reports zero divergences while one
chain sticks in the funnel neck (R-hat 1.02-1.07 on `sigma`, per-chain ESS
6-7). Refinement absorbs the energy error that would have made NUTS diverge,
so the user loses Stan's reparameterisation signal. Does a per-chain
statistic that the default run already records separate silent-funnel runs
from clean runs well enough to ship as an observe-only warning beside WP44's
`ChainWarning`?

Statistics (per chain, from telemetry already collected; nothing is
configured):

* **R, refined-leaf rate**: `(leaves_built - refinement_level_built[0]) /
  leaves_built` over the retained partition (`RunTelemetry::retained()`).
* **S, step-collapse factor**: median over the cell's chains of the
  end-of-warmup step (`RunTelemetry::warmup_end().step_size()`) divided by the
  chain's own end-of-warmup step.
* Recorded, not tested: mean refinement level (all leaves, and refined leaves
  only), end-of-warmup and final step, retained and warmup divergences, depth
  caps, refinement exhaustions, WP44 warnings by check and chain.

## Design

* oWALNUTS at the shipped `Sampler` defaults, the WP44 cell verbatim (4
  chains x 1,000/1,000, `Init::uniform()`, no chain rescue, four threads,
  BridgeStan 2.9.0). Kernel revision must be
  `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`.
* Fresh seeds **731401, 731402, 731403** (reference runs 731410, 731411),
  verified unused by `git grep -w` here and on `main`, and over every sibling
  worktree's `protocol.json` / `PREREGISTRATION.md`.
* **Positives (4)**: the house 10-D Neal funnel at 1,000/1,000 (house starts
  omega in {-3, -1, 1, 3}), `eight_schools_centered`, `seeds_centered`,
  `radon_all-radon_hierarchical_intercept_centered`.
* **Negatives (14)**: the 13 house models with oWALNUTS 3/3 in posteriordb v6
  (arK, arma11, hmm_drive_0, diamonds, logearn_interaction, garch11,
  gp_pois_regr, hmm_example, lotka_volterra, kidscore_momhsiq,
  logmesquite_logvash, nes, one_comp_mm_elim_abs) plus
  `eight_schools_noncentered`. (In v6, eight_schools_noncentered is itself
  3/3; the list is the 14 3/3 models.)
* Order: positives in the listed order, then negatives, seeds ascending,
  strictly sequential, each cell launched once (launch markers); timeout
  2,400 s; failures are results.
* **References**: posteriordb reference draws for every negative and for
  eight_schools_centered; exact moments and the exact tail mass
  P(omega < -5) = 0.0478 for the funnel. posteriordb has no reference for
  seeds_centered or radon centered, so before the cells (not evidence) a
  CmdStan 2.39.0 reference is drawn from the identical posterior written
  non-centred (`reference_models/`): 10 chains x (1,000 warmup + 10,000
  draws thinned by 10), adapt_delta 0.95. It is accepted only with max rank
  R-hat <= 1.01, min bulk ESS >= 2,000 and zero divergences; otherwise those
  cells are judged on gates only.
* **Truth**: a cell is *wrong* iff any house gate fails (rank R-hat <= 1.01,
  bulk and tail ESS >= 400 on every reference parameter, zero retained
  divergences, finite draws, no sampler error) or max |z| > 3 against the
  reference (z = (mean - ref) / sqrt(MCSE^2 + ref MCSE^2); for the funnel
  also the tail mass). Primary confusion: *positive cells* are wrong cells of
  positives-list models; *negative cells* are clean cells of negatives-list
  models. Off-diagonal cells are reported and excluded.

## Thresholds (a priori)

Computed once, after all cells, from the negatives only:
`T_R = 3 x median R` and `T_S = 3 x median S`, the medians pooled over every
chain of every process-valid negatives-list cell (up to 168 chains). A chain
fires when its statistic is strictly above the threshold; a cell fires when
any chain fires. Any other threshold is post hoc and labelled so.

## Decision rule (frozen)

Candidates in order: C_R (R > T_R), C_S (S > T_S), C_RS (either). Ship the
first candidate that meets **both**

* cell level: sensitivity >= 0.75 over positive cells (with at least 6
  positive cells) and specificity >= 13/14 over negative cells; and
* model level (a model fires when >= 2 of its 3 cells fire; a
  positives-list model counts when >= 2 of its cells are wrong, a
  negatives-list model when >= 2 are clean): sensitivity >= 3/4 and
  specificity >= 13/14,

as an observe-only `ChainWarning` variant with the threshold frozen at its
a-priori value (draws bit-identical, kernel revision unchanged, CHANGELOG
entry). Otherwise ship nothing and document the negative.

## Predictions

* **P1** (task): the refined-leaf rate on positives is >= 3x the median over
  negatives (pooled positive-chain median R >= T_R). **P1b**: the same for
  each positive model's median chain.
* **P2** (task): C_R at T_R gives sensitivity >= 3/4 and specificity >= 13/14
  (the decision rule for C_R).
* **P3** (task): WP44's warnings alone fire on <= 2 of the 4 positive models
  (model level, all four in the denominator).
* **P4** (my forecast, written against P2): from WP34 (`refinement_role_v1`
  `da` arm: refined fraction 0.0093 on eight_schools_noncentered, 0.0108 on
  one_comp, 0.0051 on garch11, median near 0.002) and WP46 (seeds_centered
  stuck chains 0.04, other chains 0.0001-0.008), I expect C_R's cell-level
  specificity to fall below 13/14, so the rule fails; and I expect the stuck
  seeds_centered chain to be the highest-R chain of its cell on >= 2 of 3
  seeds.
* **P5** (my forecast): C_S fires on the funnel but not on seeds_centered
  (WP46 saw equal steps across chains there).

Smoke runs on seed 1 (eight_schools_noncentered, funnel) were made to check
the harness output only; they are not evidence and are not committed.

## Amendment A1 (2026-10-25, after the nine funnel / eight_schools_centered / seeds_centered cells, before any other cell)

radon hierarchical_intercept_centered moves from the fourth positive to the
end of the run order, after all 42 negative cells. The frozen CmdStan
reference for radon runs at about 25 minutes per batch of four chains (about
75 minutes for ten), and the first run attempt stopped before radon's first
cell because the reference file did not exist yet (no radon launch marker
was written; no cell was lost). The reference procedure, thresholds, truths
and decision rule are unchanged. The reference run overlaps the negative
cells, which adds contention only; walls are not evidence.
