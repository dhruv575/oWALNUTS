# Joint default study — results

Seed medians over 3 seeds (86101–86103) of the per-cell minimum over reference parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences per seed; `max|z|` = worst posterior-mean z against the posteriordb reference. Arms: `owalnuts-da` = the current `sampler` defaults (`UTurnRule::Endpoints`, `DiagonalMetricRegularization::TowardUnit`), `owalnuts-rhosum` = `MomentumSum`, `owalnuts-stanreg` = `Stan` regularisation, `owalnuts-joint` = both; everything else `Sampler` defaults (`h0 0.5`, depth 10, eight levels, `delta 1`, dual averaging 0.8, WP24 warmup rule, adapted diagonal, cache).

## Per-model cells

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | bulk ESS/grad x1e3 | max R-hat | div | depth caps | max abs z | final h (seed 1, per chain) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| eight_schools-eight_schools_noncentered | da | 3/3 | 0.03 | 66,526 | 1,953 | 1,652 | 69,272.3 | 28.934 | 1.0029 | 0,0,0 | 0,0,0 | 1.22 | 0.414, 0.508, 0.467, 0.47 |
| eight_schools-eight_schools_noncentered | rhosum | 3/3 | 0.04 | 71,217 | 1,893 | 1,593 | 46,317.4 | 26.465 | 1.0029 | 0,0,0 | 0,0,0 | 1.16 | 0.622, 0.462, 0.473, 0.538 |
| eight_schools-eight_schools_noncentered | stanreg | 3/3 | 0.04 | 66,217 | 1,570 | 1,123 | 37,397.1 | 23.858 | 1.0022 | 0,0,0 | 0,0,0 | 1.48 | 0.514, 0.548, 0.46, 0.548 |
| eight_schools-eight_schools_noncentered | joint | 3/3 | 0.04 | 70,674 | 2,220 | 2,189 | 55,602.0 | 30.117 | 1.0020 | 0,0,0 | 0,0,0 | 1.83 | 0.567, 0.521, 0.443, 0.528 |
| eight_schools-eight_schools_centered | da | 0/3 | 0.09 | 162,649 | 91 | 72 | 1,064.2 | 0.561 | 1.0348 | 0,0,0 | 0,0,0 | 1.96 | 0.18, 0.227, 0.184, 0.252 |
| eight_schools-eight_schools_centered | rhosum | 0/3 | 0.11 | 215,292 | 41 | 78 | 362.4 | 0.188 | 1.0764 | 0,0,7 | 0,0,0 | 0.66 | 0.118, 0.153, 0.183, 0.157 |
| eight_schools-eight_schools_centered | stanreg | 0/3 | 0.09 | 173,889 | 45 | 80 | 599.8 | 0.296 | 1.0728 | 3,0,0 | 0,0,0 | 2.12 | 0.167, 0.219, 0.185, 0.187 |
| eight_schools-eight_schools_centered | joint | 0/3 | 0.11 | 245,562 | 109 | 98 | 979.4 | 0.442 | 1.0413 | 0,0,0 | 0,0,0 | 1.37 | 0.198, 0.172, 0.25, 0.12 |
| diamonds-diamonds | da | 3/3 | 69.07 | 5,209,020 | 930 | 1,209 | 13.5 | 0.178 | 1.0048 | 0,0,0 | 939,791,1012 | 2.16 | 0.00313, 0.00294, 0.00318, 0.00312 |
| diamonds-diamonds | rhosum | 1/3 | 49.83 | 3,652,267 | 491 | 826 | 10.3 | 0.134 | 1.0102 | 0,0,0 | 445,403,386 | 1.94 | 0.00349, 0.00284, 0.00296, 0.00298 |
| diamonds-diamonds | stanreg | 3/3 | 62.91 | 4,679,678 | 758 | 1,038 | 12.4 | 0.162 | 1.0069 | 0,0,0 | 972,884,853 | 1.62 | 0.00276, 0.00407, 0.00328, 0.00355 |
| diamonds-diamonds | joint | 3/3 | 93.37 | 6,693,585 | 1,119 | 1,952 | 12.4 | 0.167 | 1.0046 | 0,0,0 | 313,905,448 | 1.74 | 0.00363, 0.00425, 0.00323, 0.00364 |
| earnings-logearn_interaction | da | 1/3 | 51.99 | 3,820,505 | 633 | 741 | 12.2 | 0.166 | 1.0104 | 0,0,0 | 203,645,473 | 1.05 | 0.00307, 0.00337, 0.00275, 0.00336 |
| earnings-logearn_interaction | rhosum | 3/3 | 36.19 | 2,868,837 | 714 | 915 | 20.9 | 0.249 | 1.0060 | 0,0,0 | 66,245,53 | 1.30 | 0.00322, 0.00387, 0.00334, 0.00358 |
| earnings-logearn_interaction | stanreg | 0/3 | 17.69 | 657,111 | 9 | 11 | 0.7 | 0.014 | 1.3905 | 0,0,0 | 79,146,11 | 1.10 | 0.0243, 0.00766, 0.116, 0.0117 |
| earnings-logearn_interaction | joint | 3/3 | 21.04 | 1,648,897 | 1,026 | 1,308 | 49.2 | 0.611 | 1.0043 | 0,0,0 | 0,0,0 | 1.14 | 0.0179, 0.0141, 0.00953, 0.0135 |
| mesquite-logmesquite_logvash | da | 3/3 | 0.32 | 340,660 | 956 | 1,215 | 3,002.6 | 3.022 | 1.0066 | 0,0,0 | 0,0,0 | 1.52 | 0.0856, 0.0831, 0.0596, 0.0755 |
| mesquite-logmesquite_logvash | rhosum | 3/3 | 0.45 | 352,713 | 1,089 | 1,360 | 2,414.2 | 3.172 | 1.0038 | 0,0,0 | 0,0,0 | 1.55 | 0.0979, 0.0604, 0.0617, 0.0747 |
| mesquite-logmesquite_logvash | stanreg | 3/3 | 0.35 | 343,089 | 1,062 | 1,441 | 3,136.3 | 3.154 | 1.0054 | 0,0,0 | 0,0,0 | 1.22 | 0.0587, 0.0739, 0.0853, 0.0641 |
| mesquite-logmesquite_logvash | joint | 3/3 | 0.35 | 390,801 | 1,324 | 1,748 | 3,493.1 | 3.388 | 1.0023 | 0,0,0 | 0,0,0 | 1.69 | 0.0669, 0.0867, 0.0828, 0.07 |
| kidiq-kidscore_momhsiq | da | 3/3 | 1.43 | 383,066 | 814 | 892 | 566.7 | 2.123 | 1.0049 | 0,0,0 | 0,0,0 | 2.11 | 0.0654, 0.0692, 0.0627, 0.0621 |
| kidiq-kidscore_momhsiq | rhosum | 3/3 | 1.58 | 445,356 | 1,444 | 1,575 | 910.2 | 3.146 | 1.0043 | 0,0,0 | 0,0,0 | 0.98 | 0.0606, 0.0643, 0.0572, 0.0739 |
| kidiq-kidscore_momhsiq | stanreg | 2/3 | 0.84 | 213,655 | 441 | 606 | 505.0 | 2.063 | 1.0099 | 0,0,0 | 0,0,0 | 1.05 | 0.0955, 0.0857, 0.0913, 0.0941 |
| kidiq-kidscore_momhsiq | joint | 3/3 | 1.50 | 398,356 | 1,536 | 1,677 | 1,165.6 | 4.195 | 1.0028 | 0,0,0 | 0,0,0 | 1.45 | 0.0947, 0.0969, 0.0886, 0.0974 |
| sblrc-blr | da | 0/3 | 0.48 | 589,200 | 340 | 323 | 708.9 | 0.581 | 1.0139 | 0,0,0 | 0,0,0 | 1.42 | 0.00349, 0.00346, 0.00338, 0.00309 |
| sblrc-blr | rhosum | 0/3 | 0.46 | 501,116 | 238 | 260 | 514.2 | 0.488 | 1.0099 | 0,0,0 | 0,0,0 | 1.12 | 0.00369, 0.00336, 0.00369, 0.00302 |
| sblrc-blr | stanreg | 3/3 | 0.14 | 199,812 | 641 | 803 | 4,445.3 | 3.206 | 1.0040 | 0,0,0 | 0,0,0 | 1.15 | 0.1, 0.103, 0.11, 0.106 |
| sblrc-blr | joint | 3/3 | 0.10 | 146,760 | 779 | 1,006 | 7,652.3 | 5.299 | 1.0063 | 0,0,0 | 0,0,0 | 1.22 | 0.103, 0.0968, 0.113, 0.105 |
| nes2000-nes | da | 3/3 | 4.49 | 423,045 | 1,237 | 1,319 | 271.2 | 2.878 | 1.0047 | 0,0,0 | 0,0,0 | 1.57 | 0.0656, 0.073, 0.0629, 0.0663 |
| nes2000-nes | rhosum | 3/3 | 5.25 | 440,113 | 1,290 | 1,637 | 252.1 | 2.931 | 1.0027 | 0,0,0 | 0,0,0 | 1.15 | 0.0692, 0.0596, 0.0489, 0.0617 |
| nes2000-nes | stanreg | 2/3 | 4.38 | 317,174 | 804 | 1,130 | 189.2 | 2.536 | 1.0055 | 0,0,0 | 0,0,0 | 1.34 | 0.0908, 0.0927, 0.0832, 0.0651 |
| nes2000-nes | joint | 3/3 | 4.40 | 417,073 | 1,805 | 2,170 | 413.1 | 4.328 | 1.0028 | 0,0,0 | 0,0,0 | 1.51 | 0.0811, 0.0806, 0.0807, 0.0799 |
| arK-arK | da | 3/3 | 1.44 | 250,127 | 1,859 | 1,769 | 1,459.2 | 7.682 | 1.0031 | 0,0,0 | 0,0,0 | 1.54 | 0.0676, 0.0672, 0.0728, 0.0744 |
| arK-arK | rhosum | 3/3 | 1.45 | 258,862 | 1,961 | 1,952 | 1,297.7 | 7.576 | 1.0029 | 0,0,0 | 0,0,0 | 1.49 | 0.066, 0.0615, 0.0729, 0.0848 |
| arK-arK | stanreg | 3/3 | 1.34 | 259,491 | 2,094 | 2,164 | 1,527.4 | 8.085 | 1.0019 | 0,0,0 | 0,0,0 | 2.19 | 0.106, 0.111, 0.131, 0.127 |
| arK-arK | joint | 3/3 | 1.53 | 282,426 | 2,391 | 2,181 | 1,547.8 | 8.236 | 1.0027 | 0,0,0 | 0,0,0 | 2.10 | 0.126, 0.103, 0.102, 0.116 |
| arma-arma11 | da | 3/3 | 2.73 | 349,123 | 1,535 | 1,732 | 599.6 | 4.783 | 1.0024 | 0,0,0 | 0,0,0 | 1.10 | 0.105, 0.111, 0.0969, 0.0976 |
| arma-arma11 | rhosum | 3/3 | 2.33 | 353,024 | 1,603 | 1,743 | 729.8 | 4.814 | 1.0033 | 0,0,0 | 0,0,0 | 1.00 | 0.108, 0.11, 0.104, 0.106 |
| arma-arma11 | stanreg | 3/3 | 2.52 | 314,570 | 2,950 | 2,581 | 1,107.4 | 8.765 | 1.0023 | 0,0,0 | 0,0,0 | 1.75 | 0.765, 0.71, 0.71, 0.757 |
| arma-arma11 | joint | 3/3 | 2.52 | 328,321 | 3,455 | 2,787 | 1,372.3 | 10.811 | 1.0016 | 0,0,0 | 0,0,0 | 1.34 | 0.704, 0.81, 0.674, 0.76 |
| garch-garch11 | da | 3/3 | 0.40 | 72,821 | 1,133 | 1,436 | 2,722.2 | 15.781 | 1.0044 | 0,0,0 | 0,0,0 | 1.76 | 0.312, 0.338, 0.3, 0.314 |
| garch-garch11 | rhosum | 3/3 | 0.47 | 90,113 | 1,746 | 1,588 | 3,817.7 | 19.258 | 1.0023 | 0,0,0 | 0,0,0 | 1.18 | 0.304, 0.287, 0.334, 0.284 |
| garch-garch11 | stanreg | 3/3 | 0.52 | 70,884 | 1,096 | 1,358 | 2,126.0 | 15.506 | 1.0031 | 0,0,0 | 0,0,0 | 1.16 | 0.377, 0.297, 0.302, 0.278 |
| garch-garch11 | joint | 3/3 | 0.53 | 97,028 | 1,738 | 1,743 | 3,365.7 | 18.282 | 1.0020 | 0,0,0 | 0,0,0 | 1.38 | 0.349, 0.331, 0.334, 0.249 |
| gp_pois_regr-gp_pois_regr | da | 3/3 | 2.41 | 1,115,941 | 875 | 1,266 | 347.3 | 0.791 | 1.0039 | 0,0,0 | 0,0,0 | 1.24 | 0.0317, 0.0256, 0.0281, 0.026 |
| gp_pois_regr-gp_pois_regr | rhosum | 3/3 | 3.25 | 1,196,001 | 709 | 725 | 218.4 | 0.593 | 1.0044 | 0,0,0 | 0,0,0 | 2.00 | 0.0268, 0.0275, 0.0257, 0.0236 |
| gp_pois_regr-gp_pois_regr | stanreg | 2/3 | 2.32 | 1,059,162 | 730 | 1,135 | 324.4 | 0.678 | 1.0062 | 0,0,0 | 0,0,0 | 1.48 | 0.0282, 0.0272, 0.0281, 0.0272 |
| gp_pois_regr-gp_pois_regr | joint | 3/3 | 3.62 | 1,182,170 | 953 | 1,399 | 262.9 | 0.776 | 1.0025 | 0,0,0 | 0,0,0 | 1.67 | 0.0272, 0.0263, 0.0283, 0.0286 |
| hmm_example-hmm_example | da | 3/3 | 3.18 | 208,006 | 1,906 | 1,695 | 599.6 | 9.164 | 1.0031 | 0,0,0 | 0,0,0 | 1.73 | 0.118, 0.152, 0.166, 0.152 |
| hmm_example-hmm_example | rhosum | 3/3 | 3.21 | 213,166 | 1,954 | 1,625 | 585.5 | 8.813 | 1.0020 | 0,0,0 | 0,0,0 | 1.42 | 0.132, 0.162, 0.129, 0.124 |
| hmm_example-hmm_example | stanreg | 3/3 | 1.61 | 113,669 | 1,664 | 1,736 | 1,035.6 | 14.130 | 1.0020 | 0,0,0 | 0,0,0 | 1.57 | 0.337, 0.328, 0.255, 0.356 |
| hmm_example-hmm_example | joint | 3/3 | 1.79 | 132,419 | 2,177 | 1,978 | 1,272.2 | 17.168 | 1.0032 | 0,0,0 | 0,0,0 | 1.08 | 0.355, 0.299, 0.249, 0.276 |
| bball_drive_event_0-hmm_drive_0 | da | 2/3 | 6.70 | 101,674 | 2,258 | 1,585 | 235.9 | 19.056 | 1.0023 | 0,0,0 | 0,0,0 | 1.10 | 0.421, 0.41, 0.425, 0.407 |
| bball_drive_event_0-hmm_drive_0 | rhosum | 1/3 | 7.50 | 112,326 | 42 | 18 | 5.7 | 0.387 | 1.0750 | 0,0,0 | 0,0,0 | 1.28 | 0.407, 0.437, 0.382, 0.368 |
| bball_drive_event_0-hmm_drive_0 | stanreg | 2/3 | 4.73 | 72,922 | 2,522 | 1,547 | 323.3 | 26.093 | 1.0052 | 0,0,0 | 0,0,0 | 1.42 | 0.619, 0.568, 0.602, 0.573 |
| bball_drive_event_0-hmm_drive_0 | joint | 1/3 | 6.07 | 86,731 | 9 | 28 | 1.4 | 0.088 | 1.3846 | 0,0,0 | 0,0,0 | 1.29 | 0.571, 0.646, 0.425, 0.651 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | da | 1/3 | 15.12 | 65,087 | 331 | 152 | 21.9 | 5.079 | 1.0129 | 0,0,0 | 0,0,0 | 1.25 | 0.351, 0.293, 0.334, 0.282 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | rhosum | 2/3 | 18.28 | 75,599 | 1,088 | 589 | 60.3 | 14.654 | 1.0040 | 0,0,0 | 0,0,0 | 3.18 | 0.332, 0.363, 0.238, 0.348 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | stanreg | 0/3 | 12.98 | 58,414 | 398 | 178 | 33.1 | 6.814 | 1.0140 | 0,0,0 | 0,0,0 | 0.98 | 0.269, 0.249, 0.465, 0.422 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | joint | 2/3 | 21.47 | 84,762 | 928 | 408 | 42.3 | 10.952 | 1.0031 | 0,0,0 | 0,0,0 | 1.02 | 0.28, 0.296, 0.281, 0.444 |
| hudson_lynx_hare-lotka_volterra | da | 1/3 | 14.38 | 291,436 | 10 | 11 | 0.7 | 0.037 | 1.3148 | 0,0,0 | 0,0,0 | 1.17 | 0.0774, 0.0769, 0.0819, 0.0815 |
| hudson_lynx_hare-lotka_volterra | rhosum | 1/3 | 10.21 | 306,172 | 645 | 1,036 | 85.2 | 2.213 | 1.0185 | 0,0,0 | 0,0,0 | 1.24 | 0.094, 0.0703, 0.0806, 0.0846 |
| hudson_lynx_hare-lotka_volterra | stanreg | 1/3 | 9.99 | 250,917 | 449 | 257 | 44.9 | 1.824 | 1.0144 | 0,0,0 | 0,0,0 | 1.35 | 0.109, 0.111, 0.109, 0.177 |
| hudson_lynx_hare-lotka_volterra | joint | 2/3 | 11.34 | 312,247 | 835 | 1,115 | 75.9 | 2.676 | 1.0038 | 0,0,0 | 0,0,0 | 1.36 | 0.107, 0.11, 0.114, 0.112 |
| mcycle_gp-accel_gp | da | 0/3 | 6.54 | 1,418,295 | 36 | 53 | 5.6 | 0.026 | 1.0883 | 0,0,0 | 1,10,0 | 2.87 | 0.00681, 0.00531, 0.00704, 0.00736 |
| mcycle_gp-accel_gp | rhosum | 0/3 | 9.70 | 2,364,107 | 300 | 207 | 31.0 | 0.121 | 1.0218 | 0,0,0 | 0,0,2 | 2.47 | 0.00969, 0.00898, 0.00854, 0.00858 |
| mcycle_gp-accel_gp | stanreg | 0/3 | 5.95 | 1,211,659 | 43 | 31 | 7.2 | 0.036 | 1.0831 | 0,0,0 | 0,0,0 | 3.22 | 0.00694, 0.00904, 0.00802, 0.01 |
| mcycle_gp-accel_gp | joint | 0/3 | 11.93 | 2,385,398 | 228 | 97 | 16.8 | 0.089 | 1.0349 | 0,0,0 | 0,0,0 | 2.78 | 0.00963, 0.0112, 0.00817, 0.00737 |

