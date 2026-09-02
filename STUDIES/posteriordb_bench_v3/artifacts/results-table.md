# posteriordb benchmark v3 — results

Seed medians over 3 seeds of the per-cell minimum over parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences summed over chains per seed; `max|z|` = worst posterior-mean z against the posteriordb reference.

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | tail ESS/s | bulk ESS/grad x1e3 | max R-hat | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.03 | 69,929 | 2,035 | 1,574 | 61,764.2 | 45,926.5 | 29.107 | 1.0016 | 0,0,0 | 1.14 |
| eight_schools-eight_schools_noncentered | owalnuts-stan-style | 3/3 | 0.03 | 66,493 | 1,695 | 1,338 | 59,376.2 | 46,726.2 | 25.796 | 1.0033 | 0,0,0 | 1.47 |
| eight_schools-eight_schools_noncentered | cmdstan | 2/3 | 0.18 | 72,426 | 2,445 | 1,950 | 13,485.6 | 10,493.0 | 33.756 | 1.0018 | 2,0,0 | 1.39 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0.19 | 56,077 | 2,193 | 1,536 | 9,482.4 | 7,120.1 | 39.111 | 1.0025 | 2,3,2 | 1.57 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.08 | 159,212 | 37 | 49 | 481.9 | 589.5 | 0.231 | 1.0832 | 9,3,9 | 1.16 |
| eight_schools-eight_schools_centered | owalnuts-stan-style | 0/3 | 0.09 | 177,001 | 87 | 60 | 897.2 | 693.6 | 0.451 | 1.0595 | 1,4,0 | 1.22 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0.19 | 166,891 | 167 | 128 | 607.0 | 599.3 | 1.074 | 1.0286 | 31,62,70 | 3.26 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0.34 | 113,913 | 103 | 100 | 278.6 | 216.0 | 0.901 | 1.0375 | 25,28,48 | 2.11 |
| diamonds-diamonds | owalnuts-da | 3/3 | 72.57 | 5,084,148 | 799 | 1,135 | 11.0 | 14.7 | 0.156 | 1.0063 | 0,0,0 | 2.60 |
| diamonds-diamonds | owalnuts-stan-style | 2/3 | 59.16 | 4,076,936 | 635 | 671 | 13.0 | 13.7 | 0.173 | 1.0083 | 0,0,0 | 2.09 |
| diamonds-diamonds | cmdstan | 3/3 | 76.57 | 6,444,618 | 1,408 | 2,067 | 18.4 | 27.5 | 0.219 | 1.0033 | 0,0,0 | 1.83 |
| diamonds-diamonds | nutpie | 1/3 | 27.28 | 2,057,622 | 407 | 533 | 14.3 | 19.5 | 0.194 | 1.0126 | 0,0,0 | 1.89 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 50.48 | 5,039,309 | 899 | 1,037 | 17.8 | 21.2 | 0.177 | 1.0033 | 0,0,0 | 0.70 |
| earnings-logearn_interaction | owalnuts-stan-style | 0/3 | 4.72 | 386,976 | 192 | 170 | 37.9 | 33.1 | 0.477 | 1.0246 | 0,0,0 | 0.96 |
| earnings-logearn_interaction | cmdstan | 3/3 | 13.53 | 1,339,060 | 1,002 | 1,318 | 78.0 | 95.9 | 0.756 | 1.0052 | 0,0,0 | 0.88 |
| earnings-logearn_interaction | nutpie | 3/3 | 9.06 | 730,831 | 660 | 795 | 72.4 | 90.4 | 0.903 | 1.0068 | 0,0,0 | 0.56 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.28 | 327,518 | 975 | 1,403 | 3,490.2 | 4,846.9 | 3.030 | 1.0034 | 0,0,0 | 1.52 |
| mesquite-logmesquite_logvash | owalnuts-stan-style | 3/3 | 0.29 | 310,106 | 926 | 916 | 2,576.6 | 3,122.4 | 2.937 | 1.0063 | 0,0,0 | 1.54 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 0.44 | 379,521 | 1,273 | 1,781 | 2,942.5 | 4,034.7 | 3.431 | 1.0038 | 0,0,0 | 2.75 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 0.70 | 198,379 | 884 | 1,265 | 1,333.1 | 1,806.6 | 4.342 | 1.0032 | 0,0,0 | 1.68 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.35 | 438,417 | 983 | 933 | 666.5 | 683.5 | 2.163 | 1.0050 | 0,0,0 | 0.61 |
| kidiq-kidscore_momhsiq | owalnuts-stan-style | 1/3 | 0.71 | 225,155 | 510 | 580 | 750.8 | 816.2 | 2.264 | 1.0106 | 0,0,0 | 1.23 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 1.11 | 349,536 | 1,548 | 1,840 | 1,225.3 | 1,409.5 | 4.498 | 1.0025 | 0,0,0 | 1.17 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 0.75 | 139,185 | 844 | 1,200 | 1,133.1 | 1,607.2 | 6.118 | 1.0048 | 0,0,0 | 1.73 |
| sblrc-blr | owalnuts-da | 0/3 | 0.42 | 550,090 | 237 | 299 | 490.2 | 609.5 | 0.413 | 1.0194 | 0,0,0 | 2.28 |
| sblrc-blr | owalnuts-stan-style | 2/3 | 0.12 | 189,316 | 797 | 831 | 6,355.2 | 6,627.6 | 4.211 | 1.0066 | 0,0,0 | 1.78 |
| sblrc-blr | cmdstan | 3/3 | 0.19 | 122,313 | 805 | 1,102 | 4,421.5 | 5,966.1 | 6.583 | 1.0055 | 0,0,0 | 1.15 |
| sblrc-blr | nutpie | 3/3 | 0.18 | 56,786 | 780 | 1,100 | 4,487.7 | 6,030.2 | 13.734 | 1.0057 | 0,0,0 | 0.96 |
| nes2000-nes | owalnuts-da | 3/3 | 4.27 | 420,620 | 1,038 | 1,441 | 249.1 | 345.9 | 2.499 | 1.0044 | 0,0,0 | 1.69 |
| nes2000-nes | owalnuts-stan-style | 3/3 | 3.68 | 313,102 | 863 | 1,077 | 231.1 | 279.8 | 2.748 | 1.0063 | 0,0,0 | 1.65 |
| nes2000-nes | cmdstan | 3/3 | 3.86 | 398,456 | 1,982 | 2,151 | 464.5 | 573.9 | 4.925 | 1.0024 | 0,0,0 | 1.76 |
| nes2000-nes | nutpie | 3/3 | 3.04 | 236,696 | 1,351 | 1,722 | 442.5 | 558.1 | 5.704 | 1.0040 | 0,0,0 | 1.31 |
| arK-arK | owalnuts-da | 3/3 | 1.30 | 235,624 | 1,826 | 2,073 | 1,518.6 | 1,643.6 | 7.752 | 1.0026 | 0,0,0 | 1.58 |
| arK-arK | owalnuts-stan-style | 3/3 | 1.23 | 232,232 | 1,807 | 1,965 | 1,560.7 | 1,567.9 | 7.780 | 1.0032 | 0,0,0 | 1.19 |
| arK-arK | cmdstan | 3/3 | 1.37 | 245,258 | 2,730 | 2,213 | 1,566.8 | 1,611.7 | 10.404 | 1.0020 | 0,0,0 | 1.72 |
| arK-arK | nutpie | 3/3 | 8.93 | 173,272 | 1,951 | 2,001 | 218.6 | 217.8 | 11.372 | 1.0027 | 0,0,0 | 2.23 |
| arma-arma11 | owalnuts-da | 2/3 | 0.31 | 116,484 | 1,468 | 1,518 | 5,351.5 | 4,973.8 | 14.020 | 1.0059 | 0,0,0 | 1.16 |
| arma-arma11 | owalnuts-stan-style | 0/3 | 0.69 | 193,168 | 4 | 4 | 5.9 | 5.8 | 0.021 | 9.4128 | 3000,2000,2000 | 2.16 |
| arma-arma11 | cmdstan | 2/3 | 0.30 | 54,222 | 3,906 | 2,403 | 13,239.6 | 8,146.0 | 72.040 | 1.0028 | 0,0,0 | 1.30 |
| arma-arma11 | nutpie | 3/3 | 2.28 | 36,426 | 4,950 | 2,898 | 2,017.5 | 1,270.9 | 133.017 | 1.0035 | 0,0,0 | 1.48 |
| garch-garch11 | owalnuts-da | 3/3 | 0.34 | 71,603 | 1,076 | 1,323 | 3,184.7 | 3,918.2 | 15.021 | 1.0031 | 0,0,0 | 1.08 |
| garch-garch11 | owalnuts-stan-style | 2/3 | 0.34 | 68,353 | 1,085 | 1,143 | 2,763.9 | 3,187.3 | 14.702 | 1.0047 | 0,0,0 | 0.84 |
| garch-garch11 | cmdstan | 3/3 | 0.61 | 92,296 | 1,925 | 1,955 | 2,804.0 | 3,198.0 | 20.860 | 1.0030 | 0,0,0 | 1.06 |
| garch-garch11 | nutpie | 3/3 | 3.14 | 61,621 | 1,591 | 1,891 | 464.7 | 570.2 | 25.822 | 1.0025 | 0,0,0 | 1.30 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 1.95 | 1,076,606 | 787 | 1,008 | 402.9 | 515.7 | 0.731 | 1.0064 | 0,0,0 | 1.32 |
| gp_pois_regr-gp_pois_regr | owalnuts-stan-style | 3/3 | 2.01 | 983,346 | 773 | 847 | 397.9 | 421.7 | 0.812 | 1.0050 | 0,0,0 | 1.97 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 2.37 | 1,316,279 | 1,361 | 1,827 | 533.1 | 769.7 | 1.073 | 1.0033 | 3,7,9 | 1.58 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 3.29 | 791,426 | 699 | 591 | 212.6 | 179.8 | 0.883 | 1.0060 | 130,177,145 | 1.77 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 2.15 | 196,736 | 1,922 | 1,797 | 895.5 | 865.1 | 9.767 | 1.0036 | 0,0,0 | 1.52 |
| hmm_example-hmm_example | owalnuts-stan-style | 3/3 | 1.08 | 93,528 | 1,540 | 1,601 | 1,493.4 | 1,476.4 | 16.813 | 1.0020 | 0,0,0 | 1.63 |
| hmm_example-hmm_example | cmdstan | 3/3 | 1.50 | 99,026 | 2,169 | 2,063 | 1,441.7 | 1,408.8 | 20.948 | 1.0022 | 0,0,0 | 1.51 |
| hmm_example-hmm_example | nutpie | 3/3 | 12.19 | 56,815 | 1,578 | 1,836 | 129.5 | 141.8 | 27.713 | 1.0031 | 0,0,0 | 1.41 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 1/3 | 5.74 | 89,513 | 26 | 12 | 4.6 | 2.0 | 0.281 | 1.1145 | 0,0,0 | 2.29 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-stan-style | 2/3 | 4.72 | 68,607 | 1,116 | 973 | 236.7 | 206.2 | 16.272 | 1.0031 | 0,0,0 | 1.67 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 3/3 | 5.50 | 64,581 | 3,676 | 1,494 | 795.2 | 344.3 | 64.579 | 1.0021 | 0,0,0 | 2.23 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 3/3 | 20.82 | 41,215 | 3,026 | 2,075 | 123.4 | 84.6 | 67.016 | 1.0025 | 0,0,0 | 1.24 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 13.32 | 61,324 | 566 | 374 | 40.6 | 28.1 | 9.076 | 1.0076 | 0,0,0 | 2.65 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-stan-style | 1/3 | 12.66 | 56,824 | 375 | 182 | 29.9 | 14.5 | 6.449 | 1.0091 | 0,0,0 | 2.26 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 16.88 | 70,206 | 1,017 | 373 | 44.9 | 16.4 | 12.837 | 1.0047 | 4,6,7 | 1.07 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 46.64 | 49,806 | 234 | 56 | 4.6 | 1.1 | 4.658 | 1.0238 | 28,268,12 | 1.15 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 3/3 | 12.99 | 277,914 | 900 | 1,505 | 76.6 | 117.1 | 3.306 | 1.0049 | 0,0,0 | 1.36 |
| hudson_lynx_hare-lotka_volterra | owalnuts-stan-style | 1/3 | 9.98 | 233,453 | 424 | 643 | 42.5 | 64.4 | 1.894 | 1.0121 | 0,0,0 | 1.21 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 10.73 | 275,324 | 958 | 1,318 | 81.6 | 111.2 | 3.479 | 1.0063 | 0,0,0 | 1.51 |
| hudson_lynx_hare-lotka_volterra | nutpie | timeout_or_crash | — | — | — | — | — | — | — | — |  | — |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 8.21 | 1,288,733 | 93 | 75 | 11.0 | 9.1 | 0.069 | 1.0645 | 0,0,0 | 2.68 |
| mcycle_gp-accel_gp | owalnuts-stan-style | 0/3 | 8.83 | 1,241,133 | 19 | 27 | 2.4 | 3.3 | 0.019 | 1.1542 | 0,0,0 | 3.04 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 33.12 | 5,630,929 | 1,178 | 822 | 36.6 | 25.5 | 0.210 | 1.0040 | 91,78,42 | 3.28 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 70.99 | 3,618,777 | 694 | 928 | 9.9 | 12.2 | 0.194 | 1.0059 | 102,123,123 | 2.28 |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| comparison | models | bulk ESS/grad ratio | bulk ESS/s ratio | wall/grad ratio | wins ESS/s | wins ESS/grad | wins outright (gates >=, ESS/grad >, ESS/s >) |
|---|---:|---:|---:|---:|---:|---:|---|
| owalnuts-da_over_cmdstan | 17 | 0.344 | 0.492 | 0.751 | 3 | 0 | none |
| owalnuts-stan-style_over_cmdstan | 17 | 0.346 | 0.462 | 0.792 | 4 | 0 | none |
| owalnuts-da_over_nutpie | 16 | 0.296 | 1.350 | 0.225 | 10 | 1 | one_comp_mm_elim_abs-one_comp_mm_elim_abs |
| owalnuts-stan-style_over_nutpie | 16 | 0.308 | 1.309 | 0.238 | 10 | 1 | one_comp_mm_elim_abs-one_comp_mm_elim_abs |

