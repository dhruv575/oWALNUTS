# WP82 results

Seeds [821821, 821822, 821823, 821824, 821825, 821826] (regression [821821, 821822, 821823]); 4 chains x 1,000/1,000; funnel 4 x 2000/20000 x 10 seeds; pinned to cores 4-7, co-tenanted.

Default vs CmdStan on eight_schools-eight_schools_centered (WP72 form): per total gradient 0.269 [0.128, 1.619], per sampling gradient 0.187; non-centred twin 0.867 / 0.875.

## 1. Telemetry (pooled over seeds)

| model | arm | step (median) | refined fraction | refined gradient share | grads / refined tr. | grads / unrefined tr. | sampling grads / tr. | terminal acceptance | refined starting in Q1 | Q1/Q4 refined | Q1/Q4 grads per tr. |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_centered | owalnuts | 0.1570 | 0.253 | 0.719 | 103.6 | 21.9 | 64.7 | 0.797 | 0.708 | 17.92 | 5.56 |
| eight_schools-eight_schools_centered | cmdstan | 0.1494 | — | — | — | — | 21.1 | 0.773 (retained 0.833) | — | — | 0.35 |
| eight_schools-eight_schools_centered | owalnuts-costda | 0.1364 | 0.216 | 0.639 | 113.5 | 24.3 | 47.6 | 0.799 | 0.746 | 26.15 | 3.81 |
| eight_schools-eight_schools_centered | owalnuts-stanacc | 0.1825 | 0.241 | 0.514 | 70.1 | 20.0 | 38.0 | 0.799 | 0.661 | 12.28 | 2.36 |
| eight_schools-eight_schools_centered | owalnuts-levels2 | 0.1796 | 0.164 | 0.145 | 18.3 | 17.9 | 20.3 | 0.800 | 0.562 | 7.93 | 0.30 |
| eight_schools-eight_schools_noncentered | owalnuts | 0.4528 | 0.054 | 0.078 | 12.6 | 8.7 | 8.7 | 0.798 | 0.414 | 1.28 | 1.10 |
| eight_schools-eight_schools_noncentered | cmdstan | 0.4418 | — | — | — | — | 8.3 | 0.775 (retained 0.887) | — | — | 1.05 |

Step ratio oWALNUTS / CmdStan (median over seeds): eight_schools-eight_schools_centered 1.176, eight_schools-eight_schools_noncentered 1.039

**eight_schools-eight_schools_centered / owalnuts, by start log-tau quartile:** Q1 refined_fraction 0.717, gradients_per_transition 184.468, depth 2.865; Q2 refined_fraction 0.184, gradients_per_transition 17.475, depth 3.674; Q3 refined_fraction 0.071, gradients_per_transition 24.000, depth 4.371; Q4 refined_fraction 0.040, gradients_per_transition 33.154, depth 4.847

**eight_schools-eight_schools_centered / cmdstan, by start log-tau quartile:** Q1 leapfrog_per_draw 12.879, acceptance 0.475, treedepth 2.844, divergent 0.107; Q2 leapfrog_per_draw 20.324, acceptance 0.848, treedepth 3.715, divergent 0.008; Q3 leapfrog_per_draw 28.003, acceptance 0.947, treedepth 4.225, divergent 0.001; Q4 leapfrog_per_draw 37.008, acceptance 0.973, treedepth 4.699, divergent 0.000

**eight_schools-eight_schools_centered / owalnuts level histogram:** transitions by selected level {'-1': 1123, '0': 16807, '1': 2972, '2': 1231, '3': 819, '4': 561, '5': 263, '6': 123, '7': 101}; built leaves by level [437455, 10235, 6823, 5394, 1639, 613, 314]

**eight_schools-eight_schools_noncentered / owalnuts, by start log-tau quartile:** Q1 refined_fraction 0.090, gradients_per_transition 9.178, depth 3.184; Q2 refined_fraction 0.032, gradients_per_transition 8.583, depth 3.140; Q3 refined_fraction 0.025, gradients_per_transition 8.520, depth 3.123; Q4 refined_fraction 0.070, gradients_per_transition 8.327, depth 2.988