## The decision statistic: seed-median min bulk ESS/gradient, candidate / da, per model

`vs CmdStan` / `vs nutpie` = this study's seed median over the v3 seed median (cited, seeds 79101–79103); `da vs v3 da` = reproduction of the v3 default arm on fresh seeds.

| model | gates da / rhosum / stanreg / joint | da ESS/grad x1e3 | rhosum / da | stanreg / da | **joint / da** | joint per seed | grads joint/da | da vs CmdStan | joint vs CmdStan | da vs nutpie | joint vs nutpie | da vs v3 da |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 3 / 3 / 3 / 3 | 28.934 | 0.91 | 0.82 | **1.04** | 1.11, 1.04, 0.96 | 1.06 | 0.86 | 0.89 | 0.74 | 0.77 | 0.99 |
| eight_schools-eight_schools_centered | 0 / 0 / 0 / 0 | 0.561 | 0.34 | 0.53 | **0.79** | 0.79, 0.38, 0.78 | 1.51 | 0.52 | 0.41 | 0.62 | 0.49 | 2.43 |
| diamonds-diamonds | 3 / 1 / 3 / 3 | 0.178 | 0.76 | 0.91 | **0.94** | 1.52, 0.82, 0.94 | 1.28 | 0.81 | 0.76 | 0.92 | 0.86 | 1.14 |
| earnings-logearn_interaction | 1 / 3 / 0 / 3 | 0.166 | 1.50 | 0.08 | **3.69** | 4.19, 2.91, 3.78 | 0.43 | 0.22 | 0.81 | 0.18 | 0.68 | 0.93 |
| mesquite-logmesquite_logvash | 3 / 3 / 3 / 3 | 3.022 | 1.05 | 1.04 | **1.12** | 1.06, 1.19, 1.23 | 1.15 | 0.88 | 0.99 | 0.70 | 0.78 | 1.00 |
| kidiq-kidscore_momhsiq | 3 / 3 / 2 / 3 | 2.123 | 1.48 | 0.97 | **1.98** | 1.78, 1.98, 1.99 | 1.04 | 0.47 | 0.93 | 0.35 | 0.69 | 0.98 |
| sblrc-blr | 0 / 0 / 3 / 3 | 0.581 | 0.84 | 5.52 | **9.12** | 8.20, 8.60, 18.66 | 0.25 | 0.09 | 0.81 | 0.04 | 0.39 | 1.41 |
| nes2000-nes | 3 / 3 / 2 / 3 | 2.878 | 1.02 | 0.88 | **1.50** | 1.44, 1.61, 2.09 | 0.99 | 0.58 | 0.88 | 0.50 | 0.76 | 1.15 |
| arK-arK | 3 / 3 / 3 / 3 | 7.682 | 0.99 | 1.05 | **1.07** | 1.06, 1.07, 1.08 | 1.13 | 0.74 | 0.79 | 0.68 | 0.72 | 0.99 |
| arma-arma11 | 3 / 3 / 3 / 3 | 4.783 | 1.01 | 1.83 | **2.26** | 2.55, 2.85, 2.20 | 0.94 | 0.07 | 0.15 | 0.04 | 0.08 | 0.34 |
| garch-garch11 | 3 / 3 / 3 / 3 | 15.781 | 1.22 | 0.98 | **1.16** | 1.06, 1.26, 1.18 | 1.33 | 0.76 | 0.88 | 0.61 | 0.71 | 1.05 |
| gp_pois_regr-gp_pois_regr | 3 / 3 / 2 / 3 | 0.791 | 0.75 | 0.86 | **0.98** | 0.91, 1.04, 1.04 | 1.06 | 0.74 | 0.72 | 0.90 | 0.88 | 1.08 |
| hmm_example-hmm_example | 3 / 3 / 3 / 3 | 9.164 | 0.96 | 1.54 | **1.87** | 2.10, 1.25, 1.93 | 0.64 | 0.44 | 0.82 | 0.33 | 0.62 | 0.94 |
| bball_drive_event_0-hmm_drive_0 | 2 / 1 / 2 / 1 | 19.056 | 0.02 | 1.37 | **0.00** | 0.00, 1.38, 0.60 | 0.85 | 0.30 | 0.00 | 0.28 | 0.00 | 67.71 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1 / 2 / 0 / 2 | 5.079 | 2.89 | 1.34 | **2.16** | 7.98, 0.97, 2.16 | 1.30 | 0.40 | 0.85 | 1.09 | 2.35 | 0.56 |
| hudson_lynx_hare-lotka_volterra | 1 / 1 / 1 / 2 | 0.037 | 59.60 | 49.11 | **72.06** | 0.80, 80.81, 1.02 | 1.07 | 0.01 | 0.77 | — | — | 0.01 |
| mcycle_gp-accel_gp | 0 / 0 / 0 / 0 | 0.026 | 4.58 | 1.34 | **3.35** | 2.15, 2.50, 3.87 | 1.68 | 0.13 | 0.42 | 0.14 | 0.46 | 0.38 |

