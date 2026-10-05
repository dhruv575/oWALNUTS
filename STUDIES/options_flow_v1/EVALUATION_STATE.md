# Evaluation state and remaining evidence

The objective remains a useful, demanding uncertainty-estimation workflow that
oWALNUTS makes materially easier or faster. Implementation tests, a fast single
posterior, and healthy sampling diagnostics do not independently establish that
objective. `DESIGN_REVIEW.md` and `../../wiki/methods.md` define the distinctions
and prospective-study discipline; proposed numerical thresholds there are not
additional user requirements.

| Requirement | Current evidence | What remains |
| --- | --- | --- |
| Correct implementation and continuation | Target parity, replay, ownership/reset checks, attested runtime, integrated repeated-fit controller and six actual compatibility proofs | Continue validating new accuracy-study adapters and broader failure conditions |
| Material practical cost or effort benefit | Fresh 36-pair T1000 comparison: 75.27s public versus 89.43s reference; ratio 1.188, interval [1.069, 1.320]; predefined speed criterion not met | Diagnose and improve costs, then validate changes on fresh evidence; broader workload benefit remains unproven |
| Trustworthy posterior interval endpoints | Independently audited 64-fit reference bank; all 48 accuracy checks passed in the fresh paired comparison | Fresh-dataset calibration and robustness beyond this fixed posterior |
| Repeated-data calibration | Demanding T1000 screen: 32/32 public and 8/8 reference usable; no calibration qualification. Earlier T32 local-level feasibility had 6/8 public and 1/2 reference usable | Prospectively powered calibration and broader robustness |
| Useful market workflow | As-of anchor bug fixed; sparse verified panel retained; activity-based collector tested and audited | Suitable data and chronological interval scoring; neither available panel nor failed acquisition establishes utility |
| Honest accounting and reproducibility | Frozen protocols, failed/unstarted denominators, independent audits, exact source archives, local raw-file manifests | Continue these requirements for each subsequent experiment |

## Current decision

The completed bank and fresh paired comparison supersede the pre-execution
statements in the historical account below. See
[`posterior-reference-bank-v1/RESULTS.md`](artifacts/posterior-reference-bank-v1/RESULTS.md)
and [`fresh-paired-comparison-v1/RESULTS.md`](artifacts/fresh-paired-comparison-v1/RESULTS.md).
The latter result and independent audits are archived in commit `9e4bcd2`.
Both workflows completed 36/36 usable fits and passed the accuracy family.
The practical-speed rule required a reference/public interval lower bound above
1.25; it failed. Preserve this decision while developing improvements.

The demanding fresh-dataset resource screen is archived in commit `413bda8`; see
[`demanding-calibration-screen-v1/RESULTS.md`](artifacts/demanding-calibration-screen-v1/RESULTS.md).
All 40 fits were usable. Eight matched controller-cost totals were 688.706s public
and 633.708s reference, excluding aggregate reporting; this descriptive reversal
reinforces target-dependent performance and is not a speed qualification. Reporting
added 2,157.532s to 3,645.807s execution. Coverage remains unresolved.

An explicit shared pre/post validation API now reproduces all 40 saved screen
records exactly, with 755 independent audit checks passing. Its alternate replay
took 611.155s internally (611.333s wrapped); the original reporting cost remains
unchanged. The replay adds raw-artifact checks and omits coverage-summary
generation, so it is not a matched end-to-end speed comparison. The feasibility
controller still uses the legacy reporting path. See
[`report-provenance-optimization-v1/RESULTS.md`](artifacts/report-provenance-optimization-v1/RESULTS.md)
and [`COHORT_VALIDATION.md`](COHORT_VALIDATION.md).

The shared-log-volatility likelihood prototype produced about 15% lower target-call
cost in a two-order microbenchmark, but its independent audit failed runtime
identity checks: the launcher imported the main editable package instead of the
configured attested worktree package. The observed result and failed audit are
preserved in
[`mixed-target-optimization-v1/RESULTS.md`](artifacts/mixed-target-optimization-v1/RESULTS.md).
It is not accepted performance evidence for the intended runtime. The correction
explicitly selects the package and verifies imported paths and hashes before
compilation and after timing. No sampling benefit or default promotion follows.

The separate corrected runtime experiment has now completed with 246 independent
audit checks passing. Both processes loaded the intended adapter and native
extension. Across 24 blocks and 36,000 calls, pooled median target costs were
76.723 microseconds for the baseline and 66.111 for the candidate; the median
paired baseline/candidate ratio was 1.1347. Three of twelve pairs were slower for
the candidate, all in the reverse compilation-order process, whose median ratio
was only 1.0390 (forward order: 1.1720). These dependent loop timings support
further development, not a statistically qualified or end-to-end speed claim.
The failed earlier experiment remains separate. See
[`mixed-target-optimization-v4/RESULTS.md`](artifacts/mixed-target-optimization-v4/RESULTS.md).

The likelihood is now available as an explicit dense/mixed/block32 development
variant; defaults are unchanged. After propagating candidate identity to every
continuation attempt and tier, 22 focused and continuation tests passed. An
attested integrated 18-case boundary check found zero candidate-only rejections
and six shared nonfinite cases. This supports a bounded workflow experiment,
not a global numerical-safety or sampling-benefit claim. See
[`SHARED_LOGVOL_LIKELIHOOD.md`](SHARED_LOGVOL_LIKELIHOOD.md).

Next work separates workflow cost improvements, calibration across demanding
fresh datasets, and viable chronological market data. Small feasibility cohorts
and fixed-target repetitions cannot replace repeated-data or market validation.

