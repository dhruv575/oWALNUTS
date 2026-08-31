# Results — oWALNUTS v10 vs NumPyro NUTS (WP14)

Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at `6af80da`; seeds [92001, 92002, 92003]; diagnostics ArviZ rank R-hat / bulk / tail ESS from exported draws (same code path for both backends). `work` is fused target calls (oWALNUTS) or leapfrog `num_steps` (NumPyro) — different operations, labelled, never equated.


## Part 1 — sspd-05 matched timing

| arm | seed | max R-hat (fn) | min bulk | min tail | div/inv/exh | cap | depth | work total | wall s | min bulk ESS/s | bulk ESS/work (×1e3) | gates |
|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| T-F (owalnuts) | 92001 | 1.0013 (sigma_x) | 1235 | 1251 | 0/0/0 | 0.00% | 6 | 934,949 | 5.4 | 231 | 1.321 | PASS |
| T-F (owalnuts) | 92002 | 1.0594 (alpha) | 75 | 23 | 0/0/0 | 0.00% | 5 | 870,180 | 4.2 | 18 | 0.086 | FAIL |
| T-F (owalnuts) | 92003 | 1.0093 (sigma_x) | 1032 | 1492 | 0/0/0 | 0.00% | 5 | 858,673 | 4.2 | 247 | 1.202 | PASS |
| T-I (owalnuts) | 92001 | 1.0103 (sigma_x) | 363 | 97 | 0/0/209 | 0.00% | 5 | 802,328 | 4.3 | 84 | 0.453 | FAIL |
| T-I (owalnuts) | 92002 | 1.0021 (alpha) | 1062 | 752 | 0/0/1 | 0.00% | 5 | 675,639 | 3.5 | 303 | 1.572 | FAIL |
| T-I (owalnuts) | 92003 | 1.0039 (alpha) | 858 | 1281 | 0/0/0 | 0.00% | 5 | 676,327 | 3.2 | 268 | 1.269 | PASS |
| T-P (owalnuts) | 92001 | 1.0107 (alpha) | 435 | 209 | 0/0/0 | 0.00% | 4 | 397,487 | 2.3 | 185 | 1.093 | FAIL |
| T-P (owalnuts) | 92002 | 1.0082 (alpha) | 344 | 201 | 0/0/3 | 0.00% | 4 | 387,968 | 2.4 | 141 | 0.887 | FAIL |
| T-P (owalnuts) | 92003 | 1.0082 (alpha) | 291 | 103 | 0/0/3 | 0.00% | 4 | 403,613 | 2.4 | 124 | 0.721 | FAIL |
| T-N (numpyro) | 92001 | 1.0019 (sigma_x) | 1296 | 1326 | 0/0/0 | 0.21% | 6 | 1,064,192 | 25.2 | 51 | 1.217 | PASS |
| T-N (numpyro) | 92002 | 1.0085 (sigma_x) | 785 | 613 | 0/0/0 | 0.25% | 6 | 1,084,988 | 30.2 | 26 | 0.723 | PASS |
| T-N (numpyro) | 92003 | 1.0037 (alpha) | 1330 | 1022 | 0/0/0 | 0.29% | 6 | 1,126,250 | 21.6 | 62 | 1.181 | PASS |

Pass counts: {'T-F': '2/3', 'T-I': '1/3', 'T-P': '0/3', 'T-N': '3/3'}

**Primary** T-F / T-N bulk ESS per total sampling second (matched-timing functionals): per functional {mu: 4.51, sigma_x: 4.24, nu: 3.76, x_initial: 3.69}, overall geometric mean **4.03** (2/3 eligible seeds).

- TF_over_TN_tail_ess_per_second: overall 4.12 (2/3 eligible)
- TF_over_TN_bulk_ess_per_work_total_LABELLED: overall 1.00 (2/3 eligible)
- TI_over_TN_bulk_ess_per_second: overall 4.26 (1/3 eligible)
- TP_over_TN_bulk_ess_per_second: overall — (0/3 eligible)
- TP_over_TI_bulk_ess_per_work_retained: overall — (0/3 eligible)
- TP_over_TI_min_bulk_ess_per_retained_call_per_seed: {"92001": 2.264, "92002": 0.509, "92003": 0.518}
- NumPyro compile probe (non-evidence): end-to-end 26.4 s, of which sampling 26.0 s → implied compile 0.4 s

