# WP72 posteriordb ratio robustness — results

oWALNUTS / CmdStan min-bulk-ESS per gradient, fixed 16, Linux. Bootstrap: seeds resampled with replacement, 10000 resamples, percentile interval.

| statistic | pool | value | 95% bootstrap interval | models | most influential model (value without it) |
|---|---|---:|---|---:|---|
| (a) v7 pooled geomean | linux_18_seeds | 0.822 | [0.776, 0.892] | 16 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.772) |
| (b) joint-pass | linux_18_seeds | 0.870 | [0.833, 0.891] | 12 | sblrc-blr (0.885) |
| (c) median of paired ratios | linux_18_seeds | 0.826 | [0.789, 0.935] | 16 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.782) |
| (d) (a) without hmm_drive_0 | linux_18_seeds | 0.824 | [0.775, 0.880] | 15 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.771) |
| (a) v7 pooled geomean | linux_new_12 | 0.813 | [0.756, 0.864] | 16 | eight_schools-eight_schools_centered (0.868) |
| (b) joint-pass | linux_new_12 | 0.866 | [0.818, 0.889] | 12 | eight_schools-eight_schools_noncentered (0.855) |
| (c) median of paired ratios | linux_new_12 | 0.808 | [0.766, 0.869] | 16 | eight_schools-eight_schools_centered (0.855) |
| (d) (a) without hmm_drive_0 | linux_new_12 | 0.813 | [0.755, 0.869] | 15 | eight_schools-eight_schools_centered (0.872) |
| (a) v7 pooled geomean | linux_wp64_6 | 1.206 | [0.921, 1.468] | 15 | bball_drive_event_0-hmm_drive_0 (0.862) |
| (b) joint-pass | linux_wp64_6 | 0.896 | [0.845, 0.909] | 11 | sblrc-blr (0.919) |
| (c) median of paired ratios | linux_wp64_6 | 1.189 | [0.958, 1.552] | 15 | bball_drive_event_0-hmm_drive_0 (0.850) |
| (d) (a) without hmm_drive_0 | linux_wp64_6 | 0.862 | [0.772, 1.474] | 14 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.793) |
| (a) v7 pooled geomean | windows_6 | 0.761 | [0.712, 1.431] | 15 | eight_schools-eight_schools_centered (0.813) |
| (b) joint-pass | windows_6 | 0.853 | [0.773, 0.944] | 10 | bball_drive_event_0-hmm_drive_0 (0.869) |
| (c) median of paired ratios | windows_6 | 0.773 | [0.740, 1.642] | 15 | eight_schools-eight_schools_centered (0.817) |
| (d) (a) without hmm_drive_0 | windows_6 | 0.749 | [0.707, 1.242] | 14 | eight_schools-eight_schools_centered (0.803) |

Headline rule (frozen): eligible ['a', 'c']; smaller leave-one-model-out max |log| influence wins. Influence: a 0.063, c 0.055. Selected: **(c)**; proposed in advance: (c).

## Per-model ratios, Linux 18 seeds

| model | (a) | (b) | (c) | stuck-chain cells oWALNUTS / CmdStan |
|---|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered | 0.985 | 1.013 | 0.995 | 0/18 / 0/18 |
| eight_schools-eight_schools_centered | 0.345 | — | 0.388 | 0/18 / 0/18 |
| diamonds-diamonds | 0.871 | 0.871 | 0.857 | 0/18 / 0/18 |
| earnings-logearn_interaction | 0.868 | 0.868 | 0.833 | 0/18 / 0/18 |
| mesquite-logmesquite_logvash | 0.876 | 0.876 | 0.896 | 0/18 / 0/18 |
| kidiq-kidscore_momhsiq | 1.005 | 1.005 | 0.959 | 0/18 / 0/18 |
| sblrc-blr | 0.727 | 0.725 | 0.766 | 0/18 / 0/18 |
| nes2000-nes | 0.868 | 0.868 | 0.851 | 0/18 / 0/18 |
| arK-arK | 0.798 | 0.798 | 0.829 | 0/18 / 0/18 |
| garch-garch11 | 0.885 | 0.885 | 0.898 | 0/18 / 0/18 |
| gp_pois_regr-gp_pois_regr | 0.703 | — | 0.677 | 0/18 / 0/18 |
| hmm_example-hmm_example | 0.860 | 0.860 | 0.840 | 0/18 / 0/18 |
| bball_drive_event_0-hmm_drive_0 | 0.785 | 0.835 | 0.966 | 1/18 / 5/18 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 2.112 | — | 1.875 | 0/18 / 0/18 |
| hudson_lynx_hare-lotka_volterra | 0.897 | 0.875 | 0.822 | 0/18 / 2/15 |
| mcycle_gp-accel_gp | 0.477 | — | 0.479 | 0/18 / 0/18 |

## hmm_drive_0: stuck chains per seed (|chain mean - reference mean| > 5 reference sd)

| seed | oWALNUTS | CmdStan |
|---|---:|---:|
| 560561 | 0 | 0 |
| 560562 | 0 | 1 |
| 560563 | 0 | 2 |
| 620601 | 0 | 1 |
| 620602 | 0 | 1 |
| 620603 | 0 | 0 |
| 720701 | 0 | 0 |
| 720702 | 0 | 1 |
| 720703 | 0 | 0 |
| 720704 | 0 | 0 |
| 720705 | 0 | 0 |
| 720706 | 0 | 0 |
| 720707 | 1 | 0 |
| 720708 | 0 | 0 |
| 720709 | 0 | 0 |
| 720710 | 0 | 0 |
| 720711 | 0 | 0 |
| 720712 | 0 | 0 |
| cells with a stuck chain | 1/18 | 5/18 |

## Gates

| arm | new 12 seeds | all 18 seeds |
|---|---:|---:|
| owalnuts | 157/192 | 239/288 |
| cmdstan | 136/192 | 198/288 |

## Predictions

| prediction | value | held |
|---|---|---|
| Q1_b_in_interval | 0.8702106341415067 | True |
| Q2_c_in_interval | 0.8255174483696378 | True |
| Q3_a_above_1_only_because_of_hmm_drive_0 | {'a': 0.8218469882138671, 'd': 0.8243456891105703} | False |
| Q4_rule_selects_c | c | True |
