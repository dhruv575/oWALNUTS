# posteriordb benchmark v4 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z | refined frac | depth caps |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.04 | 64,438 | 2,027 | 1,550 | 53,865.7 | 43,703.1 | 31.464 | 1.0021 | 0,0,0 | 1.39 | 0.055 | 0 |
| eight_schools-eight_schools_noncentered | owalnuts-da-stanreg | 3/3 | 0.03 | 68,016 | 1,820 | 1,594 | 52,334.4 | 45,839.2 | 26.759 | 1.0022 | 0,0,0 | 1.59 | 0.059 | 0 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 0.22 | 75,894 | 2,125 | 1,666 | 9,831.2 | 7,635.9 | 28.003 | 1.0019 | 1,1,0 | 1.32 | — | 0 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.25 | 55,711 | 2,206 | 1,514 | 8,090.9 | 6,118.3 | 39.594 | 1.0023 | 2,3,5 | 1.64 | — | 0 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.10 | 205,387 | 55 | 37 | 341.3 | 257.2 | 0.168 | 1.0771 | 0,0,1 | 1.35 | 0.282 | 0 |
| eight_schools-eight_schools_centered | owalnuts-da-stanreg | 0/3 | 0.09 | 190,921 | 27 | 26 | 299.4 | 283.8 | 0.153 | 1.1041 | 1,0,0 | 0.74 | 0.270 | 0 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.21 | 177,627 | 111 | 89 | 204.9 | 165.1 | 0.622 | 1.0401 | 100,32,287 | 2.09 | — | 0 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0.36 | 103,592 | 71 | 39 | 195.6 | 106.9 | 0.770 | 1.0409 | 43,125,68 | 3.63 | — | 0 |
| diamonds-diamonds | owalnuts-da | 3/3 | 78.00 | 5,117,279 | 901 | 1,116 | 9.8 | 14.3 | 0.180 | 1.0066 | 0,0,0 | 2.26 | 0.008 | 871 |
| diamonds-diamonds | owalnuts-da-stanreg | 2/3 | 64.31 | 4,620,245 | 638 | 1,123 | 9.3 | 16.9 | 0.129 | 1.0053 | 0,0,0 | 2.17 | 0.011 | 899 |
| diamonds-diamonds | cmdstan | 3/3 | 74.49 | 6,486,912 | 1,373 | 1,896 | 18.4 | 26.7 | 0.211 | 1.0030 | 0,0,0 | 1.84 | — | 3,305 |
| diamonds-diamonds | nutpie | 0/3 | 26.20 | 2,082,442 | 354 | 509 | 14.1 | 18.1 | 0.173 | 1.0158 | 0,0,0 | 2.44 | — | 9 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 51.21 | 4,345,416 | 804 | 910 | 15.7 | 17.8 | 0.212 | 1.0048 | 0,0,0 | 1.07 | 0.024 | 338 |
| earnings-logearn_interaction | owalnuts-da-stanreg | 0/3 | 5.99 | 531,341 | 45 | 72 | 5.4 | 12.9 | 0.074 | 1.0840 | 0,0,0 | 1.89 | 0.010 | 0 |
| earnings-logearn_interaction | cmdstan | 3/3 | 12.37 | 1,317,197 | 1,127 | 1,354 | 87.5 | 104.0 | 0.864 | 1.0060 | 0,0,0 | 0.94 | — | 0 |
| earnings-logearn_interaction | nutpie | 3/3 | 8.74 | 730,114 | 699 | 889 | 80.9 | 101.7 | 0.965 | 1.0027 | 0,0,0 | 1.14 | — | 0 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.27 | 319,739 | 908 | 1,105 | 3,123.2 | 4,036.5 | 2.854 | 1.0048 | 0,0,0 | 1.61 | 0.042 | 0 |
| mesquite-logmesquite_logvash | owalnuts-da-stanreg | 3/3 | 0.29 | 337,696 | 1,081 | 1,236 | 3,735.8 | 4,121.1 | 3.200 | 1.0039 | 0,0,0 | 1.49 | 0.034 | 0 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.39 | 363,362 | 1,269 | 1,700 | 3,282.0 | 4,464.5 | 3.324 | 1.0015 | 0,0,0 | 1.67 | — | 0 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.68 | 195,375 | 833 | 1,034 | 1,221.2 | 1,559.6 | 4.263 | 1.0054 | 0,0,0 | 1.04 | — | 0 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.28 | 406,362 | 979 | 889 | 702.6 | 632.7 | 2.410 | 1.0042 | 0,0,0 | 1.58 | 0.009 | 0 |
| kidiq-kidscore_momhsiq | owalnuts-da-stanreg | 0/3 | 0.69 | 189,063 | 403 | 474 | 699.2 | 834.0 | 2.270 | 1.0181 | 0,0,0 | 1.82 | 0.005 | 0 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 1.13 | 360,842 | 1,485 | 1,704 | 1,304.0 | 1,341.5 | 4.071 | 1.0035 | 0,0,0 | 1.90 | — | 0 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 0.66 | 138,990 | 778 | 1,167 | 1,173.4 | 1,771.4 | 5.660 | 1.0038 | 0,0,0 | 1.00 | — | 0 |
| sblrc-blr | owalnuts-da | 0/3 | 0.48 | 561,439 | 280 | 350 | 578.4 | 728.4 | 0.497 | 1.0142 | 0,0,0 | 1.47 | 0.030 | 0 |
| sblrc-blr | owalnuts-da-stanreg | 3/3 | 0.16 | 189,592 | 748 | 749 | 4,689.3 | 4,960.7 | 3.853 | 1.0042 | 0,0,0 | 1.38 | 0.013 | 0 |
| sblrc-blr | cmdstan | 3/3 | 0.60 | 122,850 | 802 | 929 | 1,434.2 | 1,735.1 | 6.073 | 1.0039 | 0,0,0 | 0.57 | — | 0 |
| sblrc-blr | nutpie | 3/3 | 0.13 | 56,224 | 838 | 1,376 | 6,351.7 | 10,504.0 | 14.817 | 1.0056 | 0,0,0 | 0.44 | — | 0 |
| nes2000-nes | owalnuts-da | 3/3 | 4.83 | 437,239 | 1,060 | 1,328 | 218.1 | 275.1 | 2.425 | 1.0040 | 0,0,0 | 1.41 | 0.004 | 0 |
| nes2000-nes | owalnuts-da-stanreg | 3/3 | 3.26 | 315,853 | 915 | 1,091 | 267.6 | 334.4 | 2.760 | 1.0071 | 0,0,0 | 1.74 | 0.007 | 0 |
| nes2000-nes | cmdstan | 3/3 | 4.00 | 394,111 | 2,055 | 2,050 | 475.7 | 512.4 | 5.288 | 1.0029 | 0,0,0 | 1.48 | — | 0 |
| nes2000-nes | nutpie | 3/3 | 3.24 | 239,593 | 1,438 | 1,940 | 475.0 | 640.9 | 6.001 | 1.0026 | 0,0,0 | 1.33 | — | 0 |
| arK-arK | owalnuts-da | 3/3 | 1.43 | 249,442 | 2,027 | 2,136 | 1,389.7 | 1,522.3 | 7.973 | 1.0040 | 0,0,0 | 1.78 | 0.010 | 0 |
| arK-arK | owalnuts-da-stanreg | 3/3 | 1.65 | 258,467 | 2,030 | 2,055 | 1,199.7 | 1,210.4 | 7.656 | 1.0036 | 0,0,0 | 1.92 | 0.014 | 0 |
| arK-arK | cmdstan | 3/3 | 1.62 | 241,426 | 2,837 | 2,341 | 1,562.4 | 1,360.2 | 11.813 | 1.0028 | 0,0,0 | 1.36 | — | 0 |
| arK-arK | nutpie | 3/3 | 10.63 | 173,862 | 2,024 | 2,207 | 190.4 | 207.6 | 11.642 | 1.0022 | 0,0,0 | 1.65 | — | 0 |
| arma-arma11 | owalnuts-da | 3/3 | 1.43 | 262,306 | 1,386 | 1,487 | 969.8 | 1,040.4 | 5.284 | 1.0035 | 0,0,0 | 1.19 | 0.023 | 0 |
| arma-arma11 | owalnuts-da-stanreg | 3/3 | 1.40 | 220,980 | 2,891 | 2,346 | 2,059.2 | 1,671.1 | 13.082 | 1.0019 | 0,0,0 | 1.45 | 0.010 | 0 |
| arma-arma11 | cmdstan | 1/3 | 12.63 | 1,663,507 | 7 | 13 | 0.5 | 0.9 | 0.004 | 1.5852 | 0,0,0 | 1.16 | — | 931 |
| arma-arma11 | nutpie | 3/3 | 1.75 | 29,730 | 4,843 | 3,006 | 2,762.6 | 1,739.8 | 162.888 | 1.0007 | 0,0,0 | 1.16 | — | 0 |
| garch-garch11 | owalnuts-da | 3/3 | 0.46 | 72,917 | 965 | 1,378 | 2,064.2 | 3,042.0 | 13.077 | 1.0068 | 0,0,0 | 1.43 | 0.028 | 0 |
| garch-garch11 | owalnuts-da-stanreg | 3/3 | 0.44 | 69,790 | 975 | 1,247 | 2,090.7 | 2,840.0 | 13.970 | 1.0051 | 0,0,0 | 0.89 | 0.036 | 0 |
| garch-garch11 | cmdstan | 3/3 | 0.71 | 91,046 | 1,839 | 1,793 | 2,593.0 | 2,391.1 | 19.990 | 1.0036 | 0,0,0 | 0.84 | — | 0 |
| garch-garch11 | nutpie | 3/3 | 4.17 | 61,536 | 1,515 | 1,978 | 356.1 | 481.9 | 24.777 | 1.0023 | 0,0,0 | 1.15 | — | 0 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 3/3 | 3.05 | 1,145,875 | 1,029 | 1,500 | 336.9 | 480.2 | 0.898 | 1.0042 | 0,0,0 | 1.69 | 0.051 | 0 |
| gp_pois_regr-gp_pois_regr | owalnuts-da-stanreg | 3/3 | 2.74 | 1,005,715 | 776 | 1,223 | 299.3 | 445.6 | 0.766 | 1.0042 | 0,0,0 | 2.10 | 0.091 | 0 |
| gp_pois_regr-gp_pois_regr | cmdstan | 1/3 | 3.22 | 1,371,064 | 1,422 | 1,949 | 463.7 | 681.1 | 1.038 | 1.0026 | 3,0,9 | 2.39 | — | 0 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 3.77 | 807,163 | 417 | 207 | 115.8 | 57.4 | 0.511 | 1.0060 | 153,141,195 | 2.16 | — | 0 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 2.98 | 213,301 | 1,697 | 1,617 | 565.7 | 543.9 | 8.406 | 1.0027 | 0,0,0 | 1.34 | 0.017 | 0 |
| hmm_example-hmm_example | owalnuts-da-stanreg | 3/3 | 1.65 | 114,996 | 1,692 | 1,746 | 1,027.0 | 998.4 | 14.711 | 1.0021 | 0,0,0 | 1.41 | 0.014 | 0 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.62 | 95,404 | 1,955 | 2,024 | 1,095.7 | 1,248.0 | 20.505 | 1.0019 | 0,0,0 | 0.90 | — | 0 |
| hmm_example-hmm_example | nutpie | 3/3 | 12.86 | 56,405 | 1,511 | 1,815 | 125.9 | 137.3 | 26.902 | 1.0023 | 0,0,0 | 1.51 | — | 0 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 3/3 | 7.12 | 112,854 | 2,380 | 1,717 | 367.0 | 269.5 | 23.523 | 1.0033 | 0,0,0 | 1.20 | 0.007 | 0 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da-stanreg | 2/3 | 5.81 | 88,195 | 2,421 | 1,639 | 395.3 | 267.6 | 27.377 | 1.0030 | 0,0,0 | 2.08 | 0.021 | 0 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 3/3 | 9.81 | 87,929 | 3,198 | 1,894 | 326.0 | 193.1 | 36.321 | 1.0027 | 0,0,0 | 1.52 | — | 0 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 1/3 | 20.55 | 43,595 | 237 | 237 | 12.3 | 12.3 | 6.068 | 1.0161 | 0,3,657 | 2.04 | — | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 1/3 | 14.75 | 60,845 | 431 | 232 | 30.1 | 16.3 | 7.110 | 1.0052 | 0,0,0 | 1.98 | 0.078 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da-stanreg | 0/3 | 12.28 | 52,992 | 535 | 252 | 45.5 | 21.4 | 10.094 | 1.0092 | 0,0,0 | 2.22 | 0.060 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 18.03 | 69,679 | 1,028 | 516 | 57.0 | 28.6 | 14.212 | 1.0051 | 3,10,32 | 2.32 | — | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 47.56 | 51,109 | 369 | 110 | 7.9 | 2.4 | 6.995 | 1.0163 | 27,28,37 | 0.79 | — | 0 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 2/3 | 19.03 | 324,678 | 877 | 1,466 | 46.1 | 79.1 | 2.701 | 1.0025 | 0,0,0 | 1.24 | 0.039 | 0 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da-stanreg | 2/3 | 19.69 | 302,298 | 758 | 965 | 38.5 | 49.0 | 2.506 | 1.0062 | 0,0,0 | 1.63 | 0.050 | 0 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 1/1 | 11.66 | 284,937 | 1,084 | 1,121 | 93.0 | 96.1 | 3.804 | 1.0038 | 0 | 1.51 | — | 0 |
| hudson_lynx_hare-lotka_volterra | nutpie | not run | — | — | — | — | — | — | — | — |  | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da | not run | — | — | — | — | — | — | — | — |  | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da-stanreg | not run | — | — | — | — | — | — | — | — |  | — | — | — |
| mcycle_gp-accel_gp | cmdstan | not run | — | — | — | — | — | — | — | — |  | — | — | — |
| mcycle_gp-accel_gp | nutpie | not run | — | — | — | — | — | — | — | — |  | — | — | — |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |
|---|---:|---:|---:|---:|---:|---:|---|
| owalnuts-da_over_cmdstan | 15 | 0.845 | 1.235 | 0.694 | 4 | 2 | eight_schools-eight_schools_noncentered, arma-arma11 |
| owalnuts-da-stanreg_over_cmdstan | 15 | 0.993 | 1.486 | 0.693 | 6 | 1 | arma-arma11 |
| owalnuts-da_over_nutpie | 15 | 0.436 | 1.672 | 0.251 | 9 | 4 | gp_pois_regr-gp_pois_regr, bball_drive_event_0-hmm_drive_0, one_comp_mm_elim_abs-one_comp_mm_elim_abs |
| owalnuts-da-stanreg_over_nutpie | 15 | 0.512 | 2.012 | 0.251 | 9 | 3 | gp_pois_regr-gp_pois_regr, bball_drive_event_0-hmm_drive_0, one_comp_mm_elim_abs-one_comp_mm_elim_abs |

