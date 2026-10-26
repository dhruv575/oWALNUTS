# WP64 Linux reproduction of E26 / E28 — comparison with the Windows record

| block | arm | Linux passes | Windows passes | same pass/fail cells | bit-identical / comparable | Linux/Windows wall per gradient |
|---|---|---:|---:|---:|---:|---:|
| v7_house | owalnuts | 44/51 | 43/51 | 48 | 0/51 | 0.200 |
| v7_house | cmdstan | 33/51 | 34/51 | 46 | 0/50 | 0.391 |
| v7_house | nutpie | 27/51 | 26/51 | 48 | 0/48 | 0.162 |
| v7_new | owalnuts | 7/15 | 6/15 | 14 | 0/15 | 0.218 |
| v7_new | cmdstan | 5/15 | 7/15 | 13 | 0/15 | 0.528 |
| v7_new | nutpie | 5/15 | 3/15 | 13 | 0/15 | 0.165 |
| v7_all | owalnuts | 51/66 | 49/66 | 62 | 0/66 | 0.204 |
| v7_all | cmdstan | 38/66 | 41/66 | 59 | 0/65 | 0.419 |
| v7_all | nutpie | 32/66 | 29/66 | 61 | 0/63 | 0.162 |
| ext | owalnuts | 41/48 | 40/48 | 45 | 0/48 | 0.233 |
| ext | cmdstan | 31/48 | 30/48 | 43 | 0/47 | 0.749 |
| dense | owalnuts-dense | 18/18 | 18/18 | 18 | 0/18 | 0.219 |

## Differing cells

- v7_house owalnuts: gp_pois_regr-gp_pois_regr/560561: linux False (ok) windows True (ok)
- v7_house owalnuts: one_comp_mm_elim_abs-one_comp_mm_elim_abs/560561: linux True (ok) windows False (ok)
- v7_house owalnuts: mcycle_gp-accel_gp/560561: linux True (ok) windows False (ok)
- v7_house cmdstan: eight_schools-eight_schools_noncentered/560562: linux False (ok) windows True (ok)
- v7_house cmdstan: bball_drive_event_0-hmm_drive_0/560561: linux True (ok) windows False (ok)
- v7_house cmdstan: bball_drive_event_0-hmm_drive_0/560562: linux False (ok) windows True (ok)
- v7_house cmdstan: bball_drive_event_0-hmm_drive_0/560563: linux False (ok) windows True (ok)
- v7_house cmdstan: hudson_lynx_hare-lotka_volterra/560563: linux True (ok) windows False (ok)
- v7_house nutpie: diamonds-diamonds/560562: linux True (ok) windows False (ok)
- v7_house nutpie: earnings-logearn_interaction/560561: linux True (ok) windows False (ok)
- v7_house nutpie: earnings-logearn_interaction/560563: linux False (ok) windows True (ok)
- v7_new owalnuts: seeds_data-seeds_centered_model/560562: linux True (ok) windows False (ok)
- v7_new cmdstan: science_irt-grsm_latent_reg_irt/560561: linux False (ok) windows True (ok)
- v7_new cmdstan: science_irt-grsm_latent_reg_irt/560562: linux False (ok) windows True (ok)
- v7_new nutpie: seeds_data-seeds_centered_model/560563: linux True (ok) windows False (ok)
- v7_new nutpie: kilpisjarvi_mod-kilpisjarvi/560561: linux True (ok) windows False (ok)
- v7_all owalnuts: gp_pois_regr-gp_pois_regr/560561: linux False (ok) windows True (ok)
- v7_all owalnuts: one_comp_mm_elim_abs-one_comp_mm_elim_abs/560561: linux True (ok) windows False (ok)
- v7_all owalnuts: mcycle_gp-accel_gp/560561: linux True (ok) windows False (ok)
- v7_all owalnuts: seeds_data-seeds_centered_model/560562: linux True (ok) windows False (ok)
- v7_all cmdstan: eight_schools-eight_schools_noncentered/560562: linux False (ok) windows True (ok)
- v7_all cmdstan: bball_drive_event_0-hmm_drive_0/560561: linux True (ok) windows False (ok)
- v7_all cmdstan: bball_drive_event_0-hmm_drive_0/560562: linux False (ok) windows True (ok)
- v7_all cmdstan: bball_drive_event_0-hmm_drive_0/560563: linux False (ok) windows True (ok)
- v7_all cmdstan: hudson_lynx_hare-lotka_volterra/560563: linux True (ok) windows False (ok)
- v7_all cmdstan: science_irt-grsm_latent_reg_irt/560561: linux False (ok) windows True (ok)
- v7_all cmdstan: science_irt-grsm_latent_reg_irt/560562: linux False (ok) windows True (ok)
- v7_all nutpie: diamonds-diamonds/560562: linux True (ok) windows False (ok)
- v7_all nutpie: earnings-logearn_interaction/560561: linux True (ok) windows False (ok)
- v7_all nutpie: earnings-logearn_interaction/560563: linux False (ok) windows True (ok)
- v7_all nutpie: seeds_data-seeds_centered_model/560563: linux True (ok) windows False (ok)
- v7_all nutpie: kilpisjarvi_mod-kilpisjarvi/560561: linux True (ok) windows False (ok)
- ext owalnuts: one_comp_mm_elim_abs-one_comp_mm_elim_abs/620601: linux True (ok) windows False (ok)
- ext owalnuts: one_comp_mm_elim_abs-one_comp_mm_elim_abs/620602: linux False (ok) windows True (ok)
- ext owalnuts: one_comp_mm_elim_abs-one_comp_mm_elim_abs/620603: linux True (ok) windows False (ok)
- ext cmdstan: eight_schools-eight_schools_noncentered/620602: linux True (ok) windows False (ok)
- ext cmdstan: eight_schools-eight_schools_noncentered/620603: linux True (ok) windows False (ok)
- ext cmdstan: bball_drive_event_0-hmm_drive_0/620601: linux False (ok) windows True (ok)
- ext cmdstan: bball_drive_event_0-hmm_drive_0/620602: linux False (ok) windows True (ok)
- ext cmdstan: bball_drive_event_0-hmm_drive_0/620603: linux True (ok) windows False (ok)

