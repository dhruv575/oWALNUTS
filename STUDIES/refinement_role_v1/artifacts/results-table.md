# refinement_role_v1 — results

Seed medians over 3 seeds (89101–89103) of the per-cell minimum over reference parameters; `gates` = cells passing R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences; CmdStan from `posteriordb_bench_v5` (seeds 87101–87103).

## Instrumentation (arm `da` = the shipped defaults, v5 seed 87101, one cell per model)

`h ratio` = median adapted `h` over the four chains / median of the twelve v5 CmdStan chain steps; `refined` = fraction of retained built leaves accepted above level 0; `rc stop` = fraction of retained transitions ending in a reverse-coarser stop; `P(|dH|>1)` at level 0 from the trace at the adapted `h`, at CmdStan's `h` and at 2`h`; `E exp(-|dH|)` is the statistic dual averaging drives to 0.8; `Stan acc` the mean of `min(1, exp(-dH))` at the same step.

| model | v5 repro | h_walnuts | h_cmdstan | h ratio | refined | rc stop | leaves/orbit | grads/leaf | acc stat | P(\|dH\|>1) @h | @h_stan | @2h | @3h | E exp(-\|dH\|) @h | Stan acc @h | Stan acc @h_stan | ESS/grad x1e3 (v5 DA / CmdStan) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered | yes | 0.5044 | 0.4167 | 1.21 | 0.0093 | 0.104 | 7.5 | 1.086 | — | 0.0245 | 0.0150 | 0.3870 | 0.8495 | 0.878 | 0.925 | 0.950 | 26.122 (24.720 / 32.978) |
| eight_schools-eight_schools_centered | yes | 0.1634 | 0.2075 | 0.79 | 0.0328 | 0.206 | 20.3 | 1.411 | — | 0.1455 | 0.2155 | 0.4050 | 0.6050 | 0.787 | 0.829 | 0.753 | 0.641 (0.349 / 0.296) |
| diamonds-diamonds | yes | 0.003847 | 0.003639 | 1.06 | 0.0001 | 0.069 | 888.4 | 1.001 | — | 0.0350 | 0.0110 | 0.5430 | 0.8340 | 0.832 | 0.890 | 0.918 | 0.194 (0.191 / 0.227) |
| earnings-logearn_interaction | yes | 0.01551 | 0.01643 | 0.94 | 0.0002 | 0.014 | 177.2 | 1.001 | — | 0.0040 | 0.0125 | 0.4375 | 0.8175 | 0.880 | 0.935 | 0.912 | 0.582 (0.582 / 0.870) |
| mesquite-logmesquite_logvash | yes | 0.07698 | 0.08468 | 0.91 | 0.0016 | 0.043 | 48.4 | 1.008 | — | 0.0075 | 0.0210 | 0.4470 | 0.7930 | 0.876 | 0.926 | 0.902 | 3.652 (3.601 / 3.983) |
| kidiq-kidscore_momhsiq | yes | 0.1058 | 0.1043 | 1.01 | 0.0010 | 0.017 | 32.9 | 1.005 | — | 0.0075 | 0.0045 | 0.4655 | 0.7950 | 0.872 | 0.925 | 0.927 | 3.731 (3.731 / 4.043) |
| sblrc-blr | yes | 0.1062 | 0.1075 | 0.99 | 0.0022 | 0.020 | 14.1 | 1.012 | — | 0.0060 | 0.0030 | 0.6235 | 0.9585 | 0.844 | 0.910 | 0.910 | 4.817 (5.748 / 6.593) |
| nes2000-nes | yes | 0.08281 | 0.07983 | 1.04 | 0.0000 | 0.035 | 49.4 | 1.008 | — | 0.0090 | 0.0055 | 0.4585 | 0.8005 | 0.869 | 0.923 | 0.930 | 4.239 (4.239 / 4.973) |
| arK-arK | yes | 0.1137 | 0.1205 | 0.94 | 0.0013 | 0.028 | 33.2 | 1.007 | — | 0.0070 | 0.0100 | 0.4095 | 0.7665 | 0.883 | 0.932 | 0.923 | 8.649 (8.739 / 10.794) |
| arma-arma11 | yes | 0.7031 | 0.6911 | 1.02 | 0.0022 | 0.008 | 5.3 | 1.013 | — | 0.0040 | 0.0040 | 0.5940 | 0.9595 | 0.860 | 0.918 | 0.925 | 32.398 (14.273 / 0.201) |
| garch-garch11 | yes | 0.3113 | 0.3194 | 0.97 | 0.0051 | 0.051 | 10.9 | 1.034 | — | 0.0150 | 0.0205 | 0.4100 | 0.7655 | 0.879 | 0.927 | 0.918 | 19.202 (19.202 / 22.321) |
| gp_pois_regr-gp_pois_regr | yes | 0.02944 | 0.02623 | 1.12 | 0.0019 | 0.202 | 125.6 | 1.012 | — | 0.0420 | 0.0205 | 0.5210 | 0.8255 | 0.836 | 0.893 | 0.921 | 0.751 (0.751 / 0.995) |
| hmm_example-hmm_example | yes | 0.2991 | 0.3442 | 0.87 | 0.0010 | 0.008 | 11.9 | 1.006 | — | 0.0050 | 0.0270 | 0.3925 | 0.7705 | 0.888 | 0.937 | 0.903 | 15.506 (15.506 / 21.238) |
| bball_drive_event_0-hmm_drive_0 | yes | 0.647 | 0.5827 | 1.11 | 0.0031 | 0.015 | 6.2 | 1.019 | — | 0.0095 | 0.0030 | 0.5920 | 0.9680 | 0.847 | 0.910 | 0.933 | 37.607 (37.607 / 39.881) |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | yes | 0.3276 | 0.3949 | 0.83 | 0.0108 | 0.062 | 9.5 | 1.061 | — | 0.0255 | 0.0365 | 0.2800 | 0.6170 | 0.898 | 0.934 | 0.910 | 16.163 (10.131 / 10.716) |
| hudson_lynx_hare-lotka_volterra | yes | 0.1123 | 0.1045 | 1.07 | 0.0023 | 0.049 | 32.5 | 1.013 | — | 0.0090 | 0.0040 | 0.4740 | 0.8405 | 0.867 | 0.922 | 0.935 | 3.529 (3.136 / 3.561) |
| mcycle_gp-accel_gp | yes | 0.007901 | 0.006399 | 1.23 | 0.0025 | 0.539 | 426.3 | 1.013 | — | 0.0585 | 0.0195 | 0.4200 | 0.7045 | 0.840 | 0.895 | 0.944 | 0.118 (0.118 / 0.251) |

