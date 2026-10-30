# Fresh fixed-map workflow validation

Eight fresh seed sets across four fixed maps, six workflows,48 fits. Original qualification thresholds and the all-fit gate were retained.

| Workflow | Qualified fits | Retained divergences | Minimum bulk ESS | Minimum tail ESS |
|---|---|---|---|---|
| raw/walnuts_dense | 6/8 | 0 | 488.393 | 226.141 |
| raw/low_rank | 8/8 | 0 | 604.906 | 1024.404 |
| affine/walnuts_dense | 7/8 | 0 | 712.949 | 351.930 |
| affine/diag | 8/8 | 0 | 1262.376 | 1786.511 |
| quadratic/walnuts_diag | 8/8 | 0 | 2005.105 | 1420.422 |
| quadratic/diag | 3/8 | 81 | 230.540 | 40.633 |

Primary gate passed: False.

Failures: [{"fold": 0, "seed": 948400001, "transform": "raw", "mode": "walnuts_dense", "failed_gates": ["tail", "sd_error"]}, {"fold": 1, "seed": 948400004, "transform": "quadratic", "mode": "diag", "failed_gates": ["divergences"]}, {"fold": 2, "seed": 948400005, "transform": "quadratic", "mode": "diag", "failed_gates": ["divergences"]}, {"fold": 2, "seed": 948400006, "transform": "quadratic", "mode": "diag", "failed_gates": ["rhat", "bulk", "tail", "divergences", "sd_error"]}, {"fold": 3, "seed": 948400007, "transform": "affine", "mode": "walnuts_dense", "failed_gates": ["rhat", "tail"]}, {"fold": 3, "seed": 948400007, "transform": "quadratic", "mode": "diag", "failed_gates": ["divergences"]}, {"fold": 3, "seed": 948400008, "transform": "quadratic", "mode": "diag", "failed_gates": ["divergences"]}, {"fold": 3, "seed": 948400008, "transform": "raw", "mode": "walnuts_dense", "failed_gates": ["tail"]}]

Contrasts: []

If any fit fails, all competitive efficiency ratios are withheld as frozen; no failed seed, workflow or functional is removed. These are fresh sampler seeds conditional on fixed exposed maps, not new data or map-training validation. Pilot/fitting costs remain necessary, and concurrent elapsed clocks are not timing evidence. The successful conditional-importance method is not superseded by this study.

A failed fixed-budget control does not establish intrinsic candidate superiority. Diagnose whether remaining failures reflect insufficient precision, numerical divergence or reference disagreement before designing any new experiment. Do not append draws to this validation or relax its thresholds. Any larger-budget confirmation needs a new frozen budget and fresh seeds; retain this outcome. No production change or goal completion.
