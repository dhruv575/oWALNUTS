# Exploratory findings — 2026-10-03

These are implementation/pilot results, not a preregistered qualification.
Study scope and unresolved gates remain in `protocol.json` and `DESIGN_REVIEW.md`.

## Exact quantile-error controls

The frozen `exact-controls-200-v1` campaign completed all 7,200 cells: Normal
and Student-t(5) stationary marginals, Gaussian AR(1) dependence 0/.9/.99,
four fixed lengths and two first-pass stopping policies, with 200 independent
replicates per combination. The independent saved-record audit passes with no
missing cells or discrepancies. A lossless archive preserves all started and
terminal records, and exact worker/auditor source snapshots are retained.

Across the 48 fixed-length endpoints, empirical standard deviation divided by
RMS reported quantile MCSE ranges approximately .86-1.12. For example, Normal
rho=.9 at 8,000 draws gives 1.022 [.918,1.122] and 1.001 [.897,1.099] for the
two endpoints. These are marginal approximate bootstrap 95% intervals, not
simultaneous qualification bounds. Five of 48 fixed-length and three of 16
usable stopped-output intervals exclude one; no multiplicity adjustment was
applied. Stopped-output summaries are conditional on usability, with the full
denominators retained separately. At rho=.99, no stopped procedure passes
health requirements within the cap; finite fixed-length estimates are still
included in the estimator analysis. These results support the error estimator
on these controls, not posterior exploration, coverage calibration, or market
usefulness. See `independent-audit-v2.json` and `audit-provenance.json`.

## Fresh residual-coordinate local reliability screen

The completed `local-residual-breadth-v1` cohort has 19/24 candidate successes
and 4/6 reference successes. These are fresh prior-generated T=128 datasets,
with the observed-data starts, all-coordinate health and 2% endpoint precision
gates frozen before execution. Candidate acceptance remains .8; reference .9
was selected from earlier development failures before this cohort's outcomes.
Candidate failures 03,05,06,07,13 all miss convergence and precision at 8,000
draws despite zero divergences. Reference 05 has 10,919 divergences and fails
convergence/precision; reference 13 has 97 divergences and misses precision.

Four successful matched pairs have full driver-cost ratios
2.8978,2.3452,2.2151,2.5588 (reference/candidate). Failed pairs 05 and 13 have no
eligible ratio. All 30 attempted outcomes and costs remain included: 527.38
seconds across candidates and 284.44 across references. The completed integrity
audit passes. This is standalone exploratory reliability evidence, not a causal
comparison with the earlier centered cohort or a calibration result. The five
candidate failures preclude promoting this recipe as broadly reliable.

An exact Gaussian-conditional whitening prototype subsequently passed six
focused and ten regression tests, including normalized Gaussian controls,
generated-gradient checks and a compiled T=128 target. Its Student-t target
is unchanged. Sampling performance was then unmeasured; the separately frozen
`local-conditional-whitening-v1` development comparison retains both failed and
passing fixtures and all four sampler/coordinate combinations.

That v1 comparison was deliberately stopped for a harness defect: Windows
timeout cleanup could terminate the Python launcher while leaving its numerical
child alive. No timeout had occurred. Two residual baselines completed, the
first whitening reference was interrupted, and nine cells were not attempted.
All twelve terminal accounting records and process-stop evidence are preserved
in `local-conditional-whitening-v1`. The interrupted raw report remains unchanged.
This yields no whitening performance conclusion or eligible geometry speed ratio.
The replacement harness assigns workers to a kill-on-close Windows Job Object
before execution and verifies descendant cleanup; a new comparison must use a
new frozen plan rather than overwrite or resume the aborted experiment.

## Completed conditional-whitening comparison

The replacement `local-conditional-whitening-v2` campaign completed all twelve
prespecified cells. Its independent audit passes source, fixture, physical-start,
diagnostic, stopping, cost and process-containment checks. These three fixtures
were selected during development, so their success fractions do not estimate
population reliability. Full controller costs in seconds are:

