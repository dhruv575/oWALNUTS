# Corrected facade-level refinement factorial

The original protocol incorrectly called the preserved baseline two-level. The
research runner uses sampler::Tuning, whose default is EIGHT levels; the
lower-level walnutpie::KernelTuning default is two. Source: src/sampler.rs
DEFAULT_MAX_REFINEMENT_LEVELS. The analytic2/1 replay happened to match because
that easy case did not need deeper refinement. It was insufficient evidence of
baseline-setting identity. Preserve the original protocol, all15 runs and tests.
Do not interpret that incomplete design as a1-versus2 baseline factorial.

Correction made before terminal analysis: run explicit8/1 on all five targets
and require exact draws/calls/diagnostics versus matched_geometry01. Then run
8/1000 on all five. Combine these with already-preserved1/1 and1/1000 to form
the intended one-versus-default-eight, strict-versus-permissive comparison.
The earlier2/1000 cases remain auxiliary, not substituted for8/1000.

All previous target accuracy, resource limits, seeds, metrics, steps, full cost
accounting and no-default-change restrictions remain unchanged. Ten new bounded
workers, five exact baseline checks followed by five new treatments. A baseline
parity failure blocks interpretation of the corresponding cell. This is still
exposed diagnosis; no improvement or application claim follows automatically.
