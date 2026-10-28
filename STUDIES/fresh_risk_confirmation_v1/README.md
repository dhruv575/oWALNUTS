# E66: fresh historical tail-risk confirmation

The fixed SV forecast improves mean tail pinball loss against rolling Student-t in all six comparisons. Against the stronger EWMA Student-t primary comparator, evidence is mixed: December and January favor SV on both sides, February favors SV for long exposure, and February short exposure remains unresolved with a slightly negative point estimate. January short's primary lower interval endpoint is only 0.250 millionths of log-return loss. These are individual descriptive intervals, not a familywise confirmation or qualification result.

All 4,320 origins, 12,960 arm forecasts, 24 reference forecasts and 57 execution jobs completed. Only **22 of 24 independent references pass their original diagnostic gates**; numerical tail availability does not repair those failures.

## Fixed comparison

December 2025, January 2026 and February 2026 were selected by calendar before acquisition. The bounded exposure audit supports a historical holdout by project access, not a prospective live holdout. BTC-PERPETUAL half-hour bars produce 1,488/1,488/1,344 consecutive forecast origins. SV K400 and rolling t5 use the same latest 250 returns; EWMA retains its declared longer causal history and resets separately for each month. No model, optimizer, quadrature or threshold was tuned after acquisition. See [frozen plan](PLAN-DRAFT.md).

Long loss is minus log return and short loss is log return. The 95% pinball score penalizes an underestimated risk limit 19 times as much as an equally overestimated limit. Positive reported advantage means baseline loss minus SV loss. Relative reductions divide by the respective baseline mean loss; they are not returns or profit margins.

| Month | Comparator | Exposure | Mean advantage x 1e6 | 95% interval, 48-origin blocks x 1e6 | Relative mean loss reduction |
|---|---|---|---:|---:|---:|
| 2025-12 | ewma_t5 | long | 15.492 | [2.324, 27.784] | 3.69% |
| 2025-12 | ewma_t5 | short | 21.979 | [8.705, 36.152] | 6.04% |
| 2025-12 | rolling_t5 | long | 24.360 | [5.871, 44.166] | 5.69% |
| 2025-12 | rolling_t5 | short | 36.478 | [10.863, 66.125] | 9.64% |
| 2026-01 | ewma_t5 | long | 12.018 | [2.543, 22.152] | 3.45% |
| 2026-01 | ewma_t5 | short | 10.483 | [0.250, 21.315] | 3.27% |
| 2026-01 | rolling_t5 | long | 38.419 | [14.406, 64.618] | 10.24% |
| 2026-01 | rolling_t5 | short | 28.827 | [8.224, 51.706] | 8.52% |
| 2026-02 | ewma_t5 | long | 23.767 | [13.519, 34.783] | 3.78% |
| 2026-02 | ewma_t5 | short | -0.510 | [-15.485, 15.420] | -0.10% |
| 2026-02 | rolling_t5 | long | 42.517 | [6.329, 89.085] | 6.56% |
| 2026-02 | rolling_t5 | short | 47.222 | [15.295, 86.702] | 8.82% |

All frozen 24/48/96-origin interval variants are retained in the three evidence summaries; the qualitative signs agree across these sensitivities. The 48-origin intervals are primary. Adjacent months, overlapping 250-return estimation windows and market dependence preclude treating months or origins as independent replications. These block lengths do not guarantee protection against longer dependence. No pooled inferential interval, selected-comparison headline or multiplicity-adjusted claim is made.

## Coverage and conservatism

| Month | Arm | Long exceedance | Short exceedance | Mean long limit | Mean short limit |
|---|---|---:|---:|---:|---:|
| 2025-12 | candidate | 4.70% | 3.56% | 0.004870 | 0.004956 |
| 2025-12 | rolling_t5 | 6.59% | 6.05% | 0.004241 | 0.004365 |
| 2025-12 | ewma_t5 | 5.71% | 4.23% | 0.004650 | 0.004975 |
| 2026-01 | candidate | 5.24% | 3.36% | 0.004295 | 0.004332 |
| 2026-01 | rolling_t5 | 7.39% | 5.85% | 0.003646 | 0.003679 |
| 2026-01 | ewma_t5 | 6.32% | 4.70% | 0.004092 | 0.004079 |
| 2026-02 | candidate | 5.28% | 3.50% | 0.007595 | 0.007628 |
| 2026-02 | rolling_t5 | 6.55% | 5.28% | 0.007070 | 0.007021 |
| 2026-02 | ewma_t5 | 5.80% | 4.76% | 0.007503 | 0.006964 |

