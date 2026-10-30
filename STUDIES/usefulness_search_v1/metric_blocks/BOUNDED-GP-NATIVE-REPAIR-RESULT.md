# Direct bounded-map full-chain calibration

Separate native calibration after the failed bounded validation. Four configurations per transform, all four fresh seeds,8000 retained draws per chain. Earlier failures remain unchanged. No WALNUTS competitive claim follows from this additional baseline search.

| Transform | Mode | Target acceptance | Qualified folds | Retained divergences | Geometric calls/minimum bulk ESS |
|---|---|---|---|---|---|
| raw | diag | 0.999 | 4/4 | 0 | 1662.5099230854894 |
| raw | diag | 0.9999 | 4/4 | 0 | 1819.952800063808 |
| raw | low_rank | 0.999 | 3/4 | 0 | 4412.354244222883 |
| raw | low_rank | 0.9999 | 2/4 | 0 | 32005.996178191195 |
| bounded | diag | 0.999 | 4/4 | 0 | 193.53261465683448 |
| bounded | diag | 0.9999 | 4/4 | 0 | 196.64755805667207 |
| bounded | low_rank | 0.999 | 4/4 | 0 | 205.46831740872022 |
| bounded | low_rank | 0.9999 | 4/4 | 0 | 258.44660739520543 |

Selections: [{"transform": "raw", "engine": "native", "selection": {"transform": "raw", "engine": "native", "mode": "diag", "target_accept": 0.999, "calls_per_min_bulk_ess_geomean": 1662.5099230854894}}, {"transform": "bounded", "engine": "native", "selection": {"transform": "bounded", "engine": "native", "mode": "diag", "target_accept": 0.999, "calls_per_min_bulk_ess_geomean": 193.53261465683448}}]

All-fit calibration gradient costs: {"walnuts": 0, "native": 212941538}

Costs above exclude full pilot generation and fitting; retain the original map-pilot ledger for both transformed engines. Unqualified rows are diagnostic only. No competitive ratio or generality claim is justified by calibration selection. Fresh validation with strong raw/affine/native controls and original-space gates is required, along with complete pilot/fitting expense and serial timing before any practical-value claim. No production change, novelty claim or goal completion.
