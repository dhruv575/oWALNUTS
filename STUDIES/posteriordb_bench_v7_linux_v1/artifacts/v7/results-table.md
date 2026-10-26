# posteriordb benchmark v7 — results

oWALNUTS commit under test: `f097391c`. Seed medians over 3 seeds of the per-cell minimum over gate parameters; `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences, finite draws, no error; `div` = retained divergences per seed; `max|z|` = worst posterior-mean z against posteriordb reference draws (— for the four gates-only posteriors). Walls are contended.

| model | block | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/grad x1e3 | bulk ESS/s | max R-hat | div | max abs z (max over seeds) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| eight_schools-eight_schools_noncentered | house | owalnuts | 3/3 | 0.0 | 72,188 | 2,292 | 1,567 | 31.744 | 70,665.9 | 1.0032 | 0,0,0 | 1.34 |
| eight_schools-eight_schools_noncentered | house | cmdstan | 1/3 | 0.1 | 72,548 | 2,067 | 1,839 | 28.192 | 30,761.5 | 1.0021 | 1,5,0 | 3.01 |
| eight_schools-eight_schools_noncentered | house | nutpie | 0/3 | 0.0 | 55,925 | 2,056 | 1,719 | 36.768 | 46,981.9 | 1.0020 | 4,4,8 | 3.03 |
| eight_schools-eight_schools_centered | house | owalnuts | 0/3 | 0.1 | 203,587 | 119 | 85 | 0.632 | 1,816.6 | 1.0320 | 0,0,1 | 2.52 |
| eight_schools-eight_schools_centered | house | cmdstan | 0/3 | 0.1 | 173,858 | 207 | 130 | 1.192 | 2,405.4 | 1.0156 | 97,73,53 | 2.76 |
| eight_schools-eight_schools_centered | house | nutpie | 0/3 | 0.1 | 112,776 | 94 | 40 | 0.811 | 1,434.1 | 1.0607 | 41,69,23 | 4.55 |
| diamonds-diamonds | house | owalnuts | 3/3 | 70.3 | 6,744,612 | 1,092 | 1,773 | 0.161 | 15.0 | 1.0039 | 0,0,0 | 2.99 |
| diamonds-diamonds | house | cmdstan | 3/3 | 65.5 | 6,472,041 | 1,331 | 1,990 | 0.206 | 20.3 | 1.0031 | 0,0,0 | 2.82 |
| diamonds-diamonds | house | nutpie | 1/3 | 21.2 | 2,055,516 | 365 | 629 | 0.174 | 16.9 | 1.0122 | 0,0,0 | 2.61 |
| diamonds-diamonds | house | owalnuts-dense | 3/3 | 4.3 | 381,271 | 4,551 | 2,424 | 12.112 | 1,036.4 | 1.0038 | 0,0,0 | 2.46 |
| earnings-logearn_interaction | house | owalnuts | 3/3 | 14.3 | 1,542,746 | 1,054 | 1,261 | 0.682 | 73.5 | 1.0063 | 0,0,0 | 3.16 |
| earnings-logearn_interaction | house | cmdstan | 3/3 | 10.6 | 1,343,366 | 1,045 | 1,279 | 0.778 | 100.4 | 1.0037 | 0,0,0 | 2.04 |
| earnings-logearn_interaction | house | nutpie | 2/3 | 8.0 | 732,190 | 628 | 894 | 0.857 | 79.1 | 1.0063 | 0,0,0 | 2.17 |
| earnings-logearn_interaction | house | owalnuts-dense | 3/3 | 5.0 | 480,319 | 1,960 | 1,747 | 4.081 | 389.8 | 1.0018 | 0,0,0 | 1.34 |
| mesquite-logmesquite_logvash | house | owalnuts | 3/3 | 0.3 | 381,912 | 1,482 | 1,836 | 3.880 | 5,511.5 | 1.0034 | 0,0,0 | 1.50 |
| mesquite-logmesquite_logvash | house | cmdstan | 3/3 | 0.3 | 384,966 | 1,512 | 1,621 | 3.920 | 5,042.9 | 1.0025 | 0,0,0 | 1.45 |
| mesquite-logmesquite_logvash | house | nutpie | 3/3 | 0.2 | 197,141 | 707 | 1,164 | 3.584 | 3,811.1 | 1.0072 | 0,0,0 | 1.88 |
| mesquite-logmesquite_logvash | house | owalnuts-dense | 3/3 | 0.1 | 73,763 | 3,658 | 2,643 | 49.672 | 63,974.9 | 1.0036 | 0,0,0 | 2.13 |
| kidiq-kidscore_momhsiq | house | owalnuts | 3/3 | 0.9 | 357,313 | 1,495 | 1,604 | 4.184 | 1,564.5 | 1.0018 | 0,0,0 | 1.90 |
| kidiq-kidscore_momhsiq | house | cmdstan | 3/3 | 0.9 | 373,283 | 1,508 | 1,832 | 4.039 | 1,640.2 | 1.0022 | 0,0,0 | 2.15 |
| kidiq-kidscore_momhsiq | house | nutpie | 3/3 | 0.4 | 139,179 | 766 | 982 | 5.505 | 1,685.8 | 1.0036 | 0,0,0 | 1.28 |
| kidiq-kidscore_momhsiq | house | owalnuts-dense | 3/3 | 0.5 | 144,448 | 3,807 | 2,637 | 23.604 | 7,732.3 | 1.0014 | 0,0,0 | 1.23 |
| sblrc-blr | house | owalnuts | 3/3 | 0.1 | 147,474 | 736 | 839 | 4.932 | 8,258.2 | 1.0032 | 0,0,0 | 2.47 |
| sblrc-blr | house | cmdstan | 3/3 | 0.1 | 124,734 | 866 | 1,034 | 7.042 | 9,687.2 | 1.0040 | 0,0,0 | 2.39 |
| sblrc-blr | house | nutpie | 3/3 | 0.1 | 56,892 | 841 | 1,122 | 14.926 | 12,362.3 | 1.0023 | 0,0,0 | 1.32 |
| nes2000-nes | house | owalnuts | 3/3 | 3.2 | 424,250 | 1,864 | 2,151 | 4.295 | 574.8 | 1.0019 | 0,0,0 | 1.38 |
| nes2000-nes | house | cmdstan | 3/3 | 2.9 | 387,819 | 2,000 | 2,204 | 4.989 | 686.8 | 1.0023 | 0,0,0 | 1.39 |
| nes2000-nes | house | nutpie | 3/3 | 2.5 | 237,509 | 1,201 | 1,898 | 5.078 | 488.9 | 1.0024 | 0,0,0 | 1.70 |
| nes2000-nes | house | owalnuts-dense | 3/3 | 0.8 | 107,409 | 6,285 | 2,617 | 56.343 | 7,522.6 | 1.0026 | 0,0,0 | 1.79 |
| arK-arK | house | owalnuts | 3/3 | 1.5 | 268,945 | 2,313 | 1,967 | 8.627 | 1,592.1 | 1.0025 | 0,0,0 | 2.03 |
| arK-arK | house | cmdstan | 3/3 | 1.3 | 243,862 | 2,712 | 2,271 | 11.123 | 2,022.9 | 1.0025 | 0,0,0 | 1.76 |
| arK-arK | house | nutpie | 3/3 | 1.5 | 172,725 | 1,986 | 2,035 | 11.500 | 1,340.5 | 1.0046 | 0,0,0 | 2.36 |
| arK-arK | house | owalnuts-dense | 3/3 | 0.5 | 76,503 | 5,249 | 2,881 | 65.385 | 10,287.8 | 1.0035 | 0,0,0 | 1.88 |
| arma-arma11 | house | owalnuts | 3/3 | 0.1 | 52,617 | 3,540 | 2,784 | 66.148 | 28,117.4 | 1.0020 | 0,0,0 | 3.28 |
| arma-arma11 | house | cmdstan | 2/3 | 0.3 | 67,827 | 3,352 | 2,259 | 49.415 | 12,106.6 | 1.0012 | 0,0,0 | 1.93 |
| arma-arma11 | house | nutpie | 2/3 | 0.3 | 34,017 | 4,965 | 3,108 | 147.088 | 18,340.5 | 1.0019 | 0,496,0 | 1.94 |
| garch-garch11 | house | owalnuts | 3/3 | 0.3 | 95,690 | 1,738 | 1,452 | 18.640 | 5,221.6 | 1.0027 | 0,0,0 | 1.70 |
| garch-garch11 | house | cmdstan | 3/3 | 0.4 | 91,315 | 1,914 | 1,713 | 20.958 | 5,127.5 | 1.0022 | 0,0,0 | 2.06 |
| garch-garch11 | house | nutpie | 3/3 | 0.5 | 61,898 | 1,611 | 1,861 | 26.271 | 3,253.0 | 1.0031 | 0,0,0 | 1.36 |
| gp_pois_regr-gp_pois_regr | house | owalnuts | 2/3 | 1.7 | 1,162,948 | 605 | 709 | 0.539 | 390.7 | 1.0080 | 0,0,0 | 2.03 |
| gp_pois_regr-gp_pois_regr | house | cmdstan | 0/3 | 1.7 | 1,308,544 | 1,154 | 1,705 | 0.880 | 681.3 | 1.0037 | 13,10,13 | 1.97 |
| gp_pois_regr-gp_pois_regr | house | nutpie | 0/3 | 1.1 | 787,822 | 593 | 414 | 0.754 | 533.9 | 1.0062 | 193,144,147 | 4.13 |
| hmm_example-hmm_example | house | owalnuts | 3/3 | 1.5 | 119,126 | 2,364 | 1,975 | 19.823 | 1,679.3 | 1.0023 | 0,0,0 | 1.55 |
| hmm_example-hmm_example | house | cmdstan | 3/3 | 1.3 | 96,092 | 2,248 | 1,932 | 23.678 | 1,835.4 | 1.0034 | 0,0,0 | 1.79 |
| hmm_example-hmm_example | house | nutpie | 3/3 | 0.8 | 56,593 | 1,775 | 2,061 | 31.049 | 2,091.5 | 1.0014 | 0,0,0 | 2.12 |
| bball_drive_event_0-hmm_drive_0 | house | owalnuts | 3/3 | 8.5 | 96,456 | 3,071 | 1,569 | 31.442 | 368.2 | 1.0029 | 0,0,0 | 2.17 |
| bball_drive_event_0-hmm_drive_0 | house | cmdstan | 1/3 | 5.8 | 80,658 | 20 | 56 | 0.308 | 4.4 | 1.1255 | 0,369,391 | 2.21 |
| bball_drive_event_0-hmm_drive_0 | house | nutpie | 1/3 | 4.4 | 45,881 | 14 | 81 | 0.317 | 3.3 | 1.1949 | 579,0,334 | 1.85 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | owalnuts | 2/3 | 14.7 | 77,636 | 1,161 | 555 | 13.851 | 71.6 | 1.0060 | 0,0,0 | 3.98 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | cmdstan | 0/3 | 14.7 | 75,175 | 658 | 340 | 8.622 | 47.7 | 1.0070 | 30,3,6 | 2.49 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | house | nutpie | 0/3 | 9.8 | 51,479 | 507 | 83 | 9.844 | 51.9 | 1.0149 | 16,27,65 | 3.28 |
| hudson_lynx_hare-lotka_volterra | house | owalnuts | 3/3 | 7.1 | 287,976 | 982 | 1,334 | 3.373 | 139.2 | 1.0025 | 0,0,0 | 1.85 |
| hudson_lynx_hare-lotka_volterra | house | cmdstan | 2/3 (error) | 6.1 | 276,084 | 971 | 1,334 | 3.509 | 159.1 | 1.0057 | 0,0 | 2.04 |
| hudson_lynx_hare-lotka_volterra | house | nutpie | timeout_or_crash | — | — | — | — | — | — | — |  | — |
| mcycle_gp-accel_gp | house | owalnuts | 1/3 | 13.8 | 2,906,750 | 374 | 237 | 0.157 | 33.8 | 1.0171 | 0,0,0 | 3.15 |
| mcycle_gp-accel_gp | house | cmdstan | 0/3 | 25.5 | 6,046,485 | 1,701 | 1,023 | 0.269 | 67.9 | 1.0048 | 24,79,40 | 2.98 |
| mcycle_gp-accel_gp | house | nutpie | 0/3 | 20.1 | 3,589,425 | 747 | 692 | 0.208 | 37.1 | 1.0051 | 93,81,125 | 2.83 |
| GLMM_Poisson_data-GLMM_Poisson_model | new | owalnuts | 0/3 | 0.5 | 380,150 | 34 | 70 | 0.090 | 73.5 | 1.0905 | 0,0,0 | — |
| GLMM_Poisson_data-GLMM_Poisson_model | new | cmdstan | 0/3 | 0.4 | 329,134 | 76 | 96 | 0.260 | 201.0 | 1.0276 | 0,0,0 | — |
| GLMM_Poisson_data-GLMM_Poisson_model | new | nutpie | 0/3 | 0.3 | 163,541 | 94 | 48 | 0.606 | 353.1 | 1.0368 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | owalnuts | 1/3 | 0.2 | 151,354 | 490 | 319 | 3.237 | 2,211.9 | 1.0103 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | cmdstan | 0/3 | 0.2 | 140,349 | 261 | 133 | 1.859 | 1,315.7 | 1.0076 | 0,0,0 | — |
| seeds_data-seeds_centered_model | new | nutpie | 1/3 | 0.1 | 98,788 | 326 | 278 | 3.378 | 2,440.3 | 1.0062 | 0,0,0 | — |
| kilpisjarvi_mod-kilpisjarvi | new | owalnuts | 3/3 | 2.2 | 4,000,330 | 789 | 975 | 0.202 | 395.0 | 1.0034 | 0,0,0 | 2.13 |
| kilpisjarvi_mod-kilpisjarvi | new | cmdstan | 3/3 | 1.6 | 4,421,588 | 1,009 | 1,124 | 0.224 | 620.7 | 1.0050 | 0,0,0 | 1.95 |
| kilpisjarvi_mod-kilpisjarvi | new | nutpie | 1/3 | 0.7 | 1,699,592 | 478 | 449 | 0.278 | 622.2 | 1.0102 | 0,0,0 | 2.10 |
| science_irt-grsm_latent_reg_irt | new | owalnuts | 3/3 | 111.0 | 293,279 | 776 | 1,467 | 2.646 | 6.7 | 1.0072 | 0,0,0 | — |
| science_irt-grsm_latent_reg_irt | new | cmdstan | 1/3 | 94.9 | 247,368 | 614 | 1,553 | 2.458 | 6.4 | 1.0118 | 0,0,0 | — |
| science_irt-grsm_latent_reg_irt | new | nutpie | 3/3 | 47.0 | 122,498 | 612 | 1,410 | 4.994 | 12.3 | 1.0079 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | owalnuts | 0/3 | 117.6 | 443,634 | 399 | 751 | 0.899 | 3.4 | 1.0111 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | cmdstan | 1/3 | 62.4 | 291,580 | 475 | 802 | 1.593 | 7.6 | 1.0066 | 0,0,0 | — |
| radon_all-radon_hierarchical_intercept_centered | new | nutpie | 0/3 | 48.1 | 118,887 | 322 | 609 | 2.707 | 6.3 | 1.0089 | 0,0,0 | — |

## Pass counts

| arm | house /51 | new five /15 | all /66 | new five by model |
|---|---:|---:|---:|---|
| owalnuts | 44 | 7 | 51 | GLMM_Poisson_model 0/3, seeds_centered_model 1/3, kilpisjarvi 3/3, grsm_latent_reg_irt 3/3, radon_hierarchical_intercept_centered 0/3 |
| cmdstan | 33 | 5 | 38 | GLMM_Poisson_model 0/3, seeds_centered_model 0/3, kilpisjarvi 3/3, grsm_latent_reg_irt 1/3, radon_hierarchical_intercept_centered 1/3 |
| nutpie | 27 | 5 | 32 | GLMM_Poisson_model 0/3, seeds_centered_model 1/3, kilpisjarvi 1/3, grsm_latent_reg_irt 3/3, radon_hierarchical_intercept_centered 0/3 |

## Head-to-head (geometric mean of seed-median ratios over models complete on both sides)

| statistic | models | value |
|---|---:|---:|
| fixed16_bulk_ess_per_gradient_vs_cmdstan | 15 | 1.154 |
| all22_bulk_ess_per_gradient_vs_cmdstan | 21 | 1.065 |
| house17_bulk_ess_per_gradient_vs_cmdstan | 16 | 1.165 |
| fixed16_wall_per_gradient_vs_cmdstan | 15 | 0.942 |
| fixed16_bulk_ess_per_second_vs_cmdstan | 15 | 1.215 |
| house17_bulk_ess_per_second_vs_nutpie | 16 | 1.454 |
| all22_bulk_ess_per_gradient_vs_nutpie | — | 0.837 |

## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed

| seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | target calls | divergences | final steps |
|---|---:|---:|---:|---|---:|---:|---|
| 560571 | 0.0499 | +0.29 | +0.30 | 554 / 1.006 | 3,819,941 | 0 | 0.0596, 0.107, 0.0758, 0.112 |
| 560572 | 0.0446 | -0.53 | -0.55 | 713 / 1.004 | 3,177,065 | 0 | 0.228, 0.137, 0.132, 0.131 |
| 560573 | 0.0531 | +0.55 | +0.60 | 511 / 1.013 | 5,144,155 | 0 | 0.0618, 0.0961, 0.138, 0.0104 |
| pooled (batch means) | 0.0492 | — | +0.33 | — | — | — | — |

## Descriptive dense arm (non-decision): `Metric::dense()` at the commit's dense defaults

| model | dense gates | defaults gates | dense/defaults ESS/grad | dense/CmdStan ESS/grad | dense max abs z |
|---|---|---|---:|---:|---:|
| diamonds-diamonds | 3/3 | 3/3 | 75.285 | 58.886 | 2.46 |
| earnings-logearn_interaction | 3/3 | 3/3 | 5.981 | 5.247 | 1.34 |
| mesquite-logmesquite_logvash | 3/3 | 3/3 | 12.803 | 12.670 | 2.13 |
| kidiq-kidscore_momhsiq | 3/3 | 3/3 | 5.641 | 5.844 | 1.23 |
| nes2000-nes | 3/3 | 3/3 | 13.117 | 11.294 | 1.79 |
| arK-arK | 3/3 | 3/3 | 7.579 | 5.879 | 1.88 |
| geomean | 18/18 | 18/18 | 12.160 | 10.721 | — |

## v7 versus v6 (house models; different seeds and, for oWALNUTS, different defaults)

| model | arm | v6 gates | v7 gates | v6 ESS/grad x1e3 | v7 ESS/grad x1e3 |
|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | owalnuts | 3/3 | 3/3 | 29.948 | 31.744 |
| eight_schools-eight_schools_noncentered | cmdstan | 1/3 | 1/3 | 29.304 | 28.192 |
| eight_schools-eight_schools_noncentered | nutpie | 0/3 | 0/3 | 44.654 | 36.768 |
| eight_schools-eight_schools_centered | owalnuts | 0/3 | 0/3 | 0.281 | 0.632 |
| eight_schools-eight_schools_centered | cmdstan | 0/3 | 0/3 | 1.210 | 1.192 |
| eight_schools-eight_schools_centered | nutpie | 0/3 | 0/3 | 0.948 | 0.811 |
| diamonds-diamonds | owalnuts | 3/3 | 3/3 | 0.171 | 0.161 |
| diamonds-diamonds | cmdstan | 3/3 | 3/3 | 0.229 | 0.206 |
| diamonds-diamonds | nutpie | 2/3 | 1/3 | 0.196 | 0.174 |
| earnings-logearn_interaction | owalnuts | 3/3 | 3/3 | 0.588 | 0.682 |
| earnings-logearn_interaction | cmdstan | 3/3 | 3/3 | 0.756 | 0.778 |
| earnings-logearn_interaction | nutpie | 3/3 | 2/3 | 0.960 | 0.857 |
| mesquite-logmesquite_logvash | owalnuts | 3/3 | 3/3 | 3.183 | 3.880 |
| mesquite-logmesquite_logvash | cmdstan | 3/3 | 3/3 | 3.724 | 3.920 |
| mesquite-logmesquite_logvash | nutpie | 3/3 | 3/3 | 4.028 | 3.584 |
| kidiq-kidscore_momhsiq | owalnuts | 3/3 | 3/3 | 4.067 | 4.184 |
| kidiq-kidscore_momhsiq | cmdstan | 3/3 | 3/3 | 3.854 | 4.039 |
| kidiq-kidscore_momhsiq | nutpie | 3/3 | 3/3 | 6.430 | 5.505 |
| sblrc-blr | owalnuts | 2/3 | 3/3 | 5.084 | 4.932 |
| sblrc-blr | cmdstan | 3/3 | 3/3 | 6.035 | 7.042 |
| sblrc-blr | nutpie | 3/3 | 3/3 | 17.850 | 14.926 |
| nes2000-nes | owalnuts | 3/3 | 3/3 | 4.528 | 4.295 |
| nes2000-nes | cmdstan | 3/3 | 3/3 | 4.710 | 4.989 |
| nes2000-nes | nutpie | 3/3 | 3/3 | 5.742 | 5.078 |
| arK-arK | owalnuts | 3/3 | 3/3 | 8.334 | 8.627 |
| arK-arK | cmdstan | 3/3 | 3/3 | 10.269 | 11.123 |
| arK-arK | nutpie | 3/3 | 3/3 | 11.947 | 11.500 |
| arma-arma11 | owalnuts | 3/3 | 3/3 | 20.356 | 66.148 |
| arma-arma11 | cmdstan | 1/3 | 2/3 | 0.004 | 49.415 |
| arma-arma11 | nutpie | 2/3 | 2/3 | 152.072 | 147.088 |
| garch-garch11 | owalnuts | 3/3 | 3/3 | 17.503 | 18.640 |
| garch-garch11 | cmdstan | 3/3 | 3/3 | 21.713 | 20.958 |
| garch-garch11 | nutpie | 3/3 | 3/3 | 23.279 | 26.271 |
| gp_pois_regr-gp_pois_regr | owalnuts | 3/3 | 2/3 | 0.718 | 0.539 |
| gp_pois_regr-gp_pois_regr | cmdstan | 0/3 | 0/3 | 1.042 | 0.880 |
| gp_pois_regr-gp_pois_regr | nutpie | 0/3 | 0/3 | 0.680 | 0.754 |
| hmm_example-hmm_example | owalnuts | 3/3 | 3/3 | 19.193 | 19.823 |
| hmm_example-hmm_example | cmdstan | 3/3 | 3/3 | 19.814 | 23.678 |
| hmm_example-hmm_example | nutpie | 3/3 | 3/3 | 27.586 | 31.049 |
| bball_drive_event_0-hmm_drive_0 | owalnuts | 3/3 | 3/3 | 42.047 | 31.442 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | 2/3 | 1/3 | 34.457 | 0.308 |
| bball_drive_event_0-hmm_drive_0 | nutpie | 1/3 | 1/3 | 0.440 | 0.317 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts | 3/3 | 2/3 | 13.579 | 13.851 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | 0/3 | 0/3 | 8.166 | 8.622 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | nutpie | 0/3 | 0/3 | 18.490 | 9.844 |
| hudson_lynx_hare-lotka_volterra | owalnuts | 3/3 | 3/3 | 3.075 | 3.373 |
| hudson_lynx_hare-lotka_volterra | cmdstan | 3/3 | 2/3 | 3.700 | 3.509 |
| hudson_lynx_hare-lotka_volterra | nutpie | 0/3 | 0/3 | 2.939 | — |
| mcycle_gp-accel_gp | owalnuts | 1/3 | 1/3 | 0.232 | 0.157 |
| mcycle_gp-accel_gp | cmdstan | 0/3 | 0/3 | 0.242 | 0.269 |
| mcycle_gp-accel_gp | nutpie | 0/3 | 0/3 | 0.173 | 0.208 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| P1_owalnuts_house_ge_42_of_51 | 44 | True |
| P2_no_passing_owalnuts_cell_max_abs_z_gt_4 | [] | True |
| P3_fixed16_bulk_ess_per_gradient_vs_cmdstan_ge_0.75 | 1.154 | None |
| P4_fixed16_wall_per_gradient_vs_cmdstan_le_1.0 | 0.942 | None |
| P5_owalnuts_new_ge_6_of_15 | 7 | True |
| P6_seeds_centered_owalnuts_0_of_3_with_zero_divergences | {'passed': 1, 'divergences': [0, 0, 0]} | False |
| P7_cmdstan_new_ge_8_of_15 | 5 | False |
| P8_funnel_abs_z_le_2_every_seed | [0.291902861605804, -0.5292285627530451, 0.547840389781723] | True |
| reported_all22_bulk_ess_per_gradient_vs_cmdstan | 1.065 | reported |
| reported_house17_bulk_ess_per_second_vs_nutpie | 1.454 | reported |
| reported_pass_counts | {'owalnuts': {'house_of_51': 44, 'new_of_15': 7, 'all_of_66': 51, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 1, 'kilpisjarvi_mod-kilpisjarvi': 3, 'science_irt-grsm_latent_reg_irt': 3, 'radon_all-radon_hierarchical_intercept_centered': 0}}, 'cmdstan': {'house_of_51': 33, 'new_of_15': 5, 'all_of_66': 38, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 0, 'kilpisjarvi_mod-kilpisjarvi': 3, 'science_irt-grsm_latent_reg_irt': 1, 'radon_all-radon_hierarchical_intercept_centered': 1}}, 'nutpie': {'house_of_51': 27, 'new_of_15': 5, 'all_of_66': 32, 'recorded_house': 51, 'recorded_new': 15, 'new_by_model': {'GLMM_Poisson_data-GLMM_Poisson_model': 0, 'seeds_data-seeds_centered_model': 1, 'kilpisjarvi_mod-kilpisjarvi': 1, 'science_irt-grsm_latent_reg_irt': 3, 'radon_all-radon_hierarchical_intercept_centered': 0}}} | reported |

**Release rule (primary, v6 verbatim incl. P4 wall):** `False`
**Release rule (secondary, without P4 wall):** `False`
