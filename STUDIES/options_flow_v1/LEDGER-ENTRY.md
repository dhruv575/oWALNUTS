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
