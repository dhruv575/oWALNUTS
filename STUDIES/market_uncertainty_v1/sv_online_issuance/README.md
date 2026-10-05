# Separate prospective SV issuer (research, not deployed)

`issue(capture,out,origin,config)` uses a new output directory, an immutable
receipt prefix, and only receipts at or before the scheduled origin. Features
are 15-minute pooled raw option amount; observations are30-minute perpetual
midpoint returns. Both-flow mean includes intercept, lagged midpoint return,
signed/total imbalance and log1p amount (P4); scale includes absolute imbalance
and log1p amount (K2). The native return outcome is not standardized. Training
uses at most256 scheduled rows and at least20 matured, eligible labels.

This is a distinct60-second decision deadline, not an amendment to the frozen
10-second exact-baseline issuer. Hardware admission grants remaining time minus
five seconds for cleanup/report handling; cleanup is not a real-time guarantee.
The postcompute monotonic decision clock must still be within60seconds or the
interval is withheld. The final small issuance.json write follows this decision;
no external timestamp certification is claimed. A late or failed fit, unpassed
precision, invalid runtime, or source drift produces no issued interval.

No live invocation or sampler test has run. Tests use injected fake workers.
A reviewed prospective configuration must supply unique initialization/sampler/
predictive seeds, executable/package paths and source/runtime hash bindings.
The old baseline scheduler and receipt collector are untouched. Snapshot and
preparation exceptions are persisted as not-issued records. Final/provisional
SV scoring uses a separate adapter; existing baseline score schema must reject
this new research-live-sv-issuance-v1 record.

`scheduler.py` declares every eligible half-hour origin whose horizon ends
within the bounded capture. It requires distinct per-origin initialization,
sampler and predictive seed roles. Missed origins are recorded and never
replayed. Capture termination, source drift, storage exhaustion and unverified
worker containment stop subsequent launches while retaining every planned
outcome. Ordinary precision or lateness failures remain local to their origin.
Each event records the issuance file's hash immediately for later scoring.

The scheduler requires a reviewed `frozen_live_sv_plan` configuration and uses
a 12 GiB disk floor. It has not been deployed. Eight issuer tests, six scheduler
tests and eight scorer tests passed together, including actual snapshot/feature
construction with a mocked sampler. Actual contained sampler integration and a
frozen launch configuration remain required before live deployment.
