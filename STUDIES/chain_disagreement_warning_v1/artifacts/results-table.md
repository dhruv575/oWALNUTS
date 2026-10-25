# WP44 chain-disagreement warning: results

Detectors (frozen WP33 thresholds): D1 end-of-warmup step < 0.1 x median; D2 last-slow-window median log density > 3 x median IQR below the chains' median; D3 the same on the retained draws; D4 ChainDisagreement (leave-one-chain-out R-hat on the unconstrained draws). Truths: T_gate = any house gate fails or a pooled reference-parameter mean is > 3 reference SD off; T_wrong = some chain's mean of some reference parameter is > 3 reference SD off; T_rhat = R-hat gate fails or T_wrong.

## Every cell

| model | seed | block | status | gates | max R-hat | min bulk / tail ESS | div | max chain dmean/refSD | wrong chains | T_gate | T_wrong | D1 | D2 | D3 | D4 | Rust = Python |
|---|---|---|---|---|---:|---|---:|---|---|---|---|---|---|---|---|---|
| eight_schools-eight_schools_noncentered | 97461 | screen | ok | pass | 1.001 | 2199 / 1988 | 0 | 0.05, 0.02, 0.06, 0.06 | - | - | - | - | - | - | - | yes |
| eight_schools-eight_schools_noncentered | 97462 | screen | ok | pass | 1.003 | 1872 / 1267 | 0 | 0.08, 0.07, 0.06, 0.08 | - | - | - | - | - | - | - | yes |
| eight_schools-eight_schools_noncentered | 97463 | screen | ok | pass | 1.003 | 1491 / 981 | 0 | 0.09, 0.05, 0.06, 0.08 | - | - | - | - | - | - | - | yes |
| eight_schools-eight_schools_centered | 97461 | screen | ok | **fail** | 1.013 | 101 / 140 | 0 | 0.12, 0.17, 0.14, 0.28 | - | Y | - | - | - | - | [2] | yes |
| eight_schools-eight_schools_centered | 97462 | screen | ok | **fail** | 1.076 | 52 / 94 | 0 | 0.14, 0.16, 0.09, 0.43 | - | Y | - | - | - | - | - | yes |
| eight_schools-eight_schools_centered | 97463 | screen | ok | **fail** | 1.099 | 33 / 84 | 5 | 0.07, 0.22, 0.42, 0.28 | - | Y | - | - | - | - | - | yes |
| diamonds-diamonds | 97461 | screen | ok | pass | 1.003 | 1212 / 1843 | 0 | 0.09, 0.07, 0.07, 0.08 | - | - | - | - | - | - | - | yes |
| diamonds-diamonds | 97462 | screen | ok | pass | 1.004 | 1129 / 1753 | 0 | 0.07, 0.07, 0.09, 0.06 | - | - | - | - | - | - | - | yes |
| diamonds-diamonds | 97463 | screen | ok | pass | 1.004 | 1219 / 1623 | 0 | 0.13, 0.08, 0.08, 0.09 | - | - | - | - | - | - | - | yes |
| earnings-logearn_interaction | 97461 | screen | ok | pass | 1.010 | 943 / 999 | 0 | 0.05, 0.21, 0.08, 0.03 | - | - | - | - | - | - | - | yes |
| earnings-logearn_interaction | 97462 | screen | ok | pass | 1.004 | 1033 / 1525 | 0 | 0.13, 0.08, 0.04, 0.04 | - | - | - | - | - | - | - | yes |
| earnings-logearn_interaction | 97463 | screen | ok | pass | 1.003 | 1164 / 1397 | 0 | 0.06, 0.07, 0.06, 0.09 | - | - | - | - | - | - | - | yes |
| mesquite-logmesquite_logvash | 97461 | screen | ok | pass | 1.005 | 1314 / 1655 | 0 | 0.09, 0.07, 0.07, 0.03 | - | - | - | - | - | - | - | yes |
| mesquite-logmesquite_logvash | 97462 | screen | ok | pass | 1.003 | 1222 / 1561 | 0 | 0.03, 0.06, 0.09, 0.06 | - | - | - | - | - | - | - | yes |
| mesquite-logmesquite_logvash | 97463 | screen | ok | pass | 1.002 | 1299 / 1473 | 0 | 0.04, 0.07, 0.02, 0.09 | - | - | - | - | - | - | - | yes |
| kidiq-kidscore_momhsiq | 97461 | screen | ok | pass | 1.004 | 1344 / 1370 | 0 | 0.07, 0.03, 0.03, 0.05 | - | - | - | - | - | - | - | yes |
| kidiq-kidscore_momhsiq | 97462 | screen | ok | pass | 1.002 | 1499 / 2072 | 0 | 0.02, 0.07, 0.07, 0.05 | - | - | - | - | - | - | - | yes |
| kidiq-kidscore_momhsiq | 97463 | screen | ok | pass | 1.002 | 1565 / 1904 | 0 | 0.07, 0.10, 0.11, 0.07 | - | - | - | - | - | - | - | yes |
| sblrc-blr | 97461 | screen | ok | pass | 1.004 | 1017 / 1330 | 0 | 0.06, 0.09, 0.04, 0.06 | - | - | - | - | - | - | - | yes |
| sblrc-blr | 97462 | screen | ok | pass | 1.003 | 857 / 1134 | 0 | 0.06, 0.05, 0.10, 0.05 | - | - | - | - | - | - | - | yes |
| sblrc-blr | 97463 | screen | ok | pass | 1.007 | 858 / 1032 | 0 | 0.10, 0.10, 0.04, 0.14 | - | - | - | - | - | - | - | yes |
| nes2000-nes | 97461 | screen | ok | pass | 1.003 | 1935 / 2224 | 0 | 0.07, 0.04, 0.03, 0.08 | - | - | - | - | - | - | - | yes |
| nes2000-nes | 97462 | screen | ok | pass | 1.006 | 1888 / 2070 | 0 | 0.11, 0.08, 0.08, 0.07 | - | - | - | - | - | - | - | yes |
| nes2000-nes | 97463 | screen | ok | pass | 1.003 | 2016 / 1987 | 0 | 0.08, 0.06, 0.04, 0.06 | - | - | - | - | - | - | - | yes |
| arK-arK | 97461 | screen | ok | pass | 1.001 | 2379 / 2086 | 0 | 0.07, 0.04, 0.05, 0.06 | - | - | - | - | - | - | - | yes |
| arK-arK | 97462 | screen | ok | pass | 1.005 | 2498 / 2083 | 0 | 0.04, 0.11, 0.06, 0.04 | - | - | - | - | - | - | - | yes |
| arK-arK | 97463 | screen | ok | pass | 1.003 | 2271 / 2376 | 0 | 0.09, 0.08, 0.05, 0.04 | - | - | - | - | - | - | - | yes |
| arma-arma11 | 97461 | screen | ok | pass | 1.001 | 3631 / 2822 | 0 | 0.03, 0.04, 0.09, 0.04 | - | - | - | - | - | - | - | yes |
| arma-arma11 | 97462 | screen | ok | pass | 1.002 | 3585 / 2508 | 0 | 0.02, 0.06, 0.07, 0.02 | - | - | - | - | - | - | - | yes |
| arma-arma11 | 97463 | screen | ok | pass | 1.001 | 3680 / 3034 | 0 | 0.07, 0.08, 0.05, 0.05 | - | - | - | - | - | - | - | yes |
| garch-garch11 | 97461 | screen | ok | pass | 1.003 | 1800 / 1781 | 0 | 0.04, 0.04, 0.08, 0.05 | - | - | - | - | - | - | - | yes |
| garch-garch11 | 97462 | screen | ok | pass | 1.003 | 1501 / 1979 | 0 | 0.10, 0.06, 0.14, 0.04 | - | - | - | - | - | - | - | yes |
| garch-garch11 | 97463 | screen | ok | pass | 1.002 | 1936 / 1626 | 0 | 0.12, 0.02, 0.07, 0.02 | - | - | - | - | - | - | - | yes |
| gp_pois_regr-gp_pois_regr | 97461 | screen | ok | pass | 1.003 | 826 / 1068 | 0 | 0.08, 0.06, 0.09, 0.11 | - | - | - | - | - | - | - | yes |
| gp_pois_regr-gp_pois_regr | 97462 | screen | ok | pass | 1.003 | 957 / 883 | 0 | 0.09, 0.08, 0.07, 0.05 | - | - | - | - | - | - | - | yes |
| gp_pois_regr-gp_pois_regr | 97463 | screen | ok | pass | 1.005 | 758 / 961 | 0 | 0.08, 0.08, 0.07, 0.09 | - | - | - | - | - | - | - | yes |
| hmm_example-hmm_example | 97461 | screen | ok | pass | 1.001 | 2381 / 2018 | 0 | 0.07, 0.05, 0.06, 0.03 | - | - | - | - | - | - | - | yes |
| hmm_example-hmm_example | 97462 | screen | ok | pass | 1.004 | 2086 / 1788 | 0 | 0.05, 0.03, 0.06, 0.04 | - | - | - | - | - | - | - | yes |
| hmm_example-hmm_example | 97463 | screen | ok | pass | 1.003 | 2409 / 1957 | 0 | 0.02, 0.04, 0.06, 0.05 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97461 | screen | ok | pass | 1.003 | 3723 / 1463 | 0 | 0.03, 0.05, 0.05, 0.07 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97462 | screen | ok | pass | 1.003 | 3749 / 1533 | 0 | 0.06, 0.08, 0.04, 0.03 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97463 | screen | ok | pass | 1.001 | 3621 / 2009 | 0 | 0.05, 0.06, 0.05, 0.07 | - | - | - | - | - | - | - | yes |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 97461 | screen | ok | **fail** | 1.014 | 395 / 140 | 0 | 0.11, 0.08, 0.48, 0.03 | - | Y | - | - | - | - | [2] | yes |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 97462 | screen | ok | **fail** | 1.007 | 799 / 308 | 0 | 0.10, 0.10, 0.08, 0.14 | - | Y | - | - | - | - | - | yes |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 97463 | screen | ok | **fail** | 1.008 | 831 / 382 | 0 | 0.10, 0.09, 0.07, 0.20 | - | Y | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97461 | screen | ok | pass | 1.005 | 748 / 1283 | 0 | 0.14, 0.05, 0.08, 0.11 | - | - | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97462 | screen | ok | pass | 1.005 | 941 / 1231 | 0 | 0.03, 0.12, 0.07, 0.07 | - | - | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97463 | screen | ok | pass | 1.008 | 970 / 1544 | 0 | 0.05, 0.14, 0.18, 0.05 | - | - | - | - | - | - | - | yes |
| mcycle_gp-accel_gp | 97461 | screen | ok | **fail** | 1.051 | 84 / 26 | 0 | 0.17, 0.41, 0.48, 0.55 | - | Y | - | - | - | - | - | yes |
| mcycle_gp-accel_gp | 97462 | screen | ok | **fail** | 1.064 | 92 / 55 | 0 | 0.21, 0.36, 0.67, 0.16 | - | Y | - | - | - | - | - | yes |
| mcycle_gp-accel_gp | 97463 | screen | ok | **fail** | 1.060 | 45 / 39 | 0 | 0.14, 0.19, 0.17, 0.83 | - | Y | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97464 | extra | ok | pass | 1.002 | 4251 / 1941 | 0 | 0.04, 0.03, 0.03, 0.06 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97465 | extra | ok | pass | 1.002 | 3656 / 1573 | 0 | 0.06, 0.06, 0.06, 0.07 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97466 | extra | ok | pass | 1.003 | 4789 / 2386 | 0 | 0.06, 0.04, 0.05, 0.05 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97467 | extra | ok | pass | 1.003 | 4725 / 2376 | 0 | 0.05, 0.07, 0.06, 0.05 | - | - | - | - | - | - | - | yes |
| bball_drive_event_0-hmm_drive_0 | 97468 | extra | ok | pass | 1.004 | 3987 / 1966 | 0 | 0.06, 0.07, 0.07, 0.04 | - | - | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97464 | extra | **timeout** | | | | | | | | | | | | | |
| hudson_lynx_hare-lotka_volterra | 97465 | extra | ok | pass | 1.004 | 1021 / 1419 | 0 | 0.10, 0.09, 0.09, 0.10 | - | - | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97466 | extra | ok | pass | 1.002 | 1059 / 1803 | 0 | 0.08, 0.06, 0.09, 0.11 | - | - | - | - | - | - | - | yes |
| hudson_lynx_hare-lotka_volterra | 97467 | extra | ok | **fail** | 1.221 | 13 / 11 | 0 | 0.08, 0.08, 0.05, 114.42 | [3] | Y | Y | - | [3] | - | [3] | yes |
| hudson_lynx_hare-lotka_volterra | 97468 | extra | ok | pass | 1.003 | 801 / 1422 | 0 | 0.06, 0.07, 0.07, 0.10 | - | - | - | - | - | - | - | yes |

