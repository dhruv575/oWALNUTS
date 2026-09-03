# posteriordb benchmark v5 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.03 | 71,955 | 1,779 | 1,478 | 54,292.1 | 46,137.4 | 24.720 | 1.0017 | 0,0,0 | 1.39 |
| eight_schools-eight_schools_noncentered | cmdstan | 3/3 | 0.15 | 75,347 | 2,448 | 1,913 | 13,611.4 | 11,006.7 | 32.978 | 1.0015 | 0,0,0 | 1.49 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.15 | 55,456 | 2,358 | 1,930 | 13,750.8 | 11,189.8 | 42.744 | 1.0018 | 2,3,1 | 1.29 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.09 | 214,349 | 75 | 136 | 890.3 | 1,621.0 | 0.349 | 1.0399 | 0,0,0 | 1.31 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.17 | 181,319 | 54 | 16 | 160.9 | 94.0 | 0.296 | 1.0598 | 43,120,280 | 0.88 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0.22 | 100,551 | 103 | 53 | 469.2 | 239.0 | 1.027 | 1.0496 | 175,32,13 | 2.86 |
| diamonds-diamonds | owalnuts-da | 3/3 | 69.57 | 6,609,452 | 1,265 | 1,641 | 18.4 | 24.7 | 0.191 | 1.0053 | 0,0,0 | 2.29 |
| diamonds-diamonds | cmdstan | 3/3 | 68.13 | 6,482,127 | 1,474 | 1,988 | 21.6 | 29.2 | 0.227 | 1.0025 | 0,0,0 | 1.83 |
| diamonds-diamonds | nutpie | 0/3 | 23.75 | 2,112,915 | 347 | 573 | 14.2 | 23.1 | 0.162 | 1.0112 | 0,0,0 | 1.69 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 16.03 | 1,563,425 | 1,043 | 1,121 | 62.7 | 72.3 | 0.582 | 1.0029 | 0,0,0 | 1.52 |
| earnings-logearn_interaction | cmdstan | 3/3 | 11.49 | 1,321,447 | 1,156 | 1,288 | 98.5 | 114.8 | 0.870 | 1.0041 | 0,0,0 | 0.81 |
| earnings-logearn_interaction | nutpie | 3/3 | 7.78 | 740,616 | 706 | 873 | 88.1 | 108.8 | 0.954 | 1.0081 | 0,0,0 | 0.57 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.29 | 380,236 | 1,389 | 1,643 | 4,762.9 | 5,780.8 | 3.601 | 1.0026 | 0,0,0 | 1.63 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.31 | 364,840 | 1,471 | 1,811 | 4,414.5 | 5,819.1 | 3.983 | 1.0034 | 0,0,0 | 1.25 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.48 | 197,188 | 853 | 1,083 | 1,796.7 | 2,229.5 | 4.237 | 1.0052 | 0,0,0 | 1.87 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 0.85 | 373,268 | 1,441 | 1,695 | 1,616.6 | 1,978.8 | 3.731 | 1.0029 | 0,0,0 | 1.07 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 0.87 | 360,241 | 1,521 | 1,792 | 1,749.2 | 2,216.7 | 4.043 | 1.0025 | 0,0,0 | 0.98 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 0.55 | 137,376 | 857 | 1,171 | 1,610.4 | 2,198.7 | 6.170 | 1.0040 | 0,0,0 | 1.34 |
| sblrc-blr | owalnuts-da | 3/3 | 0.08 | 142,661 | 820 | 1,103 | 9,978.6 | 13,423.4 | 5.748 | 1.0050 | 0,0,0 | 1.47 |
| sblrc-blr | cmdstan | 2/3 | 0.19 | 128,761 | 811 | 1,133 | 4,352.6 | 6,082.3 | 6.593 | 1.0045 | 0,0,0 | 1.69 |
| sblrc-blr | nutpie | 3/3 | 0.11 | 56,547 | 885 | 1,384 | 7,218.2 | 11,699.1 | 15.602 | 1.0028 | 0,0,0 | 0.78 |
| nes2000-nes | owalnuts-da | 3/3 | 3.43 | 422,166 | 1,785 | 1,980 | 520.6 | 585.2 | 4.239 | 1.0038 | 0,0,0 | 1.21 |
| nes2000-nes | cmdstan | 3/3 | 3.23 | 393,895 | 1,984 | 2,243 | 611.0 | 711.7 | 4.973 | 1.0024 | 0,0,0 | 1.51 |
| nes2000-nes | nutpie | 3/3 | 2.32 | 238,098 | 1,398 | 1,868 | 587.2 | 782.7 | 5.859 | 1.0025 | 0,0,0 | 1.14 |
| arK-arK | owalnuts-da | 3/3 | 1.05 | 277,002 | 2,467 | 2,236 | 2,288.8 | 2,027.3 | 8.739 | 1.0023 | 0,0,0 | 1.87 |
| arK-arK | cmdstan | 3/3 | 1.23 | 244,474 | 2,639 | 2,233 | 2,149.4 | 1,873.9 | 10.794 | 1.0024 | 0,0,0 | 1.21 |
| arK-arK | nutpie | 3/3 | 7.28 | 174,709 | 2,005 | 2,003 | 283.5 | 259.2 | 11.492 | 1.0024 | 0,0,0 | 1.24 |
| arma-arma11 | owalnuts-da | 3/3 | 1.80 | 281,622 | 3,791 | 2,743 | 2,228.5 | 1,507.3 | 14.273 | 1.0011 | 0,0,0 | 0.67 |
| arma-arma11 | cmdstan | 1/3 | 0.19 | 46,066 | 7 | 1,500 | 42.7 | 8,924.9 | 0.201 | 1.5264 | 0,258,0 | 1.17 |
| arma-arma11 | nutpie | 1/3 | 1.10 | 30,092 | 7 | 4 | 6.5 | 3.7 | 0.278 | 1.5266 | 477,515,0 | 1.16 |
| garch-garch11 | owalnuts-da | 3/3 | 0.36 | 94,853 | 1,786 | 1,873 | 4,922.8 | 5,146.2 | 19.202 | 1.0025 | 0,0,0 | 1.93 |
| garch-garch11 | cmdstan | 3/3 | 0.45 | 89,994 | 2,015 | 1,946 | 3,916.0 | 4,390.9 | 22.321 | 1.0021 | 0,0,0 | 1.11 |
| garch-garch11 | nutpie | 3/3 | 2.23 | 61,461 | 1,594 | 1,523 | 715.5 | 683.5 | 25.609 | 1.0033 | 0,0,0 | 0.76 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 3/3 | 1.58 | 1,120,332 | 856 | 986 | 540.7 | 604.8 | 0.751 | 1.0060 | 0,0,0 | 2.88 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 1.80 | 1,315,607 | 1,266 | 1,856 | 748.8 | 1,137.5 | 0.995 | 1.0028 | 22,6,12 | 2.05 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 1.98 | 781,862 | 381 | 182 | 192.0 | 91.6 | 0.487 | 1.0098 | 206,142,755 | 2.16 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 1.38 | 141,887 | 2,259 | 2,094 | 1,596.0 | 1,636.9 | 15.506 | 1.0016 | 0,0,0 | 2.07 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.03 | 96,549 | 2,051 | 2,014 | 1,980.8 | 1,958.4 | 21.238 | 1.0008 | 0,0,0 | 1.19 |
| hmm_example-hmm_example | nutpie | 3/3 | 8.60 | 56,011 | 1,592 | 1,732 | 185.9 | 196.3 | 28.332 | 1.0032 | 0,0,0 | 1.20 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 6.52 | 100,495 | 4,024 | 1,894 | 497.6 | 232.5 | 37.607 | 1.0041 | 0,0,0 | 1.21 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 3.63 | 60,424 | 3,111 | 1,517 | 522.3 | 254.7 | 39.881 | 1.0025 | 414,0,0 | 1.21 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 3/3 | 12.66 | 39,557 | 4,110 | 1,684 | 254.8 | 133.0 | 95.105 | 1.0021 | 0,0,0 | 1.45 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 1/3 | 13.51 | 78,976 | 800 | 364 | 59.2 | 26.9 | 10.131 | 1.0068 | 0,0,0 | 1.89 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 1/3 | 13.47 | 71,351 | 765 | 415 | 56.8 | 30.8 | 10.716 | 1.0083 | 146,0,3 | 1.04 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 33.86 | 51,477 | 1,142 | 594 | 34.2 | 17.8 | 22.184 | 1.0030 | 1,5,18 | 6.69 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 3/3 | 7.70 | 287,343 | 901 | 1,280 | 117.0 | 166.9 | 3.136 | 1.0062 | 0,0,0 | 1.40 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 7.30 | 272,760 | 1,003 | 1,400 | 135.1 | 191.8 | 3.561 | 1.0019 | 0,0,0 | 1.31 |
| hudson_lynx_hare-lotka_volterra | nutpie | timeout_or_crash | — | — | — | — | — | — | — | — |  | — |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 16.04 | 2,925,193 | 359 | 137 | 22.0 | 9.5 | 0.118 | 1.0163 | 0,0,0 | 2.44 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 26.16 | 5,896,464 | 1,470 | 959 | 57.8 | 36.7 | 0.251 | 1.0054 | 80,37,68 | 2.63 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 46.95 | 3,549,989 | 600 | 401 | 11.4 | 7.6 | 0.165 | 1.0070 | 114,209,108 | 2.61 |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |
|---|---:|---:|---:|---:|---:|---:|---|
| owalnuts-da_over_cmdstan | 17 | 1.069 | 1.401 | 0.801 | 8 | 2 | eight_schools-eight_schools_centered, arma-arma11 |
| owalnuts-da_over_nutpie | 16 | 0.841 | 3.085 | 0.273 | 14 | 3 | diamonds-diamonds, arma-arma11, gp_pois_regr-gp_pois_regr |

