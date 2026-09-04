# posteriordb benchmark v6 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.03 | 72,171 | 2,109 | 1,667 | 62,631.1 | 49,689.2 | 29.948 | 1.0023 | 0,0,0 | 1.31 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 0.17 | 75,417 | 2,210 | 2,012 | 11,954.0 | 7,964.0 | 29.304 | 1.0015 | 0,2,1 | 2.39 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.06 | 55,569 | 2,481 | 1,774 | 41,573.5 | 29,327.3 | 44.654 | 1.0013 | 2,3,4 | 1.55 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.14 | 258,830 | 76 | 57 | 516.5 | 484.6 | 0.281 | 1.0440 | 3,0,0 | 1.28 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.21 | 192,060 | 230 | 276 | 754.9 | 759.9 | 1.210 | 1.0168 | 42,42,36 | 3.59 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0.07 | 106,468 | 97 | 55 | 1,489.9 | 854.3 | 0.948 | 1.0392 | 22,53,41 | 3.47 |
| diamonds-diamonds | owalnuts-da | 3/3 | 86.87 | 6,564,995 | 1,118 | 1,690 | 12.8 | 19.5 | 0.171 | 1.0043 | 0,0,0 | 2.16 |
| diamonds-diamonds | cmdstan | 3/3 | 86.00 | 6,444,046 | 1,481 | 2,103 | 16.5 | 22.3 | 0.229 | 1.0032 | 0,0,0 | 1.96 |
| diamonds-diamonds | nutpie | 2/3 | 27.29 | 2,110,327 | 413 | 605 | 15.0 | 22.6 | 0.196 | 1.0084 | 0,0,0 | 1.99 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 20.97 | 1,811,264 | 1,057 | 1,333 | 46.7 | 63.6 | 0.588 | 1.0035 | 0,0,0 | 0.88 |
| earnings-logearn_interaction | cmdstan | 3/3 | 13.00 | 1,308,211 | 1,009 | 1,096 | 74.5 | 78.2 | 0.756 | 1.0047 | 0,0,0 | 1.03 |
| earnings-logearn_interaction | nutpie | 3/3 | 7.33 | 736,687 | 696 | 912 | 95.6 | 125.2 | 0.960 | 1.0057 | 0,0,0 | 0.56 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.35 | 385,511 | 1,223 | 1,624 | 3,545.4 | 4,528.0 | 3.183 | 1.0022 | 0,0,0 | 1.41 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.44 | 369,468 | 1,376 | 1,680 | 3,105.2 | 3,789.0 | 3.724 | 1.0045 | 0,0,0 | 1.22 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.21 | 194,717 | 799 | 1,010 | 3,615.2 | 4,894.8 | 4.028 | 1.0050 | 0,0,0 | 1.34 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.27 | 368,716 | 1,517 | 1,784 | 1,159.3 | 1,402.0 | 4.067 | 1.0036 | 0,0,0 | 2.06 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 1.46 | 365,900 | 1,344 | 1,492 | 974.3 | 1,059.7 | 3.854 | 1.0014 | 0,0,0 | 2.71 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 0.41 | 139,929 | 900 | 1,123 | 2,317.6 | 2,892.0 | 6.430 | 1.0051 | 0,0,0 | 2.34 |
| sblrc-blr | owalnuts-da | 2/3 | 0.12 | 146,089 | 744 | 1,067 | 6,041.8 | 8,787.7 | 5.084 | 1.0049 | 0,0 | 1.33 |
| sblrc-blr | cmdstan | 3/3 | 0.18 | 124,635 | 743 | 1,135 | 3,988.4 | 6,363.7 | 6.035 | 1.0038 | 0,0,0 | 1.48 |
| sblrc-blr | nutpie | 3/3 | 0.07 | 55,976 | 999 | 1,370 | 14,001.5 | 18,125.1 | 17.850 | 1.0027 | 0,0,0 | 0.65 |
| nes2000-nes | owalnuts-da | 3/3 | 4.54 | 420,395 | 1,936 | 1,932 | 410.9 | 425.4 | 4.528 | 1.0024 | 0,0,0 | 1.60 |
| nes2000-nes | cmdstan | 3/3 | 4.32 | 395,149 | 1,836 | 2,060 | 419.0 | 470.2 | 4.710 | 1.0026 | 0,0,0 | 1.79 |
| nes2000-nes | nutpie | 3/3 | 2.35 | 237,402 | 1,375 | 1,463 | 581.3 | 628.4 | 5.742 | 1.0028 | 0,0,0 | 2.08 |
| arK-arK | owalnuts-da | 3/3 | 2.25 | 277,661 | 2,296 | 2,359 | 1,011.3 | 1,046.5 | 8.334 | 1.0026 | 0,0,0 | 1.80 |
| arK-arK | cmdstan | 3/3 | 1.77 | 248,391 | 2,551 | 2,336 | 1,419.9 | 1,327.5 | 10.269 | 1.0019 | 0,0,0 | 1.62 |
| arK-arK | nutpie | 3/3 | 1.33 | 174,424 | 2,065 | 2,015 | 1,548.8 | 1,527.9 | 11.947 | 1.0020 | 0,0,0 | 0.62 |
| arma-arma11 | owalnuts-da | 3/3 | 0.89 | 188,805 | 3,740 | 2,635 | 4,332.6 | 3,052.8 | 20.356 | 1.0021 | 0,0,0 | 0.96 |
| arma-arma11 | cmdstan | 1/3 | 12.50 | 1,820,123 | 7 | 4 | 0.6 | 0.3 | 0.004 | 1.5256 | 0,0,0 | 1.16 |
| arma-arma11 | nutpie | 2/3 | 0.15 | 31,411 | 4,777 | 3,270 | 30,903.2 | 21,152.2 | 152.072 | 1.0023 | 0,0,0 | 1.40 |
| garch-garch11 | owalnuts-da | 3/3 | 0.48 | 96,538 | 1,690 | 1,607 | 3,544.3 | 3,370.3 | 17.503 | 1.0023 | 0,0,0 | 1.19 |
| garch-garch11 | cmdstan | 3/3 | 0.56 | 89,558 | 1,945 | 1,880 | 3,335.2 | 3,094.5 | 21.713 | 1.0029 | 0,0,0 | 0.98 |
| garch-garch11 | nutpie | 3/3 | 0.50 | 62,188 | 1,448 | 1,771 | 2,950.0 | 3,447.9 | 23.279 | 1.0020 | 0,0,0 | 1.33 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 3/3 | 2.23 | 1,179,461 | 844 | 971 | 377.5 | 397.4 | 0.718 | 1.0036 | 0,0,0 | 2.09 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 2.21 | 1,290,281 | 1,348 | 1,892 | 568.3 | 857.5 | 1.042 | 1.0023 | 5,6,2 | 1.35 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 1.42 | 785,955 | 527 | 349 | 380.9 | 252.1 | 0.680 | 1.0053 | 182,191,124 | 2.02 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 1.34 | 121,212 | 2,432 | 1,647 | 1,597.3 | 1,111.9 | 19.193 | 1.0021 | 0,0,0 | 1.35 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.72 | 99,314 | 1,968 | 1,812 | 1,142.6 | 1,195.9 | 19.814 | 1.0020 | 0,0,0 | 1.69 |
| hmm_example-hmm_example | nutpie | 3/3 | 1.00 | 56,102 | 1,546 | 1,766 | 1,544.1 | 1,761.8 | 27.586 | 1.0025 | 0,0,0 | 1.45 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 3/3 | 4.93 | 82,475 | 3,774 | 1,853 | 673.0 | 298.2 | 42.047 | 1.0029 | 0,0,0 | 1.73 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 5.48 | 68,420 | 2,904 | 1,215 | 313.4 | 131.1 | 34.457 | 1.0040 | 0,0,2 | 1.23 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 1/3 | 3.45 | 39,845 | 17 | 12 | 5.4 | 3.6 | 0.440 | 1.1552 | 0,467,327 | 1.08 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 3/3 | 22.91 | 79,054 | 1,064 | 492 | 53.1 | 25.1 | 13.579 | 1.0045 | 0,0,0 | 2.43 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 17.69 | 72,639 | 586 | 290 | 35.2 | 14.7 | 8.166 | 1.0084 | 11,2,15 | 0.86 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 14.22 | 51,381 | 950 | 492 | 66.8 | 34.6 | 18.490 | 1.0046 | 16,19,7 | 4.85 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 3/3 | 11.46 | 307,499 | 958 | 1,450 | 79.9 | 116.9 | 3.075 | 1.0023 | 0,0,0 | 1.18 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 8.00 | 271,555 | 1,018 | 1,358 | 117.0 | 168.1 | 3.700 | 1.0041 | 0,0,0 | 1.17 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 6.36 | 145,763 | 428 | 679 | 67.4 | 106.8 | 2.939 | 1.0070 | 38 | 1.23 |
| mcycle_gp-accel_gp | owalnuts-da | 1/3 | 18.65 | 2,937,877 | 695 | 451 | 31.8 | 24.2 | 0.232 | 1.0101 | 0,0,0 | 3.16 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 30.80 | 5,576,148 | 1,447 | 1,527 | 40.2 | 39.8 | 0.242 | 1.0034 | 57,84,42 | 2.76 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 21.65 | 3,612,964 | 612 | 539 | 28.7 | 24.2 | 0.173 | 1.0061 | 131,110,144 | 2.37 |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |
|---|---:|---:|---:|---:|---:|---:|---|
| owalnuts-da_over_cmdstan | 16 | 1.462 | 1.865 | 0.815 | 8 | 5 | eight_schools-eight_schools_noncentered, kidiq-kidscore_momhsiq, arma-arma11, bball_drive_event_0-hmm_drive_0, one_comp_mm_elim_abs-one_comp_mm_elim_abs |
| owalnuts-da_over_nutpie | 15 | 0.900 | 0.996 | 0.877 | 5 | 3 | bball_drive_event_0-hmm_drive_0, mcycle_gp-accel_gp |

