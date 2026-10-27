# Opt-in exact-t5 resident comparison: four complete updates

2026-10-27. Development cost/equivalence check only. All four planned updates passed.
The explicit exact_t5 backend reduced directly measured complete refresh time from
approximately2.45seconds to0.90seconds on this fixed workload, while retaining
byte-identical posterior draws and unchanged predictive summaries within declared
numerical tolerances. SciPy remains the default; the exact backend is research opt-in.

| Update | Archived SciPy total (s) | Exact-t5 total (s) | Native sampling (s) | Summaries plus bookkeeping (s) |
|---|---:|---:|---:|---:|
|1|2.44015|0.89941|0.23888|0.66011|
|2|2.45286|0.90510|0.24232|0.66230|
|3|2.45256|0.90085|0.24118|0.65921|
|4|2.46284|0.90223|0.24413|0.65762|

Median complete costs are2.45271seconds and0.90154seconds, a descriptive2.72x ratio.
These are directly measured complete ticks, not sums of independently measured
sampling and arithmetic. JSON persistence and baseline equivalence checks are
outside the tick timer. The new backend initialization/JIT took0.17188seconds,
outside per-tick cost but inside the9.08977second supervised envelope. All eight
focused tests passed first in0.813seconds. Actual Python peakRSS was282,230,784bytes.

This is four fixed updates on the same instance after a restart, compared to an
archived run, not a randomized throughput/latency benchmark. It remains above the
inherited0.4second research threshold; no market/economic latency requirement has
been established. It does not qualify posterior accuracy, forecasting calibration,
pricing, profitability or deployment. No quadrature order or sampling budget changed.

## Equivalence and exact scope

N250/K400, four chains, depth10/refinement8, original initial fit/adaptation, all
seeds/data, frozen window remap and appended0innovation/mass1 are unchanged.
Full configuration, tuning, adaptation, native identity, runtime package versions,
and generated data were checked against the pinned original successful baseline.
All four saved compact NumPy files are byte-identical to baseline (not just close).
Scale quantiles are exactly unchanged. Maximum return endpoint difference is
6.938893903907228e-18, below the predeclared1e-10 times baseline90% interval-width
threshold. No missing, failed, interrupted or unattempted updates remain.

The byte-preserved validated Student-t5 numerical implementation replaces only
CDF dispatch through an instance-level adapter. Frozen original processor is
untouched; no module-global monkeypatch. GH64/128, all draws, roots, residual and
cross-order checks, chunk512 and64MiB cache per rule are unchanged. Each row records
explicit backend identity and exact/base/adapter hashes. The backend rejects nu!=5.

Frozen candidate source530a8e36; source archive SHA256
`8297eec3ce2e4c329e26b59fb161f674718c156109caf22020457f6dd474eca7`.
Native SHA256`db2c445a7a94da67d55d22d3b367c44544630655f07c88068e5456a2c7d93863`
was verified before launch. Environment prefix and NumPy2.4.6/SciPy1.18.1/
numba0.67.0/llvmlite0.49.0/owalnuts0.3.0 match the archived baseline.

One authorized envelope started18:03:32UTC and ended18:03:42UTC, supervisor1889,
with180seconds execution budget and bounded teardown. It passed all eight tests,
all four exact-draw/equivalence checks, and post-run source integrity. Owned process
group drained. No retry or extra study was run. Downloaded artifact SHA256
`c58519a10837621f3a09881207c974e6cb99fe6fb9fa4ebdeb7d77e9007f7e29` was verified
locally; each compact hash and its complete bytes were independently compared with
baseline. Parent received all-clear to stop the instance after retrieval.

Original evidence is in run/, preflight.json and source/.../FUSED-MANIFEST.json.
summary.json is a derived report; original outputs remain byte-preserved.
CHECKSUMS.sha256 covers this packet except itself. Existing baseline infrastructure
failure and previous smoke outputs remain untouched in host-development-20261027/.

## Remaining work

Fresh multi-seed, multi-stream tests must establish full-return posterior accuracy
against trustworthy independent references and separately assess predictive
calibration with meaningful forecast baselines. Neither follows from numerical
equivalence on these four already-selected updates. Numerical summaries alone
remain approximately0.66seconds, above the inherited0.4second research benchmark;
further cost work requires its own bounded plan and must preserve correctness.
No deployment readiness or profitability claim is supported. Parent confirmed the
AWS instance stopped after verified artifact retrieval; no remote work remains.
