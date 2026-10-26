# WP70 results

Seeds [700711, 700712, 700713]; 4 chains x 1,000/1,000 (warmup2000: 2,000/1,000); pinned to cores 4-7, co-tenanted.

| model | arm | gates | grads | min bulk ESS | min tail ESS | max R-hat | bulk ESS/grad x1e3 (seed median) | div | max abs z |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| mcycle_gp-accel_gp | cmdstan | 0/3 | 5,243,072 | 1,441 | 1,044 | 1.0054 | 0.275 | 37,174,81 | 3.41 |
| mcycle_gp-accel_gp | owalnuts | 0/3 | 2,951,819 | 460 | 181 | 1.0167 | 0.156 | 0,0,0 | 2.86 |
| mcycle_gp-accel_gp | cand-target095 | 3/3 | 7,328,361 | 1,241 | 840 | 1.0064 | 0.169 | 0,0,0 | 2.85 |
| mcycle_gp-accel_gp | cand-depth12 | 0/3 | 2,396,126 | 55 | 21 | 1.0602 | 0.023 | 0,0,0 | 2.70 |
| mcycle_gp-accel_gp | cand-warmup2000 | 0/3 | 3,438,254 | 187 | 92 | 1.0251 | 0.053 | 0,0,0 | 4.01 |
| eight_schools-eight_schools_noncentered | owalnuts | 3/3 | 69,913 | 2,097 | 1,620 | 1.0026 | 30.000 | 0,0,0 | 1.99 |
| eight_schools-eight_schools_noncentered | cand-target095 | 3/3 | 114,994 | 2,456 | 2,241 | 1.0024 | 22.305 | 0,0,0 | 2.31 |
| eight_schools-eight_schools_noncentered | cand-depth12 | 3/3 | 69,913 | 2,097 | 1,620 | 1.0026 | 30.000 | 0,0,0 | 1.99 |
| eight_schools-eight_schools_noncentered | cand-warmup2000 | 3/3 | 109,055 | 2,068 | 1,573 | 1.0026 | 18.653 | 0,0,0 | 1.89 |
| kidiq-kidscore_momhsiq | owalnuts | 3/3 | 368,651 | 1,392 | 1,590 | 1.0041 | 3.783 | 0,0,0 | 2.63 |
| kidiq-kidscore_momhsiq | cand-target095 | 3/3 | 479,667 | 1,607 | 1,850 | 1.0033 | 3.233 | 0,0,0 | 2.35 |
| kidiq-kidscore_momhsiq | cand-depth12 | 3/3 | 431,662 | 1,569 | 1,631 | 1.0036 | 3.653 | 0,0,0 | 1.92 |
| kidiq-kidscore_momhsiq | cand-warmup2000 | 3/3 | 485,213 | 1,666 | 1,746 | 1.0035 | 3.442 | 0,0,0 | 1.12 |
| arK-arK | owalnuts | 3/3 | 265,330 | 2,334 | 2,198 | 1.0027 | 8.574 | 0,0,0 | 1.89 |
| arK-arK | cand-target095 | 3/3 | 393,869 | 2,306 | 2,185 | 1.0022 | 6.044 | 0,0,0 | 3.17 |
| arK-arK | cand-depth12 | 3/3 | 265,330 | 2,334 | 2,198 | 1.0027 | 8.574 | 0,0,0 | 1.89 |
| arK-arK | cand-warmup2000 | 3/3 | 391,847 | 2,420 | 2,376 | 1.0021 | 6.175 | 0,0,0 | 3.03 |
| gp_pois_regr-gp_pois_regr | owalnuts | 3/3 | 1,156,261 | 810 | 942 | 1.0051 | 0.721 | 0,0,0 | 2.04 |
| gp_pois_regr-gp_pois_regr | cand-target095 | 3/3 | 2,016,055 | 1,451 | 1,978 | 1.0023 | 0.727 | 0,0,0 | 2.12 |
| gp_pois_regr-gp_pois_regr | cand-depth12 | 2/3 | 1,156,261 | 761 | 1,115 | 1.0051 | 0.678 | 0,0,0 | 2.06 |
| gp_pois_regr-gp_pois_regr | cand-warmup2000 | 3/3 | 1,717,133 | 928 | 1,183 | 1.0062 | 0.532 | 0,0,0 | 2.90 |
| garch-garch11 | owalnuts | 3/3 | 95,414 | 1,736 | 1,825 | 1.0039 | 18.224 | 0,0,0 | 1.71 |
| garch-garch11 | cand-target095 | 3/3 | 132,899 | 1,789 | 1,731 | 1.0024 | 13.543 | 0,0,0 | 2.15 |
| garch-garch11 | cand-depth12 | 3/3 | 95,414 | 1,736 | 1,825 | 1.0039 | 18.224 | 0,0,0 | 1.71 |
| garch-garch11 | cand-warmup2000 | 3/3 | 137,242 | 1,863 | 1,827 | 1.0030 | 13.476 | 0,0,0 | 2.02 |

Baseline: oWALNUTS/CmdStan accel_gp ESS per gradient 0.567; accel passes oWALNUTS 0/3, CmdStan 0/3.

| candidate | hypothesis (supported?) | R1 accel vs CmdStan | R2 accel gates | R3a control passes | R3b control geomean | rule |
|---|---|---|---|---|---|---|
| cand-target095 | H1 (False) | 0.616 (False) | 3/3 vs 0/3 (True) | 15 vs 15 (True) | 0.804 (False) | **False** |
| cand-depth12 | H2 (False) | 0.084 (False) | 0/3 vs 0/3 (True) | 14 vs 15 (False) | 0.981 (True) | **False** |
| cand-warmup2000 | H3 (False) | 0.192 (False) | 0/3 vs 0/3 (True) | 15 vs 15 (True) | 0.740 (False) | **False** |