Geomean h ratio 1.000 (range 0.79–1.23); median refined fraction 0.0022 (range 0.0000–0.0328); v5 cells reproduced bit-for-bit (same gradients and min ESS): 17 of 17.

## Trace: what refinement would cost at a larger step (arm `da`, seed 87101; level-0 leaf statistic from posterior draws with fresh momenta)

| model | step | P(\|dH\|>0.5) L0 | P(\|dH\|>1) L0 | P(\|dH\|>2) L0 | P(\|dH\|>1) L1 | P(\|dH\|>1) L2 | q50 \|dH\| | q90 | q99 | E exp(-\|dH\|) | Stan acc | nonfinite |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 0.5h = 0.2522 | 0.0010 | 0.0005 | 0.0000 | 0.0000 | 0.0000 | 0.0103 | 0.0451 | 0.242 | 0.981 | 0.990 | 0 |
| eight_schools-eight_schools_noncentered | h = 0.5044 | 0.0600 | 0.0245 | 0.0135 | 0.0000 | 0.0000 | 0.0843 | 0.351 | 2.08 | 0.878 | 0.925 | 0 |
| eight_schools-eight_schools_noncentered | h_stan = 0.4167 | 0.0340 | 0.0150 | 0.0055 | 0.0000 | 0.0000 | 0.049 | 0.215 | 1.33 | 0.914 | 0.950 | 0 |
| eight_schools-eight_schools_noncentered | 1.5h = 0.7567 | 0.2965 | 0.1500 | 0.0900 | 0.0105 | 0.0000 | 0.301 | 1.67 | 46.8 | 0.684 | 0.770 | 0 |
| eight_schools-eight_schools_noncentered | 2h = 1.009 | 0.5865 | 0.3870 | 0.2265 | 0.0455 | 0.0005 | 0.843 | 8.95 | 1.21e+03 | 0.477 | 0.571 | 0 |
| eight_schools-eight_schools_noncentered | 3h = 1.513 | 0.9285 | 0.8495 | 0.7260 | 0.2535 | 0.0135 | 6.47 | 1.79e+03 | 6.58e+06 | 0.136 | 0.174 | 0 |
| eight_schools-eight_schools_centered | 0.5h = 0.08168 | 0.0675 | 0.0510 | 0.0395 | 0.0200 | 0.0070 | 0.00944 | 0.245 | 11.3 | 0.917 | 0.938 | 0 |
| eight_schools-eight_schools_centered | h = 0.1634 | 0.1980 | 0.1455 | 0.1140 | 0.0525 | 0.0195 | 0.0745 | 3.49 | 1.06e+03 | 0.787 | 0.829 | 0 |
| eight_schools-eight_schools_centered | h_stan = 0.2075 | 0.2700 | 0.2155 | 0.1740 | 0.0835 | 0.0305 | 0.122 | 24.9 | 2.44e+05 | 0.704 | 0.753 | 0 |
| eight_schools-eight_schools_centered | 1.5h = 0.245 | 0.3570 | 0.2720 | 0.2145 | 0.0955 | 0.0345 | 0.305 | 50.9 | 2.15e+04 | 0.645 | 0.694 | 0 |
| eight_schools-eight_schools_centered | 2h = 0.3267 | 0.4930 | 0.4050 | 0.3360 | 0.1520 | 0.0545 | 0.922 | 393 | 2.57e+05 | 0.519 | 0.571 | 0 |
| eight_schools-eight_schools_centered | 3h = 0.4901 | 0.6690 | 0.6050 | 0.5465 | 0.3020 | 0.1045 | 9.48 | 1.4e+04 | 1.42e+07 | 0.340 | 0.381 | 0 |
| diamonds-diamonds | 0.5h = 0.001923 | 0.0005 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0131 | 0.0572 | 0.125 | 0.974 | 0.986 | 0 |
| diamonds-diamonds | h = 0.003847 | 0.1130 | 0.0350 | 0.0090 | 0.0000 | 0.0000 | 0.109 | 0.453 | 1.01 | 0.832 | 0.890 | 0 |
| diamonds-diamonds | h_stan = 0.003639 | 0.0695 | 0.0110 | 0.0005 | 0.0000 | 0.0000 | 0.0926 | 0.402 | 1 | 0.865 | 0.918 | 0 |
| diamonds-diamonds | 1.5h = 0.00577 | 0.4425 | 0.2725 | 0.1445 | 0.0045 | 0.0000 | 0.374 | 1.98 | 4.66 | 0.594 | 0.679 | 0 |
| diamonds-diamonds | 2h = 0.007694 | 0.6825 | 0.5430 | 0.4010 | 0.0065 | 0.0000 | 1.22 | 8.79 | 20.2 | 0.376 | 0.447 | 0 |
| diamonds-diamonds | 3h = 0.01154 | 0.8845 | 0.8340 | 0.7540 | 0.2260 | 0.0030 | 14.5 | 80.5 | 198 | 0.145 | 0.175 | 0 |
| earnings-logearn_interaction | 0.5h = 0.007757 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00987 | 0.0432 | 0.0974 | 0.983 | 0.992 | 0 |
| earnings-logearn_interaction | h = 0.01551 | 0.0445 | 0.0040 | 0.0000 | 0.0000 | 0.0000 | 0.0827 | 0.333 | 0.768 | 0.880 | 0.935 | 0 |
| earnings-logearn_interaction | h_stan = 0.01643 | 0.0915 | 0.0125 | 0.0005 | 0.0000 | 0.0000 | 0.101 | 0.43 | 0.94 | 0.846 | 0.912 | 0 |
| earnings-logearn_interaction | 1.5h = 0.02327 | 0.3370 | 0.1535 | 0.0405 | 0.0000 | 0.0000 | 0.283 | 1.25 | 2.52 | 0.685 | 0.785 | 0 |
| earnings-logearn_interaction | 2h = 0.03103 | 0.5975 | 0.4375 | 0.2770 | 0.0040 | 0.0000 | 0.828 | 4.33 | 11 | 0.458 | 0.554 | 0 |
| earnings-logearn_interaction | 3h = 0.04654 | 0.8845 | 0.8175 | 0.7175 | 0.0010 | 0.0000 | 7.87 | 45.7 | 106 | 0.156 | 0.197 | 0 |
| mesquite-logmesquite_logvash | 0.5h = 0.03849 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0108 | 0.0432 | 0.0966 | 0.982 | 0.991 | 0 |
| mesquite-logmesquite_logvash | h = 0.07698 | 0.0585 | 0.0075 | 0.0010 | 0.0000 | 0.0000 | 0.0823 | 0.346 | 0.817 | 0.876 | 0.926 | 0 |
| mesquite-logmesquite_logvash | h_stan = 0.08468 | 0.1035 | 0.0210 | 0.0020 | 0.0000 | 0.0000 | 0.0999 | 0.472 | 1.2 | 0.842 | 0.902 | 0 |
| mesquite-logmesquite_logvash | 1.5h = 0.1155 | 0.3435 | 0.1770 | 0.0680 | 0.0020 | 0.0000 | 0.3 | 1.54 | 4.51 | 0.676 | 0.762 | 0 |
| mesquite-logmesquite_logvash | 2h = 0.154 | 0.6120 | 0.4470 | 0.2945 | 0.0070 | 0.0000 | 0.901 | 5.96 | 18.3 | 0.452 | 0.538 | 0 |
| mesquite-logmesquite_logvash | 3h = 0.2309 | 0.8685 | 0.7930 | 0.7125 | 0.0740 | 0.0000 | 7.87 | 62.1 | 182 | 0.172 | 0.213 | 0 |
| kidiq-kidscore_momhsiq | 0.5h = 0.0529 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0111 | 0.0453 | 0.0954 | 0.982 | 0.991 | 0 |
| kidiq-kidscore_momhsiq | h = 0.1058 | 0.0590 | 0.0075 | 0.0005 | 0.0000 | 0.0000 | 0.0939 | 0.375 | 0.85 | 0.872 | 0.925 | 0 |
| kidiq-kidscore_momhsiq | h_stan = 0.1043 | 0.0495 | 0.0045 | 0.0000 | 0.0000 | 0.0000 | 0.0881 | 0.359 | 0.809 | 0.875 | 0.927 | 0 |
| kidiq-kidscore_momhsiq | 1.5h = 0.1587 | 0.3610 | 0.1740 | 0.0645 | 0.0010 | 0.0000 | 0.338 | 1.39 | 4.01 | 0.668 | 0.758 | 0 |
| kidiq-kidscore_momhsiq | 2h = 0.2116 | 0.6140 | 0.4655 | 0.3170 | 0.0055 | 0.0000 | 0.926 | 5.68 | 13.5 | 0.444 | 0.525 | 0 |
| kidiq-kidscore_momhsiq | 3h = 0.3174 | 0.8610 | 0.7950 | 0.7250 | 0.0420 | 0.0000 | 9.98 | 57 | 130 | 0.171 | 0.209 | 0 |
| sblrc-blr | 0.5h = 0.05311 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.015 | 0.0487 | 0.087 | 0.978 | 0.989 | 0 |
| sblrc-blr | h = 0.1062 | 0.0635 | 0.0060 | 0.0000 | 0.0000 | 0.0000 | 0.124 | 0.398 | 0.73 | 0.844 | 0.910 | 0 |
| sblrc-blr | h_stan = 0.1075 | 0.0660 | 0.0030 | 0.0000 | 0.0000 | 0.0000 | 0.131 | 0.419 | 0.769 | 0.843 | 0.910 | 0 |
| sblrc-blr | 1.5h = 0.1593 | 0.4780 | 0.2210 | 0.0625 | 0.0010 | 0.0000 | 0.452 | 1.49 | 3.29 | 0.596 | 0.712 | 0 |
| sblrc-blr | 2h = 0.2124 | 0.7955 | 0.6235 | 0.3935 | 0.0160 | 0.0000 | 1.4 | 4.8 | 11.3 | 0.315 | 0.413 | 0 |
| sblrc-blr | 3h = 0.3187 | 0.9785 | 0.9585 | 0.9185 | 0.0560 | 0.0000 | 14.6 | 46.3 | 95.3 | 0.040 | 0.055 | 0 |
| nes2000-nes | 0.5h = 0.04141 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0108 | 0.0491 | 0.0992 | 0.981 | 0.991 | 0 |
| nes2000-nes | h = 0.08281 | 0.0670 | 0.0090 | 0.0005 | 0.0000 | 0.0000 | 0.0872 | 0.383 | 0.921 | 0.869 | 0.923 | 0 |
| nes2000-nes | h_stan = 0.07983 | 0.0510 | 0.0055 | 0.0000 | 0.0000 | 0.0000 | 0.0767 | 0.366 | 0.838 | 0.878 | 0.930 | 0 |
| nes2000-nes | 1.5h = 0.1242 | 0.3675 | 0.2005 | 0.0700 | 0.0010 | 0.0000 | 0.355 | 1.61 | 4.37 | 0.659 | 0.754 | 0 |
| nes2000-nes | 2h = 0.1656 | 0.6150 | 0.4585 | 0.3095 | 0.0080 | 0.0000 | 0.934 | 6.16 | 17.4 | 0.445 | 0.524 | 0 |
| nes2000-nes | 3h = 0.2484 | 0.8660 | 0.8005 | 0.7130 | 0.0585 | 0.0000 | 10.8 | 64.6 | 158 | 0.170 | 0.208 | 0 |
| arK-arK | 0.5h = 0.05686 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00909 | 0.0413 | 0.101 | 0.984 | 0.992 | 0 |
| arK-arK | h = 0.1137 | 0.0495 | 0.0070 | 0.0000 | 0.0000 | 0.0000 | 0.0742 | 0.345 | 0.764 | 0.883 | 0.932 | 0 |
| arK-arK | h_stan = 0.1205 | 0.0620 | 0.0100 | 0.0000 | 0.0000 | 0.0000 | 0.0832 | 0.367 | 0.988 | 0.870 | 0.923 | 0 |
| arK-arK | 1.5h = 0.1706 | 0.3105 | 0.1490 | 0.0535 | 0.0000 | 0.0000 | 0.265 | 1.43 | 3.4 | 0.695 | 0.784 | 0 |
| arK-arK | 2h = 0.2274 | 0.5675 | 0.4095 | 0.2555 | 0.0025 | 0.0000 | 0.734 | 5.01 | 11.3 | 0.485 | 0.566 | 0 |
| arK-arK | 3h = 0.3412 | 0.8350 | 0.7665 | 0.6785 | 0.0280 | 0.0000 | 6.51 | 46 | 127 | 0.198 | 0.240 | 0 |
| arma-arma11 | 0.5h = 0.3515 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0141 | 0.0422 | 0.107 | 0.980 | 0.990 | 0 |
| arma-arma11 | h = 0.7031 | 0.0495 | 0.0040 | 0.0010 | 0.0000 | 0.0000 | 0.113 | 0.364 | 0.746 | 0.860 | 0.918 | 0 |
| arma-arma11 | h_stan = 0.6911 | 0.0355 | 0.0040 | 0.0000 | 0.0000 | 0.0000 | 0.104 | 0.342 | 0.718 | 0.870 | 0.925 | 0 |
| arma-arma11 | 1.5h = 1.055 | 0.4380 | 0.1755 | 0.0455 | 0.0005 | 0.0000 | 0.424 | 1.35 | 3.01 | 0.621 | 0.727 | 0 |
| arma-arma11 | 2h = 1.406 | 0.7740 | 0.5940 | 0.3640 | 0.0080 | 0.0000 | 1.3 | 4.92 | 12.8 | 0.333 | 0.430 | 0 |
| arma-arma11 | 3h = 2.109 | 0.9785 | 0.9595 | 0.9200 | 0.0830 | 0.0000 | 12.8 | 65 | 246 | 0.040 | 0.057 | 0 |
| garch-garch11 | 0.5h = 0.1556 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00776 | 0.0435 | 0.133 | 0.982 | 0.991 | 0 |
| garch-garch11 | h = 0.3113 | 0.0665 | 0.0150 | 0.0035 | 0.0000 | 0.0000 | 0.0621 | 0.354 | 1.1 | 0.879 | 0.927 | 0 |
| garch-garch11 | h_stan = 0.3194 | 0.0830 | 0.0205 | 0.0030 | 0.0000 | 0.0000 | 0.0781 | 0.431 | 1.34 | 0.865 | 0.918 | 0 |
| garch-garch11 | 1.5h = 0.4669 | 0.3095 | 0.1635 | 0.0690 | 0.0005 | 0.0000 | 0.218 | 1.28 | 7.06 | 0.692 | 0.773 | 0 |
| garch-garch11 | 2h = 0.6225 | 0.5685 | 0.4100 | 0.2605 | 0.0070 | 0.0000 | 0.632 | 4.75 | 23.7 | 0.485 | 0.574 | 0 |
| garch-garch11 | 3h = 0.9338 | 0.8405 | 0.7655 | 0.6605 | 0.1460 | 0.0010 | 4.59 | 41.3 | 165 | 0.200 | 0.255 | 0 |
| gp_pois_regr-gp_pois_regr | 0.5h = 0.01472 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0108 | 0.0637 | 0.179 | 0.975 | 0.987 | 0 |
| gp_pois_regr-gp_pois_regr | h = 0.02944 | 0.1170 | 0.0420 | 0.0110 | 0.0000 | 0.0000 | 0.0905 | 0.568 | 1.85 | 0.836 | 0.893 | 0 |
| gp_pois_regr-gp_pois_regr | h_stan = 0.02623 | 0.0715 | 0.0205 | 0.0030 | 0.0000 | 0.0000 | 0.0716 | 0.387 | 1.19 | 0.872 | 0.921 | 0 |
| gp_pois_regr-gp_pois_regr | 1.5h = 0.04416 | 0.4180 | 0.2585 | 0.1300 | 0.0005 | 0.0000 | 0.35 | 2.64 | 12.7 | 0.607 | 0.693 | 0 |
| gp_pois_regr-gp_pois_regr | 2h = 0.05888 | 0.6690 | 0.5210 | 0.3785 | 0.0190 | 0.0000 | 1.1 | 11.5 | 78.1 | 0.393 | 0.467 | 0 |
| gp_pois_regr-gp_pois_regr | 3h = 0.08832 | 0.8930 | 0.8255 | 0.7600 | 0.2150 | 0.0015 | 10.4 | 123 | 1.6e+03 | 0.141 | 0.175 | 0 |
| hmm_example-hmm_example | 0.5h = 0.1495 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00857 | 0.0397 | 0.078 | 0.984 | 0.992 | 0 |
| hmm_example-hmm_example | h = 0.2991 | 0.0395 | 0.0050 | 0.0000 | 0.0000 | 0.0000 | 0.0753 | 0.328 | 0.674 | 0.888 | 0.937 | 0 |
| hmm_example-hmm_example | h_stan = 0.3442 | 0.1070 | 0.0270 | 0.0025 | 0.0000 | 0.0000 | 0.114 | 0.494 | 1.28 | 0.837 | 0.903 | 0 |
| hmm_example-hmm_example | 1.5h = 0.4486 | 0.2970 | 0.1370 | 0.0355 | 0.0005 | 0.0000 | 0.246 | 1.31 | 3.26 | 0.706 | 0.799 | 0 |
| hmm_example-hmm_example | 2h = 0.5981 | 0.5655 | 0.3925 | 0.2360 | 0.0090 | 0.0000 | 0.64 | 4.22 | 11.3 | 0.493 | 0.582 | 0 |
| hmm_example-hmm_example | 3h = 0.8972 | 0.8555 | 0.7705 | 0.6780 | 0.0080 | 0.0000 | 5.4 | 38.9 | 96.1 | 0.187 | 0.231 | 0 |
| bball_drive_event_0-hmm_drive_0 | 0.5h = 0.3235 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0162 | 0.0511 | 0.119 | 0.978 | 0.988 | 0 |
| bball_drive_event_0-hmm_drive_0 | h = 0.647 | 0.0670 | 0.0095 | 0.0015 | 0.0000 | 0.0000 | 0.135 | 0.419 | 0.939 | 0.847 | 0.910 | 0 |
| bball_drive_event_0-hmm_drive_0 | h_stan = 0.5827 | 0.0285 | 0.0030 | 0.0000 | 0.0000 | 0.0000 | 0.0948 | 0.302 | 0.657 | 0.882 | 0.933 | 0 |
| bball_drive_event_0-hmm_drive_0 | 1.5h = 0.9705 | 0.4515 | 0.2000 | 0.0585 | 0.0010 | 0.0000 | 0.464 | 1.55 | 3.95 | 0.607 | 0.718 | 0 |
| bball_drive_event_0-hmm_drive_0 | 2h = 1.294 | 0.7690 | 0.5920 | 0.3555 | 0.0055 | 0.0000 | 1.4 | 5.04 | 16.1 | 0.338 | 0.433 | 0 |
| bball_drive_event_0-hmm_drive_0 | 3h = 1.941 | 0.9850 | 0.9680 | 0.9330 | 0.1585 | 0.0005 | 13.8 | 55.5 | 320 | 0.034 | 0.051 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.5h = 0.1638 | 0.0030 | 0.0015 | 0.0005 | 0.0000 | 0.0000 | 0.00427 | 0.0325 | 0.155 | 0.983 | 0.990 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | h = 0.3276 | 0.0635 | 0.0255 | 0.0130 | 0.0005 | 0.0000 | 0.0368 | 0.254 | 1.47 | 0.898 | 0.934 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | h_stan = 0.3949 | 0.0855 | 0.0365 | 0.0175 | 0.0005 | 0.0000 | 0.0639 | 0.436 | 3.39 | 0.865 | 0.910 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1.5h = 0.4914 | 0.2195 | 0.1225 | 0.0655 | 0.0055 | 0.0000 | 0.121 | 1.06 | 8.28 | 0.753 | 0.821 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 2h = 0.6552 | 0.4235 | 0.2800 | 0.1840 | 0.0270 | 0.0015 | 0.312 | 3.27 | 36.6 | 0.585 | 0.668 | 0 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 3h = 0.9828 | 0.7455 | 0.6170 | 0.4665 | 0.1310 | 0.0085 | 1.42 | 26.2 | 499 | 0.315 | 0.385 | 0 |
| hudson_lynx_hare-lotka_volterra | 0.5h = 0.05615 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0117 | 0.0483 | 0.106 | 0.981 | 0.990 | 0 |
| hudson_lynx_hare-lotka_volterra | h = 0.1123 | 0.0550 | 0.0090 | 0.0005 | 0.0000 | 0.0000 | 0.0988 | 0.382 | 0.81 | 0.867 | 0.922 | 0 |
| hudson_lynx_hare-lotka_volterra | h_stan = 0.1045 | 0.0320 | 0.0040 | 0.0005 | 0.0000 | 0.0000 | 0.0797 | 0.311 | 0.744 | 0.886 | 0.935 | 0 |
| hudson_lynx_hare-lotka_volterra | 1.5h = 0.1685 | 0.3870 | 0.1815 | 0.0655 | 0.0015 | 0.0000 | 0.326 | 1.55 | 3.52 | 0.653 | 0.751 | 0 |
| hudson_lynx_hare-lotka_volterra | 2h = 0.2246 | 0.6440 | 0.4740 | 0.3015 | 0.0065 | 0.0000 | 0.919 | 5.6 | 16.8 | 0.424 | 0.518 | 0 |
| hudson_lynx_hare-lotka_volterra | 3h = 0.3369 | 0.9130 | 0.8405 | 0.7480 | 0.0615 | 0.0000 | 8.49 | 55.5 | 157 | 0.135 | 0.170 | 0 |
| mcycle_gp-accel_gp | 0.5h = 0.00395 | 0.0060 | 0.0005 | 0.0000 | 0.0000 | 0.0000 | 0.00951 | 0.0722 | 0.293 | 0.974 | 0.986 | 0 |
| mcycle_gp-accel_gp | h = 0.007901 | 0.1260 | 0.0585 | 0.0295 | 0.0000 | 0.0000 | 0.0798 | 0.693 | 4.03 | 0.840 | 0.895 | 0 |
| mcycle_gp-accel_gp | h_stan = 0.006399 | 0.0540 | 0.0195 | 0.0055 | 0.0000 | 0.0000 | 0.0376 | 0.321 | 1.22 | 0.905 | 0.944 | 0 |
| mcycle_gp-accel_gp | 1.5h = 0.01185 | 0.3445 | 0.2270 | 0.1400 | 0.0095 | 0.0000 | 0.291 | 3.63 | 43.4 | 0.657 | 0.731 | 0 |
| mcycle_gp-accel_gp | 2h = 0.0158 | 0.5515 | 0.4200 | 0.3215 | 0.0420 | 0.0005 | 0.819 | 16.6 | 242 | 0.477 | 0.548 | 0 |
| mcycle_gp-accel_gp | 3h = 0.0237 | 0.7960 | 0.7045 | 0.6160 | 0.2120 | 0.0100 | 7.59 | 174 | 3.06e+03 | 0.240 | 0.286 | 0 |

