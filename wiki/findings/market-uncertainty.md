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

A separate September historical acquisition completed API-level coverage with
201,712 unique pooled BTC-option trades and 1,440 half-hour perpetual bars.
The collector subdivides saturated time windows, checks complete leaf coverage,
and rejects conflicting duplicate IDs. It used 628 requests and 121 MB of
responses in 376.6 seconds. See
[acquisition evidence](../../STUDIES/market_uncertainty_v1/artifacts/historical-september-acquisition-v1/RESULTS.md).
The history host is necessary: an earlier production-host query returned empty
for an interval where history records existed. API coverage does not certify
exchange data accuracy, publication latency, or absence of later revisions.

The frozen chronological exact baseline completed on this dataset. Its final
September 22–30 segment has 432 common scored origins. Price-only versus
flow-in-mean results were 93.52% versus 93.98% coverage for nominal 90%
predictive intervals, interval scores 0.0135421 versus 0.0135737 (lower is
better), and log scores 4.44556 versus 4.44232 (higher is better). Flow slightly
improved coverage but worsened both proper scores; this simple specification
does not demonstrate incremental predictive value. All 1,440 scheduled origins
per arm remain recorded, including 21 initial no-forecast outcomes and the
final October 1 origin with no subsequent observed label. See
[baseline evidence](../../STUDIES/market_uncertainty_v1/artifacts/historical-baseline-evaluation-v1/RESULTS.md).
These are retrospective event-time/bar-close results under explicit bar-open
timestamp and zero publication-lag assumptions, not live receipt-time midpoint
forecasts. Temporal dependence precludes an ordinary independent-binomial
coverage guarantee; genuinely future evaluation remains necessary.

A specialist Gamma/Gaussian plus elliptical/scalar-slice comparator passed six
mathematical and transition tests. Its fixed T32 diagnostic completed with
healthy chains but failed the declared endpoint-precision gate for volatility
scale and terminal log volatility. The full-joint NumPyro reference passed.
Hybrid time was 29.91 seconds versus 5.48 seconds for reference, but there is
no eligible speed comparison: precision differed and hybrid chains ran
sequentially while the reference ran in parallel. No retry or tuning followed.
See [the retained diagnostic](../../STUDIES/market_uncertainty_v1/artifacts/sv-hybrid-t32-v1/RESULTS.md).

The first historical SV pilot then fitted all four flow ablations with both
full-joint samplers at the fixed September 15 00:00 UTC validation origin.
Every fit used the preceding 256 scheduled observations, unchanged illustrative
priors, and the existing health/endpoint gates. All eight fits passed. Public
complete-process costs totaled 23.47 seconds across four fits, versus 40.19
seconds for reference; individual ranges were 5.36–6.91 and 8.11–11.16 seconds.
All source/runtime identities, CPU containment and saved coordinate transforms
verified. This is computational feasibility on one actual market posterior per
ablation, not evidence of predictive quality, reliable speed across periods, or
which flow placement is best. See
[historical SV evidence](../../STUDIES/market_uncertainty_v1/artifacts/sv-historical-pilot-v1/RESULTS.md).
The next study is a fixed rolling grid of historical forecast times, with
model-quality and matched sampler-cost comparisons reported separately.

That rolling study launched at 2026-10-05 03:09:55 UTC on its original root-owned
process. It declares 72 origins every three hours from September 22 00:00 through
September 30 21:00, four public model ablations and a matched both-flow reference
at each origin: 360 intended fits. Ablation groups rotate and paired backend order
alternates. The six-hour admission budget may leave unstarted rows, which remain
in the denominator. Only the 72 both-flow pairs support sampler comparisons;
model scores use individual and common eligible grids with the exact baselines.
Inspect `target/sv-historical-rolling-v1/run-v1/execution.json` and the original
process for completion; launch is not a result. The immutable launch snapshot is
[archived here](../../STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-launch-v1/SUMMARY.md).

The separate two-hour receipt capture completed on its original process with
one acknowledged connection, 7,148 quote messages, 474 option-trade messages
and no reported gaps. Its terminal receipts reconcile with the earlier prefix;
the prior feature values and first matured return are unchanged. Four default
forecast origins have known received-flow windows and three have matured
labels. This validates the input/reconciliation path, not interval coverage or
exchange feed completeness. See
[terminal capture evidence](../../STUDIES/market_uncertainty_v1/artifacts/horizon-terminal-v1/RESULTS.md).

Separate live SV issuance, scheduling and delayed scoring modules now exist.
They retain the historical both-flow model's four mean and two scale covariates,
but use genuine receipt-time midpoint inputs. A distinct 60-second decision
deadline includes snapshot, fit, diagnostics and hash verification; late or
unusable fits are withheld. The scheduler records each issuance hash before
later scoring and stops further launches on unverified worker containment.
Provisional scores can be withdrawn by late gap evidence. Twenty-two mocked
tests passed, including the actual snapshot/features/issuer/scorer path with a
mock sampler. See [validation evidence](../../STUDIES/market_uncertainty_v1/artifacts/live-sv-mock-validation-v1.json).
The rolling campaign subsequently completed all 360 fits, all passing, with
72 common scored origins. The no-flow SV model had mean interval score
0.01054978 versus 0.01206660 for the exact price baseline; the both-flow SV
score was 0.01059432. Flow did not improve the SV score on this development
cohort. Matched both-flow public/reference costs were 467.44/648.34 seconds,
including all 72 fits per backend. These are descriptive historical results,
not future calibration or general speed qualification. See
[full results and evidence](../../STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-v1/RESULTS.md).

