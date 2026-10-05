# Market uncertainty: data, model and computation

The practical objective is to issue useful uncertainty estimates from market
information available at a stated decision time. Three separate results are
required: observable forecast targets, calibrated and informative predictions,
and affordable inference. A sampler convergence pass establishes none of the
other two by itself.

## Current direction

The exploratory workflow is documented in
[`STUDIES/market_uncertainty_v1`](../../STUDIES/market_uncertainty_v1/README.md).
It pools option trade flow and predicts independently received BTC-PERPETUAL
midpoint returns. This is a different estimand from the earlier sparse
per-contract option trade return. It is not a BTC spot index, executable P&L,
causal flow impact, or evidence about U.S.-listed options.

The committed receipt collector and causal feature builder passed 15 tests and
an actual two-minute integration check. Raw messages and source snapshots are
archived with hashes. The short capture supports two-second pipeline checks;
the default 15-minute feature window and 30-minute return horizon correctly
produce no usable origins from it. A separate bounded two-hour capture is in
progress; its launch manifest is at
`target/market-receipt-route-v2/horizon-capture-v1-launch`. Do not infer completion
from this page: inspect the actual process and terminal output.

## Evidence that changed the direction

The old sparse-panel chronological diagnostic covered 49/64 scoreable outcomes
with nominal 90% intervals, both with and without a simple flow predictor.
There were 764 scheduled contract/origin cells, not 764 observed returns.
This is a negative descriptive calibration result on previously inspected data.
The study README links its executable record. Pooling across contracts resolves
some observation scarcity, but does not establish a predictive flow effect.

A new synthetic robust state-space pilot compares a specialized blocked Gibbs
algorithm, two NumPyro parameterizations and oWALNUTS on the same posterior.
The blocked algorithm exploits exact Gaussian conditional latent-path updates;
it is a competing algorithm, not an oWALNUTS speedup. Initial results and a
corrected oWALNUTS adapter run are in `target/market-compute-route-v1`.
The original adapter normalization failure is retained. These are exploratory
single-fixture results, not a repeated speed qualification or market validation.

## Next decisive checks

1. Exercise one complete causal forecasting loop, preserving insufficient
   history and missing inputs instead of forcing an interval.
2. Compare price-history-only and flow-augmented predictions on the same
   chronological origins, reporting availability, interval width, coverage and
   proper scores. Collect enough calendar blocks and regimes to assess them.
3. Compare complete inference costs at matched endpoint precision, including
   specialized state-space algorithms. If blocked updates dominate, investigate
   an exact linear-state block coupled to oWALNUTS for non-Gaussian volatility
   and global parameters, rather than claiming generic sampling is necessary.

Parallel continuation was integrated on main as `4fe485d`. The default stays
single-threaded; explicit multiple threads advance independent chains in a
bounded pool while preserving per-chain state. Rust and isolated debug Python
checks cover exact replay, concurrency and lifecycle behavior. A separate release
build and latency experiment are pending; the old attested study runtime was
not replaced. See [the API note](../../integrations/python/PARALLEL_CONTINUATION.md).

Keep future-observation predictive intervals, posterior parameter credible
intervals and repeated-sample confidence intervals explicitly distinct. The
current market deliverable is predictive uncertainty; no broad coverage
guarantee has been established.
