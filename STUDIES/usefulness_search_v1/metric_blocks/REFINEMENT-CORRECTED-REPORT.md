# Refinement/error-threshold ablation

Corrected one-versus-eight-level exposed factorial; two-level rows are auxiliary. Not independent validation or standard-NUTS equivalence.

| Target | Levels | Error threshold | WALNUTS pass | Native continuation ratio | Baseline WALNUTS continuation ratio | Reverse calls |
|---|---|---|---|---|---|---|
| arK-arK | 1 | 1.0 | True | 0.721 | 0.900 | 0 |
| sblrc-blr | 1 | 1.0 | True | 0.699 | 1.073 | 0 |
| eight_schools-eight_schools_centered | 1 | 1.0 | False | unqualified | unqualified | 0 |
| garch-garch11 | 1 | 1.0 | True | 1.001 | 1.225 | 0 |
| gp_pois_regr-gp_pois_regr | 1 | 1.0 | False | unqualified | unqualified | 0 |
| arK-arK | 1 | 1000.0 | True | 1.107 | 1.382 | 0 |
| sblrc-blr | 1 | 1000.0 | True | 0.949 | 1.457 | 0 |
| eight_schools-eight_schools_centered | 1 | 1000.0 | False | unqualified | unqualified | 0 |
| garch-garch11 | 1 | 1000.0 | True | 1.014 | 1.241 | 0 |
| gp_pois_regr-gp_pois_regr | 1 | 1000.0 | False | unqualified | unqualified | 0 |
| arK-arK | 2 | 1000.0 | True | 1.107 | 1.382 | 0 |
| sblrc-blr | 2 | 1000.0 | True | 0.949 | 1.457 | 0 |
| eight_schools-eight_schools_centered | 2 | 1000.0 | False | unqualified | unqualified | 8 |
| garch-garch11 | 2 | 1000.0 | True | 1.014 | 1.241 | 0 |
| gp_pois_regr-gp_pois_regr | 2 | 1000.0 | False | unqualified | unqualified | 110 |
| arK-arK | 8 | 1.0 | True | 0.801 | 1.000 | 1794 |
| sblrc-blr | 8 | 1.0 | True | 0.651 | 1.000 | 2545 |
| eight_schools-eight_schools_centered | 8 | 1.0 | False | unqualified | unqualified | 28784 |
| garch-garch11 | 8 | 1.0 | True | 0.817 | 1.000 | 2790 |
| gp_pois_regr-gp_pois_regr | 8 | 1.0 | False | unqualified | unqualified | 11895 |
| arK-arK | 8 | 1000.0 | True | 1.107 | 1.382 | 0 |
| sblrc-blr | 8 | 1000.0 | True | 0.949 | 1.457 | 0 |
| eight_schools-eight_schools_centered | 8 | 1000.0 | False | unqualified | unqualified | 8 |
| garch-garch11 | 8 | 1000.0 | True | 1.014 | 1.241 | 0 |
| gp_pois_regr-gp_pois_regr | 8 | 1000.0 | False | unqualified | unqualified | 118 |

Full workflow ratios, all diagnostics and failures are preserved in JSON. Both accuracy gates are required for each ratio. No runtime comparison or default recommendation.

Permissive-level exact comparisons: [{"model": "arK-arK", "permissive_levels_exact_draw_and_call_parity": true}, {"model": "eight_schools-eight_schools_centered", "permissive_levels_exact_draw_and_call_parity": false}, {"model": "garch-garch11", "permissive_levels_exact_draw_and_call_parity": true}, {"model": "gp_pois_regr-gp_pois_regr", "permissive_levels_exact_draw_and_call_parity": false}, {"model": "sblrc-blr", "permissive_levels_exact_draw_and_call_parity": true}].
