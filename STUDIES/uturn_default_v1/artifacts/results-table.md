# U-turn-rule default study — results

Seed medians over 3 seeds (80101–80103) of the per-cell minimum over reference parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; `div` = sampling divergences per seed; `max|z|` = worst posterior-mean z against the posteriordb reference. Arms: `owalnuts-da` = `UTurnRule::Endpoints` (current default), `owalnuts-da-rhosum` = `MomentumSum`, `owalnuts-da-cross` = `EndpointsWithCross`; everything else `Sampler` defaults.

## Per-model cells

| model | arm | gates | wall s | grads | min bulk ESS | min tail ESS | bulk ESS/s | bulk ESS/grad x1e3 | max R-hat | div | depth caps | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| eight_schools-eight_schools_noncentered | owalnuts-da | 3/3 | 0.04 | 68,192 | 2,136 | 1,481 | 55,932.0 | 32.017 | 1.0023 | 0,0,0 | 0,0,0 | 1.37 |
| eight_schools-eight_schools_noncentered | owalnuts-da-rhosum | 3/3 | 0.04 | 67,875 | 1,981 | 1,476 | 44,572.4 | 28.309 | 1.0033 | 0,0,0 | 0,0,0 | 1.42 |
| eight_schools-eight_schools_noncentered | owalnuts-da-cross | 3/3 | 0.04 | 63,301 | 1,928 | 1,529 | 41,969.4 | 29.843 | 1.0028 | 0,0,0 | 0,0,0 | 1.98 |
| eight_schools-eight_schools_centered | owalnuts-da | 0/3 | 0.08 | 160,252 | 53 | 34 | 708.3 | 0.351 | 1.0770 | 1,2,0 | 0,0,0 | 1.61 |
| eight_schools-eight_schools_centered | owalnuts-da-rhosum | 0/3 | 0.11 | 197,040 | 74 | 100 | 580.2 | 0.275 | 1.0558 | 5,0,3 | 0,0,0 | 2.03 |
| eight_schools-eight_schools_centered | owalnuts-da-cross | 0/3 | 0.11 | 163,698 | 59 | 26 | 283.5 | 0.214 | 1.0622 | 0,37,2 | 0,0,0 | 1.87 |
| diamonds-diamonds | owalnuts-da | 3/3 | 88.54 | 5,105,289 | 890 | 1,280 | 9.8 | 0.174 | 1.0061 | 0,0,0 | 754,743,765 | 1.90 |
| diamonds-diamonds | owalnuts-da-rhosum | 3/3 | 63.09 | 3,653,567 | 506 | 671 | 8.3 | 0.140 | 1.0092 | 0,0,0 | 374,406,515 | 2.02 |
| diamonds-diamonds | owalnuts-da-cross | 3/3 | 88.61 | 5,126,042 | 843 | 1,026 | 9.8 | 0.167 | 1.0077 | 0,0,0 | 862,967,954 | 2.17 |
| earnings-logearn_interaction | owalnuts-da | 3/3 | 60.62 | 4,654,206 | 969 | 1,086 | 16.0 | 0.208 | 1.0054 | 0,0,0 | 460,243,234 | 0.63 |
| earnings-logearn_interaction | owalnuts-da-rhosum | 2/3 | 40.74 | 3,390,718 | 661 | 852 | 16.1 | 0.193 | 1.0089 | 0,0,0 | 211,184,166 | 1.07 |
| earnings-logearn_interaction | owalnuts-da-cross | 3/3 | 57.76 | 4,772,453 | 974 | 994 | 17.6 | 0.206 | 1.0027 | 0,0,0 | 473,323,434 | 1.79 |
| mesquite-logmesquite_logvash | owalnuts-da | 3/3 | 0.35 | 323,505 | 949 | 1,156 | 2,711.4 | 2.997 | 1.0042 | 0,0,0 | 0,0,0 | 1.35 |
| mesquite-logmesquite_logvash | owalnuts-da-rhosum | 3/3 | 0.42 | 329,956 | 986 | 1,380 | 2,311.1 | 3.082 | 1.0038 | 0,0,0 | 0,0,0 | 1.09 |
| mesquite-logmesquite_logvash | owalnuts-da-cross | 3/3 | 0.34 | 306,833 | 965 | 1,149 | 2,763.1 | 3.023 | 1.0053 | 0,0,0 | 0,0,0 | 1.10 |
| kidiq-kidscore_momhsiq | owalnuts-da | 3/3 | 1.68 | 463,368 | 940 | 891 | 564.9 | 2.028 | 1.0039 | 0,0,0 | 0,0,0 | 1.51 |
| kidiq-kidscore_momhsiq | owalnuts-da-rhosum | 3/3 | 1.77 | 467,769 | 1,320 | 1,425 | 752.0 | 2.785 | 1.0041 | 0,0,0 | 0,0,0 | 0.52 |
| kidiq-kidscore_momhsiq | owalnuts-da-cross | 3/3 | 1.65 | 452,104 | 909 | 873 | 536.5 | 2.109 | 1.0054 | 0,0,0 | 0,0,0 | 1.16 |
| sblrc-blr | owalnuts-da | 0/3 | 0.54 | 550,993 | 267 | 325 | 483.0 | 0.484 | 1.0234 | 0,0,0 | 0,0,0 | 1.21 |
| sblrc-blr | owalnuts-da-rhosum | 0/3 | 0.48 | 493,457 | 230 | 255 | 488.5 | 0.478 | 1.0131 | 0,0,0 | 0,0,0 | 0.77 |
| sblrc-blr | owalnuts-da-cross | 0/3 | 0.40 | 456,729 | 217 | 257 | 542.7 | 0.476 | 1.0208 | 0,0,0 | 0,0,0 | 0.68 |
| nes2000-nes | owalnuts-da | 3/3 | 4.46 | 402,218 | 1,019 | 1,459 | 227.5 | 2.534 | 1.0033 | 0,0,0 | 0,0,0 | 1.50 |
| nes2000-nes | owalnuts-da-rhosum | 3/3 | 4.71 | 437,570 | 1,298 | 1,813 | 279.6 | 2.983 | 1.0024 | 0,0,0 | 0,0,0 | 1.69 |
| nes2000-nes | owalnuts-da-cross | 3/3 | 4.54 | 399,681 | 968 | 1,478 | 213.3 | 2.421 | 1.0043 | 0,0,0 | 0,0,0 | 1.00 |
| arK-arK | owalnuts-da | 3/3 | 1.33 | 243,108 | 2,067 | 1,972 | 1,564.6 | 8.552 | 1.0038 | 0,0,0 | 0,0,0 | 2.36 |
| arK-arK | owalnuts-da-rhosum | 3/3 | 1.39 | 250,550 | 1,954 | 1,867 | 1,387.9 | 7.797 | 1.0032 | 0,0,0 | 0,0,0 | 0.90 |
| arK-arK | owalnuts-da-cross | 3/3 | 1.23 | 222,160 | 1,827 | 1,697 | 1,483.4 | 8.225 | 1.0041 | 0,0,0 | 0,0,0 | 1.41 |
| arma-arma11 | owalnuts-da | 3/3 | 0.31 | 110,694 | 1,527 | 1,689 | 4,904.0 | 13.792 | 1.0032 | 0,0,0 | 0,0,0 | 0.99 |
| arma-arma11 | owalnuts-da-rhosum | 3/3 | 0.27 | 109,928 | 1,361 | 1,738 | 4,981.7 | 12.382 | 1.0020 | 0,0,0 | 0,0,0 | 1.13 |
| arma-arma11 | owalnuts-da-cross | 3/3 | 0.28 | 101,260 | 1,382 | 1,695 | 5,056.2 | 14.083 | 1.0070 | 0,0,0 | 0,0,0 | 1.09 |
| garch-garch11 | owalnuts-da | 3/3 | 0.38 | 70,020 | 1,022 | 1,316 | 2,715.4 | 14.670 | 1.0034 | 0,0,0 | 0,0,0 | 1.56 |
| garch-garch11 | owalnuts-da-rhosum | 3/3 | 0.48 | 88,542 | 1,647 | 1,908 | 3,415.6 | 18.607 | 1.0043 | 0,0,0 | 0,0,0 | 0.73 |
| garch-garch11 | owalnuts-da-cross | 3/3 | 0.36 | 66,541 | 1,026 | 1,250 | 2,842.5 | 15.522 | 1.0039 | 0,0,0 | 0,0,0 | 1.06 |
| gp_pois_regr-gp_pois_regr | owalnuts-da | 3/3 | 2.35 | 1,080,280 | 866 | 1,304 | 368.4 | 0.813 | 1.0053 | 0,0,0 | 0,0,0 | 2.09 |
| gp_pois_regr-gp_pois_regr | owalnuts-da-rhosum | 2/3 | 2.66 | 1,251,278 | 807 | 712 | 321.5 | 0.687 | 1.0049 | 0,0,0 | 0,0,0 | 1.87 |
| gp_pois_regr-gp_pois_regr | owalnuts-da-cross | 3/3 | 2.45 | 1,126,871 | 823 | 749 | 335.4 | 0.713 | 1.0038 | 0,0,0 | 0,0,0 | 1.59 |
| hmm_example-hmm_example | owalnuts-da | 3/3 | 2.37 | 195,657 | 1,940 | 1,613 | 818.2 | 9.915 | 1.0030 | 0,0,0 | 0,0,0 | 1.20 |
| hmm_example-hmm_example | owalnuts-da-rhosum | 3/3 | 2.21 | 179,610 | 1,704 | 1,426 | 771.9 | 9.524 | 1.0020 | 0,0,0 | 0,0,0 | 1.12 |
| hmm_example-hmm_example | owalnuts-da-cross | 3/3 | 2.52 | 195,754 | 1,811 | 1,480 | 724.8 | 9.274 | 1.0040 | 0,0,0 | 0,0,0 | 1.78 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da | 3/3 | 5.37 | 85,488 | 2,207 | 1,602 | 408.1 | 25.813 | 1.0019 | 0,0,0 | 0,0,0 | 1.99 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da-rhosum | 2/3 | 5.74 | 84,898 | 2,685 | 1,477 | 512.2 | 32.396 | 1.0019 | 0,0,0 | 0,0,0 | 0.84 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-da-cross | 2/3 | 6.35 | 88,217 | 1,381 | 1,231 | 210.1 | 15.727 | 1.0031 | 0,0,0 | 0,0,0 | 1.46 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da | 1/3 | 15.67 | 61,877 | 484 | 256 | 30.9 | 8.114 | 1.0086 | 0,0,0 | 0,0,0 | 2.20 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da-rhosum | 1/3 | 17.25 | 73,871 | 826 | 396 | 48.3 | 11.179 | 1.0051 | 0,0,0 | 0,0,0 | 1.41 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-da-cross | 1/3 | 13.68 | 58,508 | 556 | 373 | 37.4 | 9.384 | 1.0078 | 0,0,0 | 0,0,0 | 4.89 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da | 1/3 | 12.01 | 278,324 | 226 | 704 | 18.9 | 0.814 | 1.0363 | 0,0,0 | 0,0,0 | 1.56 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da-rhosum | 2/3 | 27.73 | 365,725 | 638 | 1,029 | 23.0 | 1.744 | 1.0034 | 0,0,0 | 0,0,0 | 1.20 |
| hudson_lynx_hare-lotka_volterra | owalnuts-da-cross | 1/3 | 17.94 | 291,925 | 62 | 235 | 3.4 | 0.212 | 1.0611 | 0,0,0 | 0,0,0 | 2.65 |
| mcycle_gp-accel_gp | owalnuts-da | 0/3 | 8.86 | 1,330,645 | 95 | 108 | 8.6 | 0.062 | 1.0570 | 0,0,0 | 0,0,5 | 2.55 |
| mcycle_gp-accel_gp | owalnuts-da-rhosum | 1/3 | 22.97 | 3,125,555 | 215 | 57 | 7.5 | 0.068 | 1.0204 | 0,0,0 | 0,0,0 | 2.79 |
| mcycle_gp-accel_gp | owalnuts-da-cross | 0/3 | 7.71 | 1,007,084 | 21 | 24 | 2.8 | 0.021 | 1.1559 | 0,0,0 | 2,0,0 | 2.67 |

