# posteriordb v7 seed extension (WP62) — results

Commit `c5c60122`. Ratio = oWALNUTS / CmdStan seed-median min-bulk-ESS per gradient. New seeds [620601, 620602, 620603]; v7 seeds [560561, 560562, 560563].

| model | new 3: passes oWALNUTS / CmdStan | new 3 ratio | v7 3 ratio | pooled 6 ratio |
|---|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 3/3 / 0/3 | 0.883 | 1.025 | 0.891 |
| eight_schools-eight_schools_centered | 0/3 / 0/3 | 0.486 | 0.182 | 0.304 |
| diamonds-diamonds | 3/3 / 3/3 | 0.846 | 0.882 | 0.870 |
| earnings-logearn_interaction | 3/3 / 3/3 | 0.747 | 0.775 | 0.761 |
| mesquite-logmesquite_logvash | 3/3 / 3/3 | 0.884 | 0.957 | 0.939 |
| kidiq-kidscore_momhsiq | 3/3 / 3/3 | 0.901 | 0.884 | 0.901 |
| sblrc-blr | 3/3 / 3/3 | 0.839 | 0.809 | 0.824 |
| nes2000-nes | 3/3 / 3/3 | 0.849 | 0.870 | 0.867 |
| arK-arK | 3/3 / 3/3 | 0.845 | 0.845 | 0.845 |
| garch-garch11 | 3/3 / 3/3 | 0.898 | 0.957 | 0.908 |
| gp_pois_regr-gp_pois_regr | 3/3 / 0/3 | 0.750 | 0.820 | 0.788 |
| hmm_example-hmm_example | 3/3 / 3/3 | 0.871 | 0.965 | 0.919 |
| bball_drive_event_0-hmm_drive_0 | 3/3 / 2/3 | 0.984 | 0.661 | 0.952 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1/3 / 0/3 | 1.630 | 0.504 | 0.843 |
| hudson_lynx_hare-lotka_volterra | 3/3 / 1/3 (error) | — | — | — |
| mcycle_gp-accel_gp | 0/3 / 0/3 | 0.345 | 0.347 | 0.346 |

| statistic | value | models |
|---|---:|---:|
| geomean, new 3 seeds | **0.810** | 15 |
| geomean, v7 3 seeds (recomputed) | 0.708 | 15 |
| geomean, pooled 6 seeds | **0.761** | 15 |
| leave-one-seed-out interval | **[0.740, 0.822]** (width 0.082) | — |
| single-seed geomeans | 560561: 1.371, 560562: 0.792, 560563: 0.942, 620601: 0.969, 620602: 0.770, 620603: 1.669 | — |
| log-scale SD of single-seed geomeans | 0.310 | — |
| jackknife SE of the pooled 6-seed geomean | 0.071 | — |
| **recommended seeds** for a +/-0.05 half-width (primary: k (2 SE_jk / 0.05)^2) | **49** | — |
| seeds for a +/-0.05 log half-width from single-seed SD (reported) | 154 | — |

| arm | passes new /48 | passes v7 /48 | passes pooled /96 |
|---|---:|---:|---:|
| owalnuts | 40/48 | 40/48 | 80/96 |
| cmdstan | 30/48 | 32/48 | 62/96 |

| prediction | value | held |
|---|---|---|
| Q1_new_three_geomean_in_[0.65,0.95] | 0.810 | True |
| Q2_pooled_six_geomean_in_[0.72,0.85] | 0.761 | True |
| Q3_loso_range_wider_than_0.08 | 0.082 | True |
| Q4_owalnuts_new_passes_ge_40_of_48 | 40 | True |
| reported_pooled_six_clears_0.75 | True | reported |
| reported_passing_owalnuts_abs_z_gt_4_new | [] | reported |
| reported_passing_owalnuts_abs_z_gt_4_pooled | [] | reported |
