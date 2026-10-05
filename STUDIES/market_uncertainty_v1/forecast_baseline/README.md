# Exact chronological Bayesian regression baseline

This interface is a solvable comparison model and an oracle for later sampler checks. It does not replace the demanding stochastic-volatility target, establish market coverage, or prove predictive value from order flow.

For each thirty-minute origin it compares price-history-only regression against price-history plus pooled option flow. It uses only earlier rows with outcomes whose availability time has passed. Missing current anchors, missing regular previous anchors, or unknown flow produce explicit no-forecast outcomes. The operational minimum remains **20 mature eligible labels**. A two-hour capture is therefore a data-plumbing check, not enough history to fit this procedure. Covariate scaling is fitted only to eligible past training rows; outcomes stay in native log-return units. Each refit has a declared zero-mean prior in that training-standardized coordinate system.

The model is Normal–Inverse-Gamma: beta conditional on variance has covariance 100 times that variance; inverse-gamma shape3/scale0.0002. The exact predictive Student-t includes both coefficient uncertainty and observation noise. Conditional-mean and coefficient credible intervals are reported separately. A zero covariate vector produces a point conditional-mean interval while retaining predictive noise. Nonfinite/boolean/nonpositive hyperparameters are rejected. Input receipt/anchor semantics are an upstream contract: this module hashes its input, but does not independently authenticate arbitrary caller-provided availability flags.

Validation: **11 tests and 15 subtests passed**, covering prior-only controls, future labels and future covariates, immature labels, raw-coordinate covariance transport, no history/flow, predictive versus mean width, wrong horizons, invalid hyperparameters, zero inputs and collinearity. The actual subprocess CLI smoke uses 30 deterministic synthetic rows; all 60 intended model/origin outputs remain, with **18 forecasts and 42 no-forecast outcomes**. It preserves the 20-label minimum. Evidence and exact executed sources are under `synthetic-cli-v1/`. These are synthetic interface results, not market performance.

From the repository root:

```powershell
python -m pytest target/market-forecast-interface-v1/test_forecast.py -q
python target/market-forecast-interface-v1/forecast.py --features PATH-TO-FEATURES.json --output NEW-FORECASTS.json
```

Outputs are exclusive and include feature/source hashes, numerical-library version and procedure minimum history. Input/source bytes are checked again before writing. The next small oracle test should freeze an identical standardized design and prior, sample the same joint beta/log-variance target with oWalnuts, and compare with these exact parameter and observed-predictive distributions. Such a check is correctness evidence on an easy target, not hard-case qualification.