| arm | cells passed | geomean ratio to da (ESS/grad) | min model ratio | models < 0.85 | models > 1.15 | geomean grads ratio | geomean ESS/s ratio | sampling-only ESS/grad ratio | geomean vs CmdStan v3 | geomean vs nutpie v3 | geomean vs v3 da | frozen cells |
|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| da | 35 | 1 | — | — | — | 1 | 1 | 1 | 0.317 | 0.359 | 0.920 | 1 |
| rhosum | 35 | **1.116** | 0.02 (bball_drive_event_0-hmm_drive_0) | eight_schools-eight_schools_centered 0.34, diamonds-diamonds 0.76, sblrc-blr 0.84, gp_pois_regr-gp_pois_regr 0.75, bball_drive_event_0-hmm_drive_0 0.02 | earnings-logearn_interaction 1.50, kidiq-kidscore_momhsiq 1.48, garch-garch11 1.22, one_comp_mm_elim_abs-one_comp_mm_elim_abs 2.89, hudson_lynx_hare-lotka_volterra 59.60, mcycle_gp-accel_gp 4.58 | 1.056 | 1.150 | 1.094 | 0.353 | 0.312 | 1.027 | 1 |
| stanreg | 33 | **1.257** | 0.08 (earnings-logearn_interaction) | eight_schools-eight_schools_noncentered 0.82, eight_schools-eight_schools_centered 0.53, earnings-logearn_interaction 0.08 | sblrc-blr 5.52, arma-arma11 1.83, hmm_example-hmm_example 1.54, bball_drive_event_0-hmm_drive_0 1.37, one_comp_mm_elim_abs-one_comp_mm_elim_abs 1.34, hudson_lynx_hare-lotka_volterra 49.11, mcycle_gp-accel_gp 1.34 | 0.734 | 1.219 | 1.381 | 0.398 | 0.358 | 1.156 | 0 |
| joint | 41 | **1.508** | 0.00 (bball_drive_event_0-hmm_drive_0) | eight_schools-eight_schools_centered 0.79, bball_drive_event_0-hmm_drive_0 0.00 | earnings-logearn_interaction 3.69, kidiq-kidscore_momhsiq 1.98, sblrc-blr 9.12, nes2000-nes 1.50, arma-arma11 2.26, garch-garch11 1.16, hmm_example-hmm_example 1.87, one_comp_mm_elim_abs-one_comp_mm_elim_abs 2.16, hudson_lynx_hare-lotka_volterra 72.06, mcycle_gp-accel_gp 3.35 | 0.960 | 1.563 | 1.531 | 0.477 | 0.424 | 1.387 | 1 |

