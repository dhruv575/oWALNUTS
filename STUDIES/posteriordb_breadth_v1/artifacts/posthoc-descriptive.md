# Post-hoc descriptive telemetry (not preregistered)

## Chains with final step < 0.2 x the cell median (all completed cells, passing included)

| model | seed | chain | cell passed | step | median step | ratio | warmup caps | retained caps | metric installed/empirical max | chain min bulk ESS | chain H0 median - others | exhaustions | cell grads / model median |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| earnings-logearn_height_male | 461463 | 3 | True | 0.00327 | 0.0272 | 0.121 | 0 | 0 | 75.7 | 205 | -0.0 | 0 | 1.00 |
| GLMM_Poisson_data-GLMM_Poisson_model | 461461 | 2 | False | 0.00224 | 0.121 | 0.018 | 225 | 343 | 29.1 | 1 | +274.5 | 0 | 0.82 |
| GLMM_Poisson_data-GLMM_Poisson_model | 461463 | 0 | False | 0.00875 | 0.0851 | 0.103 | 587 | 0 | 1.47e+03 | 38 | -7.1 | 0 | 1.00 |
| low_dim_gauss_mix-low_dim_gauss_mix | 461462 | 2 | True | 0.00871 | 0.61 | 0.014 | 401 | 0 | 1.3e+04 | 329 | -0.0 | 0 | 5.18 |

4 collapsed chains in 4 cells.

## Gradient cost per cell

