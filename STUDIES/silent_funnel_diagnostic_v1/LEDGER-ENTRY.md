### WP55-SILENT-FUNNEL-DIAGNOSTIC — the refined-leaf rate does not separate silent-funnel runs from clean runs; nothing ships

2026-10-25 on `wt/silent-funnel`. The preregistration, protocol and harness were frozen at `e4d65d52` before the first evidence cell. Amendment A1 (`980a1577`) moved the three radon cells to the end of the run while radon's reference finished; it was made after 9 cells and before any other. 54 cells ran 02:40–03:45 local, strictly sequential, each launched once, with 0 process errors and kernel `...-v10` unchanged.

**Design.** Shipped defaults (WP44 cell, 4 x 1,000/1,000, no rescue), seeds 731401–731403.
- Positives: house funnel at 1,000/1,000, `eight_schools_centered`, `seeds_centered`, radon `hierarchical_intercept_centered`.
- Negatives: the 14 house models at 3/3 in posteriordb v6.
- References: posteriordb, the exact funnel, and CmdStan 2.39.0 references for seeds_centered and radon, drawn from the identical posteriors written non-centred. Both were accepted: R-hat <= 1.0014, ESS >= 8,398, 0 divergences.
- A cell is wrong iff a house gate fails or max |z| > 3.
- Frozen a-priori thresholds: 3 x the negatives' pooled chain median of the retained refined-leaf rate R (giving T_R = 0.00565) and of the cross-chain end-of-warmup step-collapse factor S (giving T_S = 3.0).

**Outcome.** Not supported.
- C_R: cell sensitivity 8/12 = 0.667, specificity 28/39 = 0.718; model level 3/4 and 10/13. Both fall short of the frozen 0.75 / 13/14.
- C_S: 0.333 / 0.949. C_RS: 0.667 / 0.667.
- WP44 `ChainWarning` alone: 0.167 / 0.974.
- R is high where refinement is busy and the run may still be correct: funnel chains 0.01–0.84 and centred Eight Schools up to 0.48, but also the clean `eight_schools_noncentered` (all 3 cells fire), `one_comp` and `garch11` (up to 0.034). It is low on the positives the study targeted: seeds_centered median 0.0020, radon 0.0012.
- seeds_centered did not reproduce WP46's neck-stuck chain (all chains within 0.17 ref SD). It was wrong only through `sigma` ESS 268–361 and R-hat about 1.01.
- Radon was wrong on 3/3 seeds (max |z| up to 3.33, `beta[1]` ESS 232–389) with almost no refinement. That is global-to-local coupling, not an absorbed funnel.
- **11 of 12 wrong positive cells had zero retained divergences** (all funnel, seeds_centered and radon cells, and 2/3 centred Eight Schools cells), and all 12 failed the R-hat/ESS gates.
- Post hoc (not evidence): cell-max R AUC 0.78; mean level of refined leaves AUC 0.84 (best cut 0.75 / 0.90).
- Predictions:
  - Held: P1 (pooled, by 3 %), P3, my P4 (specificity < 13/14) and my P5.
  - Failed: P1b, P2, and P4's stuck-chain part.

**Decision.** No `ChainWarning` variant. Library untouched.

**Next.**
1. Document that oWALNUTS can sample centred hierarchical funnels with zero divergences; the R-hat/ESS gates, not the divergence count, are the check.
2. A future instrument needs targeted neck-start positives and should test refined-leaf depth or per-chain scale-parameter ESS, not the rate.