## Per-model final steps and depth caps (owalnuts-da; per seed)

| model | final step per chain (seed 1 / 2 / 3) | depth caps per seed | divergences per seed |
|---|---|---|---|
| eight_schools-eight_schools_noncentered | [0.518, 0.386, 0.491, 0.517] / [0.375, 0.472, 0.526, 0.485] / [0.52, 0.34, 0.438, 0.413] | 0,0,0 | 0,0,0 |
| eight_schools-eight_schools_centered | [0.257, 0.224, 0.102, 0.0756] / [0.208, 0.195, 0.257, 0.159] / [0.202, 0.212, 0.267, 0.311] | 0,0,0 | 0,0,0 |
| diamonds-diamonds | [0.00398, 0.00469, 0.00371, 0.00332] / [0.00339, 0.00308, 0.00398, 0.0031] / [0.00399, 0.00356, 0.00342, 0.00383] | 246,539,285 | 0,0,0 |
| earnings-logearn_interaction | [0.013, 0.016, 0.0152, 0.0158] / [0.0138, 0.0174, 0.0175, 0.0152] / [0.0177, 0.0177, 0.0151, 0.0138] | 0,0,0 | 0,0,0 |
| mesquite-logmesquite_logvash | [0.0896, 0.0701, 0.067, 0.0839] / [0.0821, 0.0672, 0.0817, 0.0696] / [0.0787, 0.0745, 0.0742, 0.0696] | 0,0,0 | 0,0,0 |
| kidiq-kidscore_momhsiq | [0.111, 0.104, 0.0946, 0.108] / [0.0952, 0.0997, 0.113, 0.0859] / [0.102, 0.116, 0.0924, 0.0978] | 0,0,0 | 0,0,0 |
| sblrc-blr | [0.109, 0.103, 0.0981, 0.117] / [0.109, 0.102, 0.0903, 0.107] / [0.112, 0.115, 0.0977, 0.102] | 0,0,0 | 0,0,0 |
| nes2000-nes | [0.091, 0.0889, 0.0702, 0.0767] / [0.0901, 0.0697, 0.0854, 0.0827] / [0.0807, 0.0781, 0.0717, 0.0767] | 0,0,0 | 0,0,0 |
| arK-arK | [0.118, 0.102, 0.131, 0.109] / [0.105, 0.113, 0.119, 0.0995] / [0.114, 0.114, 0.122, 0.108] | 0,0,0 | 0,0,0 |
| arma-arma11 | [0.705, 0.701, 0.7, 0.743] / [0.665, 0.635, 0.856, 0.769] / [0.793, 0.654, 0.61, 0.635] | 0,0,0 | 0,0,0 |
| garch-garch11 | [0.269, 0.296, 0.326, 0.333] / [0.274, 0.331, 0.321, 0.338] / [0.273, 0.339, 0.275, 0.374] | 0,0,0 | 0,0,0 |
| gp_pois_regr-gp_pois_regr | [0.0307, 0.0267, 0.0304, 0.0285] / [0.0318, 0.0333, 0.0294, 0.0321] / [0.0322, 0.0301, 0.0307, 0.026] | 0,0,0 | 0,0,0 |
| hmm_example-hmm_example | [0.277, 0.305, 0.317, 0.293] / [0.32, 0.285, 0.311, 0.319] / [0.274, 0.261, 0.291, 0.289] | 0,0,0 | 0,0,0 |
| bball_drive_event_0-hmm_drive_0 | [0.667, 0.602, 0.627, 0.671] / [0.613, 0.372, 0.65, 0.577] / [0.71, 0.679, 0.611, 0.649] | 0,0,0 | 0,0,0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | [0.313, 0.342, 0.281, 0.445] / [0.372, 0.337, 0.433, 0.388] / [0.41, 0.459, 0.593, 0.441] | 0,0,0 | 0,0,0 |
| hudson_lynx_hare-lotka_volterra | [0.103, 0.112, 0.113, 0.116] / [0.12, 0.0903, 0.117, 0.129] / [0.116, 0.115, 0.091, 0.108] | 0,0,0 | 0,0,0 |
| mcycle_gp-accel_gp | [0.00651, 0.00871, 0.00709, 0.00886] / [0.00939, 0.00825, 0.00777, 0.00579] / [0.00911, 0.00755, 0.00927, 0.00881] | 1,0,0 | 0,0,0 |

