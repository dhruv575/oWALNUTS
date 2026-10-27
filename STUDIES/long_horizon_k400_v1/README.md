# E63: fixed K400 over 2,000 updates

The fixed resident sampler completed all 8,000 updates across four continuous lanes. At the 44 prespecified checkpoints, all 264 full-return query comparisons and 88 analytic scale-quantile comparisons were available, with all 18 independent references meeting the frozen reliability criteria. This is bounded corroboration on one paired synthetic path with two sampler seeds. It is not a universal no-drift result, a WP96 qualification, or evidence of market profitability.

The largest discrepancies occurred in one control replicate at the final checkpoint. Signed early-to-late errors varied in direction across the two seeds. The experiment does not establish a common direction of accumulating error, but sparse checkpoints and two replicates cannot rule out episodic or systematic approximation errors.

## Frozen design and comparisons

Each lane used a 250-return window, four chains and 400 retained transitions per update, with unchanged E61 target, resident engine and GH64/128 evaluator. One fresh prior-drawn path supplied the control and paired shift variants. Starting at data index 1250, the shift doubled return innovations around the unchanged beta; the first changed observation entered update 1001. Both sampler replicates shared their own seeds between variants. The compact draws from the first 1,000 updates were byte-identical between paired variants for both replicates, as expected; these duplicates are not independent evidence.

Primary queries were current-window mean plus population standard deviation times [-2,-1,0,1,2]. Their causal grid was fixed before observing the next label. Checkpoints were 1, 500, 999, 1000, 1001, 1002, 1010, 1025, 1500, 1750 and 2000. The next observed label was scored separately. At tick 1000 the two conditioning windows were identical but the next label already differed; shared posterior draws were scored separately against each label. Eighteen independent four-chain nutpie fits used 2,000 warmup and 4,000 retained draws each.

| Lane | Maximum absolute grid CDF error | Maximum absolute grid log-density error (nats) | Maximum absolute scale P50 error | Maximum absolute scale P95 error |
|---|---:|---:|---:|---:|
| Control, seed 0 | 0.002531 | 0.027083 | 1.105% | 4.954% |
| Control, seed 1 | 0.003574 | 0.059840 | 2.278% | 2.309% |
| Shift, seed 0 | 0.003403 | 0.027061 | 1.294% | 4.954% |
| Shift, seed 1 | 0.001603 | 0.025186 | 1.203% | 2.309% |

These are descriptive maxima, not qualification thresholds. The largest grid CDF error was -0.003574 at control seed 1, tick 2000, query index 1; candidate/reference MCSEs were 0.001100 and 0.000335. The largest grid log-density error was -0.059840 nats at the same lane/tick, query index 0; candidate/reference delta MCSEs were 0.020464 and 0.006080. Some discrepancies exceed two combined estimated standard errors. No simultaneous-error guarantee or automatic two-SE pass is claimed; short-chain MCSE can underestimate uncertainty.

The largest scale P50 error was -2.278% at control seed 1, tick 2000, with own/reference relative MCSEs 0.783% and 0.216%. The largest P95 error was +4.954% at seed 0, tick 500, with MCSEs 1.514% and 0.341%; that shared pre-shift result appears in both variants. The old WP96 2%/5% rule is not applied to this new schedule.

For the prespecified early [1,500,999] and late [1500,1750,2000] averages, signed late-minus-early grid CDF contrasts ranged from -0.001457 to +0.000922; log-density contrasts ranged from -0.015109 to +0.016709 nats. Paired shift-minus-control drift contrasts ranged from -0.001515 to +0.001607 for CDF and -0.011513 to +0.028282 nats for log-density. The complete per-query/per-seed tables retain the signs and shared-reference uncertainty. They do not treat dependent ticks as independent observations or supply a population confidence interval.

All reference diagnostics passed: maximum rank Rhat 1.000931, minimum bulk ESS 5853.4, minimum tail ESS 6349.6, zero retained divergences, maximum CDF MCSE 0.000417 and maximum delta log-density MCSE 0.007140. The realized-label diagnostic's largest CDF discrepancy was 0.004694; its largest log-density discrepancy was 0.053229 nats. These are separate from the primary grid.