## Head-to-head (v7 statistics)

| statistic | Linux | Windows |
|---|---:|---:|
| all22_bulk_ess_per_gradient_vs_cmdstan | 1.065 (21) | 0.734 (21) |
| all22_bulk_ess_per_gradient_vs_nutpie | 0.837 (0) | 0.645 (0) |
| fixed16_bulk_ess_per_gradient_vs_cmdstan | 1.154 (15) | 0.708 (15) |
| fixed16_bulk_ess_per_second_vs_cmdstan | 1.215 (15) | 0.398 (15) |
| fixed16_wall_per_gradient_vs_cmdstan | 0.942 (15) | 1.849 (15) |
| house17_bulk_ess_per_gradient_vs_cmdstan | 1.165 (16) | 0.735 (16) |
| house17_bulk_ess_per_second_vs_nutpie | 1.454 (16) | 1.226 (16) |

## Extension statistics

| statistic | Linux | Windows |
|---|---|---|
| new_three | 1.2757752278920511 | 0.8098263181717908 |
| v7_three_recomputed | 1.153914935783606 | 0.707988142248859 |
| pooled_six | 1.205615012837121 | 0.7613877400739644 |
| seed_interval | [1.158823416398581, 1.2654423385472018] | [0.7395442451043893, 0.8215784816469415] |
| jackknife_se_pooled_geomean | 0.0897320335882217 | 0.07135608680001017 |

## Funnel

| seed | Linux z | Windows z | bit-identical | Linux wall s | Windows wall s |
|---|---:|---:|---|---:|---:|
| 560571 | +0.29 | +1.69 | False | 0.40 | 0.54 |
| 560572 | -0.53 | -0.59 | False | 0.35 | 1.28 |
| 560573 | +0.55 | +0.84 | False | 1.12 | 0.71 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| L1_owalnuts_pass_counts_reproduce_exactly | {'house': 44, 'new': 7, 'ext': 41} | False |
| L2_competitor_pass_counts_within_tolerance | {'cmdstan_house': {'linux': 33, 'windows': 34, 'held': True}, 'cmdstan_new': {'linux': 5, 'windows': 7, 'held': True}, 'cmdstan_ext': {'linux': 31, 'windows': 30, 'held': True}, 'nutpie_house': {'linux': 27, 'windows': 26, 'held': True}, 'nutpie_new': {'linux': 5, 'windows': 3, 'held': True}} | True |
| L3_linux_pooled_six_seed_fixed16_ess_per_gradient_in_interval | 1.205615012837121 | False |
| L4_linux_fixed16_wall_per_gradient_vs_cmdstan_le_1 | 0.9415710241885838 | None |
| R1_bit_identity_reported | {'owalnuts_bit_identical_cells': 0, 'owalnuts_comparable_cells': 114, 'funnel_bit_identical_seeds': 0} | reported |