## Funnel tail mass `P(omega < -5)` (exact 0.0478), 4 x 2,000 / 20,000 per seed

`z` = (estimate − exact) / MCSE of the indicator (`diagnostics::mcse_mean`, the WP28 statistic; the gate is |z| <= 2 on every seed); `z_bm` = the WP26 batch-means statistic per seed; pooled = three seeds pooled with batch-means s.e. At the paper tuning the metric is the identity, so the regularisation is inert (`stanreg` = `da`, `joint` = `rhosum`).

| tuning | arm | per-seed estimate (z) | all abs(z) <= 2 | per-seed z_bm | pooled estimate (z_bm) | omega bulk ESS / R-hat per seed | target calls (3 seeds) | omega bulk ESS / call x1e3 | depth caps | divergences | retained exhaustions | final h (seed 1) |
|---|---|---|---|---|---|---|---:|---:|---|---|---|---|
| paper | da | 0.0539 (+0.77), 0.0405 (-1.12), 0.0439 (-0.65) | **yes** | +0.83, -1.12, -0.66 | 0.0461 (-0.44) | 584 / 1.012, 754 / 1.006, 650 / 1.006 | 6,730,195 | 0.295 | 2,8,7 | 0,0,0 | 2,0,0 | 0.393, 0.521, 0.577, 0.506 |
| paper | rhosum | 0.0524 (+0.68), 0.0526 (+0.61), 0.0482 (+0.05) | **yes** | +0.69, +0.62, +0.05 | 0.0510 (+0.80) | 544 / 1.005, 662 / 1.005, 669 / 1.007 | 7,667,150 | 0.245 | 2,12,5 | 0,0,0 | 1,1,1 | 0.584, 0.64, 0.58, 0.495 |
| paper | stanreg | 0.0539 (+0.77), 0.0405 (-1.12), 0.0439 (-0.65) | **yes** | +0.83, -1.12, -0.66 | 0.0461 (-0.44) | 584 / 1.012, 754 / 1.006, 650 / 1.006 | 6,730,195 | 0.295 | 2,8,7 | 0,0,0 | 2,0,0 | 0.393, 0.521, 0.577, 0.506 |
| paper | joint | 0.0524 (+0.68), 0.0526 (+0.61), 0.0482 (+0.05) | **yes** | +0.69, +0.62, +0.05 | 0.0510 (+0.80) | 544 / 1.005, 662 / 1.005, 669 / 1.007 | 7,667,150 | 0.245 | 2,12,5 | 0,0,0 | 1,1,1 | 0.584, 0.64, 0.58, 0.495 |
| defaults | da | 0.1046 (+1.55), 0.0594 (+1.02), 0.0431 (-0.46) | **yes** | +2.97, +1.23, -0.63 | 0.0690 (+2.79) | 111 / 1.044, 314 / 1.007, 245 / 1.035 | 9,320,947 | 0.072 | 53,0,41 | 2,9,4 | 11,49,74 | 0.116, 0.0499, 0.164, 0.049 |
| defaults | rhosum | 0.0403 (-1.21), 0.0467 (-0.12), 0.0404 (-1.24) | **yes** | -1.24, -0.13, -1.38 | 0.0425 (-1.37) | 444 / 1.013, 418 / 1.007, 690 / 1.002 | 12,292,077 | 0.126 | 71,1,17 | 0,9,0 | 1,91,5 | 0.203, 0.157, 0.0919, 0.0256 |
| defaults | stanreg | 0.0455 (-0.20), 0.0558 (+0.66), 0.0678 (+1.36) | **yes** | -0.25, +0.77, +1.67 | 0.0564 (+1.40) | 220 / 1.026, 270 / 1.014, 345 / 1.010 | 8,126,099 | 0.103 | 15,2,13 | 0,4,0 | 4,62,6 | 0.0578, 0.214, 0.0397, 0.147 |
| defaults | joint | 0.0474 (-0.06), 0.0549 (+0.81), 0.0393 (-1.16) | **yes** | -0.06, +0.92, -1.22 | 0.0472 (-0.15) | 357 / 1.010, 618 / 1.003, 408 / 1.004 | 13,268,242 | 0.104 | 0,16,85 | 0,0,0 | 39,9,2 | 0.14, 0.0578, 0.0914, 0.0392 |

