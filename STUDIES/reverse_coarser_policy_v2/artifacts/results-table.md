# reverse_coarser_policy_v2 — results

Seed medians over 3 seeds (92101–92103) of the per-cell minimum over reference parameters of bulk ESS per gradient (all target calls, warmup included); `gates` = cells passing rank R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences (of 3 per arm). `stop` = shipped defaults; `beyond-adapt` = `ZeroWeightBeyondAdaptSelected` under the shipped adaptation; `stop-fixed` / `beyond-fixed` = the two policies at the `stop` cell's adapted step (same seed), mass adapted, step fixed. `rc stop` = reverse-coarser stops per retained transition (`stop`); `cont` = continued leaves per retained transition; `zero-w` = zero-weight leaves / built leaves.

## Adapted step: `beyond-adapt` vs `stop` (the decision comparison)

| model | ESS/grad x1e3 stop | beyond-adapt | ratio | ratio (sampling grads) | gates stop/adapt | h adapt/stop | leaves/orbit stop → adapt | rc stop | cont | zero-w | depth cap stop → adapt |
|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered **(target)** | 28.636 | 33.937 | 1.185 | 1.159 | 3/3 | 1.064 | 6.7 → 7.3 | 0.129 | 0.166 | 0.077 | 0.000 → 0.000 |
| eight_schools-eight_schools_centered **(target)** | 0.353 | 0.122 | 0.347 | 0.285 | 0/0 | 0.858 | 12.6 → 20.3 | 0.271 | 0.279 | 0.095 | 0.000 → 0.000 |
| diamonds-diamonds | 0.192 | 0.190 | 0.987 | 1.001 | 3/3 | 1.084 | 963.7 → 965.2 | 0.029 | 0.060 | 0.028 | 0.090 → 0.058 |
| earnings-logearn_interaction | 0.598 | 0.640 | 1.070 | 1.053 | 3/3 | 1.073 | 176.9 → 181.9 | 0.013 | 0.031 | 0.008 | 0.000 → 0.000 |
| mesquite-logmesquite_logvash | 3.501 | 3.402 | 0.972 | 0.977 | 3/3 | 1.005 | 45.8 → 48.3 | 0.068 | 0.086 | 0.036 | 0.000 → 0.000 |
| kidiq-kidscore_momhsiq | 4.317 | 3.564 | 0.826 | 0.968 | 3/3 | 1.014 | 33.7 → 32.8 | 0.014 | 0.034 | 0.011 | 0.000 → 0.000 |
| sblrc-blr | 6.557 | 4.916 | 0.750 | 0.804 | 3/3 | 1.007 | 14.8 → 14.9 | 0.012 | 0.012 | 0.005 | 0.000 → 0.000 |
| nes2000-nes | 4.269 | 3.901 | 0.914 | 0.957 | 3/3 | 1.049 | 50.9 → 49.6 | 0.014 | 0.053 | 0.023 | 0.000 → 0.000 |
| arK-arK | 8.530 | 7.646 | 0.896 | 0.922 | 3/3 | 1.021 | 33.2 → 32.8 | 0.015 | 0.035 | 0.013 | 0.000 → 0.000 |
| arma-arma11 | 13.752 | 13.796 | 1.003 | 1.003 | 3/3 | 1.026 | 5.6 → 5.5 | 0.007 | 0.006 | 0.004 | 0.000 → 0.000 |
| garch-garch11 | 20.100 | 18.558 | 0.923 | 0.911 | 3/3 | 1.071 | 10.6 → 10.4 | 0.088 | 0.092 | 0.039 | 0.000 → 0.000 |
| gp_pois_regr-gp_pois_regr **(target)** | 0.804 | 0.724 | 0.901 | 0.917 | 3/3 | 0.979 | 141.1 → 159.2 | 0.183 | 0.230 | 0.090 | 0.000 → 0.000 |
| hmm_example-hmm_example | 16.458 | 15.901 | 0.966 | 1.076 | 3/3 | 1.026 | 11.6 → 11.5 | 0.012 | 0.009 | 0.003 | 0.000 → 0.000 |
| bball_drive_event_0-hmm_drive_0 | 25.745 | 27.104 | 1.053 | 1.230 | 3/3 | 0.962 | 6.3 → 6.5 | 0.018 | 0.016 | 0.008 | 0.000 → 0.000 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 11.364 | 10.602 | 0.933 | 0.914 | 2/1 | 0.939 | 7.5 → 8.1 | 0.107 | 0.133 | 0.077 | 0.000 → 0.000 |
| hudson_lynx_hare-lotka_volterra | 1.972 | 1.941 | 0.984 | 0.976 | 3/3 | 0.939 | 33.7 → 35.6 | 0.043 | 0.061 | 0.023 | 0.000 → 0.000 |
| mcycle_gp-accel_gp **(target)** | 0.170 | 0.112 | 0.659 | 0.718 | 0/1 | 1.098 | 357.3 → 526.3 | 0.583 | 0.961 | 0.391 | 0.000 → 0.000 |

