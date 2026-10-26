# WP77 results

Seeds [770771, 770772, 770773, 770774, 770775, 770776]; 4 chains x 1,000 draws, warmup per arm (default 1,000, half 500, init25 1,000); funnel 4 x 2000 draws x 30 seeds; pinned to cores 4-7, co-tenanted.

Default passes 87/102 (CmdStan 74); default retained divergences 0; default max passing |z| 5.39 (one_comp_mm_elim_abs-one_comp_mm_elim_abs/770773).
Default vs CmdStan (WP72 form): per total gradient 0.791, per sampling gradient 0.829.

## Rules

| candidate | G passes vs default | H headline (>= 1.15) [95 % seed bootstrap] | M per-model median (>= 1.10) | L LOMO min (>= 1.05) | D new divergences | Z max passing abs z (<= 4) | F funnel P5 ± s.e. | proposes default |
|---|---|---|---|---|---|---|---|---|
| owalnuts-half | 81 vs 87 (False) | 1.119 [0.861, 1.224] (False) | 1.180 (True) | 1.098 w/o eight_schools-eight_schools_centered (True) | 0 (True) | 3.38 kidiq-kidscore_momhsiq/770773 (True) | 0.0487 ± 0.0048 (True) | **False** |
| owalnuts-init25 | 87 vs 87 (True) | 1.016 [0.914, 1.151] (False) | 0.988 (False) | 0.980 w/o bball_drive_event_0-hmm_drive_0 (False) | 0 (True) | 5.85 one_comp_mm_elim_abs-one_comp_mm_elim_abs/770775 (False) | 0.0530 ± 0.0051 (False) | **False** |

## Reported

| candidate | per sampling gradient headline / median / LOMO min | vs CmdStan per total gradient | vs CmdStan per sampling gradient | total grads | warmup grads | min bulk ESS | divergences |
|---|---|---:|---:|---:|---:|---:|---:|
| owalnuts-half | 0.875 / 0.936 / 0.852 | 0.889 | 0.739 | 0.799 | 0.580 | 0.947 | 0 |
| owalnuts-init25 | 1.047 / 0.998 / 0.981 | 0.832 | 0.876 | 0.990 | 0.985 | 0.960 | 0 |

## Per model (median of paired per-seed ratios vs default, per total gradient; passes of 6)

| model | default passes | owalnuts-half ratio | owalnuts-half per sampling grad | owalnuts-half passes | owalnuts-init25 ratio | owalnuts-init25 per sampling grad | owalnuts-init25 passes |
|---|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 6 | 1.442 | 1.084 | 6 | 1.104 | 1.130 | 6 |
| eight_schools-eight_schools_centered | 0 | 1.510 | 1.349 | 0 | 0.802 | 0.715 | 0 |
| diamonds-diamonds | 6 | 1.202 | 0.936 | 6 | 1.000 | 1.014 | 6 |
| earnings-logearn_interaction | 6 | 1.096 | 0.819 | 5 | 0.988 | 1.026 | 6 |
| mesquite-logmesquite_logvash | 6 | 1.318 | 0.996 | 6 | 0.928 | 0.948 | 6 |
| kidiq-kidscore_momhsiq | 6 | 1.180 | 0.968 | 6 | 0.910 | 0.948 | 6 |
| sblrc-blr | 6 | 0.896 | 0.649 | 6 | 0.993 | 1.009 | 6 |
| nes2000-nes | 6 | 1.277 | 1.036 | 6 | 0.956 | 0.971 | 6 |
| arK-arK | 6 | 1.180 | 0.916 | 6 | 0.989 | 0.977 | 6 |
| arma-arma11 | 6 | 1.134 | 0.925 | 6 | 1.036 | 0.998 | 6 |
| garch-garch11 | 6 | 1.233 | 0.958 | 6 | 0.977 | 0.949 | 6 |
| gp_pois_regr-gp_pois_regr | 6 | 1.387 | 1.082 | 6 | 1.070 | 1.045 | 6 |
| hmm_example-hmm_example | 6 | 1.193 | 0.969 | 6 | 0.977 | 0.942 | 6 |
| bball_drive_event_0-hmm_drive_0 | 6 | 0.356 | 0.287 | 3 | 1.817 | 2.938 | 5 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 3 | 1.019 | 0.784 | 2 | 1.170 | 1.181 | 4 |
| hudson_lynx_hare-lotka_volterra | 6 | 1.164 | 0.895 | 5 | 0.887 | 0.911 | 5 |
| mcycle_gp-accel_gp | 0 | 1.145 | 0.831 | 0 | 0.949 | 1.020 | 1 |

## Funnel (P(omega < -5), exact 0.0478)

| arm | seeds | pooled P5 | s.e. | t | within 1 s.e. | warmup lengths |
|---|---:|---:|---:|---:|---|---|
| default | 30 | 0.0513 | 0.0060 | +0.58 | True | [1000] |
| half | 30 | 0.0487 | 0.0048 | +0.18 | True | [500] |
| init25 | 30 | 0.0530 | 0.0051 | +1.03 | False | [1000] |