After the timing campaign ended, the real contained-worker integration test
passed at 2,000 retained draws following a failed 1,000-draw precision check.
Complete issuance took 3.25 seconds; provisional and synthetic terminal scoring
agreed. Independent verification checked source/runtime identities, hardware,
reported numerical gates and scoring; it did not recompute diagnostics from
raw draws. This uses synthetic receipts and a simulated origin clock, not live
market issuance. See
[integration evidence](../../STUDIES/market_uncertainty_v1/artifacts/live-sv-production-smoke-v1/RESULTS.md).
The separate live SV scheduler has now launched on the existing 48-hour
receipt capture, using an immutable source mirror and configuration hash
`d27c6c315e0faac66f8bccaecd315481008573e222204d27394c47a14d00cf79`.
Its 95-origin schedule retains the five origins missed before launch; those
are not replayed. The initial process check confirms the scheduler is running,
but no SV interval has yet been issued. Twenty mature training observations
are required, so early scheduled decisions may also withhold forecasts.
`target/market-sv-online-issuance-run-v1` holds its plan and issuance ledger;
`target/sv-live-launch-v1/execution-handle.json` identifies the original process.
Existing exact-baseline issuance and collection remain unchanged. This launch
does not establish market calibration or future forecast availability.

Final live-SV aggregation now requires all 95 planned origins, preserves
unusable outcomes, and checks baseline comparisons against identical realized
returns. Changed upstream lineage invalidates affected forecasts without
removing them from the denominator; changed issuance identities remain hard
errors. Fourteen mocked tests passed; this is evaluation infrastructure, not
observed market performance. See
[aggregate validation](../../STUDIES/market_uncertainty_v1/artifacts/live-sv-aggregate-validation-v1.json).

Two research routes remain candidates for improving predictive quality.
First, test coarse contract-marked flow (put/call, maturity and moneyness) in
volatility dynamics against the same SV model without flow and with pooled
flow. Evidence linking buying pressure to implied-volatility shape
([Bollen and Whaley](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2004.00647.x))
does not establish prediction of realized BTC returns. Opening-position flow
used in [Pan and Poteshman](https://www.mit.edu/people/junpan/volume.pdf)
is unavailable in the current public tape. Second, only after collecting
substantially more stress-period evidence, test flow-dependent calm/stress
transition probabilities against an otherwise identical no-flow regime model.
Neither route is justified by higher coverage alone: proper predictive scores,
interval width, availability and temporal clustering of misses must be assessed
on a subsequently frozen calendar period. Current historical results are
development evidence. Future-return intervals are predictive intervals;
coefficient posterior intervals and confidence intervals for forecast
performance answer different questions.

The first route now has a separate development implementation. All 201,712
September trades retain valid required contract marks. The coverage-aware
24-bucket builder conserves pooled counts and amounts over 1,440 windows;
missing coverage rejects admission instead of implying zero trading. The
adapter compares no flow, pooled activity and marked activity in volatility,
keeping the mean at intercept plus lagged return. Training-only log-amount
scaling and explicit dimension-scaled illustrative priors are fixed choices,
not learned evidence of useful flow effects. Fifteen construction/admission
tests pass. See [feature evidence](../../STUDIES/market_uncertainty_v1/artifacts/marked-flow-conservation-v1/validation.json).

At the fixed September 15 pilot origin, all six public/reference fits passed.
The marked-activity model cost 7.53 seconds public versus 8.54 seconds reference;
the full six-fit campaign cost 48.31 seconds. Source, runtime, reported numerical
gates, paired starts and hardware checks passed. This establishes one-origin
computational feasibility, not improved forecasts. See
[pilot evidence](../../STUDIES/market_uncertainty_v1/artifacts/marked-sv-pilot-v1/README.md).
A 72-origin development comparison has launched with 156 intended fits:
72 public pooled-activity, 72 public marked-activity, and 12 matched
marked-activity reference fits. Exact canonical target comparisons permit
reuse of all 72 prior no-flow forecasts; their previous costs are excluded
from new timing comparisons. The fixed source/configuration and reuse proof
are preserved in [launch evidence](../../STUDIES/market_uncertainty_v1/artifacts/marked-sv-rolling-launch-v1/RESULTS.md).
The original process is recorded in
`target/marked-sv-rolling-v1/execution-handle.json`.
The study completed all 156 new fits successfully. Across the 72 common
origins, interval scores were 0.010549783 without flow, 0.010566725 with pooled
activity and 0.010591066 with marked activity; all three covered 90.28% of
outcomes. The richer representation did not improve scores. The 12 matched
marked-activity pairs cost 82.01 seconds public versus 115.39 seconds reference.
The full new campaign cost 1,041.78 seconds. See
[terminal evidence](../../STUDIES/market_uncertainty_v1/artifacts/marked-sv-rolling-v1/RESULTS.md).
Further complexity tuning on this same development history is stopping;
validation on a separately fixed period and the ongoing live schedule remain
necessary. The live model is not changed after inspecting these results.

A separate October validation is now running: 32 fixed forecast origins and
64 paired no-flow SV fits, compared with the unchanged exact price-only
baseline. The scientific choices were frozen before acquiring the historical
October bars. Twelve preparation/reporting tests and an independent causal
audit passed. See [October launch evidence](../../STUDIES/market_uncertainty_v1/artifacts/sv-october-validation-launch-v1/RESULTS.md).
This four-day retrospective comparison assumes zero publication lag and does
not establish general calibration; existing live October receipts also mean
the market period was not universally unseen. Terminal results are pending.
