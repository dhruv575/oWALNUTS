# start_rule_paired_v1 (WP60) — results

Commit `f097391c`; 5 seeds paired; ratio = best_of_16 / uniform min-bulk-ESS per gradient.

| model | paired | ratio geomean | per-seed ratios | seeds < 1 | passes u / b | grads median u / b | warmup grads median u / b | start log density median u / b | min-step / median-step u ; b | max abs z u / b |
|---|---:|---:|---|---:|---|---|---|---|---|---|
| mcycle_gp-accel_gp | 5 | **3.025** | 1.79, 2.32, 33.69, 0.46, 3.96 | 1 | 0/5 / 1/5 | 2,630,669 / 2,836,210 | 1,321,439 / 1,306,115 | -36611.6 / -2650.6 | [0.729, 0.76, 0.815, 0.935, 0.803] ; [0.909, 0.919, 0.918, 0.968, 0.839] | 3.17 / 3.40 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 5 | **0.890** | 0.64, 1.45, 0.59, 3.21, 0.31 | 3 | 3/5 / 1/5 | 79,949 / 77,643 | 42,764 / 43,722 | -88.8 / -59.1 | [0.908, 0.869, 0.879, 0.891, 0.782] ; [0.915, 0.806, 0.764, 0.672, 0.787] | 5.53 / 3.40 |
| bball_drive_event_0-hmm_drive_0 | 5 | **0.320** | 1.96, 0.04, 1.16, 0.94, 0.04 | 3 | 5/5 / 3/5 | 120,129 / 105,019 | 95,551 / 67,351 | -22747.1 / -3627.0 | [0.933, 0.928, 0.897, 0.915, 0.174] ; [0.934, 0.645, 0.912, 0.153, 0.175] | 1.97 / 2.77 |
| earnings-logearn_interaction | 5 | **1.106** | 0.87, 1.22, 1.19, 1.05, 1.24 | 1 | 5/5 / 5/5 | 1,613,217 / 1,490,016 | 887,297 / 796,122 | -2542552.3 / -61559.5 | [0.875, 0.905, 0.709, 0.932, 0.126] ; [0.899, 0.983, 0.612, 0.906, 0.902] | 1.15 / 2.12 |
| eight_schools-eight_schools_centered | 5 | **1.388** | 6.85, 2.01, 12.01, 0.39, 0.08 | 2 | 0/5 / 0/5 | 286,465 / 224,445 | 93,348 / 89,908 | -56.9 / -48.9 | [0.485, 0.679, 0.737, 0.116, 0.332] ; [0.886, 0.639, 0.698, 0.606, 0.336] | 2.69 / 2.95 |
| kidiq-kidscore_momhsiq | 5 | **1.081** | 1.17, 1.11, 1.11, 0.89, 1.14 | 1 | 5/5 / 5/5 | 370,413 / 384,247 | 231,896 / 243,756 | -2440775.8 / -24644.4 | [0.88, 0.868, 0.818, 0.926, 0.937] ; [0.789, 0.931, 0.959, 0.88, 0.895] | 2.20 / 2.17 |

**Paired geomean over the six models: 1.061** (2/6 models below 1.0; pooled over all pairs 1.061); complete: True
**Hypothesis:** H0 supported (the start rule is not the cause; seeds / rescue removal are)
**Decision (frozen rule):** KEEP: recommend keeping Init::best_of(16) as the default
Passes: uniform 18/30, best_of_16 15/30