## Per-model final steps and depth caps (owalnuts-da; per seed)

| model | final step per chain (seed 1 / 2 / 3) | depth caps per seed | divergences per seed |
|---|---|---|---|
| eight_schools-eight_schools_noncentered | [0.357, 0.456, 0.562, 0.433] / [0.494, 0.491, 0.397, 0.496] / [0.506, 0.441, 0.39, 0.57] | 0,0,0 | 0,0,0 |
| eight_schools-eight_schools_centered | [0.119, 0.275, 0.18, 0.248] / [0.129, 0.249, 0.181, 0.0974] / [0.224, 0.0969, 0.13, 0.232] | 0,0,0 | 3,0,0 |
| diamonds-diamonds | [0.00306, 0.00424, 0.00237, 0.00422] / [0.00417, 0.00347, 0.00331, 0.00387] / [0.0034, 0.0027, 0.00345, 0.00345] | 914,306,734 | 0,0,0 |
| earnings-logearn_interaction | [0.0175, 0.0171, 0.0174, 0.014] / [0.0136, 0.0156, 0.0142, 0.0166] / [0.0173, 0.0143, 0.0153, 0.018] | 0,0,0 | 0,0,0 |
| mesquite-logmesquite_logvash | [0.0794, 0.0793, 0.0673, 0.0759] / [0.0719, 0.0763, 0.0672, 0.096] / [0.07, 0.0607, 0.067, 0.079] | 0,0,0 | 0,0,0 |
| kidiq-kidscore_momhsiq | [0.0968, 0.126, 0.116, 0.0942] / [0.0889, 0.0809, 0.0878, 0.0947] / [0.101, 0.0937, 0.0956, 0.0843] | 0,0,0 | 0,0,0 |
| sblrc-blr | [0.101, 0.0968, 0.112, 0.105] / [0.119, 0.11, 0.0945, 0.0987] | 0,0 | 0,0 |
| nes2000-nes | [0.062, 0.0696, 0.0839, 0.0729] / [0.0819, 0.103, 0.0749, 0.0739] / [0.0832, 0.0755, 0.0723, 0.0771] | 0,0,0 | 0,0,0 |
| arK-arK | [0.108, 0.116, 0.124, 0.116] / [0.121, 0.113, 0.127, 0.104] / [0.11, 0.104, 0.104, 0.124] | 0,0,0 | 0,0,0 |
| arma-arma11 | [0.756, 0.712, 0.739, 0.762] / [0.683, 0.704, 0.671, 0.654] / [0.698, 0.737, 0.624, 0.704] | 0,0,0 | 0,0,0 |
| garch-garch11 | [0.24, 0.317, 0.31, 0.285] / [0.336, 0.326, 0.349, 0.357] / [0.319, 0.288, 0.319, 0.313] | 0,0,0 | 0,0,0 |
| gp_pois_regr-gp_pois_regr | [0.0295, 0.0299, 0.0298, 0.0231] / [0.0341, 0.0271, 0.0256, 0.0283] / [0.0271, 0.0276, 0.0252, 0.0256] | 0,0,0 | 0,0,0 |
| hmm_example-hmm_example | [0.305, 0.32, 0.287, 0.307] / [0.329, 0.293, 0.276, 0.345] / [0.293, 0.31, 0.312, 0.255] | 0,0,0 | 0,0,0 |
| bball_drive_event_0-hmm_drive_0 | [0.594, 0.68, 0.67, 0.633] / [0.696, 0.68, 0.573, 0.626] / [0.575, 0.604, 0.704, 0.634] | 0,0,0 | 0,0,0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | [0.349, 0.367, 0.396, 0.418] / [0.324, 0.35, 0.294, 0.319] / [0.43, 0.415, 0.36, 0.371] | 0,0,0 | 0,0,0 |
| hudson_lynx_hare-lotka_volterra | [0.12, 0.0855, 0.117, 0.0975] / [0.101, 0.0977, 0.104, 0.0959] / [0.0976, 0.115, 0.103, 0.123] | 0,0,0 | 0,0,0 |
| mcycle_gp-accel_gp | [0.00734, 0.0123, 0.00747, 0.00918] / [0.00746, 0.00769, 0.008, 0.00721] / [0.00949, 0.00787, 0.00628, 0.00667] | 0,1,0 | 0,0,0 |