## Confusion (all process-valid cells)

| truth | detector set | TP | FN | FP | TN | sensitivity | specificity | false positives |
|---|---|---:|---:|---:|---:|---:|---:|---|
| T_gate | D1_warmup_step | 0 | 10 | 0 | 50 | 0.000 | 1.000 | - |
| T_gate | D2_warmup_density | 1 | 9 | 0 | 50 | 0.100 | 1.000 | - |
| T_gate | D3_sampled_density | 0 | 10 | 0 | 50 | 0.000 | 1.000 | - |
| T_gate | D4_rhat_loo | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_gate | C1 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_gate | C2 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_gate | C3 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_gate | C4 | 1 | 9 | 0 | 50 | 0.100 | 1.000 | - |
| T_gate | C5 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_gate | phase_warmup_end | 1 | 9 | 0 | 50 | 0.100 | 1.000 | - |
| T_gate | phase_sampling_end | 3 | 7 | 0 | 50 | 0.300 | 1.000 | - |
| T_wrong | D1_warmup_step | 0 | 1 | 0 | 59 | 0.000 | 1.000 | - |
| T_wrong | D2_warmup_density | 1 | 0 | 0 | 59 | 1.000 | 1.000 | - |
| T_wrong | D3_sampled_density | 0 | 1 | 0 | 59 | 0.000 | 1.000 | - |
| T_wrong | D4_rhat_loo | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_wrong | C1 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_wrong | C2 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_wrong | C3 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_wrong | C4 | 1 | 0 | 0 | 59 | 1.000 | 1.000 | - |
| T_wrong | C5 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_wrong | phase_warmup_end | 1 | 0 | 0 | 59 | 1.000 | 1.000 | - |
| T_wrong | phase_sampling_end | 1 | 0 | 2 | 57 | 1.000 | 0.966 | eight_schools-eight_schools_centered/97461, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 |
| T_rhat | D1_warmup_step | 0 | 8 | 0 | 52 | 0.000 | 1.000 | - |
| T_rhat | D2_warmup_density | 1 | 7 | 0 | 52 | 0.125 | 1.000 | - |
| T_rhat | D3_sampled_density | 0 | 8 | 0 | 52 | 0.000 | 1.000 | - |
| T_rhat | D4_rhat_loo | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |
| T_rhat | C1 | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |
| T_rhat | C2 | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |
| T_rhat | C3 | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |
| T_rhat | C4 | 1 | 7 | 0 | 52 | 0.125 | 1.000 | - |
| T_rhat | C5 | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |
| T_rhat | phase_warmup_end | 1 | 7 | 0 | 52 | 0.125 | 1.000 | - |
| T_rhat | phase_sampling_end | 3 | 5 | 0 | 52 | 0.375 | 1.000 | - |

