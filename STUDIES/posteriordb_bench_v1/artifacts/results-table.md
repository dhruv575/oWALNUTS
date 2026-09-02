# posteriordb benchmark v1 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.17 | 74,795 | 1,718 | 1,545 | 10,917.8 | 9,638.5 | 22.976 | 1.0022 | 0,0,0 | 1.42 |
| eight_schools-eight_schools_noncentered | owalnuts-paper | 3/3 | 0.15 | 67,543 | 1,488 | 1,459 | 9,796.1 | 9,684.9 | 21.789 | 1.0027 | 0,0,0 | 1.57 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 0.17 | 74,036 | 2,406 | 1,803 | 14,306.1 | 10,860.1 | 32.473 | 1.0021 | 0,1,1 | 1.03 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.16 | 55,792 | 2,259 | 1,577 | 13,983.3 | 11,187.0 | 40.495 | 1.0026 | 2,2,1 | 1.40 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.93 | 160,423 | 84 | 128 | 91.0 | 139.4 | 0.467 | 1.0432 | 0,4,1 | 1.49 |
| eight_schools-eight_schools_centered | owalnuts-paper | 0/3 | 0.48 | 145,807 | 78 | 164 | 171.1 | 194.0 | 0.525 | 1.0374 | 10,2,27 | 0.92 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.22 | 168,091 | 120 | 57 | 555.6 | 244.0 | 0.641 | 1.0359 | 93,54,74 | 2.03 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 1.08 | 111,345 | 180 | 129 | 154.1 | 127.7 | 1.599 | 1.0267 | 20,40,57 | 2.88 |
| diamonds-diamonds | owalnuts-da | 0/3 | 26.57 | 1,574,768 | 35 | 78 | 1.3 | 2.9 | 0.022 | 1.0946 | 0,0,0 | 2.08 |
| diamonds-diamonds | owalnuts-paper | 0/3 | 2.78 | 128,000 | 4 | 4 | 1.4 | 1.4 | 0.032 | — | 2000,4000,3000 | 21.05 |
| diamonds-diamonds | cmdstan | 3/3 | 89.43 | 6,487,941 | 1,364 | 1,926 | 15.2 | 22.8 | 0.215 | 1.0030 | 0,0,0 | 2.19 |
| diamonds-diamonds | nutpie | 1/3 | 34.27 | 2,096,006 | 338 | 603 | 11.7 | 18.1 | 0.163 | 1.0123 | 0,0,0 | 2.43 |
| earnings-logearn_interaction | owalnuts-da | 0/3 | 18.99 | 1,512,495 | 22 | 45 | 1.1 | 2.3 | 0.015 | 1.1287 | 0,0,0 | 1.21 |
| earnings-logearn_interaction | owalnuts-paper | 0/3 | 1.32 | 128,000 | 4 | 4 | 3.1 | 3.1 | 0.032 | — | 4000,4000,4000 | 14.77 |
| earnings-logearn_interaction | cmdstan | 3/3 | 11.43 | 1,285,739 | 1,069 | 1,276 | 89.7 | 116.6 | 0.779 | 1.0031 | 0,0,0 | 1.42 |
| earnings-logearn_interaction | nutpie | 2/3 | 8.08 | 737,825 | 653 | 790 | 78.3 | 97.8 | 0.884 | 1.0067 | 0,0,0 | 2.13 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.84 | 328,345 | 928 | 1,180 | 1,115.9 | 1,399.9 | 2.827 | 1.0047 | 0,0,0 | 0.90 |
| mesquite-logmesquite_logvash | owalnuts-paper | 0/3 | 0.68 | 219,915 | 7 | 4 | 8.8 | 5.9 | 0.026 | 1.5431 | 1000,0,0 | 1.20 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.30 | 365,746 | 1,444 | 1,798 | 4,747.9 | 5,027.6 | 3.841 | 1.0023 | 0,0,0 | 1.18 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.42 | 197,131 | 839 | 909 | 2,006.9 | 2,149.3 | 4.255 | 1.0053 | 0,0,0 | 1.13 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.32 | 329,242 | 959 | 928 | 660.8 | 705.9 | 2.668 | 1.0049 | 0,0,0 | 1.23 |
| kidiq-kidscore_momhsiq | owalnuts-paper | 0/3 | 0.44 | 128,000 | 4 | 4 | 9.2 | 9.2 | 0.032 | — | 4000,4000,4000 | 43.18 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 0.82 | 360,707 | 1,361 | 1,729 | 1,653.9 | 2,033.6 | 3.717 | 1.0031 | 0,0,0 | 0.95 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 0.62 | 139,016 | 699 | 1,166 | 1,122.6 | 1,830.0 | 5.019 | 1.0053 | 0,0,0 | 1.94 |
| sblrc-blr | owalnuts-da | 0/3 | 0.98 | 446,149 | 149 | 208 | 137.4 | 191.8 | 0.295 | 1.3058 | 0,0 | 1.24 |
| sblrc-blr | owalnuts-paper | 0/3 | 0.56 | 128,000 | 4 | 4 | 7.3 | 7.3 | 0.032 | — | 2000,4000,3000 | 4.47 |
| sblrc-blr | cmdstan | 2/3 | 0.15 | 124,574 | 901 | 1,113 | 4,031.6 | 5,319.2 | 6.980 | 1.0040 | 0,0,0 | 1.40 |
| sblrc-blr | nutpie | 3/3 | 0.12 | 56,993 | 883 | 1,553 | 6,704.1 | 12,985.5 | 15.500 | 1.0044 | 0,0,0 | 1.39 |
| nes2000-nes | owalnuts-da | 3/3 | 5.40 | 413,384 | 1,037 | 1,258 | 192.2 | 229.5 | 2.401 | 1.0057 | 0,0,0 | 1.51 |
| nes2000-nes | owalnuts-paper | 0/3 | 1.27 | 128,000 | 4 | 4 | 3.2 | 3.2 | 0.032 | — | 1000,3000,0 | 2.61 |
| nes2000-nes | cmdstan | 3/3 | 6.03 | 403,211 | 1,940 | 2,184 | 321.8 | 374.4 | 4.812 | 1.0024 | 0,0,0 | 1.98 |
| nes2000-nes | nutpie | 3/3 | 3.77 | 236,699 | 1,294 | 1,605 | 359.0 | 409.3 | 5.470 | 1.0023 | 0,0,0 | 2.16 |
| arK-arK | owalnuts-da | 3/3 | 10.54 | 241,119 | 1,871 | 1,935 | 171.6 | 183.5 | 7.770 | 1.0028 | 0,0,0 | 0.97 |
| arK-arK | owalnuts-paper | 1/3 | 27.02 | 312,701 | 7 | 4 | 0.2 | 0.1 | 0.018 | 1.5305 | 0,0,0 | 1.76 |
| arK-arK | cmdstan | 3/3 | 1.03 | 238,570 | 2,585 | 2,235 | 2,341.5 | 2,173.0 | 10.607 | 1.0032 | 0,0,0 | 1.30 |
| arK-arK | nutpie | 3/3 | 6.56 | 174,267 | 1,958 | 1,832 | 284.1 | 279.1 | 11.233 | 1.0027 | 0,0,0 | 2.28 |
| arma-arma11 | owalnuts-da | error | — | — | — | — | — | — | — | — |  | — |
| arma-arma11 | owalnuts-paper | error | — | — | — | — | — | — | — | — |  | — |
| arma-arma11 | cmdstan | 2/3 | 0.73 | 67,839 | 3,052 | 2,639 | 5,184.6 | 3,901.2 | 44.984 | 1.0022 | 0,0,0 | 1.69 |
| arma-arma11 | nutpie | 2/3 | 1.24 | 31,527 | 4,525 | 2,769 | 3,652.6 | 2,235.0 | 143.520 | 1.0028 | 0,0,0 | 1.21 |
| garch-garch11 | owalnuts-da | 3/3 | 3.42 | 80,611 | 1,055 | 1,495 | 319.5 | 435.9 | 13.369 | 1.0048 | 0,0,0 | 0.92 |
| garch-garch11 | owalnuts-paper | 3/3 | 3.13 | 74,702 | 924 | 1,350 | 270.9 | 335.1 | 11.973 | 1.0041 | 0,0,0 | 0.73 |
| garch-garch11 | cmdstan | 3/3 | 0.64 | 88,707 | 1,778 | 2,114 | 2,900.7 | 3,295.7 | 20.259 | 1.0015 | 0,0,0 | 1.35 |
| garch-garch11 | nutpie | 3/3 | 2.50 | 61,668 | 1,503 | 1,630 | 680.8 | 655.8 | 24.176 | 1.0030 | 0,0,0 | 0.94 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 3.66 | 1,063,866 | 611 | 819 | 179.9 | 241.2 | 0.635 | 1.0063 | 0,0,0 | 1.53 |
| gp_pois_regr-gp_pois_regr | owalnuts-paper | error | — | — | — | — | — | — | — | — |  | — |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 1.73 | 1,319,609 | 1,436 | 1,807 | 781.1 | 1,002.0 | 1.088 | 1.0051 | 4,24,13 | 1.89 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 2.15 | 795,088 | 835 | 720 | 388.1 | 334.6 | 1.046 | 1.0034 | 175,136,143 | 1.84 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 33.01 | 204,717 | 1,720 | 1,617 | 50.2 | 49.0 | 8.310 | 1.0035 | 0,0,0 | 1.42 |
| hmm_example-hmm_example | owalnuts-paper | 0/3 | 97.04 | 292,920 | 4 | 4 | 0.1 | 0.0 | 0.015 | 3.4079 | 0,0,0 | 1.98 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.52 | 100,959 | 2,278 | 2,175 | 1,494.5 | 1,443.6 | 22.721 | 1.0031 | 0,0,0 | 1.29 |
| hmm_example-hmm_example | nutpie | 3/3 | 8.07 | 57,005 | 1,526 | 1,743 | 185.5 | 232.5 | 26.604 | 1.0018 | 0,0,0 | 1.52 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 33.81 | 93,709 | 728 | 451 | 20.4 | 13.3 | 7.500 | 1.0051 | 0,0,0 | 1.91 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-paper | 0/3 | 45.64 | 128,000 | 4 | 4 | 0.1 | 0.1 | 0.032 | — | 0,0,0 | 6.15 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 3/3 | 4.58 | 74,905 | 4,194 | 1,936 | 975.6 | 449.3 | 59.655 | 1.0024 | 0,0,0 | 1.28 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 2/3 | 14.71 | 42,847 | 3,115 | 1,306 | 163.6 | 68.5 | 71.551 | 1.0036 | 0,546,0 | 1.17 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 45.90 | 66,456 | 267 | 91 | 6.0 | 2.0 | 3.946 | 1.0151 | 0,0,0 | 1.03 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-paper | 1/3 | 321.07 | 216,045 | 148 | 32 | 1.5 | 0.7 | 2.241 | 1.0508 | 0,0,0 | 2.36 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 16.97 | 69,334 | 403 | 65 | 23.7 | 3.8 | 5.425 | 1.0159 | 3,8,46 | 2.17 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 39.64 | 50,605 | 958 | 390 | 24.2 | 9.4 | 19.394 | 1.0057 | 13,14,11 | 4.40 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 1/3 | 9.29 | 271,158 | 957 | 1,117 | 103.0 | 120.2 | 3.529 | 1.0046 | 0 | 1.07 |
| hudson_lynx_hare-lotka_volterra | owalnuts-paper | 0/3 | 17.33 | 155,831 | 4 | 4 | 0.2 | 0.2 | 0.026 | 9.4245 | 0 | 3.46 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 2/3 | 7.86 | 268,021 | 739 | 1,221 | 105.8 | 155.2 | 2.756 | 1.0062 | 0,0,0 | 1.22 |
| hudson_lynx_hare-lotka_volterra | nutpie | 1/3 | 5.35 | 137,485 | 185 | 420 | 32.0 | 72.8 | 1.364 | 1.0982 | 417,0,423 | 1.75 |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 4.82 | 774,402 | 7 | 11 | 1.4 | 2.1 | 0.009 | 1.6387 | 1000,0,0 | 4.10 |
| mcycle_gp-accel_gp | owalnuts-paper | 0/3 | 0.85 | 128,000 | 4 | 4 | 4.8 | 4.8 | 0.032 | — | 2000,3000 | 53.39 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 24.66 | 5,656,496 | 1,380 | 930 | 56.6 | 37.4 | 0.230 | 1.0053 | 60,202,44 | 3.07 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 17.11 | 3,606,539 | 692 | 801 | 40.4 | 47.5 | 0.191 | 1.0070 | 149,118,111 | 2.83 |

