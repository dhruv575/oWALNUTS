# WP73 results

Seeds [730731, 730732, 730733]; 4 chains x 1,000/1,000 (`half`: 500/1,000); funnel 2000/20000 x 10 seeds; pinned to cores 4-7, co-tenanted.

## Descriptive arm: warmup share of all gradients (seed medians)

| model | oWALNUTS | CmdStan | nutpie | oW - Cmd | oW - nutpie | oW passes | Cmd passes | nutpie passes | ESS/grad oW/Cmd | oW/nutpie |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 0.512 | 0.508 | 0.520 | +0.003 | -0.008 | 3/3 | 1/3 | 1/3 | 0.908 | 0.685 |
| eight_schools-eight_schools_centered | 0.246 | 0.605 | 0.518 | -0.360 | -0.272 | 0/3 | 0/3 | 0/3 | 0.210 | 0.351 |
| diamonds-diamonds | 0.417 | 0.399 | 0.516 | +0.019 | -0.099 | 3/3 | 3/3 | 1/3 | 0.890 | 1.078 |
| earnings-logearn_interaction | 0.523 | 0.487 | 0.499 | +0.036 | +0.024 | 3/3 | 3/3 | 2/3 | 0.890 | 0.846 |
| mesquite-logmesquite_logvash | 0.482 | 0.475 | 0.519 | +0.007 | -0.038 | 3/3 | 3/3 | 2/3 | 0.975 | 0.910 |
| kidiq-kidscore_momhsiq | 0.628 | 0.643 | 0.516 | -0.014 | +0.112 | 3/3 | 3/3 | 3/3 | 0.903 | 0.625 |
| sblrc-blr | 0.604 | 0.538 | 0.531 | +0.066 | +0.073 | 3/3 | 3/3 | 3/3 | 0.877 | 0.331 |
| nes2000-nes | 0.537 | 0.499 | 0.528 | +0.038 | +0.009 | 3/3 | 3/3 | 3/3 | 0.909 | 0.765 |
| arK-arK | 0.519 | 0.509 | 0.523 | +0.010 | -0.004 | 3/3 | 3/3 | 3/3 | 0.780 | 0.712 |
| arma-arma11 | 0.587 | 0.526 | 0.467 | +0.061 | +0.121 | 3/3 | 2/3 | 2/3 | 1.189 | 5.802 |
| garch-garch11 | 0.530 | 0.498 | 0.532 | +0.031 | -0.002 | 3/3 | 3/3 | 3/3 | 0.913 | 0.805 |
| gp_pois_regr-gp_pois_regr | 0.544 | 0.480 | 0.537 | +0.064 | +0.007 | 3/3 | 0/3 | 0/3 | 0.761 | 0.919 |
| hmm_example-hmm_example | 0.590 | 0.541 | 0.526 | +0.048 | +0.064 | 3/3 | 3/3 | 3/3 | 0.832 | 0.661 |
| bball_drive_event_0-hmm_drive_0 | 0.665 | 0.679 | 0.545 | -0.014 | +0.121 | 1/3 | 1/3 | 2/3 | 1.974 | 0.004 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 0.521 | 0.523 | 0.531 | -0.002 | -0.010 | 1/3 | 0/3 | 0/3 | 0.487 | 0.650 |
| hudson_lynx_hare-lotka_volterra | 0.524 | 0.485 | 0.507 | +0.039 | +0.017 | 2/3 | 3/3 | 2/3 | 0.920 | — |
| mcycle_gp-accel_gp | 0.517 | 0.448 | 0.524 | +0.069 | -0.007 | 0/3 | 0/3 | 0/3 | 0.465 | 0.840 |

## Gradients per transition by warmup phase (seed medians), oWALNUTS / CmdStan

