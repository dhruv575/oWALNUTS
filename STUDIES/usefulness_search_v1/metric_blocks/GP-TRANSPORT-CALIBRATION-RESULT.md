# Full-chain transport calibration

All four maps and both transformations were retained. Settings were selected only from configurations passing all original-space accuracy and tail gates on every fold. This is calibration, not independent validation.

| Transform | Engine/mode | Target acceptance | Qualified folds | Geometric calls/minimum bulk ESS |
|---|---|---|---|---|
| affine | walnuts_diag | 0.9 | 4/4 | 441.18615027730334 |
| affine | walnuts_diag | 0.99 | 4/4 | 764.4204622091623 |
| affine | walnuts_dense | 0.9 | 4/4 | 401.2147767105992 |
| affine | walnuts_dense | 0.99 | 4/4 | 718.7404983781356 |
| affine | diag | 0.9 | 0/4 | 275.5006719437124 |
| affine | diag | 0.99 | 4/4 | 470.77923318071197 |
| affine | low_rank | 0.9 | 0/4 | 490.6828313018851 |
| affine | low_rank | 0.99 | 4/4 | 784.4900156452297 |
| quadratic | walnuts_diag | 0.9 | 4/4 | 78.01430921928525 |
| quadratic | walnuts_diag | 0.99 | 4/4 | 171.1213612350955 |
| quadratic | walnuts_dense | 0.9 | 4/4 | 98.94716047197753 |
| quadratic | walnuts_dense | 0.99 | 4/4 | 199.7599956958321 |
| quadratic | diag | 0.9 | 0/4 | 71.23053353529318 |
| quadratic | diag | 0.99 | 0/4 | 431.2011637206957 |
| quadratic | low_rank | 0.9 | 0/4 | 114.90435686828322 |
| quadratic | low_rank | 0.99 | 0/4 | 183.70266539079003 |

Selections:

{"transform": "affine", "engine": "walnuts", "selection": {"transform": "affine", "engine": "walnuts", "mode": "walnuts_dense", "target_accept": 0.9, "calls_per_min_bulk_ess_geomean": 401.2147767105992}}
{"transform": "affine", "engine": "native", "selection": {"transform": "affine", "engine": "native", "mode": "diag", "target_accept": 0.99, "calls_per_min_bulk_ess_geomean": 470.77923318071197}}
{"transform": "quadratic", "engine": "walnuts", "selection": {"transform": "quadratic", "engine": "walnuts", "mode": "walnuts_diag", "target_accept": 0.9, "calls_per_min_bulk_ess_geomean": 78.01430921928525}}
{"transform": "quadratic", "engine": "native", "selection": null}

The table includes unqualified configurations for diagnosis; their efficiencies are not competitive evidence. No native failure may be labeled inherent superiority without attempting a stronger baseline. In particular a missing transformed-native selection requires a separately preserved repair study before any competitive ratio. Original raw native and the successful conditional-importance control remain relevant.

COST-LEDGER.json records full pilot cost for every map and all completed calibration calls. Both transformed engines share the same map/pilot expense. Fitting invokes no target evaluations, but its original elapsed time was not measured. Concurrent calibration clocks do not establish wall-time advantage. No production change, application success, uniqueness or goal completion.
