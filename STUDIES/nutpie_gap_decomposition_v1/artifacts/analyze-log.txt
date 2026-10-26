# WP80 nutpie gap decomposition — results

## Part 1: per-model split over 18 seeds (cells on disk)

Logs are nutpie over oWALNUTS (positive = nutpie ahead); mean over paired ok seeds. G = A + B + C exactly.

Mean over the 15 entering models: G 0.233 (lead x1.262; from WP76's per-model (c): x1.431), A -0.376, B 0.580, C 0.028. P1 (top three = sblrc-blr, bball_drive_event_0-hmm_drive_0, eight_schools-eight_schools_centered): held = False; top-three share of sum G 0.611.

| rank | model | seeds | (c) o/n | G | A ESS/draw | B sampling grad/draw | C warmup | share of sum G | grad/draw o / n | B4 (cell, built) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 1 | sblrc-blr | 18 | 0.342 | 1.017 | 0.034 | 0.813 | 0.171 | 0.291 | 14.8 / 6.6 | 0.007 |
| 2 | eight_schools-eight_schools_centered | 18 | 0.607 | 0.656 | -0.210 | 1.139 | -0.273 | 0.188 | 35.5 / 11.9 | 0.855 |
| 3 | hmm_example-hmm_example | 18 | 0.634 | 0.458 | -0.268 | 0.551 | 0.175 | 0.131 | 11.8 / 6.8 | 0.009 |
| 4 | mcycle_gp-accel_gp | 18 | 0.610 | 0.402 | 0.673 | -0.210 | -0.061 | 0.115 | 376.9 / 426.2 | 0.019 |
| 5 | earnings-logearn_interaction | 18 | 0.686 | 0.366 | -0.388 | 0.673 | 0.082 | 0.105 | 176.6 / 91.8 | 0.001 |
| 6 | kidiq-kidscore_momhsiq | 18 | 0.734 | 0.336 | -0.593 | 0.681 | 0.247 | 0.096 | 33.6 / 16.9 | 0.006 |
| 7 | arK-arK | 18 | 0.730 | 0.302 | -0.122 | 0.405 | 0.020 | 0.087 | 31.1 / 20.8 | 0.010 |
| 8 | nes2000-nes | 18 | 0.732 | 0.298 | -0.293 | 0.582 | 0.009 | 0.085 | 50.8 / 28.1 | 0.005 |
| 9 | garch-garch11 | 18 | 0.750 | 0.286 | -0.133 | 0.443 | -0.024 | 0.082 | 11.4 / 7.3 | 0.042 |
| 10 | eight_schools-eight_schools_noncentered | 18 | 0.756 | 0.249 | 0.008 | 0.185 | 0.056 | 0.071 | 8.0 / 6.7 | 0.094 |
| 11 | mesquite-logmesquite_logvash | 18 | 0.841 | 0.153 | -0.515 | 0.739 | -0.070 | 0.044 | 49.2 / 23.7 | 0.008 |
| 12 | gp_pois_regr-gp_pois_regr | 18 | 0.741 | 0.112 | -0.293 | 0.404 | 0.002 | 0.032 | 136.1 / 92.6 | 0.011 |
| 13 | diamonds-diamonds | 18 | 1.037 | -0.053 | -1.210 | 1.342 | -0.185 | -0.015 | 975.0 / 252.9 | 0.000 |
| 14 | one_comp_mm_elim_abs-one_comp_mm_elim_abs | 18 | 1.207 | -0.162 | -0.597 | 0.410 | 0.025 | -0.046 | 8.9 / 6.0 | 0.132 |
| 15 | bball_drive_event_0-hmm_drive_0 | 18 | 0.484 | -0.932 | -1.734 | 0.552 | 0.250 | -0.267 | 7.6 / 4.6 | 0.041 |
| — | hudson_lynx_hare-lotka_volterra (excluded: 11 paired ok seeds) | | | | | | | | | |

## Part 3: telemetry (seeds 720701-720703)

Same-seed identity with WP72 / WP76 cells: oWALNUTS 12/12, nutpie 12/12.

| model | seeds | G | A | C | B | B4 refinement | B1 step | B2 distance | ln e o / n | S o / n |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| sblrc-blr | 3 | 0.968 | 0.014 | 0.141 | 0.813 | 0.005 | 0.349 | 0.460 | -1.099 / -0.750 | 0.867 / 0.270 |
| bball_drive_event_0-hmm_drive_0 | 3 | -0.502 | -1.476 | 0.197 | 0.777 | 0.010 | 0.608 | 0.160 | -0.740 / -0.132 | 0.475 / 0.146 |
| eight_schools-eight_schools_centered | 3 | 0.003 | -1.179 | -0.447 | 1.629 | 1.377 | 0.213 | 0.040 | -1.439 / -1.226 | 0.312 / 0.520 |
| diamonds-diamonds | 3 | -0.165 | -1.301 | -0.188 | 1.324 | 0.000 | 2.621 | -1.298 | -5.550 / -2.929 | 0.298 / 1.806 |

| hypothesis | criterion | per carrying model | supported |
|---|---|---|---|
| H1_step | B1 >= ln 1.25 on >= 2 of 3 | blr 0.349, hmm_drive_0 0.608, eight_schools_centered 0.213 | True |
| H2_distance_per_draw | B2 >= ln 1.25 on >= 2 of 3 | blr 0.460, hmm_drive_0 0.160, eight_schools_centered 0.040 | False |
| H4_refinement_spend | B4 >= ln 1.25 on >= 2 of 3 | blr 0.005, hmm_drive_0 0.010, eight_schools_centered 1.377 | False |
| H5_ess_per_draw | A >= ln 1.25 on >= 2 of 3 | blr 0.014, hmm_drive_0 -1.476, eight_schools_centered -1.179 | False |
| H3_metric_match | S_o - S_n >= 0.35 on >= 2 of 3 | blr 0.598, hmm_drive_0 0.329, eight_schools_centered -0.208 | False |

| rank | component | mean over carrying models |
|---:|---|---:|
| 1 | B4 | 0.464 |
| 2 | B1 | 0.390 |
| 3 | B2 | 0.220 |
| 4 | C | -0.036 |
| 5 | A | -0.880 |

P2 (first-ranked = B1): held = False

## Orbit telemetry per cell

| model | seed | o grad/draw | o leaves att/built/orbit | o depth mode | o refined frac | n grad/draw | n depth mode | n accept | step o / n (raw) |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| sblrc-blr | 720701 | 15.1 | 15.0/15.0/11.8 | 3 | 0.004 | 6.5 | 2 | 0.816 | 0.1016 / 0.6070 |
| sblrc-blr | 720702 | 14.6 | 14.5/14.5/11.3 | 3 | 0.009 | 6.5 | 2 | 0.801 | 0.1021 / 0.7041 |
| sblrc-blr | 720703 | 14.8 | 14.8/14.7/11.5 | 3 | 0.011 | 6.7 | 2 | 0.815 | 0.1084 / 0.6597 |
| bball_drive_event_0-hmm_drive_0 | 720701 | 6.4 | 6.4/6.3/6.9 | 3 | 0.009 | 4.5 | 2 | 0.817 | 0.5906 / 0.8597 |
| bball_drive_event_0-hmm_drive_0 | 720702 | 12.6 | 12.5/12.5/11.9 | 3 | 0.018 | 4.2 | 2 | 0.623 | 0.4301 / 0.8871 |
| bball_drive_event_0-hmm_drive_0 | 720703 | 10.5 | 10.4/10.4/10.1 | 3 | 0.014 | 4.4 | 2 | 0.810 | 0.6294 / 0.8898 |
| eight_schools-eight_schools_centered | 720701 | 53.1 | 12.3/12.1/10.9 | 4 | 0.298 | 10.4 | 3 | 0.600 | 0.2117 / 0.4248 |
| eight_schools-eight_schools_centered | 720702 | 48.5 | 12.4/12.1/10.8 | 4 | 0.341 | 13.1 | 3 | 0.722 | 0.2676 / 0.3885 |
| eight_schools-eight_schools_centered | 720703 | 57.2 | 15.5/15.2/13.5 | 4 | 0.303 | 8.1 | 3 | 0.511 | 0.1984 / 0.3642 |
| diamonds-diamonds | 720701 | 981.9 | 981.7/981.7/960.7 | 10 | 0.011 | 263.4 | 6 | 0.839 | 0.0034 / 0.0650 |
| diamonds-diamonds | 720702 | 927.5 | 927.0/927.0/886.3 | 10 | 0.026 | 248.8 | 6 | 0.841 | 0.0039 / 0.0621 |
| diamonds-diamonds | 720703 | 991.0 | 990.7/990.7/976.0 | 10 | 0.009 | 259.5 | 6 | 0.844 | 0.0034 / 0.0601 |
