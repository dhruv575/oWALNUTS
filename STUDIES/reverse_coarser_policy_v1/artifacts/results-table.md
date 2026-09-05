# reverse_coarser_policy_v1 — results

Seed medians over 3 seeds (91101–91103) of the per-cell minimum over reference parameters of bulk ESS per gradient (all target calls, warmup included); `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences (of 3); CmdStan from `posteriordb_bench_v5` (seeds 87101–87103). `rc stop` = fraction of retained transitions ending in a reverse-coarser stop (`stop` arm); `cont` = continued leaves per retained transition (`beyond` arm); `zero-w` = zero-weight leaves / built leaves; `depth cap` = fraction of retained transitions ending at the depth cap.

## Per model

| model | ESS/grad x1e3 `stop` | `beyond` | ratio | ratio (sampling grads) | ratio (per s) | gates stop/beyond | h beyond/stop | leaves/orbit stop → beyond | rc stop | cont | zero-w | depth cap stop → beyond | vs CmdStan stop / beyond |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|
| eight_schools-eight_schools_noncentered **(target)** | 31.059 | 40.327 | 1.298 | 1.258 | 1.587 | 3/3 | 1.120 | 6.5 → 6.9 | 0.114 | 0.202 | 0.091 | 0.000 → 0.000 | 0.942 / 1.223 |
| eight_schools-eight_schools_centered **(target)** | 0.276 | 0.204 | 0.740 | 0.690 | 0.808 | 0/0 | 1.171 | 13.5 → 14.5 | 0.262 | 0.410 | 0.170 | 0.000 → 0.000 | 0.933 / 0.690 |
| diamonds-diamonds | 0.169 | 0.171 | 1.014 | 1.133 | 1.032 | 3/3 | 1.242 | 998.2 → 929.4 | 0.007 | 0.178 | 0.077 | 0.151 → 0.032 | 0.742 / 0.752 |
| earnings-logearn_interaction | 0.556 | 0.613 | 1.103 | 1.282 | 1.065 | 3/2 | 1.203 | 179.5 → 151.2 | 0.013 | 0.140 | 0.057 | 0.000 → 0.000 | 0.639 / 0.705 |
| mesquite-logmesquite_logvash | 3.118 | 2.874 | 0.922 | 1.019 | 0.877 | 3/3 | 1.212 | 49.8 → 44.0 | 0.038 | 0.158 | 0.068 | 0.000 → 0.000 | 0.783 / 0.722 |
| kidiq-kidscore_momhsiq | 4.055 | 4.457 | 1.099 | 1.256 | 1.126 | 3/3 | 1.170 | 35.8 → 29.5 | 0.010 | 0.073 | 0.029 | 0.000 → 0.000 | 1.003 / 1.102 |
| sblrc-blr | 5.936 | 4.808 | 0.810 | 1.037 | 0.827 | 3/2 | 1.028 | 15.0 → 14.5 | 0.006 | 0.012 | 0.004 | 0.000 → 0.000 | 0.900 / 0.729 |
| nes2000-nes | 4.395 | 3.488 | 0.794 | 0.853 | 0.802 | 3/3 | 1.237 | 52.0 → 43.9 | 0.013 | 0.147 | 0.062 | 0.000 → 0.000 | 0.884 / 0.701 |
| arK-arK | 9.000 | 8.842 | 0.982 | 0.997 | 0.968 | 3/3 | 1.134 | 30.3 → 29.3 | 0.038 | 0.109 | 0.045 | 0.000 → 0.000 | 0.834 / 0.819 |
| arma-arma11 | 13.287 | 13.884 | 1.045 | 1.139 | 1.033 | 3/3 | 1.075 | 5.6 → 5.2 | 0.008 | 0.017 | 0.008 | 0.000 → 0.000 | 66.225 / 69.202 |
| garch-garch11 | 19.378 | 17.588 | 0.908 | 0.909 | 1.022 | 3/3 | 1.068 | 10.4 → 9.9 | 0.074 | 0.132 | 0.061 | 0.000 → 0.000 | 0.868 / 0.788 |
| gp_pois_regr-gp_pois_regr **(target)** | 0.583 | 0.663 | 1.138 | 1.239 | 1.103 | 2/3 | 1.081 | 139.7 → 128.9 | 0.183 | 0.434 | 0.185 | 0.000 → 0.000 | 0.586 / 0.667 |
| hmm_example-hmm_example | 14.354 | 15.429 | 1.075 | 0.892 | 1.071 | 3/3 | 1.084 | 11.4 → 10.7 | 0.017 | 0.046 | 0.020 | 0.000 → 0.000 | 0.676 / 0.726 |
| bball_drive_event_0-hmm_drive_0 | 44.331 | 47.012 | 1.060 | 0.930 | 1.040 | 3/3 | 1.044 | 6.2 → 6.1 | 0.018 | 0.028 | 0.013 | 0.000 → 0.000 | 1.112 / 1.179 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 11.392 | 12.180 | 1.069 | 0.941 | 1.088 | 1/3 | 0.993 | 6.7 → 7.8 | 0.126 | 0.164 | 0.087 | 0.000 → 0.000 | 1.063 / 1.137 |
| hudson_lynx_hare-lotka_volterra | 1.224 | 1.588 | 1.298 | 1.031 | 1.610 | 2/2 | 1.069 | 29.8 → 30.2 | 0.055 | 0.148 | 0.066 | 0.000 → 0.000 | 0.344 / 0.446 |
| mcycle_gp-accel_gp **(target)** | 0.054 | 0.033 | 0.612 | 0.614 | 0.592 | 0/0 | 1.304 | 321.0 → 506.6 | 0.580 | 1.321 | 0.566 | 0.000 → 0.000 | 0.213 / 0.131 |

## Decision (protocol.json `decision_rule`)

| statistic | value |
|---|---:|
| geomean ratio `beyond`/`stop`, 17 models | 0.981 |
| geomean ratio, 14 CmdStan-healthy models | 1.030 |
| geomean ratio, 4 target models | 0.904 |
| geomean ratio, 13 control models | 1.005 |
| geomean ratio on sampling gradients only | 0.994 |
| geomean ratio per second | 1.011 |
| worst model | 0.612 (mcycle_gp-accel_gp) |
| gates passed (of 51) stop / beyond | 41 / 42 |
| vs CmdStan (healthy) stop / beyond | 0.783 / 0.807 |
| C1 geomean >= 1.1 | False |
| C2 no model < 0.9 | False |
| C3 gates >= stop | True |
| C4 funnel \|z\| <= 2 every seed (beyond) | True |
| C5 targets geomean >= 1.15 | False |
| **flip the default** | **False** |

## Funnel (Neal's 10-D funnel at the sampler defaults, 4 x 2,000/20,000, P(omega < -5) exact 0.0478)

| arm | seed | estimate | MCSE z | batch-means z | omega bulk ESS | ESS/call x1e3 | rc stops | continuations | zero-w leaves / built | depth caps | divergences |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| stop | 91101 | 0.0560 | +0.56 | +0.79 | 335 | 0.038 | 22339 | 0 | 0 / 4982561 | 508 | 15 |
| stop | 91102 | 0.0474 | -0.07 | -0.07 | 685 | 0.192 | 20732 | 0 | 0 / 1969361 | 31 | 2 |
| stop | 91103 | 0.0443 | -0.52 | -0.54 | 454 | 0.111 | 24985 | 0 | 0 / 1182558 | 1 | 3 |
| beyond | 91101 | 0.0583 | +1.25 | +1.36 | 701 | 0.127 | 0 | 28541 | 173581 / 2650301 | 51 | 1 |
| beyond | 91102 | 0.0415 | -0.82 | -0.87 | 564 | 0.106 | 0 | 15905 | 77727 / 3597924 | 143 | 0 |
| beyond | 91103 | 0.0437 | -0.57 | -0.60 | 587 | 0.119 | 0 | 19135 | 94202 / 2750767 | 37 | 0 |
