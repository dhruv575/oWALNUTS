# Serial complete-workflow results

Fixed budgets, four exposed-map scenarios, precompiled libraries. Process time includes child imports, setup, sampling, diagnostics and writes. This is not a precision-matched speed ranking.

| Scenario | Workflow | Qualified | Process seconds | Worst mean MCSE/reference SD | Max mean error/reference SD |
|---|---|---|---|---|---|
| 0 | raw/walnuts_dense | True | 3.944956505999926 | 0.008638776608809764 | 0.019691133915971156 |
| 0 | raw/diag | True | 7.901030096999875 | 0.009577766997668566 | 0.015410018139814645 |
| 0 | affine/walnuts_dense | False | unavailable | unavailable | unavailable |
| 0 | affine/diag | False | unavailable | unavailable | unavailable |
| 0 | bounded/walnuts_dense | False | unavailable | unavailable | unavailable |
| 0 | bounded/diag | False | unavailable | unavailable | unavailable |
| 0 | importance/importance | True | 10.264635332000125 | 0.017767806664867433 | 0.020239229764155337 |
| 1 | raw/diag | True | 13.484509021000122 | 0.011098838451645535 | 0.017385269247070317 |
| 1 | affine/walnuts_dense | False | unavailable | unavailable | unavailable |
| 1 | affine/diag | False | unavailable | unavailable | unavailable |
| 1 | bounded/walnuts_dense | False | unavailable | unavailable | unavailable |
| 1 | bounded/diag | False | unavailable | unavailable | unavailable |
| 1 | importance/importance | True | 11.050219926999944 | 0.01090670968570511 | 0.021616789265321457 |
| 1 | raw/walnuts_dense | True | 4.5260257480001655 | 0.01277178847606774 | 0.014485067993487895 |
| 2 | affine/walnuts_dense | False | unavailable | unavailable | unavailable |
| 2 | affine/diag | False | unavailable | unavailable | unavailable |
| 2 | bounded/walnuts_dense | False | unavailable | unavailable | unavailable |
| 2 | bounded/diag | False | unavailable | unavailable | unavailable |
| 2 | importance/importance | True | 8.96021809900003 | 0.01408392694357415 | 0.017069030564327837 |
| 2 | raw/walnuts_dense | True | 3.9505987380000533 | 0.009164157721835346 | 0.01168200880588701 |
| 2 | raw/diag | True | 5.472951181000099 | 0.009066105531107399 | 0.01298426565065069 |
| 3 | affine/diag | False | unavailable | unavailable | unavailable |
| 3 | bounded/walnuts_dense | False | unavailable | unavailable | unavailable |
| 3 | bounded/diag | False | unavailable | unavailable | unavailable |
| 3 | importance/importance | True | 11.084266623999838 | 0.01392392362830664 | 0.017084351938587424 |
| 3 | raw/walnuts_dense | True | 4.374333621000005 | 0.010782988050076247 | 0.024052571477179874 |
| 3 | raw/diag | True | 12.124931182999944 | 0.010689203118807973 | 0.013425844071367314 |
| 3 | affine/walnuts_dense | False | unavailable | unavailable | unavailable |

All28 qualified: False.

No method or scenario is removed. If any fails, competitive summaries are withheld. Even if all pass, these four conditional scenarios and fixed budgets do not prove a practical advantage or optimal implementation. Setup is regenerated per workflow; map training, proposal construction and achieved precision must remain visible. Native and importance ESS are not treated as equivalent.