| Fixture | oW residual | NumPyro residual | oW whitened | NumPyro whitened |
| --- | ---: | ---: | ---: | ---: |
| 00 | pass 17.05 | pass 53.02 | pass 660.32 | pass 159.60 |
| 03 | fail 36.46 | fail 65.14 | pass 220.97 | pass 41.82 |
| 05 | fail 81.90 | fail 125.79 | timeout 1800.27 | pass 47.94 |

Whitening rescues fixture 03 for both backends, but the current oW implementation
is slower on both successful whitening pairs. On fixture 05 it exhausts the
prospective 1,800-second worker budget. Its completed 1,000-draw tier is unhealthy
(scale R-hat about 1.54, bulk ESS about 7), with 999 retained maximum-depth stops
despite zero divergences. This timeout is a budgeted computational failure,
distinct from the deliberately aborted v1 harness experiment. All failure costs
remain included and comparisons involving failed arms have no speed ratio.

Candidate whitening parity checks still use the expensive unrolled JAX route,
whereas the reference uses the tested scan implementation. This is a measured
workflow cost to fix, but it cannot explain all sampling cost or poor mixing.
No hypothetical parity-cost subtraction is reported as a speed improvement.
Whitening remains experimental; continuation, target evaluation cost and kernel
work diagnostics require validation before a fresh performance comparison.

## Fresh long-path reference follow-up

On the prospectively generated T=1000/G=4 fixture in `python-flow-long-v1`,
the NumPyro continuation reference completes its declared 8,000-draw cap but
fails with nine retained divergences. All 1,012 canonical coordinate diagnostics
otherwise pass (maximum R-hat 1.000464, minimum bulk/tail ESS 14,855/17,629).
Endpoint precision alone passes from 2,000 draws; its maximum MCSE/width at
8,000 is .009208. This does not override the failed health gate. The 328.90-second
wrapper cost is a failure cost, not time to a usable result. A separately recorded
repository-search overlap also flags its timing as potentially affected by host
activity. `reference-audit.json` checks the fixture, source snapshot, fixed
adaptation and CPU affinity against the frozen plan.

The public PyMC/oWALNUTS block-32 candidate completes successfully at 8,000
draws per chain with zero divergences and maximum endpoint MCSE/width .016403
across all 14 physical functionals and four observed forecasts. Earlier tiers
at 1,000/2,000/4,000 miss precision (.044393/.035541/.024740). Its wrapper cost
is 822.94 seconds including every full restart, or 835.25 seconds including
the separate 12.31-second validation preparation. This establishes completion
of one fresh demanding case, not a speed win: the failed reference has no
eligible time-to-success ratio. A stronger reference acceptance configuration
and independent endpoint accuracy checks remain necessary.

## Computational checks

Independent Rust hand gradients versus JAX autodiff on five perturbed centered
positions agree to maximum absolute log-density error 4.98e-14 and gradient error
2.85e-14 (`artifacts/parity/report.json`). Separate finite-difference and
change-of-variable tests cover both centered and noncentered implementations.
The original crate's kernel fingerprint and sampler API suites passed 17 tests.

The ingestion tests exercise feature-time leakage, duplicate keys, missing panel
groups and held-out-data independence of scaling. Local-level prediction tests
distinguish latent uncertainty from observation noise and preserve covariance
across future horizons. These do not establish forecast calibration on markets.

## Hierarchical volatility pilot

Fixture: T=128, G=4, four chains, 1,000 warmup and 1,000 retained per chain,
exploratory seed 99061001. All arms use the same physical starts and data.
Reports: `artifacts/pilot-fair-99061001/`.

Both centered arms fail the all-coordinate convergence screen: the volatility
innovation scale is slow. Both noncentered arms pass, with zero retained
divergences. The noncentered oWALNUTS run has minimum bulk ESS about 1,100 and
maximum rank R-hat 1.00273; the noncentered NumPyro run has minimum bulk ESS about
1,455 and maximum rank R-hat 1.00308. Across the 14 reported physical functionals,
posterior means differ by at most 1.16 combined estimated MCSEs.

