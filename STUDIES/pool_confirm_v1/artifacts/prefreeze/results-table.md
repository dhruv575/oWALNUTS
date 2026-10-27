## Verdict

Verdict: {"headline_allowed": false, "headline_configs": [], "smallest_passing_K_both": null, "smallest_passing_configs_both": [], "passing_per_dataset": {"sim": [], "real": []}, "smallest_passing_K_per_dataset": {"sim": null, "real": null}, "smallest_passing_K_asis_per_dataset": {"sim": null, "real": null}, "secondary_uniform_pass_both": [], "largest_tolerance": {"sim:K200:H1:uniform:asis": null, "sim:K200:H10:exp:pf-lagnorm": null, "sim:K200:H10:uniform:pf-lagnorm": null, "sim:K200:H20:exp:pf-lagnorm": null, "sim:K200:H20:uniform:pf-lagnorm": null, "real:K20:H1:uniform:asis": null, "real:K20:H10:exp:pf-lagnorm": null, "real:K20:H10:uniform:pf-lagnorm": null, "real:K20:H20:exp:pf-lagnorm": null, "real:K20:H20:uniform:pf-lagnorm": null}}

## Pass on both datasets per (K, H, weighting)

| K | estimator | H | weighting | sim | real | both | latency ms sim / real (library + pooling, median) |
|---|---|---|---|---|---|---|---|
| 20 | asis | 1 | uniform | missing | FAIL | no | n/a / 26.7 |
| 20 | pf-lagnorm | 10 | exp | missing | FAIL | no | n/a / 26.8 |
| 20 | pf-lagnorm | 10 | uniform | missing | FAIL | no | n/a / 26.7 |
| 20 | pf-lagnorm | 20 | exp | missing | FAIL | no | n/a / 26.7 |
| 20 | pf-lagnorm | 20 | uniform | missing | FAIL | no | n/a / 26.7 |
| 50 | asis | 1 | uniform | missing | missing | no | n/a / n/a |
| 50 | pf-lagnorm | 10 | exp | missing | missing | no | n/a / n/a |
| 50 | pf-lagnorm | 10 | uniform | missing | missing | no | n/a / n/a |
| 50 | pf-lagnorm | 20 | exp | missing | missing | no | n/a / n/a |
| 50 | pf-lagnorm | 20 | uniform | missing | missing | no | n/a / n/a |
| 200 | asis | 1 | uniform | FAIL | missing | no | 65.3 / n/a |
| 200 | pf-lagnorm | 10 | exp | FAIL | missing | no | 65.3 / n/a |
| 200 | pf-lagnorm | 10 | uniform | FAIL | missing | no | 65.3 / n/a |
| 200 | pf-lagnorm | 20 | exp | FAIL | missing | no | 65.3 / n/a |
| 200 | pf-lagnorm | 20 | uniform | FAIL | missing | no | 65.3 / n/a |

## sim: pass share per (K, H, weighting) against the frozen rule

Pass = |P50 err| <= 2 % and |P95 err| <= 5 % vs the gated reference, no stuck chain, library call + pooling arithmetic < 0.4 s, on >= 95 % of the 300 scored ticks pooled and >= 90 % per seed, drift within 0.5 pp per seed. 'ge20' = pass share over ticks >= 20 (full pools). wESS = weight ESS of the pool (median / min over ticks). own MCSE = chain-split own MCSE of the pooled P50 (median). Latency medians are medians of the seed medians. 'largest tol.' = first (P50, P95) pair on the WP88 grid met at >= 95 % / >= 90 %.