## The decision statistic: seed-median min bulk ESS/gradient, candidate / endpoints, per model

`vs CmdStan` = this study's seed-median over the v3 CmdStan seed-median (cited, seeds 79101–79103); `da vs v3 da` = reproduction of the v3 endpoint arm on fresh seeds.

| model | gates da / rhosum / cross | da ESS/grad x1e3 | rhosum ESS/grad x1e3 | **rhosum / da** | per seed | cross / da | grads rhosum/da | da vs CmdStan | rhosum vs CmdStan | da vs v3 da |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 3 / 3 / 3 | 32.017 | 28.309 | **0.88** | 1.31, 0.87, 0.83 | 0.93 | 1.00 | 0.95 | 0.84 | 1.10 |
| eight_schools-eight_schools_centered | 0 / 0 / 0 | 0.351 | 0.275 | **0.78** | 0.21, 2.61, 1.13 | 0.61 | 1.23 | 0.33 | 0.26 | 1.52 |
| diamonds-diamonds | 3 / 3 / 3 | 0.174 | 0.140 | **0.80** | 0.79, 0.82, 0.89 | 0.96 | 0.72 | 0.80 | 0.64 | 1.12 |
| earnings-logearn_interaction | 3 / 2 / 3 | 0.208 | 0.193 | **0.93** | 0.98, 1.11, 0.91 | 0.99 | 0.73 | 0.28 | 0.26 | 1.17 |
| mesquite-logmesquite_logvash | 3 / 3 / 3 | 2.997 | 3.082 | **1.03** | 1.06, 1.00, 1.11 | 1.01 | 1.02 | 0.87 | 0.90 | 0.99 |
| kidiq-kidscore_momhsiq | 3 / 3 / 3 | 2.028 | 2.785 | **1.37** | 1.43, 1.30, 1.12 | 1.04 | 1.01 | 0.45 | 0.62 | 0.94 |
| sblrc-blr | 0 / 0 / 0 | 0.484 | 0.478 | **0.99** | 1.98, 0.82, 0.99 | 0.98 | 0.90 | 0.07 | 0.07 | 1.17 |
| nes2000-nes | 3 / 3 / 3 | 2.534 | 2.983 | **1.18** | 1.29, 1.29, 1.09 | 0.96 | 1.09 | 0.51 | 0.61 | 1.01 |
| arK-arK | 3 / 3 / 3 | 8.552 | 7.797 | **0.91** | 0.91, 0.99, 0.84 | 0.96 | 1.03 | 0.82 | 0.75 | 1.10 |
| arma-arma11 | 3 / 3 / 3 | 13.792 | 12.382 | **0.90** | 1.01, 0.97, 0.90 | 1.02 | 0.99 | 0.19 | 0.17 | 0.98 |
| garch-garch11 | 3 / 3 / 3 | 14.670 | 18.607 | **1.27** | 1.26, 1.06, 1.43 | 1.06 | 1.26 | 0.70 | 0.89 | 0.98 |
| gp_pois_regr-gp_pois_regr | 3 / 2 / 3 | 0.813 | 0.687 | **0.85** | 0.36, 1.17, 0.85 | 0.88 | 1.16 | 0.76 | 0.64 | 1.11 |
| hmm_example-hmm_example | 3 / 3 / 3 | 9.915 | 9.524 | **0.96** | 0.95, 1.00, 0.94 | 0.94 | 0.92 | 0.47 | 0.45 | 1.02 |
| bball_drive_event_0-hmm_drive_0 | 3 / 2 / 2 | 25.813 | 32.396 | **1.26** | 1.23, 1.38, 0.01 | 0.61 | 0.99 | 0.40 | 0.50 | 91.72 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1 / 1 / 1 | 8.114 | 11.179 | **1.38** | 2.57, 1.11, 0.98 | 1.16 | 1.19 | 0.63 | 0.87 | 0.89 |
| hudson_lynx_hare-lotka_volterra | 1 / 2 / 1 | 0.814 | 1.744 | **2.14** | 2.14, 1.06, 0.99 | 0.26 | 1.31 | 0.23 | 0.50 | 0.25 |
| mcycle_gp-accel_gp | 0 / 1 / 0 | 0.062 | 0.068 | **1.09** | 5.17, 0.74, 3.22 | 0.34 | 2.35 | 0.29 | 0.32 | 0.90 |

