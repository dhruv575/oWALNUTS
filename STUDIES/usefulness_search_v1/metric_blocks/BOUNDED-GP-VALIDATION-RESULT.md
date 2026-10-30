# Fresh fixed-map workflow validation

Eight fresh seed sets across four fixed maps, six workflows,48 fits. Original qualification thresholds and the all-fit gate were retained.

| Workflow | Qualified fits | Retained divergences | Minimum bulk ESS | Minimum tail ESS |
|---|---|---|---|---|
| raw/walnuts_dense | 8/8 | 0 | 3010.840 | 2173.389 |
| raw/low_rank | 7/8 | 1 | 3022.303 | 4309.248 |
| affine/walnuts_dense | 8/8 | 0 | 2704.101 | 1572.997 |
| affine/diag | 8/8 | 0 | 4930.227 | 6785.220 |
| bounded/walnuts_dense | 8/8 | 0 | 9731.746 | 7473.372 |
| bounded/low_rank | 7/8 | 2 | 8843.009 | 10780.254 |

Primary gate passed: False.

Failures: [{"fold": 2, "seed": 948700005, "transform": "bounded", "mode": "low_rank", "failed_gates": ["divergences"]}, {"fold": 3, "seed": 948700008, "transform": "raw", "mode": "low_rank", "failed_gates": ["divergences"]}]

Contrasts: []

If any fit fails, all competitive efficiency ratios are withheld as frozen; no failed seed, workflow or functional is removed. These are fresh sampler seeds conditional on fixed exposed maps, not new data or map-training validation. Pilot/fitting costs remain necessary, and concurrent elapsed clocks are not timing evidence. The successful conditional-importance method is not superseded by this study.

A failed fixed-budget control does not establish intrinsic candidate superiority. Diagnose whether remaining failures reflect insufficient precision, numerical divergence or reference disagreement before designing any new experiment. Do not append draws to this validation or relax its thresholds. Any larger-budget confirmation needs a new frozen budget and fresh seeds; retain this outcome. No production change or goal completion.
