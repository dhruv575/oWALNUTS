# September historical baseline: frozen-recipe result

This is retrospective event-time pooled BTC option amount versus the next BTC-PERPETUAL traded bar-close return. It is not a receipt-time midpoint forecast. The frozen zero-publication-lag assumption treats each completed close as available at bar end. All returned option prints, including retained combo/block metadata, are included by the acquisition protocol. Raw response reconstruction, complete trade-window coverage and the complete 1,440-bar grid passed before fitting.

Both exact Bayesian baselines used identical scheduled origins, at least20 matured training labels, a rolling256-origin lookback, and training-only feature scaling. The flow model adds signed-amount imbalance and log1p(total amount) to intercept/lag-return. Priors and recipe were frozen before evaluation; no retuning or retries occurred.

| Phase | Scheduled per arm | Forecasts | Scored pairs | Price coverage | Flow coverage |
|---|---:|---:|---:|---:|---:|
| Initialization |671|650|650|95.38%|95.23%|
| Validation |336|336|336|92.56%|92.26%|
| Exploratory evaluation |433|433|432|93.52%|93.98%|

Each arm retained21 initial no-forecast rows. The433 final-phase scheduled origins include October1 00:00, whose next-bar outcome is absent; its forecast is retained but unscored. No missing outcome is counted as covered.

On the432 common scored final-phase origins, price-only versus flow-added mean interval scores were0.0135421 versus0.0135737 (lower is better); mean log scores4.44556 versus4.44232 (higher is better). Mean widths were0.0100890 versus0.0100768. Price lower/upper misses were18/10; flow17/9. Flow slightly improved coverage but slightly worsened both proper scores: this frozen simple linear specification does not establish useful incremental flow prediction. Validation interval score slightly favored flow, while log score did not. No significance or iid binomial interval is claimed for dependent chronological observations.

Verified worker evaluation took4.394s; observed shell invocation took5.748s including startup. All2,880 intended model/origin outcomes are retained. Source and exact recipe hashes, verified features and complete results are archived; acquisition raw data remain external and hash-bound. This is exploratory historical evidence, not certified coverage, executable trading value or genuinely future evaluation.