## Arms against `da` (min bulk ESS per gradient; seed medians; ratio arm / da)

| arm | cells passed | geomean vs da (17) | geomean vs da (healthy 14) | min ratio (model) | models < 0.85 | vs CmdStan v5 (healthy) | vs CmdStan v5 (17) | h vs CmdStan | h vs da | grads vs da | refined | rc stop | wall/grad vs CmdStan |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| da | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| da06 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| da06-d05 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| paper08 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| paper06 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| stanacc | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| da06-d2 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |
| stanacc-d2 | 0/0 | — | — | — (None) | none | — | — | — | — | — | — | — | — |

## Per model (ratio arm / da of seed-median min bulk ESS per gradient; gates arm/da; h ratio vs CmdStan; refined fraction)

| model | da | da06 | da06-d05 | paper08 | paper06 | stanacc | da06-d2 | stanacc-d2 |
|---|---|---|---|---|---|---|---|---|
| eight_schools-eight_schools_noncentered | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| eight_schools-eight_schools_centered | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| diamonds-diamonds | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| earnings-logearn_interaction | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| mesquite-logmesquite_logvash | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| kidiq-kidscore_momhsiq | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| sblrc-blr | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| nes2000-nes | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| arK-arK | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| arma-arma11 | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| garch-garch11 | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| gp_pois_regr-gp_pois_regr | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| hmm_example-hmm_example | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| bball_drive_event_0-hmm_drive_0 | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| hudson_lynx_hare-lotka_volterra | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |
| mcycle_gp-accel_gp | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) | — (0/3; h —; r —) |

