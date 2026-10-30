# Direct bounded-map full-chain calibration

All four maps and equal six-setting searches per engine are retained. The old bounded-feature screen remains failed on its relative tail gate; this is a separate direct experiment.

| Transform | Mode | Target acceptance | Qualified folds | Retained divergences | Geometric calls/minimum bulk ESS |
|---|---|---|---|---|---|
| bounded | walnuts_diag | 0.9 | 4/4 | 0 | 72.9112044690667 |
| bounded | walnuts_diag | 0.99 | 4/4 | 0 | 145.3464566171182 |
| bounded | walnuts_diag | 0.999 | 4/4 | 0 | 313.7602266563847 |
| bounded | walnuts_dense | 0.9 | 4/4 | 0 | 71.83998083338263 |
| bounded | walnuts_dense | 0.99 | 4/4 | 0 | 144.87820472799413 |
| bounded | walnuts_dense | 0.999 | 4/4 | 0 | 299.0099862874673 |
| bounded | diag | 0.9 | 0/4 | 78 | 77.89369424735165 |
| bounded | diag | 0.99 | 3/4 | 1 | 129.86905727254975 |
| bounded | diag | 0.999 | 4/4 | 0 | 248.55422344835492 |
| bounded | low_rank | 0.9 | 0/4 | 106 | 91.06989193536036 |
| bounded | low_rank | 0.99 | 4/4 | 0 | 169.29417379593224 |
| bounded | low_rank | 0.999 | 4/4 | 0 | 308.1492541047268 |
| quadratic | walnuts_diag | 0.9 | 4/4 | 0 | 88.79881360811153 |
| quadratic | diag | 0.999 | 3/4 | 1 | 279.04095222259417 |

Selections: [{"transform": "bounded", "engine": "walnuts", "selection": {"transform": "bounded", "engine": "walnuts", "mode": "walnuts_dense", "target_accept": 0.9, "calls_per_min_bulk_ess_geomean": 71.83998083338263}}, {"transform": "bounded", "engine": "native", "selection": {"transform": "bounded", "engine": "native", "mode": "low_rank", "target_accept": 0.99, "calls_per_min_bulk_ess_geomean": 169.29417379593224}}]

All-fit calibration gradient costs: {"walnuts": 12044749, "native": 11927951}

Costs above exclude full pilot generation and fitting; retain the original map-pilot ledger for both transformed engines. Unqualified rows are diagnostic only. No competitive ratio or generality claim is justified by calibration selection. Fresh validation with strong raw/affine/native controls and original-space gates is required, along with complete pilot/fitting expense and serial timing before any practical-value claim. No production change, novelty claim or goal completion.
