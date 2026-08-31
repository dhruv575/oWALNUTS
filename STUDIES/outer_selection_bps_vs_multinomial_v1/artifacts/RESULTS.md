# Results: outer-selection-bps-vs-multinomial-v1

Primary ratio (BPS / multinomial, bulk ESS per retained target call, geomean over six functionals): **1.7453**
Verdict: **bps_advantage_confirmed_default_stands**

## Per-functional ratios (BPS / multinomial)

| functional | bulk ESS/call | tail ESS/call | squared bulk ESS/call | lag-1 ACF bps | lag-1 ACF multinomial |
|---|---:|---:|---:|---:|---:|
| mu | 1.7343 | 1.6946 | 1.6502 | +0.2209 | +0.5200 |
| tau | 1.7560 | 1.4387 | 1.7560 | +0.0797 | +0.3549 |
| mean_theta | 1.6687 | 1.4946 | 1.6884 | +0.1284 | +0.4330 |
| sd_theta | 1.7989 | 1.5780 | 1.7989 | +0.0291 | +0.3115 |
| theta_1 | 1.7732 | 1.6156 | 1.8054 | +0.0946 | +0.3971 |
| theta_8 | 1.7432 | 1.4628 | 1.6398 | +0.0861 | +0.3770 |

## Safety gates

- zero_divergences_and_invalid_evaluations: True
- depth_cap_delta_le_0_005: True
- depth_cap_delta: 0.0
- min_tail_ess_per_call_ratio_ge_0_95: True
- min_tail_ess_per_call_ratio: 1.4386728516276899
- min_squared_bulk_ess_per_call_ratio_ge_0_95: True
- min_squared_bulk_ess_per_call_ratio: 1.639782202922946
- all_cells_passed_health_gates: True

## Per-cell health

| arm | seed | max R-hat | min bulk ESS | min tail ESS | depth-cap rate | div | invalid | retained calls | wall s | passed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| bps | 82001 | 1.00303 | 2328.4 | 1628.0 | 0.00000 | 0 | 0 | 61871 | 0.099 | True |
| bps | 82002 | 1.00160 | 2100.0 | 1552.4 | 0.00000 | 0 | 0 | 49253 | 0.085 | True |
| bps | 82003 | 1.00226 | 2078.7 | 1191.5 | 0.00000 | 0 | 0 | 63986 | 0.107 | True |
| multinomial | 82001 | 1.00344 | 1139.3 | 670.4 | 0.00000 | 0 | 0 | 51945 | 0.087 | True |
| multinomial | 82002 | 1.00629 | 1143.4 | 1246.5 | 0.00000 | 0 | 0 | 51445 | 0.083 | True |
| multinomial | 82003 | 1.00547 | 1243.5 | 991.3 | 0.00000 | 0 | 0 | 62794 | 0.097 | True |

## Mechanism

| arm | self-retention | E-BFMI range | mean depth | mean leaves built | mean calls/transition |
|---|---:|---|---:|---:|---:|
| bps | 0.00392 | 0.856–1.014 | 3.765 | 13.46 | 14.59 |
| multinomial | 0.10736 | 0.836–1.052 | 3.666 | 12.62 | 13.85 |

## Per-cell, per-functional bulk ESS

| arm | seed | mu | tau | mean_theta | sd_theta | theta_1 | theta_8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| bps | 82001 | 2328.4 | 2334.6 | 2947.2 | 2463.8 | 3266.6 | 3568.6 |
| bps | 82002 | 2380.4 | 2100.0 | 2684.4 | 2385.1 | 2927.7 | 3188.4 |
| bps | 82003 | 2575.6 | 2078.7 | 3031.2 | 2419.2 | 3092.6 | 3219.5 |
| multinomial | 82001 | 1370.5 | 1139.3 | 1765.9 | 1224.8 | 1719.0 | 2081.0 |
| multinomial | 82002 | 1343.3 | 1143.4 | 1667.0 | 1237.6 | 1457.7 | 1810.9 |
| multinomial | 82003 | 1279.2 | 1243.5 | 1508.8 | 1386.4 | 1821.9 | 1579.2 |