## v5 versus v3 (seed medians; ratio v5 / v3; same protocol, competitor versions and settings, seeds 79101-79103 -> 87101-87103; the only sampler change is the post-WP31 default pair in the DA arm; cmdstan and nutpie differ by seed noise)

| model | arm | v3 gates | v5 gates | v3 ESS/grad x1e3 | v5 ESS/grad x1e3 | ESS/grad v5/v3 | ESS/s v5/v3 | wall v5/v3 | grads v5/v3 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 3/3 | 29.107 | 24.720 | 0.85 | 0.88 | 1.12 | 1.03 |
| eight_schools-eight_schools_noncentered | cmdstan | 2/3 | 3/3 | 33.756 | 32.978 | 0.98 | 1.01 | 0.80 | 1.04 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 39.111 | 42.744 | 1.09 | 1.45 | 0.78 | 0.99 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0/3 | 0.231 | 0.349 | 1.51 | 1.85 | 1.13 | 1.35 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 1.074 | 0.296 | 0.28 | 0.27 | 0.90 | 1.09 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 0.901 | 1.027 | 1.14 | 1.68 | 0.64 | 0.88 |
| diamonds-diamonds | owalnuts-da | 3/3 | 3/3 | 0.156 | 0.191 | 1.23 | 1.67 | 0.96 | 1.30 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.219 | 0.227 | 1.04 | 1.18 | 0.89 | 1.01 |
| diamonds-diamonds | nutpie | 1/3 | 0/3 | 0.194 | 0.162 | 0.84 | 0.99 | 0.87 | 1.03 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 3/3 | 0.177 | 0.582 | 3.28 | 3.52 | 0.32 | 0.31 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.756 | 0.870 | 1.15 | 1.26 | 0.85 | 0.99 |
| earnings-logearn_interaction | nutpie | 3/3 | 3/3 | 0.903 | 0.954 | 1.06 | 1.22 | 0.86 | 1.01 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 3/3 | 3.030 | 3.601 | 1.19 | 1.36 | 1.02 | 1.16 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 3.431 | 3.983 | 1.16 | 1.50 | 0.71 | 0.96 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.342 | 4.237 | 0.98 | 1.35 | 0.68 | 0.99 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 3/3 | 2.163 | 3.731 | 1.73 | 2.43 | 0.63 | 0.85 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 4.498 | 4.043 | 0.90 | 1.43 | 0.78 | 1.03 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 3/3 | 6.118 | 6.170 | 1.01 | 1.42 | 0.74 | 0.99 |
| sblrc-blr | owalnuts-da | 0/3 | 3/3 | 0.413 | 5.748 | 13.92 | 20.36 | 0.19 | 0.26 |
| sblrc-blr | cmdstan | 3/3 | 2/3 | 6.583 | 6.593 | 1.00 | 0.98 | 1.00 | 1.05 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 13.734 | 15.602 | 1.14 | 1.61 | 0.61 | 1.00 |
| nes2000-nes | owalnuts-da | 3/3 | 3/3 | 2.499 | 4.239 | 1.70 | 2.09 | 0.80 | 1.00 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.925 | 4.973 | 1.01 | 1.32 | 0.84 | 0.99 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.704 | 5.859 | 1.03 | 1.33 | 0.76 | 1.01 |
| arK-arK | owalnuts-da | 3/3 | 3/3 | 7.752 | 8.739 | 1.13 | 1.51 | 0.81 | 1.18 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.404 | 10.794 | 1.04 | 1.37 | 0.89 | 1.00 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.372 | 11.492 | 1.01 | 1.30 | 0.82 | 1.01 |
| arma-arma11 | owalnuts-da | 2/3 | 3/3 | 14.020 | 14.273 | 1.02 | 0.42 | 5.91 | 2.42 |
| arma-arma11 | cmdstan | 2/3 | 1/3 | 72.040 | 0.201 | 0.00 | 0.00 | 0.65 | 0.85 |
| arma-arma11 | nutpie | 3/3 | 1/3 | 133.017 | 0.278 | 0.00 | 0.00 | 0.48 | 0.83 |
| garch-garch11 | owalnuts-da | 3/3 | 3/3 | 15.021 | 19.202 | 1.28 | 1.55 | 1.07 | 1.32 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 20.860 | 22.321 | 1.07 | 1.40 | 0.74 | 0.98 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 25.822 | 25.609 | 0.99 | 1.54 | 0.71 | 1.00 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 3/3 | 0.731 | 0.751 | 1.03 | 1.34 | 0.81 | 1.04 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 1.073 | 0.995 | 0.93 | 1.40 | 0.76 | 1.00 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 0.883 | 0.487 | 0.55 | 0.90 | 0.60 | 0.99 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 3/3 | 9.767 | 15.506 | 1.59 | 1.78 | 0.64 | 0.72 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 20.948 | 21.238 | 1.01 | 1.37 | 0.68 | 0.97 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 27.713 | 28.332 | 1.02 | 1.44 | 0.71 | 0.99 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 1/3 | 2/3 | 0.281 | 37.607 | 133.62 | 108.32 | 1.14 | 1.12 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 3/3 | 2/3 | 64.579 | 39.881 | 0.62 | 0.66 | 0.66 | 0.94 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 3/3 | 3/3 | 67.016 | 95.105 | 1.42 | 2.07 | 0.61 | 0.96 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 1/3 | 9.076 | 10.131 | 1.12 | 1.46 | 1.01 | 1.29 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 1/3 | 12.837 | 10.716 | 0.83 | 1.27 | 0.80 | 1.02 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 4.658 | 22.184 | 4.76 | 7.46 | 0.73 | 1.03 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 3/3 | 3/3 | 3.306 | 3.136 | 0.95 | 1.53 | 0.59 | 1.03 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 3/3 | 3.479 | 3.561 | 1.02 | 1.66 | 0.68 | 0.99 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 0/3 | — | — | — | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 0/3 | 0.069 | 0.118 | 1.71 | 2.00 | 1.95 | 2.27 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.210 | 0.251 | 1.19 | 1.58 | 0.79 | 1.05 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.194 | 0.165 | 0.85 | 1.15 | 0.66 | 0.98 |