## Per model absolute (seed medians): ESS/grad x1e3, min bulk ESS, gradients, final steps per seed, final delta per seed

### da

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### da06

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### da06-d05

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### paper08

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### paper06

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### stanacc

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### da06-d2

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

### stanacc-d2

| model | gates | ESS/grad x1e3 | min bulk ESS | grads | leaves/orbit | grads/leaf | acc stat | final h per chain (seed 1 / 2 / 3) | final delta (seed 1 / 2 / 3) | depth caps | div | max R-hat | max abs z |
|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|
| eight_schools-eight_schools_noncentered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| eight_schools-eight_schools_centered | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| diamonds-diamonds | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| earnings-logearn_interaction | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mesquite-logmesquite_logvash | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| kidiq-kidscore_momhsiq | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| sblrc-blr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| nes2000-nes | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arK-arK | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| arma-arma11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| garch-garch11 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| gp_pois_regr-gp_pois_regr | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hmm_example-hmm_example | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| bball_drive_event_0-hmm_drive_0 | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| hudson_lynx_hare-lotka_volterra | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |
| mcycle_gp-accel_gp | 0/0 | — | — | — | — | — | — |  |  |  |  | — | — |

## Funnel tail mass P(omega < -5) at the sampler defaults (exact 0.0478), 4 x 2,000 / 20,000 per seed

