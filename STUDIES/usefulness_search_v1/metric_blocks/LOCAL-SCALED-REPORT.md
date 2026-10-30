# Fresh local scale-corrected policy results

Frozen six-target/six-arm validation,16 fresh seeds per target. Local WSL only; no cloud observations pooled.
Continuation gate: **FAIL**. This is a research continuation criterion, not goal completion or application evidence.

| Target | Passes scaled/hybrid/v4/Fisher/dense/auto | ESS/call vs auto | ESS/call vs Fisher | ESS/operational-second vs auto |
|---|---|---|---|---|
| arK-arK | 16/16/16/16/16/16 | 1.249 [1.217, 1.285] | 0.996 [0.996, 0.997] | 0.708 [0.681, 0.738] |
| arma-arma11 | 16/16/16/15/16/16 | 1.179 [1.121, 1.241] | unqualified | 0.823 [0.778, 0.871] |
| eight_schools-eight_schools_centered | 0/0/0/0/0/0 | unqualified | unqualified | unqualified |
| garch-garch11 | 16/16/16/16/16/16 | 1.260 [1.117, 1.435] | 0.801 [0.696, 0.908] | 0.751 [0.701, 0.808] |
| gp_pois_regr-gp_pois_regr | 16/16/16/8/9/16 | 0.999 [0.999, 0.999] | unqualified | 0.810 [0.793, 0.828] |
| sblrc-blr | 16/16/16/16/16/16 | 14.300 [13.666, 15.120] | 0.992 [0.977, 1.002] | 3.721 [3.454, 4.015] |

Intervals are95% paired bootstrap intervals (10000 replicates, frozen seed929599999). They are exploratory per-target intervals, not simultaneous inference. A ratio is reported only if all16 candidate/control pairs pass every accuracy gate. Failed controls receive no infinite-ratio credit.

Accuracy losses vs auto/v4/old hybrid: [].
Prespecified non-Gaussian signals: ["garch-garch11"].
Fully qualified targets below the .90 Fisher efficiency floor: ["garch-garch11"].

## Repair and old-policy contrasts

| Target | Candidate branch counts | ESS/call vs old hybrid | ESS/operational-second vs old hybrid |
|---|---|---|---|
| arK-arK | {"fisher": 16} | 1.000 [1.000, 1.000] | 1.008 [0.980, 1.034] |
| arma-arma11 | {"fisher": 13, "auto": 3} | 1.000 [1.000, 1.000] | 0.997 [0.970, 1.025] |
| eight_schools-eight_schools_centered | {"auto": 16} | unqualified | unqualified |
| garch-garch11 | {"fisher": 9, "auto": 7} | 1.000 [1.000, 1.000] | 1.035 [1.003, 1.067] |
| gp_pois_regr-gp_pois_regr | {"auto": 16} | 1.000 [1.000, 1.000] | 1.015 [1.000, 1.030] |
| sblrc-blr | {"fisher": 14, "scaled_block": 2} | 1.145 [1.000, 1.476] | 1.160 [1.016, 1.443] |

## Evidence and limits

All eight chunks verified: 672 jobs and 576 matched stages. Algorithm/source and target hashes agree across chunks. Each local evidence archive was read back and its members verified. These are local copies, not S3/off-device backups.

Operational time includes supervised worker startup, model loading, policy fitting, sampler invocation and output, plus the shared pilot charged to every arm. Common reference diagnostics and controller IO are excluded. The ESS/time ratio uses measured minimum bulkESS divided by this time; it is distinct from raw elapsed-time ratios. Startup and the80-digit Fisher solver can dominate cheap targets. This is not a comparison against optimized or persistent-process implementations.

The unconditional Fisher arm is the published dense estimator in our fixed-stage schedule. It does not reproduce the published native Fisher-HMC adaptation schedule. Native full-schedule controls remain a required comparison before practical superiority claims.

The six models are an exposed development family; new seeds protect against reuse of fitted trajectories, not model-selection bias. Centered eight-schools remains in the denominator and failure record. The regression also has a cheap collapsed control. Neither a repaired regression fallback nor this gate demonstrates application value, profitability or uniqueness. See RELATED-WORK-CHECK.md and SCORE-GATE-METHODS.md.