## owalnuts-da-stanreg versus owalnuts-da (same seeds and starts; seed medians; ratio stanreg / da; final h per chain on the first seed)

| model | da gates | stanreg gates | da ESS/grad x1e3 | stanreg ESS/grad x1e3 | ESS/grad ratio | ESS/s ratio | grads ratio | da final h | stanreg final h |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| eight_schools-eight_schools_noncentered | 3/3 | 3/3 | 31.464 | 26.759 | 0.85 | 0.97 | 1.06 | 0.45/0.5/0.44/0.44 | 0.45/0.42/0.32/0.43 |
| eight_schools-eight_schools_centered | 0/3 | 0/3 | 0.168 | 0.153 | 0.91 | 0.88 | 0.93 | 0.24/0.13/0.067/0.21 | 0.34/0.14/0.2/0.24 |
| diamonds-diamonds | 3/3 | 2/3 | 0.180 | 0.129 | 0.71 | 0.95 | 0.90 | 0.0037/0.0035/0.0033/0.0033 | 0.0038/0.0041/0.0035/0.0039 |
| earnings-logearn_interaction | 3/3 | 0/3 | 0.212 | 0.074 | 0.35 | 0.34 | 0.12 | 0.0034/0.0036/0.0036/0.0028 | 0.015/0.01/0.016/0.016 |
| mesquite-logmesquite_logvash | 3/3 | 3/3 | 2.854 | 3.200 | 1.12 | 1.20 | 1.06 | 0.084/0.095/0.069/0.072 | 0.082/0.076/0.085/0.073 |
| kidiq-kidscore_momhsiq | 3/3 | 0/3 | 2.410 | 2.270 | 0.94 | 1.00 | 0.47 | 0.06/0.059/0.067/0.065 | 0.1/0.097/0.047/0.1 |
| sblrc-blr | 0/3 | 3/3 | 0.497 | 3.853 | 7.76 | 8.11 | 0.34 | 0.0037/0.0038/0.0039/0.0037 | 0.098/0.11/0.096/0.11 |
| nes2000-nes | 3/3 | 3/3 | 2.425 | 2.760 | 1.14 | 1.23 | 0.72 | 0.06/0.062/0.067/0.064 | 0.08/0.082/0.082/0.076 |
| arK-arK | 3/3 | 3/3 | 7.973 | 7.656 | 0.96 | 0.86 | 1.04 | 0.074/0.073/0.074/0.063 | 0.11/0.11/0.12/0.089 |
| arma-arma11 | 3/3 | 3/3 | 5.284 | 13.082 | 2.48 | 2.12 | 0.84 | 0.097/0.092/0.1/0.1 | 0.7/0.74/0.84/0.77 |
| garch-garch11 | 3/3 | 3/3 | 13.077 | 13.970 | 1.07 | 1.01 | 0.96 | 0.31/0.3/0.32/0.33 | 0.3/0.33/0.38/0.27 |
| gp_pois_regr-gp_pois_regr | 3/3 | 3/3 | 0.898 | 0.766 | 0.85 | 0.89 | 0.88 | 0.029/0.027/0.026/0.026 | 0.032/0.035/0.028/0.027 |
| hmm_example-hmm_example | 3/3 | 3/3 | 8.406 | 14.711 | 1.75 | 1.82 | 0.54 | 0.17/0.15/0.13/0.13 | 0.29/0.33/0.29/0.36 |
| bball_drive_event_0-hmm_drive_0 | 3/3 | 2/3 | 23.523 | 27.377 | 1.16 | 1.08 | 0.78 | 0.4/0.39/0.077/0.38 | 0.54/0.67/0.38/0.68 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1/3 | 0/3 | 7.110 | 10.094 | 1.42 | 1.51 | 0.87 | 0.26/0.27/0.41/0.41 | 0.36/0.39/0.45/0.39 |
| hudson_lynx_hare-lotka_volterra | 2/3 | 2/3 | 2.701 | 2.506 | 0.93 | 0.83 | 0.93 | 0.073/0.072/0.041/0.043 | 0.12/0.11/0.1/0.1 |
| mcycle_gp-accel_gp | 0/3 | 0/3 | — | — | — | — | — | — | — |

