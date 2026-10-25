# WP48 dense metric on posteriordb — results

Seed medians over 3 seeds. `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences. `kappa` = condition number of the pooled retained unconstrained posterior covariance in the installed metric's whitened coordinates (median over chains). Walls are CONTENDED (about ten agents on 16 cores); `quiet ESS/s` uses the separately measured gradient and kernel costs.

| model | d | arm | gates | grads | min bulk ESS | bulk ESS/grad x1e3 | ratio vs diag | step | cap frac | kappa | max R-hat | div | max abs z | wall s (contended) | quiet ESS/s |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 10 | owalnuts-diag | 3/3 | 72,013 | 2,171 | 30.153 | 1.00 | 0.49 | 0.000 | 2.07 | 1.0023 | 0,0,0 | 1.52 | 0.25 | 39,184.5 |
| eight_schools-eight_schools_noncentered | 10 | owalnuts-dense | 3/3 | 240,784 | 1,282 | 3.781 | 0.13 | 0.158 | 0.000 | 88.2 | 1.0039 | 0,0,0 | 1.29 | 0.81 | 3,332.1 |
| eight_schools-eight_schools_noncentered | 10 | owalnuts-dense-seeded | 3/3 | 73,248 | 2,252 | 29.128 | 0.97 | 0.495 | 0.000 | 2.01 | 1.0025 | 0,0,0 | 1.76 | 0.47 | 35,677.0 |
| eight_schools-eight_schools_noncentered | 10 | owalnuts-dense-stan | 3/3 | 77,783 | 2,132 | 25.766 | 0.85 | 0.497 | 0.000 | 2.07 | 1.0031 | 0,0,0 | 1.28 | 0.45 | 30,563.8 |
| eight_schools-eight_schools_centered | 10 | owalnuts-diag | 0/3 | 308,380 | 30 | 0.096 | 1.00 | 0.171 | 0.000 | 24.1 | 1.0955 | 0,0,0 | 1.24 | 1.51 | 64.6 |
| eight_schools-eight_schools_centered | 10 | owalnuts-dense | 0/3 | 1,230,195 | 9 | 0.007 | 0.07 | 0.0408 | 0.160 | 771 | 1.3601 | 0,0,3 | 1.71 | 7.07 | 3.1 |
| eight_schools-eight_schools_centered | 10 | owalnuts-dense-seeded | 0/3 | 234,476 | 131 | 0.557 | 5.78 | 0.151 | 0.000 | 3.68 | 1.0308 | 0,0,0 | 1.21 | 1.40 | 602.8 |
| eight_schools-eight_schools_centered | 10 | owalnuts-dense-stan | 0/3 | 268,671 | 62 | 0.231 | 2.40 | 0.231 | 0.000 | 5.22 | 1.0480 | 0,0,0 | 1.61 | 1.37 | 188.9 |
| diamonds-diamonds | 26 | owalnuts-diag | 3/3 | 6,683,541 | 1,275 | 0.188 | 1.00 | 0.00347 | 0.103 | 2.51e+05 | 1.0037 | 0,0,0 | 2.10 | 1094.61 | 15.2 |
| diamonds-diamonds | 26 | owalnuts-dense | 2/3 | 931,340 | 562 | 0.592 | 3.14 | 0.0291 | 0.005 | 1.07e+05 | 1.0099 | 0,0,0 | 1.84 | 305.97 | 33.0 |
| diamonds-diamonds | 26 | owalnuts-dense-seeded | 3/3 | 1,118,561 | 1,941 | 1.696 | 9.00 | 0.0298 | 0.000 | 1.36e+03 | 1.0035 | 0,0,0 | 3.02 | 130.26 | 134.7 |
| diamonds-diamonds | 26 | owalnuts-dense-stan | 3/3 | 1,686,351 | 1,692 | 0.994 | 5.28 | 0.0101 | 0.000 | 1.2e+04 | 1.0029 | 0,0,0 | 2.11 | 202.15 | 63.9 |
| diamonds-diamonds | 26 | cmdstan-dense | 3/3 | 200,624 | 4,129 | 20.579 | 109.21 | 0.291 | 0.000 | 17.3 | 1.0027 | 0,0,0 | 2.85 | 3.14 | — |
| earnings-logearn_interaction | 5 | owalnuts-diag | 3/3 | 1,480,892 | 956 | 0.668 | 1.00 | 0.0165 | 0.000 | 1.24e+04 | 1.0040 | 0,0,0 | 0.77 | 168.24 | 52.4 |
| earnings-logearn_interaction | 5 | owalnuts-dense | 0/3 | 2,414,769 | 9 | 0.003 | 0.00 | 0.00362 | 0.197 | 2.8e+07 | 1.3933 | 0,0,0 | 1.32 | 327.41 | 0.2 |
| earnings-logearn_interaction | 5 | owalnuts-dense-seeded | 3/3 | 3,867,891 | 797 | 0.206 | 0.31 | 0.00202 | 0.281 | 2.22e+05 | 1.0040 | 0,0,0 | 1.50 | 320.56 | 17.0 |
| earnings-logearn_interaction | 5 | owalnuts-dense-stan | 3/3 | 540,694 | 1,899 | 3.583 | 5.36 | 0.104 | 0.000 | 93.7 | 1.0028 | 0,0,0 | 1.62 | 41.78 | 216.0 |
| mesquite-logmesquite_logvash | 7 | owalnuts-diag | 3/3 | 377,935 | 1,283 | 3.437 | 1.00 | 0.0801 | 0.000 | 528 | 1.0021 | 0,0,0 | 1.48 | 9.27 | 1,955.4 |
| mesquite-logmesquite_logvash | 7 | owalnuts-dense | 3/3 | 208,579 | 1,026 | 4.076 | 1.19 | 0.088 | 0.000 | 217 | 1.0046 | 0,0,0 | 1.99 | 6.20 | 2,317.8 |
| mesquite-logmesquite_logvash | 7 | owalnuts-dense-seeded | 3/3 | 109,102 | 2,920 | 26.702 | 7.77 | 0.376 | 0.000 | 7.57 | 1.0025 | 0,0,0 | 0.71 | 2.69 | 15,076.9 |
| mesquite-logmesquite_logvash | 7 | owalnuts-dense-stan | 3/3 | 78,579 | 4,580 | 58.282 | 16.96 | 0.64 | 0.000 | 1.83 | 1.0044 | 0,0,0 | 1.51 | 1.89 | 30,988.1 |
| kidiq-kidscore_momhsiq | 4 | owalnuts-diag | 3/3 | 399,896 | 1,445 | 4.043 | 1.00 | 0.0905 | 0.000 | 189 | 1.0026 | 0,0,0 | 0.75 | 21.52 | 735.7 |
| kidiq-kidscore_momhsiq | 4 | owalnuts-dense | 0/3 | 984,161 | 134 | 0.138 | 0.03 | 0.00915 | 0.039 | 3.28e+05 | 1.0966 | 0,0,0 | 1.17 | 43.42 | 15.0 |
| kidiq-kidscore_momhsiq | 4 | owalnuts-dense-seeded | 3/3 | 1,156,572 | 960 | 0.830 | 0.21 | 0.0114 | 0.000 | 7.62e+03 | 1.0050 | 0,0,0 | 1.00 | 36.87 | 146.5 |
| kidiq-kidscore_momhsiq | 4 | owalnuts-dense-stan | 3/3 | 149,693 | 3,997 | 26.703 | 6.60 | 0.721 | 0.000 | 1.43 | 1.0017 | 0,0,0 | 0.80 | 6.54 | 3,752.5 |
| sblrc-blr | 6 | owalnuts-diag | 3/3 | 151,400 | 875 | 6.196 | 1.00 | 0.104 | 0.000 | 62.3 | 1.0029 | 0,0,0 | 2.14 | 1.43 | 5,513.0 |
| sblrc-blr | 6 | owalnuts-dense | 0/3 | 175,186 | 296 | 1.780 | 0.29 | 0.0509 | 0.000 | 496 | 1.0209 | 212,0,0 | 0.84 | 2.95 | 1,012.4 |
| sblrc-blr | 6 | owalnuts-dense-seeded | 3/3 | 175,613 | 427 | 2.340 | 0.38 | 0.052 | 0.000 | 263 | 1.0076 | 0,0,0 | 1.41 | 2.17 | 2,045.8 |
| sblrc-blr | 6 | owalnuts-dense-stan | 3/3 | 170,835 | 724 | 4.156 | 0.67 | 0.105 | 0.000 | 61.3 | 1.0050 | 0,0,0 | 1.19 | 4.40 | 2,665.5 |
| nes2000-nes | 10 | owalnuts-diag | 3/3 | 421,562 | 1,799 | 4.266 | 1.00 | 0.0808 | 0.000 | 435 | 1.0031 | 0,0,0 | 1.73 | 43.59 | 356.4 |
| nes2000-nes | 10 | owalnuts-dense | 2/3 | 237,260 | 484 | 1.894 | 0.44 | 0.12 | 0.000 | 1.78e+03 | 1.0081 | 0,0,0 | 2.70 | 20.79 | 101.5 |
| nes2000-nes | 10 | owalnuts-dense-seeded | 3/3 | 217,671 | 3,014 | 13.664 | 3.20 | 0.174 | 0.000 | 40.3 | 1.0017 | 0,0,0 | 1.51 | 17.31 | 1,084.8 |
| nes2000-nes | 10 | owalnuts-dense-stan | 3/3 | 101,317 | 7,234 | 71.400 | 16.73 | 0.625 | 0.000 | 2.11 | 1.0030 | 0,0,0 | 1.91 | 7.52 | 5,827.6 |
| arK-arK | 7 | owalnuts-diag | 3/3 | 260,986 | 2,454 | 8.843 | 1.00 | 0.116 | 0.000 | 120 | 1.0032 | 0,0,0 | 1.74 | 14.90 | 1,152.4 |
| arK-arK | 7 | owalnuts-dense | 3/3 | 206,411 | 1,246 | 7.081 | 0.80 | 0.26 | 0.000 | 208 | 1.0029 | 0,0,0 | 1.52 | 12.62 | 687.6 |
| arK-arK | 7 | owalnuts-dense-seeded | 3/3 | 90,934 | 4,027 | 44.281 | 5.01 | 0.463 | 0.000 | 4.64 | 1.0023 | 0,0,0 | 1.52 | 3.88 | 5,813.2 |
| arK-arK | 7 | owalnuts-dense-stan | 3/3 | 78,277 | 5,115 | 67.008 | 7.58 | 0.665 | 0.000 | 1.79 | 1.0034 | 0,0,0 | 1.65 | 3.52 | 8,511.5 |
| arma-arma11 | 4 | owalnuts-diag | 3/3 | 110,102 | 3,329 | 30.237 | 1.00 | 0.694 | 0.000 | 1.74 | 1.0020 | 0,0,0 | 0.92 | 6.03 | 2,636.1 |
| arma-arma11 | 4 | owalnuts-dense | 2/3 | 142,355 | 1,784 | 12.530 | 0.41 | 0.219 | 0.000 | 16.3 | 1.0030 | 0,0,0 | 2.04 | 8.05 | 1,082.4 |
| arma-arma11 | 4 | owalnuts-dense-seeded | 3/3 | 115,583 | 3,371 | 25.928 | 0.86 | 0.653 | 0.000 | 1.88 | 1.0021 | 0,0,0 | 1.09 | 5.51 | 2,271.4 |
| arma-arma11 | 4 | owalnuts-dense-stan | 3/3 | 115,842 | 3,961 | 34.195 | 1.13 | 0.716 | 0.000 | 1.47 | 1.0014 | 0,0,0 | 0.82 | 4.73 | 2,964.7 |
| garch-garch11 | 4 | owalnuts-diag | 3/3 | 95,038 | 1,809 | 19.033 | 1.00 | 0.31 | 0.000 | 8.01 | 1.0031 | 0,0,0 | 0.95 | 4.61 | 2,445.0 |
| garch-garch11 | 4 | owalnuts-dense | 1/3 | 1,416,764 | 7 | 0.005 | 0.00 | 0.136 | 0.248 | 1.14e+04 | 1.5259 | 0,0,0 | 1.43 | 139.73 | 0.2 |
| garch-garch11 | 4 | owalnuts-dense-seeded | 3/3 | 67,143 | 1,887 | 28.102 | 1.48 | 0.414 | 0.000 | 3.11 | 1.0020 | 0,0,0 | 1.01 | 2.70 | 3,580.1 |
| garch-garch11 | 4 | owalnuts-dense-stan | 3/3 | 70,519 | 1,971 | 27.682 | 1.45 | 0.479 | 0.000 | 1.62 | 1.0028 | 0,0,0 | 0.75 | 2.69 | 3,465.0 |
| gp_pois_regr-gp_pois_regr | 13 | owalnuts-diag | 3/3 | 1,189,860 | 736 | 0.658 | 1.00 | 0.0279 | 0.000 | 543 | 1.0080 | 0,0,0 | 1.43 | 48.81 | 156.4 |
| gp_pois_regr-gp_pois_regr | 13 | owalnuts-dense | 0/3 | 923,241 | 13 | 0.014 | 0.02 | 0.0795 | 0.000 | 2.48e+03 | 1.2361 | 0,0,0 | 2.74 | 34.69 | 1.7 |
| gp_pois_regr-gp_pois_regr | 13 | owalnuts-dense-seeded | 3/3 | 593,082 | 1,622 | 2.751 | 4.18 | 0.0656 | 0.000 | 46 | 1.0022 | 0,0,0 | 1.83 | 20.85 | 676.8 |
| gp_pois_regr-gp_pois_regr | 13 | owalnuts-dense-stan | 2/3 | 319,414 | 528 | 1.622 | 2.47 | 0.164 | 0.000 | 3.88 | 1.0095 | 0,0,0 | 1.93 | 12.44 | 371.9 |
| gp_pois_regr-gp_pois_regr | 13 | cmdstan-dense | 0/3 | 314,992 | 632 | 1.945 | 2.96 | 0.155 | 0.000 | 3.39 | 1.0107 | 9,114,10 | 2.52 | 0.65 | — |
| hmm_example-hmm_example | 4 | owalnuts-diag | 3/3 | 123,796 | 1,994 | 14.759 | 1.00 | 0.321 | 0.000 | 17.7 | 1.0019 | 0,0,0 | 1.51 | 10.88 | 1,141.2 |
| hmm_example-hmm_example | 4 | owalnuts-dense | 1/3 | 237,825 | 721 | 2.191 | 0.15 | 0.12 | 0.000 | 1.9e+03 | 1.0064 | 0,0,0 | 1.39 | 21.21 | 135.0 |
| hmm_example-hmm_example | 4 | owalnuts-dense-seeded | 3/3 | 126,899 | 2,603 | 20.516 | 1.39 | 0.282 | 0.000 | 11.3 | 1.0027 | 0,0,0 | 1.52 | 10.87 | 1,737.1 |
| hmm_example-hmm_example | 4 | owalnuts-dense-stan | 3/3 | 83,331 | 3,742 | 44.904 | 3.04 | 0.702 | 0.000 | 1.44 | 1.0013 | 0,0,0 | 1.56 | 5.97 | 3,649.7 |
| bball_drive_event_0-hmm_drive_0 | 6 | owalnuts-diag | 3/3 | 91,876 | 4,289 | 48.674 | 1.00 | 0.637 | 0.000 | 1.88 | 1.0016 | 0,0,0 | 1.91 | 27.74 | 741.4 |
| bball_drive_event_0-hmm_drive_0 | 6 | owalnuts-dense | 0/3 | 217,781 | 29 | 0.117 | 0.00 | 0.108 | 0.000 | 3.88e+05 | 1.0913 | 0,0,0 | 1.22 | 74.29 | 1.4 |
| bball_drive_event_0-hmm_drive_0 | 6 | owalnuts-dense-seeded | 2/3 | 100,340 | 3,438 | 34.266 | 0.70 | 0.522 | 0.000 | 3.27 | 1.0028 | 0,0,0 | 1.92 | 31.67 | 524.0 |
| bball_drive_event_0-hmm_drive_0 | 6 | owalnuts-dense-stan | 3/3 | 107,849 | 4,357 | 40.395 | 0.83 | 0.653 | 0.000 | 1.59 | 1.0023 | 0,0,0 | 1.20 | 31.46 | 567.0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | owalnuts-diag | 1/3 | 83,060 | 657 | 7.534 | 1.00 | 0.371 | 0.000 | 4.85 | 1.0091 | 0,0,0 | 0.87 | 78.46 | 43.0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | owalnuts-dense | 0/3 | 177,440 | 153 | 0.868 | 0.12 | 0.247 | 0.000 | 649 | 1.0161 | 0,0 | 1.34 | 128.00 | 3.2 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | owalnuts-dense-seeded | 2/3 | 67,144 | 1,001 | 14.902 | 1.98 | 0.363 | 0.000 | 4.04 | 1.0055 | 0,0,0 | 3.13 | 46.66 | 95.4 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | owalnuts-dense-stan | 3/3 | 74,794 | 1,088 | 15.147 | 2.01 | 0.433 | 0.000 | 1.73 | 1.0031 | 0,0,0 | 2.50 | 50.81 | 98.8 |
| hudson_lynx_hare-lotka_volterra | 8 | owalnuts-diag | 2/3 | 312,428 | 888 | 2.878 | 1.00 | 0.106 | 0.000 | 272 | 1.0053 | 0,0 | 0.93 | 45.69 | 110.3 |
| hudson_lynx_hare-lotka_volterra | None | owalnuts-dense | error | — | — | — | — | — | — | — | — |  | — | — | — |
| hudson_lynx_hare-lotka_volterra | 8 | owalnuts-dense-seeded | 1/3 | 171,036 | 1,348 | 6.861 | 2.38 | 0.359 | 0.000 | 75 | 1.1295 | 0,0 | 1.16 | 18.55 | 199.7 |
| hudson_lynx_hare-lotka_volterra | 8 | owalnuts-dense-stan | 1/3 | 273,255 | 1,669 | 3.900 | 1.35 | 0.545 | 0.000 | 277 | 1.2359 | 0,0 | 1.45 | 27.78 | 64.1 |
| mcycle_gp-accel_gp | 66 | owalnuts-diag | 0/3 | 2,720,642 | 304 | 0.112 | 1.00 | 0.0083 | 0.000 | 1.13e+03 | 1.0120 | 0,0,0 | 3.75 | 50.00 | 14.1 |
| mcycle_gp-accel_gp | 66 | owalnuts-dense | 0/3 | 800,103 | 5 | 0.009 | 0.08 | 0.0289 | 0.000 | 1.58e+06 | 2.8036 | 0,0,0 | 3.73 | 19.94 | 0.5 |
| mcycle_gp-accel_gp | 66 | owalnuts-dense-seeded | 0/3 | 1,948,493 | 336 | 0.179 | 1.60 | 0.0106 | 0.000 | 559 | 1.0177 | 0,0,0 | 2.66 | 40.35 | 17.7 |
| mcycle_gp-accel_gp | 66 | owalnuts-dense-stan | 0/3 | 1,209,818 | 103 | 0.077 | 0.69 | 0.0311 | 0.000 | 80.8 | 1.0317 | 0,0,0 | 2.90 | 23.02 | 9.1 |
| mcycle_gp-accel_gp | 66 | cmdstan-dense | 0/3 | 1,967,893 | 309 | 0.157 | 1.40 | 0.039 | 0.000 | 23.1 | 1.0179 | 228,315,130 | 3.03 | 10.53 | — |

## owalnuts-dense versus owalnuts-diag

- geomean ESS/grad ratio, all complete models: 0.082; non-target models: 0.069; quiet ESS/s: 0.054
- gates 17 versus diag 42
- documentation decision: advised on none -> not supported
- auto rule d <= 100 and max|corr| >= 0.6: selected ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'mesquite-logmesquite_logvash', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'nes2000-nes', 'arK-arK', 'garch-garch11', 'gp_pois_regr-gp_pois_regr', 'hmm_example-hmm_example', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; winners []; losers ['eight_schools-eight_schools_noncentered', 'eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'nes2000-nes', 'arK-arK', 'arma-arma11', 'garch-garch11', 'gp_pois_regr-gp_pois_regr', 'hmm_example-hmm_example', 'bball_drive_event_0-hmm_drive_0', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; false positives ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'nes2000-nes', 'arK-arK', 'garch-garch11', 'gp_pois_regr-gp_pois_regr', 'hmm_example-hmm_example', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; missed []; recommend auto: False

| model | ESS/grad ratio | contended ESS/s ratio | quiet ESS/s ratio | gates | diag gates | class |
|---|---:|---:|---:|---|---|---|
| eight_schools-eight_schools_noncentered | 0.13 | 0.18 | 0.09 | 3/3 | 3/3 | loser |
| eight_schools-eight_schools_centered | 0.07 | 0.07 | 0.05 | 0/3 | 0/3 | loser |
| diamonds-diamonds | 3.14 | 1.91 | 2.17 | 2/3 | 3/3 | loser |
| earnings-logearn_interaction | 0.00 | 0.00 | 0.00 | 0/3 | 3/3 | loser |
| mesquite-logmesquite_logvash | 1.19 | 1.88 | 1.19 | 3/3 | 3/3 | neutral |
| kidiq-kidscore_momhsiq | 0.03 | 0.07 | 0.02 | 0/3 | 3/3 | loser |
| sblrc-blr | 0.29 | 0.16 | 0.18 | 0/3 | 3/3 | loser |
| nes2000-nes | 0.44 | 0.55 | 0.28 | 2/3 | 3/3 | loser |
| arK-arK | 0.80 | 0.83 | 0.60 | 3/3 | 3/3 | loser |
| arma-arma11 | 0.41 | 0.40 | 0.41 | 2/3 | 3/3 | loser |
| garch-garch11 | 0.00 | 0.00 | 0.00 | 1/3 | 3/3 | loser |
| gp_pois_regr-gp_pois_regr | 0.02 | 0.03 | 0.01 | 0/3 | 3/3 | loser |
| hmm_example-hmm_example | 0.15 | 0.15 | 0.12 | 1/3 | 3/3 | loser |
| bball_drive_event_0-hmm_drive_0 | 0.00 | 0.00 | 0.00 | 0/3 | 3/3 | loser |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.12 | 0.14 | 0.07 | 0/3 | 1/3 | loser |
| hudson_lynx_hare-lotka_volterra | — | — | — | 0/3 | 2/3 | loser |
| mcycle_gp-accel_gp | 0.08 | 0.06 | 0.04 | 0/3 | 0/3 | loser |

## owalnuts-dense-seeded versus owalnuts-diag

- geomean ESS/grad ratio, all complete models: 1.666; non-target models: 1.387; quiet ESS/s: 1.673
- gates 41 versus diag 42
- documentation decision: advised on ['diamonds-diamonds', 'mcycle_gp-accel_gp', 'gp_pois_regr-gp_pois_regr'] -> supported
- auto rule d <= 100 and max|corr| >= 0.6: selected ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'mesquite-logmesquite_logvash', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'nes2000-nes', 'arK-arK', 'garch-garch11', 'gp_pois_regr-gp_pois_regr', 'hmm_example-hmm_example', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; winners ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'mesquite-logmesquite_logvash', 'nes2000-nes', 'arK-arK', 'gp_pois_regr-gp_pois_regr', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'mcycle_gp-accel_gp']; losers ['eight_schools-eight_schools_noncentered', 'earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'arma-arma11', 'bball_drive_event_0-hmm_drive_0', 'hudson_lynx_hare-lotka_volterra']; false positives ['earnings-logearn_interaction', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'hudson_lynx_hare-lotka_volterra']; missed []; recommend auto: False

| model | ESS/grad ratio | contended ESS/s ratio | quiet ESS/s ratio | gates | diag gates | class |
|---|---:|---:|---:|---|---|---|
| eight_schools-eight_schools_noncentered | 0.97 | 0.63 | 0.91 | 3/3 | 3/3 | loser |
| eight_schools-eight_schools_centered | 5.78 | 3.58 | 9.33 | 0/3 | 0/3 | winner |
| diamonds-diamonds | 9.00 | 11.37 | 8.86 | 3/3 | 3/3 | winner |
| earnings-logearn_interaction | 0.31 | 0.40 | 0.32 | 3/3 | 3/3 | loser |
| mesquite-logmesquite_logvash | 7.77 | 7.52 | 7.71 | 3/3 | 3/3 | winner |
| kidiq-kidscore_momhsiq | 0.21 | 0.35 | 0.20 | 3/3 | 3/3 | loser |
| sblrc-blr | 0.38 | 0.39 | 0.37 | 3/3 | 3/3 | loser |
| nes2000-nes | 3.20 | 3.92 | 3.04 | 3/3 | 3/3 | winner |
| arK-arK | 5.01 | 6.21 | 5.04 | 3/3 | 3/3 | winner |
| arma-arma11 | 0.86 | 0.98 | 0.86 | 3/3 | 3/3 | loser |
| garch-garch11 | 1.48 | 1.66 | 1.46 | 3/3 | 3/3 | neutral |
| gp_pois_regr-gp_pois_regr | 4.18 | 5.11 | 4.33 | 3/3 | 3/3 | winner |
| hmm_example-hmm_example | 1.39 | 1.43 | 1.52 | 3/3 | 3/3 | neutral |
| bball_drive_event_0-hmm_drive_0 | 0.70 | 0.67 | 0.71 | 2/3 | 3/3 | loser |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1.98 | 2.57 | 2.22 | 2/3 | 1/3 | winner |
| hudson_lynx_hare-lotka_volterra | 2.38 | 3.40 | 1.81 | 1/3 | 2/3 | loser |
| mcycle_gp-accel_gp | 1.60 | 1.46 | 1.26 | 0/3 | 0/3 | winner |

## owalnuts-dense-stan versus owalnuts-diag

- geomean ESS/grad ratio, all complete models: 2.591; non-target models: 2.715; quiet ESS/s: 2.307
- gates 42 versus diag 42
- documentation decision: advised on ['diamonds-diamonds'] -> mixed
- auto rule d <= 100 and max|corr| >= 0.6: selected ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'mesquite-logmesquite_logvash', 'kidiq-kidscore_momhsiq', 'sblrc-blr', 'nes2000-nes', 'arK-arK', 'garch-garch11', 'gp_pois_regr-gp_pois_regr', 'hmm_example-hmm_example', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; winners ['eight_schools-eight_schools_centered', 'diamonds-diamonds', 'earnings-logearn_interaction', 'mesquite-logmesquite_logvash', 'kidiq-kidscore_momhsiq', 'nes2000-nes', 'arK-arK', 'hmm_example-hmm_example', 'one_comp_mm_elim_abs-one_comp_mm_elim_abs']; losers ['eight_schools-eight_schools_noncentered', 'sblrc-blr', 'gp_pois_regr-gp_pois_regr', 'bball_drive_event_0-hmm_drive_0', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; false positives ['sblrc-blr', 'gp_pois_regr-gp_pois_regr', 'hudson_lynx_hare-lotka_volterra', 'mcycle_gp-accel_gp']; missed []; recommend auto: False

| model | ESS/grad ratio | contended ESS/s ratio | quiet ESS/s ratio | gates | diag gates | class |
|---|---:|---:|---:|---|---|---|
| eight_schools-eight_schools_noncentered | 0.85 | 0.52 | 0.78 | 3/3 | 3/3 | loser |
| eight_schools-eight_schools_centered | 2.40 | 1.85 | 2.92 | 0/3 | 0/3 | winner |
| diamonds-diamonds | 5.28 | 7.02 | 4.20 | 3/3 | 3/3 | winner |
| earnings-logearn_interaction | 5.36 | 7.48 | 4.12 | 3/3 | 3/3 | winner |
| mesquite-logmesquite_logvash | 16.96 | 16.42 | 15.85 | 3/3 | 3/3 | winner |
| kidiq-kidscore_momhsiq | 6.60 | 8.22 | 5.10 | 3/3 | 3/3 | winner |
| sblrc-blr | 0.67 | 0.26 | 0.48 | 3/3 | 3/3 | loser |
| nes2000-nes | 16.73 | 23.76 | 16.35 | 3/3 | 3/3 | winner |
| arK-arK | 7.58 | 8.83 | 7.39 | 3/3 | 3/3 | winner |
| arma-arma11 | 1.13 | 1.52 | 1.12 | 3/3 | 3/3 | neutral |
| garch-garch11 | 1.45 | 1.83 | 1.42 | 3/3 | 3/3 | neutral |
| gp_pois_regr-gp_pois_regr | 2.47 | 2.90 | 2.38 | 2/3 | 3/3 | loser |
| hmm_example-hmm_example | 3.04 | 3.96 | 3.20 | 3/3 | 3/3 | winner |
| bball_drive_event_0-hmm_drive_0 | 0.83 | 0.86 | 0.76 | 3/3 | 3/3 | loser |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 2.01 | 2.63 | 2.30 | 3/3 | 1/3 | winner |
| hudson_lynx_hare-lotka_volterra | 1.35 | 1.97 | 0.58 | 1/3 | 2/3 | loser |
| mcycle_gp-accel_gp | 0.69 | 0.69 | 0.65 | 0/3 | 0/3 | loser |

## Predictor statistics (owalnuts-diag, first 500 retained draws per chain pooled; seed median)

| model | d | max abs corr | corr condition |
|---|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 10 | 0.190 | 1.96 |
| eight_schools-eight_schools_centered | 10 | 0.637 | 27.7 |
| diamonds-diamonds | 26 | 0.898 | 2.57e+05 |
| earnings-logearn_interaction | 5 | 0.999 | 1.29e+04 |
| mesquite-logmesquite_logvash | 7 | 0.957 | 560 |
| kidiq-kidscore_momhsiq | 4 | 0.948 | 191 |
| sblrc-blr | 6 | 0.815 | 24.4 |
| nes2000-nes | 10 | 0.787 | 416 |
| arK-arK | 7 | 0.645 | 116 |
| arma-arma11 | 4 | 0.262 | 1.73 |
| garch-garch11 | 4 | 0.692 | 8.3 |
| gp_pois_regr-gp_pois_regr | 13 | 0.974 | 542 |
| hmm_example-hmm_example | 4 | 0.888 | 16.9 |
| bball_drive_event_0-hmm_drive_0 | 6 | 0.132 | 1.47 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 4 | 0.623 | 4.62 |
| hudson_lynx_hare-lotka_volterra | 8 | 0.954 | 281 |
| mcycle_gp-accel_gp | 66 | 0.768 | 1.26e+03 |

## CmdStan diag_e reference (posteriordb_bench_v6 cells, seeds 90101-90103)

| model | gates | bulk ESS/grad x1e3 | step | depth caps | divergences |
|---|---|---:|---:|---|---|
| diamonds-diamonds | 3/3 | 0.229 | 0.00361 | [3546, 3249, 3453] | [0, 0, 0] |
| mcycle_gp-accel_gp | 0/3 | 0.242 | 0.00671 | [1567, 876, 2258] | [57, 84, 42] |
| gp_pois_regr-gp_pois_regr | 0/3 | 1.042 | 0.0261 | [0, 0, 0] | [5, 6, 2] |

## Funnel side check (P(omega < -5), exact 0.0478; gate |z| <= 2 per seed)

| cell | estimate | MCSE z | batch-means z | omega bulk ESS | omega R-hat | divergences | final steps |
|---|---:|---:|---:|---:|---:|---:|---|
| dense-148102 | 0.0312 | -3.56 | -4.05 | 7 | 1.5434 | 1 | 0.468, 1.64e-06, 0.012, 0.125 |
| dense-seeded-148101 | 0.0459 | -0.25 | -0.26 | 635 | 1.0038 | 15 | 0.103, 0.0637, 0.021, 0.00916 |
| dense-seeded-148102 | 0.0413 | -1.27 | -1.29 | 709 | 1.0037 | 2 | 0.158, 0.0907, 0.0528, 0.14 |
| dense-seeded-148103 | 0.0472 | -0.09 | -0.09 | 675 | 1.0052 | 4 | 0.151, 0.165, 0.153, 0.0812 |
| dense-stan-148101 | 0.0429 | -0.75 | -0.77 | 542 | 1.0080 | 22 | 0.115, 0.0609, 0.0679, 0.118 |
| dense-stan-148102 | 0.0539 | +1.12 | +1.21 | 703 | 1.0039 | 10 | 0.123, 0.0814, 0.189, 0.0964 |
| dense-stan-148103 | 0.0348 | -2.88 | -2.93 | 610 | 1.0102 | 2 | 0.0381, 0.169, 0.214, 0.0953 |

## Cost decomposition (contended micro-benchmarks, minima over repetitions)

| d | diag kernel us/grad | dense kernel us/grad | dense-seeded kernel us/grad | dense-stan kernel us/grad |
|---:|---:|---:|---:|---:|
| 4 | 0.397 | 0.457 | 0.545 | 0.556 |
| 5 | 0.404 | 0.442 | 0.608 | 0.655 |
| 6 | 0.408 | 0.462 | 0.599 | 0.588 |
| 7 | 0.414 | 0.466 | 0.632 | 0.634 |
| 8 | 0.416 | 0.478 | 0.627 | 0.626 |
| 10 | 0.432 | 0.550 | 0.679 | 0.677 |
| 13 | 0.424 | 0.563 | 0.685 | 0.694 |
| 26 | 0.507 | 0.936 | 1.190 | 1.263 |
| 66 | 0.747 | 3.033 | 3.359 | 3.559 |

| model | gradient us |
|---|---:|
| eight_schools-eight_schools_noncentered | 2.42 |
| eight_schools-eight_schools_centered | 2.64 |
| diamonds-diamonds | 47.48 |
| earnings-logearn_interaction | 45.63 |
| mesquite-logmesquite_logvash | 5.93 |
| kidiq-kidscore_momhsiq | 20.70 |
| sblrc-blr | 3.62 |
| nes2000-nes | 45.05 |
| arK-arK | 27.31 |
| arma-arma11 | 17.95 |
| garch-garch11 | 28.27 |
| gp_pois_regr-gp_pois_regr | 15.25 |
| hmm_example-hmm_example | 43.54 |
| bball_drive_event_0-hmm_drive_0 | 179.82 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 598.46 |
| hudson_lynx_hare-lotka_volterra | 85.88 |
| mcycle_gp-accel_gp | 26.67 |

## Preregistered predictions

| prediction | held | value |
|---|---|---|
| ratio_predictions_held_owalnuts-dense-seeded | — | 12/17 |
| ratio_predictions_held_owalnuts-dense-stan | — | 13/17 |
| literal_dense_ratio_below_1 | True | `{"below_1": "15/17", "gates_le_diag_every_model": true}` |
| P1 | False | `{"owalnuts-dense": 0.0819041485331775, "owalnuts-dense-seeded": 1.6660143417886544, "owalnuts-dense-stan": 2.5908904238444697}` |
| P2 | False | `{"earnings-logearn_interaction": {"gates": 3, "gates_diag": 3, "kappa_dense_seeded": 222122.05638320657, "kappa_diag": 12370.864827783958, "held": false}, "kidiq-kidscore_momhsiq": {"gates": 3, "gates_diag": 3, "kappa_dense_seeded": 7619.254717736414, "kappa_diag": 188.9046344210645, "held": false}, "sblrc-blr": {"gates": 3, "gates_diag": 3, "kappa_dense_seeded": 262.85283346258564, "kappa_diag": 62.291259970238656, "held": false}}` |
| P3 | False | `{"diag_cap_fraction": 0.10275, "diag_step": 0.003470817720516974, "stan_zero_cap_seeds": 3, "stan_step": 0.010106359675414432, "seeded_step": 0.029763246886223817}` |
| P4 | False | `{"owalnuts-dense": {"advised_models": [], "verdict": "not supported"}, "owalnuts-dense-seeded": {"advised_models": ["diamonds-diamonds", "mcycle_gp-accel_gp", "gp_pois_regr-gp_pois_regr"], "verdict": "supported"}, "owalnuts-dense-stan": {"advised_models": ["diamonds-diamonds"], "verdict": "mixed"}}` |
| P5 | True | `{"owalnuts-dense": {"recommend_auto": false, "false_positives": ["eight_schools-eight_schools_centered", "diamonds-diamonds", "earnings-logearn_interaction", "kidiq-kidscore_momhsiq", "sblrc-blr", "nes2000-nes", "arK-arK", "garch-garch11", "gp_pois_regr-gp_pois_regr", "hmm_example-hmm_example", "one_comp_mm_elim_abs-one_comp_mm_elim_abs", "hudson_lynx_hare-lotka_volterra", "mcycle_gp-accel_gp"], "missed": []}, "owalnuts-dense-seeded": {"recommend_auto": false, "false_positives": ["earnings-logearn_interaction", "kidiq-kidscore_momhsiq", "sblrc-blr", "hudson_lynx_hare-lotka_volterra"], "missed"` |
| P6 | False | `{"dense-148102": -3.5552477369249496, "dense-seeded-148101": -0.25273038422572897, "dense-seeded-148102": -1.2651396870761475, "dense-seeded-148103": -0.0909694495128212, "dense-stan-148101": -0.753027016272366, "dense-stan-148102": 1.12470155157358, "dense-stan-148103": -2.879720318487764}` |
| P7 | True | `{"4": {"dense_seeded_minus_diag_us": 0.14763529778385753, "dense_stan_minus_diag_us": 0.1593963211959919}, "5": {"dense_seeded_minus_diag_us": 0.20370471985869784, "dense_stan_minus_diag_us": 0.2506374324899742}, "6": {"dense_seeded_minus_diag_us": 0.19009907677824156, "dense_stan_minus_diag_us": 0.17966246139189418}, "7": {"dense_seeded_minus_diag_us": 0.21882216654384895, "dense_stan_minus_diag_us": 0.2206251750172253}, "8": {"dense_seeded_minus_diag_us": 0.21039140013459054, "dense_stan_minus_diag_us": 0.2101170040101488}, "10": {"dense_seeded_minus_diag_us": 0.24638108665989011, "dense_sta` |
| P8 | False | `{"diamonds-diamonds": {"cmdstan_dense_over_v6_diag_e": 89.73253144708121, "dense_stan_over_cmdstan_dense": 0.04830377773415276, "dense_seeded_over_cmdstan_dense": 0.08242862450370363, "both_pass_all": true, "cmdstan_dense_gates": 3}, "mcycle_gp-accel_gp": {"cmdstan_dense_over_v6_diag_e": 0.6489471870030926, "dense_stan_over_cmdstan_dense": 0.4939045407661573, "dense_seeded_over_cmdstan_dense": 1.1416582290224715, "both_pass_all": false, "cmdstan_dense_gates": 0}, "gp_pois_regr-gp_pois_regr": {"cmdstan_dense_over_v6_diag_e": 1.8654843780652528, "dense_stan_over_cmdstan_dense": 0.834200700796322` |
| P9 | False | `{"stan_below_diag": {"diamonds-diamonds": true, "earnings-logearn_interaction": true, "mesquite-logmesquite_logvash": true, "kidiq-kidscore_momhsiq": true, "nes2000-nes": true, "arK-arK": true, "hudson_lynx_hare-lotka_volterra": false, "mcycle_gp-accel_gp": true}, "literal_above_diag": 14, "kappa": {"eight_schools-eight_schools_noncentered": {"diag": 2.0698828429608795, "dense_stan": 2.0700364954671637, "dense": 88.1785295209109, "dense_seeded": 2.0103677850076904, "ref_kdiag": null}, "eight_schools-eight_schools_centered": {"diag": 24.13036465066763, "dense_stan": 5.219366888957126, "dense": ` |

| model | arm | predicted ratio | observed | within factor 2 |
|---|---|---:|---:|---|
| eight_schools-eight_schools_noncentered | owalnuts-dense-seeded | 1.0 | 0.97 | True |
| eight_schools-eight_schools_noncentered | owalnuts-dense-stan | 1.0 | 0.85 | True |
| eight_schools-eight_schools_centered | owalnuts-dense-seeded | 1.0 | 5.78 | False |
| eight_schools-eight_schools_centered | owalnuts-dense-stan | 1.0 | 2.40 | False |
| diamonds-diamonds | owalnuts-dense-seeded | 9.9 | 9.00 | True |
| diamonds-diamonds | owalnuts-dense-stan | 94.62 | 5.28 | False |
| earnings-logearn_interaction | owalnuts-dense-seeded | 0.2 | 0.31 | True |
| earnings-logearn_interaction | owalnuts-dense-stan | 9.75 | 5.36 | True |
| mesquite-logmesquite_logvash | owalnuts-dense-seeded | 6.86 | 7.77 | True |
| mesquite-logmesquite_logvash | owalnuts-dense-stan | 17.39 | 16.96 | True |
| kidiq-kidscore_momhsiq | owalnuts-dense-seeded | 0.14 | 0.21 | True |
| kidiq-kidscore_momhsiq | owalnuts-dense-stan | 10.97 | 6.60 | True |
| sblrc-blr | owalnuts-dense-seeded | 0.39 | 0.38 | True |
| sblrc-blr | owalnuts-dense-stan | 0.83 | 0.67 | True |
| nes2000-nes | owalnuts-dense-seeded | 2.61 | 3.20 | True |
| nes2000-nes | owalnuts-dense-stan | 14.8 | 16.73 | True |
| arK-arK | owalnuts-dense-seeded | 4.48 | 5.01 | True |
| arK-arK | owalnuts-dense-stan | 8.22 | 7.58 | True |
| arma-arma11 | owalnuts-dense-seeded | 0.85 | 0.86 | True |
| arma-arma11 | owalnuts-dense-stan | 1.06 | 1.13 | True |
| garch-garch11 | owalnuts-dense-seeded | 1.37 | 1.48 | True |
| garch-garch11 | owalnuts-dense-stan | 2.37 | 1.45 | True |
| gp_pois_regr-gp_pois_regr | owalnuts-dense-seeded | 1.2 | 4.18 | False |
| gp_pois_regr-gp_pois_regr | owalnuts-dense-stan | 1.3 | 2.47 | True |
| hmm_example-hmm_example | owalnuts-dense-seeded | 1.08 | 1.39 | True |
| hmm_example-hmm_example | owalnuts-dense-stan | 3.48 | 3.04 | True |
| bball_drive_event_0-hmm_drive_0 | owalnuts-dense-seeded | 0.66 | 0.70 | True |
| bball_drive_event_0-hmm_drive_0 | owalnuts-dense-stan | 1.0 | 0.83 | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-dense-seeded | 0.93 | 1.98 | False |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-dense-stan | 1.82 | 2.01 | True |
| hudson_lynx_hare-lotka_volterra | owalnuts-dense-seeded | 5.34 | 2.38 | False |
| hudson_lynx_hare-lotka_volterra | owalnuts-dense-stan | 12.59 | 1.35 | False |
| mcycle_gp-accel_gp | owalnuts-dense-seeded | 0.69 | 1.60 | False |
| mcycle_gp-accel_gp | owalnuts-dense-stan | 2.0 | 0.69 | False |
