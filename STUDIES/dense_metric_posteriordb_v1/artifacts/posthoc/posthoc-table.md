# Post-hoc diagnostic: dense-stan with symmetrized precision (NOT preregistered evidence)

Seeds 148201-148203, the three target models, arms owalnuts-diag and owalnuts-dense-stan-sym (PerTransition seeding + Stan regularisation + `with_dense_symmetrized_precision(true)`). Run after every preregistered cell, to test the mechanism found in the analysis; walls contended.

| model | arm | gates | median grads | median min bulk ESS | bulk ESS/grad x1e3 | ratio vs diag | median step | kappa | max ridge (last window) | max R-hat | divergences |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| diamonds-diamonds | owalnuts-diag | 3/3 | 6,676,914 | 1,118 | 0.169 | 1.00 | 0.0033 | 2.73e+05 | 0 | 1.0038 | [0, 0, 0] |
| diamonds-diamonds | owalnuts-dense-stan-sym | 3/3 | 372,526 | 4,368 | 11.096 | 65.66 | 0.283 | 19.1 | 0 | 1.0030 | [0, 0, 0] |
| gp_pois_regr-gp_pois_regr | owalnuts-diag | 2/3 | 1,136,033 | 878 | 0.783 | 1.00 | 0.0297 | 555 | 0 | 1.0032 | [0, 0, 0] |
| gp_pois_regr-gp_pois_regr | owalnuts-dense-stan-sym | 2/3 | 321,765 | 518 | 1.517 | 1.94 | 0.158 | 3.46 | 0 | 1.0090 | [0, 0, 0] |
| mcycle_gp-accel_gp | owalnuts-diag | 0/3 | 2,541,338 | 252 | 0.099 | 1.00 | 0.00855 | 1.06e+03 | 0 | 1.0226 | [0, 0, 0] |
| mcycle_gp-accel_gp | owalnuts-dense-stan-sym | 0/3 | 992,205 | 214 | 0.132 | 1.34 | 0.0524 | 17.6 | 0 | 1.0272 | [0, 0, 0] |
