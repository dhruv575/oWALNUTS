# WP81 diagonal metric shrinkage — results

## Part 1: installed inverse mass / posterior variance

Per coordinate: median over chains, then over 3 seeds; band [0.5, 2.0]. 'own' = the cell's retained draws; 'ref' = posteriordb reference (unconstrained).

| model | dim | oWALNUTS own min..max (outside) | oWALNUTS ref min..max | nutpie own min..max (outside) | nutpie ref min..max | step o / n | lowanchor own max | coordcap own max |
|---|---:|---|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 10 | 0.95..1.07 (0) | — | 0.61..1.03 (0) | — | 0.4589 / 0.6302 | 1.07 | 1.07 |
| eight_schools-eight_schools_centered | 10 | 0.76..1.07 (0) | 0.56..1.09 | 0.25..0.52 (8) | 0.12..0.61 | 0.1845 / 0.4276 | 1.07 | 1.07 |
| diamonds-diamonds | 26 | 0.93..4.32 (1) | 0.91..4.27 | 0.01..1.00 (7) | 0.01..1.00 | 0.0033 / 0.0621 | 1.07 | 1.06 |
| earnings-logearn_interaction | 5 | 1.00..1.06 (0) | 0.99..1.06 | 0.03..1.03 (4) | 0.03..0.98 | 0.0164 / 0.1411 | 1.17 | 1.02 |
| mesquite-logmesquite_logvash | 7 | 0.97..1.04 (0) | 0.96..1.03 | 0.10..0.88 (5) | 0.11..0.90 | 0.0759 / 0.2874 | 1.04 | 1.04 |
| kidiq-kidscore_momhsiq | 4 | 0.95..1.06 (0) | 0.96..1.06 | 0.14..1.01 (3) | 0.14..1.00 | 0.1008 / 0.3799 | 1.03 | 1.02 |
| sblrc-blr | 6 | 1.00..12.21 (5) | 0.94..11.30 | 0.45..0.98 (3) | 0.45..0.98 | 0.1061 / 0.6601 | 1.03 | 1.10 |
| nes2000-nes | 10 | 0.91..1.03 (0) | 0.89..1.05 | 0.10..0.99 (8) | 0.10..1.01 | 0.0828 / 0.2846 | 1.03 | 1.07 |
| arK-arK | 7 | 0.95..1.04 (0) | 0.95..1.07 | 0.24..1.01 (5) | 0.23..1.02 | 0.1203 / 0.3378 | 1.08 | 1.03 |
| arma-arma11 | 4 | 1.00..1.04 (0) | 0.98..1.01 | 0.91..1.01 (0) | 0.93..1.00 | 0.7240 / 1.0253 | 0.99 | 1.02 |
| garch-garch11 | 4 | 0.94..1.08 (0) | 0.94..1.13 | 0.45..0.97 (1) | 0.47..0.95 | 0.3071 / 0.5947 | 1.08 | 1.08 |
| gp_pois_regr-gp_pois_regr | 13 | 0.89..1.05 (0) | — | 0.05..1.04 (11) | — | 0.0280 / 0.1453 | 1.05 | 1.05 |
| hmm_example-hmm_example | 4 | 1.00..1.06 (0) | 0.98..0.99 | 0.43..0.98 (2) | 0.42..0.98 | 0.2984 / 0.6916 | 1.06 | 1.05 |
| bball_drive_event_0-hmm_drive_0 | 6 | 0.21..1.04 (1) | 0.94..1.13 | 0.68..0.99 (0) | 0.76..1.02 | 0.6060 / 0.7930 | 1.10 | 1.06 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | 0.95..1.04 (0) | 0.75..1.03 | 0.45..0.97 (2) | 0.32..0.93 | 0.3825 / 0.6445 | 1.04 | 1.04 |
| hudson_lynx_hare-lotka_volterra | 8 | 0.94..1.01 (0) | 1.00..1.06 | 0.17..0.94 (5) | 0.15..0.91 | 0.1106 / 0.3426 | 1.01 | 1.01 |
| mcycle_gp-accel_gp | 66 | 0.67..1.13 (0) | 0.69..1.13 | 0.02..0.39 (66) | 0.02..0.39 | 0.0082 / 0.0474 | 1.13 | 1.13 |

D1 (coordinator: step-gap models have oWALNUTS coordinates outside the band, nutpie none): False — blr 5/3 False, hmm_drive_0 1/0 True, eight_schools_centered 0/8 False, diamonds 1/7 False
D1b (this study): False — blr 5 True, diamonds 1 True, hmm_drive_0 1 False, eight_schools_centered 0 True

## Part 2: candidates against the frozen rule

Default: 40/51 cells pass; funnel mean 0.0502 ± 0.0043 (0.55 s.e.)

| criterion | owalnuts-lowanchor | owalnuts-coordcap |
|---|---|---|
| R1_gates_not_lower | 41 vs default 40 — held | 41 vs default 40 — held |
| R2_headline_geomean_ge_1.10 | 1.025 — FAILED | 1.017 — FAILED |
| R3_per_model_median_ge_1.05 | 1.000 — FAILED | 1.000 — FAILED |
| R4_lomo_min_ge_1.00 | 0.994 — FAILED | 0.982 — FAILED |
| R5_no_new_divergences | none — held | none — held |
| R6_funnel_mean_within_1se | mean 0.0502 ± 0.0043 (0.56 s.e.) — held | mean 0.0499 ± 0.0043 (0.50 s.e.) — held |
| R7_fingerprint_flags_off | True — held | True — held |
| meets rule | False | False |
| headline interval | [0.997, 1.378] | [0.990, 1.422] |
| cells identical to default | 27/51 | 27/51 |

| model | owalnuts-lowanchor | owalnuts-coordcap |
|---|---:|---:|
| eight_schools-eight_schools_noncentered | 1.000 | 1.000 |
| eight_schools-eight_schools_centered | 1.000 | 1.000 |
| diamonds-diamonds | 1.160 | 0.916 |
| earnings-logearn_interaction | 0.725 | 0.879 |
| mesquite-logmesquite_logvash | 1.000 | 1.000 |
| kidiq-kidscore_momhsiq | 1.025 | 1.018 |
| sblrc-blr | 1.671 | 1.794 |
| nes2000-nes | 1.069 | 1.048 |
| arK-arK | 1.009 | 0.928 |
| arma-arma11 | 0.977 | 0.960 |
| garch-garch11 | 1.000 | 1.000 |
| gp_pois_regr-gp_pois_regr | 1.000 | 1.000 |
| hmm_example-hmm_example | 1.000 | 0.970 |
| bball_drive_event_0-hmm_drive_0 | 1.000 | 1.000 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1.000 | 1.000 |
| hudson_lynx_hare-lotka_volterra | 1.000 | 1.000 |
| mcycle_gp-accel_gp | 1.000 | 1.000 |

## Predictions

| prediction | held |
|---|---|
| D1 | False |
| D1b | False |
| C1_both_fail_R2 | True |
| C2_both_fail_R3 | True |
| C3_sblrc_ratio_ge_1.5_both | True |
| C4_identical_cells_ge | {'owalnuts-lowanchor': {'value': 27, 'held': True}, 'owalnuts-coordcap': {'value': 27, 'held': True}} |
| C5_R1_R5_R6_hold_both | True |