| arm | cells passed | geomean ratio to da (ESS/grad) | min model ratio | models < 0.85 | models > 1.15 | geomean grads ratio | geomean ESS/s ratio | geomean vs CmdStan v3 | geomean vs v3 da |
|---|---:|---:|---|---|---|---:|---:|---:|---:|
| owalnuts-da | 38 | 1 | — | — | — | 1 | 1 | 0.434 | 1.263 |
| owalnuts-da-rhosum | 37 | **1.064** | 0.78 (eight_schools-eight_schools_centered) | eight_schools-eight_schools_centered 0.78, diamonds-diamonds 0.80, gp_pois_regr-gp_pois_regr 0.85 | kidiq-kidscore_momhsiq 1.37, nes2000-nes 1.18, garch-garch11 1.27, bball_drive_event_0-hmm_drive_0 1.26, one_comp_mm_elim_abs-one_comp_mm_elim_abs 1.38, hudson_lynx_hare-lotka_volterra 2.14 | 1.071 | 1.025 | 0.462 | 1.343 |
| owalnuts-da-cross | 37 | **0.811** | 0.26 (hudson_lynx_hare-lotka_volterra) | eight_schools-eight_schools_centered 0.61, bball_drive_event_0-hmm_drive_0 0.61, hudson_lynx_hare-lotka_volterra 0.26, mcycle_gp-accel_gp 0.34 | one_comp_mm_elim_abs-one_comp_mm_elim_abs 1.16 | 0.957 | 0.764 | 0.352 | 1.024 |