| model | initial fast | w0 | w1 | w2 | w3 | w4 | terminal | sampling | oW initial | Cmd initial | nutpie metric-adapting | nutpie step-only | nutpie last metric change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 1.02 | 0.87 | 0.97 | 1.03 | 0.89 | 1.05 | 0.95 | 0.94 | 13 | 12 | 7.4 | 6.6 | 849 |
| eight_schools-eight_schools_centered | 0.82 | 1.17 | 0.60 | 0.91 | 0.85 | 0.99 | 1.08 | 4.16 | 64 | 78 | 13.4 | 14.0 | 849 |
| diamonds-diamonds | 2.58 | 1.18 | 1.04 | 1.06 | 1.05 | 1.04 | 1.05 | 0.98 | 319 | 124 | 264.2 | 265.1 | 849 |
| earnings-logearn_interaction | 0.81 | 0.34 | 0.86 | 1.29 | 1.52 | 1.19 | 1.13 | 1.06 | 98 | 121 | 91.6 | 92.9 | 849 |
| mesquite-logmesquite_logvash | 1.15 | 0.97 | 1.06 | 1.01 | 1.12 | 1.09 | 0.99 | 1.06 | 46 | 41 | 25.8 | 23.5 | 849 |
| kidiq-kidscore_momhsiq | 0.95 | 0.93 | 1.80 | 1.13 | 0.99 | 1.07 | 1.01 | 1.09 | 229 | 240 | 18.3 | 17.0 | 849 |
| sblrc-blr | 7.09 | 0.61 | 2.27 | 0.73 | 0.98 | 1.10 | 1.04 | 1.08 | 85 | 12 | 7.6 | 6.7 | 849 |
| nes2000-nes | 1.56 | 1.00 | 1.22 | 1.01 | 1.02 | 1.13 | 0.98 | 0.99 | 127 | 81 | 32.2 | 28.1 | 849 |
| arK-arK | 2.60 | 1.08 | 1.35 | 1.00 | 1.04 | 1.10 | 1.02 | 1.14 | 74 | 29 | 23.0 | 21.0 | 849 |
| arma-arma11 | 4.13 | 1.39 | 2.06 | 0.64 | 0.22 | 0.49 | 0.95 | 1.00 | 30 | 7 | 6.3 | 6.3 | 849 |
| garch-garch11 | 1.24 | 1.00 | 0.88 | 1.11 | 1.06 | 1.09 | 0.89 | 0.96 | 21 | 17 | 8.4 | 7.1 | 849 |
| gp_pois_regr-gp_pois_regr | 1.14 | 0.93 | 0.89 | 0.83 | 1.00 | 0.99 | 0.84 | 0.76 | 284 | 249 | 109.3 | 96.4 | 849 |
| hmm_example-hmm_example | 1.60 | 1.10 | 1.37 | 0.98 | 1.09 | 1.20 | 1.05 | 1.04 | 67 | 42 | 7.6 | 6.6 | 849 |
| bball_drive_event_0-hmm_drive_0 | 2.40 | 0.97 | 1.35 | 0.97 | 0.77 | 1.01 | 0.89 | 1.07 | 83 | 35 | 6.2 | 4.5 | 849 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1.03 | 0.97 | 0.83 | 1.01 | 1.13 | 1.19 | 0.90 | 1.10 | 18 | 18 | 6.8 | 6.3 | 849 |
| hudson_lynx_hare-lotka_volterra | 1.76 | 1.19 | 1.42 | 0.95 | 0.99 | 1.07 | 0.91 | 0.91 | 53 | 30 | 19.2 | 19.0 | 849 |
| mcycle_gp-accel_gp | 0.60 | 0.36 | 0.61 | 0.54 | 0.50 | 0.52 | 0.60 | 0.40 | 306 | 508 | 468.6 | 452.0 | 849 |

## Predictions

```
{
 "P1_median_share_diff_vs_cmdstan": {
  "value": 0.03135047532778956,
  "interval": [
   0.0,
   0.05
  ],
  "models": 17,
  "held": true
 },
 "P2_wp58_overlap_share_diff_vs_cmdstan": {
  "value": {
   "eight_schools-eight_schools_noncentered": {
    "vs_cmdstan": 0.003395093552022166,
    "vs_nutpie": -0.00842891768575127
   },
   "gp_pois_regr-gp_pois_regr": {
    "vs_cmdstan": 0.06402086626549275,
    "vs_nutpie": 0.00740534014048444
   },
   "hudson_lynx_hare-lotka_volterra": {
    "vs_cmdstan": 0.039192369946092875,
    "vs_nutpie": 0.01720192445261315
   }
  },
  "interval": [
   0.0,
   0.05
  ],
  "held": false
 },
 "P3_initial_fast_per_transition_ratio": {
  "value": 1.2359328726554788,
  "threshold": 1.5,
  "held": false
 },
 "P4_slow_window_per_transition_ratio": {
  "value": 1.0123142501924103,
  "interval": [
   1.0,
   1.3
  ],
  "held": true
 },
 "phase_ratio_medians": {
  "initial_fast": 1.2359328726554788,
  "window_0": 0.975,
  "window_1": 1.0608075551700877,
  "window_2": 1.0033464280517967,
  "window_3": 0.9998053038476827,
  "window_4": 1.0712091954022989,
  "terminal_fast": 0.9788683199441145,
  "sampling": 1.0354060243086138
 }
}
```