## v3 versus v2 (seed medians; ratio v3 / v2; same protocol and settings, seeds 78101-78103 -> 79101-79103; the only sampler change is the WP24 warmup exhaustion rule in the DA arm)

| model | arm | v2 gates | v3 gates | v2 ESS/grad x1e3 | v3 ESS/grad x1e3 | ESS/grad v3/v2 | ESS/s v3/v2 | wall v3/v2 | grads v3/v2 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 3/3 | 26.354 | 29.107 | 1.10 | 0.80 | 1.12 | 0.97 |
| eight_schools-eight_schools_noncentered | owalnuts-stan-style | 3/3 | 3/3 | 23.855 | 25.796 | 1.08 | 0.87 | 1.05 | 0.85 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 2/3 | 29.143 | 33.756 | 1.16 | 0.99 | 1.19 | 0.99 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 34.548 | 39.111 | 1.13 | 0.68 | 1.42 | 1.01 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0/3 | 0.563 | 0.231 | 0.41 | 0.38 | 1.12 | 0.89 |
| eight_schools-eight_schools_centered | owalnuts-stan-style | 0/3 | 0/3 | 0.483 | 0.451 | 0.93 | 1.18 | 1.30 | 1.05 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 1.017 | 1.074 | 1.06 | 1.78 | 1.04 | 0.97 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 1.272 | 0.901 | 0.71 | 2.24 | 0.21 | 1.04 |
| diamonds-diamonds | owalnuts-da | 3/3 | 3/3 | 0.183 | 0.156 | 0.85 | 0.95 | 1.00 | 1.06 |
| diamonds-diamonds | owalnuts-stan-style | 3/3 | 2/3 | 0.178 | 0.173 | 0.97 | 0.94 | 1.13 | 0.97 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.206 | 0.219 | 1.06 | 1.02 | 1.07 | 1.02 |
| diamonds-diamonds | nutpie | 0/3 | 1/3 | 0.142 | 0.194 | 1.36 | 1.52 | 0.89 | 0.98 |
| earnings-logearn_interaction | owalnuts-da | 2/3 | 3/3 | 0.175 | 0.177 | 1.01 | 1.25 | 1.03 | 1.30 |
| earnings-logearn_interaction | owalnuts-stan-style | 0/3 | 0/3 | 0.345 | 0.477 | 1.38 | 0.99 | 1.25 | 0.92 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.796 | 0.756 | 0.95 | 1.40 | 0.69 | 1.00 |
| earnings-logearn_interaction | nutpie | 3/3 | 3/3 | 0.994 | 0.903 | 0.91 | 1.24 | 0.72 | 0.99 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 3/3 | 3.116 | 3.030 | 0.97 | 0.86 | 1.10 | 0.99 |
| mesquite-logmesquite_logvash | owalnuts-stan-style | 3/3 | 3/3 | 2.368 | 2.937 | 1.24 | 0.95 | 1.17 | 1.06 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 4.264 | 3.431 | 0.80 | 0.62 | 1.45 | 1.00 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.501 | 4.342 | 0.96 | 0.85 | 1.25 | 1.02 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 3/3 | 2.207 | 2.163 | 0.98 | 0.87 | 1.25 | 1.18 |
| kidiq-kidscore_momhsiq | owalnuts-stan-style | 2/3 | 1/3 | 1.662 | 2.264 | 1.36 | 1.24 | 1.08 | 0.95 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 4.507 | 4.498 | 1.00 | 0.69 | 1.18 | 0.96 |
| kidiq-kidscore_momhsiq | nutpie | 2/3 | 3/3 | 5.425 | 6.118 | 1.13 | 0.86 | 1.30 | 1.00 |
| sblrc-blr | owalnuts-da | 1/3 | 0/3 | 0.617 | 0.413 | 0.67 | 0.54 | 1.18 | 0.99 |
| sblrc-blr | owalnuts-stan-style | 2/3 | 2/3 | 3.764 | 4.211 | 1.12 | 1.02 | 1.11 | 0.96 |
| sblrc-blr | cmdstan | 3/3 | 3/3 | 6.993 | 6.583 | 0.94 | 0.87 | 1.16 | 0.96 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 15.869 | 13.734 | 0.87 | 0.67 | 1.37 | 1.02 |
| nes2000-nes | owalnuts-da | 3/3 | 3/3 | 2.655 | 2.499 | 0.94 | 0.91 | 1.13 | 1.03 |
| nes2000-nes | owalnuts-stan-style | 3/3 | 3/3 | 2.583 | 2.748 | 1.06 | 0.89 | 1.25 | 0.99 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.869 | 4.925 | 1.01 | 0.84 | 1.11 | 1.00 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.519 | 5.704 | 1.03 | 0.91 | 1.13 | 1.00 |
| arK-arK | owalnuts-da | 3/3 | 3/3 | 7.826 | 7.752 | 0.99 | 0.88 | 1.11 | 0.93 |
| arK-arK | owalnuts-stan-style | 3/3 | 3/3 | 8.522 | 7.780 | 0.91 | 0.83 | 1.19 | 1.01 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.557 | 10.404 | 0.99 | 0.77 | 1.12 | 1.00 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.181 | 11.372 | 1.02 | 0.81 | 1.21 | 0.99 |
| arma-arma11 | owalnuts-da | 0/3 | 2/3 | 0.033 | 14.020 | 424.22 | 352.79 | 1.05 | 0.87 |
| arma-arma11 | owalnuts-stan-style | 0/3 | 0/3 | 0.025 | 0.021 | 0.84 | 0.44 | 2.29 | 1.19 |
| arma-arma11 | cmdstan | 2/3 | 2/3 | 73.630 | 72.040 | 0.98 | 0.74 | 1.37 | 1.10 |
| arma-arma11 | nutpie | 2/3 | 3/3 | 146.686 | 133.017 | 0.91 | 0.66 | 1.29 | 0.99 |
| garch-garch11 | owalnuts-da | 3/3 | 3/3 | 11.374 | 15.021 | 1.32 | 1.15 | 1.03 | 0.91 |
| garch-garch11 | owalnuts-stan-style | 3/3 | 2/3 | 10.414 | 14.702 | 1.41 | 1.20 | 0.95 | 0.87 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 21.607 | 20.860 | 0.97 | 0.74 | 1.15 | 1.03 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 25.918 | 25.822 | 1.00 | 0.76 | 1.39 | 1.00 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 2/3 | 2/3 | 0.705 | 0.731 | 1.04 | 0.77 | 1.31 | 0.97 |
| gp_pois_regr-gp_pois_regr | owalnuts-stan-style | 3/3 | 3/3 | 0.675 | 0.812 | 1.20 | 0.81 | 1.34 | 1.03 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 0.931 | 1.073 | 1.15 | 0.69 | 1.60 | 1.06 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 1.066 | 0.883 | 0.83 | 1.79 | 0.69 | 1.03 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 3/3 | 8.892 | 9.767 | 1.10 | 0.81 | 1.31 | 0.97 |
| hmm_example-hmm_example | owalnuts-stan-style | 3/3 | 3/3 | 14.679 | 16.813 | 1.15 | 1.03 | 1.12 | 0.97 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 23.701 | 20.948 | 0.88 | 0.87 | 1.19 | 1.00 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 31.961 | 27.713 | 0.87 | 0.67 | 1.30 | 1.01 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 2/3 | 1/3 | 12.103 | 0.281 | 0.02 | 0.02 | 1.17 | 0.94 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-stan-style | 2/3 | 2/3 | 6.934 | 16.272 | 2.35 | 2.18 | 0.92 | 0.85 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 3/3 | 33.516 | 64.579 | 1.93 | 3.21 | 0.67 | 0.81 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 2/3 | 3/3 | 94.134 | 67.016 | 0.71 | 0.46 | 1.39 | 1.01 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 0/3 | 0/3 | 4.341 | 9.076 | 2.09 | 1.66 | 1.19 | 0.90 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-stan-style | 0/3 | 1/3 | 6.551 | 6.449 | 0.98 | 0.85 | 1.14 | 0.89 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 0/3 | 10.181 | 12.837 | 1.26 | 0.79 | 1.26 | 0.94 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 11.408 | 4.658 | 0.41 | 0.22 | 1.63 | 0.98 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 1/3 | 3/3 | 0.025 | 3.306 | 130.95 | 436.50 | 0.50 | 0.99 |
| hudson_lynx_hare-lotka_volterra | owalnuts-stan-style | 2/3 | 1/3 | 3.067 | 1.894 | 0.62 | 0.48 | 1.17 | 0.94 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 3/3 | 3.642 | 3.479 | 0.96 | 0.46 | 1.89 | 1.00 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 0/3 | 0.126 | — | — | — | — | — |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 0/3 | 0.056 | 0.069 | 1.23 | 0.81 | 1.43 | 0.94 |
| mcycle_gp-accel_gp | owalnuts-stan-style | 0/3 | 0/3 | 0.018 | 0.019 | 1.05 | 0.52 | 1.76 | 1.21 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.283 | 0.210 | 0.74 | 0.48 | 1.55 | 0.95 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.226 | 0.194 | 0.86 | 0.50 | 1.68 | 1.00 |

