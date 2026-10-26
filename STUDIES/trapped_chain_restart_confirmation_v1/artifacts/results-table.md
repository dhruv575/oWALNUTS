# WP69 results (261/261 cells)

**Verdict:** DO NOT PROPOSE the default

| clause | holds |
|---|---|
| a | False |
| b | False |
| c | True |
| d | True |
| fingerprint | True |

## Arm A (lotka, 60 fresh seeds x 4 chains)

Trapped chains: defaults 0/240, restart 0/240; detector TP 0 FN 0 FP 2 TN 238 (not reached 0); min healthy ratio 0.023838470358960535; passes 55 vs 55 of 60; gradients 17355798 vs 17219262; wall 422.3 vs 413.6 s (pinned, co-tenanted); restarts 2, re-trapped 0

| seed | trapped d | flags d | restarted | trapped r | R-hat d | R-hat r | passed d/r | grads d | grads r | wall d | wall r | fingerprint |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6901007 | [] | [] | [] | [] | 1.037 | 1.037 | False/False | 280809 | 280809 | 6.4 | 6.6 | True |
| 6901017 | [] | [] | [] | [] | 1.010 | 1.010 | False/False | 276270 | 276270 | 5.7 | 5.9 | True |
| 6901025 | [] | [0] | [0] | [] | 1.008 | 1.008 | True/True | 371842 | 310062 | 14.6 | 8.9 | True |
| 6901026 | [] | [] | [] | [] | 1.010 | 1.010 | False/False | 289416 | 289416 | 6.2 | 6.5 | True |
| 6901032 | [] | [] | [] | [] | 1.020 | 1.020 | False/False | 272807 | 272807 | 5.9 | 6.0 | True |
| 6901036 | [] | [1] | [1] | [] | 1.005 | 1.006 | True/True | 493733 | 418977 | 37.1 | 25.2 | True |
| 6901056 | [] | [] | [] | [] | 1.063 | 1.063 | False/False | 253386 | 253386 | 5.4 | 5.6 | True |

## Arm B (17 house models x 3 seeds)

Passes 42 vs 42 of 51; flagged chains 1 in 1 cells ['B--earnings__logearn_interaction--defaults--6902001']; false positives (flag on a cell passing at defaults) 1; geomean ESS/gradient ratio 1.0007; median wall ratio on non-firing cells 1.0180

