# rescue_removal_paired_v1 (WP61) — results

Commit `c8b4bb2d`; 5 seeds paired; ratio = rescue_on / rescue_off min-bulk-ESS per gradient.

| model | paired | ratio geomean | per-seed ratios | seeds < 1 | passes off / on | grads median off / on | warmup grads median off / on | restarts per seed (on) | criteria (on) | min-step / median-step off ; on | max abs z off / on |
|---|---:|---:|---|---:|---|---|---|---|---|---|---|
| mcycle_gp-accel_gp | 5 | **1.012** | 1.00, 1.00, 0.90, 1.18, 1.00 | 1 | 0/5 / 0/5 | 2,954,564 / 2,888,403 | 1,335,155 / 1,324,941 | [0, 0, 1, 1, 0] | LogDensity, LogDensity | [0.872, 0.808, 0.807, 0.953, 0.77] ; [0.872, 0.808, 0.782, 0.956, 0.77] | 3.19 / 3.19 |
| one_comp_mm_elim_abs-one_comp_mm_elim_abs | 5 | **1.000** | 1.00, 1.00, 1.00, 1.00, 1.00 | 0 | 2/5 / 2/5 | 77,609 / 77,609 | 41,475 / 41,475 | [0, 0, 0, 0, 0] | none | [0.801, 0.874, 0.828, 0.756, 0.924] ; [0.801, 0.874, 0.828, 0.756, 0.924] | 3.68 / 3.68 |
| bball_drive_event_0-hmm_drive_0 | 5 | **1.109** | 1.31, 1.00, 1.17, 1.00, 1.09 | 0 | 5/5 / 5/5 | 76,754 / 76,754 | 51,465 / 51,465 | [1, 0, 1, 0, 2] | LogDensity, LogDensity, LogDensity, LogDensity | [0.135, 0.919, 0.833, 0.788, 0.929] ; [0.863, 0.919, 0.784, 0.788, 0.917] | 2.74 / 2.74 |
| eight_schools-eight_schools_centered | 5 | **1.000** | 1.00, 1.00, 1.00, 1.00, 1.00 | 0 | 0/5 / 0/5 | 199,124 / 199,124 | 87,199 / 87,199 | [0, 0, 0, 0, 0] | none | [0.801, 0.677, 0.276, 0.526, 0.657] ; [0.801, 0.677, 0.276, 0.526, 0.657] | 2.45 / 2.45 |
| nes2000-nes | 5 | **1.000** | 1.00, 1.00, 1.00, 1.00, 1.00 | 0 | 5/5 / 5/5 | 437,222 / 437,222 | 228,503 / 228,503 | [0, 0, 0, 0, 0] | none | [0.939, 0.885, 0.892, 0.853, 0.924] ; [0.939, 0.885, 0.892, 0.853, 0.924] | 2.41 / 2.41 |

**Paired geomean over the five models: 1.023** (0/5 models below 1.0, 2/5 above; pooled over all pairs 1.023); complete: True
**Hypothesis:** H1 refuted / H0 supported (rescue removal does not explain it; seeds do)
**Decision (frozen rule):** ATTRIBUTION ONLY: no default change (frozen rule)
Passes: rescue_off 12/25, rescue_on 12/25
