# WP76 nutpie 18-seed — results

Statistic (c), fixed 16, 18 Linux seeds; 95 % seed-bootstrap interval (10000 resamples). Per-second walls are pinned, co-tenanted (lane 1).

| ratio | value | interval | models | most influential model (value without) |
|---|---:|---|---:|---|
| owalnuts_vs_nutpie_per_gradient | 0.699 | [0.650, 0.962] | 15 | sblrc-blr (0.735) |
| owalnuts_vs_nutpie_per_second | 0.932 | [0.865, 1.275] | 15 | bball_drive_event_0-hmm_drive_0 (0.964) |
| owalnuts_vs_cmdstan_per_gradient | 0.826 | [0.789, 0.931] | 16 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.782) |
| owalnuts_vs_cmdstan_per_second | 0.886 | [0.846, 1.000] | 16 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.840) |
| nutpie_vs_cmdstan_per_gradient | 1.174 | [1.094, 1.287] | 15 | sblrc-blr (1.126) |
| nutpie_vs_cmdstan_per_second | 0.949 | [0.887, 1.050] | 15 | one_comp_mm_elim_abs-one_comp_mm_elim_abs (0.910) |

| arm | gates /288 | recorded | non-ok cells |
|---|---:|---:|---|
| owalnuts | 239 | 288 | — |
| cmdstan | 198 | 288 | error 3 |
| nutpie | 163 | 288 | timeout_or_crash 7 |

| model | oWALNUTS | CmdStan | nutpie | per-grad (c) vs nutpie | per-sec (c) vs nutpie | stuck cells o/c/n |
|---|---:|---:|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered | 18/18 | 10/18 | 2/18 | 0.756 | 1.485 | 0/0/0 |
| eight_schools-eight_schools_centered | 0/18 | 0/18 | 0/18 | 0.607 | 0.821 | 0/0/0 |
| diamonds-diamonds | 18/18 | 18/18 | 2/18 | 1.037 | 1.023 | 0/0/0 |
| earnings-logearn_interaction | 18/18 | 18/18 | 16/18 | 0.686 | 0.839 | 0/0/0 |
| mesquite-logmesquite_logvash | 18/18 | 18/18 | 18/18 | 0.841 | 1.186 | 0/0/0 |
| kidiq-kidscore_momhsiq | 18/18 | 18/18 | 17/18 | 0.734 | 0.961 | 0/0/0 |
| sblrc-blr | 17/18 | 18/18 | 18/18 | 0.342 | 0.662 | 0/0/0 |
| nes2000-nes | 18/18 | 18/18 | 18/18 | 0.732 | 1.053 | 0/0/0 |
| arK-arK | 18/18 | 18/18 | 18/18 | 0.730 | 1.165 | 0/0/0 |
| garch-garch11 | 18/18 | 18/18 | 18/18 | 0.750 | 1.170 | 0/0/0 |
| gp_pois_regr-gp_pois_regr | 14/18 | 0/18 | 0/18 | 0.741 | 0.781 | 0/0/0 |
| hmm_example-hmm_example | 18/18 | 18/18 | 18/18 | 0.634 | 0.779 | 0/0/0 |
| bball_drive_event_0-hmm_drive_0 | 17/18 | 13/18 | 11/18 | 0.484 | 0.584 | 1/5/6 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 10/18 | 0/18 | 0/18 | 1.207 | 1.251 | 0/0/0 |
| hudson_lynx_hare-lotka_volterra | 17/18 | 13/18 | 7/18 | — | — | 0/2/2 |
| mcycle_gp-accel_gp | 2/18 | 0/18 | 0/18 | 0.610 | 0.695 | 0/0/0 |

## hmm_drive_0 stuck chains per seed

| seed | oWALNUTS | CmdStan | nutpie |
|---|---:|---:|---:|
| 560561 | 0 | 0 | 1 |
| 560562 | 0 | 1 | 0 |
| 560563 | 0 | 2 | 2 |
| 620601 | 0 | 1 | 0 |
| 620602 | 0 | 1 | 1 |
| 620603 | 0 | 0 | 1 |
| 720701 | 0 | 0 | 0 |
| 720702 | 0 | 1 | 0 |
| 720703 | 0 | 0 | 0 |
| 720704 | 0 | 0 | 1 |
| 720705 | 0 | 0 | 0 |
| 720706 | 0 | 0 | 0 |
| 720707 | 1 | 0 | 1 |
| 720708 | 0 | 0 | 0 |
| 720709 | 0 | 0 | 0 |
| 720710 | 0 | 0 | 0 |
| 720711 | 0 | 0 | 0 |
| 720712 | 0 | 0 | 0 |
| cells with a stuck chain | 1/18 | 5/18 | 6/18 |

nutpie same-seed repeat vs WP64 (560561-560563): 45/48 identical; pass agreement 47/48

## Predictions

| prediction | value | held |
|---|---|---|
| N1_per_gradient_c_vs_nutpie_in_[1.0,1.4] | 0.6987638328951099 | False |
| N1b_per_gradient_c_vs_nutpie_in_[0.55,0.95] | 0.6987638328951099 | True |
| N2_per_second_c_vs_nutpie_in_[1.2,1.8] | 0.9324193031417858 | False |
| N3_nutpie_gates_below_owalnuts | {'nutpie': 163, 'owalnuts': 239} | True |