| model | seed | passed d | passed r | R-hat d | R-hat r | min step ratio | restarted | shifted d | fingerprint |
|---|---|---|---|---|---|---|---|---|---|
| eight_schools-eight_schools_noncentered | 6902001 | True | True | 1.0020 | 1.0020 | 0.562 | [] | [] | True |
| eight_schools-eight_schools_noncentered | 6902002 | True | True | 1.0017 | 1.0017 | 0.896 | [] | [] | True |
| eight_schools-eight_schools_noncentered | 6902003 | True | True | 1.0020 | 1.0020 | 0.800 | [] | [] | True |
| eight_schools-eight_schools_centered | 6902001 | False | False | 1.0840 | 1.0840 | 0.744 | [] | [] | True |
| eight_schools-eight_schools_centered | 6902002 | False | False | 1.0137 | 1.0137 | 0.258 | [] | [] | True |
| eight_schools-eight_schools_centered | 6902003 | False | False | 1.0331 | 1.0331 | 0.483 | [] | [] | True |
| diamonds-diamonds | 6902001 | True | True | 1.0025 | 1.0025 | 0.578 | [] | [] | True |
| diamonds-diamonds | 6902002 | True | True | 1.0039 | 1.0039 | 0.740 | [] | [] | True |
| diamonds-diamonds | 6902003 | True | True | 1.0033 | 1.0033 | 0.950 | [] | [] | True |
| earnings-logearn_interaction | 6902001 | True | True | 1.0015 | 1.0018 | 0.031 | [1] | [] | True |
| earnings-logearn_interaction | 6902002 | True | True | 1.0030 | 1.0030 | 0.119 | [] | [] | True |
| earnings-logearn_interaction | 6902003 | True | True | 1.0032 | 1.0032 | 0.140 | [] | [] | True |
| mesquite-logmesquite_logvash | 6902001 | True | True | 1.0019 | 1.0019 | 0.761 | [] | [] | True |
| mesquite-logmesquite_logvash | 6902002 | True | True | 1.0037 | 1.0037 | 0.603 | [] | [] | True |
| mesquite-logmesquite_logvash | 6902003 | True | True | 1.0031 | 1.0031 | 0.464 | [] | [] | True |
| kidiq-kidscore_momhsiq | 6902001 | True | True | 1.0045 | 1.0045 | 0.972 | [] | [] | True |
| kidiq-kidscore_momhsiq | 6902002 | True | True | 1.0037 | 1.0037 | 0.858 | [] | [] | True |
| kidiq-kidscore_momhsiq | 6902003 | True | True | 1.0033 | 1.0033 | 0.647 | [] | [] | True |
| sblrc-blr | 6902001 | True | True | 1.0046 | 1.0046 | 0.585 | [] | [] | True |
| sblrc-blr | 6902002 | True | True | 1.0076 | 1.0076 | 0.453 | [] | [] | True |
| sblrc-blr | 6902003 | True | True | 1.0039 | 1.0039 | 0.578 | [] | [] | True |
| nes2000-nes | 6902001 | True | True | 1.0015 | 1.0015 | 0.662 | [] | [] | True |
| nes2000-nes | 6902002 | True | True | 1.0038 | 1.0038 | 0.527 | [] | [] | True |
| nes2000-nes | 6902003 | True | True | 1.0014 | 1.0014 | 0.907 | [] | [] | True |
| arK-arK | 6902001 | True | True | 1.0044 | 1.0044 | 0.318 | [] | [] | True |
| arK-arK | 6902002 | True | True | 1.0025 | 1.0025 | 0.935 | [] | [] | True |
| arK-arK | 6902003 | True | True | 1.0013 | 1.0013 | 0.898 | [] | [] | True |
| arma-arma11 | 6902001 | True | True | 1.0010 | 1.0010 | 0.852 | [] | [] | True |
| arma-arma11 | 6902002 | True | True | 1.0007 | 1.0007 | 0.433 | [] | [] | True |
| arma-arma11 | 6902003 | True | True | 1.0021 | 1.0021 | 0.840 | [] | [] | True |
| garch-garch11 | 6902001 | True | True | 1.0031 | 1.0031 | 0.617 | [] | [] | True |
| garch-garch11 | 6902002 | True | True | 1.0022 | 1.0022 | 0.821 | [] | [] | True |
| garch-garch11 | 6902003 | True | True | 1.0019 | 1.0019 | 0.630 | [] | [] | True |
| gp_pois_regr-gp_pois_regr | 6902001 | True | True | 1.0043 | 1.0043 | 0.927 | [] | [] | True |
| gp_pois_regr-gp_pois_regr | 6902002 | True | True | 1.0072 | 1.0072 | 0.536 | [] | [] | True |
| gp_pois_regr-gp_pois_regr | 6902003 | True | True | 1.0042 | 1.0042 | 0.890 | [] | [] | True |
| hmm_example-hmm_example | 6902001 | True | True | 1.0012 | 1.0012 | 0.767 | [] | [] | True |
| hmm_example-hmm_example | 6902002 | True | True | 1.0030 | 1.0030 | 0.780 | [] | [] | True |
| hmm_example-hmm_example | 6902003 | True | True | 1.0041 | 1.0041 | 0.897 | [] | [] | True |
| bball_drive_event_0-hmm_drive_0 | 6902001 | True | True | 1.0033 | 1.0033 | 0.674 | [] | [] | True |
| bball_drive_event_0-hmm_drive_0 | 6902002 | True | True | 1.0021 | 1.0021 | 0.638 | [] | [] | True |
| bball_drive_event_0-hmm_drive_0 | 6902003 | True | True | 1.0020 | 1.0020 | 0.880 | [] | [] | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6902001 | False | False | 1.0171 | 1.0171 | 0.677 | [] | [] | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6902002 | True | True | 1.0041 | 1.0041 | 0.537 | [] | [] | True |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 6902003 | False | False | 1.0087 | 1.0087 | 0.699 | [] | [] | True |
| hudson_lynx_hare-lotka_volterra | 6902001 | True | True | 1.0028 | 1.0028 | 0.828 | [] | [] | True |
| hudson_lynx_hare-lotka_volterra | 6902002 | True | True | 1.0010 | 1.0010 | 0.893 | [] | [] | True |
| hudson_lynx_hare-lotka_volterra | 6902003 | False | False | 1.1492 | 1.1492 | 0.111 | [] | [2] | True |
| mcycle_gp-accel_gp | 6902001 | False | False | 1.0506 | 1.0506 | 0.947 | [] | [] | True |
| mcycle_gp-accel_gp | 6902002 | False | False | 1.0114 | 1.0114 | 0.143 | [] | [] | True |
| mcycle_gp-accel_gp | 6902003 | False | False | 1.0088 | 1.0088 | 0.951 | [] | [] | True |

