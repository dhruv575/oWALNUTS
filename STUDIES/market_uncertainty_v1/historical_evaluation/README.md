# Historical market interval evaluation

This route evaluates next-half-hour BTC-PERPETUAL **bar-close returns** using
pooled BTC-option trade flow. It is a retrospective research workflow. The live
receipt-time midpoint workflow is separate.

`evaluate.py` reconstructs the dataset from the collector's raw responses before
fitting anything. It requires a complete terminal acquisition, matching source
and protocol hashes, complete unsaturated trade windows, agreeing duplicate
trade IDs, and a complete half-hour bar grid. The exported trades and bars must
equal that reconstruction. An empty response from another host is not evidence
of zero option flow.

## Timing and model contract

- Treat candle timestamps as bar opens and the close as available at bar end.
  Zero publication lag is an explicit replay assumption, not a measured fact.
- At each origin use option prints in `[origin - 15 minutes, origin)` and a
  lagged return ending at that origin. Amount is raw underlying-coin amount,
  not delta exposure; direction is the taker direction.
- Fit only labels that have matured by the origin, with a rolling 256-origin
  window and at least 20 eligible labels. Standardize covariates using that
  training window; leave returns in native log-return units.
- Compare an intercept/lag-return model with one adding flow imbalance and
  log total amount. Both use the exact conjugate posterior in
  `forecast_baseline/forecast.py`.
- Preserve all scheduled origins. No forecast and no observed future label
  are separate states; neither counts as coverage.

The resulting intervals are Bayesian posterior predictive observation
intervals. Parameter credible intervals and frequentist confidence intervals
answer different questions. Coverage across dependent market returns remains
an empirical diagnostic, not a general guarantee.

## Run the frozen September baseline

From the repository root, with the existing acquisition and isolated Python
environment available:

```powershell
target/python-workflow-env/Scripts/python.exe STUDIES/market_uncertainty_v1/historical_evaluation/evaluate.py --acquisition target/market-history-acquisition-v1/september-development-v1 --protocol target/market-history-acquisition-v1/protocol-frozen-v1.json --collector-source target/market-history-acquisition-v1/collector.py --recipe target/historical-baseline-evaluation-v1/recipe-frozen.json --out target/historical-baseline-evaluation-v1/reproduction-new
```

Use a new output directory. The command verifies the exact frozen source
bindings; changing sources requires a separately identified recipe, not editing
the existing evidence. This command is a reproduction of an already inspected
historical experiment, not a new qualification study.

The September split is initialization through September 14, validation through
September 21, and exploratory evaluation September 22–30. The final scheduled
October 1 00:00 origin has no subsequent observed bar in this acquisition and
is retained unscored. The original results and complete denominators are in
[`historical-baseline-evaluation-v1`](../artifacts/historical-baseline-evaluation-v1/RESULTS.md).

## Use the same inputs for stochastic volatility

`sv_prototype/historical_inputs.py` accepts the verified flat rows directly.
It builds the mean and volatility designs for `neither`, `mean`, `scale`, or
`both` flow ablations. Every model includes the lagged return in its mean.
Missing outcomes retain their latent time steps; unknown scale forcing rejects
the fit. Current and future labels are never used to construct a forecast.

The full-joint sampler workflow checks independent normalized density/gradient
agreement, then requires chain diagnostics and endpoint Monte Carlo precision
before calling a fit usable. A completed process alone does not imply a usable
interval. The first matched market pilot is preserved in
[`sv-historical-pilot-v1`](../artifacts/sv-historical-pilot-v1/RESULTS.md).

For model comparisons, report availability separately from interval score,
width, coverage, and lower/upper misses on common forecast origins. For sampler
comparisons, match the posterior, starts, precision gates and complete costs;
include setup and failed attempts. Neither narrow intervals nor faster failed
fits count as a successful workflow.