## v6 versus v5 (seed medians; ratio v6 / v5; seeds 90101-90103 versus 87101-87103; oWALNUTS adds the WP33 chain-rescue default, competitors show seed noise)

| model | arm | v5 gates | v6 gates | v5 ESS/grad x1e3 | v6 ESS/grad x1e3 | ESS/grad v6/v5 | ESS/s v6/v5 | wall v6/v5 | grads v6/v5 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 3/3 | 24.720 | 29.948 | 1.21 | 1.15 | 1.02 | 1.00 |
| eight_schools-eight_schools_noncentered | cmdstan | 3/3 | 1/3 | 32.978 | 29.304 | 0.89 | 0.88 | 1.17 | 1.00 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 42.744 | 44.654 | 1.04 | 3.02 | 0.41 | 1.00 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0/3 | 0.349 | 0.281 | 0.81 | 0.58 | 1.66 | 1.21 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 0.296 | 1.210 | 4.09 | 4.69 | 1.22 | 1.06 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 1.027 | 0.948 | 0.92 | 3.18 | 0.31 | 1.06 |
| diamonds-diamonds | owalnuts-da | 3/3 | 3/3 | 0.191 | 0.171 | 0.89 | 0.70 | 1.25 | 0.99 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.227 | 0.229 | 1.01 | 0.76 | 1.26 | 0.99 |
| diamonds-diamonds | nutpie | 0/3 | 2/3 | 0.162 | 0.196 | 1.21 | 1.06 | 1.15 | 1.00 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 3/3 | 0.582 | 0.588 | 1.01 | 0.74 | 1.31 | 1.16 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.870 | 0.756 | 0.87 | 0.76 | 1.13 | 0.99 |
| earnings-logearn_interaction | nutpie | 3/3 | 3/3 | 0.954 | 0.960 | 1.01 | 1.09 | 0.94 | 0.99 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 3/3 | 3.601 | 3.183 | 0.88 | 0.74 | 1.20 | 1.01 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 3.983 | 3.724 | 0.94 | 0.70 | 1.42 | 1.01 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.237 | 4.028 | 0.95 | 2.01 | 0.43 | 0.99 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 3/3 | 3.731 | 4.067 | 1.09 | 0.72 | 1.50 | 0.99 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 4.043 | 3.854 | 0.95 | 0.56 | 1.68 | 1.02 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 3/3 | 6.170 | 6.430 | 1.04 | 1.44 | 0.74 | 1.02 |
| sblrc-blr | owalnuts-da | 3/3 | 2/3 | 5.748 | 5.084 | 0.88 | 0.61 | 1.50 | 1.02 |
| sblrc-blr | cmdstan | 2/3 | 3/3 | 6.593 | 6.035 | 0.92 | 0.92 | 0.94 | 0.97 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 15.602 | 17.850 | 1.14 | 1.94 | 0.63 | 0.99 |
| nes2000-nes | owalnuts-da | 3/3 | 3/3 | 4.239 | 4.528 | 1.07 | 0.79 | 1.32 | 1.00 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.973 | 4.710 | 0.95 | 0.69 | 1.34 | 1.00 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.859 | 5.742 | 0.98 | 0.99 | 1.01 | 1.00 |
| arK-arK | owalnuts-da | 3/3 | 3/3 | 8.739 | 8.334 | 0.95 | 0.44 | 2.14 | 1.00 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.794 | 10.269 | 0.95 | 0.66 | 1.44 | 1.02 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.492 | 11.947 | 1.04 | 5.46 | 0.18 | 1.00 |
| arma-arma11 | owalnuts-da | 3/3 | 3/3 | 14.273 | 20.356 | 1.43 | 1.94 | 0.49 | 0.67 |
| arma-arma11 | cmdstan | 1/3 | 1/3 | 0.201 | 0.004 | 0.02 | 0.01 | 64.94 | 39.51 |
| arma-arma11 | nutpie | 1/3 | 2/3 | 0.278 | 152.072 | 547.72 | 4730.89 | 0.14 | 1.04 |
| garch-garch11 | owalnuts-da | 3/3 | 3/3 | 19.202 | 17.503 | 0.91 | 0.72 | 1.31 | 1.02 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 22.321 | 21.713 | 0.97 | 0.85 | 1.24 | 1.00 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 25.609 | 23.279 | 0.91 | 4.12 | 0.23 | 1.01 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 3/3 | 3/3 | 0.751 | 0.718 | 0.96 | 0.70 | 1.41 | 1.05 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 0.995 | 1.042 | 1.05 | 0.76 | 1.23 | 0.98 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 0.487 | 0.680 | 1.39 | 1.98 | 0.71 | 1.01 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 3/3 | 15.506 | 19.193 | 1.24 | 1.00 | 0.97 | 0.85 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 21.238 | 19.814 | 0.93 | 0.58 | 1.67 | 1.03 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 28.332 | 27.586 | 0.97 | 8.30 | 0.12 | 1.00 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 3/3 | 37.607 | 42.047 | 1.12 | 1.35 | 0.76 | 0.82 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 2/3 | 39.881 | 34.457 | 0.86 | 0.60 | 1.51 | 1.13 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 3/3 | 1/3 | 95.105 | 0.440 | 0.00 | 0.02 | 0.27 | 1.01 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 1/3 | 3/3 | 10.131 | 13.579 | 1.34 | 0.90 | 1.70 | 1.00 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 1/3 | 0/3 | 10.716 | 8.166 | 0.76 | 0.62 | 1.31 | 1.02 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 22.184 | 18.490 | 0.83 | 1.95 | 0.42 | 1.00 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 3/3 | 3/3 | 3.136 | 3.075 | 0.98 | 0.68 | 1.49 | 1.07 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 3/3 | 3.561 | 3.700 | 1.04 | 0.87 | 1.10 | 1.00 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 0/3 | — | 2.939 | — | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 1/3 | 0.118 | 0.232 | 1.98 | 1.44 | 1.16 | 1.00 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.251 | 0.242 | 0.96 | 0.70 | 1.18 | 0.95 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.165 | 0.173 | 1.05 | 2.52 | 0.46 | 1.02 |