| arm | seed | estimate | MCSE z (gate) | batch-means z | omega bulk ESS / R-hat | omega ESS/call x1e3 | target calls | divergences | retained exhaustions | final h | final delta |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---|

## Eight Schools strict track (v9 settings: h 0.3, depth 8, eight levels, 4 x 1,000/1,000, threads 1, `walnutpie` facade; the arm's rule replaces `WarmupConfig::new(0.95)` and `delta = 1` where it changes them)

| arm | calls per seed | min bulk ESS | max R-hat | div / exhaust | geomean min bulk ESS/call | ratio to da | all healthy | final h (seed 1) | final delta (seed 1) |
|---|---|---|---|---|---:|---:|---|---|---|

## Decision rule (flip the sampler default to an arm with geomean >= 1.15x da over 17 models, no model < 0.85x, gates >= da, funnel |z| <= 2 on every seed, Eight Schools >= 0.9x)

| arm | C1 geomean >= 1.15 | C2 min >= 0.85 | C3 gates >= da | C4 funnel | C5 Eight Schools >= 0.9 | all held |
|---|---|---|---|---|---|---|
| da06 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| da06-d05 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| paper08 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| paper06 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| stanacc | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| da06-d2 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |
| stanacc-d2 | — (None) | — None (None) | 0 vs 0 (None) |  (None) | — (None) | **False** |

Arms meeting the rule: none.