The upcoming likelihood comparison retains the existing single-CPU procedure.
Parallel continuation is now implemented separately on main (commit `4fe485d`),
with exact replay and lifecycle tests; see
`integrations/python/PARALLEL_CONTINUATION.md`. The previously attested study
runtime remains unchanged, and `ContinuedReference` still uses sequential chains.
A multicore latency study must build and identify its own release runtime and
compare an equally capable parallel reference. No speed result follows from the
correctness tests or the single-CPU likelihood experiment.

## Historical development decisions (before the completed bank and comparison)

The A/B/A compatibility check and actual-market timing study are complete.
The short compatibility fits were correctly rejected under the production cap;
all twelve production-policy market fits passed. Keep individual successful fits
separate from whole-cohort success in subsequent studies, and retain all failed
attempts and their costs. The independent timing audit passed 577 checks.

The bounded correlated analytic study terminated with four failed sentinels
and 24 unstarted main trials. Its CLI passed a string output directory to a
worker requiring a Path; no bank result was serialized. This is an integration
failure, not an accuracy result. Preserve the attempt and costs, fix the entry
point with regression coverage, and move to the actual posterior resource
pilot without automatically repeating the analytic campaign. The independent Gaussian-AR
indicator covariance is a finite-sample variance control; translating it into
quantile uncertainty uses a delta approximation, not an exact quantile interval.
Preserve the existing equivalence tolerance and all known failures. This study
must not become an open-ended search for a favorable analytic result.

The actual posterior pilot used the existing T1000/G4 flow fixture and its
strongest tested reference: associative mixed-coordinate NumPyro at target
acceptance .9. The noncentered reference failed both optimized long comparisons
and is not the strongest baseline. The public comparator remains the attested
mixed-coordinate continuation workflow.

The four-fit resource pilot is now terminal: both reference workflows completed
in 282.06 and 268.00 seconds and passed both checkpoint gates. Both public
samplers completed healthy 8k draws, but the resource adapter incorrectly
required its own package initializer in the legacy sampler source record.
Their resource outcomes remain failed. All four outcomes and 834.85 seconds
are independently audited and archived. The exact-package-path adapter fix
passes 50 tests and both actual saved public reports. Separately audited
saved-draw recovery completed for both public fits in 154.82 additional seconds;
both 4k/8k checkpoint gates and predictive quadrature checks passed. Original
public resource statuses remain failed, and no sampling was repeated. Full
pilot plus recovery controller cost was 989.67 seconds. This supports resource
feasibility, not an uninterrupted workflow speed ratio or endpoint accuracy.

Compact admission checks now pass diagnostically on both actual reference
outputs. Mixed parameter/predictive analysis now shares the same whole-fit
bootstrap multiplicities across all twelve endpoints; scalar/batched regression
checks cover nonzero variation and dependence. A saved-data common-grid probe
resolved its declared weighted brackets in 20 queries and 57.41 contained
seconds, with about 1.13 GB peak committed memory. This probe used only two
reference fits and six distinct normalized mixtures; it does not establish
64-fit runtime, bank accuracy, or independent-fit diversity. Its estimated
quadrature errors are not certified envelopes.

The prospective scope is 32 fresh fits per backend, with separate six-hour
fitting and two-hour analysis caps. Fresh fit and bootstrap seed audits are
archived, but no production bank has been launched. The 64-fit-shaped resource
probe completed all 40 parameter callbacks and 30,000 shared bootstrap rows in
255.74 contained seconds, with 1.54 GB peak committed memory. Its deterministic
copies of two pilot fits are not independent posterior fits and cannot supply
statistical evidence; grid construction was measured separately. Exact executed
sources and containment records passed an independent root review. Before
freezing the bank, finish reviewing and testing the integrated analysis launcher.
The analysis intent must
be frozen before any fit starts, retain all 64 terminal outcomes, and bind both
controller validation and actual output artifacts through final verification.

Two independently initialized fits per backend, fixed 8,000 retained draws and
a prospectively declared 4,000-draw prefix are a resource pilot only. They
measure fitting, serialization, compact endpoint/CDF extraction, analysis,
memory and failures. They cannot support a defensible reference-bootstrap
accuracy claim. Plan a subsequent bank with substantially more independent
fits (16-32 per backend, preferably 32) using measured costs, fresh streams and
a separate frozen budget. Keep pilot draws out of that bank.

Report the bank's achieved endpoint uncertainty and propagate its shared error
across candidate repetitions. Do not silently require the earlier proposed
.001-width precision, call overlapping bands equivalence, or treat a reference
sampler's output as exact truth. Full health diagnostics cover all 1,012 latent
and global coordinates, 14 physical functionals and four forecasts; the smaller
predeclared endpoint-accuracy family does not replace those checks.

## Market-data limit

The verified older panel offers five eligible forecasts and two outcomes at the
fixed replay origins. The September 11-18 activity-selection attempt found no
contracts passing all frozen thresholds among 536 instruments represented by
eligible first-day trades. Both outcomes remain in the evidence record. A
different data source or decision frequency requires a justified new protocol;
lowering thresholds after a failure does not make the original attempt pass.

The user has been asked which market/data access should anchor practical
evaluation. That choice remains open; computational work can proceed without
claiming that crypto trade data proves usefulness for US-listed options.

## Authoritative recent evidence

- `artifacts/optimized-mixed-comparison-v1/execution-summary.json`
- `artifacts/reference-bank-allocation-vectorized-60min-v1/OUTCOME.md`
- `IID_ENDPOINT_DIAGNOSTIC.md`
- `ANCHORED_ROLLING_REPLAY.md`
- `artifacts/deribit-activity-access-v1/OUTCOME.md`

The overall goal is not complete. Reassess this state from the artifacts rather
than treating this summary as proof that a requirement has been satisfied.
