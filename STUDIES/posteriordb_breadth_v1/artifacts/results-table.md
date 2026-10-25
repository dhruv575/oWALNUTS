# posteriordb breadth v1 (WP46) — results

oWALNUTS shipped defaults, 4 x 1,000/1,000, seeds 461461, 461462, 461463. Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on every gate parameter, zero retained divergences. `caps` = retained depth-10 fraction; `refined` = retained refined-leaf fraction; `inv` = retained invalid/zero-density/non-finite evaluations; `exh` = retained refinement exhaustions; walls are contended (ten agents, 16 cores, Windows owned BridgeStan worker serialises gradients) and are not evidence.

| tier | model | seed | pass | min bulk | min tail | max R-hat | div | max abs z | median h | min h/median | caps | refined | inv | exh | chain disagr. (sd) | grads | ESS/grad x1e3 | wall s | mechanism |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ref | low_dim_gauss_mix-low_dim_gauss_mix | 461461 | yes | 4321 | 2538 | 1.0030 | 0 | 1.82 | 0.567 | 0.90 | 0.000 | 0.0017 | 0 | 0 | 0.06 | 76,927 | 56.168 | 22.5 | — |
| ref | low_dim_gauss_mix-low_dim_gauss_mix | 461462 | yes | 2867 | 2563 | 1.0015 | 0 | 1.81 | 0.61 | 0.01 | 0.000 | 0.0036 | 0 | 0 | 0.07 | 548,532 | 5.227 | 238.5 | step_collapse |
| ref | low_dim_gauss_mix-low_dim_gauss_mix | 461463 | yes | 3337 | 2365 | 1.0016 | 0 | 1.74 | 0.526 | 0.92 | 0.000 | 0.0019 | 0 | 0 | 0.06 | 105,866 | 31.519 | 22.0 | — |
| ref | kilpisjarvi_mod-kilpisjarvi | 461461 | yes | 847 | 1032 | 1.0057 | 0 | 0.64 | 0.00328 | 0.66 | 0.122 | 0.0001 | 0 | 0 | 0.08 | 4,195,604 | 0.202 | 32.6 | borderline: depth_cap |
| ref | kilpisjarvi_mod-kilpisjarvi | 461462 | NO | 8 | 36 | 1.4536 | 0 | 3.28 | 0.00294 | 0.60 | 0.204 | 0.0001 | 0 | 0 | 1.71 | 3,960,177 | 0.002 | 35.9 | multimodality,depth_cap,metric_floor |
| ref | kilpisjarvi_mod-kilpisjarvi | 461463 | yes | 842 | 950 | 1.0063 | 0 | 1.69 | 0.00293 | 0.98 | 0.132 | 0.0001 | 0 | 0 | 0.18 | 4,104,724 | 0.205 | 88.6 | borderline: depth_cap |
| ref | gp_pois_regr-gp_regr | 461461 | yes | 3843 | 2912 | 1.0008 | 0 | 2.20 | 0.75 | 0.92 | 0.000 | 0.0017 | 0 | 0 | 0.07 | 40,283 | 95.398 | 3.9 | — |
| ref | gp_pois_regr-gp_regr | 461462 | yes | 3653 | 2273 | 1.0020 | 0 | 1.88 | 0.754 | 0.93 | 0.000 | 0.0020 | 0 | 0 | 0.11 | 40,605 | 89.954 | 1.9 | — |
| ref | gp_pois_regr-gp_regr | 461463 | yes | 3773 | 2936 | 1.0017 | 0 | 1.39 | 0.81 | 0.81 | 0.000 | 0.0019 | 0 | 0 | 0.05 | 38,669 | 97.580 | 1.9 | — |
| ref | bball_drive_event_1-hmm_drive_1 | 461461 | yes | 2584 | 1728 | 1.0016 | 0 | 1.31 | 0.276 | 0.97 | 0.000 | 0.0024 | 0 | 0 | 0.08 | 184,130 | 14.036 | 94.0 | — |
| ref | bball_drive_event_1-hmm_drive_1 | 461462 | yes | 2554 | 2347 | 1.0019 | 0 | 1.67 | 0.251 | 0.95 | 0.000 | 0.0013 | 0 | 0 | 0.07 | 235,219 | 10.860 | 139.7 | — |
| ref | bball_drive_event_1-hmm_drive_1 | 461463 | yes | 2452 | 1959 | 1.0028 | 0 | 2.05 | 0.264 | 0.83 | 0.000 | 0.0012 | 0 | 0 | 0.12 | 565,354 | 4.338 | 270.7 | — |
| ref | sblri-blr | 461461 | yes | 751 | 1263 | 1.0037 | 0 | 0.87 | 0.213 | 0.94 | 0.000 | 0.0017 | 0 | 0 | 0.13 | 85,697 | 8.763 | 1.2 | metric_floor |
| ref | sblri-blr | 461462 | yes | 831 | 1012 | 1.0068 | 0 | 2.01 | 0.216 | 0.87 | 0.000 | 0.0014 | 0 | 0 | 0.16 | 81,840 | 10.159 | 1.0 | borderline: metric_floor |
| ref | sblri-blr | 461463 | yes | 665 | 1191 | 1.0087 | 0 | 2.54 | 0.21 | 0.94 | 0.000 | 0.0009 | 0 | 0 | 0.12 | 89,825 | 7.402 | 1.8 | borderline: metric_floor |
| ref | earnings-logearn_logheight_male | 461461 | yes | 1217 | 1391 | 1.0040 | 0 | 0.54 | 0.00748 | 0.95 | 0.000 | 0.0002 | 0 | 0 | 0.11 | 2,647,082 | 0.460 | 248.2 | — |
| ref | earnings-logearn_logheight_male | 461462 | yes | 1040 | 1386 | 1.0025 | 0 | 1.11 | 0.00676 | 0.93 | 0.000 | 0.0001 | 0 | 0 | 0.14 | 2,744,380 | 0.379 | 281.8 | — |
| ref | earnings-logearn_logheight_male | 461463 | yes | 899 | 933 | 1.0053 | 0 | 0.65 | 0.00606 | 0.86 | 0.000 | 0.0001 | 0 | 0 | 0.14 | 2,999,092 | 0.300 | 519.9 | borderline: unclassified_slow_mixing |
| ref | earnings-logearn_height_male | 461461 | yes | 1261 | 1446 | 1.0060 | 0 | 1.77 | 0.0248 | 0.65 | 0.000 | 0.0000 | 0 | 0 | 0.05 | 1,004,049 | 1.256 | 134.9 | borderline: metric_floor |
| ref | earnings-logearn_height_male | 461462 | yes | 1026 | 1307 | 1.0076 | 0 | 0.74 | 0.0264 | 0.95 | 0.000 | 0.0002 | 0 | 0 | 0.13 | 889,871 | 1.154 | 116.6 | borderline: unclassified_slow_mixing |
| ref | earnings-logearn_height_male | 461463 | yes | 1114 | 1317 | 1.0037 | 0 | 1.28 | 0.0272 | 0.12 | 0.000 | 0.0002 | 0 | 0 | 0.07 | 962,601 | 1.157 | 96.2 | step_collapse,metric_floor |
| ref | kidiq-kidscore_interaction | 461461 | NO | 703 | 831 | 1.0117 | 0 | 1.92 | 0.0319 | 0.84 | 0.000 | 0.0006 | 0 | 0 | 0.17 | 707,974 | 0.993 | 106.8 | unclassified_slow_mixing |
| ref | kidiq-kidscore_interaction | 461462 | yes | 824 | 966 | 1.0046 | 0 | 1.47 | 0.0307 | 0.94 | 0.000 | 0.0003 | 0 | 0 | 0.18 | 732,184 | 1.125 | 144.3 | — |
| ref | kidiq-kidscore_interaction | 461463 | yes | 857 | 999 | 1.0057 | 0 | 0.78 | 0.0313 | 0.87 | 0.000 | 0.0003 | 0 | 0 | 0.14 | 726,440 | 1.180 | 428.7 | borderline: unclassified_slow_mixing |
| ref | kidiq_with_mom_work-kidscore_mom_work | 461461 | yes | 1420 | 1791 | 1.0031 | 0 | 0.84 | 0.329 | 0.95 | 0.000 | 0.0004 | 0 | 0 | 0.13 | 158,665 | 8.951 | 11.6 | — |
| ref | kidiq_with_mom_work-kidscore_mom_work | 461462 | yes | 1233 | 2012 | 1.0008 | 0 | 1.58 | 0.316 | 0.92 | 0.000 | 0.0023 | 0 | 0 | 0.05 | 156,653 | 7.868 | 17.7 | — |
| ref | kidiq_with_mom_work-kidscore_mom_work | 461463 | yes | 1303 | 1685 | 1.0037 | 0 | 0.83 | 0.329 | 0.87 | 0.000 | 0.0021 | 0 | 0 | 0.10 | 157,354 | 8.278 | 9.8 | — |
| ref | kidiq_with_mom_work-kidscore_interaction_c2 | 461461 | yes | 2031 | 2152 | 1.0018 | 0 | 1.67 | 0.501 | 0.97 | 0.000 | 0.0029 | 0 | 0 | 0.12 | 89,273 | 22.753 | 6.7 | — |
| ref | kidiq_with_mom_work-kidscore_interaction_c2 | 461462 | yes | 1940 | 2252 | 1.0034 | 0 | 1.26 | 0.528 | 0.96 | 0.000 | 0.0037 | 0 | 0 | 0.14 | 87,448 | 22.185 | 4.9 | — |
| ref | kidiq_with_mom_work-kidscore_interaction_c2 | 461463 | yes | 2197 | 2491 | 1.0016 | 0 | 1.29 | 0.484 | 0.85 | 0.000 | 0.0027 | 0 | 0 | 0.06 | 89,858 | 24.445 | 7.1 | — |
| ref | mesquite-logmesquite_logvas | 461461 | yes | 1318 | 1798 | 1.0035 | 0 | 2.68 | 0.0695 | 0.82 | 0.000 | 0.0010 | 0 | 0 | 0.06 | 418,829 | 3.147 | 9.8 | — |
| ref | mesquite-logmesquite_logvas | 461462 | yes | 1602 | 1924 | 1.0022 | 0 | 2.21 | 0.0743 | 0.95 | 0.000 | 0.0013 | 0 | 0 | 0.07 | 409,352 | 3.913 | 8.8 | — |
| ref | mesquite-logmesquite_logvas | 461463 | yes | 1409 | 1538 | 1.0045 | 0 | 2.16 | 0.073 | 0.95 | 0.000 | 0.0010 | 0 | 0 | 0.10 | 417,016 | 3.378 | 39.7 | — |
| ref | mesquite-mesquite | 461461 | yes | 2066 | 1994 | 1.0035 | 0 | 1.39 | 0.0666 | 0.90 | 0.000 | 0.0009 | 0 | 0 | 0.10 | 666,117 | 3.101 | 54.7 | — |
| ref | mesquite-mesquite | 461462 | yes | 1845 | 2008 | 1.0033 | 0 | 1.22 | 0.0707 | 0.93 | 0.000 | 0.0019 | 0 | 0 | 0.09 | 683,436 | 2.699 | 40.5 | — |
| ref | mesquite-mesquite | 461463 | yes | 2194 | 2166 | 1.0035 | 0 | 1.06 | 0.0678 | 0.89 | 0.000 | 0.0012 | 0 | 0 | 0.09 | 684,486 | 3.206 | 30.8 | — |
| ref | nes1996-nes | 461461 | yes | 2128 | 2323 | 1.0030 | 0 | 2.50 | 0.0783 | 0.95 | 0.000 | 0.0006 | 0 | 0 | 0.12 | 417,935 | 5.092 | 101.9 | — |
| ref | nes1996-nes | 461462 | yes | 1679 | 1939 | 1.0037 | 0 | 2.79 | 0.0851 | 0.95 | 0.000 | 0.0021 | 0 | 0 | 0.10 | 392,008 | 4.282 | 80.2 | — |
| ref | nes1996-nes | 461463 | yes | 1959 | 2296 | 1.0018 | 0 | 1.93 | 0.0799 | 0.93 | 0.000 | 0.0004 | 0 | 0 | 0.08 | 397,837 | 4.923 | 93.0 | — |
| ref | nes1980-nes | 461461 | yes | 2018 | 2125 | 1.0042 | 0 | 1.80 | 0.0879 | 0.85 | 0.000 | 0.0007 | 0 | 0 | 0.09 | 380,808 | 5.300 | 50.7 | — |
| ref | nes1980-nes | 461462 | yes | 1971 | 2245 | 1.0026 | 0 | 1.53 | 0.0886 | 0.91 | 0.000 | 0.0015 | 0 | 0 | 0.12 | 376,117 | 5.241 | 53.1 | — |
| ref | nes1980-nes | 461463 | yes | 1725 | 1924 | 1.0025 | 0 | 1.99 | 0.0925 | 0.90 | 0.000 | 0.0014 | 0 | 0 | 0.14 | 368,852 | 4.676 | 106.5 | — |
| gates | seeds_data-seeds_centered_model | 461461 | NO | 272 | 124 | 1.0200 | 0 | — | 0.219 | 0.89 | 0.000 | 0.0042 | 0 | 0 | 0.17 | 155,973 | 1.744 | 7.1 | unclassified_slow_mixing |
| gates | seeds_data-seeds_centered_model | 461462 | NO | 60 | 15 | 1.0658 | 0 | — | 0.221 | 0.94 | 0.000 | 0.0104 | 0 | 0 | 0.45 | 169,249 | 0.356 | 9.3 | unclassified_slow_mixing |
| gates | seeds_data-seeds_centered_model | 461463 | NO | 92 | 26 | 1.0385 | 0 | — | 0.158 | 0.76 | 0.000 | 0.0095 | 0 | 0 | 0.29 | 183,518 | 0.503 | 8.2 | unclassified_slow_mixing |
| gates | GLMM_Poisson_data-GLMM_Poisson_model | 461461 | NO | 7 | 11 | 1.6205 | 0 | — | 0.121 | 0.02 | 0.086 | 0.0026 | 0 | 0 | 1.62 | 1,307,391 | 0.005 | 53.5 | start_lottery,depth_cap,step_collapse,metric_floor |
| gates | GLMM_Poisson_data-GLMM_Poisson_model | 461462 | NO | 5 | 11 | 2.8484 | 0 | — | 0.0132 | 0.47 | 0.210 | 0.0012 | 0 | 0 | 2.31 | 2,988,939 | 0.002 | 312.4 | start_lottery,depth_cap,metric_floor |
| gates | GLMM_Poisson_data-GLMM_Poisson_model | 461463 | NO | 7 | 11 | 1.6514 | 0 | — | 0.0851 | 0.10 | 0.000 | 0.0025 | 138061 | 1000 | 2.31 | 1,597,820 | 0.004 | 51.0 | start_lottery,step_collapse,metric_floor,constraint_boundary |
| gates | radon_all-radon_hierarchical_intercept_centered | 461461 | yes | 416 | 907 | 1.0077 | 0 | — | 0.173 | 0.88 | 0.000 | 0.0024 | 0 | 0 | 0.12 | 342,060 | 1.215 | 1150.0 | borderline: unclassified_slow_mixing |
| gates | radon_all-radon_hierarchical_intercept_centered | 461462 | yes | 441 | 506 | 1.0083 | 0 | — | 0.166 | 0.90 | 0.000 | 0.0008 | 0 | 0 | 0.10 | 395,943 | 1.114 | 905.3 | borderline: unclassified_slow_mixing |
| gates | radon_all-radon_hierarchical_intercept_centered | 461463 | yes | 463 | 878 | 1.0075 | 0 | — | 0.173 | 0.91 | 0.000 | 0.0006 | 0 | 0 | 0.13 | 367,168 | 1.260 | 707.1 | borderline: unclassified_slow_mixing |
| gates | sat-hier_2pl | 461461 | yes | 1965 | 1886 | 1.0086 | 0 | — | 0.194 | 0.97 | 0.000 | 0.0014 | 0 | 0 | 0.10 | 898,705 | 2.187 | 1519.1 | borderline: unclassified_slow_mixing |
| gates | sat-hier_2pl | 461462 | yes | 1777 | 1938 | 1.0077 | 0 | — | 0.188 | 0.92 | 0.000 | 0.0016 | 0 | 0 | 0.10 | 485,709 | 3.658 | 787.4 | borderline: unclassified_slow_mixing |
| gates | sat-hier_2pl | 461463 | yes | 1763 | 1859 | 1.0077 | 0 | — | 0.197 | 0.94 | 0.000 | 0.0026 | 0 | 0 | 0.14 | 718,580 | 2.454 | 805.8 | borderline: unclassified_slow_mixing |
| gates | science_irt-grsm_latent_reg_irt | 461461 | NO | 543 | 1048 | 1.0160 | 0 | — | 0.193 | 0.88 | 0.000 | 0.0023 | 0 | 0 | 0.14 | 308,512 | 1.761 | 752.8 | unclassified_slow_mixing |
| gates | science_irt-grsm_latent_reg_irt | 461462 | yes | 715 | 1376 | 1.0088 | 0 | — | 0.191 | 0.96 | 0.000 | 0.0027 | 0 | 0 | 0.16 | 270,604 | 2.641 | 647.1 | borderline: unclassified_slow_mixing |
| gates | science_irt-grsm_latent_reg_irt | 461463 | yes | 528 | 1204 | 1.0089 | 0 | — | 0.187 | 0.93 | 0.000 | 0.0024 | 0 | 0 | 0.13 | 318,993 | 1.655 | 743.9 | borderline: unclassified_slow_mixing |

