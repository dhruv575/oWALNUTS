# Exploratory findings — 2026-10-03

These are implementation/pilot results, not a preregistered qualification.
Study scope and unresolved gates remain in `protocol.json` and `DESIGN_REVIEW.md`.

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

## Design implications

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