## Funnel tail mass `P(omega < -5)` (exact 0.0478), 4 x 2,000 / 20,000 per seed, pooled over the three seeds (batch means of 500)

| tuning | rule | pooled estimate | s.e. | **z** | per-seed z | target calls (3 seeds) | omega bulk ESS / call x1e3 | depth caps | divergences | retained exhaustions |
|---|---|---:|---:|---:|---|---:|---:|---|---|---|
| paper | endpoints | 0.0521 | 0.0047 | **+0.90** | +0.03, -0.24, +1.57 | 7,159,772 | 0.237 | 64,0,18 | 0,0,0 | 0,0,5 |
| paper | rhosum | 0.0520 | 0.0040 | **+1.03** | +1.78, -1.10, +0.79 | 6,918,105 | 0.270 | 0,11,16 | 0,0,0 | 25,4,3 |
| paper | cross | 0.0453 | 0.0038 | **-0.66** | -0.92, -0.44, +0.19 | 6,145,186 | 0.303 | 0,13,0 | 0,0,1 | 0,0,19 |
| defaults | endpoints | 0.0171 | 0.0027 | **-11.24** | -11.57, -6.01, -4.47 | 8,353,504 | 0.100 | 0,133,6 | 162,24,7 | 2232,362,1948 |
| defaults | rhosum | 0.0313 | 0.0049 | **-3.39** | -3.91, -5.73, +0.02 | 11,470,693 | 0.102 | 29,127,56 | 6,24,3 | 2153,1215,782 |
| defaults | cross | 0.0396 | 0.0068 | **-1.19** | -3.54, +0.01, -0.00 | 5,705,991 | 0.113 | 31,0,9 | 30,181,355 | 1755,2940,2764 |