| K | estimator | H | weighting | pass pooled | per seed | ge20 | P50 ok | P95 ok | \|P50 err\| med | \|P95 err\| med | signed P50 | signed P95 | drift pp per seed | pool n | wESS med / min | in ref 90 % | own MCSE P50 | lib ms | pool ms | total ms | largest tol. | rule |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | asis | 1 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 20 | pf-lagnorm | 10 | exp | missing | | | | | | | | | | | | | | | | | | |
| 20 | pf-lagnorm | 10 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 20 | pf-lagnorm | 20 | exp | missing | | | | | | | | | | | | | | | | | | |
| 20 | pf-lagnorm | 20 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 50 | asis | 1 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 10 | exp | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 10 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 20 | exp | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 20 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 200 | asis | 1 | uniform | 66.7 % | 67 % | n/a | 67 % | 67 % | 0.78 % | 0.96 % | -0.63 % | -0.65 % | n/a | 800 | 800 / 800 | 0.899 | 0.78 % | 64.0 | 0.12 | 65.3 | None | FAIL |
| 200 | pf-lagnorm | 10 | exp | 66.7 % | 67 % | n/a | 67 % | 67 % | 0.62 % | 0.66 % | -0.47 % | -0.35 % | n/a | 1200 | 1186 / 800 | 0.897 | 0.88 % | 64.0 | 0.18 | 65.3 | None | FAIL |
| 200 | pf-lagnorm | 10 | uniform | 66.7 % | 67 % | n/a | 67 % | 67 % | 0.61 % | 0.63 % | -0.46 % | -0.32 % | n/a | 1200 | 1189 / 800 | 0.897 | 0.89 % | 64.0 | 0.14 | 65.3 | None | FAIL |
| 200 | pf-lagnorm | 20 | exp | 66.7 % | 67 % | n/a | 67 % | 67 % | 0.62 % | 0.66 % | -0.47 % | -0.35 % | n/a | 1200 | 1188 / 800 | 0.897 | 0.88 % | 64.0 | 0.13 | 65.3 | None | FAIL |
| 200 | pf-lagnorm | 20 | uniform | 66.7 % | 67 % | n/a | 67 % | 67 % | 0.61 % | 0.63 % | -0.46 % | -0.32 % | n/a | 1200 | 1189 / 800 | 0.897 | 0.89 % | 64.0 | 0.13 | 65.3 | None | FAIL |

## real: pass share per (K, H, weighting) against the frozen rule

Pass = |P50 err| <= 2 % and |P95 err| <= 5 % vs the gated reference, no stuck chain, library call + pooling arithmetic < 0.4 s, on >= 95 % of the 300 scored ticks pooled and >= 90 % per seed, drift within 0.5 pp per seed. 'ge20' = pass share over ticks >= 20 (full pools). wESS = weight ESS of the pool (median / min over ticks). own MCSE = chain-split own MCSE of the pooled P50 (median). Latency medians are medians of the seed medians. 'largest tol.' = first (P50, P95) pair on the WP88 grid met at >= 95 % / >= 90 %.

| K | estimator | H | weighting | pass pooled | per seed | ge20 | P50 ok | P95 ok | \|P50 err\| med | \|P95 err\| med | signed P50 | signed P95 | drift pp per seed | pool n | wESS med / min | in ref 90 % | own MCSE P50 | lib ms | pool ms | total ms | largest tol. | rule |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20 | asis | 1 | uniform | 33.3 % | 33 % | n/a | 67 % | 33 % | 0.87 % | 3.28 % | 0.87 % | 3.28 % | n/a | 80 | 80 / 80 | 0.875 | 5.83 % | 26.4 | 0.04 | 26.7 | None | FAIL |
| 20 | pf-lagnorm | 10 | exp | 33.3 % | 33 % | n/a | 67 % | 33 % | 0.33 % | 3.31 % | -0.29 % | 3.31 % | n/a | 120 | 117 / 80 | 0.881 | 4.41 % | 26.4 | 0.07 | 26.8 | None | FAIL |
| 20 | pf-lagnorm | 10 | uniform | 33.3 % | 33 % | n/a | 67 % | 33 % | 0.38 % | 3.31 % | -0.34 % | 3.31 % | n/a | 120 | 117 / 80 | 0.882 | 4.17 % | 26.4 | 0.05 | 26.7 | None | FAIL |
| 20 | pf-lagnorm | 20 | exp | 33.3 % | 33 % | n/a | 67 % | 33 % | 0.36 % | 3.31 % | -0.31 % | 3.31 % | n/a | 120 | 117 / 80 | 0.882 | 4.29 % | 26.4 | 0.05 | 26.7 | None | FAIL |
| 20 | pf-lagnorm | 20 | uniform | 33.3 % | 33 % | n/a | 67 % | 33 % | 0.38 % | 3.31 % | -0.34 % | 3.31 % | n/a | 120 | 117 / 80 | 0.882 | 4.17 % | 26.4 | 0.05 | 26.7 | None | FAIL |
| 50 | asis | 1 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 10 | exp | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 10 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 20 | exp | missing | | | | | | | | | | | | | | | | | | |
| 50 | pf-lagnorm | 20 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 200 | asis | 1 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 200 | pf-lagnorm | 10 | exp | missing | | | | | | | | | | | | | | | | | | |
| 200 | pf-lagnorm | 10 | uniform | missing | | | | | | | | | | | | | | | | | | |
| 200 | pf-lagnorm | 20 | exp | missing | | | | | | | | | | | | | | | | | | |
| 200 | pf-lagnorm | 20 | uniform | missing | | | | | | | | | | | | | | | | | | |