## Health and cost

All 12,800,000 warm-update retained transitions had zero divergences, maximum-depth stops, refinement exhaustion, invalid-evaluation stops, recoverable target failures and zero-density evaluations. Initial retained samples comprised another 3,200 transitions with the same zero adverse-event counts. Initialization warmup was different: among 16,000 warmup transitions there were 48 divergences, 1,664 maximum-depth stops, 48 refinement exhaustions and 128 recoverable zero-density evaluations. Sixteen initial guard checks produced zero restarts; no initial chain warnings were recorded. Paired pre-shift work is counted as executed work, not independent replication.

The complete campaign took 950.37 seconds, with sampled peak RSS 2,346,704,896 bytes and 196,637,883 output bytes. Four candidate lanes ran concurrently on disjoint four-core sets; references ran serially after all lanes drained. Median native update wall time was 0.2468 seconds (P95 0.2674); median time through the immutable record was 0.2542 seconds (P95 0.2760). The 44 six-query plus scale summaries had median arithmetic time 0.1190 seconds (P95 0.3429). Each lane's engine initialization took 2.94 to 3.06 seconds, including a 2.32 to 2.43 second initial fit; lane elapsed times were 516.45 to 524.75 seconds. Whole-campaign time includes subprocess imports, source/runtime checks, compilation, persistence, references and analysis. These are shared-host measurements. Scoring occurred only at the fixed checkpoints, and no full-return quantile roots were computed; these costs are not an every-update full-quote latency benchmark.

## Preserved integrity failure and separate correction

The original supervisor correctly retained `evidence_complete=false`: the post-run integrity checker generated 144 path-classification exceptions because it tested whether any ancestor was named `lanes`. The host path `/home/ubuntu/lanes/...` made non-lane JSON look like campaign lane evidence. No reported error was a hash mismatch.

The original checker, 144-error audit, summary and supervisor output remain unchanged. A separately authorized local integrity-only correction uses ancestry relative to the campaign's own `lanes` directory and one explicit remote-to-local prefix mapping for captured library paths. A fixture checks the ancestor collision, correct relocation, a tampered artifact and wrong-prefix rejection. The corrected audit verified 8,234 referenced files with zero errors; an independent reviewer reproduced that result. No sampler, generator, forecast, score or frozen statistical analysis was rerun. All 8,638 archived file hashes were independently verified. Recorded host postchecks covered 18,775 source/runtime bindings with zero mismatches. AWS was stopped after the archive was safely downloaded.

## Evidence and limits

- [Frozen comparisons and accounting](execution-20261027/evidence/long-horizon-k400-20261027/campaign01/work/SUMMARY.json), with original integrity status preserved.
- [Descriptive health/cost rendering](DESCRIPTIVE-REPORT.json) and [rendering source](render_report.py).
- [Separate corrected integrity audit](integrity-correction/CORRECTED-INTEGRITY.json) and [correction source](integrity-correction/integrity_corrected.py).
- [Archive verification](execution-20261027/VERIFICATION.json). Full archive: `C:/dev/owalnuts/target/long-horizon-k400-20261027-evidence.tar.gz`, 107,029,733 bytes, SHA256 `6d952b9fecc77758714c19c174b13c0cb7e2306c25013d94dbc6c64fb4af7705`. The complete extracted packet remains in this study worktree; raw artifacts were not discarded.
- Authorized manifest SHA256 `3eb14d1a5ab95add9f8e83ca4b990efc9baf45fbb8ae6c9b0a7701c41a4411c5`; the scientific source bundle and all inputs were sealed before production outcomes.

This study addresses approximation fidelity through 2,000 updates on one matched synthetic control and one fixed shift. It does not establish calibration across broad prior draws, real-market forecasting value, robust behavior under other shifts, or a profitable AMM. E61 supplies separate short-horizon prior-predictive evidence; E62 supplies a separate real-period comparison. No default or deployment decision follows automatically.
