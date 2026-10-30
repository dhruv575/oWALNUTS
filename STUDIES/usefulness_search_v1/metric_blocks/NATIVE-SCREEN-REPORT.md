# Native comparison screen results

Exploratory exposed-model screen, not application validation or simultaneous inference.

Passes out of four fresh seeds:

| Target | walnuts_auto | scaled_original | scaled_fast | fisher_fast | native_draw_diag | native_diag | native_low_rank |
|---|---:|---:|---:|---:|---:|---:|---:|
| arma-arma11 | 4 | 4 | 4 | 4 | 3 | 0 | 0 |
| arK-arK | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| sblrc-blr | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| eight_schools-eight_schools_centered | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| garch-garch11 | 4 | 4 | 4 | 4 | 4 | 4 | 2 |
| gp_pois_regr-gp_pois_regr | 4 | 4 | 4 | 3 | 0 | 0 | 0 |

Promising efficiency screen: False.
Paired accuracy losses versus automatic: 0.

Fast scaled / control geometric ESS-per-gradient and ESS-per-post-import-second ratios:

- arma-arma11: walnuts_auto 1.335/1.191; scaled_original 1.000/1.051; fisher_fast 0.998/1.004; native_draw_diag unqualified; native_diag unqualified; native_low_rank unqualified
- arK-arK: walnuts_auto 1.263/1.148; scaled_original 1.000/1.025; fisher_fast 0.997/0.963; native_draw_diag 4.918/3.863; native_diag 5.458/3.868; native_low_rank 0.412/0.361
- sblrc-blr: walnuts_auto 12.202/5.951; scaled_original 1.000/1.147; fisher_fast 1.030/0.994; native_draw_diag 3.590/3.477; native_diag 3.481/2.291; native_low_rank 0.413/0.258
- eight_schools-eight_schools_centered: walnuts_auto unqualified; scaled_original unqualified; fisher_fast unqualified; native_draw_diag unqualified; native_diag unqualified; native_low_rank unqualified
- garch-garch11: walnuts_auto 1.611/1.404; scaled_original 0.981/1.026; fisher_fast 0.851/0.901; native_draw_diag 1.192/1.070; native_diag 1.063/0.865; native_low_rank unqualified
- gp_pois_regr-gp_pois_regr: walnuts_auto 0.999/0.974; scaled_original 1.000/1.043; fisher_fast unqualified; native_draw_diag unqualified; native_diag unqualified; native_low_rank unqualified

Unqualified pairs have no efficiency claim. JSON preserves all paired ratios and exploratory bootstrap intervals. Native default starts and schedules differ from WALNUTS; these are workflow comparisons. Timing excludes imports and common reference diagnostics. The ARMA exposed replay reproduced native failures without instrumentation. No deployment or application value is established.