## Confusion (17-model screen only)

| truth | detector set | TP | FN | FP | TN | sensitivity | specificity |
|---|---|---:|---:|---:|---:|---:|---:|
| T_gate | D1_warmup_step | 0 | 9 | 0 | 42 | 0.000 | 1.000 |
| T_gate | D2_warmup_density | 0 | 9 | 0 | 42 | 0.000 | 1.000 |
| T_gate | D3_sampled_density | 0 | 9 | 0 | 42 | 0.000 | 1.000 |
| T_gate | D4_rhat_loo | 2 | 7 | 0 | 42 | 0.222 | 1.000 |
| T_gate | C1 | 2 | 7 | 0 | 42 | 0.222 | 1.000 |
| T_gate | C2 | 2 | 7 | 0 | 42 | 0.222 | 1.000 |
| T_gate | C3 | 2 | 7 | 0 | 42 | 0.222 | 1.000 |
| T_gate | C4 | 0 | 9 | 0 | 42 | 0.000 | 1.000 |
| T_gate | C5 | 2 | 7 | 0 | 42 | 0.222 | 1.000 |
| T_wrong | D1_warmup_step | 0 | 0 | 0 | 51 | nan | 1.000 |
| T_wrong | D2_warmup_density | 0 | 0 | 0 | 51 | nan | 1.000 |
| T_wrong | D3_sampled_density | 0 | 0 | 0 | 51 | nan | 1.000 |
| T_wrong | D4_rhat_loo | 0 | 0 | 2 | 49 | nan | 0.961 |
| T_wrong | C1 | 0 | 0 | 2 | 49 | nan | 0.961 |
| T_wrong | C2 | 0 | 0 | 2 | 49 | nan | 0.961 |
| T_wrong | C3 | 0 | 0 | 2 | 49 | nan | 0.961 |
| T_wrong | C4 | 0 | 0 | 0 | 51 | nan | 1.000 |
| T_wrong | C5 | 0 | 0 | 2 | 49 | nan | 0.961 |
| T_rhat | D1_warmup_step | 0 | 7 | 0 | 44 | 0.000 | 1.000 |
| T_rhat | D2_warmup_density | 0 | 7 | 0 | 44 | 0.000 | 1.000 |
| T_rhat | D3_sampled_density | 0 | 7 | 0 | 44 | 0.000 | 1.000 |
| T_rhat | D4_rhat_loo | 2 | 5 | 0 | 44 | 0.286 | 1.000 |
| T_rhat | C1 | 2 | 5 | 0 | 44 | 0.286 | 1.000 |
| T_rhat | C2 | 2 | 5 | 0 | 44 | 0.286 | 1.000 |
| T_rhat | C3 | 2 | 5 | 0 | 44 | 0.286 | 1.000 |
| T_rhat | C4 | 0 | 7 | 0 | 44 | 0.000 | 1.000 |
| T_rhat | C5 | 2 | 5 | 0 | 44 | 0.286 | 1.000 |