| arm | v5 cells passed | v6 cells passed | geomean ESS/grad v6/v5 | geomean ESS/s v6/v5 | geomean grads v6/v5 |
|---|---:|---:|---:|---:|---:|
| owalnuts-da | 42 | 45 | 1.08 | 0.83 | 0.98 |
| cmdstan | 36 | 34 | 0.81 | 0.63 | 1.25 |
| nutpie | 28 | 29 | 1.09 | 2.76 | 1.01 |

## Chain-rescue events (owalnuts-da)

| model | seed | chain | boundary transition | criterion | source | step before -> after | median log density |
|---|---:|---:|---:|---|---:|---|---:|
| eight_schools-eight_schools_centered | 90103 | 0 | 149 | Step | 3 | 0.0141 -> 0.308 | -53.1 |
| diamonds-diamonds | 90101 | 1 | 99 | LogDensity | 2 | 0.00528 -> 0.00129 | -1.75e+04 |
| diamonds-diamonds | 90102 | 3 | 99 | LogDensity | 1 | 0.00103 -> 0.000906 | -455 |
| earnings-logearn_interaction | 90101 | 2 | 249 | Step | 3 | 0.000328 -> 0.0153 | -1.91e+03 |
| earnings-logearn_interaction | 90102 | 1 | 99 | LogDensity | 0 | 0.0223 -> 0.0205 | -9.95e+03 |
| earnings-logearn_interaction | 90102 | 2 | 99 | Step | 0 | 0.000901 -> 0.0205 | -5.25e+03 |
| earnings-logearn_interaction | 90103 | 3 | 99 | LogDensity | 0 | 0.0212 -> 0.0176 | -9.24e+03 |
| kidiq-kidscore_momhsiq | 90101 | 0 | 249 | Step | 3 | 0.00964 -> 0.601 | -1.88e+03 |
| kidiq-kidscore_momhsiq | 90101 | 1 | 99 | LogDensity | 0 | 0.0362 -> 0.0498 | -3.76e+03 |
| kidiq-kidscore_momhsiq | 90101 | 1 | 149 | LogDensity | 2 | 0.0104 -> 0.0186 | -2.44e+03 |
| kidiq-kidscore_momhsiq | 90102 | 0 | 99 | LogDensity | 1 | 0.0145 -> 0.0154 | -2.97e+03 |
| kidiq-kidscore_momhsiq | 90102 | 2 | 99 | LogDensity | 1 | 0.0391 -> 0.0154 | -4.52e+03 |
| sblrc-blr | 90102 | 3 | 99 | LogDensity | 2 | 0.00775 -> 0.00114 | -1.34e+04 |
| sblrc-blr | 90103 | 1 | 99 | LogDensity | 3 | 0.00146 -> 0.00177 | -314 |
| arma-arma11 | 90101 | 3 | 99 | Step | 0 | 3.42e-38 -> 0.0154 | -324 |
| arma-arma11 | 90102 | 1 | 99 | Step | 0 | 4.99e-17 -> 0.0118 | -1.42e+15 |
| arma-arma11 | 90102 | 2 | 99 | LogDensity | 0 | 3.91e-07 -> 0.0118 | -926 |
| arma-arma11 | 90102 | 3 | 99 | Step | 0 | 3.86e-37 -> 0.0118 | -757 |
| arma-arma11 | 90103 | 2 | 99 | Step | 1 | 3.68e-05 -> 0.0162 | -354 |
| bball_drive_event_0-hmm_drive_0 | 90101 | 3 | 99 | LogDensity | 2 | 0.0577 -> 0.056 | -2.1e+03 |
| bball_drive_event_0-hmm_drive_0 | 90102 | 0 | 99 | LogDensity | 3 | 0.0498 -> 0.094 | -2.01e+03 |
| bball_drive_event_0-hmm_drive_0 | 90103 | 0 | 99 | LogDensity | 2 | 0.03 -> 0.0483 | -1.99e+03 |
| hudson_lynx_hare-lotka_volterra | 90101 | 0 | 99 | LogDensity | 1 | 0.0277 -> 0.0166 | -196 |
| hudson_lynx_hare-lotka_volterra | 90101 | 2 | 99 | LogDensity | 1 | 0.0127 -> 0.0166 | -243 |
| hudson_lynx_hare-lotka_volterra | 90102 | 2 | 99 | LogDensity | 1 | 0.0434 -> 0.0234 | -369 |
| hudson_lynx_hare-lotka_volterra | 90102 | 3 | 99 | LogDensity | 1 | 0.0726 -> 0.0234 | -201 |
| hudson_lynx_hare-lotka_volterra | 90103 | 1 | 99 | Step | 2 | 4.93e-06 -> 0.0165 | -1.05e+04 |
| mcycle_gp-accel_gp | 90101 | 2 | 99 | LogDensity | 3 | 0.0125 -> 0.00709 | -692 |
| mcycle_gp-accel_gp | 90102 | 1 | 99 | LogDensity | 0 | 0.0387 -> 0.0161 | -1.3e+03 |
| mcycle_gp-accel_gp | 90102 | 2 | 99 | LogDensity | 0 | 0.0263 -> 0.0161 | -5.83e+03 |

## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed

| seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | target calls | divergences | retained exhaustions | rescued | final steps |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| 90101 | 0.0373 | -1.04 | -1.09 | 388 / 1.003 | 5,445,150 | 0 | 2 | 3 | 0.0101, 0.0816, 0.0205, 0.0927 |
| 90102 | 0.0498 | +0.25 | +0.27 | 539 / 1.009 | 3,836,916 | 0 | 46 | 1 | 0.225, 0.088, 0.162, 0.151 |
| 90103 | 0.0671 | +1.69 | +1.86 | 356 / 1.004 | 5,167,023 | 2 | 21 | 0 | 0.0561, 0.027, 0.1, 0.0576 |
| pooled (batch means) | 0.0514 | — | +0.68 | — | — | — | — | — | — |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_da_gate_passes_ge_42_of_51 | 45 | True |
| P2_no_passing_da_cell_max_abs_z_gt_4 | ['one_comp_mm_elim_abs-one_comp_mm_elim_abs/90103=4.023'] | False |
| P3_fixed_16_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.75 | 0.848 | None |
| P4_fixed_16_geomean_wall_per_gradient_vs_cmdstan_le_1.0 | 0.825 | None |
| P5_da_geomean_bulk_ess_per_second_vs_nutpie_ge_1.5 | 0.996 | False |
| P6_funnel_defaults_abs_z_le_2_every_seed | [-1.0432199496005408, 0.24764408810261393, 1.6893873620762003] | True |
| P7_no_frozen_owalnuts_chain | [] | True |
| reported_all_153_cells_present | 153 | True |
| reported_rescue_events | [{'model': 'eight_schools-eight_schools_centered', 'seed': 90103, 'chain': 0, 'criterion': 'Step', 'log_density_iqr': 7.65147750086777, 'median_log_density': -53.09345319035944, 'source': 3, 'source_position': 39, 'step_after': 0.3083655106374107, 'step_before': 0.014052888932275156, 'transition': 149, 'window_index': 1, 'window_transitions': 50}, {'model': 'diamonds-diamonds', 'seed': 90101, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 1416.0398682574014, 'median_log_density': -17511.475913571834, 'source': 2, 'source_position': 11, 'step_after': 0.0012862973146915767, 'step_before': 0.00528340228903736, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'diamonds-diamonds', 'seed': 90102, 'chain': 3, 'criterion': 'LogDensity', 'log_density_iqr': 3784.832160697883, 'median_log_density': -454.9562979898359, 'source': 1, 'source_position': 3, 'step_after': 0.0009059163703244141, 'step_before': 0.0010317345025339182, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'earnings-logearn_interaction', 'seed': 90101, 'chain': 2, 'criterion': 'Step', 'log_density_iqr': 489.8651608198534, 'median_log_density': -1914.3730394810987, 'source': 3, 'source_position': 16, 'step_after': 0.015293430808633459, 'step_before': 0.00032804364573417515, 'transition': 249, 'window_index': 2, 'window_transitions': 100}, {'model': 'earnings-logearn_interaction', 'seed': 90102, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 317.8872591384843, 'median_log_density': -9948.110987150194, 'source': 0, 'source_position': 15, 'step_after': 0.020522276923796916, 'step_before': 0.022335022801969487, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'earnings-logearn_interaction', 'seed': 90102, 'chain': 2, 'criterion': 'Step', 'log_density_iqr': 3343.6013524731443, 'median_log_density': -5251.4383053180545, 'source': 0, 'source_position': 4, 'step_after': 0.020522276923796916, 'step_before': 0.0009012201017305787, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'earnings-logearn_interaction', 'seed': 90103, 'chain': 3, 'criterion': 'LogDensity', 'log_density_iqr': 193.53815146859233, 'median_log_density': -9239.446693789281, 'source': 0, 'source_position': 4, 'step_after': 0.017589898919399227, 'step_before': 0.021193707857252813, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'kidiq-kidscore_momhsiq', 'seed': 90101, 'chain': 0, 'criterion': 'Step', 'log_density_iqr': 1.3929977139832772, 'median_log_density': -1876.5821840883048, 'source': 3, 'source_position': 71, 'step_after': 0.6006379649991825, 'step_before': 0.009637640336246952, 'transition': 249, 'window_index': 2, 'window_transitions': 100}, {'model': 'kidiq-kidscore_momhsiq', 'seed': 90101, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 164.3627090768673, 'median_log_density': -3759.6631136820824, 'source': 0, 'source_position': 18, 'step_after': 0.049816964791099684, 'step_before': 0.03620778691872861, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'kidiq-kidscore_momhsiq', 'seed': 90101, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 821.0996877774842, 'median_log_density': -2437.9911085576637, 'source': 2, 'source_position': 39, 'step_after': 0.01863450791361805, 'step_before': 0.010382220875052353, 'transition': 149, 'window_index': 1, 'window_transitions': 50}, {'model': 'kidiq-kidscore_momhsiq', 'seed': 90102, 'chain': 0, 'criterion': 'LogDensity', 'log_density_iqr': 309.700774929408, 'median_log_density': -2970.8226657103746, 'source': 1, 'source_position': 12, 'step_after': 0.015429340015841144, 'step_before': 0.01449931882494714, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'kidiq-kidscore_momhsiq', 'seed': 90102, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 375.92058323737365, 'median_log_density': -4524.463812764942, 'source': 1, 'source_position': 15, 'step_after': 0.015429340015841144, 'step_before': 0.03910912567410798, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'sblrc-blr', 'seed': 90102, 'chain': 3, 'criterion': 'LogDensity', 'log_density_iqr': 263.791477506662, 'median_log_density': -13359.51437986529, 'source': 2, 'source_position': 24, 'step_after': 0.0011365193050287734, 'step_before': 0.007753371262035904, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'sblrc-blr', 'seed': 90103, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 41.78572769628312, 'median_log_density': -314.46192442359086, 'source': 3, 'source_position': 4, 'step_after': 0.0017723818452085793, 'step_before': 0.0014592283158340663, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'arma-arma11', 'seed': 90101, 'chain': 3, 'criterion': 'Step', 'log_density_iqr': 0.0, 'median_log_density': -324.0685373745203, 'source': 0, 'source_position': 16, 'step_after': 0.01544762026261982, 'step_before': 3.4174120955254185e-38, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'arma-arma11', 'seed': 90102, 'chain': 1, 'criterion': 'Step', 'log_density_iqr': 0.0, 'median_log_density': -1422934576897006.2, 'source': 0, 'source_position': 1, 'step_after': 0.011769838145171201, 'step_before': 4.99007758744153e-17, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'arma-arma11', 'seed': 90102, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 0.000820994476953274, 'median_log_density': -925.5153883316535, 'source': 0, 'source_position': 18, 'step_after': 0.011769838145171201, 'step_before': 3.9114071718208323e-07, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'arma-arma11', 'seed': 90102, 'chain': 3, 'criterion': 'Step', 'log_density_iqr': 0.0, 'median_log_density': -757.2908330003734, 'source': 0, 'source_position': 9, 'step_after': 0.011769838145171201, 'step_before': 3.859512571416981e-37, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'arma-arma11', 'seed': 90103, 'chain': 2, 'criterion': 'Step', 'log_density_iqr': 0.03434956351151186, 'median_log_density': -353.9571524721319, 'source': 1, 'source_position': 21, 'step_after': 0.016151388242446097, 'step_before': 3.684672168208857e-05, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'bball_drive_event_0-hmm_drive_0', 'seed': 90101, 'chain': 3, 'criterion': 'LogDensity', 'log_density_iqr': 14.388420429625057, 'median_log_density': -2100.4357519512027, 'source': 2, 'source_position': 12, 'step_after': 0.05604232640390409, 'step_before': 0.05770356820176453, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'bball_drive_event_0-hmm_drive_0', 'seed': 90102, 'chain': 0, 'criterion': 'LogDensity', 'log_density_iqr': 38.574021932594405, 'median_log_density': -2009.9396035272425, 'source': 3, 'source_position': 24, 'step_after': 0.09395051878998231, 'step_before': 0.04979242875043225, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'bball_drive_event_0-hmm_drive_0', 'seed': 90103, 'chain': 0, 'criterion': 'LogDensity', 'log_density_iqr': 8.79017197634903, 'median_log_density': -1990.3349742981172, 'source': 2, 'source_position': 14, 'step_after': 0.04831614712511203, 'step_before': 0.030002793071319426, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'hudson_lynx_hare-lotka_volterra', 'seed': 90101, 'chain': 0, 'criterion': 'LogDensity', 'log_density_iqr': 4.230879006613833, 'median_log_density': -196.48017575589563, 'source': 1, 'source_position': 21, 'step_after': 0.01664337905904104, 'step_before': 0.02765500457873848, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'hudson_lynx_hare-lotka_volterra', 'seed': 90101, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 25.50276290412927, 'median_log_density': -243.29978851803466, 'source': 1, 'source_position': 11, 'step_after': 0.01664337905904104, 'step_before': 0.012701467506068079, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'hudson_lynx_hare-lotka_volterra', 'seed': 90102, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 9.670510663331356, 'median_log_density': -368.50689993475123, 'source': 1, 'source_position': 4, 'step_after': 0.02343868967902307, 'step_before': 0.04341227490456222, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'hudson_lynx_hare-lotka_volterra', 'seed': 90102, 'chain': 3, 'criterion': 'LogDensity', 'log_density_iqr': 14.34658511469624, 'median_log_density': -201.40865358632777, 'source': 1, 'source_position': 4, 'step_after': 0.02343868967902307, 'step_before': 0.07261661316864416, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'hudson_lynx_hare-lotka_volterra', 'seed': 90103, 'chain': 1, 'criterion': 'Step', 'log_density_iqr': 21.128236107117118, 'median_log_density': -10465.161118041928, 'source': 2, 'source_position': 10, 'step_after': 0.016521696933209335, 'step_before': 4.930904483285757e-06, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'mcycle_gp-accel_gp', 'seed': 90101, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 40.711902184109135, 'median_log_density': -691.6326161105138, 'source': 3, 'source_position': 24, 'step_after': 0.00708782241662056, 'step_before': 0.012478623029074192, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'mcycle_gp-accel_gp', 'seed': 90102, 'chain': 1, 'criterion': 'LogDensity', 'log_density_iqr': 45.00636379692105, 'median_log_density': -1298.8696066347356, 'source': 0, 'source_position': 12, 'step_after': 0.016078270343466622, 'step_before': 0.03871394992111221, 'transition': 99, 'window_index': 0, 'window_transitions': 25}, {'model': 'mcycle_gp-accel_gp', 'seed': 90102, 'chain': 2, 'criterion': 'LogDensity', 'log_density_iqr': 9909.104329249987, 'median_log_density': -5825.32310084611, 'source': 0, 'source_position': 17, 'step_after': 0.016078270343466622, 'step_before': 0.026267118510889576, 'transition': 99, 'window_index': 0, 'window_transitions': 25}] | reported |
| reported_da_v6_over_v5_geomean_bulk_ess_per_gradient | 1.075 | reported |
| reported_da_models_below_0.8x_v5 | {} | reported |
| reported_da_models_above_1.2x_v5 | {'eight_schools-eight_schools_noncentered': 1.2114992699085247, 'arma-arma11': 1.4261913728331703, 'hmm_example-hmm_example': 1.2377452961241715, 'one_comp_mm_elim_abs-one_comp_mm_elim_abs': 1.340343314492, 'mcycle_gp-accel_gp': 1.9775770525994583} | reported |
| reported_competitor_v6_over_v5_geomean_bulk_ess_per_gradient | {'cmdstan': 0.8119295645064385, 'nutpie': 1.0853440253672402} | reported |
| reported_owalnuts_cells_not_ok | ['sblrc-blr/owalnuts-da/90101: '] | reported |

**Release headline ready:** `False`
