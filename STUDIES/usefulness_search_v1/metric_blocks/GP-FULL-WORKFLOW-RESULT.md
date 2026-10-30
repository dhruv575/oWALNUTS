# Serial complete-workflow results

Fixed budgets, four exposed-map scenarios, precompiled libraries. Process time includes child imports, setup, sampling, diagnostics and writes. This is not a precision-matched speed ranking.

| Scenario | Workflow | Qualified | Process seconds | Worst mean MCSE/reference SD | Max mean error/reference SD |
|---|---|---|---|---|---|
| 0 | raw/walnuts_dense | True | 18.027808999000005 | 0.017629159390805445 | 0.024706937489603994 |
| 0 | raw/diag | True | 42.157553318 | 0.009483317952131936 | 0.018121787925009833 |
| 0 | affine/walnuts_dense | True | 29.812834479000003 | 0.01786805940523305 | 0.02151055843862872 |
| 0 | affine/diag | True | 39.49884918100001 | 0.012530164681471532 | 0.02362399772093181 |
| 0 | bounded/walnuts_dense | True | 19.47837869999998 | 0.011469576922251725 | 0.017342277287318277 |
| 0 | bounded/diag | True | 36.55088209200002 | 0.010824887910300007 | 0.019213874762176213 |
| 0 | importance/importance | True | 19.060019029999978 | 0.008996519343348117 | 0.015158982505652348 |
| 1 | raw/diag | True | 34.872506044999994 | 0.009815275954578583 | 0.013547201963706932 |
| 1 | affine/walnuts_dense | True | 27.15522353099999 | 0.018595852133639887 | 0.020463417115167432 |
| 1 | affine/diag | True | 32.97167480999997 | 0.012683352045227405 | 0.03178845855797243 |
| 1 | bounded/walnuts_dense | True | 17.608117774999982 | 0.008774484742460713 | 0.020702941346365498 |
| 1 | bounded/diag | True | 32.93239971500003 | 0.009842550370591703 | 0.019515573526353417 |
| 1 | importance/importance | True | 17.66196716600001 | 0.009222938404327087 | 0.022083972999118837 |
| 1 | raw/walnuts_dense | True | 13.424940767999999 | 0.018258212873865223 | 0.015358396164912507 |
| 2 | affine/walnuts_dense | True | 25.390459667000016 | 0.017303856886232125 | 0.018112794860141983 |
| 2 | affine/diag | True | 37.762498669000024 | 0.013305309367206152 | 0.02750071324604816 |
| 2 | bounded/walnuts_dense | True | 18.894716963999997 | 0.013283431477426354 | 0.0104268984461366 |
| 2 | bounded/diag | True | 33.600399236000044 | 0.010606961332964633 | 0.016795491961463387 |
| 2 | importance/importance | True | 19.247142715999985 | 0.008840536446071861 | 0.021145671989135053 |
| 2 | raw/walnuts_dense | True | 12.305744909000055 | 0.02834310477512592 | 0.03282976325279883 |
| 2 | raw/diag | True | 29.090607748000025 | 0.009243098535491379 | 0.03067028141290014 |
| 3 | affine/diag | True | 32.199385060000054 | 0.014479738433484959 | 0.022529606506127918 |
| 3 | bounded/walnuts_dense | True | 17.39295630999993 | 0.010672003340799074 | 0.018484566485746406 |
| 3 | bounded/diag | True | 33.36583486400002 | 0.010288612988332302 | 0.024946542303092463 |
| 3 | importance/importance | True | 22.65203624200001 | 0.00891414068330044 | 0.023672817104416072 |
| 3 | raw/walnuts_dense | True | 16.46618369700002 | 0.01999363529317476 | 0.025065913070440638 |
| 3 | raw/diag | True | 35.39382854200005 | 0.00974225732009403 | 0.016082452196176107 |
| 3 | affine/walnuts_dense | True | 37.53583724800001 | 0.017973953213406533 | 0.016351503133837094 |

All28 qualified: True.

No method or scenario is removed. If any fails, competitive summaries are withheld. Even if all pass, these four conditional scenarios and fixed budgets do not prove a practical advantage or optimal implementation. Setup is regenerated per workflow; map training, proposal construction and achieved precision must remain visible. Native and importance ESS are not treated as equivalent.
