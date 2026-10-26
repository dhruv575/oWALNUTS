# posteriordb v7 seed extension (WP62) — results

Commit `c5c60122`. Ratio = oWALNUTS / CmdStan seed-median min-bulk-ESS per gradient. New seeds [620601, 620602, 620603]; v7 seeds [560561, 560562, 560563].

| model | new 3: passes oWALNUTS / CmdStan | new 3 ratio | v7 3 ratio | pooled 6 ratio |
|---|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 3/3 / 2/3 | 0.816 | 1.126 | 1.045 |
| eight_schools-eight_schools_centered | 0/3 / 0/3 | 0.436 | 0.530 | 0.575 |
| diamonds-diamonds | 3/3 / 3/3 | 0.862 | 0.782 | 0.831 |
| earnings-logearn_interaction | 3/3 / 3/3 | 0.828 | 0.877 | 0.891 |
| mesquite-logmesquite_logvash | 3/3 / 3/3 | 0.856 | 0.990 | 0.919 |
| kidiq-kidscore_momhsiq | 3/3 / 3/3 | 1.032 | 1.036 | 1.034 |
| sblrc-blr | 3/3 / 3/3 | 0.680 | 0.700 | 0.693 |
| nes2000-nes | 3/3 / 3/3 | 0.893 | 0.861 | 0.888 |
| arK-arK | 3/3 / 3/3 | 0.813 | 0.776 | 0.779 |
| garch-garch11 | 3/3 / 3/3 | 0.916 | 0.889 | 0.904 |
| gp_pois_regr-gp_pois_regr | 3/3 / 0/3 | 0.765 | 0.612 | 0.677 |
| hmm_example-hmm_example | 3/3 / 3/3 | 0.980 | 0.837 | 0.934 |
| bball_drive_event_0-hmm_drive_0 | 3/3 / 1/3 | 276.344 | 102.024 | 132.866 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 2/3 / 0/3 | 4.770 | 1.607 | 2.530 |
| hudson_lynx_hare-lotka_volterra | 3/3 / 1/3 (error) | — | — | — |
| mcycle_gp-accel_gp | 0/3 / 0/3 | 0.385 | 0.583 | 0.424 |

| statistic | value | models |
|---|---:|---:|
| geomean, new 3 seeds | **1.276** | 15 |
| geomean, v7 3 seeds (recomputed) | 1.154 | 15 |
| geomean, pooled 6 seeds | **1.206** | 15 |
| leave-one-seed-out interval | **[1.159, 1.265]** (width 0.107) | — |
| single-seed geomeans | 560561: 0.977, 560562: 1.054, 560563: 1.128, 620601: 1.184, 620602: 1.236, 620603: 1.572 | — |
| log-scale SD of single-seed geomeans | 0.164 | — |
| jackknife SE of the pooled 6-seed geomean | 0.090 | — |
| **recommended seeds** for a +/-0.05 half-width (primary: k (2 SE_jk / 0.05)^2) | **78** | — |
| seeds for a +/-0.05 log half-width from single-seed SD (reported) | 44 | — |

| arm | passes new /48 | passes v7 /48 | passes pooled /96 |
|---|---:|---:|---:|
| owalnuts | 41/48 | 41/48 | 82/96 |
| cmdstan | 31/48 | 31/48 | 62/96 |

| prediction | value | held |
|---|---|---|
| Q1_new_three_geomean_in_[0.65,0.95] | 1.276 | False |
| Q2_pooled_six_geomean_in_[0.72,0.85] | 1.206 | False |
| Q3_loso_range_wider_than_0.08 | 0.107 | True |
| Q4_owalnuts_new_passes_ge_40_of_48 | 41 | True |
| reported_pooled_six_clears_0.75 | True | reported |
| reported_passing_owalnuts_abs_z_gt_4_new | [] | reported |
| reported_passing_owalnuts_abs_z_gt_4_pooled | [] | reported |
