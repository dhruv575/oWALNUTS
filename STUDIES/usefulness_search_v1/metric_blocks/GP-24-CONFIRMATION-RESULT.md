# Fresh fixed-map workflow validation

Eight fresh seed sets across four fixed maps, six workflows,48 fits. Prospectively frozen24-quantity qualification thresholds and the all-fit gate were retained.

| Workflow | Qualified fits | Retained divergences | Minimum bulk ESS | Minimum tail ESS |
|---|---|---|---|---|
| raw/walnuts_dense | 8/8 | 0 | 3561.313 | 2357.497 |
| raw/diag | 8/8 | 0 | 9575.670 | 14405.399 |
| affine/walnuts_dense | 8/8 | 0 | 1349.170 | 473.644 |
| affine/diag | 8/8 | 0 | 5260.837 | 6561.566 |
| bounded/walnuts_dense | 8/8 | 0 | 7639.299 | 4880.374 |
| bounded/diag | 8/8 | 0 | 8437.458 | 10418.200 |

Primary gate passed: True.

Failures: []

Contrasts: [{"pilot_inclusive": false, "comparator": "raw-walnuts_dense", "ratio": 5.97373545731182, "interval": [5.2123535366888865, 6.8463343982253075]}, {"pilot_inclusive": false, "comparator": "raw-diag", "ratio": 30.65264833378097, "interval": [26.868529471140988, 34.84349892540442]}, {"pilot_inclusive": false, "comparator": "affine-walnuts_dense", "ratio": 6.777761511907441, "interval": [5.3966066393590495, 8.512395692740329]}, {"pilot_inclusive": false, "comparator": "affine-diag", "ratio": 6.797058845213587, "interval": [6.527734170167554, 7.0774954587512555]}, {"pilot_inclusive": false, "comparator": "bounded-diag", "ratio": 3.493074514022183, "interval": [3.2528305165554565, 3.7471838287787826]}, {"pilot_inclusive": true, "comparator": "raw-walnuts_dense", "ratio": 2.7699907972459523, "interval": [2.4418979688228237, 3.142166099808891]}, {"pilot_inclusive": true, "comparator": "raw-diag", "ratio": 14.213477379863434, "interval": [12.413581415915944, 15.991632128064545]}, {"pilot_inclusive": true, "comparator": "affine-walnuts_dense", "ratio": 4.757028211856656, "interval": [3.837566378950404, 5.896788530492954]}, {"pilot_inclusive": true, "comparator": "affine-diag", "ratio": 4.147959297911805, "interval": [3.9391985910654634, 4.367783430913362]}, {"pilot_inclusive": true, "comparator": "bounded-diag", "ratio": 2.230857550817596, "interval": [2.066390646183385, 2.3917360684274103]}]

If any fit fails, all competitive efficiency ratios are withheld as frozen; no failed seed, workflow or functional is removed. These are fresh sampler seeds conditional on fixed exposed maps, not new data or map-training validation. Pilot/fitting costs remain necessary, and concurrent elapsed clocks are not timing evidence. The successful conditional-importance method is not superseded by this study.

A failed fixed-budget control does not establish intrinsic candidate superiority. Diagnose whether remaining failures reflect insufficient precision, numerical divergence or reference disagreement before designing any new experiment. Do not append draws to this validation or relax its thresholds. Any larger-budget confirmation needs a new frozen budget and fresh seeds; retain this outcome. No production change or goal completion.
