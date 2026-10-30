# Stronger transformed-native calibration

This adds16 fits to the preserved original16 quadratic native fits. Same maps/seeds, unchanged diagnostic gates; this is baseline calibration, not validation.

| Mode | Target acceptance | Qualified folds | Geometric calls/minimum bulk ESS |
|---|---|---|---|
| diag | 0.9 | 0/4 | 71.23053353529318 |
| diag | 0.99 | 0/4 | 431.2011637206957 |
| diag | 0.999 | 4/4 | 265.88432536974994 |
| diag | 0.9999 | 1/4 | 346.1829723878816 |
| low_rank | 0.9 | 0/4 | 114.90435686828322 |
| low_rank | 0.99 | 0/4 | 183.70266539079003 |
| low_rank | 0.999 | 3/4 | 321.1319901687118 |
| low_rank | 0.9999 | 3/4 | 366.71286285360947 |

Selection: [{"transform": "quadratic", "engine": "native", "selection": {"transform": "quadratic", "engine": "native", "mode": "diag", "target_accept": 0.999, "calls_per_min_bulk_ess_geomean": 265.88432536974994}}]
Additional native calibration gradient calls: 11992206.

Unqualified rows are diagnostic only. If a selection exists, freeze it for a new-seed comparison with the selected quadratic WAL configuration, affine configurations and raw controls; retain all four maps and account for full pilot/fitting work. Otherwise report the remaining qualification gap. No competitive or goal-completion claim is made from these calibration outcomes.
