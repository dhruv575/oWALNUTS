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
| kidiq__kidscore_momhsiq | zero | 1/2 | 0 | 343824 | 5 | 8 | 0.016 | 0.013 | 4.2804 | 1000,0 | 9.395e-1 | 3.709e-2 | 2.668 |
| kidiq__kidscore_momhsiq | floor-zero | 1/2 | 0 | 342882 | 529 | 614 | 1.288 | 1.055 | 2.2069 | 1000,0 | 9.709e-1 | 2.811e-2 | 2.668 |
| kidiq__kidscore_momhsiq | guarded-zero | 1/2 | 0 | 336086 | 428 | 504 | 1.319 | 1.080 | 1.8680 | 1000,0 | 1.464e0 | 4.406e-2 | 2.668 |
| kidiq__kidscore_momhsiq | zero-wide | 0/2 | 0 | 326413 | 501 | 566 | 1.440 | 1.180 | 1.3006 | 0,0 | 1.464e0 | 6.751e-2 | 2.668 |
| kidiq__kidscore_momhsiq | guarded-zero-wide | 0/2 | 0 | 295201 | 388 | 283 | 1.318 | 1.079 | 1.3003 | 0,0 | 1.603e0 | 6.744e-2 | 2.668 |
| sblrc__blr | da | 0/2 | 0 | 459180 | 204 | 180 | 0.432 | 1.000 | 1.0190 | 0,0 | 1.000e0 | 3.438e-3 | 0.295 |
| sblrc__blr | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e-8 | 1.000e-1 | 0.295 |
| sblrc__blr | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 5.000e-2 | 1.000e-1 | 0.295 |
| sblrc__blr | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e-8 | 1.000e-1 | 0.295 |
| sblrc__blr | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e0 | 1.000e-1 | 0.295 |
| sblrc__blr | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.073 | 1283649186370338.7500 | 3000,3000 | 1.000e0 | 1.000e-1 | 0.295 |
| sblrc__blr | zero | 2/2 | 0 | 303535 | 4 | 4 | 0.015 | 0.034 | 3.4343 | 1000,1000 | 6.104e-1 | 9.825e-4 | 0.295 |
| sblrc__blr | floor-zero | 2/2 | 0 | 393229 | 5 | 4 | 0.012 | 0.029 | 2.8426 | 1000,1000 | 6.893e-1 | 1.033e-3 | 0.295 |
| sblrc__blr | guarded-zero | 2/2 | 0 | 322666 | 6 | 4 | 0.018 | 0.041 | 2.4823 | 1000,1000 | 1.285e0 | 2.020e-3 | 0.295 |
| sblrc__blr | zero-wide | 0/2 | 0 | 455318 | 213 | 212 | 0.423 | 0.978 | 1.3131 | 0,0 | 1.405e0 | 2.467e-3 | 0.295 |
| sblrc__blr | guarded-zero-wide | 0/2 | 0 | 444962 | 19 | 45 | 0.046 | 0.107 | 1.3599 | 0,0 | 1.369e0 | 2.889e-3 | 0.295 |
| earnings__logearn_interaction | da | 0/2 | 0 | 1116276 | 6 | 11 | 0.006 | 1.000 | 1.7003 | 0,0 | 1.000e0 | 2.916e-3 | 0.015 |
| earnings__logearn_interaction | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e-8 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 5.000e-2 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e-8 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e0 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 5.488 | 1283649186370338.7500 | 4000,4000 | 1.000e0 | 1.000e-1 | 0.015 |
| earnings__logearn_interaction | zero | 2/2 | 0 | 230884 | 4 | 4 | 0.022 | 3.807 | 641824593185175.0000 | 2000,1000 | 2.649e-5 | 1.000e-4 | 0.015 |
| earnings__logearn_interaction | floor-zero | 2/2 | 0 | 353169 | 4 | 4 | 0.019 | 3.381 | 641824593185172.8750 | 2000,1000 | 3.062e-1 | 1.000e-4 | 0.015 |
| earnings__logearn_interaction | guarded-zero | 2/2 | 0 | 405274 | 4 | 4 | 0.019 | 3.283 | 641824593185171.8750 | 2000,1000 | 1.159e0 | 9.102e-4 | 0.015 |
| earnings__logearn_interaction | zero-wide | 0/2 | 0 | 1045798 | 6 | 11 | 0.006 | 1.023 | 1.7978 | 0,0 | 1.350e0 | 2.987e-3 | 0.015 |
| earnings__logearn_interaction | guarded-zero-wide | 0/2 | 0 | 999824 | 6 | 13 | 0.006 | 1.126 | 1.6810 | 0,0 | 1.263e0 | 3.451e-3 | 0.015 |
| diamonds__diamonds | da | 0/2 | 0 | 1601154 | 63 | 117 | 0.039 | 1.000 | 1.0484 | 0,0 | 1.000e0 | 3.198e-3 | 0.022 |
| diamonds__diamonds | paper | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e-8 | 1.000e-1 | 0.022 |
| diamonds__diamonds | floor | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 5.000e-2 | 1.000e-1 | 0.022 |
| diamonds__diamonds | defer | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.079e-8 | 1.000e-1 | 0.022 |
| diamonds__diamonds | guarded | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e0 | 1.000e-1 | 0.022 |
| diamonds__diamonds | guarded-trim | 2/2 | 0 | 128000 | 4 | 4 | 0.032 | 0.801 | 1283649186370338.7500 | 3000,2000 | 1.000e0 | 1.000e-1 | 0.022 |
| diamonds__diamonds | zero | 1/2 | 0 | 1280922 | 24 | 47 | 0.018 | 0.453 | 1.3261 | 0,0 | 1.469e0 | 4.089e-3 | 0.022 |
| diamonds__diamonds | floor-zero | 0/2 | 0 | 1318228 | 47 | 88 | 0.035 | 0.884 | 1.3472 | 0,0 | 1.545e0 | 4.247e-3 | 0.022 |
| diamonds__diamonds | guarded-zero | 0/2 | 0 | 1445160 | 59 | 138 | 0.041 | 1.037 | 1.0787 | 0,0 | 1.343e0 | 3.910e-3 | 0.022 |
| diamonds__diamonds | zero-wide | 0/2 | 0 | 1522802 | 81 | 176 | 0.053 | 1.347 | 1.0697 | 0,0 | 1.507e0 | 3.902e-3 | 0.022 |
| diamonds__diamonds | guarded-zero-wide | 0/2 | 0 | 1550802 | 95 | 177 | 0.061 | 1.557 | 1.0509 | 0,0 | 1.550e0 | 3.872e-3 | 0.022 |
| nes2000__nes | da | 0/2 | 0 | 405280 | 1109 | 1320 | 2.744 | 1.000 | 1.0037 | 0,0 | 1.000e0 | 6.599e-2 | 2.401 |
| nes2000__nes | paper | 2/2 | 0 | 151562 | 4 | 4 | 0.027 | 0.010 | 641824593185174.1250 | 1000,2000 | 1.000e-8 | 1.000e-1 | 2.401 |
| nes2000__nes | floor | 2/2 | 0 | 151562 | 4 | 4 | 0.027 | 0.010 | 641824593185174.1250 | 1000,2000 | 5.000e-2 | 1.000e-1 | 2.401 |
| nes2000__nes | defer | 2/2 | 0 | 147172 | 4 | 4 | 0.028 | 0.010 | 641824593185174.1250 | 1000,2000 | 1.000e-8 | 1.000e-1 | 2.401 |
| nes2000__nes | guarded | 2/2 | 0 | 162062 | 4 | 4 | 0.026 | 0.010 | 6.4836 | 1000,1878 | 1.000e0 | 1.000e-1 | 2.401 |
| nes2000__nes | guarded-trim | 2/2 | 0 | 166122 | 4 | 4 | 0.026 | 0.009 | 6.4440 | 1000,1878 | 1.000e0 | 1.000e-1 | 2.401 |
| nes2000__nes | zero | 0/2 | 0 | 386476 | 996 | 1315 | 2.576 | 0.939 | 1.0050 | 0,0 | 1.535e0 | 7.090e-2 | 2.401 |
| nes2000__nes | floor-zero | 0/2 | 0 | 385535 | 986 | 1212 | 2.554 | 0.931 | 1.0050 | 0,0 | 1.485e0 | 7.212e-2 | 2.401 |
| nes2000__nes | guarded-zero | 0/2 | 0 | 404220 | 1100 | 1498 | 2.722 | 0.992 | 1.0057 | 0,0 | 1.438e0 | 6.341e-2 | 2.401 |
| nes2000__nes | zero-wide | 0/2 | 0 | 398362 | 1065 | 1337 | 2.673 | 0.974 | 1.0069 | 0,0 | 1.433e0 | 6.570e-2 | 2.401 |
| nes2000__nes | guarded-zero-wide | 0/2 | 0 | 390771 | 1177 | 1470 | 3.010 | 1.097 | 1.0044 | 0,0 | 1.376e0 | 6.635e-2 | 2.401 |
| mesquite__logmesquite_logvash | da | 0/2 | 0 | 332931 | 1073 | 1334 | 3.223 | 1.000 | 1.0046 | 0,0 | 1.000e0 | 7.061e-2 | 2.827 |
| mesquite__logmesquite_logvash | paper | 2/2 | 0 | 192629 | 4 | 4 | 0.023 | 0.007 | 3.4103 | 0,0 | 6.098e-1 | 9.698e-2 | 2.827 |
| mesquite__logmesquite_logvash | floor | 2/2 | 0 | 191006 | 4 | 4 | 0.023 | 0.007 | 3.4097 | 0,0 | 6.348e-1 | 9.872e-2 | 2.827 |
| mesquite__logmesquite_logvash | defer | 2/2 | 0 | 186336 | 4 | 4 | 0.024 | 0.007 | 3.4146 | 0,0 | 5.860e-1 | 9.765e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded | 2/2 | 0 | 186336 | 4 | 4 | 0.024 | 0.007 | 3.4146 | 0,0 | 1.086e0 | 9.765e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded-trim | 2/2 | 0 | 178684 | 4 | 4 | 0.025 | 0.008 | 3.4107 | 0,0 | 1.323e0 | 1.034e-1 | 2.827 |
| mesquite__logmesquite_logvash | zero | 0/2 | 0 | 320572 | 997 | 1206 | 3.108 | 0.964 | 1.0045 | 0,0 | 1.404e0 | 7.350e-2 | 2.827 |
| mesquite__logmesquite_logvash | floor-zero | 0/2 | 0 | 320572 | 997 | 1206 | 3.108 | 0.964 | 1.0045 | 0,0 | 1.404e0 | 7.350e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded-zero | 0/2 | 0 | 326620 | 1181 | 1473 | 3.615 | 1.122 | 1.0040 | 0,0 | 1.457e0 | 7.164e-2 | 2.827 |
| mesquite__logmesquite_logvash | zero-wide | 0/2 | 0 | 323582 | 954 | 1203 | 2.949 | 0.915 | 1.0056 | 0,0 | 1.439e0 | 7.147e-2 | 2.827 |
| mesquite__logmesquite_logvash | guarded-zero-wide | 0/2 | 0 | 327241 | 1177 | 1415 | 3.594 | 1.115 | 1.0040 | 0,0 | 1.438e0 | 7.104e-2 | 2.827 |
| hmm_example__hmm_example | da | 0/2 | 0 | 204426 | 1993 | 1506 | 9.750 | 1.000 | 1.0028 | 0,0 | 1.000e0 | 1.398e-1 | 8.310 |
| hmm_example__hmm_example | paper | 2/2 | 0 | 245130 | 6 | 4 | 0.026 | 0.003 | 641824593185170.1250 | 0,0 | 1.624e-2 | 1.228e-1 | 8.310 |
| hmm_example__hmm_example | floor | 1/2 | 0 | 194600 | 815 | 759 | 4.485 | 0.460 | 2.2042 | 0,0 | 7.738e-1 | 1.516e-1 | 8.310 |
| hmm_example__hmm_example | defer | 1/2 | 0 | 180671 | 622 | 704 | 3.243 | 0.333 | 1.2653 | 0,0 | 1.307e0 | 1.733e-1 | 8.310 |
| hmm_example__hmm_example | guarded | 0/2 | 0 | 159783 | 1514 | 1272 | 9.492 | 0.974 | 1.0030 | 0,0 | 1.348e0 | 1.837e-1 | 8.310 |
| hmm_example__hmm_example | guarded-trim | 0/2 | 0 | 151646 | 1800 | 1432 | 11.902 | 1.221 | 1.0024 | 0,0 | 1.986e0 | 1.883e-1 | 8.310 |
| hmm_example__hmm_example | zero | 0/2 | 0 | 193486 | 1701 | 1823 | 8.790 | 0.902 | 1.0026 | 0,0 | 1.621e0 | 1.620e-1 | 8.310 |
| hmm_example__hmm_example | floor-zero | 0/2 | 0 | 193486 | 1701 | 1823 | 8.790 | 0.902 | 1.0026 | 0,0 | 1.621e0 | 1.620e-1 | 8.310 |
| hmm_example__hmm_example | guarded-zero | 0/2 | 0 | 201432 | 1909 | 1504 | 9.467 | 0.971 | 1.0037 | 0,0 | 1.637e0 | 1.436e-1 | 8.310 |
| hmm_example__hmm_example | zero-wide | 0/2 | 0 | 193486 | 1701 | 1823 | 8.790 | 0.902 | 1.0026 | 0,0 | 1.621e0 | 1.620e-1 | 8.310 |
| hmm_example__hmm_example | guarded-zero-wide | 0/2 | 0 | 201432 | 1909 | 1504 | 9.467 | 0.971 | 1.0037 | 0,0 | 1.637e0 | 1.436e-1 | 8.310 |

## Decision rule

| arm | robust (no frozen/error cell on any model) | models with r >= 0.8 | geomean r | clears the bar |
|---|---|---:|---:|---|

(`paper` is never a candidate; the winner is the first clearing arm in the listed order.)

| paper | false | 0/7 | 0.055 | false |
| floor | false | 0/7 | 0.115 | false |
| defer | false | 0/7 | 0.111 | false |
| guarded | false | 1/7 | 0.128 | false |
| guarded-trim | false | 1/7 | 0.133 | false |
| zero | false | 3/7 | 0.348 | false |
| floor-zero | false | 4/7 | 0.688 | false |
| guarded-zero | false | 4/7 | 0.772 | false |
| zero-wide | true | 7/7 | 1.036 | true |
| guarded-zero-wide | true | 6/7 | 0.816 | false |

Preregistered rule -> new `PaperAdaptationConfig::default()`: **zero-wide**