*Post-hoc, labelled — matched-timing-v1 four-functional gate (mu, sigma_x, nu, x_initial), as the v7 study gated:* pass counts {'T-F': '2/3', 'T-I': '1/3', 'T-P': '1/3', 'T-N': '3/3'}; T-F/T-N bulk ESS/s 4.03 (2/3 eligible), tail 4.12; T-I/T-N 4.26 (1/3); T-P/T-N 2.85 (1/3). Per-seed table columns 'max R-hat / min ESS' above are the nine-functional preregistered gate.

Predictions:
- P1_TF_over_TN_ge_3: **held** — observed 4.0346292690750065
- P2_TF_TI_TN_pass_3of3: **failed** — observed {"T-F": "2/3", "T-I": "1/3", "T-N": "3/3"}
- P3_TP_over_TI_ge_2_every_seed: **failed** — observed {"92001": 2.264048535888063, "92002": 0.5089462448106494, "92003": 0.518301956006344}

## Part 2 — real-market T=48

| arm | seed | max R-hat (fn) | min bulk | min tail | div/inv/exh | cap | depth | work total | wall s | min bulk ESS/s | bulk ESS/work (×1e3) | gates |
|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| R-B (owalnuts) | 92001 | 1.0031 (beta) | 1189 | 1333 | 0/0/0 | 0.00% | 5 | 339,201 | 1.0 | 1222 | 3.504 | PASS |
| R-B (owalnuts) | 92002 | 1.0053 (gamma) | 848 | 786 | 0/0/0 | 0.00% | 5 | 322,154 | 0.9 | 921 | 2.633 | PASS |
| R-B (owalnuts) | 92003 | 1.0033 (gamma) | 991 | 1111 | 0/0/0 | 0.00% | 5 | 307,572 | 0.9 | 1112 | 3.224 | PASS |
| R-I (owalnuts) | 92001 | 1.0038 (gamma) | 970 | 454 | 0/0/0 | 0.00% | 5 | 329,296 | 1.0 | 1020 | 2.945 | PASS |
| R-I (owalnuts) | 92002 | 1.0023 (sigma_x) | 921 | 833 | 0/0/0 | 0.00% | 5 | 377,051 | 1.1 | 841 | 2.443 | PASS |
| R-I (owalnuts) | 92003 | 1.0051 (alpha) | 1185 | 1203 | 0/0/0 | 0.00% | 5 | 335,057 | 1.1 | 1087 | 3.537 | PASS |
| R-N (numpyro) | 92001 | 1.0030 (sigma_x) | 1464 | 2504 | 0/0/0 | 0.00% | 4 | 235,484 | 5.9 | 248 | 6.218 | PASS |
| R-N (numpyro) | 92002 | 1.0021 (sigma_x) | 1529 | 2829 | 0/0/0 | 0.00% | 5 | 288,843 | 6.7 | 228 | 5.293 | PASS |
| R-N (numpyro) | 92003 | 1.0046 (sigma_x) | 1195 | 1266 | 0/0/0 | 0.00% | 5 | 296,578 | 6.2 | 191 | 4.028 | PASS |

Pass counts: {'R-B': '3/3', 'R-I': '3/3', 'R-N': '3/3'}

- RB_over_RN_bulk_ess_per_second: overall 3.82 (3/3 eligible)
- RI_over_RN_bulk_ess_per_second: overall 3.17 (3/3 eligible)
- RB_over_RN_bulk_ess_per_work_total_LABELLED: overall 0.48 (3/3 eligible)
- RI_over_RN_bulk_ess_per_work_total_LABELLED: overall 0.41 (3/3 eligible)
- NumPyro compile probe (non-evidence): end-to-end 9.1 s, sampling 8.8 s

Predictions:
- P4_RB_RI_pass_3of3_cap_le_1pct: **held** — observed {"R-B": "3/3", "R-I": "3/3"}
- P5_RN_pass_3of3: **held** — observed "3/3"
- P6_RI_median_depth_le_RB: **held** — observed {"R-I": [5, 5, 5], "R-B": [5, 5, 5]}

## Part 3 — Neal's funnel

