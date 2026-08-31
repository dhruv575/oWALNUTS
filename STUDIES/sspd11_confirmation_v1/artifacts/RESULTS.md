## Primary — sspd-11, kernel v10, seeds 91001–91003

| seed | arm | max R-hat | min bulk ESS | min tail ESS | div/inv/exh | cap rate | median depth | retained calls | wall s | min bulk ESS/call | max |z| vs I | max |z| vs N | run gates | confirmed-run |
|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 91001 | I | 1.0066 | 931 | 2119 | 0/0/0 | 0.0040 | 8 | 1,836,230 | 28 | 5.07e-04 |  | 1.83 | PASS | yes |
| 91001 | P | 1.0102 | 691 | 624 | 0/0/0 | 0.0001 | 6 | 529,147 | 9 | 1.31e-03 | 1.86 | 1.25 | FAIL | no |
| 91002 | I | 1.0072 | 962 | 1884 | 0/0/0 | 0.0061 | 8 | 1,845,443 | 25 | 5.22e-04 |  | 0.89 | PASS | yes |
| 91002 | P | 1.0070 | 697 | 962 | 0/0/0 | 0.0004 | 6 | 451,040 | 7 | 1.55e-03 | 1.66 | 1.63 | PASS | yes |
| 91003 | I | 1.0035 | 919 | 1714 | 0/0/0 | 0.0039 | 8 | 1,792,193 | 24 | 5.13e-04 |  | 1.46 | PASS | yes |
| 91003 | P | 1.0058 | 740 | 776 | 0/0/0 | 0.0005 | 6 | 538,252 | 9 | 1.38e-03 | 1.92 | 1.43 | PASS | yes |

Confirmation: I 3/3 → **confirmed**; P 2/3 → **not confirmed**.
P/I min-bulk-ESS-per-retained-call ratio: per seed [2.573, 2.963, 2.683], geometric mean 2.735, range [2.573, 2.963].

Predictions:
- P passes all gates on 3/3 seeds (confirmed) — **failed**
- I passes all gates on 3/3 seeds (confirmed) — **held**
- P/I min-bulk-ESS-per-call ratio geometric mean >= 2 (WP4b single seed: 2.8) — **held**
- P agrees with I and with N on every functional (|z| <= 3) on every seed — **held**
- P median depth 6 (as WP4b), I median depth 8 with cap rate <= 1% — **held**

## Secondary — Stock–Watson arm A (paper-mode v3, kernel v10), seeds 91011–91013

| arm | seed | max R-hat (gated) | min bulk ESS | min tail ESS | div/inv/exh | cap rate | calls | wall s | final δ / h per chain | gates |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| A1 | 91011 | 1.0074 | 592 | 1287 | 0/0/0 | 0.0000 | 2,554,616 | 9 | 0.333/0.0061; 0.374/0.0066; 0.292/0.0065; 0.264/0.0070 | PASS |
| A2 | 91012 | 1.0071 | 463 | 796 | 0/0/0 | 0.0000 | 2,494,088 | 9 | 0.243/0.0060; 0.305/0.0069; 0.283/0.0063; 0.286/0.0061 | PASS |
| A3 | 91013 | 1.0101 | 484 | 527 | 0/0/0 | 0.0000 | 2,312,864 | 10 | 0.278/0.0069; 0.302/0.0063; 0.266/0.0065; 0.329/0.0069 | FAIL |

Pass rate 2/3; max gated R-hat per seed {"A1": 1.0074, "A2": 1.0071, "A3": 1.0101}.