## Fixed step: `beyond-fixed` vs `stop-fixed` (the mechanism comparison)

| model | fixed step | ESS/grad x1e3 stop-fixed | beyond-fixed | ratio | ratio (sampling grads) | gates fixed stop/beyond | stop-fixed vs stop | leaves/orbit stop-fixed → beyond-fixed | rc stop (fixed) | cont | zero-w | depth cap → |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---|
| eight_schools-eight_schools_noncentered **(target)** | 0.4866 | 31.965 | 38.705 | 1.211 | 1.211 | 3/3 | 1.116 | 6.5 → 7.0 | 0.113 | 0.114 | 0.050 | 0.000 → 0.000 |
| eight_schools-eight_schools_centered **(target)** | 0.2079 | 0.128 | 0.106 | 0.828 | 0.607 | 0/0 | 0.362 | 11.5 → 16.6 | 0.315 | 0.427 | 0.182 | 0.000 → 0.000 |
| diamonds-diamonds | 0.003589 | 0.113 | 0.138 | 1.221 | 1.700 | 1/3 | 0.589 | 977.3 → 992.5 | 0.022 | 0.031 | 0.015 | 0.279 → 0.084 |
| earnings-logearn_interaction | 0.01488 | 0.254 | 0.180 | 0.710 | 0.829 | 3/3 | 0.424 | 187.9 → 195.0 | 0.004 | 0.007 | 0.002 | 0.000 → 0.000 |
| mesquite-logmesquite_logvash | 0.07478 | 3.353 | 3.497 | 1.043 | 1.037 | 3/3 | 0.958 | 48.9 → 50.9 | 0.053 | 0.069 | 0.028 | 0.000 → 0.000 |
| kidiq-kidscore_momhsiq | 0.09641 | 1.278 | 1.789 | 1.400 | 1.091 | 3/3 | 0.296 | 34.4 → 34.9 | 0.010 | 0.011 | 0.002 | 0.000 → 0.000 |
| sblrc-blr | 0.105 | 0.984 | 0.785 | 0.798 | 0.896 | 3/3 | 0.150 | 14.5 → 14.9 | 0.007 | 0.010 | 0.003 | 0.000 → 0.000 |
| nes2000-nes | 0.08042 | 3.906 | 3.843 | 0.984 | 1.046 | 3/3 | 0.915 | 50.9 → 50.8 | 0.014 | 0.022 | 0.009 | 0.000 → 0.000 |
| arK-arK | 0.1137 | 7.294 | 6.979 | 0.957 | 0.996 | 3/3 | 0.855 | 33.2 → 33.5 | 0.013 | 0.018 | 0.007 | 0.000 → 0.000 |
| arma-arma11 | 0.6723 | 0.004 | 0.004 | 0.968 | 0.999 | 1/1 | 0.000 | 0.0 → 0.0 | 0.003 | 0.001 | 0.003 | 0.000 → 0.000 |
| garch-garch11 | 0.3133 | 19.017 | 19.374 | 1.019 | 1.053 | 3/3 | 0.946 | 11.2 → 10.9 | 0.035 | 0.084 | 0.036 | 0.000 → 0.000 |
| gp_pois_regr-gp_pois_regr **(target)** | 0.02856 | 0.738 | 0.699 | 0.947 | 0.890 | 3/3 | 0.919 | 130.1 → 147.4 | 0.186 | 0.266 | 0.116 | 0.000 → 0.000 |
| hmm_example-hmm_example | 0.3089 | 12.331 | 10.264 | 0.832 | 0.960 | 3/3 | 0.749 | 11.5 → 11.6 | 0.014 | 0.015 | 0.005 | 0.000 → 0.000 |
| bball_drive_event_0-hmm_drive_0 | 0.6211 | 20.655 | 7.650 | 0.370 | 0.380 | 2/1 | 0.802 | 6.4 → 5.7 | 0.009 | 0.077 | 0.045 | 0.000 → 0.000 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.4214 | 11.149 | 10.696 | 0.959 | 1.041 | 0/3 | 0.981 | 7.1 → 7.6 | 0.123 | 0.168 | 0.098 | 0.000 → 0.000 |
| hudson_lynx_hare-lotka_volterra | 0.1068 | 0.626 | 0.458 | 0.732 | 0.729 | 1/3 | 0.318 | 24.8 → 28.3 | 0.204 | 0.099 | 0.027 | 0.000 → 0.000 |
| mcycle_gp-accel_gp **(target)** | 0.008144 | 0.162 | 0.116 | 0.716 | 0.712 | 0/1 | 0.953 | 292.1 → 511.3 | 0.520 | 0.741 | 0.321 | 0.000 → 0.000 |