geomean ESS/grad ratio 1.158 over 16 models; min earnings-logearn_interaction 0.35; models below 0.8x: {'diamonds-diamonds': 0.7135792476346928, 'earnings-logearn_interaction': 0.35061056001790025}; gates lost (stanreg passes fewer seeds than da): ['diamonds-diamonds', 'earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'bball_drive_event_0-hmm_drive_0', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs']; cells passing da 39 / stanreg 33.

## v4 versus v3 (seed medians; ratio v4 / v3; same protocol, seeds 79101-79103 -> 83101-83103; the sampler change is `max_refinement_levels` 4 -> 8 in every oWALNUTS arm; the stanreg arm is compared with the v3 DA arm)

| model | arm | v3 gates | v4 gates | v3 ESS/grad x1e3 | v4 ESS/grad x1e3 | ESS/grad v4/v3 | ESS/s v4/v3 | wall v4/v3 | grads v4/v3 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 29.107 | 31.464 | 1.08 | 0.87 | 1.27 | 0.92 |
| eight_schools-eight_schools_noncentered | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 29.107 | 26.759 | 0.92 | 0.85 | 1.19 | 0.97 |
| eight_schools-eight_schools_noncentered | cmdstan (v3 cmdstan) | 2/3 | 1/3 | 33.756 | 28.003 | 0.83 | 0.73 | 1.19 | 1.05 |
| eight_schools-eight_schools_noncentered | nutpie (v3 nutpie) | 0/3 | 0/3 | 39.111 | 39.594 | 1.01 | 0.85 | 1.30 | 0.99 |
| eight_schools-eight_schools_centered | owalnuts-da (v3 owalnuts-da) | 0/3 | 0/3 | 0.231 | 0.168 | 0.73 | 0.71 | 1.34 | 1.29 |
| eight_schools-eight_schools_centered | owalnuts-da-stanreg (v3 owalnuts-da) | 0/3 | 0/3 | 0.231 | 0.153 | 0.66 | 0.62 | 1.20 | 1.20 |
| eight_schools-eight_schools_centered | cmdstan (v3 cmdstan) | 0/3 | 0/3 | 1.074 | 0.622 | 0.58 | 0.34 | 1.07 | 1.06 |
| eight_schools-eight_schools_centered | nutpie (v3 nutpie) | 0/3 | 0/3 | 0.901 | 0.770 | 0.85 | 0.70 | 1.06 | 0.91 |
| diamonds-diamonds | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 0.156 | 0.180 | 1.16 | 0.89 | 1.07 | 1.01 |
| diamonds-diamonds | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 2/3 | 0.156 | 0.129 | 0.83 | 0.85 | 0.89 | 0.91 |
| diamonds-diamonds | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 0.219 | 0.211 | 0.97 | 1.00 | 0.97 | 1.01 |
| diamonds-diamonds | nutpie (v3 nutpie) | 1/3 | 0/3 | 0.194 | 0.173 | 0.89 | 0.98 | 0.96 | 1.01 |
| earnings-logearn_interaction | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 0.177 | 0.212 | 1.19 | 0.88 | 1.01 | 0.86 |
| earnings-logearn_interaction | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 0/3 | 0.177 | 0.074 | 0.42 | 0.30 | 0.12 | 0.11 |
| earnings-logearn_interaction | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 0.756 | 0.864 | 1.14 | 1.12 | 0.91 | 0.98 |
| earnings-logearn_interaction | nutpie (v3 nutpie) | 3/3 | 3/3 | 0.903 | 0.965 | 1.07 | 1.12 | 0.96 | 1.00 |
| mesquite-logmesquite_logvash | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 3.030 | 2.854 | 0.94 | 0.89 | 0.96 | 0.98 |
| mesquite-logmesquite_logvash | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 3.030 | 3.200 | 1.06 | 1.07 | 1.03 | 1.03 |
| mesquite-logmesquite_logvash | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 3.431 | 3.324 | 0.97 | 1.12 | 0.88 | 0.96 |
| mesquite-logmesquite_logvash | nutpie (v3 nutpie) | 3/3 | 3/3 | 4.342 | 4.263 | 0.98 | 0.92 | 0.97 | 0.98 |
| kidiq-kidscore_momhsiq | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 2.163 | 2.410 | 1.11 | 1.05 | 0.95 | 0.93 |
| kidiq-kidscore_momhsiq | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 0/3 | 2.163 | 2.270 | 1.05 | 1.05 | 0.51 | 0.43 |
| kidiq-kidscore_momhsiq | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 4.498 | 4.071 | 0.91 | 1.06 | 1.01 | 1.03 |
| kidiq-kidscore_momhsiq | nutpie (v3 nutpie) | 3/3 | 3/3 | 6.118 | 5.660 | 0.93 | 1.04 | 0.88 | 1.00 |
| sblrc-blr | owalnuts-da (v3 owalnuts-da) | 0/3 | 0/3 | 0.413 | 0.497 | 1.20 | 1.18 | 1.14 | 1.02 |
| sblrc-blr | owalnuts-da-stanreg (v3 owalnuts-da) | 0/3 | 3/3 | 0.413 | 3.853 | 9.33 | 9.57 | 0.38 | 0.34 |
| sblrc-blr | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 6.583 | 6.073 | 0.92 | 0.32 | 3.22 | 1.00 |
| sblrc-blr | nutpie (v3 nutpie) | 3/3 | 3/3 | 13.734 | 14.817 | 1.08 | 1.42 | 0.73 | 0.99 |
| nes2000-nes | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 2.499 | 2.425 | 0.97 | 0.88 | 1.13 | 1.04 |
| nes2000-nes | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 2.499 | 2.760 | 1.10 | 1.07 | 0.76 | 0.75 |
| nes2000-nes | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 4.925 | 5.288 | 1.07 | 1.02 | 1.03 | 0.99 |
| nes2000-nes | nutpie (v3 nutpie) | 3/3 | 3/3 | 5.704 | 6.001 | 1.05 | 1.07 | 1.06 | 1.01 |
| arK-arK | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 7.752 | 7.973 | 1.03 | 0.92 | 1.10 | 1.06 |
| arK-arK | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 7.752 | 7.656 | 0.99 | 0.79 | 1.27 | 1.10 |
| arK-arK | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 10.404 | 11.813 | 1.14 | 1.00 | 1.18 | 0.98 |
| arK-arK | nutpie (v3 nutpie) | 3/3 | 3/3 | 11.372 | 11.642 | 1.02 | 0.87 | 1.19 | 1.00 |
| arma-arma11 | owalnuts-da (v3 owalnuts-da) | 2/3 | 3/3 | 14.020 | 5.284 | 0.38 | 0.18 | 4.68 | 2.25 |
| arma-arma11 | owalnuts-da-stanreg (v3 owalnuts-da) | 2/3 | 3/3 | 14.020 | 13.082 | 0.93 | 0.38 | 4.60 | 1.90 |
| arma-arma11 | cmdstan (v3 cmdstan) | 2/3 | 1/3 | 72.040 | 0.004 | 0.00 | 0.00 | 42.82 | 30.68 |
| arma-arma11 | nutpie (v3 nutpie) | 3/3 | 3/3 | 133.017 | 162.888 | 1.22 | 1.37 | 0.77 | 0.82 |
| garch-garch11 | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 15.021 | 13.077 | 0.87 | 0.65 | 1.36 | 1.02 |
| garch-garch11 | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 15.021 | 13.970 | 0.93 | 0.66 | 1.30 | 0.97 |
| garch-garch11 | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 20.860 | 19.990 | 0.96 | 0.92 | 1.16 | 0.99 |
| garch-garch11 | nutpie (v3 nutpie) | 3/3 | 3/3 | 25.822 | 24.777 | 0.96 | 0.77 | 1.33 | 1.00 |
| gp_pois_regr-gp_pois_regr | owalnuts-da (v3 owalnuts-da) | 2/3 | 3/3 | 0.731 | 0.898 | 1.23 | 0.84 | 1.56 | 1.06 |
| gp_pois_regr-gp_pois_regr | owalnuts-da-stanreg (v3 owalnuts-da) | 2/3 | 3/3 | 0.731 | 0.766 | 1.05 | 0.74 | 1.40 | 0.93 |
| gp_pois_regr-gp_pois_regr | cmdstan (v3 cmdstan) | 0/3 | 1/3 | 1.073 | 1.038 | 0.97 | 0.87 | 1.35 | 1.04 |
| gp_pois_regr-gp_pois_regr | nutpie (v3 nutpie) | 0/3 | 0/3 | 0.883 | 0.511 | 0.58 | 0.54 | 1.15 | 1.02 |
| hmm_example-hmm_example | owalnuts-da (v3 owalnuts-da) | 3/3 | 3/3 | 9.767 | 8.406 | 0.86 | 0.63 | 1.39 | 1.08 |
| hmm_example-hmm_example | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 3/3 | 9.767 | 14.711 | 1.51 | 1.15 | 0.77 | 0.58 |
| hmm_example-hmm_example | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 20.948 | 20.505 | 0.98 | 0.76 | 1.08 | 0.96 |
| hmm_example-hmm_example | nutpie (v3 nutpie) | 3/3 | 3/3 | 27.713 | 26.902 | 0.97 | 0.97 | 1.06 | 0.99 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da (v3 owalnuts-da) | 1/3 | 3/3 | 0.281 | 23.523 | 83.58 | 79.89 | 1.24 | 1.26 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da-stanreg (v3 owalnuts-da) | 1/3 | 2/3 | 0.281 | 27.377 | 97.27 | 86.06 | 1.01 | 0.99 |
| bball_drive_event_0-hmm_drive_0 | cmdstan (v3 cmdstan) | 3/3 | 3/3 | 64.579 | 36.321 | 0.56 | 0.41 | 1.78 | 1.36 |
| bball_drive_event_0-hmm_drive_0 | nutpie (v3 nutpie) | 3/3 | 1/3 | 67.016 | 6.068 | 0.09 | 0.10 | 0.99 | 1.06 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da (v3 owalnuts-da) | 0/3 | 1/3 | 9.076 | 7.110 | 0.78 | 0.74 | 1.11 | 0.99 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da-stanreg (v3 owalnuts-da) | 0/3 | 0/3 | 9.076 | 10.094 | 1.11 | 1.12 | 0.92 | 0.86 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan (v3 cmdstan) | 0/3 | 0/3 | 12.837 | 14.212 | 1.11 | 1.27 | 1.07 | 0.99 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie (v3 nutpie) | 0/3 | 0/3 | 4.658 | 6.995 | 1.50 | 1.72 | 1.02 | 1.03 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da (v3 owalnuts-da) | 3/3 | 2/3 | 3.306 | 2.701 | 0.82 | 0.60 | 1.46 | 1.17 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da-stanreg (v3 owalnuts-da) | 3/3 | 2/3 | 3.306 | 2.506 | 0.76 | 0.50 | 1.51 | 1.09 |
| hudson_lynx_hare-lotka_volterra | cmdstan (v3 cmdstan) | 3/3 | 1/3 | 3.479 | 3.804 | 1.09 | 1.14 | 1.09 | 1.03 |
| hudson_lynx_hare-lotka_volterra | nutpie (v3 nutpie) | 0/3 | 0/3 | — | — | — | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da (v3 owalnuts-da) | 0/3 | 0/3 | 0.069 | — | — | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da-stanreg (v3 owalnuts-da) | 0/3 | 0/3 | 0.069 | — | — | — | — | — |
| mcycle_gp-accel_gp | cmdstan (v3 cmdstan) | 0/3 | 0/3 | 0.210 | — | — | — | — | — |
| mcycle_gp-accel_gp | nutpie (v3 nutpie) | 0/3 | 0/3 | 0.194 | — | — | — | — | — |

