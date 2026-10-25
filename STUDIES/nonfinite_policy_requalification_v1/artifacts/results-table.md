# WP54 results table

Every pair of cells (abort, reject_leaf). `nfr` = nonfinite-position rejections (RejectLeaf leaves); `div` = retained divergences; `ident` = draws bit-identical (only defined where abort completed).

| block | model | seed | abort | reject_leaf | ident | rl nfr | rl div | rl max abs z | rl gates |
|---|---|---:|---|---|---|---:|---:|---:|---|
| S1-replication-house | sblrc-blr | 50801734 | aborted | ok pass z 1.63 | None | 1 | 0 | 1.63 | all |
| S1-replication-wp50 | sblrc-blr | 50801734 | aborted | ok pass z 1.63 | None | 1 | 0 | 1.63 | all |
| S2-lotka-wp48 | hudson_lynx_hare-lotka_volterra | 148101 | timeout | timeout | None | None | None |  |  |
| S2-lotka-wp48 | hudson_lynx_hare-lotka_volterra | 148102 | ok pass z 0.82 | ok pass z 0.82 | True | 0 | 0 | 0.82 | all |
| S2-lotka-wp48 | hudson_lynx_hare-lotka_volterra | 148103 | ok pass z 1.04 | ok pass z 1.04 | True | 0 | 0 | 1.04 | all |
| S3-sblrc-fresh | sblrc-blr | 5402101 | ok pass z 0.66 | ok pass z 0.66 | True | 0 | 0 | 0.66 | all |
| S3-sblrc-fresh | sblrc-blr | 5402102 | ok pass z 0.45 | ok pass z 0.45 | True | 0 | 0 | 0.45 | all |
| S3-sblrc-fresh | sblrc-blr | 5402103 | ok pass z 0.99 | ok pass z 0.99 | True | 0 | 0 | 0.99 | all |
| S3-sblrc-fresh | sblrc-blr | 5402104 | ok pass z 1.67 | ok pass z 1.67 | True | 0 | 0 | 1.67 | all |
| S3-sblrc-fresh | sblrc-blr | 5402105 | ok pass z 0.37 | ok pass z 0.37 | True | 0 | 0 | 0.37 | all |
| S3-sblrc-fresh | sblrc-blr | 5402106 | ok pass z 1.92 | ok pass z 1.92 | True | 0 | 0 | 1.92 | all |
| S3-sblrc-fresh | sblrc-blr | 5402107 | ok pass z 1.09 | ok pass z 1.09 | True | 0 | 0 | 1.09 | all |
| S3-sblrc-fresh | sblrc-blr | 5402108 | ok pass z 0.78 | ok pass z 0.78 | True | 0 | 0 | 0.78 | all |
| S3-sblrc-fresh | sblrc-blr | 5402109 | ok pass z 1.65 | ok pass z 1.65 | True | 0 | 0 | 1.65 | all |
| S3-sblrc-fresh | sblrc-blr | 5402110 | ok pass z 1.34 | ok pass z 1.34 | True | 0 | 0 | 1.34 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403101 | ok pass z 1.38 | ok pass z 1.38 | True | 0 | 0 | 1.38 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403102 | ok fail z 1.20 | ok fail z 1.20 | True | 0 | 0 | 1.2 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403103 | ok pass z 0.69 | ok pass z 0.69 | True | 0 | 0 | 0.69 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403104 | timeout | timeout | None | None | None |  |  |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403105 | ok pass z 1.95 | ok pass z 1.95 | True | 0 | 0 | 1.95 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403106 | ok pass z 1.73 | ok pass z 1.73 | True | 0 | 0 | 1.73 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403107 | timeout | timeout | None | None | None |  |  |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403108 | ok fail z 1.19 | ok fail z 1.19 | True | 0 | 0 | 1.19 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403109 | ok pass z 1.86 | ok pass z 1.86 | True | 0 | 0 | 1.86 | all |
| S4-lotka-fresh | hudson_lynx_hare-lotka_volterra | 5403110 | timeout | timeout | None | None | None |  |  |
| F-funnel | funnel | 5404101 | ok z +0.14 | ok z +0.14 | True | 0 | 0 |  | all |
| F-funnel | funnel | 5404102 | ok z +0.59 | ok z +0.59 | True | 0 | 0 |  | all |
| F-funnel | funnel | 5404103 | ok z -0.02 | ok z -0.02 | True | 0 | 2 |  | all |
| H-house | eight_schools-eight_schools_noncentered | 5401101 | ok pass z 2.54 | ok pass z 2.54 | True | 0 | 0 | 2.54 | all |
| H-house | eight_schools-eight_schools_noncentered | 5401102 | ok pass z 1.98 | ok pass z 1.98 | True | 0 | 0 | 1.98 | all |
| H-house | eight_schools-eight_schools_noncentered | 5401103 | ok pass z 1.27 | ok pass z 1.27 | True | 0 | 0 | 1.27 | all |
| H-house | eight_schools-eight_schools_centered | 5401101 | ok fail z 2.31 | ok fail z 2.31 | True | 0 | 0 | 2.31 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | eight_schools-eight_schools_centered | 5401102 | ok fail z 2.13 | ok fail z 2.13 | True | 0 | 0 | 2.13 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | eight_schools-eight_schools_centered | 5401103 | ok fail z 2.29 | ok fail z 2.29 | True | 0 | 0 | 2.29 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | diamonds-diamonds | 5401101 | ok pass z 2.38 | ok pass z 2.38 | True | 0 | 0 | 2.38 | all |
| H-house | diamonds-diamonds | 5401102 | ok pass z 2.14 | ok pass z 2.14 | True | 0 | 0 | 2.14 | all |
| H-house | diamonds-diamonds | 5401103 | ok pass z 2.34 | ok pass z 2.34 | True | 0 | 0 | 2.34 | all |
| H-house | earnings-logearn_interaction | 5401101 | ok pass z 1.05 | ok pass z 1.05 | True | 0 | 0 | 1.05 | all |
| H-house | earnings-logearn_interaction | 5401102 | ok pass z 0.70 | ok pass z 0.70 | True | 0 | 0 | 0.7 | all |
| H-house | earnings-logearn_interaction | 5401103 | ok pass z 1.16 | ok pass z 1.16 | True | 0 | 0 | 1.16 | all |
| H-house | mesquite-logmesquite_logvash | 5401101 | ok pass z 0.92 | ok pass z 0.92 | True | 0 | 0 | 0.92 | all |
| H-house | mesquite-logmesquite_logvash | 5401102 | ok pass z 1.45 | ok pass z 1.45 | True | 0 | 0 | 1.45 | all |
| H-house | mesquite-logmesquite_logvash | 5401103 | ok pass z 1.36 | ok pass z 1.36 | True | 0 | 0 | 1.36 | all |
| H-house | kidiq-kidscore_momhsiq | 5401101 | ok pass z 1.81 | ok pass z 1.81 | True | 0 | 0 | 1.81 | all |
| H-house | kidiq-kidscore_momhsiq | 5401102 | ok pass z 2.58 | ok pass z 2.58 | True | 0 | 0 | 2.58 | all |
| H-house | kidiq-kidscore_momhsiq | 5401103 | ok pass z 1.26 | ok pass z 1.26 | True | 0 | 0 | 1.26 | all |
| H-house | sblrc-blr | 5401101 | ok pass z 0.96 | ok pass z 0.96 | True | 0 | 0 | 0.96 | all |
| H-house | sblrc-blr | 5401102 | ok pass z 1.52 | ok pass z 1.52 | True | 0 | 0 | 1.52 | all |
| H-house | sblrc-blr | 5401103 | ok pass z 1.19 | ok pass z 1.19 | True | 0 | 0 | 1.19 | all |
| H-house | nes2000-nes | 5401101 | ok pass z 2.15 | ok pass z 2.15 | True | 0 | 0 | 2.15 | all |
| H-house | nes2000-nes | 5401102 | ok pass z 2.74 | ok pass z 2.74 | True | 0 | 0 | 2.74 | all |
| H-house | nes2000-nes | 5401103 | ok pass z 1.78 | ok pass z 1.78 | True | 0 | 0 | 1.78 | all |
| H-house | arK-arK | 5401101 | ok pass z 1.14 | ok pass z 1.14 | True | 0 | 0 | 1.14 | all |
| H-house | arK-arK | 5401102 | ok pass z 2.29 | ok pass z 2.29 | True | 0 | 0 | 2.29 | all |
| H-house | arK-arK | 5401103 | ok pass z 1.37 | ok pass z 1.37 | True | 0 | 0 | 1.37 | all |
| H-house | arma-arma11 | 5401101 | ok pass z 1.40 | ok pass z 1.40 | True | 0 | 0 | 1.4 | all |
| H-house | arma-arma11 | 5401102 | ok pass z 0.71 | ok pass z 0.71 | True | 0 | 0 | 0.71 | all |
| H-house | arma-arma11 | 5401103 | ok pass z 1.31 | ok pass z 1.31 | True | 0 | 0 | 1.31 | all |
| H-house | garch-garch11 | 5401101 | ok pass z 1.92 | ok pass z 1.92 | True | 0 | 0 | 1.92 | all |
| H-house | garch-garch11 | 5401102 | ok pass z 0.76 | ok pass z 0.76 | True | 0 | 0 | 0.76 | all |
| H-house | garch-garch11 | 5401103 | ok pass z 0.87 | ok pass z 0.87 | True | 0 | 0 | 0.87 | all |
| H-house | gp_pois_regr-gp_pois_regr | 5401101 | ok pass z 1.93 | ok pass z 1.93 | True | 0 | 0 | 1.93 | all |
| H-house | gp_pois_regr-gp_pois_regr | 5401102 | ok fail z 1.67 | ok fail z 1.67 | True | 0 | 0 | 1.67 | min_tail_ess |
| H-house | gp_pois_regr-gp_pois_regr | 5401103 | ok pass z 1.77 | ok pass z 1.77 | True | 0 | 0 | 1.77 | all |
| H-house | hmm_example-hmm_example | 5401101 | ok pass z 1.70 | ok pass z 1.70 | True | 0 | 0 | 1.7 | all |
| H-house | hmm_example-hmm_example | 5401102 | ok pass z 1.19 | ok pass z 1.19 | True | 0 | 0 | 1.19 | all |
| H-house | hmm_example-hmm_example | 5401103 | ok pass z 0.68 | ok pass z 0.68 | True | 0 | 0 | 0.68 | all |
| H-house | bball_drive_event_0-hmm_drive_0 | 5401101 | ok pass z 1.37 | ok pass z 1.37 | True | 0 | 0 | 1.37 | all |
| H-house | bball_drive_event_0-hmm_drive_0 | 5401102 | ok pass z 2.38 | ok pass z 2.38 | True | 0 | 0 | 2.38 | all |
| H-house | bball_drive_event_0-hmm_drive_0 | 5401103 | ok pass z 1.64 | ok pass z 1.64 | True | 0 | 0 | 1.64 | all |
| H-house | one_comp_mm_elim_abs-one_comp_mm_elim_abs | 5401101 | ok pass z 1.86 | ok pass z 1.86 | True | 0 | 0 | 1.86 | all |
| H-house | one_comp_mm_elim_abs-one_comp_mm_elim_abs | 5401102 | ok fail z 0.99 | ok fail z 0.99 | True | 0 | 0 | 0.99 | max_rank_rhat,min_tail_ess |
| H-house | one_comp_mm_elim_abs-one_comp_mm_elim_abs | 5401103 | ok fail z 0.78 | ok fail z 0.78 | True | 0 | 0 | 0.78 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | hudson_lynx_hare-lotka_volterra | 5401101 | ok fail z 1.12 | ok fail z 1.12 | True | 0 | 0 | 1.12 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | hudson_lynx_hare-lotka_volterra | 5401102 | ok pass z 0.95 | ok pass z 0.95 | True | 0 | 0 | 0.95 | all |
| H-house | hudson_lynx_hare-lotka_volterra | 5401103 | ok pass z 1.35 | ok pass z 1.35 | True | 0 | 0 | 1.35 | all |
| H-house | mcycle_gp-accel_gp | 5401101 | ok fail z 2.62 | ok fail z 2.62 | True | 0 | 0 | 2.62 | max_rank_rhat,min_tail_ess |
| H-house | mcycle_gp-accel_gp | 5401102 | ok fail z 2.01 | ok fail z 2.01 | True | 0 | 0 | 2.01 | max_rank_rhat,min_bulk_ess,min_tail_ess |
| H-house | mcycle_gp-accel_gp | 5401103 | ok fail z 2.70 | ok fail z 2.70 | True | 0 | 0 | 2.7 | max_rank_rhat,min_bulk_ess,min_tail_ess |

Completed: abort 73/79, reject_leaf 75/79.
Fingerprint: 73/73 completed-abort cells bit-identical.
House geomean min bulk ESS/gradient: abort 0.0035247404254715, reject_leaf 0.0035247404254715.
Decision: {"D1_bit_identical_all_completed_abort_cells": true, "D2_reject_completes_strictly_more": true, "D3_no_silently_wrong_rescue": true, "D4_funnel_passes_under_reject_leaf": true, "flip": true}