| arm | seed | P(ω<−5) (exact .0478) | z | P(ω<−6) (exact .0228) | var ω (9) | q1% (−6.98) | div | inv/exh | depth-cap | R-hat ω | bulk/tail ESS ω | work total | wall s | under-covers | gates |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|---|
| FN-F (owalnuts) | 92001 | 0.0510 | +0.73 | 0.0246 | 8.97 | -7.02 | 0 | 0/0 | 63 | 1.0016 | 1657/2363 | 8,046,047 | 4.2 | no | PASS |
| FN-F (owalnuts) | 92002 | 0.0461 | -0.37 | 0.0226 | 8.94 | -7.11 | 0 | 0/0 | 13 | 1.0035 | 1632/2097 | 8,125,546 | 4.3 | no | PASS |
| FN-F (owalnuts) | 92003 | 0.0476 | -0.05 | 0.0226 | 9.26 | -7.01 | 0 | 0/0 | 144 | 1.0035 | 1396/2511 | 8,262,142 | 4.2 | no | PASS |
| FN-A (owalnuts) | 92001 | 0.0498 | +0.42 | 0.0241 | 9.40 | -7.03 | 0 | 0/0 | 7 | 1.0102 | 827/2117 | 5,245,965 | 2.8 | no | FAIL |
| FN-A (owalnuts) | 92002 | 0.0439 | -0.80 | 0.0207 | 8.81 | -6.88 | 0 | 0/0 | 1 | 1.0032 | 1312/1889 | 4,478,993 | 2.3 | no | PASS |
| FN-A (owalnuts) | 92003 | 0.0428 | -0.94 | 0.0207 | 8.64 | -6.90 | 0 | 0/0 | 83 | 1.0030 | 1557/1585 | 5,740,410 | 3.7 | no | PASS |
| FN-N80 (numpyro) | 92001 | 0.0000 | -1.31 | 0.0000 | 5.34 | -4.23 | 1391 | 0/0 | 529 | 1.0422 | 96/34 | 5,894,562 | 24.2 | yes | FAIL |
| FN-N80 (numpyro) | 92002 | 0.0000 | -2.23 | 0.0000 | 6.10 | -3.97 | 590 | 0/0 | 555 | 1.0215 | 565/99 | 6,952,912 | 28.0 | yes | FAIL |
| FN-N80 (numpyro) | 92003 | 0.0000 | -0.85 | 0.0000 | 7.07 | -4.02 | 2088 | 0/0 | 626 | 1.1321 | 21/14 | 6,743,470 | 23.2 | yes | FAIL |
| FN-N95 (numpyro) | 92001 | 0.0000 | -3.93 | 0.0000 | 5.99 | -3.37 | 1276 | 0/0 | 300 | 1.0138 | 671/307 | 6,141,220 | 32.8 | yes | FAIL |
| FN-N95 (numpyro) | 92002 | 0.0000 | -8.19 | 0.0000 | 6.20 | -3.99 | 365 | 0/0 | 512 | 1.0174 | 1115/1337 | 7,644,180 | 33.6 | yes | FAIL |
| FN-N95 (numpyro) | 92003 | 0.0115 | -0.49 | 0.0000 | 8.80 | -5.13 | 3449 | 0/0 | 2602 | 1.1772 | 16/8 | 14,129,910 | 48.3 | yes | FAIL |

Pass counts: {'FN-F': '3/3', 'FN-A': '2/3', 'FN-N80': '0/3', 'FN-N95': '0/3'}; under-coverage counts: {'FN-F': '0/3', 'FN-A': '0/3', 'FN-N80': '3/3', 'FN-N95': '3/3'}; cells with divergences: {'FN-F': '0/3', 'FN-A': '0/3', 'FN-N80': '3/3', 'FN-N95': '3/3'}

Predictions:
- P7_FNF_FNA_pass_3of3: **failed** — observed {"FN-F": "3/3", "FN-A": "2/3"}
- P8_FNN80_undercovers_ge2_div_3of3: **held** — observed {"under": 3, "div": 3, "n": 3}
- P9_FNN95_undercovers_ge2_div_ge2: **held** — observed {"under": 3, "div": 3, "n": 3}
- P10_no_numpyro_cell_passes: **held** — observed {"FN-N80": "0/3", "FN-N95": "0/3"}
