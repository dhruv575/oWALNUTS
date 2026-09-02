# paper_adaptation_robust_v1 — results

Seed medians over 2 seeds (4 chains, 1,000/1,000, unconstrained coordinates, `owalnuts::diagnostics`); `frozen` = cells (of 2) with a chain whose retained refinement exhaustions exceed 500 or with undefined R-hat; `r` = bulk ESS/gradient over the in-study `da` arm; `v1 da` = v1 seed-median min bulk ESS/gradient x1e3 (arviz, constrained reference parameters), orientation only.

| model | arm | frozen | error | grads | min bulk ESS | min tail ESS | bulk ESS/grad x1e3 | r vs da | max R-hat | div | final delta | final h | v1 da ESS/grad x1e3 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kidiq__kidscore_momhsiq | da | 0/2 | 0 | 391810 | 407 | 471 | 1.221 | 1.000 | 1.2864 | 0,0 | 1.000e0 | 5.842e-2 | 2.668 |
| kidiq__kidscore_momhsiq | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.026 | 1283649186370338.7500 | 3000,4000 | 1.000e-8 | 1.000e-1 | 2.668 |
| kidiq__kidscore_momhsiq | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.026 | 1283649186370338.7500 | 3000,4000 | 5.000e-2 | 1.000e-1 | 2.668 |
| kidiq__kidscore_momhsiq | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.026 | 1283649186370338.7500 | 3000,4000 | 1.000e-8 | 1.000e-1 | 2.668 |
| kidiq__kidscore_momhsiq | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.026 | 1283649186370338.7500 | 3000,4000 | 1.000e0 | 1.000e-1 | 2.668 |
| kidiq__kidscore_momhsiq | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.026 | 1283649186370338.7500 | 3000,4000 | 1.000e0 | 1.000e-1 | 2.668 |
| sblrc__blr | da | 0/2 | 0 | 459180 | 204 | 180 | 0.432 | 1.000 | 1.0190 | 0,0 | 1.000e0 | 3.438e-3 | 0.295 |
| sblrc__blr | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e-8 | 1.000e-1 | 0.295 |
| sblrc__blr | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 5.000e-2 | 1.000e-1 | 0.295 |
| sblrc__blr | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e-8 | 1.000e-1 | 0.295 |
| sblrc__blr | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e0 | 1.000e-1 | 0.295 |
| sblrc__blr | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e0 | 1.000e-1 | 0.295 |
| earnings__logearn_interaction | da | 0/2 | 0 | 1116276 | 6 | 11 | 0.006 | 1.000 | 1.7003 | 0,0 | 1.000e0 | 2.916e-3 | 0.015 |
| earnings__logearn_interaction | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e-8 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 5.000e-2 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e-8 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e0 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e0 | 1.000e-1 | 0.015 |
| diamonds__diamonds | da | 0/2 | 0 | 1601154 | 63 | 117 | 0.039 | 1.000 | 1.0484 | 0,0 | 1.000e0 | 3.198e-3 | 0.022 |
| diamonds__diamonds | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e-8 | 1.000e-1 | 0.022 |
| diamonds__diamonds | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 5.000e-2 | 1.000e-1 | 0.022 |
| diamonds__diamonds | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.079e-8 | 1.000e-1 | 0.022 |
| diamonds__diamonds | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e0 | 1.000e-1 | 0.022 |
| diamonds__diamonds | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e0 | 1.000e-1 | 0.022 |
| nes2000__nes | da | 0/2 | 0 | 405280 | 1109 | 1320 | 2.744 | 1.000 | 1.0037 | 0,0 | 1.000e0 | 6.599e-2 | 2.401 |
| nes2000__nes | paper | 2/2 | 0 | 151562 | 4 | 4 | 0.027 | 0.010 | 641824593185174.1250 | 1000,2000 | 1.000e-8 | 1.000e-1 | 2.401 |
| nes2000__nes | floor | 2/2 | 0 | 151562 | 4 | 4 | 0.027 | 0.010 | 641824593185174.1250 | 1000,2000 | 5.000e-2 | 1.000e-1 | 2.401 |
| nes2000__nes | defer | 2/2 | 0 | 147172 | 4 | 4 | 0.028 | 0.010 | 641824593185174.1250 | 1000,2000 | 1.000e-8 | 1.000e-1 | 2.401 |
| nes2000__nes | guarded | 2/2 | 0 | 162062 | 4 | 4 | 0.026 | 0.010 | 6.4836 | 1000,1878 | 1.000e0 | 1.000e-1 | 2.401 |
| nes2000__nes | guarded-trim | 2/2 | 0 | 166122 | 4 | 4 | 0.026 | 0.009 | 6.4440 | 1000,1878 | 1.000e0 | 1.000e-1 | 2.401 |
| mesquite__logmesquite_logvash | da | 0/2 | 0 | 332931 | 1073 | 1334 | 3.223 | 1.000 | 1.0046 | 0,0 | 1.000e0 | 7.061e-2 | 2.827 |
| mesquite__logmesquite_logvash | paper | 2/2 | 0 | 192629 | 4 | 4 | 0.023 | 0.007 | 3.4103 | 0,0 | 6.098e-1 | 9.698e-2 | 2.827 |
| mesquite__logmesquite_logvash | floor | 2/2 | 0 | 191006 | 4 | 4 | 0.023 | 0.007 | 3.4097 | 0,0 | 6.348e-1 | 9.872e-2 | 2.827 |
| mesquite__logmesquite_logvash | defer | 2/2 | 0 | 186336 | 4 | 4 | 0.024 | 0.007 | 3.4146 | 0,0 | 5.860e-1 | 9.765e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded | 2/2 | 0 | 186336 | 4 | 4 | 0.024 | 0.007 | 3.4146 | 0,0 | 1.086e0 | 9.765e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded-trim | 2/2 | 0 | 178684 | 4 | 4 | 0.025 | 0.008 | 3.4107 | 0,0 | 1.323e0 | 1.034e-1 | 2.827 |
| hmm_example__hmm_example | da | 0/2 | 0 | 204426 | 1993 | 1506 | 9.750 | 1.000 | 1.0028 | 0,0 | 1.000e0 | 1.398e-1 | 8.310 |
| hmm_example__hmm_example | paper | 2/2 | 0 | 245130 | 6 | 4 | 0.026 | 0.003 | 641824593185170.1250 | 0,0 | 1.624e-2 | 1.228e-1 | 8.310 |
| hmm_example__hmm_example | floor | 1/2 | 0 | 194600 | 815 | 759 | 4.485 | 0.460 | 2.2042 | 0,0 | 7.738e-1 | 1.516e-1 | 8.310 |
| hmm_example__hmm_example | defer | 1/2 | 0 | 180671 | 622 | 704 | 3.243 | 0.333 | 1.2653 | 0,0 | 1.307e0 | 1.733e-1 | 8.310 |
| hmm_example__hmm_example | guarded | 0/2 | 0 | 159783 | 1514 | 1272 | 9.492 | 0.974 | 1.0030 | 0,0 | 1.348e0 | 1.837e-1 | 8.310 |
| hmm_example__hmm_example | guarded-trim | 0/2 | 0 | 151646 | 1800 | 1432 | 11.902 | 1.221 | 1.0024 | 0,0 | 1.986e0 | 1.883e-1 | 8.310 |

## Decision rule

| arm | robust (no frozen/error cell on any model) | models with r >= 0.8 | geomean r | clears the bar |
|---|---|---:|---:|---|

(`paper` is never a candidate; the winner is the first clearing arm in the listed order.)

| paper | false | 0/7 | 0.055 | false |
| floor | false | 0/7 | 0.115 | false |
| defer | false | 0/7 | 0.111 | false |
| guarded | false | 1/7 | 0.128 | false |
| guarded-trim | false | 1/7 | 0.133 | false |

Preregistered rule -> new `PaperAdaptationConfig::default()`: **none (default unchanged)**