Limits are in log-return units. SV short exceedance rates of 3.36% to 3.56% are below the nominal 5%; this is conservative behavior, not proof of calibration. Coverage alone rewards excessive limits, which is why the fixed proper pinball score remains the comparison endpoint.

## Numerical and reference limitations

All 4,344 candidate/reference tail evaluations met the unchanged numerical gates. Maximum cross-CDF and own-root residual were 1.522e-11; maximum width-normalized GH64/128 endpoint difference was 1.627e-15. Agreement is a numerical diagnostic, not a certified error bound for the posterior model.

December reference tick 1 failed its original log-density MCSE gate (0.017919 versus the 0.01 limit). Tick 851 failed that gate (0.021760) and had one retained divergence. Both are preserved; neither was replaced nor admitted by relaxing a criterion. All 24 references have both tail precision outputs, but only 22 pass the original reference diagnostics. Candidate/baseline historical scores remain available independently of these checks.

Across the 24 fixed spots, candidate-minus-reference endpoint differences range from -0.000116014 to 0.000080017 for P5 and from -0.000081221 to 0.000111150 for P95. Maximum candidate-own quantile MCSE is 0.00011955; maximum reference-own MCSE is 0.00003349. These extrema include the two diagnostically rejected references and cannot certify whole-path approximation. Chain-aware CDF MCSE divided by predictive density is diagnostic, not an adaptive stopping rule.

## Native health and cost

Every month has 12 initial warmup divergences and 32 warmup zero-density/recoverable target failures among 4,000 discarded transitions. Initial warmup maximum-depth stops are 501/777/480 in December/January/February. Each retained initial fit has 800 transitions with zero such divergences, zero-density events or maximum-depth stops. All four initialization guards per month are recorded, with no restarts. Discarded warmup is kept separate from retained evidence.

The 2,380,800/2,380,800/2,150,400 rolling transitions have zero divergences, nonfinite energy errors, zero-density evaluations or maximum-depth stops. Native stop codes 0, 1 and 4 mean outer U-turn, recursive U-turn and accepted reverse-coarser stop respectively; code 1 is not a maximum-depth stop (that is code 2).

Whole campaign wall time was 1,932.116 seconds, including native inference, baselines, four parallel reference queues and tail postprocessing; sampled peak RSS was 8,195,444,736 bytes. Concurrent native job walls were approximately 748.2/1,514.5/672.7 seconds, so January's cost must not be hidden in a universal throughput average. Baselines ran in subsequent serial phases. Median cached SV quantile postprocessing was 0.541/0.541/0.568 seconds per origin; rolling and EWMA analytic quantiles were approximately 0.00032 and 0.00014 seconds. These are phase-specific shared-host measurements, not measured combined live-update latency, executable quote latency or trading profitability.

## Acquisition exception and provenance

The original no-retry acquisition failed with a transport reset after 55 complete days and 56 attempted requests out of 96. No accepted panel or outcomes were inspected. Before a second request sequence, parent and independent reviewer recorded a one-time infrastructure amendment permitting one full unchanged reacquisition, preserving the failed attempt, source, dates and limits. The second attempt completed all 96 days/4,608 bars. The 55 overlapping validated bar series were identical despite different raw envelopes. There was no stitching, outcome-based source choice or further retry. This is an explicit deviation from the original no-retry rule, not a claim of uninterrupted original compliance.

The postsealed audit reproduces every paired mean and relative loss reduction from complete ledgers without rerunning inference, scoring or bootstrap. Full raw evidence stays outside Git:

- Archive: `C:/dev/owalnuts/target/risk-confirmation-evidence-20261027.tar.gz` (529,320,111 bytes).
- Archive SHA256: `b67a9b060858bcd14f8b5060cbec2452a2d8c002f3eb986774dbc73cbddf1ba4`.
- Verified expansion: `C:/dev/owalnuts/target/risk-confirmation-verified-20261027`.
- All 49,815 archived file hashes were independently recomputed with no mismatch. Bounded summaries, full hash inventory, acquisition provenance and verification records are retained in [evidence](evidence/).

This studies log-return risk limits. It does not measure fills, adverse selection, funding, liquidation, transaction costs or AMM P&L. Conditional Student-t log returns have infinite E[exp(R)]; finite expected-price or unbounded-short dollar-loss claims are unavailable. See the [decision contract](../amm_decision_contract_v1/README.md) for bounded decision targets.