| arm | v3 cells passed | v5 cells passed | geomean ESS/grad v5/v3 | geomean ESS/s v5/v3 | geomean grads v5/v3 |
|---|---:|---:|---:|---:|---:|
| owalnuts-da | 35 | 42 | 2.01 | 2.31 | 1.02 |
| cmdstan | 37 | 36 | 0.65 | 0.81 | 0.99 |
| nutpie | 31 | 28 | 0.74 | 1.04 | 0.98 |

| v5 owalnuts-da against the v3 competitor medians (orientation; WP31 cited these) | models | ESS/grad ratio | ESS/s ratio |
|---|---:|---:|---:|
| owalnuts-da_over_v3_cmdstan | 17 | 0.692 | 1.137 |
| owalnuts-da_over_v3_nutpie | 16 | 0.624 | 3.199 |

## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed

| seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | target calls | divergences | retained exhaustions | final steps |
|---|---:|---:|---:|---|---:|---:|---:|---|
| 87101 | 0.0571 | +1.02 | +1.08 | 571 / 1.005 | 4,049,144 | 0 | 0 | 0.107, 0.0482, 0.0976, 0.146 |
| 87102 | 0.0474 | -0.05 | -0.05 | 639 / 1.006 | 3,466,793 | 0 | 7 | 0.0649, 0.114, 0.0729, 0.187 |
| 87103 | 0.0578 | +0.93 | +1.11 | 274 / 1.010 | 9,072,925 | 0 | 6 | 0.00132, 0.0217, 0.0444, 0.135 |
| pooled (batch means) | 0.0541 | — | +1.34 | — | — | — | — | — |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_da_gate_passes_ge_39_of_51 | 42 | True |
| P2_da_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.45_over_17 | 1.069 | True |
| P3_da_geomean_bulk_ess_per_second_vs_nutpie_ge_1.5 | 3.085 | True |
| P4_da_geomean_wall_per_gradient_le_1.0x_cmdstan | 0.801 | True |
| P5_funnel_defaults_abs_z_le_2_every_seed | [1.0207972314331428, -0.050834939161407536, 0.9262058118993653] | True |
| reported_da_v5_over_v3_geomean_bulk_ess_per_gradient | 2.012 | reported |
| reported_da_models_below_0.8x_v3 | {} | reported |
| reported_da_models_above_1.2x_v3 | {'eight_schools-eight_schools_centered': 1.5112719213342254, 'diamonds-diamonds': 1.2293864923733986, 'earnings-logearn_interaction': 3.2819576649667033, 'kidiq-kidscore_momhsiq': 1.7250260997468332, 'sblrc-blr': 13.92388712005818, 'nes2000-nes': 1.696062293971141, 'garch-garch11': 1.2783313487261256, 'hmm_example-hmm_example': 1.5875623520180142, 'bball_drive_event_0-hmm_drive_0': 133.62022097644692, 'mcycle_gp-accel_gp': 1.7079749853075923} | reported |
| reported_competitor_v5_over_v3_geomean_bulk_ess_per_gradient | {'cmdstan': 0.6477101039521255, 'nutpie': 0.7424868044797849} | reported |
| reported_da_frozen_cells | [] | reported |
| reported_owalnuts_cells_not_ok | [] | reported |