## Candidates against the frozen rule

Default passes 40/51 (CmdStan 34, nutpie 30).

| candidate | R1 passes vs default | R2 geomean ESS / total gradient vs default | R3 funnel P5 ± s.e. | R4 fingerprint | rule | warmup grads vs default | total grads vs default | min ESS vs default | early-stopped chains |
|---|---|---|---|---|---|---:|---:|---:|---:|
| owalnuts-init25 | 43 vs 40 (True) | 1.440 over 17 (True) | 0.0463 ± 0.0017 (True) | True | **True** | 0.985 | 0.995 | 1.015 | 0 |
| owalnuts-half | 40 vs 40 (True) | 1.315 over 17 (True) | 0.0499 ± 0.0032 (True) | True | **True** | 0.578 | 0.796 | 1.025 | 0 |
| owalnuts-stablestop | 40 vs 40 (True) | 1.124 over 17 (True) | 0.0477 ± 0.0015 (True) | True | **True** | 0.836 | 0.904 | 1.000 | 68 |

## Per-model ESS per total gradient vs default (seed medians) and passes

| model | default passes | owalnuts-init25 ratio | owalnuts-init25 passes | owalnuts-half ratio | owalnuts-half passes | owalnuts-stablestop ratio | owalnuts-stablestop passes |
|---|---:|---:|---:|---:|---:|---:|---:|
| eight_schools-eight_schools_noncentered | 3/3 | 1.004 | 3/3 | 1.356 | 3/3 | 1.161 | 3/3 |
| eight_schools-eight_schools_centered | 0/3 | 2.415 | 0/3 | 5.056 | 0/3 | 2.224 | 0/3 |
| diamonds-diamonds | 3/3 | 0.928 | 3/3 | 1.090 | 3/3 | 1.000 | 3/3 |
| earnings-logearn_interaction | 3/3 | 0.838 | 3/3 | 0.882 | 3/3 | 1.034 | 3/3 |
| mesquite-logmesquite_logvash | 3/3 | 1.006 | 3/3 | 1.316 | 3/3 | 1.008 | 3/3 |
| kidiq-kidscore_momhsiq | 3/3 | 0.922 | 3/3 | 1.188 | 3/3 | 1.107 | 3/3 |
| sblrc-blr | 3/3 | 1.009 | 3/3 | 0.977 | 2/3 | 1.000 | 3/3 |
| nes2000-nes | 3/3 | 1.197 | 3/3 | 1.412 | 3/3 | 1.263 | 3/3 |
| arK-arK | 3/3 | 1.213 | 3/3 | 1.444 | 3/3 | 1.185 | 3/3 |
| arma-arma11 | 3/3 | 1.092 | 3/3 | 1.241 | 3/3 | 1.098 | 3/3 |
| garch-garch11 | 3/3 | 1.089 | 3/3 | 1.153 | 3/3 | 1.147 | 3/3 |
| gp_pois_regr-gp_pois_regr | 3/3 | 1.018 | 3/3 | 1.033 | 3/3 | 1.010 | 3/3 |
| hmm_example-hmm_example | 3/3 | 1.038 | 3/3 | 1.245 | 3/3 | 1.054 | 3/3 |
| bball_drive_event_0-hmm_drive_0 | 1/3 | 118.814 | 3/3 | 0.634 | 1/3 | 1.076 | 1/3 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 1/3 | 1.196 | 1/3 | 1.639 | 2/3 | 1.012 | 1/3 |
| hudson_lynx_hare-lotka_volterra | 2/3 | 0.944 | 3/3 | 1.293 | 2/3 | 1.122 | 2/3 |
| mcycle_gp-accel_gp | 0/3 | 1.135 | 0/3 | 2.065 | 0/3 | 1.000 | 0/3 |

## Funnel sanity (P(omega < -5), exact 0.0478)

| arm | seeds | pooled P5 | s.e. | t | within 1 s.e. | warmup share | warmup lengths | early-stopped chains |
|---|---:|---:|---:|---:|---|---:|---|---:|
| default | 10 | 0.0477 | 0.0015 | -0.04 | True | 0.034 | [2000] | 0 |
| init25 | 10 | 0.0463 | 0.0017 | -0.89 | True | 0.051 | [2000] | 0 |
| half | 10 | 0.0499 | 0.0032 | +0.67 | True | 0.023 | [1000] | 0 |
| stablestop | 10 | 0.0477 | 0.0015 | -0.04 | True | 0.034 | [2000] | 0 |