## False negatives (full union C1)

- T_gate: eight_schools-eight_schools_centered/97462, eight_schools-eight_schools_centered/97463, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97462, one_comp_mm_elim_abs-one_comp_mm_elim_abs/97463, mcycle_gp-accel_gp/97461, mcycle_gp-accel_gp/97462, mcycle_gp-accel_gp/97463
- T_wrong: none
- T_rhat: eight_schools-eight_schools_centered/97462, eight_schools-eight_schools_centered/97463, mcycle_gp-accel_gp/97461, mcycle_gp-accel_gp/97462, mcycle_gp-accel_gp/97463

## Chain-level agreement (cells with a wrong or flagged chain)

| cell | wrong chains | flagged chains | by detector |
|---|---|---|---|
| eight_schools-eight_schools_centered/97461 | - | [2] | {'D4_rhat_loo': [2]} |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461 | - | [2] | {'D4_rhat_loo': [2]} |
| hudson_lynx_hare-lotka_volterra/97467 | [3] | [3] | {'D2_warmup_density': [3], 'D4_rhat_loo': [3]} |

## Warning lines as printed by `Summary`

- `eight_schools-eight_schools_centered/97461`: `warning: chain 2 disagrees with the other chains: max R-hat 1.013 falls to 1.006 without this chain`
- `one_comp_mm_elim_abs-one_comp_mm_elim_abs/97461`: `warning: chain 2 disagrees with the other chains: max R-hat 1.014 falls to 1.005 without this chain`
- `hudson_lynx_hare-lotka_volterra/97467`: `warning: chain 3 disagrees with the other chains: last-warmup-window median log density -297.837 is 160.690 below the chains' median -137.146 (limit 8.147 = 3 x median IQR); max R-hat 1.221 falls to 1.004 without this chain`

