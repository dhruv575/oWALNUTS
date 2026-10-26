# WP65 part (c): wall per gradient on Linux, fixed-16, one seed

Seed 652651; 4 chains x 1,000/1,000; every process pinned to cores 4-7 on a shared box with three other lanes active (pinned, co-tenanted walls). `wall/grad` = wall seconds around the sampler call (oWALNUTS start search excluded, CmdStan process launch and CSV I/O included, as v7) divided by all gradients including warmup. `gates` = rank R-hat <= 1.01, bulk/tail ESS >= 400, zero retained divergences.

| model | arm | execution | gates | wall s | grads | wall/grad us | min bulk ESS | bulk ESS/grad x1e3 | max abs z |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | cmdstan | cmdstan | 1/1 | 0.06 | 81,388 | 0.723 | 2,597 | 31.912 | 2.06 |
| eight_schools-eight_schools_noncentered | owalnuts | ReplicatedConcurrent | 1/1 | 0.04 | 68,806 | 0.557 | 2,055 | 29.864 | 1.40 |
| eight_schools-eight_schools_noncentered | owalnuts-serialised | DirectSerialised | 1/1 | 0.10 | 68,806 | 1.492 | 2,055 | 29.864 | 1.40 |
| eight_schools-eight_schools_noncentered | owalnuts-threaded | DirectConcurrent | 1/1 | 0.04 | 68,806 | 0.644 | 2,055 | 29.864 | 1.40 |
| eight_schools-eight_schools_centered | cmdstan | cmdstan | 0/1 | 0.08 | 173,922 | 0.444 | 13 | 0.076 | 2.65 |
| eight_schools-eight_schools_centered | owalnuts | ReplicatedConcurrent | 0/1 | 0.09 | 219,621 | 0.419 | 144 | 0.654 | 1.87 |
| eight_schools-eight_schools_centered | owalnuts-serialised | DirectSerialised | 0/1 | 0.27 | 219,621 | 1.211 | 144 | 0.654 | 1.87 |
| eight_schools-eight_schools_centered | owalnuts-threaded | DirectConcurrent | 0/1 | 0.10 | 219,621 | 0.434 | 144 | 0.654 | 1.87 |
| diamonds-diamonds | cmdstan | cmdstan | 1/1 | 63.91 | 6,307,746 | 10.132 | 1,417 | 0.225 | 1.63 |
| diamonds-diamonds | owalnuts | ReplicatedConcurrent | 1/1 | 69.51 | 6,732,385 | 10.325 | 1,172 | 0.174 | 1.87 |
| diamonds-diamonds | owalnuts-serialised | DirectSerialised | 1/1 | 277.71 | 6,732,385 | 41.250 | 1,172 | 0.174 | 1.87 |
| diamonds-diamonds | owalnuts-threaded | DirectConcurrent | 1/1 | 67.85 | 6,732,385 | 10.079 | 1,172 | 0.174 | 1.87 |
| earnings-logearn_interaction | cmdstan | cmdstan | 1/1 | 11.02 | 1,354,869 | 8.133 | 1,117 | 0.824 | 0.64 |
| earnings-logearn_interaction | owalnuts | ReplicatedConcurrent | 1/1 | 15.86 | 1,553,876 | 10.209 | 1,199 | 0.771 | 0.97 |
| earnings-logearn_interaction | owalnuts-serialised | DirectSerialised | 1/1 | 48.80 | 1,553,876 | 31.405 | 1,199 | 0.771 | 0.97 |
| earnings-logearn_interaction | owalnuts-threaded | DirectConcurrent | 1/1 | 22.27 | 1,553,876 | 14.335 | 1,199 | 0.771 | 0.97 |
| mesquite-logmesquite_logvash | cmdstan | cmdstan | 1/1 | 0.27 | 366,733 | 0.738 | 1,492 | 4.069 | 0.60 |
| mesquite-logmesquite_logvash | owalnuts | ReplicatedConcurrent | 1/1 | 0.26 | 352,636 | 0.732 | 1,211 | 3.435 | 1.61 |
| mesquite-logmesquite_logvash | owalnuts-serialised | DirectSerialised | 1/1 | 1.12 | 352,636 | 3.184 | 1,211 | 3.435 | 1.61 |
| mesquite-logmesquite_logvash | owalnuts-threaded | DirectConcurrent | 1/1 | 0.33 | 352,636 | 0.943 | 1,211 | 3.435 | 1.61 |
| kidiq-kidscore_momhsiq | cmdstan | cmdstan | 1/1 | 0.96 | 373,305 | 2.577 | 1,221 | 3.272 | 2.73 |
| kidiq-kidscore_momhsiq | owalnuts | ReplicatedConcurrent | 1/1 | 0.89 | 347,446 | 2.547 | 1,546 | 4.449 | 1.33 |
| kidiq-kidscore_momhsiq | owalnuts-serialised | DirectSerialised | 1/1 | 3.54 | 347,446 | 10.184 | 1,546 | 4.449 | 1.33 |
| kidiq-kidscore_momhsiq | owalnuts-threaded | DirectConcurrent | 1/1 | 1.17 | 347,446 | 3.357 | 1,546 | 4.449 | 1.33 |
| sblrc-blr | cmdstan | cmdstan | 1/1 | 0.09 | 128,953 | 0.690 | 842 | 6.527 | 1.67 |
| sblrc-blr | owalnuts | ReplicatedConcurrent | 0/1 | 0.09 | 145,275 | 0.647 | 653 | 4.498 | 1.37 |
| sblrc-blr | owalnuts-serialised | DirectSerialised | 0/1 | 0.35 | 145,275 | 2.435 | 653 | 4.498 | 1.37 |
| sblrc-blr | owalnuts-threaded | DirectConcurrent | 0/1 | 0.10 | 145,275 | 0.711 | 653 | 4.498 | 1.37 |
| nes2000-nes | cmdstan | cmdstan | 1/1 | 2.98 | 396,817 | 7.498 | 2,052 | 5.170 | 1.60 |
| nes2000-nes | owalnuts | ReplicatedConcurrent | 1/1 | 3.16 | 433,097 | 7.305 | 1,886 | 4.355 | 1.35 |
| nes2000-nes | owalnuts-serialised | DirectSerialised | 1/1 | 12.73 | 433,097 | 29.386 | 1,886 | 4.355 | 1.35 |
| nes2000-nes | owalnuts-threaded | DirectConcurrent | 1/1 | 4.65 | 433,097 | 10.728 | 1,886 | 4.355 | 1.35 |
| arK-arK | cmdstan | cmdstan | 1/1 | 1.33 | 244,013 | 5.439 | 2,461 | 10.084 | 1.95 |
| arK-arK | owalnuts | ReplicatedConcurrent | 1/1 | 1.43 | 270,155 | 5.294 | 2,332 | 8.633 | 1.27 |
| arK-arK | owalnuts-serialised | DirectSerialised | 1/1 | 5.88 | 270,155 | 21.768 | 2,332 | 8.633 | 1.27 |
| arK-arK | owalnuts-threaded | DirectConcurrent | 1/1 | 2.32 | 270,155 | 8.582 | 2,332 | 8.633 | 1.27 |
| garch-garch11 | cmdstan | cmdstan | 1/1 | 0.38 | 91,617 | 4.119 | 1,853 | 20.221 | 1.54 |
| garch-garch11 | owalnuts | ReplicatedConcurrent | 1/1 | 0.33 | 93,998 | 3.542 | 1,766 | 18.786 | 1.50 |
| garch-garch11 | owalnuts-serialised | DirectSerialised | 1/1 | 1.40 | 93,998 | 14.890 | 1,766 | 18.786 | 1.50 |
| garch-garch11 | owalnuts-threaded | DirectConcurrent | 1/1 | 0.49 | 93,998 | 5.211 | 1,766 | 18.786 | 1.50 |
| gp_pois_regr-gp_pois_regr | cmdstan | cmdstan | 0/1 | 1.65 | 1,208,387 | 1.363 | 1,293 | 1.070 | 1.53 |
| gp_pois_regr-gp_pois_regr | owalnuts | ReplicatedConcurrent | 1/1 | 1.62 | 1,194,984 | 1.353 | 788 | 0.659 | 1.46 |
| gp_pois_regr-gp_pois_regr | owalnuts-serialised | DirectSerialised | 1/1 | 6.41 | 1,194,984 | 5.361 | 788 | 0.659 | 1.46 |
| gp_pois_regr-gp_pois_regr | owalnuts-threaded | DirectConcurrent | 1/1 | 1.97 | 1,194,984 | 1.652 | 788 | 0.659 | 1.46 |
| hmm_example-hmm_example | cmdstan | cmdstan | 1/1 | 1.34 | 100,380 | 13.388 | 2,412 | 24.025 | 0.86 |
| hmm_example-hmm_example | owalnuts | ReplicatedConcurrent | 1/1 | 1.37 | 117,025 | 11.721 | 2,173 | 18.567 | 1.15 |
| hmm_example-hmm_example | owalnuts-serialised | DirectSerialised | 1/1 | 5.46 | 117,025 | 46.658 | 2,173 | 18.567 | 1.15 |
| hmm_example-hmm_example | owalnuts-threaded | DirectConcurrent | 1/1 | 1.66 | 117,025 | 14.145 | 2,173 | 18.567 | 1.15 |
| bball_drive_event_0-hmm_drive_0 | cmdstan | cmdstan | 1/1 | 6.12 | 66,544 | 91.924 | 4,370 | 65.665 | 0.92 |
| bball_drive_event_0-hmm_drive_0 | owalnuts | ReplicatedConcurrent | 1/1 | 10.17 | 106,883 | 95.154 | 3,069 | 28.716 | 1.48 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-serialised | DirectSerialised | 1/1 | 23.31 | 106,883 | 218.070 | 3,069 | 28.716 | 1.48 |
| bball_drive_event_0-hmm_drive_0 | owalnuts-threaded | DirectConcurrent | 1/1 | 12.60 | 106,883 | 117.906 | 3,069 | 28.716 | 1.48 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | cmdstan | cmdstan | 0/1 | 14.35 | 68,587 | 209.288 | 1,201 | 17.506 | 4.41 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts | ReplicatedConcurrent | 1/1 | 13.14 | 76,504 | 171.762 | 1,168 | 15.266 | 4.69 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-serialised | DirectSerialised | 1/1 | 50.02 | 76,504 | 653.794 | 1,168 | 15.266 | 4.69 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | owalnuts-threaded | DirectConcurrent | 1/1 | 13.83 | 76,504 | 180.814 | 1,168 | 15.266 | 4.69 |
| hudson_lynx_hare-lotka_volterra | cmdstan | cmdstan | 1/1 | 6.38 | 262,107 | 24.353 | 903 | 3.445 | 1.38 |
| hudson_lynx_hare-lotka_volterra | owalnuts | ReplicatedConcurrent | 1/1 | 6.14 | 280,025 | 21.935 | 1,007 | 3.596 | 1.30 |
| hudson_lynx_hare-lotka_volterra | owalnuts-serialised | DirectSerialised | 1/1 | 22.97 | 280,025 | 82.026 | 1,007 | 3.596 | 1.30 |
| hudson_lynx_hare-lotka_volterra | owalnuts-threaded | DirectConcurrent | 1/1 | 7.58 | 280,025 | 27.085 | 1,007 | 3.596 | 1.30 |
| mcycle_gp-accel_gp | cmdstan | cmdstan | 0/1 | 24.78 | 6,027,979 | 4.112 | 2,012 | 0.334 | 2.80 |
| mcycle_gp-accel_gp | owalnuts | ReplicatedConcurrent | 0/1 | 13.03 | 2,855,922 | 4.562 | 641 | 0.224 | 3.04 |
| mcycle_gp-accel_gp | owalnuts-serialised | DirectSerialised | 0/1 | 48.45 | 2,855,922 | 16.964 | 641 | 0.224 | 3.04 |
| mcycle_gp-accel_gp | owalnuts-threaded | DirectConcurrent | 0/1 | 17.83 | 2,855,922 | 6.244 | 641 | 0.224 | 3.04 |