Reference tier: **40/42** cells pass. Gates-only tier: **8/15**.

## Mechanism counts over failing and borderline cells

| label | primary | any |
|---|---:|---:|
| constraint_boundary | 0 | 1 |
| depth_cap | 2 | 5 |
| metric_floor | 3 | 7 |
| multimodality | 1 | 1 |
| start_lottery | 3 | 3 |
| step_collapse | 0 | 2 |
| unclassified_slow_mixing | 16 | 16 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_reference_tier_pass_count | {"predicted": 32, "interval": [28, 36], "value": 40, "below_v6_rate": false} | False |
| P2_failing_families | {"predicted_models": ["kilpisjarvi_mod-kilpisjarvi", "bball_drive_event_1-hmm_drive_1", "earnings-logearn_logheight_male", "kidiq-kidscore_interaction", "seeds_data-seeds_centered_model"], "observed_failing_models": ["GLMM_Poisson_data-GLMM_Poisson_model", "kidiq-kidscore_interaction", "kilpisjarvi_mod-kilpisjarvi", "science_irt-grsm_latent_reg_irt", "seeds_data-seeds_centered_model"], "predicted_and_failed": ["kidiq-kidscore_interaction", "kilpisjarvi_mod-kilpisjarvi", "seeds_data-seeds_centered_model"], "predicted_but_clean": ["bball_drive_event_1-hmm_drive_1", "earnings-logearn_logheight_male"], "unpredicted_failures": ["GLMM_Poisson_data-GLMM_Poisson_model", "science_irt-grsm_latent_reg_irt"]} | reported |
| P3_gates_only_tier_pass_count | {"interval": [7, 13], "value": 8} | True |
| P4_passing_reference_cells_max_abs_z_le_4 | {"value": []} | True |
| P6_modal_primary_mechanism_failing_reference_cells | {"counts": {"multimodality": 1, "unclassified_slow_mixing": 1}, "value": "multimodality"} | False |
| P5_no_process_errors | {"value": []} | True |