## Decision

`{"rule_A": null, "rule_B": "C1", "ships": "C1", "ships_under": "rule_B"}`

## Predictions

- P1: C1 sensitivity against T_gate (fails rule A: ESS- and divergence-only failures have no wrong chain) - predicted 0.35 in [0.15, 0.6], observed 0.300: **held**
- P2: C1 specificity against T_gate - predicted 0.96 in [0.9, 1.0], observed 1.000: **held**
- P3: C1 sensitivity against T_wrong - predicted 0.95 in [0.75, 1.0], observed 1.000: **held**
- P4: C1 specificity against T_wrong - predicted 0.94 in [0.88, 1.0], observed 0.966: **held**
- P5: D3 (retained-draw density) specificity against T_wrong - predicted 0.99 in [0.97, 1.0], observed 1.000: **held**
- P6: D4 (leave-one-out R-hat) specificity against T_gate - predicted 1.0 in [0.98, 1.0], observed 1.000: **held**

## Exploratory threshold sweep (all cells; reported only, cannot ship)

| phases | step ratio | IQRs | T_gate sens | T_gate spec | T_wrong sens | T_wrong spec | T_wrong FP |
|---|---:|---:|---:|---:|---:|---:|---|
| warmup | 0.05 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 2.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.05 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.05 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 3.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.05 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.05 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 5.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.05 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.05 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 10.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.05 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.1 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 2.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.1 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.1 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 3.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.1 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.1 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 5.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.1 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.1 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 10.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.1 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.2 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 2.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.2 | 2.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.2 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 3.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.2 | 3.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.2 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 5.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.2 | 5.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| warmup | 0.2 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |
| sampled | - | 10.0 | 0.000 | 1.000 | 0.000 | 1.000 | - |
| warmup+sampled | 0.2 | 10.0 | 0.100 | 1.000 | 1.000 | 1.000 | - |

Cells not ok: ['hudson_lynx_hare-lotka_volterra/97464: timeout']
Rust/Python detector mismatches: none