| model | seed | passed | gradients | warmup share | / model median |
|---|---:|---|---:|---:|---:|
| bball_drive_event_1-hmm_drive_1 | 461461 | True | 184,130 | 0.71 | 0.78 |
| bball_drive_event_1-hmm_drive_1 | 461462 | True | 235,219 | 0.75 | 1.00 |
| bball_drive_event_1-hmm_drive_1 | 461463 | True | 565,354 | 0.90 | 2.40 |
| earnings-logearn_height_male | 461461 | True | 1,004,049 | 0.54 | 1.04 |
| earnings-logearn_height_male | 461462 | True | 889,871 | 0.55 | 0.92 |
| earnings-logearn_height_male | 461463 | True | 962,601 | 0.52 | 1.00 |
| earnings-logearn_logheight_male | 461461 | True | 2,647,082 | 0.44 | 0.96 |
| earnings-logearn_logheight_male | 461462 | True | 2,744,380 | 0.41 | 1.00 |
| earnings-logearn_logheight_male | 461463 | True | 2,999,092 | 0.42 | 1.09 |
| GLMM_Poisson_data-GLMM_Poisson_model | 461461 | False | 1,307,391 | 0.56 | 0.82 |
| GLMM_Poisson_data-GLMM_Poisson_model | 461462 | False | 2,988,939 | 0.62 | 1.87 |
| GLMM_Poisson_data-GLMM_Poisson_model | 461463 | False | 1,597,820 | 0.75 | 1.00 |
| gp_pois_regr-gp_regr | 461461 | True | 40,283 | 0.52 | 1.00 |
| gp_pois_regr-gp_regr | 461462 | True | 40,605 | 0.53 | 1.01 |
| gp_pois_regr-gp_regr | 461463 | True | 38,669 | 0.51 | 0.96 |
| kidiq-kidscore_interaction | 461461 | False | 707,974 | 0.52 | 0.97 |
| kidiq-kidscore_interaction | 461462 | True | 732,184 | 0.51 | 1.01 |
| kidiq-kidscore_interaction | 461463 | True | 726,440 | 0.50 | 1.00 |
| kidiq_with_mom_work-kidscore_interaction_c2 | 461461 | True | 89,273 | 0.66 | 1.00 |
| kidiq_with_mom_work-kidscore_interaction_c2 | 461462 | True | 87,448 | 0.66 | 0.98 |
| kidiq_with_mom_work-kidscore_interaction_c2 | 461463 | True | 89,858 | 0.66 | 1.01 |
| kidiq_with_mom_work-kidscore_mom_work | 461461 | True | 158,665 | 0.72 | 1.01 |
| kidiq_with_mom_work-kidscore_mom_work | 461462 | True | 156,653 | 0.71 | 1.00 |
| kidiq_with_mom_work-kidscore_mom_work | 461463 | True | 157,354 | 0.72 | 1.00 |
| kilpisjarvi_mod-kilpisjarvi | 461461 | True | 4,195,604 | 0.43 | 1.02 |
| kilpisjarvi_mod-kilpisjarvi | 461462 | False | 3,960,177 | 0.44 | 0.96 |
| kilpisjarvi_mod-kilpisjarvi | 461463 | True | 4,104,724 | 0.42 | 1.00 |
| low_dim_gauss_mix-low_dim_gauss_mix | 461461 | True | 76,927 | 0.66 | 0.73 |
| low_dim_gauss_mix-low_dim_gauss_mix | 461462 | True | 548,532 | 0.94 | 5.18 |
| low_dim_gauss_mix-low_dim_gauss_mix | 461463 | True | 105,866 | 0.75 | 1.00 |
| mesquite-logmesquite_logvas | 461461 | True | 418,829 | 0.48 | 1.00 |
| mesquite-logmesquite_logvas | 461462 | True | 409,352 | 0.50 | 0.98 |
| mesquite-logmesquite_logvas | 461463 | True | 417,016 | 0.48 | 1.00 |
| mesquite-mesquite | 461461 | True | 666,117 | 0.67 | 0.97 |
| mesquite-mesquite | 461462 | True | 683,436 | 0.70 | 1.00 |
| mesquite-mesquite | 461463 | True | 684,486 | 0.68 | 1.00 |
| nes1980-nes | 461461 | True | 380,808 | 0.51 | 1.01 |
| nes1980-nes | 461462 | True | 376,117 | 0.53 | 1.00 |
| nes1980-nes | 461463 | True | 368,852 | 0.55 | 0.98 |
| nes1996-nes | 461461 | True | 417,935 | 0.51 | 1.05 |
| nes1996-nes | 461462 | True | 392,008 | 0.54 | 0.99 |
| nes1996-nes | 461463 | True | 397,837 | 0.50 | 1.00 |
| radon_all-radon_hierarchical_intercept_centered | 461461 | True | 342,060 | 0.64 | 0.93 |
| radon_all-radon_hierarchical_intercept_centered | 461462 | True | 395,943 | 0.69 | 1.08 |
| radon_all-radon_hierarchical_intercept_centered | 461463 | True | 367,168 | 0.66 | 1.00 |
| sat-hier_2pl | 461461 | True | 898,705 | 0.86 | 1.25 |
| sat-hier_2pl | 461462 | True | 485,709 | 0.75 | 0.68 |
| sat-hier_2pl | 461463 | True | 718,580 | 0.84 | 1.00 |
| sblri-blr | 461461 | True | 85,697 | 0.62 | 1.00 |
| sblri-blr | 461462 | True | 81,840 | 0.61 | 0.95 |
| sblri-blr | 461463 | True | 89,825 | 0.63 | 1.05 |
| science_irt-grsm_latent_reg_irt | 461461 | False | 308,512 | 0.70 | 1.00 |
| science_irt-grsm_latent_reg_irt | 461462 | True | 270,604 | 0.59 | 0.88 |
| science_irt-grsm_latent_reg_irt | 461463 | True | 318,993 | 0.66 | 1.03 |
| seeds_data-seeds_centered_model | 461461 | False | 155,973 | 0.53 | 0.92 |
| seeds_data-seeds_centered_model | 461462 | False | 169,249 | 0.56 | 1.00 |
| seeds_data-seeds_centered_model | 461463 | False | 183,518 | 0.44 | 1.08 |