Observed subprocess times were about 3.24 s for oWALNUTS and 14.48 s for NumPyro.
This is **not** a qualified 4.47x speed claim: it is one exploratory fixture on a
development machine, the reference has different effective sample counts,
interval precision is not matched by a stopping rule, postprocessing and Rust
build costs are outside those process times, and binary/source attestation was
not yet enforced. It identifies a worthwhile follow-up: compare both noncentered
implementations at longer paths and multiple fresh fixtures, measuring time to
the same interval precision.

The earlier `pilot-99061001` used an unnecessary extra reference compilation and
is superseded for timing purposes. It remains as recorded history. The initial
`smoke-reference` failed in the reporting layer because of an ArviZ API mismatch;
its failure artifact remains present. Tiny smoke outputs are not convergence or
calibration evidence.

## Long-path and usable-gradient follow-ups

`artifacts/long-path-99061002` tested T=1000/G=4 with the same 1,000/1,000
four-chain budget. Native noncentered oWALNUTS passed, with zero divergences,
maximum R-hat 1.00705 and minimum bulk/tail ESS about 837/863. The initial
NumPyro noncentered implementation passed its ESS/R-hat screen but had two
retained divergences. Its 778.7-second process time versus native's 68.0 seconds
is therefore **not an eligible healthy-pair speed comparison**. The reference
used a serial AR transform, motivating an independently checked associative
prefix implementation and direct innovation priors before further timing.

The optimized reference density/gradient agrees with the original at T=8,128,1000
within 1e-12 on the tested perturbations (`optimized-reference-parity.json`).
This is an implementation optimization, not a different posterior.

`artifacts/controlled-optimized-128` adds enforced CPU-0 affinity, pinned Rust
1.88 build-source attestation, and a density-only oWALNUTS autodiff arm. All three
noncentered arms pass at T=128: optimized NumPyro, native oWALNUTS, and autodiff
oWALNUTS. Their measured process/report-inclusive times are approximately
26.80/27.43, 3.82/4.38, and 10.80/11.34 seconds, respectively; minimum bulk ESS
is about 1312,1100,834. These remain single-fixture cold timings with unmatched
endpoint precision. The new autodiff arm tests an important adoption condition:
the user supplies a compact log density instead of deriving its gradient.

The completed controlled T=1000 comparison (`controlled-optimized-1000`) gives
process/report-inclusive times of 80.10/83.34 seconds for optimized NumPyro,
66.07/69.25 for native oWALNUTS, and 216.37/219.50 for autodiff oWALNUTS.
NumPyro and native pass the diagnostic screen with zero divergences. Autodiff
has zero divergences but fails the R-hat screen (maximum 1.01211). This is a
material adoption gap: the convenient density-only path has not demonstrated
competitive performance on this long path. Effective sample counts and interval
precision differ, so the healthy native pair is not an equal-precision win.

Target microbenchmarks (`target-eval-v1`) isolated repeated per-row distribution
setup in the generic likelihood. Flattening the vector likelihood reduced
autodiff evaluation from 245–269 to 163–169 microseconds on the same saved
posterior positions, approximately 1.55x. Gradients agreed exactly and density
changed by 3.64e-12 from summation order. This target-only improvement still
needs end-to-end validation; it does not revise the historical sampling result.

The subsequent grouped `Linear` likelihood reduces the fixed-position target
cost further to 132–134 microseconds and 7,031 tape nodes. Its separately recorded
whole-fit follow-up (`grouped-ad-1000`) passes with zero divergences, maximum
R-hat 1.00399, minimum bulk/tail ESS about 1016/983, and process/report-inclusive
times 126.50/129.77 seconds. This improves the original autodiff run materially,
but remains slower than the historical optimized NumPyro run on this fixture.
These are diagnostic comparisons with unmatched endpoint precision.

