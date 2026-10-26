# WP74 results (96 cells, 96 ok)

**Verdict: PROPOSE K.** Implementation mismatches: 0.

| clause | K | S | G |
|---|---|---|---|
| (i) | True | False | False |
| (ii) | True | True | False |
| (iii) | True | True | True |

## Arm (i), fresh (block I)

splits 5 (2-2: 1, 3-1: 4); undefined []; missed: current ['I--two_mode--7401201', 'I--two_mode--7401203', 'I--two_mode--7401204', 'I--two_mode--7401205'], K [], S ['I--two_mode--7401203', 'I--two_mode--7401204', 'I--two_mode--7401205'], G ['I--two_mode--7401201', 'I--two_mode--7401203', 'I--two_mode--7401204', 'I--two_mode--7401205']; non-split firings K [] S [] G ['I--bball_drive_event_0__hmm_drive_0--7401105']

| cell | split | groups | max R-hat | current | K | S | G | K true group | K clusters | G gap/thr (warm, samp) |
|---|---|---|---|---|---|---|---|---|---|---|
| I--two_mode--7401201 | 2-2 | [[0, 2], [1, 3]] | 1.733 | [] | [0, 2] | [0, 2] | [] | True | [[0, 2], [1, 3]] | 0.05, 0.08 |
| I--two_mode--7401202 | none | [[], [0, 1, 2, 3]] | 1.003 | [] | [] | [] | [] | None | None | 0.02, 0.04 |
| I--two_mode--7401203 | 3-1 | [[3], [0, 1, 2]] | 1.621 | [] | [1, 3] | [] | [] | False | [[0, 2], [1], [3]] | 0.07, 0.07 |
| I--two_mode--7401204 | 3-1 | [[0], [1, 2, 3]] | 1.345 | [] | [0, 1] | [] | [] | False | [[0], [1], [2, 3]] | 0.09, 0.03 |
| I--two_mode--7401205 | 3-1 | [[1, 2, 3], [0]] | 1.453 | [] | [0, 2] | [] | [] | False | [[0], [1, 3], [2]] | 0.11, 0.12 |
| I--two_mode--7401206 | none | [[], [0, 1, 2, 3]] | 1.005 | [] | [] | [] | [] | None | None | 0.01, 0.01 |
| I--bball_drive_event_0__hmm_drive_0--7401101 | none | [[], [0, 1, 2, 3]] | 1.003 | [] | [] | [] | [] | None | None | 0.02, 0.02 |
| I--bball_drive_event_0__hmm_drive_0--7401102 | none | [[], [0, 1, 2, 3]] | 1.001 | [] | [] | [] | [] | None | None | 0.08, 0.02 |
| I--bball_drive_event_0__hmm_drive_0--7401103 | 3-1 | [[0], [1, 2, 3]] | 1.050 | [0] | [0] | [] | [0] | True | [[0], [1, 2, 3]] | 9.15, 0.06 |
| I--bball_drive_event_0__hmm_drive_0--7401104 | none | [[], [0, 1, 2, 3]] | 1.001 | [] | [] | [] | [] | None | None | 0.02, 0.02 |
| I--bball_drive_event_0__hmm_drive_0--7401105 | none | [[], [0, 1, 2, 3]] | 1.002 | [3] | [] | [] | [3] | None | None | 8.76, 0.01 |
| I--bball_drive_event_0__hmm_drive_0--7401106 | none | [[], [0, 1, 2, 3]] | 1.002 | [] | [] | [] | [] | None | None | 0.05, 0.02 |

## Motivating replay (block IV, not decision)

splits 6 (2-2: 3, 3-1: 3); undefined []; missed: current ['IV--two_mode--6903201', 'IV--two_mode--6903202', 'IV--two_mode--6903205'], K ['IV--two_mode--6903202'], S ['IV--two_mode--6903202'], G ['IV--two_mode--6903201', 'IV--two_mode--6903202', 'IV--two_mode--6903205']; non-split firings K [] S [] G []