**eight_schools-eight_schools_noncentered / cmdstan, by start log-tau quartile:** Q1 leapfrog_per_draw 8.552, acceptance 0.909, treedepth 3.056, divergent 0.000; Q2 leapfrog_per_draw 8.431, acceptance 0.915, treedepth 3.075, divergent 0.000; Q3 leapfrog_per_draw 8.339, acceptance 0.894, treedepth 3.079, divergent 0.000; Q4 leapfrog_per_draw 8.111, acceptance 0.799, treedepth 3.048, divergent 0.000

**eight_schools-eight_schools_noncentered / owalnuts level histogram:** transitions by selected level {'-1': 460, '0': 22237, '1': 1255, '2': 48}; built leaves by level [189854, 1747, 14]

## 2. Predictions

| prediction | values | held |
|---|---|---|
| P1_concentration | refined_starting_in_q1_fraction 0.708, q1_over_q4_refined_fraction 17.922 | True |
| P2_step_set_by_bulk | owalnuts_over_cmdstan_step 1.176 | True |
| P3_neck_paid_in_refinement | refined_gradient_share 0.719, owalnuts_q1_over_q4 5.564, cmdstan_q1_over_q4 0.348 | True |
| P4_twin | refined_fraction 0.054 | False |

## 3. Rule

| candidate | K1 centred vs CmdStan (>= 0.60) [95 % seed bootstrap] | K2 centred passes / divergences vs default | K3 funnel P5 ± s.e. | K4 regression passes, geomean (>= 0.95) | K5 tests | qualifies |
|---|---|---|---|---|---|---|
| owalnuts-costda | 0.577 [0.246, 1.911] (False) | 0 vs 0, 0 vs 12 (True) | 0.0466 ± 0.0033 (True) | 15 vs 15, 0.909 (False) | False | **False** |
| owalnuts-stanacc | 0.929 [0.258, 2.074] (True) | 0 vs 0, 3 vs 12 (True) | 0.0524 ± 0.0039 (False) | 14 vs 15, 0.618 (False) | False | **False** |
| owalnuts-levels2 | 0.799 [0.120, 2.965] (True) | 0 vs 0, 256 vs 12 (False) | 0.0075 ± 0.0025 (False) | 15 vs 15, 1.034 (True) | False | **False** |

| candidate | centred vs default (total grad) | centred vs CmdStan per sampling grad | eight_schools-eight_schools_noncentered | sblrc-blr | arK-arK | gp_pois_regr-gp_pois_regr | hmm_example-hmm_example |
|---|---:|---:|---:|---:|---:|---:|---:|
| owalnuts-costda | 1.642 | 0.492 | 0.868 (3/3) | 1.023 (3/3) | 0.960 (3/3) | 0.754 (3/3) | 0.966 (3/3) |
| owalnuts-stanacc | 2.028 | 0.794 | 1.030 (3/3) | 0.740 (3/3) | 0.770 (3/3) | 0.964 (2/3) | 0.159 (3/3) |
| owalnuts-levels2 | 2.456 | 0.963 | 1.227 (3/3) | 1.205 (3/3) | 0.900 (3/3) | 0.904 (3/3) | 0.981 (3/3) |

Default regression passes: {'eight_schools-eight_schools_noncentered': 3, 'sblrc-blr': 3, 'arK-arK': 3, 'gp_pois_regr-gp_pois_regr': 3, 'hmm_example-hmm_example': 3}. Centred passes {'owalnuts': 0, 'owalnuts-costda': 0, 'owalnuts-stanacc': 0, 'owalnuts-levels2': 0, 'cmdstan': 0}, divergences {'owalnuts': 12, 'owalnuts-costda': 0, 'owalnuts-stanacc': 3, 'owalnuts-levels2': 256, 'cmdstan': 692}.

## 4. Funnel (P(omega < -5), exact 0.0478)

| arm | seeds | pooled P5 | s.e. | t | within 1 s.e. |
|---|---:|---:|---:|---:|---|
| default | 10 | 0.0466 | 0.0022 | -0.54 | True |
| costda | 10 | 0.0466 | 0.0033 | -0.34 | True |
| stanacc | 10 | 0.0524 | 0.0039 | +1.18 | False |
| levels2 | 10 | 0.0075 | 0.0025 | -16.18 | False |