The local-level T=128 application fixture (seed 99062002, four chains,
1,000 warmup and 1,000 retained draws) reverses the parameterization lesson.
Centered NumPyro/native/autodiff all pass with zero divergences; process times
are approximately 13.26/1.01/0.84 seconds, with minimum bulk ESS 695/642/559.
All three noncentered arms fail diagnostics. Therefore noncentering is a
model-dependent choice, not a universal product default. Equal-precision and
repeated-fit comparisons remain necessary before interpreting the timing gap.

The first local precision comparison passed each arm's individual checks but
failed the paired provenance audit because shared Python sources changed during
development between arms. The original results and rejection remain recorded.
A fresh shared-source follow-up with chain seed 99062003, the same fixed fixture,
and identical planned tiers [1000,2000,4000,8000] passes the strict comparison
audit (`local-precision-comparison-audit-99062003.json`). Autodiff oWALNUTS first
passes at 4,000 draws per chain, NumPyro at 8,000. Including every full restart,
diagnostics and controller invocation, times are 8.472 and 72.574 seconds,
respectively (8.57x ratio). Both satisfy the 2%-of-width endpoint-MCSE screen and
all-coordinate health gates. This is one fixed-fixture cold-start exploratory
comparison, not independent calibration or a broad speed qualification.

The dynamic-data NumPyro cohort uses three fresh prior-generated flow datasets
(99063001–99063003) and distinct chain seeds (99064001–99064003). Each fit resets
full warmup while reusing the same-shape compiled model. All pass the health
screen; engine times are 27.224,20.457,21.074 seconds and report-inclusive times
are approximately 28.004,21.169,21.817 seconds. The complete worker takes 73.815
seconds. Compilation is not separately isolated. Matching autodiff fits are
recorded separately; a warm reference timing alone does not establish a sampler
comparison.

The three matched autodiff flow fits also pass health diagnostics, with
report-inclusive times 4.470,9.465,10.488 seconds. Neither implementation meets
the 2% endpoint-MCSE/width target on any of these three fits (autodiff maxima
0.02576,0.03020,0.02640; reference 0.02906,0.02410,0.02699). Therefore this cohort
does not establish an equal-precision speed advantage. Maximum functional mean
differences are 2.21,1.71,1.92 combined estimated MCSEs. The reference ran first
as a reused process, while autodiff used separate workers; these timing scopes
and execution order remain explicit in the comparison artifact.

Qualification still needs independent datasets, fixed precision rules,
calibration, and a steady-state repeated-fit comparison so compiler startup
cannot establish the whole advantage.

## Interim breadth evidence (run still active)

The frozen `breadth-v1` plan contains 48 prior-generated datasets and 60 fits,
including 12 reference fits selected before execution. At the first independently
audited three flow comparisons, every candidate and reference reached the fixed
health and 2% endpoint-MCSE gates. Full cell-driver costs include lower tiers
that did not reach precision:

| Preselected flow fixture | AD selected draws/chain | NumPyro selected draws/chain | AD seconds | NumPyro seconds |
|---|---:|---:|---:|---:|
| 00 | 2000 | 2000 | 14.048 | 52.178 |
| 05 | 4000 | 2000 | 41.136 | 55.549 |
| 08 | 2000 | 2000 | 14.961 | 51.258 |

The first-pair and flow-05/08 audit JSON files verify sources, executables,
canonical dispersed starts, fixture identities, reported truth, precision gates
and cumulative costs. These are cold full-restart workflows, not the compilation-
reusing or adaptation-continuing Python workflows. The different selected tier
on fixture 05 illustrates why fixed-draw speed alone would misstate useful
performance. This interim subset cannot support an aggregate speed, reliability
or calibration claim; all 60 intended cells remain in the final denominator.
No source or binary is changed during this run.

## Design implications