| arm | v2 cells passed | v3 cells passed | geomean ESS/grad v3/v2 | geomean ESS/s v3/v2 |
|---|---:|---:|---:|---:|
| owalnuts-da | 32 | 35 | 1.51 | 1.41 |
| owalnuts-stan-style | 32 | 29 | 1.11 | 0.90 |
| cmdstan | 35 | 37 | 1.03 | 0.88 |
| nutpie | 27 | 31 | 0.89 | 0.81 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_da_gate_passes_ge_33_of_51 | 35 | True |
| P2_da_arma11_gate_passes_ge_2_of_3 | 2 | True |
| P3_da_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.40_all_models | 0.344 | False |
| P3b_da_geomean_bulk_ess_per_gradient_vs_cmdstan_ge_0.45_excluding_lotka_volterra | 0.323 | False |
| P4_no_model_da_bulk_ess_per_gradient_below_0.8x_v2 | {'eight_schools-eight_schools_centered': 0.41073157819867395, 'sblrc-blr': 0.668620429134289, 'bball_drive_event_0-hmm_drive_0': 0.023254803013913198} | False |
| P5_da_wall_per_gradient_le_1.0x_cmdstan | 0.751 | True |
| reported_da_frozen_cells | [] | reported |
| reported_owalnuts_cells_not_ok | [] | reported |
