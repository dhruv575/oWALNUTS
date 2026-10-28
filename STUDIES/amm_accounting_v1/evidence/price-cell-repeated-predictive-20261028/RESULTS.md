# Repeated-update predictive-functional verification

All twelve fixed warm/cold pairs passed diagnostic thresholds for the three
predeclared latent-increment CDFs at -.005,0,.005. The largest absolute mean
discrepancy was 2.593 combined MCSEs; none exceeded four. All 72 numerical
checks passed: maximum difference between 64- and 128-node quadrature was
4.441e-16, with independent adaptive integration at each worst-discrepancy
draw also meeting tolerance. These numerical checks cover the saved states,
not every possible posterior state or a mathematical global error bound.

All 24 input trace hashes matched the verified full-run manifest. Every warm
and cold coordinate summary was reproduced from full finite arrays with exact
expected chain/draw/dimension shapes and 1e-11 numerical tolerance. The same
ArviZ implementation was used, so this verifies reproducibility rather than
independent correctness of the diagnostic algorithm. Analysis elapsed time was
84.347 seconds under a 300-second timeout and 4 GiB address-space cap.

The complete analysis archive, source bindings and all 24 input trace bindings
were verified after download. Functional arrays and comparison tables are
preserved, including all twelve fixed slots. No seeds or draws were replaced.

Together with the coordinate results, this supports limited reliability over
three consecutive synthetic shifts at 1,024 warm draws per chain. It does not
establish a general speed advantage (the narrow-cell warm runs were slower),
historical observation validity, market forecasting calibration, economic
decision value or profitability.