## Decision (protocol.json `decision_rule`; `beyond-adapt` vs `stop`)

| statistic | value |
|---|---:|
| geomean ratio, 17 models | 0.878 |
| geomean ratio, 14 CmdStan-healthy models | 0.949 |
| geomean ratio, 4 target models | 0.703 |
| geomean ratio, 13 control models | 0.940 |
| geomean ratio on sampling gradients only | 0.900 |
| geomean adapted-step ratio adapt/stop (max \|log\|) | 1.011 (0.153) |
| worst model | 0.347 (eight_schools-eight_schools_centered) |
| gates passed (of 51) stop / beyond-adapt | 44 / 44 |
| vs CmdStan (healthy) stop / beyond-adapt | 0.826 / 0.783 |
| C1 geomean >= 1.1 | False |
| C2 no model < 0.9 | False |
| C3 gates >= stop | True |
| C4 funnel \|z\| <= 2 every seed (beyond-adapt) | True |
| C5 targets geomean >= 1.15 | False |
| **flip the default** | **False** |

## Mechanism (`beyond-fixed` vs `stop-fixed`; registered predictions M1, M2)

| statistic | value |
|---|---:|
| geomean fixed ratio, 17 models | 0.890 |
| geomean fixed ratio, 4 target models | 0.908 |
| geomean fixed ratio, 13 controls | 0.885 |
| geomean fixed ratio on sampling gradients | 0.910 |
| worst fixed ratio | 0.370 |
| stop-fixed vs stop (geomean; fixing the step costs nothing if ~1) | 0.397 |
| gates stop-fixed / beyond-fixed | 35 / 42 |
| M1 targets geomean >= 1.15 | False |
| M2 controls within 1.05x | False |
| **truncation hypothesis supported** | **False** |

## Funnel (Neal's 10-D funnel at the sampler defaults, 4 x 2,000/20,000, P(omega < -5) exact 0.0478)

| arm | seed | estimate | MCSE z | batch-means z | omega bulk ESS | ESS/call x1e3 | rc stops | continuations | zero-w leaves / built | depth caps | divergences |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| stop | 92101 | 0.0489 | +0.18 | +0.19 | 574 | 0.112 | 27633 | 0 | 0 / 1078812 | 2 | 6 |
| stop | 92102 | 0.0400 | -0.99 | -1.13 | 445 | 0.101 | 13238 | 0 | 0 / 3317943 | 145 | 0 |
| stop | 92103 | 0.0495 | +0.28 | +0.29 | 549 | 0.123 | 28734 | 0 | 0 / 916980 | 0 | 4 |
| beyond-adapt | 92101 | 0.0457 | -0.28 | -0.33 | 589 | 0.119 | 0 | 23963 | 95158 / 1834728 | 9 | 8 |
| beyond-adapt | 92102 | 0.0563 | +1.25 | +1.31 | 625 | 0.125 | 0 | 25039 | 125475 / 2020855 | 9 | 2 |
| beyond-adapt | 92103 | 0.0485 | +0.10 | +0.11 | 412 | 0.083 | 0 | 25093 | 119312 / 1733564 | 15 | 0 |
