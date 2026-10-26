### WP85-METRIC-AUTOSELECT-CONFIRMATION-V1: Hessian-fit dense auto-selection does not qualify as the default; every safety and efficiency rule held (105 = 105 gates, 2.01x, 122/122 bit-identical) but the branch choice was seed-dependent on 3 of 22 models (allowed 2); flag stays research opt-in

- **When and where.** 2026-10-26 on `wt/metric-autoselect-confirmation`,
  preregistered at `d708449b`; library `fc41994a` makes the flag the plain
  diagonal run above `DenseMass::MAX_DIMENSION` (256; radon, grsm_irt).
  Lane 3 (pinned, co-tenanted), 22 v7 posteriors x 6 fresh seeds
  (868501–868506) x {diagonal, auto} at 4 x 1,000/1,000 plus the funnel at
  30 seeds; no reruns; one pipeline-only amendment before evidence
  (`e188ddf6`, funnel s.e. guard).
- **Rules.** R1 passes 105 vs 105, R2 headline 2.01x, R3 no model below
  0.9x, R4 no new divergences, R5 max |z| 3.54, R6 122/122 diagonal-branch
  and capped cells bit-identical to the diagonal arm, R8 funnel P5
  0.0492 ± 0.0017, R9 0 vs 0 trapped lotka_volterra cells, D integrity:
  all held. **R7 failed**: the same branch on all six seeds for 19 of 22
  models against the required 20 (kidiq dense 4/6, garch11 2/6,
  lotka_volterra 4/6; both branches pass every gate on each).
- **Reported.** Wall per gradient auto/diagonal geomean 1.036 (observer
  1.026 on diagonal-branch models); dense-branch warmup gradients 0.49x
  the diagonal's (40 cells); branch as predicted 118/132 (kilpisjarvi
  diagonal 6/6 against a dense prediction; kidiq dense 4/6 against WP79's
  0/3).
- **Decision.** No flip. `with_dense_auto_select` stays research opt-in.
  The `proposed_flip` text in `protocol.json` records what would have
  changed. Next: a decision statistic that is stable across seeds near the
  linearity and gain thresholds, then a second confirmation.
