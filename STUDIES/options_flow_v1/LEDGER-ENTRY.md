# Exploratory workflow development — 2026-10-03

Status: development and diagnostic pilots; not preregistered qualification.
No shipped sampler defaults or core kernel semantics changed.

## Scope and evidence

The study asks whether oWALNUTS makes demanding uncertainty estimation materially
easier or faster. It implements a hierarchical flow/volatility model and a
separate local-level option-price application model, with independent normalized
density checks, manual-gradient and density-only Rust arms, NumPyro controls,
physical-coordinate diagnostics and observed predictive intervals.

Pilot configurations, seeds, failures, source snapshots and measured timings
remain in immutable artifact directories. `PILOT_FINDINGS.md` explains which
comparisons are superseded and why none establishes qualification. Raw posterior
arrays stay local, with terminal-cell hashes captured by `artifact_manifest.py`.

The short flow fixture favors noncentering, while the local-level fixture favors
centering. On the controlled long flow fixture, the original autodiff arm was
slower and failed the convergence screen. Target-only vectorization and grouped
linear predictors improve its evaluation cost; whole-fit validation follows
separately. These findings motivate model implementation and geometry work,
not changes to the sampling kernel.

## Evaluation infrastructure

Build attestation binds Rust binaries to source and the pinned toolchain.
Worker affinity is enforced and recorded. Precision tiers charge all full
restarts; failed, missing and unhealthy fits remain failures. Calibration power
planning uses simultaneous exact coverage bounds, with operational usefulness
kept distinct from synthetic coverage. Historical-data adapters require explicit
feature and outcome availability, training-only scaling and rolling origins.

## Unsupported claims and next decisions

There is no demonstrated real-market predictive advantage, observed onboarding
success, powered calibration qualification, or broad equal-precision speed win.
Historical options-flow data with verified provenance is still unavailable.
Next decisions depend on completed equal-precision comparisons, repeated fits
with reference compilation reused, prior-generative difficult cases, and an
independently frozen protocol with fresh seeds before qualification evidence.

## Follow-up checkpoint — 2026-10-03

The fixed Fisher and mean-shear geometry screen failed the ESS gate in all six
T=128 arms, despite correct normalized transforms. This candidate remains
unpromoted. Canonical start matrices are now supported across every flow arm;
the breadth planner generates independently seeded dispersed starts.

The ordinary Python/JAX path passed a local-model diagnostic pilot but exposed
substantial callback cost. Testing the existing compiled PyMC interface found
and fixed a nonfinite-gradient transport failure without changing the raw ABI
or kernel (`d3e91d0`). Independent density/gradient checks and boundary-regression
tests pass.

The planned seed-99062004 comparison allows NumPyro to continue after one warmup
and PyMC/oWALNUTS to reuse compilation while charging full sampling restarts.
Both end healthy but miss the fixed 2% endpoint-MCSE threshold at 8,000 draws.
The independent audit accepts provenance and cost accounting and emits no
speed ratio. Earlier positive timing pilots remain narrowly scoped.

Validation: full study Python suite 100 passes, an additional raw-artifact
manifest test passes, Rust suite 13 passes, strict clippy passes, and the release
build is source-attested. Powered calibration and real-data usefulness remain
unestablished. The next exploratory breadth screen is designed for 24 prior
datasets per model, with six reference checks selected in advance.
