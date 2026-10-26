# WP85 `metric_autoselect_confirmation_v1`: preregistration

This document was frozen before the first evidence cell. Where it and
`protocol.json` differ, `protocol.json` is authoritative.

## Question

Does WP79's auto-selection rule qualify as the sampler default? The rule is
used unchanged: `DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5)`. There is
no re-tuning. earnings and kidiq are accepted as diagonal.

## Scope change, disclosed before any cell

Two of the hard posteriors are larger than `DenseMass::MAX_DIMENSION` (256):

- radon, with dimension 391;
- grsm_latent_reg_irt, with dimension 408.

On these, WP79's code returns a configuration error.

The scope commit changes this. Above 256 dimensions the flag is ineligible:
the run is the unflagged diagonal run, and no decision is recorded
(`diag-cap`). This path is covered by a new bit-identity test.

## Design

- **Posteriordb arm:** all 22 v7 posteriors (17 house and 5 hard) x 6 fresh
  seeds (868501-868506) x {diag, auto}.
  - Runs are 4 chains x 1,000 warmup / 1,000 draws, with replicated dispatch.
  - The v7 gates apply. The four posteriors without reference draws use the
    v7 gates-only parameter set.
- **Funnel arm:** 30 seeds (868401-868430) x {diag, auto}, at 2,000 warmup /
  20,000 draws.
- **Machine:** lane 3, `taskset -c 8-11`.
- **No reruns.**

## Rules for the flip

| Rule | Condition |
|---|---|
| R1 | auto passes >= diag passes, over all 132 cells |
| R2 | WP72 (c) headline ratio auto/diag >= 1.5 |
| R3 | no model below 0.9x |
| R4 | 0 new divergences |
| R5 | max \|z\| on passing reference cells <= 4 |
| R6 | every diagonal / diag-cap cell is bit-identical to the diag arm |
| R7 | the branch is identical across seeds on >= 20 of 22 models |
| R8 | funnel P5 is within 1 s.e. of 0.0478 |
| R9 | lotka_volterra trapped cells (R-hat > 1.1): auto <= diag |
| D | integrity checks pass |

R8 is the diagonal's own result by construction.

## Reported, not ruled on

- wall per gradient, auto/diag;
- the dense branch's warmup overhead.

## Predictions

- The branch matches `predicted_branch` on at least 120 of 132 runs.
  - kilpisjarvi is predicted dense.
  - GLMM_Poisson and seeds_centered are predicted diag.
  - radon and grsm_irt are predicted diag-cap.
- Every rule holds. R2 is predicted at about 2.2.
- R8 has about a 0.68 chance of holding.
- Predicted verdict: the flip qualifies, conditional on R8.

## The proposed flip

If every rule holds, the change is the `proposed_flip` entry in
`protocol.json`. It has four parts:

- **Default:** `DEFAULT_DENSE_AUTO_SELECT` goes into the diagonal default
  adaptation (two or more chains).
- **Research gate:** the research gate is lifted.
- **Algorithm revision and fingerprints:** no change to `ALGORITHM_REVISION`
  or to the fingerprints, following WP68's precedent.
- **Python:** a new `auto_metric` keyword. No signature changes.