Per-model ESS/gradient ratio: eight_schools_noncentered 1.0000, eight_schools_centered 1.0000, diamonds 1.0000, logearn_interaction 1.0128, logmesquite_logvash 1.0000, kidscore_momhsiq 1.0000, blr 1.0000, nes 1.0000, arK 1.0000, arma11 1.0000, garch11 1.0000, gp_pois_regr 1.0000, hmm_example 1.0000, hmm_drive_0 1.0000, one_comp_mm_elim_abs 1.0000, lotka_volterra 1.0000, accel_gp 1.0000

## Arm C (genuine second modes)

Firings 0; second-mode cells 12; chain-disagreement warning non-empty on 6; R-hat > 1.01 on 12

| block | seed | targeted | arm | second-mode chains / mixed | R-hat | warning | min step ratio | restarted |
|---|---|---|---|---|---|---|---|---|
| C | 952202 | True | d | [] | 1.003 | [] | 0.864 | [] |
| C | 952202 | True | r | [] | 1.003 | [] | 0.864 | [] |
| C | 600602 | True | d | [] | 1.001 | [] | 0.736 | [] |
| C | 600602 | True | r | [] | 1.001 | [] | 0.736 | [] |
| C | 600605 | True | d | [] | 1.003 | [] | 0.759 | [] |
| C | 600605 | True | r | [] | 1.003 | [] | 0.759 | [] |
| C | 6903101 | False | d | [] | 1.002 | [] | 0.831 | [] |
| C | 6903101 | False | r | [] | 1.002 | [] | 0.831 | [] |
| C | 6903102 | False | d | [2] | 1.022 | ["last-warmup-window median log density -1962.914 is 62.834 below the chains' median -1900.080 (limit 6.729 = 3 x median IQR)", 'max R-hat 1.022 falls to 1.002 without this chain'] | 0.919 | [] |
| C | 6903102 | False | r | [2] | 1.022 | ["last-warmup-window median log density -1962.914 is 62.834 below the chains' median -1900.080 (limit 6.729 = 3 x median IQR)", 'max R-hat 1.022 falls to 1.002 without this chain'] | 0.919 | [] |
| C | 6903103 | False | d | [] | 1.002 | [] | 0.868 | [] |
| C | 6903103 | False | r | [] | 1.002 | [] | 0.868 | [] |
| M | 6903201 | False | d | mixed=True end_minor=2 | 1.733 | [] | 0.801 | [] |
| M | 6903201 | False | r | mixed=True end_minor=2 | 1.733 | [] | 0.801 | [] |
| M | 6903202 | False | d | mixed=True end_minor=2 | 1.501 | [] | 0.887 | [] |
| M | 6903202 | False | r | mixed=True end_minor=2 | 1.501 | [] | 0.887 | [] |
| M | 6903203 | False | d | mixed=True end_minor=3 | 1.500 | [1] | 0.821 | [] |
| M | 6903203 | False | r | mixed=True end_minor=3 | 1.500 | [1] | 0.821 | [] |
| M | 6903204 | False | d | mixed=True end_minor=1 | 1.528 | [0] | 0.562 | [] |
| M | 6903204 | False | r | mixed=True end_minor=1 | 1.528 | [0] | 0.562 | [] |
| M | 6903205 | False | d | mixed=True end_minor=2 | 1.732 | [] | 0.624 | [] |
| M | 6903205 | False | r | mixed=True end_minor=2 | 1.732 | [] | 0.624 | [] |
| M | 6903206 | False | d | mixed=False end_minor=0 | 1.003 | [] | 0.681 | [] |
| M | 6903206 | False | r | mixed=False end_minor=0 | 1.003 | [] | 0.681 | [] |

## Arm D (sync point, 100-D Gaussian)

| chains | repeat ratios | median | overhead |
|---|---|---|---|
| 1 | 0.9995, 1.0016, 1.0025, 1.0009, 1.0010 | 1.0010 | +0.0010 |
| 4 | 1.0106, 1.0118, 1.0115, 1.0149, 1.0048 | 1.0115 | +0.0115 |
| 16 | 1.0186, 1.0237, 1.0049, 1.0509, 1.0042 | 1.0186 | +0.0186 |

## Predictions

| id | observed | held |
|---|---|---|
| P1 | defaults 0/240, restart 0/240 | False |
| P2 | {'tp': 0, 'fn': 0, 'fp': 2, 'tn': 238, 'fn_not_reached': 0} | False |
| P3 | firing ['B--earnings__logearn_interaction--defaults--6902001']; fp_b 1; passes 42 vs 42; ratio 1.0007 | False |
| P4 | firings 0; second-mode cells 12, warning reports 6, R-hat reports 12 | False |
| P5 | {1: 0.000979660954617323, 4: 0.01148801074398409, 16: 0.01860048092266653} | True |
| P6 | 123/123 pairs; sync identical 15/15 | True |