## Eight Schools strict track (v38/v9 settings: h 0.3, depth 8, eight levels, delta 1, accept 0.95, 4 x 1,000/1,000, threads 1, `walnutpie` facade)

| arm | seed | calls | min bulk ESS | min tail ESS | max R-hat | bulk ESS/call | tail ESS/call | wall s (median) | div | exhaustions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| da | 86101 | 117,727 | 1,819 | 1,539 | 1.0022 | 0.01545 | 0.01307 | 0.0422 | 0 | 0 |
| da | 86102 | 122,738 | 2,124 | 1,469 | 1.0019 | 0.01730 | 0.01197 | 0.0408 | 0 | 0 |
| da | 86103 | 117,205 | 1,808 | 1,295 | 1.0021 | 0.01542 | 0.01105 | 0.0414 | 0 | 0 |
| rhosum | 86101 | 120,273 | 2,479 | 2,133 | 1.0016 | 0.02061 | 0.01773 | 0.0459 | 0 | 0 |
| rhosum | 86102 | 122,260 | 2,584 | 2,079 | 1.0038 | 0.02113 | 0.01701 | 0.0473 | 0 | 0 |
| rhosum | 86103 | 119,063 | 2,744 | 2,093 | 1.0047 | 0.02305 | 0.01758 | 0.0479 | 0 | 0 |
| stanreg | 86101 | 111,836 | 1,851 | 1,638 | 1.0031 | 0.01655 | 0.01465 | 0.0403 | 0 | 0 |
| stanreg | 86102 | 110,234 | 2,215 | 1,494 | 1.0008 | 0.02010 | 0.01355 | 0.0416 | 0 | 0 |
| stanreg | 86103 | 107,848 | 1,756 | 1,439 | 1.0018 | 0.01628 | 0.01334 | 0.0377 | 0 | 0 |
| joint | 86101 | 118,104 | 2,477 | 1,680 | 1.0005 | 0.02097 | 0.01423 | 0.0478 | 0 | 0 |
| joint | 86102 | 118,125 | 2,594 | 2,064 | 1.0019 | 0.02196 | 0.01748 | 0.0467 | 0 | 0 |
| joint | 86103 | 123,901 | 2,402 | 1,574 | 1.0035 | 0.01939 | 0.01270 | 0.0520 | 0 | 0 |

