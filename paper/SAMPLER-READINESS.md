# Sampler readiness: retained negative and development results

These studies extend the evidence ledger, not the existing 44-comparison figure
bundle. They do not establish an original algorithm contribution or profitability.

## Warm-start effort tradeoff

The paired E72 study planned 12 monthly paths: three months, two external seed
replicates, and warm budgets K=400 and K=1600. Ten paths completed. Both January
K=1600 paths reached the declared one-hour limit and were not extended. Preserve
90 available scores out of 96 planned slots and 42 available pairs out of 48.

K=1600 reduced estimated log-density and PIT Monte Carlo error in all 42
available pairs. Absolute reference discrepancy improved in 28/42 log-density
and 30/42 PIT pairs. Completed paths cost approximately four times as much.
This supports a precision/cost tradeoff, with a material bounded-runtime failure;
it does not support universal accuracy improvement or real-time readiness.

Source: [E72 results](../STUDIES/warm_budget_factorial_v1/RESULTS.md), including
all-reference and reference-passing analyses and versioned archive verification.

## Specialized same-target transitions

The original augmented elliptical-slice specialist and its interwoven variant
completed all 192 chains across 24 fixed market windows. All 48 four-chain fits
failed at least one declared diagnostic gate. Scale and terminal-volatility
coordinates were flagged on all 24 windows for both methods. Interweaving
improved the mean-level coordinate substantially, but that improvement was
insufficient to establish full-posterior fidelity. Predictive agreement must
not override these flags; Monte Carlo errors can themselves be unreliable under
poor mixing.

Source: [market results](../STUDIES/market_uncertainty_v1/sv_hybrid/MARKET-RESULTS.md).

A subsequent fixed 16-state centered-path block update passed all 254 diagnostic
flags on one literal synthetic development fixture. Its predictive estimates
were compared with the preserved independent reference, with separate Monte
Carlo errors. This is developmental evidence only. The separately frozen
24-window market test completed: 10/24 fits passed all coordinate gates and
14 remained flagged, chiefly scale mixing. All 96 chains completed; maximum
absolute log-density discrepancy on the 22 passing references was 0.018963.
The substantial improvement remains insufficient for full posterior readiness.
See the [complete market results](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-MARKET-RESULTS.md).

Source: [block derivation and development](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-PATH.md)
and [fixed market plan](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-MARKET-PLAN.md).

## Implications for the manuscript

Keep posterior fidelity, prediction, decision value and profitability separate.
Report the runtime failures and diagnostic failures alongside favorable
development results. The current windows are development-exposed. Any final
comparative claim needs a declared evaluation design, fair computational costs,
and adequate references; any economic claim additionally needs feasible
execution and accounting. Established blocking and elliptical-slice techniques
are controls, not a claimed new inference algorithm.