## Latency per (dataset, K): library call per tick, 100 ticks x 3 seeds (tick 0 excluded); pooling arithmetic at H = 20 exp

| dataset | K | lib median ms | lib p95 ms (worst seed) | pool ms H=10 / H=20 (exp, median) | total < 0.4 s (H=20 exp) | lib < 10 ms | lib < 50 ms | lib < 100 ms | arviz own MCSE P50 (H=1) | ESS h_next (H=1) | R-hat <= 1.01 (H=1) | div ticks | tick-0 s | tick-0 attempts | kept |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sim | 20 | missing | | | | | | | | | | | | | |
| sim | 50 | missing | | | | | | | | | | | | | |
| sim | 200 | 64.0 | 66.4 | 0.18 / 0.13 | 100.0 % | 0 % | 0 % | 100 % | 0.68 % | 1265 | 100 % | 0 | 2.202 | 1 | [0, 1, 2, 3] |
| real | 20 | 26.4 | 26.9 | 0.07 / 0.05 | 100.0 % | 0 % | 100 % | 100 % | 6.07 % | 133 | 0 % | 0 | 4.822 | 1 | [0, 1, 2, 3] |
| real | 50 | missing | | | | | | | | | | | | | |
| real | 200 | missing | | | | | | | | | | | | | |

## Gated reference (4 x 2,000/20,000 per tick, every tick 0..100, per dataset; trapped-chain guard on by default)

| dataset | ticks planned | recorded | ok | gate failed (both seeds) | second seed used | ticks with a flagged chain | flagged ticks | min chains kept | max R-hat(h_next) | rel. MCSE P50 med / max | rel. MCSE P95 med / max | min ESS | sampler wall median / max s | driver wall median s | total sampler min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sim | 3 | 3 | 3 | 0 | 0 | 0 | [] | 4 | 1.0000 | 0.08 % / 0.09 % | 0.23 % / 0.24 % | 108503 | 10.3 / 12.1 | 16.3 | 0.5 |
| real | 3 | 3 | 3 | 0 | 0 | 0 | [] | 4 | 1.0001 | 0.12 % / 0.13 % | 0.31 % / 0.33 % | 83903 | 28.0 / 28.3 | 33.4 | 1.3 |

## Reference lag curve per dataset: the gated reference at tick t-j against tick t (staleness with no Monte Carlo noise)

| dataset | lag j | pairs | \|P50 change\| median | within 2 % | signed mean P50 | \|P95 change\| median | within 5 % | signed mean P95 | both within |
|---|---|---|---|---|---|---|---|---|---|
| sim | 1 | 2 | 4.46 % | 0 % | 4.46 % | 5.01 % | 50 % | 5.01 % | 0 % |
| sim | 2 | 1 | 9.11 % | 0 % | 9.11 % | 10.26 % | 0 % | 10.26 % | 0 % |
| real | 1 | 2 | 8.49 % | 0 % | 0.57 % | 8.68 % | 0 % | 0.32 % | 0 % |
| real | 2 | 1 | 0.42 % | 100 % | 0.42 % | 0.11 % | 100 % | -0.11 % | 100 % |

## Importance-weight efficiency per lag group (weight ESS / draws of the group, median over ticks, median over seeds)

| dataset | K | lag 0 | lag 1 | lag 2 | lag 3 | lag 4 | lag 5 | lag 6 | lag 7 | lag 8 | lag 9 | lag 10 | lag 11 | lag 12 | lag 13 | lag 14 | lag 15 | lag 16 | lag 17 | lag 18 | lag 19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sim | 200 | 100 % | 97 % | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| real | 20 | 100 % | 93 % | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Warm tick-0 fits (gated; outside the latency statistics)

| cell | status | attempts | tick-0 seed | wall s | flagged (last attempt) | kept | tick-0 P50 err | tick-0 P95 err |
|---|---|---|---|---|---|---|---|---|
| warm200-sim-s993972 | ok | 1 | 993972 | 2.202 | [] | [0, 1, 2, 3] | 0.07 % | -0.65 % |
| warm20-real-s993971 | ok | 1 | 993971 | 4.822 | [] | [0, 1, 2, 3] | 0.22 % | 2.82 % |