| cell | split | groups | max R-hat | current | K | S | G | K true group | K clusters | G gap/thr (warm, samp) |
|---|---|---|---|---|---|---|---|---|---|---|
| IV--two_mode--6903201 | 2-2 | [[2, 3], [0, 1]] | 1.733 | [] | [2, 3] | [2, 3] | [] | True | [[0, 1], [2, 3]] | 0.08, 0.08 |
| IV--two_mode--6903202 | 2-2 | [[0, 1], [2, 3]] | 1.501 | [] | [] | [] | [] | None | [[0], [1], [2], [3]] | 0.06, 0.05 |
| IV--two_mode--6903203 | 3-1 | [[0, 2, 3], [1]] | 1.500 | [1] | [1] | [] | [] | True | [[0, 2, 3], [1]] | 0.06, 0.10 |
| IV--two_mode--6903204 | 3-1 | [[0], [1, 2, 3]] | 1.528 | [0] | [0] | [] | [] | True | [[0], [1, 2, 3]] | 0.05, 0.06 |
| IV--two_mode--6903205 | 2-2 | [[1, 3], [0, 2]] | 1.732 | [] | [1, 3] | [1, 3] | [] | True | [[0, 2], [1, 3]] | 0.07, 0.07 |
| IV--two_mode--6903206 | none | [[], [0, 1, 2, 3]] | 1.003 | [] | [] | [] | [] | None | None | 0.01, 0.01 |
| IV--bball_drive_event_0__hmm_drive_0--6903102 | 3-1 | [[2], [0, 1, 3]] | 1.022 | [2] | [2] | [] | [2] | True | [[0, 1, 3], [2]] | 9.33, 0.03 |

## Arm (ii), 17 house models x 3 fresh seeds

completed 51/51; passing 43; not completed []; FP K []; FP S []; FP G ['II--bball_drive_event_0__hmm_drive_0--7402001', 'II--hudson_lynx_hare__lotka_volterra--7402001']; shipped warning on passing cells ['II--bball_drive_event_0__hmm_drive_0--7402001', 'II--bball_drive_event_0__hmm_drive_0--7402003', 'II--hudson_lynx_hare__lotka_volterra--7402001']; max G gap/threshold on passing cells 7.963867933312611

New K firings on failing cells: [{'id': 'II--sblrc__blr--7402002', 'named': [0], 'off_chains': [], 'named_off': False}, {'id': 'II--hudson_lynx_hare__lotka_volterra--7402002', 'named': [1], 'off_chains': [1], 'named_off': True}]

New S firings on failing cells: []

New G firings on failing cells: [{'id': 'II--hudson_lynx_hare__lotka_volterra--7402002', 'named': [1], 'off_chains': [1], 'named_off': True}]