The compiled public PyMC flow route passes independent normalized-density and
gradient checks at T=128 and T=1000. Its first practical comparison nevertheless
loses to the optimized NumPyro continuation workflow: both first pass at 2000
draws, but wrapper costs are 52.968 versus 35.341 seconds, respectively. The
candidate takes 1.499 times as long. Both check all 14 reported flow functionals
and all four observed forecasts, with identical canonical starts, fixture and
seed. The candidate compiles once but restarts warmup and sampling at each tier;
the reference warms up once and continues fixed retained batches. Existing disk
caches are retained, and candidate parity preparation is separately recorded.
This is one reused development fixture under explicitly different practical
execution policies; it does not support a Python speed advantage. The complete
audit is `artifacts/python-flow-workflow-99771001-audit.json`.

Profiling identified substantial forward/reverse Scan overhead. The tested
bounded block-prefix recurrence keeps O(T) work and automatic gradients while
reducing target-only call cost roughly fourfold at T128 and eightfold at T1000.
Block size 32 passes compiled density/gradient parity through T1000 and explicit
recurrence tests, with scalar fallback outside its declared rho range. A fresh
sampler-seed comparison on the same development dataset reverses execution order
and uses this implementation: both workflows first pass at 2000 draws, with
candidate/reference wrapper costs 17.155/36.525 seconds, or a 2.129 ratio. The
same prewarmed-cache policy applies; candidate parity preparation is separately
recorded (11.412 seconds). Including that preparation gives 28.567 candidate
seconds versus 36.525 reference seconds, a more modest 1.279 ratio. This is a
measured practical-workflow improvement on one reused
fixture, not a reliability or calibration qualification. See the independent
`python-flow-workflow-99771002-audit.json`; the original scalar loss is retained.

The separate eight-cell local experiment compares centered and observation-
residual coordinates in both public PyMC/oWALNUTS and NumPyro continuation, on
two preselected development fixtures and fresh seeds. Both centered workflows
fail both cases within the fixed cap. Residual PyMC/oWALNUTS passes both at 4000
draws (12.016 and 12.331 wrapper seconds). Residual NumPyro passes case 01 in
31.201 seconds, giving a 2.530 ratio only for that successful matched pair.
Its case 00 passes parameter diagnostics and endpoint precision but records four
retained divergences, so the overall gate fails. All centered-versus-residual
speed ratios remain null: this is a descriptive improvement in successful fits,
not a time-to-success ratio against failed runs. All eight cells and costs are
preserved in `local-residual-workflow-v1/audit.json`. Fresh prior breadth remains
necessary before selecting a broadly reliable local recipe.

The completed flow portion of `breadth-v1` has 23/24 candidate precision
successes and 6/6 prespecified reference successes. The six matched driver-cost
ratios (reference/candidate) are 3.714, 1.350, 3.426, 1.575, 1.204 and 1.900.
These are descriptive cold full-restart results, not a population speed claim.
The failed candidate, flow-22, remains in the 24-case denominator: at 8000 draws
it is healthy, but beta_bar and tau endpoint-MCSE/width ratios are .024873 and
.021651. Its 72.654 seconds are charged as an unsuccessful procedure.
Flow-19 overlaps creation of a separate Git worktree; its timing is flagged as
potentially affected by host activity and is not an isolated timing measurement.
All integrity checks in `flow-complete-audit.json` pass. The full batch is now
terminal. Local-level candidates pass 14/24 cases: nine fail convergence and
one fails precision despite healthy diagnostics. References pass 3/6 cases.
In reference pairs 00, 13 and 16, both arms fail, so their speed ratios are null.
The three successful pairs have descriptive driver-cost ratios 3.858, 4.914 and
2.938. All candidate costs (355.738 seconds) and reference costs (355.145 seconds)
remain counted, including unsuccessful attempts. The full 60-cell audit finds
no source, fixture, configuration, start, truth-field or cost discrepancies.
This is evidence against broad reliability of the current centered local recipe,
not a powered calibration result. The shared failure and follow-up trace analysis
are reviewed in `LOCAL_BREADTH_FAILURE_REVIEW.md`.

