# delta2_default_confirmation_v1 (WP63) — results

Commit `33a8e39d`; ratio = delta2 / default min-bulk-ESS per gradient, paired by seed.

| model | ratio geomean (A) | per-seed ratios (A) | passes default / delta2 (A+B) | divergent cells default / delta2 | max abs z default / delta2 | grads median default / delta2 | failed gates default ; delta2 |
|---|---:|---|---|---|---|---|---|
| eight_schools-eight_schools_noncentered | **1.027** | 0.83, 1.32, 0.91, 1.13 | 4/4 / 4/4 | 0 / 0 | 2.81 / 1.75 | 69,720 / 68,482 | - ; - |
| eight_schools-eight_schools_centered | **0.357** | 0.68, 1.24, 0.34, 0.06 | 0/4 / 0/4 | 0 / 2 | 2.36 / 1.87 | 203,669 / 297,730 | max_rank_rhat, min_bulk_ess, min_tail_ess ; max_rank_rhat, min_bulk_ess, min_tail_ess, sampling_divergences |
| diamonds-diamonds | **0.931** | 1.08, 1.08, 0.84, 0.77 | 4/4 / 4/4 | 0 / 0 | 2.49 / 2.91 | 6,642,562 / 6,775,754 | - ; - |
| earnings-logearn_interaction | **0.879** | 0.77, 1.18, 0.79, 0.83 | 4/4 / 4/4 | 0 / 0 | 2.21 / 2.19 | 1,492,484 / 1,553,692 | - ; - |
| mesquite-logmesquite_logvash | **0.958** | 0.82, 1.14, 0.94, 0.96 | 4/4 / 4/4 | 0 / 0 | 1.69 / 1.74 | 378,646 / 389,445 | - ; - |
| kidiq-kidscore_momhsiq | **1.156** | 0.94, 0.94, 1.40, 1.45 | 4/4 / 4/4 | 0 / 0 | 2.14 / 2.02 | 346,900 / 373,417 | - ; - |
| sblrc-blr | **1.031** | 0.83, 1.22, 0.98, 1.14 | 4/4 / 4/4 | 0 / 0 | 1.63 / 1.46 | 154,588 / 156,258 | - ; - |
| nes2000-nes | **1.014** | 1.05, 1.07, 1.00, 0.94 | 4/4 / 4/4 | 0 / 0 | 1.67 / 3.39 | 426,728 / 428,608 | - ; - |
| arK-arK | **1.111** | 1.43, 0.99, 1.15, 0.93 | 4/4 / 4/4 | 0 / 0 | 2.21 / 1.90 | 267,926 / 262,196 | - ; - |
| arma-arma11 | **1.069** | 1.06, 1.08, 1.15, 1.00 | 4/4 / 4/4 | 0 / 0 | 2.39 / 1.95 | 54,442 / 51,664 | - ; - |
| garch-garch11 | **1.133** | 0.96, 1.12, 1.14, 1.34 | 4/4 / 4/4 | 0 / 0 | 3.08 / 1.98 | 94,568 / 94,091 | - ; - |
| gp_pois_regr-gp_pois_regr | **1.460** | 3.05, 1.00, 1.45, 1.03 | 2/4 / 4/4 | 0 / 0 | 2.65 / 2.70 | 1,203,288 / 1,316,814 | max_rank_rhat, min_bulk_ess, min_tail_ess ; - |
| hmm_example-hmm_example | **1.021** | 0.99, 0.99, 1.15, 0.97 | 4/4 / 4/4 | 0 / 0 | 1.57 / 2.35 | 113,186 / 109,122 | - ; - |
| bball_drive_event_0-hmm_drive_0 | **0.172** | 0.69, 0.00, 0.83, 0.83 | 8/8 / 7/8 | 0 / 0 | 2.72 / 2.28 | 80,540 / 77,068 | - ; max_rank_rhat, min_bulk_ess, min_tail_ess |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | **0.736** | 1.29, 1.19, 0.33, 0.59 | 3/4 / 1/4 | 0 / 0 | 3.86 / 2.41 | 78,986 / 74,031 | min_tail_ess ; max_rank_rhat, min_bulk_ess, min_tail_ess |
| hudson_lynx_hare-lotka_volterra | **1.104** | 1.08, 1.03, 1.14, 1.18 | 4/4 / 4/4 | 0 / 0 | 1.99 / 1.81 | 278,282 / 283,348 | - ; - |
| mcycle_gp-accel_gp | **1.594** | 0.42, 0.16, 3.23, 29.28 | 0/8 / 2/8 | 0 / 0 | 3.57 / 5.07 | 2,800,718 / 3,400,060 | max_rank_rhat, min_bulk_ess, min_tail_ess ; max_rank_rhat, min_bulk_ess, min_tail_ess |

**Paired geomean over A (17 models): 0.896**; LOSO 630601: 0.874, 630602: 0.985, 630603: 0.871, 630604: 0.860 (min 0.860); pooled over all A pairs 0.896; passing pairs only 1.019; per-seed geomeans 630601: 0.966, 630602: 0.675, 630603: 0.976, 630604: 1.014
Gates: default A 57/68, B 4/8, A+B 61; delta2 A 57/68, B 5/8, A+B 62
Errors: {'default': [], 'delta2': []}
Passing cells with |z| > 4: {'default': [], 'delta2': ['A mcycle_gp-accel_gp 630604 sdgp_1 5.07']}

| funnel arm | seeds | pooled P(omega<-5) | between-seed SE | seeds abs z > 2 | divergences (div-free seeds) | depth caps | median gradients | geomean min ESS / gradient | pooled P(omega<-6) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| default | 12 | 0.0502 | 0.0029 | 2 | 5 (8) | 913 | 4,190,056 | 1.044e-04 | 0.0243 |
| delta2 | 12 | 0.0484 | 0.0026 | 2 | 26 (6) | 1445 | 4,389,450 | 1.123e-04 | 0.0236 |

Funnel: delta2 - default = -0.0018, SE of the difference 0.0039 (exact 0.0478); divergence ratio 5.20

Decision rule: R1_paired_geomean_ge_1.08 FAIL; R2_loso_min_ge_1.00 FAIL; R3_gates_AB_delta2_ge_default_minus_1 PASS; R4_no_delta2_passing_cell_abs_z_gt_4 FAIL; R5_funnel_tail_not_lower_by_more_than_1_se_diff PASS; R6_funnel_divergences_le_1.5x FAIL
**Decision (frozen rule): NO FLIP: document and change nothing** (complete: True)

Predictions: P1_paired_geomean_in_[1.05,1.15] failed; P2_loso_min_ge_1.0 failed; P3_gates_within_1 held; P4_funnel_tail_within_1_se_diff held; P5_funnel_divergences_within_1.5x failed