| arm | v3 cells passed | v4 cells passed | geomean ESS/grad v4/v3 | geomean ESS/s v4/v3 |
|---|---:|---:|---:|---:|
| owalnuts-da (v3 owalnuts-da) | 35 | 39 | 1.22 | 1.00 |
| owalnuts-da-stanreg (v3 owalnuts-da) | 35 | 33 | 1.42 | 1.17 |
| cmdstan (v3 cmdstan) | 37 | 34 | 0.51 | 0.43 |
| nutpie (v3 nutpie) | 31 | 28 | 0.84 | 0.84 |

## Retained transitions that refined (fraction with selected refinement level > 0; seed medians over the four chains' 4,000 retained transitions)

| model | owalnuts-da | da at level 5-8 | owalnuts-da-stanreg |
|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 0.0545 | 0.00000 | 0.0593 |
| eight_schools-eight_schools_centered | 0.2820 | 0.00477 | 0.2703 |
| diamonds-diamonds | 0.0083 | 0.00000 | 0.0113 |
| earnings-logearn_interaction | 0.0243 | 0.00000 | 0.0103 |
| mesquite-logmesquite_logvash | 0.0421 | 0.00000 | 0.0345 |
| kidiq-kidscore_momhsiq | 0.0093 | 0.00000 | 0.0053 |
| sblrc-blr | 0.0301 | 0.00000 | 0.0125 |
| nes2000-nes | 0.0035 | 0.00000 | 0.0070 |
| arK-arK | 0.0103 | 0.00000 | 0.0138 |
| arma-arma11 | 0.0229 | 0.00000 | 0.0103 |
| garch-garch11 | 0.0283 | 0.00000 | 0.0356 |
| gp_pois_regr-gp_pois_regr | 0.0505 | 0.00000 | 0.0907 |
| hmm_example-hmm_example | 0.0168 | 0.00000 | 0.0143 |
| bball_drive_event_0-hmm_drive_0 | 0.0073 | 0.00000 | 0.0209 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.0776 | 0.00000 | 0.0596 |
| hudson_lynx_hare-lotka_volterra | 0.0388 | 0.00000 | 0.0497 |
| mcycle_gp-accel_gp | — | — | — |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_da_gate_passes_ge_35_of_51 | 39 | True |
| P2_da_geomean_bulk_ess_per_gradient_vs_cmdstan_within_0.9_1.1x_of_v3_0.344 | 0.845 | False |
| P3_stanreg_over_da_bulk_ess_per_gradient_ge_2x_on_sblrc_and_earnings | {'sblrc': 7.755902106804, 'earnings': 0.35061056001790025} | False |
| P4_stanreg_over_da_geomean_ge_1.1_and_no_model_below_0.8 | {'geomean': 1.1581568222777758, 'min_model': 'earnings-logearn_interaction', 'min_ratio': 0.35061056001790025, 'models_below_0.8': {'diamonds-diamonds': 0.7135792476346928, 'earnings-logearn_interaction': 0.35061056001790025}} | False |
| P5_da_wall_per_gradient_le_1.0x_cmdstan | 0.694 | True |
| default_rule_stanreg_ge_1.1_geomean_no_model_below_0.8_no_gate_lost | {'geomean': 1.1581568222777758, 'models_below_0.8': {'diamonds-diamonds': 0.7135792476346928, 'earnings-logearn_interaction': 0.35061056001790025}, 'gates_lost': ['diamonds-diamonds', 'earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'bball_drive_event_0-hmm_drive_0', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs'], 'da_cells': 39, 'stanreg_cells': 33} | False |
| reported_max_refinement_levels_in_cells | [8] | reported |
| reported_da_refined_fraction_per_model | {'eight_schools-eight_schools_noncentered': {'da': 0.054503582395087, 'da_beyond_level_4': 0.0, 'stanreg': 0.05930470347648262}, 'eight_schools-eight_schools_centered': {'da': 0.2819698173153296, 'da_beyond_level_4': 0.004765687053216839, 'stanreg': 0.2702702702702703}, 'diamonds-diamonds': {'da': 0.008274824473420261, 'da_beyond_level_4': 0.0, 'stanreg': 0.011303692539562924}, 'earnings-logearn_interaction': {'da': 0.024329069475796338, 'da_beyond_level_4': 0.0, 'stanreg': 0.010288582183186951}, 'mesquite-logmesquite_logvash': {'da': 0.04206791687785099, 'da_beyond_level_4': 0.0, 'stanreg': 0.034482758620689655}, 'kidiq-kidscore_momhsiq': {'da': 0.009282488710486703, 'da_beyond_level_4': 0.0, 'stanreg': 0.00526579739217653}, 'sblrc-blr': {'da': 0.03009027081243731, 'da_beyond_level_4': 0.0, 'stanreg': 0.01252191334835963}, 'nes2000-nes': {'da': 0.003504380475594493, 'da_beyond_level_4': 0.0, 'stanreg': 0.007017543859649123}, 'arK-arK': {'da': 0.010270541082164329, 'da_beyond_level_4': 0.0, 'stanreg': 0.013822568484543855}, 'arma-arma11': {'da': 0.022870067856245287, 'da_beyond_level_4': 0.0, 'stanreg': 0.01029633350075339}, 'garch-garch11': {'da': 0.028268551236749116, 'da_beyond_level_4': 0.0, 'stanreg': 0.035641547861507125}, 'gp_pois_regr-gp_pois_regr': {'da': 0.050505050505050504, 'da_beyond_level_4': 0.0, 'stanreg': 0.09074642126789366}, 'hmm_example-hmm_example': {'da': 0.016813048933500628, 'da_beyond_level_4': 0.0, 'stanreg': 0.014285714285714285}, 'bball_drive_event_0-hmm_drive_0': {'da': 0.007259073842302879, 'da_beyond_level_4': 0.0, 'stanreg': 0.020906801007556677}, 'one_comp_mm_elim_abs-one_comp_mm_elim_abs': {'da': 0.07763975155279502, 'da_beyond_level_4': 0.0, 'stanreg': 0.05960603734970581}, 'hudson_lynx_hare-lotka_volterra': {'da': 0.038751887267237044, 'da_beyond_level_4': 0.0, 'stanreg': 0.0497223624432105}, 'mcycle_gp-accel_gp': {'da': None, 'da_beyond_level_4': None, 'stanreg': None}} | reported |
| reported_da_frozen_cells | ['hudson_lynx_hare-lotka_volterra/83102'] | reported |
| reported_owalnuts_cells_not_ok | [] | reported |
