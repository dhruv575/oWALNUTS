# Matched-geometry diagnostic

Exposed single-seed diagnostic; no fresh efficacy or application claim.

| Target | Native pass | WALNUTS pass | ESS/call ratio, continuation | ESS/call ratio, full workflow |
|---|---|---|---|---|
| arma-arma11 | unavailable | unavailable | unqualified | unqualified |
| arK-arK | True | True | 0.801 | 0.839 |
| sblrc-blr | True | True | 0.651 | 0.699 |
| eight_schools-eight_schools_centered | False | False | unqualified | unqualified |
| garch-garch11 | True | True | 0.817 | 0.859 |
| gp_pois_regr-gp_pois_regr | False | False | unqualified | unqualified |

ARMA failed the reconstruction gate before WALNUTS sampling; retain this failure. All other workers completed. The three qualified pairs favor native NUTS at these shared geometries and native-tuned fixed steps. This does not establish native superiority under WALNUTS-specific step tuning. Do not use wall time: parallelism differs.

Default native step-size jitter caused the first prefix qualification to fail its fixed-step requirement. A separate no-jitter batch passed all six prefix, geometry/step and actual-call difference checks. Original benchmark settings and results were not changed.

Next diagnostic: a prespecified bounded WALNUTS step-size ladder on these exposed metrics, followed by fresh whole-pilot replication only if a meaningful qualified signal emerges. No selection on these data can count as confirmation.