The existing public Python/JAX interface was built in an isolated Python 3.14
environment with the pinned Rust toolchain. Its adapter test and two study
target/coordinate checks pass. A T=128 local-level pilot using the same fixture,
seed 99062002, four chains and 1,000/1,000 iterations passes health diagnostics.
Its CPU-0 wrapper time is 13.062 seconds, including 0.241 seconds for the first
density call and 10.088 seconds of sampling over 130,833 target calls
(`python-jax-local-99062002`). This is close to the earlier NumPyro cold timing;
the much faster Rust generic-autodiff timing cannot be generalized to the
Python/JAX callback path. Extension binary identity is recorded, but this pilot
does not claim build attestation or equal interval precision. Existing compiled
Python model adapters are a separate adoption investigation.

That investigation found a concrete bug in the existing PyMC compiled adapter:
PyTensor can produce a finite log density with a nonfinite gradient on a coarse
proposal. The raw callback previously aborted; it now returns the established
recoverable zero-density signal, matching the ordinary callable default. Focused
tests cover invalid-domain proposals, derivative overflow, unchanged finite
values, recoverable sampling and invalid initial points. This is a Python adapter
fix; the raw ABI and sampler kernel are unchanged.

The PyMC local model uses automatically generated derivatives. Explicit float64
distribution constants restore normalized-density/gradient agreement to roughly
6.3e-13/1.6e-13 on the checked points. The fixed public path samples 130,558
target evaluations in 0.636 seconds, but that short pilot misses convergence
and is not an eligible usable-result timing.

A separate predeclared exploratory workflow pair (`best-workflow-99062004-plan.json`)
gives each framework a practical execution policy: NumPyro continues fixed-size
retained batches after one warmup; PyMC/oWALNUTS compiles its target once and
charges every full sampling restart. Continuation reproduces uninterrupted
samples bit-for-bit in tests and keeps step size and metric fixed. On the same
local fixture and fresh seed 99062004, both finish healthy but miss the 2%
endpoint precision requirement at the planned 8,000-draw cap. NumPyro's worst
ratio is 0.03256; PyMC/oWALNUTS's is 0.02286. Their wrapper costs, 75.957 and
18.176 seconds, are costs of **incomplete-to-target workflows**, not a speedup
ratio. No failed run is replaced or relabeled as passing. This illustrates why
the earlier single-fixture Rust speed result cannot establish broad reliability.

The fixed prior-Fisher geometry candidate and its mean-shear variant were
checked independently against JAX through T=1000 (12 cases; maximum density
error 3.82e-11, gradient error 1.14e-12). The matched T=128 sampling screen
(`geometry-screen-128`) then failed for all six combinations of transform and
native/autodiff/NumPyro implementation: minimum bulk ESS was only 227–280,
dominated by the innovation scale, despite zero divergences. No speed comparison
is eligible. Whitening the path at a fixed reference scale does not remove the
centered scale/path coupling. This candidate does not replace the stronger
tested noncentered flow recipe; long-path geometry benefits remain unestablished.

- Geometry matters immediately: noncentering fixes the first pilot's slow scale
  parameter in both samplers. This is evidence for a reusable model workflow,
  not yet for a kernel change.
- A small SBC smoke run cannot qualify interval calibration. Exact planning
  calculations in `calibration-power.json` show the replication cost of a
  simultaneous coverage-equivalence claim; the final scope and power remain
  to be frozen.
- No verified historical options-flow dataset has been found in the inspected
  repositories. The real-data adapter records declared provenance but cannot
  establish its authenticity. Market utility remains unmeasured.
- The existing application's price model provides a second useful fixture,
  with explicit empirical-Bayes anchor and latent-versus-observed forecast
  semantics. It must not be represented as an order-flow model.