## Wall per gradient, geometric mean over models complete on both sides

| ratio | models | geomean |
|---|---:|---:|
| owalnuts_over_cmdstan | 16 | 0.959 |
| owalnuts-serialised_over_cmdstan | 16 | 3.462 |
| owalnuts-threaded_over_cmdstan | 16 | 1.198 |
| owalnuts-serialised_over_owalnuts | 16 | 3.609 |
| owalnuts-threaded_over_owalnuts | 16 | 1.248 |

| per model | owalnuts_over_cmdstan | owalnuts-serialised_over_cmdstan | owalnuts-threaded_over_cmdstan | owalnuts-serialised_over_owalnuts | owalnuts-threaded_over_owalnuts |
|---|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 0.771 | 2.065 | 0.892 | 2.678 | 1.157 |
| eight_schools-eight_schools_centered | 0.943 | 2.726 | 0.976 | 2.891 | 1.035 |
| diamonds-diamonds | 1.019 | 4.071 | 0.995 | 3.995 | 0.976 |
| earnings-logearn_interaction | 1.255 | 3.861 | 1.763 | 3.076 | 1.404 |
| mesquite-logmesquite_logvash | 0.993 | 4.317 | 1.279 | 4.349 | 1.288 |
| kidiq-kidscore_momhsiq | 0.988 | 3.952 | 1.303 | 3.998 | 1.318 |
| sblrc-blr | 0.939 | 3.530 | 1.031 | 3.761 | 1.098 |
| nes2000-nes | 0.974 | 3.919 | 1.431 | 4.023 | 1.469 |
| arK-arK | 0.973 | 4.002 | 1.578 | 4.112 | 1.621 |
| garch-garch11 | 0.860 | 3.615 | 1.265 | 4.204 | 1.471 |
| gp_pois_regr-gp_pois_regr | 0.993 | 3.934 | 1.212 | 3.961 | 1.221 |
| hmm_example-hmm_example | 0.875 | 3.485 | 1.057 | 3.981 | 1.207 |
| bball_drive_event_0-hmm_drive_0 | 1.035 | 2.372 | 1.283 | 2.292 | 1.239 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.821 | 3.124 | 0.864 | 3.806 | 1.053 |
| hudson_lynx_hare-lotka_volterra | 0.901 | 3.368 | 1.112 | 3.740 | 1.235 |
| mcycle_gp-accel_gp | 1.110 | 4.126 | 1.519 | 3.719 | 1.369 |

