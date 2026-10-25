# posteriordb benchmark v7 — results

oWALNUTS commit under test: `f097391c`. Seed medians over 3 seeds of the per-cell minimum over gate parameters; `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences, finite draws, no error; `div` = retained divergences per seed; `max|z|` = worst posterior-mean z against posteriordb reference draws (— for the four gates-only posteriors). Walls are contended.

| model | block | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/grad x1e3 | bulk ESS/s | max R-hat | div | max abs z (max over seeds) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | house | owalnuts | 3/3 | 0.2 | 69,236 | 2,074 | 1,608 | 28.923 | 13,127.4 | 1.0025 | 0,0,0 | 2.14 |
| eight_schools-eight_schools_noncentered | house | cmdstan | 2/3 | 0.3 | 78,582 | 2,243 | 1,852 | 28.221 | 6,771.2 | 1.0021 | 1,0,0 | 1.62 |
| eight_schools-eight_schools_noncentered | house | nutpie | 0/3 | 0.5 | 55,847 | 2,136 | 1,534 | 38.243 | 4,672.0 | 1.0020 | 2,2,3 | 1.91 |
| eight_schools-eight_schools_centered | house | owalnuts | 0/3 | 0.5 | 234,145 | 54 | 95 | 0.167 | 78.6 | 1.0753 | 5,0,0 | 4.45 |
| eight_schools-eight_schools_centered | house | cmdstan | 0/3 | 0.4 | 160,479 | 155 | 103 | 0.918 | 181.7 | 1.0441 | 69,123,64 | 2.52 |
| eight_schools-eight_schools_centered | house | nutpie | 0/3 | 0.5 | 101,025 | 189 | 109 | 1.869 | 367.7 | 1.0228 | 28,41,20 | 5.69 |
| diamonds-diamonds | house | owalnuts | 3/3 | 412.9 | 6,714,917 | 1,206 | 1,854 | 0.180 | 3.0 | 1.0048 | 0,0,0 | 2.48 |
| diamonds-diamonds | house | cmdstan | 3/3 | 161.7 | 6,331,941 | 1,313 | 1,941 | 0.204 | 8.0 | 1.0053 | 0,0,0 | 2.19 |
| diamonds-diamonds | house | nutpie | 0/3 | 82.8 | 2,072,848 | 391 | 512 | 0.189 | 4.4 | 1.0127 | 0,0,0 | 2.69 |
| diamonds-diamonds | house | owalnuts-dense | 3/3 | 18.1 | 374,065 | 4,537 | 2,435 | 12.128 | 250.4 | 1.0048 | 0,0,0 | 3.05 |
| earnings-logearn_interaction | house | owalnuts | 3/3 | 70.1 | 1,517,690 | 930 | 1,229 | 0.613 | 14.0 | 1.0051 | 0,0,0 | 1.12 |
| earnings-logearn_interaction | house | cmdstan | 3/3 | 47.9 | 1,332,883 | 1,038 | 1,238 | 0.791 | 21.7 | 1.0044 | 0,0,0 | 1.62 |
| earnings-logearn_interaction | house | nutpie | 2/3 | 16.1 | 722,637 | 649 | 885 | 0.900 | 39.0 | 1.0084 | 0,0,0 | 1.82 |
| earnings-logearn_interaction | house | owalnuts-dense | 3/3 | 20.6 | 478,538 | 1,884 | 1,931 | 3.937 | 91.4 | 1.0037 | 0,0,0 | 1.58 |
| mesquite-logmesquite_logvash | house | owalnuts | 3/3 | 3.0 | 371,842 | 1,320 | 1,679 | 3.563 | 366.1 | 1.0082 | 0,0,0 | 1.88 |
| mesquite-logmesquite_logvash | house | cmdstan | 3/3 | 0.8 | 383,910 | 1,407 | 1,671 | 3.723 | 1,882.7 | 1.0026 | 0,0,0 | 2.84 |
| mesquite-logmesquite_logvash | house | nutpie | 3/3 | 1.3 | 196,498 | 814 | 1,112 | 4.071 | 597.7 | 1.0037 | 0,0,0 | 1.85 |
| mesquite-logmesquite_logvash | house | owalnuts-dense | 3/3 | 0.4 | 74,540 | 3,992 | 2,698 | 53.562 | 10,895.0 | 1.0017 | 0,0,0 | 1.17 |
| kidiq-kidscore_momhsiq | house | owalnuts | 3/3 | 5.9 | 340,593 | 1,414 | 1,522 | 3.893 | 237.6 | 1.0029 | 0,0,0 | 1.37 |
| kidiq-kidscore_momhsiq | house | cmdstan | 3/3 | 2.0 | 365,122 | 1,570 | 1,891 | 4.403 | 817.3 | 1.0026 | 0,0,0 | 1.99 |
| kidiq-kidscore_momhsiq | house | nutpie | 3/3 | 1.4 | 140,620 | 877 | 1,206 | 6.342 | 647.5 | 1.0042 | 0,0,0 | 1.63 |
| kidiq-kidscore_momhsiq | house | owalnuts-dense | 3/3 | 2.2 | 146,748 | 3,659 | 2,798 | 25.696 | 1,726.2 | 1.0020 | 0,0,0 | 2.25 |
| sblrc-blr | house | owalnuts | 3/3 | 0.6 | 147,650 | 818 | 965 | 5.073 | 1,211.3 | 1.0039 | 0,0,0 | 1.78 |
| sblrc-blr | house | cmdstan | 3/3 | 0.4 | 122,216 | 766 | 952 | 6.271 | 2,259.0 | 1.0028 | 0,0,0 | 1.51 |
| sblrc-blr | house | nutpie | 3/3 | 0.3 | 56,172 | 812 | 1,164 | 14.308 | 2,767.3 | 1.0027 | 0,0,0 | 1.79 |
| nes2000-nes | house | owalnuts | 3/3 | 17.1 | 414,098 | 1,724 | 1,972 | 4.111 | 100.3 | 1.0026 | 0,0,0 | 2.63 |
| nes2000-nes | house | cmdstan | 3/3 | 6.5 | 397,603 | 1,943 | 2,277 | 4.726 | 256.8 | 1.0020 | 0,0,0 | 2.66 |
| nes2000-nes | house | nutpie | 3/3 | 5.4 | 237,155 | 1,333 | 1,571 | 5.616 | 245.6 | 1.0034 | 0,0,0 | 1.60 |
| nes2000-nes | house | owalnuts-dense | 3/3 | 4.5 | 109,610 | 6,951 | 2,648 | 65.905 | 1,584.5 | 1.0062 | 0,0,0 | 1.74 |
| arK-arK | house | owalnuts | 3/3 | 5.8 | 268,709 | 2,333 | 2,280 | 8.540 | 401.8 | 1.0013 | 0,0,0 | 1.84 |
| arK-arK | house | cmdstan | 3/3 | 2.2 | 237,096 | 2,520 | 2,381 | 10.106 | 1,031.7 | 1.0032 | 0,0,0 | 2.23 |
| arK-arK | house | nutpie | 3/3 | 15.3 | 173,523 | 1,935 | 2,061 | 11.168 | 124.1 | 1.0038 | 0,0,0 | 2.24 |
| arK-arK | house | owalnuts-dense | 3/3 | 1.7 | 76,964 | 5,610 | 2,857 | 73.234 | 3,395.7 | 1.0025 | 0,0,0 | 1.71 |
| arma-arma11 | house | owalnuts | 3/3 | 0.6 | 54,029 | 3,798 | 2,646 | 66.846 | 5,776.5 | 1.0020 | 0,0,0 | 2.44 |
| arma-arma11 | house | cmdstan | 2/3 | 1.0 | 64,684 | 3,339 | 2,831 | 51.615 | 3,196.5 | 1.0013 | 0,0,0 | 1.26 |
| arma-arma11 | house | nutpie | 2/3 | 3.4 | 34,019 | 4,965 | 3,130 | 146.203 | 1,469.9 | 1.0019 | 0,496,0 | 1.50 |
| garch-garch11 | house | owalnuts | 3/3 | 2.0 | 94,880 | 1,981 | 1,886 | 20.522 | 957.1 | 1.0022 | 0,0,0 | 1.78 |
| garch-garch11 | house | cmdstan | 3/3 | 1.1 | 89,478 | 1,919 | 1,932 | 21.445 | 1,732.1 | 1.0026 | 0,0,0 | 1.59 |
| garch-garch11 | house | nutpie | 3/3 | 5.9 | 62,010 | 1,462 | 1,796 | 23.305 | 248.9 | 1.0023 | 0,0,0 | 1.48 |
| gp_pois_regr-gp_pois_regr | house | owalnuts | 3/3 | 12.6 | 1,324,166 | 1,010 | 1,374 | 0.853 | 84.1 | 1.0037 | 0,0,0 | 2.90 |
| gp_pois_regr-gp_pois_regr | house | cmdstan | 0/3 | 4.4 | 1,284,643 | 1,336 | 1,568 | 1.040 | 332.3 | 1.0027 | 6,2,6 | 2.15 |
| gp_pois_regr-gp_pois_regr | house | nutpie | 0/3 | 5.5 | 791,378 | 888 | 913 | 1.123 | 161.2 | 1.0054 | 98,195,138 | 2.70 |
| hmm_example-hmm_example | house | owalnuts | 3/3 | 5.0 | 119,061 | 2,379 | 1,914 | 20.040 | 477.7 | 1.0025 | 0,0,0 | 2.06 |
| hmm_example-hmm_example | house | cmdstan | 3/3 | 2.6 | 95,051 | 1,974 | 2,001 | 20.769 | 872.0 | 1.0023 | 0,0,0 | 1.81 |
| hmm_example-hmm_example | house | nutpie | 3/3 | 16.4 | 56,586 | 1,630 | 1,839 | 28.812 | 92.8 | 1.0039 | 0,0,0 | 1.57 |
| bball_drive_event_0-hmm_drive_0 | house | owalnuts | 3/3 | 16.4 | 86,795 | 2,512 | 1,340 | 28.943 | 153.1 | 1.0026 | 0,0,0 | 2.39 |
| bball_drive_event_0-hmm_drive_0 | house | cmdstan | 2/3 | 8.8 | 76,063 | 3,700 | 1,713 | 43.786 | 361.2 | 1.0025 | 810,0,0 | 2.07 |
| bball_drive_event_0-hmm_drive_0 | house | nutpie | 1/3 | 32.8 | 42,610 | 197 | 782 | 4.675 | 6.0 | 1.0460 | 136,0,577 | 1.70 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | owalnuts | 1/3 | 49.4 | 78,383 | 738 | 394 | 9.640 | 14.9 | 1.0027 | 0,0,0 | 3.82 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | cmdstan | 0/3 | 28.3 | 75,378 | 1,441 | 645 | 19.122 | 50.9 | 1.0044 | 2,2,3 | 5.07 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | nutpie | 0/3 | 65.7 | 50,605 | 340 | 113 | 6.719 | 6.0 | 1.0087 | 32,34,31 | 2.03 |
| hudson_lynx_hare-lotka_volterra | house | owalnuts | 3/3 | 29.3 | 298,749 | 1,102 | 1,334 | 3.627 | 37.1 | 1.0053 | 0,0,0 | 1.94 |
| hudson_lynx_hare-lotka_volterra | house | cmdstan | 1/3 (error) | 10.7 | 268,684 | 468 | 626 | 1.662 | 42.1 | 1.1638 | 0,70 | 3.23 |
| hudson_lynx_hare-lotka_volterra | house | nutpie | timeout_or_crash | — | — | — | — | — | — | — |  | — |
| mcycle_gp-accel_gp | house | owalnuts | 0/3 | 58.0 | 2,850,777 | 280 | 125 | 0.098 | 4.8 | 1.0287 | 0,0,0 | 3.25 |
| mcycle_gp-accel_gp | house | cmdstan | 0/3 | 36.8 | 5,495,064 | 1,627 | 1,254 | 0.283 | 43.1 | 1.0050 | 339,59,55 | 3.17 |
| mcycle_gp-accel_gp | house | nutpie | 0/3 | 74.9 | 3,644,674 | 694 | 669 | 0.190 | 9.1 | 1.0054 | 116,97,91 | 3.28 |
| GLMM_Poisson_data-GLMM_Poisson_model | new | owalnuts | 0/3 | 2.7 | 396,936 | 52 | 59 | 0.119 | 14.3 | 1.0584 | 0,0,0 | — |
| GLMM_Poisson_data-GLMM_Poisson_model | new | cmdstan | 0/3 | 1.0 | 354,928 | 66 | 76 | 0.187 | 63.8 | 1.0476 | 0,0,0 | — |
| GLMM_Poisson_data-GLMM_Poisson_model | new | nutpie | 0/3 | 1.1 | 164,954 | 60 | 60 | 0.248 | 26.5 | 1.0539 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | owalnuts | 0/3 | 1.2 | 157,948 | 238 | 94 | 1.508 | 192.6 | 1.0248 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | cmdstan | 0/3 | 0.5 | 156,128 | 229 | 156 | 1.495 | 447.7 | 1.0067 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | nutpie | 0/3 | 0.6 | 94,960 | 324 | 250 | 3.440 | 571.3 | 1.0065 | 0,0,0 | — |
| kilpisjarvi_mod-kilpisjarvi | new | owalnuts | 3/3 | 11.4 | 4,106,429 | 906 | 1,067 | 0.222 | 79.6 | 1.0040 | 0,0,0 | 1.77 |
| kilpisjarvi_mod-kilpisjarvi | new | cmdstan | 3/3 | 2.6 | 4,390,569 | 1,076 | 1,101 | 0.245 | 369.8 | 1.0029 | 0,0,0 | 1.55 |
| kilpisjarvi_mod-kilpisjarvi | new | nutpie | 0/3 | 3.7 | 1,658,150 | 395 | 361 | 0.239 | 106.0 | 1.0107 | 0,0,0 | 0.94 |
| science_irt-grsm_latent_reg_irt | new | owalnuts | 3/3 | 476.5 | 289,217 | 643 | 1,485 | 2.380 | 1.4 | 1.0071 | 0,0,0 | — |
| science_irt-grsm_latent_reg_irt | new | cmdstan | 3/3 | 198.6 | 246,946 | 665 | 1,257 | 2.730 | 3.3 | 1.0076 | 0,0,0 | — |
| science_irt-grsm_latent_reg_irt | new | nutpie | 3/3 | 329.2 | 122,646 | 540 | 924 | 4.404 | 1.5 | 1.0082 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | owalnuts | 0/3 | 465.4 | 636,569 | 314 | 620 | 0.560 | 0.8 | 1.0092 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | cmdstan | 1/3 | 75.6 | 282,543 | 390 | 715 | 1.368 | 5.1 | 1.0066 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | nutpie | 0/3 | 644.6 | 118,906 | 321 | 591 | 2.699 | 0.5 | 1.0094 | 0,0,0 | — |

## Pass counts

| arm | house /51 | new five /15 | all /66 | new five by model |
|---|---:|---:|---:|---|
| owalnuts | 43 | 6 | 49 | GLMM_Poisson_model 0/3, seeds_centered_model 0/3, kilpisjarvi 3/3, grsm_latent_reg_irt 3/3, radon_hierarchical_intercept_centered 0/3 |
| cmdstan | 34 | 7 | 41 | GLMM_Poisson_model 0/3, seeds_centered_model 0/3, kilpisjarvi 3/3, grsm_latent_reg_irt 3/3, radon_hierarchical_intercept_centered 1/3 |
| nutpie | 26 | 3 | 29 | GLMM_Poisson_model 0/3, seeds_centered_model 0/3, kilpisjarvi 0/3, grsm_latent_reg_irt 3/3, radon_hierarchical_intercept_centered 0/3 |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| statistic | models | value |
|---|---:|---:|
| fixed16_bulk_ess_per_gradient_vs_cmdstan | 15 | 0.708 |
| all22_bulk_ess_per_gradient_vs_cmdstan | 21 | 0.734 |
| house17_bulk_ess_per_gradient_vs_cmdstan | 16 | 0.735 |
| fixed16_wall_per_gradient_vs_cmdstan | 15 | 1.849 |
| fixed16_bulk_ess_per_second_vs_cmdstan | 15 | 0.398 |
| house17_bulk_ess_per_second_vs_nutpie | 16 | 1.226 |
| all22_bulk_ess_per_gradient_vs_nutpie | — | 0.645 |

## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed

| seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | target calls | divergences | final steps |
|---|---:|---:|---:|---|---:|---:|---|
| 560571 | 0.0646 | +1.69 | +1.83 | 523 / 1.010 | 3,969,649 | 1 | 0.0832, 0.123, 0.109, 0.0909 |
| 560572 | 0.0435 | -0.59 | -0.59 | 498 / 1.004 | 6,010,280 | 0 | 0.0259, 0.00877, 0.0606, 0.147 |
| 560573 | 0.0540 | +0.84 | +0.89 | 569 / 1.005 | 4,845,443 | 5 | 0.128, 0.112, 0.0177, 0.199 |
| pooled (batch means) | 0.0540 | — | +1.36 | — | — | — | — |

## Descriptive dense arm (non-decision): `Metric::dense()` at the commit's dense defaults

| model | dense gates | defaults gates | dense/defaults ESS/grad | dense/CmdStan ESS/grad | dense max abs z |
|---|---|---|---:|---:|---:|
| diamonds-diamonds | 3/3 | 3/3 | 67.536 | 59.595 | 3.05 |
| earnings-logearn_interaction | 3/3 | 3/3 | 6.423 | 4.979 | 1.58 |
| mesquite-logmesquite_logvash | 3/3 | 3/3 | 15.032 | 14.387 | 1.17 |
| kidiq-kidscore_momhsiq | 3/3 | 3/3 | 6.601 | 5.836 | 2.25 |
| nes2000-nes | 3/3 | 3/3 | 16.032 | 13.946 | 1.74 |
| arK-arK | 3/3 | 3/3 | 8.575 | 7.246 | 1.71 |
| geomean | 18/18 | 18/18 | 13.449 | 11.664 | — |

## v7 versus v6 (house models; different seeds and, for oWALNUTS, different defaults)

| model | arm | v6 gates | v7 gates | v6 ESS/grad x1e3 | v7 ESS/grad x1e3 |
|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts | 3/3 | 3/3 | 29.948 | 28.923 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 2/3 | 29.304 | 28.221 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 44.654 | 38.243 |
| eight_schools-eight_schools_centered | owalnuts | 0/3 | 0/3 | 0.281 | 0.167 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 1.210 | 0.918 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 0.948 | 1.869 |
| diamonds-diamonds | owalnuts | 3/3 | 3/3 | 0.171 | 0.180 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.229 | 0.204 |
| diamonds-diamonds | nutpie | 2/3 | 0/3 | 0.196 | 0.189 |
| earnings-logearn_interaction | owalnuts | 3/3 | 3/3 | 0.588 | 0.613 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.756 | 0.791 |
| earnings-logearn_interaction | nutpie | 3/3 | 2/3 | 0.960 | 0.900 |
| mesquite-logmesquite_logvash | owalnuts | 3/3 | 3/3 | 3.183 | 3.563 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 3.724 | 3.723 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.028 | 4.071 |
| kidiq-kidscore_momhsiq | owalnuts | 3/3 | 3/3 | 4.067 | 3.893 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 3.854 | 4.403 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 3/3 | 6.430 | 6.342 |
| sblrc-blr | owalnuts | 2/3 | 3/3 | 5.084 | 5.073 |
| sblrc-blr | cmdstan | 3/3 | 3/3 | 6.035 | 6.271 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 17.850 | 14.308 |
| nes2000-nes | owalnuts | 3/3 | 3/3 | 4.528 | 4.111 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.710 | 4.726 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.742 | 5.616 |
| arK-arK | owalnuts | 3/3 | 3/3 | 8.334 | 8.540 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.269 | 10.106 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.947 | 11.168 |
| arma-arma11 | owalnuts | 3/3 | 3/3 | 20.356 | 66.846 |
| arma-arma11 | cmdstan | 1/3 | 2/3 | 0.004 | 51.615 |
| arma-arma11 | nutpie | 2/3 | 2/3 | 152.072 | 146.203 |
| garch-garch11 | owalnuts | 3/3 | 3/3 | 17.503 | 20.522 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 21.713 | 21.445 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 23.279 | 23.305 |
| gp_pois_regr-gp_pois_regr | owalnuts | 3/3 | 3/3 | 0.718 | 0.853 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 1.042 | 1.040 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 0.680 | 1.123 |
| hmm_example-hmm_example | owalnuts | 3/3 | 3/3 | 19.193 | 20.040 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 19.814 | 20.769 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 27.586 | 28.812 |
| bball_drive_event_0-hmm_drive_0 | owalnuts | 3/3 | 3/3 | 42.047 | 28.943 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 2/3 | 34.457 | 43.786 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 1/3 | 1/3 | 0.440 | 4.675 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts | 3/3 | 1/3 | 13.579 | 9.640 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 0/3 | 8.166 | 19.122 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 18.490 | 6.719 |
| hudson_lynx_hare-lotka_volterra | owalnuts | 3/3 | 3/3 | 3.075 | 3.627 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 1/3 | 3.700 | 1.662 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 0/3 | 2.939 | — |
| mcycle_gp-accel_gp | owalnuts | 1/3 | 0/3 | 0.232 | 0.098 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.242 | 0.283 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.173 | 0.190 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_owalnuts_house_ge_42_of_51 | 43 | True |
| P2_no_passing_owalnuts_cell_max_abs_z_gt_4 | [] | True |
| P3_fixed16_bulk_ess_per_gradient_vs_cmdstan_ge_0.75 | 0.708 | None |
| P4_fixed16_wall_per_gradient_vs_cmdstan_le_1.0 | 1.849 | None |
| P5_owalnuts_new_ge_6_of_15 | 6 | True |
| P6_seeds_centered_owalnuts_0_of_3_with_zero_divergences | {'passed': 0, 'divergences': [0, 0, 0]} | True |
| P7_cmdstan_new_ge_8_of_15 | 7 | False |
| P8_funnel_abs_z_le_2_every_seed | [1.6939318592489074, -0.5898133124330701, 0.8365112639665497] | True |
| reported_all22_bulk_ess_per_gradient_vs_cmdstan | 0.734 | reported |
| reported_house17_bulk_ess_per_second_vs_nutpie | 1.226 | reported |
| reported_pass_counts | {'owalnuts': {'house_of_51': 43, 'new_of_15': 6, 'all_of_66': 49, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 0, 'kilpisjarvi_mod-kilpisjarvi': 3, 'science_irt-grsm_latent_reg_irt': 3, 'radon_all-radon_hierarchical_intercept_centered': 0}}, 'cmdstan': {'house_of_51': 34, 'new_of_15': 7, 'all_of_66': 41, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 0, 'kilpisjarvi_mod-kilpisjarvi': 3, 'science_irt-grsm_latent_reg_irt': 3, 'radon_all-radon_hierarchical_intercept_centered': 1}}, 'nutpie': {'house_of_51': 26, 'new_of_15': 3, 'all_of_66': 29, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 0, 'kilpisjarvi_mod-kilpisjarvi': 0, 'science_irt-grsm_latent_reg_irt': 3, 'radon_all-radon_hierarchical_intercept_centered': 0}}} | reported |

**Release rule (primary, v6 verbatim incl. P4 wall):** `False`
**Release rule (secondary, without P4 wall):** `False`
