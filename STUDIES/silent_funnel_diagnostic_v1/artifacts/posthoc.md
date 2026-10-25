# WP55 post-hoc descriptive analysis (not evidence)

12 positive (positives-list, wrong) cells, 39 negative (negatives-list, clean) cells.

| score | AUC | best post-hoc cut | sens | spec |
|---|---:|---:|---:|---:|
| R_cell_max | 0.778 | 0.02693 | 0.50 | 1.00 |
| S_cell_max | 0.688 | 1.246 | 0.58 | 0.95 |
| R_max_over_cell_median | 0.669 | 3.312 | 0.50 | 0.82 |
| depth_given_refined_cell_max | 0.839 | 1.034 | 0.75 | 0.90 |

Top-5 negatives per score:

* R_cell_max: one_comp_mm_elim_abs-one_comp_mm_elim_abs/731402 0.02693, eight_schools-eight_schools_noncentered/731403 0.02412, garch-garch11/731403 0.02343, eight_schools-eight_schools_noncentered/731402 0.01635, eight_schools-eight_schools_noncentered/731401 0.01281
* S_cell_max: arma-arma11/731401 18.38, earnings-logearn_interaction/731401 3.662, hmm_example-hmm_example/731401 1.246, hudson_lynx_hare-lotka_volterra/731402 1.229, garch-garch11/731402 1.205
* R_max_over_cell_median: kidiq-kidscore_momhsiq/731401 6.019, hmm_example-hmm_example/731401 5.542, nes2000-nes/731401 4.531, hmm_example-hmm_example/731402 4.4, kidiq-kidscore_momhsiq/731403 3.838
* depth_given_refined_cell_max: gp_pois_regr-gp_pois_regr/731402 1.089, eight_schools-eight_schools_noncentered/731402 1.07, eight_schools-eight_schools_noncentered/731403 1.048, eight_schools-eight_schools_noncentered/731401 1.045, one_comp_mm_elim_abs-one_comp_mm_elim_abs/731402 1.034

| positive cell | highest-R chain | furthest chain | chain distance (ref sd) | R per chain |
|---|---:|---:|---|---|
| funnel10/731401 | 3 | 3 | 1.23 0.18 0.45 2.19 | 0.2697 0.0499 0.0350 0.8373 |
| funnel10/731402 | 2 | 2 | 0.46 0.06 0.77 0.23 | 0.0001 0.1285 0.6240 0.0417 |
| funnel10/731403 | 3 | 0 | 0.41 0.04 0.19 0.08 | 0.0127 0.0107 0.0301 0.0827 |
| eight_schools-eight_schools_centered/731401 | 2 | 2 | 0.09 0.06 0.73 0.05 | 0.0680 0.1042 0.4771 0.0431 |
| eight_schools-eight_schools_centered/731402 | 1 | 0 | 0.20 0.04 0.18 0.07 | 0.0132 0.1162 0.0974 0.0891 |
| eight_schools-eight_schools_centered/731403 | 1 | 2 | 0.16 0.09 0.18 0.05 | 0.0012 0.2137 0.1915 0.0352 |
| seeds_data-seeds_centered_model/731401 | 0 | 2 | 0.09 0.07 0.12 0.07 | 0.0063 0.0025 0.0009 0.0044 |
| seeds_data-seeds_centered_model/731402 | 2 | 0 | 0.14 0.11 0.06 0.13 | 0.0015 0.0011 0.0104 0.0013 |
| seeds_data-seeds_centered_model/731403 | 1 | 3 | 0.08 0.08 0.10 0.17 | 0.0047 0.0053 0.0004 0.0010 |
| radon_all-radon_hierarchical_intercept_centered/731401 | 0 | 2 | 0.11 0.10 0.11 0.10 | 0.0025 0.0009 0.0012 0.0000 |
| radon_all-radon_hierarchical_intercept_centered/731402 | 0 | 2 | 0.07 0.13 0.17 0.15 | 0.0021 0.0013 0.0000 0.0013 |
| radon_all-radon_hierarchical_intercept_centered/731403 | 1 | 0 | 0.14 0.10 0.08 0.09 | 0.0002 0.0033 0.0000 0.0018 |
