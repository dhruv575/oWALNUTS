# WP65 frozen decision rule

ReplicatedConcurrent qualified on Linux: **True**; failed clauses: none
DirectConcurrent (STAN_THREADS) qualified on Linux: **True**; failed clauses: none

| clause | held | detail |
|---|---|---|
| Q1_replicated_zero_faults | True | `{"faults": 0, "children": 500}` |
| Q2_bit_identity | True | `{"stress": {"comparable": 500, "differing_seeds": [], "identical": 500}, "bench": {"comparable": 16, "identical": 16}}` |
| Q3a_replicated4_over_direct4_ge_2 | True | `{"values": {"eight_schools-eight_schools_noncentered": 5.432655948357685, "arK-arK": 4.059872658193773, "diamonds-diamonds": 3.983232719382711}}` |
| Q3b_serialised_over_replicated_wall_per_gradient_ge_1_5 | True | `{"value": 3.60890345922584, "n_models": 16}` |
| Q4_replicated_arm_all_ok | True | `{"ok": 16}` |
| T1_threaded_direct_zero_faults | True | `{"faults": 0, "children": 500}` |
| T2_threads_direct4_over_nothreads_direct4_ge_2 | True | `{"values": {"eight_schools-eight_schools_noncentered": 4.365072306856165, "arK-arK": 2.543638489777282, "diamonds-diamonds": 4.031458489091527}}` |
| T3_threaded_arm_all_ok_and_wall_le_1_25 | True | `{"ok": 16, "value": 1.2484176663774063}` |