| cell | passed | R-hat | off | max R (unc) | current | K | S | G |
|---|---|---|---|---|---|---|---|---|
| II--eight_schools__eight_schools_noncentered--7402001 | True | 1.0012 | [] | 1.0026 | [] | [] | [] | [] |
| II--eight_schools__eight_schools_noncentered--7402002 | True | 1.0013 | [] | 1.0023 | [] | [] | [] | [] |
| II--eight_schools__eight_schools_noncentered--7402003 | True | 1.0016 | [] | 1.0022 | [] | [] | [] | [] |
| II--eight_schools__eight_schools_centered--7402001 | False | 1.0735 | [] | 1.0735 | [] | [] | [] | [] |
| II--eight_schools__eight_schools_centered--7402002 | False | 1.0513 | [] | 1.0513 | [] | [] | [] | [] |
| II--eight_schools__eight_schools_centered--7402003 | False | 1.0923 | [] | 1.0923 | [] | [] | [] | [] |
| II--diamonds__diamonds--7402001 | True | 1.0037 | [] | 1.0037 | [] | [] | [] | [] |
| II--diamonds__diamonds--7402002 | True | 1.0033 | [] | 1.0033 | [] | [] | [] | [] |
| II--diamonds__diamonds--7402003 | True | 1.0033 | [] | 1.0033 | [] | [] | [] | [] |
| II--earnings__logearn_interaction--7402001 | True | 1.0034 | [] | 1.0034 | [] | [] | [] | [] |
| II--earnings__logearn_interaction--7402002 | True | 1.0045 | [] | 1.0045 | [] | [] | [] | [] |
| II--earnings__logearn_interaction--7402003 | True | 1.0075 | [] | 1.0075 | [] | [] | [] | [] |
| II--mesquite__logmesquite_logvash--7402001 | True | 1.0045 | [] | 1.0045 | [] | [] | [] | [] |
| II--mesquite__logmesquite_logvash--7402002 | True | 1.0044 | [] | 1.0044 | [] | [] | [] | [] |
| II--mesquite__logmesquite_logvash--7402003 | True | 1.0076 | [] | 1.0076 | [] | [] | [] | [] |
| II--kidiq__kidscore_momhsiq--7402001 | True | 1.0019 | [] | 1.0019 | [] | [] | [] | [] |
| II--kidiq__kidscore_momhsiq--7402002 | True | 1.0025 | [] | 1.0025 | [] | [] | [] | [] |
| II--kidiq__kidscore_momhsiq--7402003 | True | 1.0033 | [] | 1.0033 | [] | [] | [] | [] |
| II--sblrc__blr--7402001 | True | 1.0029 | [] | 1.0029 | [] | [] | [] | [] |
| II--sblrc__blr--7402002 | False | 1.0122 | [] | 1.0122 | [0] | [0] | [] | [] |
| II--sblrc__blr--7402003 | True | 1.0094 | [] | 1.0094 | [] | [] | [] | [] |
| II--nes2000__nes--7402001 | True | 1.0029 | [] | 1.0029 | [] | [] | [] | [] |
| II--nes2000__nes--7402002 | True | 1.0032 | [] | 1.0032 | [] | [] | [] | [] |
| II--nes2000__nes--7402003 | True | 1.0024 | [] | 1.0024 | [] | [] | [] | [] |
| II--arK__arK--7402001 | True | 1.0020 | [] | 1.0020 | [] | [] | [] | [] |
| II--arK__arK--7402002 | True | 1.0018 | [] | 1.0018 | [] | [] | [] | [] |
| II--arK__arK--7402003 | True | 1.0023 | [] | 1.0023 | [] | [] | [] | [] |
| II--arma__arma11--7402001 | True | 1.0032 | [] | 1.0032 | [] | [] | [] | [] |
| II--arma__arma11--7402002 | True | 1.0010 | [] | 1.0010 | [] | [] | [] | [] |
| II--arma__arma11--7402003 | True | 1.0011 | [] | 1.0011 | [] | [] | [] | [] |
| II--garch__garch11--7402001 | True | 1.0005 | [] | 1.0005 | [] | [] | [] | [] |
| II--garch__garch11--7402002 | True | 1.0022 | [] | 1.0025 | [] | [] | [] | [] |
| II--garch__garch11--7402003 | True | 1.0023 | [] | 1.0028 | [] | [] | [] | [] |
| II--gp_pois_regr__gp_pois_regr--7402001 | True | 1.0049 | [] | 1.0066 | [] | [] | [] | [] |
| II--gp_pois_regr__gp_pois_regr--7402002 | True | 1.0041 | [] | 1.0048 | [] | [] | [] | [] |
| II--gp_pois_regr__gp_pois_regr--7402003 | True | 1.0022 | [] | 1.0041 | [] | [] | [] | [] |
| II--hmm_example__hmm_example--7402001 | True | 1.0014 | [] | 1.0014 | [] | [] | [] | [] |
| II--hmm_example__hmm_example--7402002 | True | 1.0015 | [] | 1.0022 | [] | [] | [] | [] |
| II--hmm_example__hmm_example--7402003 | True | 1.0057 | [] | 1.0065 | [] | [] | [] | [] |
| II--bball_drive_event_0__hmm_drive_0--7402001 | True | 1.0025 | [] | 1.0024 | [2] | [] | [] | [2] |
| II--bball_drive_event_0__hmm_drive_0--7402002 | True | 1.0041 | [] | 1.0041 | [] | [] | [] | [] |
| II--bball_drive_event_0__hmm_drive_0--7402003 | True | 1.0029 | [] | 1.0026 | [1] | [] | [] | [] |
| II--one_comp_mm_elim_abs__one_comp_mm_elim_abs--7402001 | False | 1.0037 | [] | 1.0037 | [] | [] | [] | [] |
| II--one_comp_mm_elim_abs__one_comp_mm_elim_abs--7402002 | True | 1.0028 | [] | 1.0028 | [] | [] | [] | [] |
| II--one_comp_mm_elim_abs__one_comp_mm_elim_abs--7402003 | True | 1.0045 | [] | 1.0044 | [] | [] | [] | [] |
| II--hudson_lynx_hare__lotka_volterra--7402001 | True | 1.0091 | [] | 1.0091 | [0] | [] | [] | [0] |
| II--hudson_lynx_hare__lotka_volterra--7402002 | False | 1.2572 | [1] | 1.2568 | [1] | [1] | [] | [1] |
| II--hudson_lynx_hare__lotka_volterra--7402003 | True | 1.0018 | [] | 1.0018 | [] | [] | [] | [] |
| II--mcycle_gp__accel_gp--7402001 | True | 1.0093 | [] | 1.0093 | [] | [] | [] | [] |
| II--mcycle_gp__accel_gp--7402002 | False | 1.0395 | [] | 1.0395 | [] | [] | [] | [] |
| II--mcycle_gp__accel_gp--7402003 | False | 1.0520 | [] | 1.0520 | [] | [] | [] | [] |

## Arm (iii), replays

