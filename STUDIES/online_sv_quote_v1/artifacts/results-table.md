| arm | N | median s | p95 s | <0.4 s | <2 s | valid (3 ref-MCSE) | valid (combined MCSE) | R-hat ok | div-free | drift in-ref90 (early/late) |
|---|---|---|---|---|---|---|---|---|---|---|
| warm50 | 250 | 0.020 | 0.044 | 1.00 | 1.00 | 0.00 | 0.03 | 0.03 | 1.00 | 0.901 (0.901/0.898) |
| warm50 | 1000 | 0.267 | 1.962 | 0.67 | 0.99 | nan | nan | nan | nan | nan (nan/nan) |
| warm200 | 250 | 0.080 | 0.176 | 1.00 | 1.00 | 0.02 | 0.52 | 0.56 | 1.00 | 0.902 (0.901/0.902) |
| warm200 | 1000 | 1.074 | 7.575 | 0.00 | 0.67 | nan | nan | nan | nan | nan (nan/nan) |
| refit | 250 | 3.066 | 19.956 | 0.00 | 0.00 | 0.09 | 0.87 | 0.93 | 1.00 |  |
| refit | 1000 | 16.708 | 69.835 | 0.00 | 0.00 | nan | nan | nan | nan |  |
| cmdstan | 250 | 6.499 | 51.471 | 0.00 | 0.00 | 0.10 | 0.82 | 0.87 | 1.00 |  |
| cmdstan | 1000 | 41.993 | 218.485 | 0.00 | 0.00 | nan | nan | nan | nan |  |
| nutpie | 250 | 1.092 | 1.542 | 0.00 | 0.99 | 0.14 | 0.96 | 1.00 | 1.00 |  |
| nutpie | 1000 | 4.474 | 5.902 | 0.00 | 0.00 | nan | nan | nan | nan |  |

{
 "K50_N250": {
  "valid_and_fast": 0.0,
  "drift_ok": true
 },
 "K50_N1000": {
  "valid_and_fast": 0.0,
  "drift_ok": false
 },
 "K50_realtime": false,
 "K200_N250": {
  "valid_and_fast": 0.016666666666666666,
  "drift_ok": true
 },
 "K200_N1000": {
  "valid_and_fast": 0.0,
  "drift_ok": false
 },
 "K200_realtime": false,
 "realtime_claim_allowed": false
}