## Preregistered predictions

| prediction | value | held |
|---|---|---|
| C1_replicated_over_cmdstan_wall_per_gradient_le | 0.959 | True |
| C2_serialised_over_cmdstan_wall_per_gradient_ge | 3.462 | True |
| C3_serialised_over_replicated_in_range | 3.609 | True |
| C4_replicated_serialised_bit_identical_every_model | 16/16 identical | True |
| C5_no_owalnuts_error_any_arm | {'owalnuts': [], 'owalnuts-serialised': [], 'owalnuts-threaded': []} | True |
| C6_threaded_over_replicated_wall_per_gradient_le | 1.248 | True |
| reported_threaded_bit_identical_to_replicated | 16/16 identical | reported |
| reported_bulk_ess_per_gradient_vs_cmdstan | {'owalnuts_over_cmdstan': 0.9438528159105326, 'owalnuts-serialised_over_cmdstan': 0.9438528159105326, 'owalnuts-threaded_over_cmdstan': 0.9438528159105326} | reported |
| reported_pass_counts_of_16 | {'cmdstan': {'passed': 12, 'recorded': 16, 'ok': 16}, 'owalnuts': {'passed': 13, 'recorded': 16, 'ok': 16}, 'owalnuts-serialised': {'passed': 13, 'recorded': 16, 'ok': 16}, 'owalnuts-threaded': {'passed': 13, 'recorded': 16, 'ok': 16}} | reported |