completed 26/26; regressions K [] S [] G []; shipped warning fired on ['III--seeds_data__seeds_centered_model--731401', 'III--seeds_data__seeds_centered_model--731402', 'III--radon_all__radon_hierarchical_intercept_centered--731401', 'III--bball_drive_event_0__hmm_drive_0--731401', 'III--arma__arma11--731401', 'III--hudson_lynx_hare__lotka_volterra--97464', 'III--hudson_lynx_hare__lotka_volterra--97467', 'III--hudson_lynx_hare__lotka_volterra--5701103', 'III--hudson_lynx_hare__lotka_volterra--5701106']; source studies recorded it on ['III--seeds_data__seeds_centered_model--731401', 'III--seeds_data__seeds_centered_model--731403', 'III--bball_drive_event_0__hmm_drive_0--731401', 'III--arma__arma11--731401', 'III--hudson_lynx_hare__lotka_volterra--97467', 'III--hudson_lynx_hare__lotka_volterra--5701103', 'III--hudson_lynx_hare__lotka_volterra--5701106']

| cell | status | recorded (source) | current | K | S | G | off | passed | hash reproduced |
|---|---|---|---|---|---|---|---|---|---|
| III--funnel10--731401 | ok | [] | [] | [] | [] | [] | None | None | - |
| III--funnel10--731402 | ok | [] | [] | [] | [] | [] | None | None | - |
| III--funnel10--731403 | ok | [] | [] | [] | [] | [] | None | None | - |
| III--eight_schools__eight_schools_centered--731401 | ok | [] | [] | [] | [] | [] | [] | False | - |
| III--eight_schools__eight_schools_centered--731402 | ok | [] | [] | [3] | [] | [] | [] | False | - |
| III--eight_schools__eight_schools_centered--731403 | ok | [] | [] | [] | [] | [] | [] | False | - |
| III--seeds_data__seeds_centered_model--731401 | ok | [2, 3] | [2] | [2] | [] | [] | None | None | - |
| III--seeds_data__seeds_centered_model--731402 | ok | [] | [1] | [1] | [] | [] | None | None | - |
| III--seeds_data__seeds_centered_model--731403 | ok | [0] | [] | [] | [] | [] | None | None | - |
| III--radon_all__radon_hierarchical_intercept_centered--731401 | ok | [] | [0] | [0, 1] | [] | [] | None | None | - |
| III--radon_all__radon_hierarchical_intercept_centered--731402 | ok | [] | [] | [] | [] | [] | None | None | - |
| III--radon_all__radon_hierarchical_intercept_centered--731403 | ok | [] | [] | [] | [] | [] | None | None | - |
| III--bball_drive_event_0__hmm_drive_0--731401 | ok | [3] | [3] | [3] | [] | [3] | [3] | False | - |
| III--arma__arma11--731401 | ok | [1] | [1] | [] | [] | [1] | [] | True | - |
| III--bball_drive_event_0__hmm_drive_0--97464 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--bball_drive_event_0__hmm_drive_0--97465 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--bball_drive_event_0__hmm_drive_0--97466 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--bball_drive_event_0__hmm_drive_0--97467 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--bball_drive_event_0__hmm_drive_0--97468 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--hudson_lynx_hare__lotka_volterra--97464 | ok | timeout | [2] | [2] | [] | [2] | [2] | False | - |
| III--hudson_lynx_hare__lotka_volterra--97465 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--hudson_lynx_hare__lotka_volterra--97466 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--hudson_lynx_hare__lotka_volterra--97467 | ok | [3] | [3] | [3] | [] | [3] | [3] | False | - |
| III--hudson_lynx_hare__lotka_volterra--97468 | ok | [] | [] | [] | [] | [] | [] | True | - |
| III--hudson_lynx_hare__lotka_volterra--5701103 | ok | [3] | [3] | [3] | [] | [3] | [3] | False | True |
| III--hudson_lynx_hare__lotka_volterra--5701106 | ok | [2] | [2] | [2] | [] | [2] | [2] | False | True |

## Replay hashes

- III--hudson_lynx_hare__lotka_volterra--5701103: expected 30343a96953b3d92, observed 30343a96953b3d92, equal True
- III--hudson_lynx_hare__lotka_volterra--5701106: expected 9765a46b67fab6f1, observed 9765a46b67fab6f1, equal True
- IV--two_mode--6903201: expected 4c5334d2ea52c7c7, observed 4c5334d2ea52c7c7, equal True
- IV--two_mode--6903202: expected a731b2e46c6dfb90, observed a731b2e46c6dfb90, equal True
- IV--two_mode--6903203: expected 4a74aa1e9c9f0614, observed 4a74aa1e9c9f0614, equal True
- IV--two_mode--6903204: expected e0b02ace10afe407, observed e0b02ace10afe407, equal True
- IV--two_mode--6903205: expected 06bb3cb679e3fcc9, observed 06bb3cb679e3fcc9, equal True
- IV--two_mode--6903206: expected 0e540698dc76c1c4, observed 0e540698dc76c1c4, equal True
- IV--bball_drive_event_0__hmm_drive_0--6903102: expected 83818c96ba4f4f4d, observed 83818c96ba4f4f4d, equal True
