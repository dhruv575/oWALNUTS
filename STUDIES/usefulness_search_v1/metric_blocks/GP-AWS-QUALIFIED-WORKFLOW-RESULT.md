# Serial complete-workflow results

Fixed budgets, four exposed-map scenarios, precompiled libraries. Process time includes child imports, setup, sampling, diagnostics and writes. This is not a precision-matched speed ranking.

| Scenario | Workflow | Qualified | Process seconds | Worst mean MCSE/reference SD | Max mean error/reference SD |
|---|---|---|---|---|---|
| 0 | raw/walnuts_dense | True | 3.455219489000001 | 0.00885500138294547 | 0.014438822541626766 |
| 0 | raw/diag | True | 6.7520771880001575 | 0.009406759762778613 | 0.012535780867226438 |
| 0 | affine/walnuts_dense | True | 11.572154760999865 | 0.00919537948239655 | 0.016894044970454734 |
| 0 | affine/diag | True | 17.227459610000096 | 0.008640000228842568 | 0.014896286499842202 |
| 0 | bounded/walnuts_dense | True | 10.924484053000015 | 0.008088611678481355 | 0.012061430943926926 |
| 0 | bounded/diag | True | 28.149049303000083 | 0.00932501278084924 | 0.015809460122513896 |
| 0 | importance/importance | True | 10.241966925000042 | 0.014661955048510122 | 0.017025186955976913 |
| 1 | raw/diag | False | 48.80279386700022 | 1.8677996502353402 | 2.1260142498339705 |
| 1 | affine/walnuts_dense | True | 18.155208545999812 | 0.01422184622971486 | 0.026206995404319824 |
| 1 | affine/diag | True | 26.44959092199997 | 0.01518730369216252 | 0.0163717417895572 |
| 1 | bounded/walnuts_dense | True | 13.934513931999845 | 0.01047823554767796 | 0.010315965330646982 |
| 1 | bounded/diag | True | 32.23842051700012 | 0.011140937006269561 | 0.014540959104117944 |
| 1 | importance/importance | True | 11.001098458000342 | 0.010067370800300927 | 0.018306503853018238 |
| 1 | raw/walnuts_dense | True | 4.371501968000302 | 0.012675936813557604 | 0.016747146168809283 |
| 2 | affine/walnuts_dense | True | 11.60191341000018 | 0.00998551092194018 | 0.019053786465229844 |
| 2 | affine/diag | True | 17.932270387000244 | 0.00883841003975097 | 0.010197665714724417 |
| 2 | bounded/walnuts_dense | True | 15.436434376999841 | 0.008172373791417003 | 0.01481769496257612 |
| 2 | bounded/diag | True | 29.347469501999967 | 0.009287064225292522 | 0.016474465460052438 |
| 2 | importance/importance | True | 8.914907817999847 | 0.011678276470099233 | 0.014090467874593355 |
| 2 | raw/walnuts_dense | True | 3.508396658000038 | 0.009649493165142551 | 0.008560157765866426 |
| 2 | raw/diag | True | 5.418125797000357 | 0.008909326022471815 | 0.011744786002927304 |
| 3 | affine/diag | True | 24.1754490860003 | 0.012336157977046668 | 0.01373534183320753 |
| 3 | bounded/walnuts_dense | True | 13.893527223000092 | 0.011884671464708788 | 0.012642958622544416 |
| 3 | bounded/diag | False | 37.21881051199989 | 0.010895072024085786 | 0.02373199493045065 |
| 3 | importance/importance | True | 11.111221605000082 | 0.01327332470904539 | 0.028936339592325673 |
| 3 | raw/walnuts_dense | True | 4.168215484000029 | 0.011094235858704822 | 0.015617709666144794 |
| 3 | raw/diag | True | 12.215012175000084 | 0.010742811976578183 | 0.020648909059556436 |
| 3 | affine/walnuts_dense | True | 18.453786454000237 | 0.010147874598781583 | 0.02674133901602474 |

All28 qualified: False.

No method or scenario is removed. If any fails, competitive summaries are withheld. Even if all pass, these four conditional scenarios and fixed budgets do not prove a practical advantage or optimal implementation. Setup is regenerated per workflow; map training, proposal construction and achieved precision must remain visible. Native and importance ESS are not treated as equivalent.
