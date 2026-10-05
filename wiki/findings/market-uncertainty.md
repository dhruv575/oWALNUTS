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
bounded pool while preserving per-chain state. Rust and isolated release Python
checks cover exact replay, concurrency and lifecycle behavior. The demanding
T1000/G4 development pilot preserved byte-identical draws and diagnostics while
reducing complete process latency by factors of 1.924 and 1.939. See
[the archived experiment](../../STUDIES/market_uncertainty_v1/artifacts/parallel-continuation-latency-v1/RESULTS.md)
and [the API note](../../integrations/python/PARALLEL_CONTINUATION.md).

The equally parallel NumPyro follow-up finished in 31.08s and 31.72s, versus
oWALNUTS at 56.09s and 35.15s on the same two development seeds. Both reference
runs passed at 2,000 draws. The first oWALNUTS run narrowly failed one precision
gate at 2,000 draws and therefore continued to 4,000; the threshold was retained.
At the shared 2,000-draw length, oWALNUTS sampling was faster but its compilation
and adaptation costs outweighed that advantage. Evidence is preserved under
[`parallel-reference-latency-v1`](../../STUDIES/market_uncertainty_v1/artifacts/parallel-reference-latency-v1/RESULTS.md). These two pairs motivate
finer continuation increments and lower setup cost; they do not establish a
general speed ranking or statistical equivalence.

A separate bounded 48-hour receipt capture is launched under
`target/market-receipt-route-v2/exploratory-48h-v1`, with frozen launch sources
in its sibling `exploratory-48h-v1-launch` directory. Inspect process and terminal
records for its actual status. The exact baseline requires 20 matured eligible
labels: the earliest possible first forecast is about 10h45m after capture starts.
Do not lower that requirement to produce an early forecast. Even an uninterrupted
48 hours supplies only a small exploratory sample, not coverage across regimes.

The next model hypothesis is that option flow may predict volatility and tails
even if it adds little directional signal. The study now includes a normalized
Student-t stochastic-volatility target, independent density/gradient checks, and
[a proposed model and hybrid-inference design](../../STUDIES/market_uncertainty_v1/SV_MODEL_DESIGN.md).
Its four planned comparisons separate flow effects in mean and volatility.
It has not yet been fitted to market data. Both sampler adapters now exist.
The first public runs failed on extreme raw-coordinate proposals; investigation
fixed an erroneous underflow rejection, while exact prior whitening addressed
the tested geometry failure without changing the posterior. Both samplers then
passed both synthetic development fits. Public times were 14.03s/10.73s versus
reference 12.04s/16.53s, with differing stopping tiers. See the study's
[whitened pilot](../../STUDIES/market_uncertainty_v1/artifacts/sv-whitened-pilot-v1/RESULTS.md).
The speed ordering is mixed; no broad advantage or market coverage follows.

The exact-baseline online scheduler has been launched from frozen sources;
its 95 eligible origins, actual missed/issued/no-forecast statuses and runtime
identity are recorded under `target/market-online-issuance-run-v1`. A separate
terminal-capture scorer preserves interval identity and invalidates provisional
coverage affected by late gap notices. Fifteen issuer/scheduler tests and eight
scorer tests passed. A live data prefix also yielded its first default-horizon
matured return, but no market interval coverage result is available yet.

Keep future-observation predictive intervals, posterior parameter credible
intervals and repeated-sample confidence intervals explicitly distinct. The
current market deliverable is predictive uncertainty; no broad coverage
guarantee has been established.

The six-dataset synthetic comparison is terminal: all twelve intended fits
passed, with no retries or discarded failures. Public full-process cost totaled
44.633 seconds versus 56.322 seconds for the independent parallel reference;
individual paired ratios ranged from 1.004 to 1.574. Both arms used identical
physical starts, exact prior whitening and the same reporting/precision gates.
These six exploratory pairs establish computational feasibility across this
small declared prior-generated set, not market coverage, broad reliability or
a general speed qualification. All failed earlier precision checkpoints and
setup/storage costs remain charged. See the
[complete outcome](../../STUDIES/market_uncertainty_v1/artifacts/sv-fresh-dataset-comparison-v1/RESULTS.md).

The production research worker now checks each fit against the independent
NumPy density/gradient oracle. Independent JAX qualification remains separate
test evidence; the public worker does not initialize JAX. Five tests, including
actual tiny CLI runs of both backends, passed; these tiny runs intentionally
do not establish sampling precision. See
[worker validation](../../STUDIES/market_uncertainty_v1/artifacts/sv-workflow-validation-v2/validation.json).
Batched reporting reproduced all six archived checkpoint reports exactly,
including predictive random streams. Its measured path calculation fell from
1.01–2.03 seconds to 0.013–0.036 seconds; these replay timings are not an
end-to-end sampler speed result. See
[reporting evidence](../../STUDIES/market_uncertainty_v1/artifacts/sv-reporting-replay-v1/RESULTS.md).

The first actual delayed provisional scoring attempt completed and preserved
both models' insufficient-history no-forecast outcomes. It creates no interval
and supplies no coverage observation. Later terminal reconciliation remains
required; see
[the immutable score](../../STUDIES/market_uncertainty_v1/artifacts/first-provisional-score-v1/provisional-score.json).

A separate historical capability probe found September pooled BTC-option
trades on the history host and half-hour perpetual bars. The same older trade
query returned empty on the production host, so empty responses there cannot
establish zero flow. Completeness is still unproven. This route targets
retrospective event-time flow and bar-close returns, with closes available only
after bar end under an explicit publication assumption. It must remain
separate from live receipt-time midpoint forecasts. Historical data can speed
development and stress testing; genuinely future evaluation is still needed.