## Eight Schools strict track (v38/v9 settings: h 0.3, depth 8, eight levels, delta 1, accept 0.95, 4 x 1,000/1,000, threads 1)

| rule | seed | calls | min bulk ESS | min tail ESS | max R-hat | bulk ESS/call | tail ESS/call | wall s (median) | div | exhaustions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| endpoints | 80101 | 111,326 | 1,897 | 1,631 | 1.0024 | 0.01704 | 0.01465 | 0.0538 | 0 | 0 |
| endpoints | 80102 | 110,317 | 2,006 | 1,713 | 1.0032 | 0.01819 | 0.01553 | 0.0522 | 0 | 0 |
| endpoints | 80103 | 110,148 | 1,853 | 1,496 | 1.0023 | 0.01683 | 0.01358 | 0.0514 | 0 | 0 |
| rhosum | 80101 | 122,779 | 2,561 | 1,716 | 1.0028 | 0.02086 | 0.01398 | 0.0633 | 0 | 0 |
| rhosum | 80102 | 124,077 | 2,510 | 1,802 | 1.0021 | 0.02023 | 0.01453 | 0.0654 | 0 | 0 |
| rhosum | 80103 | 121,902 | 1,881 | 1,261 | 1.0026 | 0.01543 | 0.01035 | 0.0627 | 0 | 0 |
| cross | 80101 | 104,561 | 1,800 | 1,432 | 1.0020 | 0.01721 | 0.01370 | 0.0524 | 0 | 0 |
| cross | 80102 | 118,326 | 1,509 | 1,496 | 1.0021 | 0.01275 | 0.01264 | 0.0578 | 0 | 0 |
| cross | 80103 | 108,171 | 2,171 | 1,506 | 1.0017 | 0.02007 | 0.01392 | 0.0523 | 0 | 0 |

| rule | geomean min bulk ESS/call | median | ratio to endpoints | all seeds healthy |
|---|---:|---:|---:|---|
| endpoints | 0.01734 | 0.01704 | 1.000 | True |
| rhosum | 0.01867 | 0.02023 | 1.077 | True |
| cross | 0.01639 | 0.01721 | 0.945 | True |

## Preregistered decision rule

| criterion | value | threshold | held |
|---|---|---|---|
| C1_geomean_ratio_ge_1.10 | 1.064 | 1.1 | False |
| C2_no_model_below_0.85 | 0.781 (eight_schools-eight_schools_centered) | 0.85 | False |
| C3_funnel_tail_mass_abs_z_le_2_both_tunings | paper +1.03, defaults -3.39 | 2.0 | False |
| C4_eight_schools_ess_per_call_ge_0.9 | 1.077 | 0.9 | True |

**Decision: keep `UTurnRule::Endpoints`** (all four criteria must hold).