| arm | geomean min bulk ESS/call | median | ratio to da | all seeds healthy |
|---|---:|---:|---:|---|
| da | 0.01603 | 0.01545 | 1.000 | True |
| rhosum | 0.02157 | 0.02113 | 1.346 | True |
| stanreg | 0.01756 | 0.01655 | 1.095 | True |
| joint | 0.02075 | 0.02097 | 1.294 | True |

## Preregistered decision rule (on `joint`)

| criterion | value | threshold | held |
|---|---|---|---|
| C1_geomean_ratio_ge_1.15 | 1.508 | 1.15 | True |
| C2_no_model_below_0.85 | 0.005 (bball_drive_event_0-hmm_drive_0) | 0.85 | False |
| C3_gates_ge_da | 41 | 35 | True |
| C4_funnel_abs_z_le_2_every_seed_both_tunings | paper +0.68, +0.61, +0.05; defaults -0.06, +0.81, -1.16 | 2.0 | True |
| C5_eight_schools_ess_per_call_ge_0.9 | 1.294 | 0.9 | True |

## Preregistered predictions (not gated)

| prediction | value | held |
|---|---|---|
| P1_joint_ge_1.2_on_healthy_regressions | earnings 3.69, kidiq 1.98, sblrc 9.12, mesquite 1.12, nes2000 1.50 | False |
| P2_earnings_gate_recovered | da 1, rhosum 3, stanreg 0, joint 3 | True |
| P3_sblrc_ge_5x | 9.12 | True |

**Decision: keep the current defaults** (all five criteria must hold).