## Appendix C versus dual averaging (paper / da, seed medians)

| model | r bulk ESS/grad | r tail ESS/grad | r bulk ESS/s | r gradients | da gates | paper gates | at least as good |
|---|---:|---:|---:|---:|---|---|---|
| eight_schools-eight_schools_noncentered | 0.948 | 1.060 | 0.897 | 0.903 | 3/3 | 3/3 | True |
| eight_schools-eight_schools_centered | 1.124 | 1.362 | 1.881 | 0.909 | 0/3 | 0/3 | True |
| diamonds-diamonds | 1.408 | 0.634 | 1.092 | 0.081 | 0/3 | 0/3 | True |
| earnings-logearn_interaction | 2.160 | 1.050 | 2.752 | 0.085 | 0/3 | 0/3 | True |
| mesquite-logmesquite_logvash | 0.009 | 0.005 | 0.008 | 0.670 | 3/3 | 0/3 | False |
| kidiq-kidscore_momhsiq | 0.012 | 0.011 | 0.014 | 0.389 | 3/3 | 0/3 | False |
| sblrc-blr | 0.107 | 0.076 | 0.053 | 0.287 | 0/3 | 0/3 | False |
| nes2000-nes | 0.013 | 0.010 | 0.017 | 0.310 | 3/3 | 0/3 | False |
| arK-arK | 0.002 | 0.002 | 0.001 | 1.297 | 3/3 | 1/3 | False |
| arma-arma11 | — | — | — | — | 0/3 | 0/3 | False |
| garch-garch11 | 0.896 | 0.788 | 0.848 | 0.927 | 3/3 | 3/3 | False |
| gp_pois_regr-gp_pois_regr | — | — | — | — | 2/3 | 0/3 | False |
| hmm_example-hmm_example | 0.002 | 0.002 | 0.001 | 1.431 | 3/3 | 0/3 | False |
| bball_drive_event_0-hmm_drive_0 | 0.004 | 0.007 | 0.004 | 1.366 | 2/3 | 0/3 | False |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.568 | 0.356 | 0.244 | 3.251 | 0/3 | 1/3 | False |
| hudson_lynx_hare-lotka_volterra | 0.007 | 0.006 | 0.002 | 0.575 | 1/3 | 0/3 | False |
| mcycle_gp-accel_gp | 3.436 | 2.002 | 3.436 | 0.165 | 0/3 | 0/3 | True |

Geometric mean over 12 models: bulk ESS/grad **0.077**, tail ESS/grad 0.061, bulk ESS/s 0.067, total gradients 0.624. Losing models: ['mesquite-logmesquite_logvash', 'kidiq-kidscore_momhsiq', 'nes2000-nes', 'arK-arK', 'garch-garch11', 'hmm_example-hmm_example', 'bball_drive_event_0-hmm_drive_0', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs']. Preregistered decision rule -> recommend Appendix C as default: **False**.

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wins ESS/s | wins ESS/grad |
|---|---:|---:|---:|---:|---:|
| owalnuts-da_over_cmdstan | 14 | 0.316 | 0.114 | 0 | 0 |
| owalnuts-paper_over_cmdstan | 13 | 0.024 | 0.007 | 0 | 0 |
| owalnuts-da_over_nutpie | 14 | 0.253 | 0.255 | 0 | 0 |
| owalnuts-paper_over_nutpie | 13 | 0.017 | 0.015 | 1 | 0 |
